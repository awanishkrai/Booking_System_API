"""
Comprehensive test suite for the Booking System API.

Coverage:
  - Auth: register, login
  - Rooms: list, detail (auth-gated)
  - Bookings: create, idempotency, duplicate prevention, slot decrement
  - Cancellation: soft-cancel, slot restoration, idempotent cancel
  - Concurrency: parallel booking stress-test (slot integrity, PostgreSQL only)
  - Permissions: unauthenticated access rejected

Notes:
  The ConcurrencyTests class is skipped when running against SQLite because
  SQLite uses file-level write locking and raises 'database table is locked'
  under concurrent access. Run against PostgreSQL in CI for concurrency tests.
"""
import unittest
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed

from django.conf import settings
from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework import status
from rest_framework.authtoken.models import Token
from rest_framework.test import APITestCase

from .models import Booking, BookingStatus, Room

User = get_user_model()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_user(username='testuser', password='Str0ng!Pass'):
    user = User.objects.create_user(username=username, password=password)
    token, _ = Token.objects.get_or_create(user=user)
    return user, token


def auth_header(token):
    return {'HTTP_AUTHORIZATION': f'Token {token.key}'}


# ---------------------------------------------------------------------------
# Auth tests
# ---------------------------------------------------------------------------

class RegisterTests(APITestCase):
    url = '/api/auth/register/'

    def test_register_success(self):
        resp = self.client.post(self.url, {
            'username': 'newuser',
            'password': 'Str0ng!Pass',
        }, format='json')
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        self.assertTrue(resp.data['success'])
        self.assertTrue(User.objects.filter(username='newuser').exists())

    def test_register_duplicate_username(self):
        User.objects.create_user(username='dup', password='Str0ng!Pass')
        resp = self.client.post(self.url, {
            'username': 'dup',
            'password': 'Str0ng!Pass',
        }, format='json')
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertFalse(resp.data['success'])

    def test_register_missing_password(self):
        resp = self.client.post(self.url, {'username': 'abc'}, format='json')
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_register_weak_password(self):
        resp = self.client.post(self.url, {
            'username': 'user2',
            'password': '123',
        }, format='json')
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_register_invalid_email(self):
        resp = self.client.post(self.url, {
            'username': 'user3',
            'email': 'not-an-email',
            'password': 'Str0ng!Pass',
        }, format='json')
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)


class LoginTests(APITestCase):
    url = '/api/auth/login/'

    def setUp(self):
        User.objects.create_user(username='loginuser', password='Str0ng!Pass')

    def test_login_success(self):
        resp = self.client.post(self.url, {
            'username': 'loginuser',
            'password': 'Str0ng!Pass',
        }, format='json')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertIn('token', resp.data)

    def test_login_wrong_password(self):
        resp = self.client.post(self.url, {
            'username': 'loginuser',
            'password': 'wrongpassword',
        }, format='json')
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)


# ---------------------------------------------------------------------------
# Room tests
# ---------------------------------------------------------------------------

class RoomTests(APITestCase):
    def setUp(self):
        self.user, self.token = make_user()
        self.room = Room.objects.create(name='Conference A', capacity=5, available_slots=5)

    def test_list_rooms_authenticated(self):
        resp = self.client.get('/api/rooms/', **auth_header(self.token))
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertTrue(resp.data['success'])
        self.assertEqual(len(resp.data['data']), 1)

    def test_list_rooms_unauthenticated(self):
        resp = self.client.get('/api/rooms/')
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_get_room_detail(self):
        resp = self.client.get(f'/api/rooms/{self.room.pk}/', **auth_header(self.token))
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data['data']['name'], 'Conference A')

    def test_get_room_not_found(self):
        resp = self.client.get('/api/rooms/9999/', **auth_header(self.token))
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)


# ---------------------------------------------------------------------------
# Booking creation tests
# ---------------------------------------------------------------------------

