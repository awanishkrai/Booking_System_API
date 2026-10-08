from django.conf import settings
from django.db import models


class Room(models.Model):
    """A bookable room with a fixed capacity and mutable available_slots."""

    name = models.CharField(max_length=255)
    capacity = models.PositiveIntegerField()
    available_slots = models.PositiveIntegerField()

    class Meta:
        ordering = ['name']
        constraints = [
            models.CheckConstraint(
                condition=models.Q(available_slots__gte=0)
                & models.Q(available_slots__lte=models.F('capacity')),
                name='available_slots_lte_capacity',
            ),
        ]

    def __str__(self) -> str:
        return self.name


class BookingStatus(models.TextChoices):
    CONFIRMED = 'CONFIRMED', 'Confirmed'
    CANCELLED = 'CANCELLED', 'Cancelled'


class Booking(models.Model):
    """
    A single-slot reservation by a user for a room.

    * ``idempotency_key`` ensures duplicate POST requests are deduplicated.
    * ``status`` enables soft-cancel (no hard deletes → full audit trail).
    * ``date`` + ``start_time`` / ``end_time`` give time-scoped reservations.
    """

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
    idempotency_key = models.UUIDField(unique=True)
    status = models.CharField(
        max_length=12,
        choices=BookingStatus.choices,
        default=BookingStatus.CONFIRMED,
    )

    # Temporal reservation fields
    date = models.DateField(null=True, blank=True)
    start_time = models.TimeField(null=True, blank=True)
    end_time = models.TimeField(null=True, blank=True)

    booking_time = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-booking_time']
        constraints = [
            # One active booking per (room, user) combination at any time
            models.UniqueConstraint(
                fields=['room', 'user'],
                condition=models.Q(status='CONFIRMED'),
                name='unique_active_room_user_booking',
            ),
        ]

    def __str__(self) -> str:
        return f"Booking #{self.pk} by {self.user} for {self.room.name} [{self.status}]"