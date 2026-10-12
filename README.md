# Booking System API

A production-grade room booking REST API built with **Django 5.1** + **Django REST Framework**.

## Features

| Feature | Status |
|---|---|
| Token authentication | ✅ |
| Idempotent booking & cancellation | ✅ |
| Soft-cancel with full audit trail | ✅ |
| Atomic slot management (F-expressions) | ✅ |
| Consistent JSON response envelope | ✅ |
| Input validation via DRF serializers | ✅ |
| Rate throttling (anon + user) | ✅ |
| Structured JSON logging | ✅ |
| Health check endpoint | ✅ |
| 27 automated tests | ✅ |
| Docker + Docker Compose | ✅ |
| GitHub Actions CI/CD | ✅ |
| PostgreSQL + Redis (production) | ✅ |

---

## Quick Start (Development)

```bash
# 1. Clone & create venv
git clone <repo-url>
cd "os project"
python -m venv venv
venv\Scripts\activate          # Windows
# source venv/bin/activate     # Linux/Mac

# 2. Install dependencies
pip install -r requirements.txt

# 3. Configure environment
copy .env.example .env         # Windows
# cp .env.example .env         # Linux/Mac
# Edit .env — set DJANGO_DEBUG=True, leave DB settings for SQLite

# 4. Migrate & run
cd booking_system
python manage.py migrate
python manage.py runserver
```

## Quick Start (Docker / Production)

```bash
# 1. Configure secrets
cp .env.example .env
# Fill in DB_PASSWORD, DJANGO_SECRET_KEY, REDIS_URL, CORS_ALLOWED_ORIGINS

# 2. Start all services
docker-compose up -d

# API available at http://localhost:8000
# Health check: http://localhost:8000/healthz/
```

---

## API Reference

All endpoints are prefixed with `/api/`.

### Auth

| Method | URL | Auth | Description |
|--------|-----|------|-------------|
| POST | `/api/auth/register/` | None | Create user account |
| POST | `/api/auth/login/` | None | Obtain auth token |

### Rooms

| Method | URL | Auth | Description |
|--------|-----|------|-------------|
| GET | `/api/rooms/` | Token | List all rooms |
| GET | `/api/rooms/<id>/` | Token | Room detail |
| GET | `/api/rooms/<id>/bookings/` | Token | Active bookings for a room |

### Bookings

| Method | URL | Auth | Description |
|--------|-----|------|-------------|
| GET | `/api/bookings/` | Token | My bookings |
| POST | `/api/bookings/book/` | Token | Book a room |
| POST | `/api/bookings/cancel/` | Token | Cancel a booking |

### Booking Request Body

```json
{
  "room_id": 1,
  "idempotency_key": "550e8400-e29b-41d4-a716-446655440000",
  "date": "2026-11-01",
  "start_time": "09:00:00",
  "end_time": "10:00:00"
}
```

### Cancel Request Body

```json
{
  "idempotency_key": "550e8400-e29b-41d4-a716-446655440000"
}
```

### Response Envelope

All responses follow a consistent envelope:

```json
{
  "success": true,
  "message": "Room booked successfully.",
  "data": { ... }
}
```

---

## Running Tests

```bash
cd booking_system
python manage.py test bookings --verbosity=2
```

---

## Environment Variables

| Variable | Default | Description |
|---|---|---|
| `DJANGO_SECRET_KEY` | insecure dev key | Secret key — **change in production** |
| `DJANGO_DEBUG` | `True` | Debug mode — set `False` in production |
| `DJANGO_ALLOWED_HOSTS` | `localhost,127.0.0.1` | Comma-separated allowed hosts |
| `DB_ENGINE` | SQLite | Django DB backend |
| `DB_NAME` | `db.sqlite3` | Database name |
| `DB_USER` | _(empty)_ | Database user |
| `DB_PASSWORD` | _(empty)_ | Database password |
| `DB_HOST` | _(empty)_ | Database host |
| `DB_PORT` | _(empty)_ | Database port |
| `REDIS_URL` | _(empty)_ | Redis URL — enables Redis cache |
| `CORS_ALLOW_ALL_ORIGINS` | `True` | **Set to `False` in production** |
| `CORS_ALLOWED_ORIGINS` | localhost origins | Comma-separated allowed origins |
