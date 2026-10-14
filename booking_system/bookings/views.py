import logging

from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import transaction
from django.db.models import F
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response

from .models import Room, Booking, BookingStatus
from .serializers import (
    RegisterSerializer,
    RoomSerializer,
    BookingSerializer,
    BookingCreateSerializer,
    CancelBookingSerializer,
)

User = get_user_model()
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _ok(data=None, message='', status_code=status.HTTP_200_OK):
    payload = {'success': True, 'message': message}
    if data is not None:
        payload['data'] = data
    return Response(payload, status=status_code)


def _err(message, status_code=status.HTTP_400_BAD_REQUEST):
    return Response({'success': False, 'message': message}, status=status_code)


# ---------------------------------------------------------------------------
# Auth endpoints
# ---------------------------------------------------------------------------

@api_view(['POST'])
@permission_classes([AllowAny])
def register(request):
    """Create a new user account."""
    serializer = RegisterSerializer(data=request.data)
    if not serializer.is_valid():
        return _err(serializer.errors, status.HTTP_400_BAD_REQUEST)

    # Run Django's password validators explicitly
    try:
        validate_password(serializer.validated_data['password'])
    except DjangoValidationError as exc:
        return _err({'password': list(exc.messages)}, status.HTTP_400_BAD_REQUEST)

    serializer.save()
    logger.info('New user registered: %s', serializer.validated_data['username'])
    return _ok(message='User created successfully.', status_code=status.HTTP_201_CREATED)


# ---------------------------------------------------------------------------
# Room endpoints
# ---------------------------------------------------------------------------

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def list_rooms(request):
    """List all rooms with current slot availability."""
    rooms = Room.objects.all()
    return _ok(data=RoomSerializer(rooms, many=True).data)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_room(request, room_id):
    """Retrieve a single room by ID."""
    try:
        room = Room.objects.get(pk=room_id)
    except Room.DoesNotExist:
        return _err('Room not found.', status.HTTP_404_NOT_FOUND)
    return _ok(data=RoomSerializer(room).data)


# ---------------------------------------------------------------------------
# Booking endpoints
# ---------------------------------------------------------------------------

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def book_room(request):
    """
    Create a booking for the authenticated user.

    Idempotency:
    * The client supplies an ``idempotency_key`` (UUID).
    * If the key has already been seen AND the booking was successfully
      created, we return the original response.
    * If the booking attempt failed we do NOT mark the key as consumed,
      so the client can safely retry.
    """
    serializer = BookingCreateSerializer(data=request.data)
    if not serializer.is_valid():
        return _err(serializer.errors)

    idempotency_key = serializer.validated_data['idempotency_key']
    user = request.user
    room: Room = serializer.validated_data['room']

    # --- Idempotency: check whether this key was already committed ----------
    existing = Booking.objects.filter(idempotency_key=idempotency_key).first()
    if existing:
        if existing.status == BookingStatus.CONFIRMED:
            logger.info('Idempotent booking replay key=%s user=%s', idempotency_key, user)
            return _ok(
                data=BookingSerializer(existing).data,
                message='Booking already confirmed (idempotent replay).',
            )
        # If previous attempt was cancelled, let it through as a new booking
        # with the same key (edge case: caller reuses keys).

    # --- Duplicate active booking check -------------------------------------
    if Booking.objects.filter(
        room=room, user=user, status=BookingStatus.CONFIRMED
    ).exists():
        return _err('You already have an active booking for this room.')

    # --- Atomic slot decrement + booking creation ---------------------------
    try:
        with transaction.atomic():
            # Lock BOTH the room row and verify availability inside transaction
            locked_room = Room.objects.select_for_update().get(pk=room.pk)
            if locked_room.available_slots <= 0:
                return _err('Room is fully booked.', status.HTTP_409_CONFLICT)

            # Atomic in-place decrement â€” avoids stale read race condition
            Room.objects.filter(pk=room.pk).update(
                available_slots=F('available_slots') - 1
            )

            booking = Booking.objects.create(
                room=locked_room,
                user=user,
                idempotency_key=idempotency_key,
                status=BookingStatus.CONFIRMED,
                date=serializer.validated_data.get('date'),
                start_time=serializer.validated_data.get('start_time'),
                end_time=serializer.validated_data.get('end_time'),
            )

    except Exception:
        logger.exception('Booking creation failed for user=%s room=%s', user, room.pk)
        return _err('Booking failed due to a server error. Please retry.', status.HTTP_500_INTERNAL_SERVER_ERROR)

    logger.info('Booking created id=%s user=%s room=%s', booking.pk, user, room.pk)
    return _ok(
        data=BookingSerializer(booking).data,
        message='Room booked successfully.',
        status_code=status.HTTP_201_CREATED,
    )


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def cancel_booking(request):
    """
    Soft-cancel an existing booking by idempotency_key.

    The ``Booking`` row is NOT deleted â€” its status is set to CANCELLED
    and available_slots is restored atomically via F()-expression to
    prevent lost-update race conditions.
    """
    serializer = CancelBookingSerializer(data=request.data)
    if not serializer.is_valid():
        return _err(serializer.errors)

    idempotency_key = serializer.validated_data.get('idempotency_key')
    booking_id = serializer.validated_data.get('booking_id')
    user = request.user

    try:
        with transaction.atomic():
            # Lock the booking row
            filter_kwargs = {'user': user}
            if idempotency_key:
                filter_kwargs['idempotency_key'] = idempotency_key
            else:
                filter_kwargs['pk'] = booking_id

            booking = Booking.objects.select_for_update().get(**filter_kwargs)

            if booking.status == BookingStatus.CANCELLED:
                return _ok(message='Booking is already cancelled.')

            # Atomically restore the slot without reading the current value
            Room.objects.filter(pk=booking.room_id).update(
                available_slots=F('available_slots') + 1
            )

            booking.status = BookingStatus.CANCELLED
            booking.save(update_fields=['status', 'updated_at'])

    except Booking.DoesNotExist:
        return _err('Booking not found.', status.HTTP_404_NOT_FOUND)
    except Exception:
        logger.exception('Cancel failed for user=%s key=%s', user, idempotency_key)
        return _err('Cancellation failed due to a server error. Please retry.', status.HTTP_500_INTERNAL_SERVER_ERROR)

    logger.info('Booking cancelled id=%s user=%s', booking.pk, user)
    return _ok(data=BookingSerializer(booking).data, message='Booking cancelled successfully.')


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def my_bookings(request):
    """List all bookings (active and cancelled) for the authenticated user."""
    bookings = Booking.objects.filter(user=request.user).select_related('room')
    return _ok(data=BookingSerializer(bookings, many=True).data)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def room_bookings(request, room_id):
    """List all CONFIRMED bookings for a specific room."""
    try:
        room = Room.objects.get(pk=room_id)
    except Room.DoesNotExist:
        return _err('Room not found.', status.HTTP_404_NOT_FOUND)

    bookings = Booking.objects.filter(
        room=room, status=BookingStatus.CONFIRMED
    ).select_related('user')
    return _ok(data=BookingSerializer(bookings, many=True).data)
