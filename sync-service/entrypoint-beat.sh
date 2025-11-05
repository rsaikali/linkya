#!/bin/bash
set -e

echo "Initializing local database..."
python -c "from src.database import db_manager; db_manager.init_local_db(); print('Database initialized successfully')"

echo "Starting Celery Beat..."
exec celery -A src.tasks.celery_app beat --loglevel=info
