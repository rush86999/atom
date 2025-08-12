#!/bin/bash
uvicorn workflows.main:app --host 0.0.0.0 --port 8003 &
celery -A workflows.celery_app worker --loglevel=info
