#!/bin/bash
set -e

echo "Starting API Automation Assistant..."

# Create data directory if it doesn't exist
mkdir -p /app/data

# Make sure we have write access to the logs directory
mkdir -p /app/logs
chmod 777 /app/logs

# Copy .env.local to .env if it exists
if [ -f /app/.env.local ]; then
    echo "Found .env.local file, copying to .env"
    cp /app/.env.local /app/.env
elif [ -f /.env.local ]; then
    echo "Found /.env.local file, copying to .env"
    cp /.env.local /app/.env
fi

# Print environment variables (excluding secrets)
echo "PORT=${PORT:-8080}"
echo "Using host: 0.0.0.0 and port: 8080"

# Start the application - explicitly binding to 0.0.0.0:8080
echo "Starting web server on 0.0.0.0:8080..."
exec uvicorn src.main:app --host 0.0.0.0 --port 8080 