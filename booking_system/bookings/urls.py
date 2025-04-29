from django.urls import path
from . import views
from .views import show_queue



# URL patterns
urlpatterns = [
    path('rooms/', views.room_list, name='room_list'),
    path('bookings/<int:room_id>/', views.booking_list, name='booking_list'),
    path('processes/create/', views.create_process, name='create_process'),
    path('processes/', views.list_processes, name='list_processes'),
    path('bookings/create/', views.make_booking, name='make_booking'),
    path('scheduler/fcfs/', views.schedule_process_fcfs, name='schedule_process_fcfs'),
    path('show_queue/', views.show_queue, name='show_queue'),
]
