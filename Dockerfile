# syntax=docker/dockerfile:1
FROM python:3.12-slim AS base

# --- Build stage ---
FROM base AS builder
WORKDIR /app

# Install system dependencies for psycopg (PostgreSQL client lib)
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq-dev gcc \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

# --- Runtime stage ---
FROM base AS runtime
WORKDIR /app

# Non-root user for security
RUN useradd --create-home appuser

# Copy installed packages from builder
COPY --from=builder /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# Copy project source
COPY booking_system/ .

# Static files directory
RUN mkdir -p staticfiles && chown -R appuser:appuser /app

USER appuser

EXPOSE 8000

# Collect static files then start gunicorn
CMD ["sh", "-c", \
     "python manage.py migrate --noinput && \
      python manage.py collectstatic --noinput && \
      gunicorn booking_system.wsgi:application \
        --bind 0.0.0.0:8000 \
        --workers 4 \
        --worker-class sync \
        --timeout 30 \
        --access-logfile - \
        --error-logfile - \
        --log-level info"]
