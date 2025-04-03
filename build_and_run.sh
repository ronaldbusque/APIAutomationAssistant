#!/bin/bash
# Script to build and run the Docker container with OpenAI agents SDK v0.0.7
# and the fixed agent_setup.py module to avoid circular imports

# Stop any existing containers
docker stop api-automation-assistant 2>/dev/null || true
docker rm api-automation-assistant 2>/dev/null || true

# Build the Docker image
echo "Building Docker image with OpenAI agents SDK v0.0.7..."
echo "Fixed import path: Using agents.models.openai_provider for v0.0.7"
echo "Using agent_setup.py to avoid circular imports with the agents package"
docker build -t api-automation-assistant .

# Run the container with appropriate environment variables
echo "Running Docker container..."
docker run --name api-automation-assistant -p 8080:8080 \
  -e GOOGLE_API_KEY="replace-with-your-actual-key" \
  -e OPENAI_API_KEY="replace-with-your-actual-key" \
  api-automation-assistant

echo "Container started. Access the application at http://localhost:8080" 