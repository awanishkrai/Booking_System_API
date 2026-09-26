from django.contrib.auth.models import User
from django.db import IntegrityError
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from .models import Room, Booking
from django.db import transaction
from django.core.cache import cache
@api_view(['POST'])
@permission_classes([AllowAny])
def register(request):
    username = request.data.get('username')
    email = request.data.get('email')
    password = request.data.get('password')

    if not username or not password:
        return Response(
            {"message": "username and password are required"},
            status=status.HTTP_400_BAD_REQUEST,
        )

    try:
        user = User.objects.create_user(
            username=username,
            email=email,
            password=password,
        )
    except IntegrityError:
        return Response(
            {"message": "username already exists"},
            status=status.HTTP_400_BAD_REQUEST,
        )

    return Response(
        {"message": "user created successfully"},
        status=status.HTTP_201_CREATED,
    )
@api_view(['POST'])
def book_room(request):
    room_id=request.data.get('room_id')
    user=request.user
    idempotency_key=request.data.get('idempotency_key')
    cache_key=f"idempotancy:{idempotency_key}"
    
    is_key= cache.add(cache_key,True,timeout=300)
    if(is_key):
        try:
            with transaction.atomic():
                room=Room.objects.select_for_update().get(id=room_id)
                booking=Booking.objects.filter(room=room,user=user).first()
                if(booking):
                    return Response(
                        {"message": "you have already booked this room"},
                        status=status.HTTP_400_BAD_REQUEST,
                    )
                if(room.available_slots>0):
                    room.available_slots-=1
                    room.save()
                    Booking.objects.create(room=room,user=user,idempotency_key=idempotency_key)
                    return Response(
                        {"message": "room booked successfully"},
                        status=status.HTTP_200_OK,
                    )
                else:
                    return Response(
                        {"message": "room is not available"},
                        status=status.HTTP_400_BAD_REQUEST,
                    )
        except Exception as e:
            return Response(
                {"message": str(e)},
                status=status.HTTP_400_BAD_REQUEST,
            ) 
    else:
        return Response(
            {"message": "request already processed"},
            status=status.HTTP_400_BAD_REQUEST,
        )  
    
    
@api_view(['GET'])
def listRooms(request):
    rooms=Room.objects.all()
    roomlist=[]
    for room in rooms:
        roomlist.append({
            "id": room.id,
            "name": room.name,
            "capacity": room.capacity,
            "available_slots": room.available_slots,
        })
    return Response(
        {"data": roomlist},
        status=status.HTTP_200_OK,
    )    

@api_view(['POST'])
def cancelBooking(request):
    idempotency_key=request.data.get("idempotency_key")
    user=request.user
    cancle_cache_key=f"cancle_idempotancy:{idempotency_key}"
    is_key=cache.add(cancle_cache_key,True,timeout=300)
    if(is_key):
        try:
            with transaction.atomic():
                booking=Booking.objects.select_for_update().get(idempotency_key=idempotency_key,user=user)
                booking.room.available_slots+=1
                booking.room.save()
                booking.delete()
                return Response(
                    {"message": "booking cancelled successfully"},
                    status=status.HTTP_200_OK,
                )
        except Exception as e:
            return Response(
                {"message": str(e)},
                status=status.HTTP_400_BAD_REQUEST,
            )
    

    
    
