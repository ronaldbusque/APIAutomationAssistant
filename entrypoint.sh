#!/bin/bash
set -e

# Create data directory if it doesn't exist
mkdir -p /app/data

# Make sure we have write access to the logs directory
mkdir -p /app/logs
chmod 777 /app/logs

# Start the application
exec uvicorn src.main:app --host 0.0.0.0 --port ${PORT:-8080} 