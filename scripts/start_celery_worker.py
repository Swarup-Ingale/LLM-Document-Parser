#!/usr/bin/env python3
import os
import sys

# Add the parent directory to Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.celery_app import celery_app
import logging

def start_celery_worker():
    """Start Celery worker with all queues"""
    print("Starting Celery worker...")
    print("Queues: parsing, batch, previews, exports")
    print("Broker: redis://localhost:6379/0")
    print("Result backend: redis://localhost:6379/1")
    print()
    
    # Start worker with all queues
    os.system("celery -A src.celery_app worker --loglevel=info --queues=parsing,batch,previews,exports --concurrency=4")

if __name__ == "__main__":
    start_celery_worker()