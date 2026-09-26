from django.urls import path
from rest_framework.authtoken.views import obtain_auth_token
from . import views

urlpatterns = [
    path('login/', obtain_auth_token, name='api_login'),
    path('register/', views.register, name='api_register'),
    path('book',views.book_room,name='book_room'),
    path('list',views.listRooms,name='listRooms'),
    path('cancel',views.cancelBooking,name='cancelBooking'),
]