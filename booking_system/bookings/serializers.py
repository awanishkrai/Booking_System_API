from rest_framework import serializers
from .models import Room, Booking


class RoomSerializer(serializers.ModelSerializer):
    class Meta:
        model = Room
        fields = ['id', 'name', 'capacity', 'available_slots']


class BookingSerializer(serializers.ModelSerializer):
    """Read-only: used for listing/displaying existing bookings."""
    user = serializers.StringRelatedField()
    room = serializers.StringRelatedField()

    class Meta:
        model = Booking
        fields = ['id', 'room', 'user', 'booking_time']


class BookingRequestSerializer(serializers.Serializer):
    """Write-only: used for creating a new booking. No user_name field —
    the user comes from request.user, never from client input."""
    room = serializers.PrimaryKeyRelatedField(queryset=Room.objects.all())
    idempotency_key = serializers.UUIDField()

    def validate_room(self, room):
        if room.available_slots <= 0:
            raise serializers.ValidationError("This room has no available slots.")
        return room