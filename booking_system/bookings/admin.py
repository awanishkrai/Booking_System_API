from django.contrib import admin
from .models import Room, Booking


@admin.register(Room)
class RoomAdmin(admin.ModelAdmin):
    list_display = ['id', 'name', 'capacity', 'available_slots']
    search_fields = ['name']
    list_filter = ['capacity']


@admin.register(Booking)
class BookingAdmin(admin.ModelAdmin):
    list_display = ['id', 'user', 'room', 'status', 'date', 'booking_time']
    list_filter = ['status', 'room']
    search_fields = ['user__username', 'room__name', 'idempotency_key']
    readonly_fields = ['booking_time', 'updated_at', 'idempotency_key']
    date_hierarchy = 'booking_time'
