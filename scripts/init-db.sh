#!/bin/bash
# Wait for postgres and run migrations
set -e

echo "Waiting for database..."
until PGPASSWORD=changebook psql -h localhost -U changebook -d changebook -c '\q' 2>/dev/null; do
  sleep 1
done
echo "Database ready."

echo "Running migrations..."
cd backend && alembic upgrade head
echo "Migrations complete."
