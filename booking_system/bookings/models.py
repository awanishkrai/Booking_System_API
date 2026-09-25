from django.conf import settings
from django.db import models
from django.core.exceptions import ValidationError


class Room(models.Model):
    name = models.CharField(max_length=255)
    capacity = models.PositiveIntegerField()
    available_slots = models.PositiveIntegerField()

    class Meta:
        constraints = [
            models.CheckConstraint(
                check=models.Q(available_slots__gte=0) & models.Q(available_slots__lte=models.F('capacity')),
                name='available_slots_lte_capacity',
            ),
        ]

    def __str__(self):
        return self.name


class Booking(models.Model):
    room = models.ForeignKey(
        Room,
        related_name='bookings',
        on_delete=models.CASCADE,
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        related_name='bookings',
        on_delete=models.CASCADE,
    )
    booking_time = models.DateTimeField(auto_now_add=True)
    idempotency_key = models.UUIDField(unique=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['room', 'user'],
                name='unique_room_user_booking',
            ),
        ]

    def __str__(self):
        return f"Booking by {self.user} for {self.room.name}"