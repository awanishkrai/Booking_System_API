from django.urls import path
from . import views

urlpatterns = [
    path('rooms/', views.room_list, name='room_list'),
    path('rooms/<int:room_id>/bookings/', views.booking_list, name='booking_list'),
    path('make_booking/', views.make_booking, name='make_booking'),
]
