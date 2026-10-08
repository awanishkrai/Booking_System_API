from django.urls import path
from rest_framework.authtoken.views import obtain_auth_token

from . import views

app_name = 'bookings'

urlpatterns = [
    # Auth
    path('auth/login/', obtain_auth_token, name='login'),
    path('auth/register/', views.register, name='register'),

    # Rooms
    path('rooms/', views.list_rooms, name='room-list'),
    path('rooms/<int:room_id>/', views.get_room, name='room-detail'),
    path('rooms/<int:room_id>/bookings/', views.room_bookings, name='room-bookings'),

    # Bookings
    path('bookings/', views.my_bookings, name='my-bookings'),
    path('bookings/book/', views.book_room, name='book-room'),
    path('bookings/cancel/', views.cancel_booking, name='cancel-booking'),
]