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

# Queues and Concurrency Primitives
process_queue = queue.Queue()
processes = {}
mutex = threading.Lock()
semaphore_lock = threading.Lock()
room_semaphores = {}
pid_counter = 1

def generate_pid():
    global pid_counter
    with mutex:
        pid_counter += 1
        return pid_counter

def fcfs_scheduling():
    try:
        if not process_queue.empty():
            process = process_queue.get_nowait()
            process["status"] = "Processing"
            processes[process["pid"]]["status"] = "Processing"
            return process
        return None
    except Exception as e:
        print(f"Error in FCFS scheduling: {e}")
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
    user_name = request.data.get('user_name')
    room_id = request.data.get('room_id')
    pid = generate_pid()

    process = {
        "pid": pid,
        "name": f"Booking-{user_name}",
        "room_id": room_id,
        "user_name": user_name,
        "status": "Queued"
    }
    processes[pid] = process
    process_queue.put(process)

    return Response({"message": "Booking request queued", "process": process}, status=status.HTTP_202_ACCEPTED)

@api_view(['GET'])
def schedule_process_fcfs(request):
    process = fcfs_scheduling()
    if process:
        return Response({"message": "FCFS executed", "process": process})
    return Response({"error": "No processes in queue"}, status=status.HTTP_400_BAD_REQUEST)


def booking_worker():
    while True:
        process = fcfs_scheduling()
        if not process:
            time.sleep(1)
            continue

        pid = process["pid"]
        room_id = process.get("room_id")
        user_name = process.get("user_name")
        semaphore_acquired = False

        try:
            with semaphore_lock:
                if room_id not in room_semaphores:
                    room = Room.objects.get(id=room_id)
                    room_semaphores[room_id] = threading.Semaphore(room.available_slots)

            with transaction.atomic():
                room = Room.objects.select_for_update().get(id=room_id)

                if room.available_slots <= 0:
                    processes[pid]["status"] = "Failed - Room Full"
                    continue

                if not room_semaphores[room_id].acquire(blocking=False):
                    processes[pid]["status"] = "Failed - No Slot Available"
                    continue

                semaphore_acquired = True

                Booking.objects.create(room=room, user_name=user_name)
                room.available_slots -= 1
                room.save()
                processes[pid]["status"] = "Completed"

        except Room.DoesNotExist:
            processes[pid]["status"] = "Failed - Room Not Found"
        except Exception as e:
            processes[pid]["status"] = f"Failed - {str(e)}"
        finally:
            if semaphore_acquired and room_id in room_semaphores:
                room_semaphores[room_id].release()

@api_view(['GET'])
def show_queue(request):
    queue_data = [process for process in processes.values()]
    return Response({"queued": queue_data})

# Start the background worker thread
threading.Thread(target=booking_worker, daemon=True).start()

# Define your URL patterns
urlpatterns = [
    path('rooms/', room_list, name='room_list'),
    path('rooms/<int:room_id>/bookings/', booking_list, name='booking_list'),
    path('processes/create/', create_process, name='create_process'),
    path('processes/', list_processes, name='list_processes'),
    path('booking/create/', make_booking, name='make_booking'),
    path('process/schedule/', schedule_process_fcfs, name='schedule_process_fcfs'),
    path('queue/', show_queue, name='show_queue'),
]
