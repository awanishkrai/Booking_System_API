import threading
import queue
import time
from datetime import datetime
from rest_framework import status
from rest_framework.response import Response
from rest_framework.decorators import api_view
from django.urls import path
from .models import Room, Booking
from .serializers import RoomSerializer, BookingSerializer
from django.db import transaction, IntegrityError

@api_view(['POST'])
def register(request):
    username=request.data.get('username')
    email=request.data.get('email')
    password=request.data.get('password')

    user = User.objects.create_user(
        username=username,
        email=email,
        password=password
    )
    return Response({
        "message":"ser created successfully"
    },status=status.HTTP_201_CREATED)
    