class BookingCreateTests(APITestCase):
    url = '/api/bookings/book/'

    def setUp(self):
        self.user, self.token = make_user()
        self.room = Room.objects.create(name='Room B', capacity=3, available_slots=3)

    def _book(self, room_id=None, idempotency_key=None, extra_headers=None):
        headers = auth_header(self.token)
        if extra_headers:
            headers.update(extra_headers)
        return self.client.post(
            self.url,
            {
                'room_id': room_id or self.room.pk,
                'idempotency_key': str(idempotency_key or uuid.uuid4()),
            },
            format='json',
            **headers,
        )

    def test_book_room_success(self):
        resp = self._book()
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        self.assertTrue(resp.data['success'])
        self.room.refresh_from_db()
        self.assertEqual(self.room.available_slots, 2)

    def test_book_unauthenticated(self):
        resp = self.client.post(self.url, {
            'room_id': self.room.pk,
            'idempotency_key': str(uuid.uuid4()),
        }, format='json')
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_idempotency_same_key_returns_existing(self):
        key = uuid.uuid4()
        resp1 = self._book(idempotency_key=key)
        resp2 = self._book(idempotency_key=key)
        self.assertEqual(resp1.status_code, status.HTTP_201_CREATED)
        self.assertEqual(resp2.status_code, status.HTTP_200_OK)
        # Slot should only be decremented once
        self.room.refresh_from_db()
        self.assertEqual(self.room.available_slots, 2)

    def test_duplicate_booking_same_room_rejected(self):
        self._book()
        resp2 = self._book()  # Same user, same room, different key
        self.assertEqual(resp2.status_code, status.HTTP_400_BAD_REQUEST)
        # Slot should still be 2 (only one booking)
        self.room.refresh_from_db()
        self.assertEqual(self.room.available_slots, 2)

    def test_fully_booked_room_rejected(self):
        room = Room.objects.create(name='Tiny', capacity=1, available_slots=0)
        resp = self.client.post(
            self.url,
            {'room_id': room.pk, 'idempotency_key': str(uuid.uuid4())},
            format='json',
            **auth_header(self.token),
        )
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_invalid_room_id(self):
        resp = self.client.post(
            self.url,
            {'room_id': 9999, 'idempotency_key': str(uuid.uuid4())},
            format='json',
            **auth_header(self.token),
        )
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_missing_room_id(self):
        resp = self.client.post(
            self.url,
            {'idempotency_key': str(uuid.uuid4())},
            format='json',
            **auth_header(self.token),
        )
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_slot_count_decrements_correctly_for_multiple_users(self):
        self.room.available_slots = 3
        self.room.save()
        users_tokens = [self.token]
        for i in range(2):
            _, t = make_user(username=f'extra{i}')
            users_tokens.append(t)

        for tok in users_tokens:
            self.client.post(
                self.url,
                {'room_id': self.room.pk, 'idempotency_key': str(uuid.uuid4())},
                format='json',
                **auth_header(tok),
            )

        self.room.refresh_from_db()
        self.assertEqual(self.room.available_slots, 0)


# ---------------------------------------------------------------------------
# Booking cancellation tests
# ---------------------------------------------------------------------------

class BookingCancelTests(APITestCase):
    cancel_url = '/api/bookings/cancel/'
    book_url = '/api/bookings/book/'

    def setUp(self):
        self.user, self.token = make_user()
        self.room = Room.objects.create(name='Room C', capacity=2, available_slots=2)
        self.key = uuid.uuid4()
        # Create a confirmed booking
        self.client.post(
            self.book_url,
            {'room_id': self.room.pk, 'idempotency_key': str(self.key)},
            format='json',
            **auth_header(self.token),
        )
        self.room.refresh_from_db()

    def test_cancel_booking_success(self):
        slots_before = self.room.available_slots
        resp = self.client.post(
            self.cancel_url,
            {'idempotency_key': str(self.key)},
            format='json',
            **auth_header(self.token),
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.room.refresh_from_db()
        self.assertEqual(self.room.available_slots, slots_before + 1)
        booking = Booking.objects.get(idempotency_key=self.key)
        self.assertEqual(booking.status, BookingStatus.CANCELLED)

    def test_cancel_idempotent(self):
        """Cancelling an already-cancelled booking returns 200 without double-restoring slots."""
        self.client.post(
            self.cancel_url,
            {'idempotency_key': str(self.key)},
            format='json',
            **auth_header(self.token),
        )
        self.room.refresh_from_db()
        slots_after_first = self.room.available_slots

        resp2 = self.client.post(
            self.cancel_url,
            {'idempotency_key': str(self.key)},
            format='json',
            **auth_header(self.token),
        )
        self.assertEqual(resp2.status_code, status.HTTP_200_OK)
        self.room.refresh_from_db()
        # Slots must NOT increase a second time
        self.assertEqual(self.room.available_slots, slots_after_first)

    def test_cancel_other_users_booking_rejected(self):
        _, other_token = make_user(username='otheruser')
        resp = self.client.post(
            self.cancel_url,
            {'idempotency_key': str(self.key)},
            format='json',
            **auth_header(other_token),
        )
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)

    def test_cancel_nonexistent_key(self):
        resp = self.client.post(
            self.cancel_url,
            {'idempotency_key': str(uuid.uuid4())},
            format='json',
            **auth_header(self.token),
        )
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)

    def test_soft_delete_booking_record_persists(self):
        self.client.post(
            self.cancel_url,
            {'idempotency_key': str(self.key)},
            format='json',
            **auth_header(self.token),
        )
        # Record must still exist in DB (soft delete)
        self.assertTrue(Booking.objects.filter(idempotency_key=self.key).exists())


