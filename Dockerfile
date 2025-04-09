# Dockerfile

# ---- Stage 1: Build Frontend Assets ----
# Use a specific Node LTS version on Alpine for smaller size
FROM node:20-alpine AS node-builder
# Set working directory for the UI
WORKDIR /app
# Copy the entire UI directory first
COPY ui/ ./ui/
# Set working directory to UI folder
WORKDIR /app/ui
# Install dependencies
RUN npm ci
# Build the UI
RUN npm run build
# List the build output to verify it was created correctly
RUN ls -la dist

# ---- Stage 2: Build Python Application ----
# Use a specific Python slim image matching project requirements (e.g., 3.11)
FROM python:3.11-slim AS python-app
# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    TZ=Etc/UTC \
    # Set PORT for Uvicorn (Fly.io requires 8080)
    PORT=8080 \
    # Add HOST variable to make sure we bind to all interfaces
    HOST=0.0.0.0 \
    # Default to empty tokens for safety
    ACCESS_TOKENS='{"example_user": "example_token"}' \
    ADMIN_TOKEN='example_admin_token'

# Set working directory
WORKDIR /app

# Install basic utilities and Python dependencies
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    curl \
    dos2unix \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt ./
RUN pip install --no-cache-dir --upgrade pip
RUN pip install --no-cache-dir -r requirements.txt

# Copy environment file (if exists, otherwise use example)
COPY .env* ./
# Ensure .env exists (copy from example if needed)
RUN if [ ! -f .env ]; then \
    if [ -f .env.local ]; then \
      cp .env.local .env; \
    elif [ -f .env.example ]; then \
      cp .env.example .env; \
    fi \
  fi

# Copy backend source code
COPY src/ ./src/

# Copy entrypoint script and fix line endings
COPY entrypoint.sh ./
# Fix line endings (converts CRLF to LF)
RUN dos2unix /app/entrypoint.sh && chmod +x /app/entrypoint.sh

# Create logs directory and ensure permissions
RUN mkdir -p /app/logs && chmod 777 /app/logs
RUN mkdir -p /app/data && chmod 777 /app/data

# Create static directory for UI
RUN mkdir -p /app/static/ui

# Copy built frontend assets from the builder stage to the location FastAPI will serve
COPY --from=node-builder /app/ui/dist/ /app/static/ui/
RUN ls -la /app/static/ui/

# Expose the internal port the app runs on
EXPOSE 8080

# Command to run the application
ENTRYPOINT ["/app/entrypoint.sh"] 