#!/bin/sh
set -e

echo "==> Waiting for PostgreSQL to be ready..."
until python -c "
import psycopg2, os, sys
try:
    psycopg2.connect(
        dbname=os.environ.get('POSTGRES_DB', 'attendance_db'),
        user=os.environ.get('POSTGRES_USER', 'attendance_user'),
        password=os.environ.get('POSTGRES_PASSWORD', 'attendance_password'),
        host=os.environ.get('POSTGRES_HOST', 'db'),
        port=os.environ.get('POSTGRES_PORT', '5432'),
    )
    print('PostgreSQL is ready!')
    sys.exit(0)
except Exception as e:
    print(f'Waiting... ({e})')
    sys.exit(1)
"; do
    sleep 2
done

echo "==> Running database migrations..."
python manage.py migrate --noinput

echo "==> Seeding default leave types and policies..."
python manage.py seed_leave_data || echo "(seed already done or skipped)"

echo "==> Starting gunicorn..."
exec gunicorn --bind 0.0.0.0:8000 --workers 2 --timeout 120 config.wsgi:application