# ---------------------------------------------------------------------------
# My bookings list test
# ---------------------------------------------------------------------------

class MyBookingsTests(APITestCase):
    def setUp(self):
        self.user, self.token = make_user()
        self.room = Room.objects.create(name='Room D', capacity=5, available_slots=5)

    def test_my_bookings_empty(self):
        resp = self.client.get('/api/bookings/', **auth_header(self.token))
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data['data'], [])

    def test_my_bookings_after_booking(self):
        self.client.post(
            '/api/bookings/book/',
            {'room_id': self.room.pk, 'idempotency_key': str(uuid.uuid4())},
            format='json',
            **auth_header(self.token),
        )
        resp = self.client.get('/api/bookings/', **auth_header(self.token))
        self.assertEqual(len(resp.data['data']), 1)


# ---------------------------------------------------------------------------
# Health check
# ---------------------------------------------------------------------------

class HealthCheckTest(APITestCase):
    def test_health_endpoint(self):
        resp = self.client.get('/healthz/')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.json()['status'], 'ok')


# ---------------------------------------------------------------------------
# Concurrency stress test  (PostgreSQL only)
# ---------------------------------------------------------------------------

_using_sqlite = settings.DATABASES['default']['ENGINE'] == 'django.db.backends.sqlite3'


@unittest.skipIf(_using_sqlite, 'Concurrency test requires PostgreSQL — SQLite does not support concurrent writes.')
class ConcurrencyTests(APITestCase):
    """
    Spawn N threads simultaneously booking a room with only K slots.
    Assert exactly K bookings are created and available_slots == 0.
    Requires PostgreSQL (row-level locking via select_for_update).
    """

    def test_concurrent_bookings_slot_integrity(self):
        NUM_USERS = 10
        SLOTS = 3

        room = Room.objects.create(name='StressRoom', capacity=SLOTS, available_slots=SLOTS)
        users_tokens = []
        for i in range(NUM_USERS):
            _, tok = make_user(username=f'concurrent_user_{i}')
            users_tokens.append(tok)

        results = []

        def book(tok):
            from django.test import RequestFactory  # noqa: F401 (thread-safe client)
            from rest_framework.test import APIClient
            c = APIClient()
            c.credentials(HTTP_AUTHORIZATION=f'Token {tok.key}')
            return c.post(
                '/api/bookings/book/',
                {'room_id': room.pk, 'idempotency_key': str(uuid.uuid4())},
                format='json',
            )

        with ThreadPoolExecutor(max_workers=NUM_USERS) as executor:
            futures = [executor.submit(book, tok) for tok in users_tokens]
            for f in as_completed(futures):
                results.append(f.result())

        successes = [r for r in results if r.status_code == status.HTTP_201_CREATED]
        room.refresh_from_db()

        self.assertEqual(len(successes), SLOTS,
                         f"Expected {SLOTS} successful bookings, got {len(successes)}")
        self.assertEqual(room.available_slots, 0,
                         f"Expected 0 available slots, got {room.available_slots}")
        self.assertEqual(
            Booking.objects.filter(room=room, status=BookingStatus.CONFIRMED).count(),
            SLOTS,
        )
