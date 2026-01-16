#!/usr/bin/env python3
import os
import sys
import subprocess
import time

# Add the parent directory to Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

def setup_technical_improvements():
    """Setup all technical improvements"""
    print("Setting up Technical Improvements...")
    
    # Install new dependencies
    print("1. Installing new dependencies...")
    subprocess.run([sys.executable, "-m", "pip", "install", "-r", "requirements.txt"])
    
    # Start Redis
    print("2. Starting Redis server...")
    subprocess.run(["./scripts/start_redis.sh"], shell=True)
    
    # Create additional directories
    print("3. Creating additional directories...")
    directories = [
        "data/previews",
        "data/exports", 
        "data/search_indexes",
        "logs/celery"
    ]
    
    for directory in directories:
        os.makedirs(directory, exist_ok=True)
        print(f"   Created: {directory}")
    
    # Download spaCy model if not exists
    print("4. Checking spaCy model...")
    try:
        import spacy
        spacy.load("en_core_web_sm")
        print("   ✓ spaCy model already installed")
    except:
        print("   Installing spaCy model...")
        subprocess.run([sys.executable, "-m", "spacy", "download", "en_core_web_sm"])
    
    print("\n✅ Technical Improvements setup complete!")
    print("\nNext steps:")
    print("1. Start Redis: redis-server")
    print("2. Start Celery worker: python scripts/start_celery_worker.py")
    print("3. Start API server: python scripts/start_api.py")
    print("4. Access web interface: http://localhost:5000")

if __name__ == "__main__":
    setup_technical_improvements()