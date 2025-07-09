#!/bin/bash

# API Server Startup Script
# This script starts the FastAPI server with appropriate settings

# Set default environment variables if not already set
export OLLAMA_HOST=${OLLAMA_HOST:-"http://localhost:11434"}
export VECTOR_DB_PATH=${VECTOR_DB_PATH:-"./chroma_db_clients"}
export LOG_LEVEL=${LOG_LEVEL:-"INFO"}
export API_PORT=${API_PORT:-"8080"}
export CORS_ORIGINS=${CORS_ORIGINS:-"*"}

# Determine environment
if [ "$ENVIRONMENT" = "production" ]; then
    echo "Starting API server in production mode..."
    # Use multiple workers in production
    exec uvicorn api_server:app \
        --host 0.0.0.0 \
        --port $API_PORT \
        --workers ${WORKERS:-4} \
        --log-level ${LOG_LEVEL,,} \
        --access-log
else
    echo "Starting API server in development mode..."
    # Use single worker with auto-reload in development
    exec uvicorn api_server:app \
        --host 0.0.0.0 \
        --port $API_PORT \
        --reload \
        --log-level ${LOG_LEVEL,,} \
        --access-log
fi