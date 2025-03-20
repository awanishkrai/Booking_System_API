import threading
import queue
from datetime import datetime
from rest_framework import status
from rest_framework.response import Response
from rest_framework.decorators import api_view
from .models import Room, Booking
from .serializers import RoomSerializer, BookingSerializer
from django.db import transaction

# Mutex lock to prevent race conditions
room_lock = threading.Lock()

# Queue for fair scheduling of booking requests
booking_queue = queue.Queue()

@api_view(['GET'])
def room_list(request):
    rooms = Room.objects.all()
    serializer = RoomSerializer(rooms, many=True)
    return Response(serializer.data)

@api_view(['GET'])
def booking_list(request, room_id):
    bookings = Booking.objects.filter(room_id=room_id)
    serializer = BookingSerializer(bookings, many=True)
    return Response(serializer.data)


# Create a dictionary to hold semaphores for each room
room_semaphores = {}

@api_view(['POST'])
def make_booking(request):
    room_id = request.data.get('room_id')
    user_name = request.data.get('user_name')

    try:
        # Get the room object
        room = Room.objects.get(id=room_id)
        
        # Initialize the semaphore for the room if it does not exist
        if room_id not in room_semaphores:
            room_semaphores[room_id] = threading.Semaphore(room.available_slots)

        # Try to acquire the semaphore (this is the atomic part)
        if room_semaphores[room_id].acquire(blocking=False):
            # Start a database transaction to make it atomic
            with transaction.atomic():
                # Lock the room row to prevent race conditions
                room = Room.objects.select_for_update().get(id=room_id)

                # Check if the room has available slots
                if room.available_slots <= 0:
                    room_semaphores[room_id].release()  # Release semaphore if booking fails
                    return Response({"error": "Room is fully booked"}, status=status.HTTP_400_BAD_REQUEST)

                # Create the booking
                booking = Booking.objects.create(room=room, user_name=user_name)

                # Decrease the available slots
                room.available_slots -= 1
                room.save()

                # Release the semaphore (free the resource)
                room_semaphores[room_id].release()

                return Response({
                    "message": "Booking successful",
                    "room": room.name,
                    "user_name": user_name
                }, status=status.HTTP_201_CREATED)
        
        else:
            return Response({"error": "No slots available, please try again later."}, status=status.HTTP_429_TOO_MANY_REQUESTS)

    except Room.DoesNotExist:
        return Response({"error": "Room not found"}, status=status.HTTP_404_NOT_FOUND)