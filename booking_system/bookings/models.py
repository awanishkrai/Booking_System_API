from django.db import models

class Room(models.Model):
    name = models.CharField(max_length=255)
    capacity = models.PositiveIntegerField()
    available_slots = models.PositiveIntegerField()

    def __str__(self):
        return self.name

class Booking(models.Model):
    room = models.ForeignKey(Room, related_name='bookings', on_delete=models.CASCADE)
    user_name = models.CharField(max_length=255)
    booking_time = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Booking by {self.user_name} for {self.room.name}"
