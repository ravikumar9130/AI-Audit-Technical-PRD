#!/usr/bin/env bash
set -e
# Run API and Celery worker in one container so the queue is always processed.
uvicorn main:app --host 0.0.0.0 --port 8000 &
exec celery -A workers.celery_app worker --loglevel=info --pool=prefork --concurrency=1
