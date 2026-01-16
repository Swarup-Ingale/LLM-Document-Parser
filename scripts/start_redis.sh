#!/bin/bash
echo "Starting Redis server for Document Parser..."

# Check if Redis is already running
if redis-cli ping > /dev/null 2>&1; then
    echo "✓ Redis is already running"
else
    echo "Starting Redis server..."
    redis-server --daemonize yes --port 6379
    sleep 2
    
    if redis-cli ping > /dev/null 2>&1; then
        echo "✓ Redis server started successfully"
    else
        echo "✗ Failed to start Redis server"
        exit 1
    fi
fi

# Create necessary Redis databases
echo "Initializing Redis databases..."
redis-cli -n 0 ping > /dev/null 2>&1
redis-cli -n 1 ping > /dev/null 2>&1

echo "Redis is ready for Document Parser"
echo "  - Broker: redis://localhost:6379/0"
echo "  - Result Backend: redis://localhost:6379/1"