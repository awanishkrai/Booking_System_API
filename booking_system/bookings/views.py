import threading
import queue
from datetime import datetime
from rest_framework import status
from rest_framework.response import Response
from rest_framework.decorators import api_view
from django.urls import path
from .models import Room, Booking
from .serializers import RoomSerializer, BookingSerializer
from django.db import transaction, IntegrityError

# OS Simulation Components
process_queue = queue.Queue()
processes = {}
mutex = threading.Lock()
semaphore = threading.Semaphore(2)  # Max 2 processes in critical section
pid_counter = 1
semaphore_lock = threading.Lock()
room_semaphores = {}

def generate_pid():
    global pid_counter
    with mutex:
        pid_counter += 1
        return pid_counter

def fcfs_scheduling():
    try:
        if not process_queue.empty():
            process = process_queue.get_nowait()  # Use get_nowait to avoid blocking
            process["status"] = "Completed"
            return process
    except queue.Empty:
        return None

@api_view(['GET'])
def room_list(request):
    rooms = Room.objects.all()
    serializer = RoomSerializer(rooms, many=True)
    return Response(serializer.data)

@api_view(['GET'])
def booking_list(request, room_id):
    try:
        bookings = Booking.objects.filter(room_id=room_id)
        serializer = BookingSerializer(bookings, many=True)
        return Response(serializer.data)
    except Room.DoesNotExist:
        return Response({"error": "Room not found"}, status=status.HTTP_404_NOT_FOUND)

@api_view(['POST'])
def create_process(request):
    pid = generate_pid()
    process = {
        "pid": pid,
        "name": f"Process-{pid}",
        "priority": 1,
        "status": "Queued"
    }
    processes[pid] = process
    process_queue.put(process)
    return Response({"message": "Process created", "process": process})

@api_view(['GET'])
def list_processes(request):
    return Response({"processes": list(processes.values())})

@api_view(['POST'])
def make_booking(request):
    room_id = request.data.get('room_id')
    user_name = request.data.get('user_name')
    semaphore_acquired = False

    try:
        with semaphore_lock:
            if room_id not in room_semaphores:
                room = Room.objects.get(id=room_id)
                room_semaphores[room_id] = threading.Semaphore(room.available_slots)

        with transaction.atomic():
            room = Room.objects.select_for_update().get(id=room_id)

            if room.available_slots <= 0:
                return Response({"error": "Room is fully booked"}, status=status.HTTP_400_BAD_REQUEST)

            if not room_semaphores[room_id].acquire(blocking=False):
                return Response({"error": "No slots available, please try again later."}, status=status.HTTP_429_TOO_MANY_REQUESTS)
            
            semaphore_acquired = True

            booking = Booking.objects.create(room=room, user_name=user_name)
            room.available_slots -= 1
            room.save()

            return Response({
                "message": "Booking successful",
                "room": room.name,
                "user_name": user_name
            }, status=status.HTTP_201_CREATED)

    except Room.DoesNotExist:
        return Response({"error": "Room not found"}, status=status.HTTP_404_NOT_FOUND)

    except IntegrityError:
        return Response({"error": "Database integrity error"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    except Exception as e:
        return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    finally:
        if semaphore_acquired and room_id in room_semaphores:
            room_semaphores[room_id].release()

@api_view(['GET'])
def schedule_process_fcfs(request):
    process = fcfs_scheduling()
    if process:
        return Response({"message": "FCFS executed", "process": process})
    return Response({"error": "No processes in queue"}, status=status.HTTP_400_BAD_REQUEST)
