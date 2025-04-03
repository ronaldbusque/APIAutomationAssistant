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

# Uninstall any existing openai-agents version and then install the exact 0.0.7 version
RUN pip uninstall -y openai-agents || true
RUN pip install --no-cache-dir openai-agents==0.0.7

# Install the latest version of google-genai
RUN pip install --no-cache-dir --upgrade google-genai>=1.9.0

# Add note about import paths to avoid circular imports
RUN echo "Note: In OpenAI Agents SDK 0.0.7, the OpenAIProvider should be imported from agents.models.openai_provider, not agents.models.providers.openai" > /app/import_note.txt

# Add test script to diagnose import issues
COPY test_openai_agents.py ./
RUN python test_openai_agents.py > /app/import_test_results.txt || echo "Test completed with errors"
RUN cat /app/import_test_results.txt

# Print installed packages for debugging
RUN pip freeze | grep -E 'openai-agents|google-genai' || echo "Packages not found"

# Add test environment file for debugging
COPY test.env /app/.env

# Copy backend source code AFTER installing dependencies
COPY src/ ./src/

# Copy entrypoint script
COPY entrypoint.sh ./
RUN chmod +x /app/entrypoint.sh

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