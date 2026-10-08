import uuid
from rest_framework import serializers
from django.contrib.auth import get_user_model

from .models import Room, Booking, BookingStatus

User = get_user_model()


# ---------------------------------------------------------------------------
# Auth serializers
# ---------------------------------------------------------------------------

class RegisterSerializer(serializers.Serializer):
    username = serializers.CharField(max_length=150)
    email = serializers.EmailField(required=False, allow_blank=True)
    password = serializers.CharField(min_length=8, write_only=True)

    def validate_username(self, value):
        if User.objects.filter(username=value).exists():
            raise serializers.ValidationError('A user with that username already exists.')
        return value

    def create(self, validated_data):
        return User.objects.create_user(
            username=validated_data['username'],
            email=validated_data.get('email', ''),
            password=validated_data['password'],
        )


# ---------------------------------------------------------------------------
# Room serializers
# ---------------------------------------------------------------------------

class RoomSerializer(serializers.ModelSerializer):
    class Meta:
        model = Room
        fields = ['id', 'name', 'capacity', 'available_slots']


# ---------------------------------------------------------------------------
# Booking serializers
# ---------------------------------------------------------------------------

class BookingSerializer(serializers.ModelSerializer):
    """Read serializer — safe to return to the client."""
    user = serializers.StringRelatedField()
    room = RoomSerializer(read_only=True)

    class Meta:
        model = Booking
        fields = [
            'id', 'room', 'user', 'status',
            'date', 'start_time', 'end_time',
            'booking_time', 'updated_at',
        ]


class BookingCreateSerializer(serializers.Serializer):
    """Write serializer — validates booking creation input."""

    room_id = serializers.PrimaryKeyRelatedField(
        queryset=Room.objects.all(), source='room'
    )
    idempotency_key = serializers.UUIDField(default=uuid.uuid4)
    date = serializers.DateField(required=False)
    start_time = serializers.TimeField(required=False)
    end_time = serializers.TimeField(required=False)

    def validate_room_id(self, room):
        if room.available_slots <= 0:
            raise serializers.ValidationError('This room has no available slots.')
        return room

    def validate(self, attrs):
        start = attrs.get('start_time')
        end = attrs.get('end_time')
        if start and end and start >= end:
            raise serializers.ValidationError('end_time must be after start_time.')
        return attrs


class CancelBookingSerializer(serializers.Serializer):
    """Write serializer — validates booking cancellation input."""
    idempotency_key = serializers.UUIDField()