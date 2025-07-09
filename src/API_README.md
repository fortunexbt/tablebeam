# Client Tracker Assistant REST API

## Overview

The Client Tracker Assistant REST API provides a production-ready HTTP interface for querying client and validator information. Built with FastAPI, it offers async operations, comprehensive error handling, and Kubernetes-ready health checks.

## Features

- **Health Checks**: `/health` and `/ready` endpoints for Kubernetes probes
- **Query Endpoint**: `/api/v1/query` for natural language queries about clients
- **CORS Support**: Configurable cross-origin resource sharing
- **OpenAPI Documentation**: Interactive API docs at `/docs`
- **Async Operations**: High-performance async request handling
- **Request Tracking**: X-Request-ID header support for distributed tracing
- **Comprehensive Error Handling**: Structured error responses with proper HTTP status codes
- **Metrics**: Basic metrics endpoint for monitoring

## Quick Start

### Running the Server

```bash
# Install dependencies
pip install -r requirements.txt

# Start the server (development mode)
python api_server.py

# Or with uvicorn directly
uvicorn api_server:app --reload
```

### Environment Variables

- `ENVIRONMENT`: Set to "production" for production deployment (default: "development")
- `LOG_LEVEL`: Logging level (default: "INFO")
- `OLLAMA_MODEL`: LLM model to use (default: "llama3.2")
- `OLLAMA_BASE_URL`: Ollama server URL (default: "http://localhost:11434")
- `MAX_QUERY_LENGTH`: Maximum query length in characters (default: 1000)
- `REQUEST_TIMEOUT`: Request timeout in seconds (default: 30)
- `CORS_ORIGINS`: Comma-separated list of allowed CORS origins (default: "*")
- `PORT`: Server port (default: 8000)
- `WORKERS`: Number of worker processes in production (default: 4)

### Using the API

#### Health Check
```bash
curl http://localhost:8000/health
```

#### Ready Check
```bash
curl http://localhost:8000/ready
```

#### Query Example
```bash
curl -X POST http://localhost:8000/api/v1/query \
  -H "Content-Type: application/json" \
  -d '{"question": "What clients are using Slack?"}'
```

### Python Client Example

See `api_client_example.py` for a complete client implementation. Basic usage:

```python
import asyncio
from api_client_example import ClientTrackerAPIClient

async def main():
    async with ClientTrackerAPIClient() as client:
        # Check health
        health = await client.check_health()
        print(f"Status: {health['status']}")
        
        # Query
        result = await client.query("What clients need onboarding?")
        print(f"Answer: {result['answer']}")

asyncio.run(main())
```

## API Endpoints

### GET /health
Returns service health status for liveness probes.

**Response:**
```json
{
  "status": "healthy",
  "timestamp": "2024-01-08T12:00:00",
  "environment": "development",
  "uptime_seconds": 3600.5
}
```

### GET /ready
Returns service readiness status with component checks.

**Response:**
```json
{
  "ready": true,
  "checks": {
    "vector_store": true,
    "llm_chain": true,
    "ollama_connection": true
  },
  "timestamp": "2024-01-08T12:00:00"
}
```

### POST /api/v1/query
Submit a natural language query about client information.

**Request:**
```json
{
  "question": "What clients are using Slack?",
  "context_limit": 20
}
```

**Response:**
```json
{
  "answer": "Based on the records, the following clients are using Slack...",
  "question": "What clients are using Slack?",
  "context_count": 5,
  "processing_time_ms": 245.67,
  "timestamp": "2024-01-08T12:00:00"
}
```

### GET /metrics
Returns basic service metrics.

**Response:**
```json
{
  "uptime_seconds": 3600.5,
  "environment": "production",
  "timestamp": "2024-01-08T12:00:00"
}
```

## Error Handling

All errors return structured JSON responses:

```json
{
  "error": "Validation Error",
  "detail": "Question must be between 1 and 1000 characters",
  "timestamp": "2024-01-08T12:00:00",
  "request_id": "123456789"
}
```

Common HTTP status codes:
- `200`: Success
- `422`: Validation error
- `503`: Service unavailable (not ready)
- `504`: Gateway timeout
- `500`: Internal server error

## Production Deployment

### Docker
The API is designed to work with the existing Dockerfile in the project.

### Kubernetes
The API includes health check endpoints specifically designed for Kubernetes:
- Liveness probe: `/health`
- Readiness probe: `/ready`

### Performance Tuning
- Adjust `WORKERS` environment variable for multi-process deployment
- Configure `REQUEST_TIMEOUT` based on your LLM response times
- Use a reverse proxy (nginx, traefik) for production deployments
- Enable response caching for frequently asked questions

### Security Considerations
- Configure `CORS_ORIGINS` to restrict allowed domains
- Use HTTPS in production (terminate TLS at load balancer/ingress)
- Implement rate limiting at the reverse proxy level
- Add authentication/authorization as needed
- Sanitize and validate all user inputs (already implemented)

## Monitoring

- Use the `/metrics` endpoint for basic monitoring
- Track X-Request-ID headers for distributed tracing
- Monitor application logs for errors and performance metrics
- Set up alerts based on health check failures

## Testing

Run the example client to test all endpoints:

```bash
python api_client_example.py
```

This will test health checks, readiness, and various query scenarios.