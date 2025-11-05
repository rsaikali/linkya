#!/bin/bash
set -e

echo "Initializing NILM database tables..."
python -c "from src.database import db_manager; db_manager.init_tables(); print('NILM database initialized successfully')"

echo "Starting Celery Beat..."
exec celery -A src.tasks.celery_app beat --loglevel=info
