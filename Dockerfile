# Multi-stage build for optimized image
FROM python:3.11-slim as builder

# Install build dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy requirements first for better caching
COPY src/requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir --user -r requirements.txt

# Final stage
FROM nvidia/cuda:12.3.1-runtime-ubuntu22.04

# Install Python and required system packages
RUN apt-get update && apt-get install -y \
    python3.11 \
    python3-pip \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user
RUN useradd -m -u 1000 appuser

# Set working directory
WORKDIR /app

# Copy Python dependencies from builder
COPY --from=builder /root/.local /home/appuser/.local

# Copy application code
COPY --chown=appuser:appuser src/ ./src/
COPY --chown=appuser:appuser README.md ./

# Create directories for model cache and chroma db
RUN mkdir -p /app/models /app/chroma_db_clients && \
    chown -R appuser:appuser /app

# Set environment variables
ENV PATH=/home/appuser/.local/bin:$PATH
ENV OLLAMA_HOST=http://localhost:11434
ENV OLLAMA_MODELS=/app/models
ENV PYTHONUNBUFFERED=1

# Switch to non-root user
USER appuser

# Default command (will be overridden by REST API)
CMD ["python3", "src/chat_interface.py"]