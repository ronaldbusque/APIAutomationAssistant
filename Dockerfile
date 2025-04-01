# Dockerfile

# ---- Stage 1: Build Frontend Assets ----
# Use a specific Node LTS version on Alpine for smaller size
FROM node:20-alpine AS node-builder
# Set working directory
WORKDIR /app/ui
# Copy package files first for layer caching
COPY ui/package.json ui/package-lock.json ./
# Install dependencies using ci for consistency
RUN npm ci
# Copy the rest of the UI source code
COPY ui/ ./
# Build the static assets
RUN npm run build

# ---- Stage 2: Build Python Application ----
# Use a specific Python slim image matching project requirements (e.g., 3.11)
FROM python:3.11-slim AS python-app
# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    TZ=Etc/UTC \
    # Set PORT for Uvicorn (Fly.io requires 8080)
    PORT=8080 \
    # Add HOST variable to make sure we bind to all interfaces
    HOST=0.0.0.0

# Set working directory
WORKDIR /app

# Install basic utilities and Python dependencies
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt ./
RUN pip install --no-cache-dir --upgrade pip
RUN pip install --no-cache-dir -r requirements.txt

# Copy backend source code
COPY src/ ./src/

# Copy entrypoint script
COPY entrypoint.sh ./
RUN chmod +x /app/entrypoint.sh

# Create logs directory and ensure permissions
RUN mkdir -p /app/logs && chmod 777 /app/logs
RUN mkdir -p /app/data && chmod 777 /app/data

# Copy built frontend assets from the builder stage to the location FastAPI will serve
COPY --from=node-builder /app/ui/dist ./static/ui

# Expose the internal port the app runs on
EXPOSE 8080

# Command to run the application
ENTRYPOINT ["/app/entrypoint.sh"] 