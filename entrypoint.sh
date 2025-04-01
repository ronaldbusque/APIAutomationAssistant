#!/bin/bash
set -e

echo "Starting API Automation Assistant..."

# Create data directory if it doesn't exist
mkdir -p /app/data

# Make sure we have write access to the logs directory
mkdir -p /app/logs
chmod 777 /app/logs

# Print networking information for debugging
echo "Network interfaces:"
ip addr

# Print environment variables (excluding secrets)
echo "PORT=${PORT:-8080}"

# Start the application - explicitly binding to 0.0.0.0:8080
echo "Starting web server on 0.0.0.0:8080..."
exec uvicorn src.main:app --host 0.0.0.0 --port 8080 