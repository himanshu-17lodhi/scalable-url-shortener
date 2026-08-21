#!/bin/sh
set -e

echo "Applying database migrations..."
alembic upgrade head

echo "Starting Uvicorn application server..."
exec "$@"
