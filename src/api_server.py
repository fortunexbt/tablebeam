#!/usr/bin/env python3
"""
Production-ready REST API server for Client Tracker Assistant
Provides endpoints for health checks and querying client information.
"""

import asyncio
import logging
import os
import time
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Dict, Any, Optional, List

import uvicorn
from fastapi import FastAPI, HTTPException, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, ValidationError
from langchain_ollama.llms import OllamaLLM
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.documents import Document

from vector import get_retriever

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

# Environment configuration
ENVIRONMENT = os.getenv("ENVIRONMENT", "development")
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3.2")
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
MAX_QUERY_LENGTH = int(os.getenv("MAX_QUERY_LENGTH", "1000"))
REQUEST_TIMEOUT = int(os.getenv("REQUEST_TIMEOUT", "30"))

# Adjust logging level based on environment
logging.getLogger().setLevel(getattr(logging, LOG_LEVEL.upper()))

# Global variables for resources
retriever = None
llm_chain = None
app_start_time = None


# Pydantic models for request/response validation
class HealthResponse(BaseModel):
    status: str = Field(..., description="Health status of the service")
    timestamp: str = Field(..., description="Current timestamp")
    environment: str = Field(..., description="Current environment")
    uptime_seconds: float = Field(..., description="Service uptime in seconds")


class ReadyResponse(BaseModel):
    ready: bool = Field(..., description="Whether the service is ready to handle requests")
    checks: Dict[str, bool] = Field(..., description="Individual component readiness checks")
    timestamp: str = Field(..., description="Current timestamp")


class QueryRequest(BaseModel):
    question: str = Field(
        ..., 
        description="Question about client information",
        min_length=1,
        max_length=MAX_QUERY_LENGTH,
        example="What is the status of client XYZ?"
    )
    context_limit: Optional[int] = Field(
        default=20,
        description="Maximum number of relevant documents to retrieve",
        ge=1,
        le=50
    )


class QueryResponse(BaseModel):
    answer: str = Field(..., description="AI-generated answer to the question")
    question: str = Field(..., description="Original question asked")
    context_count: int = Field(..., description="Number of documents used for context")
    processing_time_ms: float = Field(..., description="Time taken to process the request in milliseconds")
    timestamp: str = Field(..., description="Response timestamp")


class ErrorResponse(BaseModel):
    error: str = Field(..., description="Error message")
    detail: Optional[str] = Field(None, description="Detailed error information")
    timestamp: str = Field(..., description="Error timestamp")
    request_id: Optional[str] = Field(None, description="Request tracking ID")


# Middleware for request ID tracking
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application lifecycle - startup and shutdown."""
    global retriever, llm_chain, app_start_time
    
    # Startup
    logger.info("Starting Client Tracker Assistant API Server")
    app_start_time = time.time()
    
    try:
        # Initialize retriever
        logger.info("Initializing vector store retriever...")
        retriever = get_retriever()
        logger.info("Vector store retriever initialized successfully")
        
        # Initialize LLM chain
        logger.info(f"Initializing LLM with model: {OLLAMA_MODEL}")
        model = OllamaLLM(
            model=OLLAMA_MODEL,
            base_url=OLLAMA_BASE_URL,
            timeout=REQUEST_TIMEOUT
        )
        
        template = """
        You are an expert assistant helping manage validator and client onboarding workflows.
        
        Here are some relevant client records: {records}
        
        Based on the information above, provide an informed response to the following question: {question}
        """
        prompt = ChatPromptTemplate.from_template(template)
        llm_chain = prompt | model
        logger.info("LLM chain initialized successfully")
        
    except Exception as e:
        logger.error(f"Failed to initialize services: {str(e)}")
        raise
    
    yield
    
    # Shutdown
    logger.info("Shutting down Client Tracker Assistant API Server")


# Create FastAPI app with custom configuration
app = FastAPI(
    title="Client Tracker Assistant API",
    description="REST API for querying client and validator information",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    lifespan=lifespan
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv("CORS_ORIGINS", "*").split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Request ID middleware
@app.middleware("http")
async def add_request_id(request: Request, call_next):
    """Add request ID to all requests for tracking."""
    request_id = request.headers.get("X-Request-ID", f"{time.time()}")
    request.state.request_id = request_id
    
    start_time = time.time()
    response = await call_next(request)
    process_time = time.time() - start_time
    
    response.headers["X-Request-ID"] = request_id
    response.headers["X-Process-Time"] = str(process_time)
    
    logger.info(
        f"Request {request_id} - {request.method} {request.url.path} - "
        f"Status: {response.status_code} - Time: {process_time:.3f}s"
    )
    
    return response


# Exception handlers
@app.exception_handler(ValidationError)
async def validation_exception_handler(request: Request, exc: ValidationError):
    """Handle Pydantic validation errors."""
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content=ErrorResponse(
            error="Validation Error",
            detail=str(exc),
            timestamp=datetime.utcnow().isoformat(),
            request_id=getattr(request.state, "request_id", None)
        ).dict()
    )


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    """Handle HTTP exceptions."""
    return JSONResponse(
        status_code=exc.status_code,
        content=ErrorResponse(
            error=exc.detail,
            timestamp=datetime.utcnow().isoformat(),
            request_id=getattr(request.state, "request_id", None)
        ).dict()
    )


@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    """Handle unexpected exceptions."""
    logger.error(f"Unexpected error: {str(exc)}", exc_info=True)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content=ErrorResponse(
            error="Internal Server Error",
            detail=str(exc) if ENVIRONMENT == "development" else None,
            timestamp=datetime.utcnow().isoformat(),
            request_id=getattr(request.state, "request_id", None)
        ).dict()
    )


# Health check endpoints
@app.get(
    "/health",
    response_model=HealthResponse,
    tags=["Health"],
    summary="Health check endpoint",
    description="Returns the health status of the service"
)
async def health_check():
    """Basic health check endpoint for Kubernetes liveness probe."""
    uptime = time.time() - app_start_time if app_start_time else 0
    
    return HealthResponse(
        status="healthy",
        timestamp=datetime.utcnow().isoformat(),
        environment=ENVIRONMENT,
        uptime_seconds=uptime
    )


@app.get(
    "/ready",
    response_model=ReadyResponse,
    tags=["Health"],
    summary="Readiness check endpoint",
    description="Returns whether the service is ready to handle requests"
)
async def ready_check():
    """Readiness check endpoint for Kubernetes readiness probe."""
    checks = {
        "vector_store": retriever is not None,
        "llm_chain": llm_chain is not None,
    }
    
    # Test Ollama connectivity
    try:
        if llm_chain:
            # Simple test to check if Ollama is responding
            test_response = await asyncio.wait_for(
                asyncio.to_thread(llm_chain.invoke, {"records": "test", "question": "test"}),
                timeout=5.0
            )
            checks["ollama_connection"] = True
    except Exception as e:
        logger.warning(f"Ollama connectivity check failed: {str(e)}")
        checks["ollama_connection"] = False
    
    all_ready = all(checks.values())
    
    if not all_ready:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Service not ready"
        )
    
    return ReadyResponse(
        ready=all_ready,
        checks=checks,
        timestamp=datetime.utcnow().isoformat()
    )


# Main API endpoints
@app.post(
    "/api/v1/query",
    response_model=QueryResponse,
    tags=["Query"],
    summary="Query client information",
    description="Submit a question about client or validator information and receive an AI-generated response"
)
async def query_endpoint(request: QueryRequest):
    """
    Process a question about client information.
    
    This endpoint:
    1. Retrieves relevant documents from the vector store
    2. Builds context from the retrieved documents
    3. Generates a response using the LLM
    4. Returns the answer with metadata
    """
    start_time = time.time()
    
    if not retriever or not llm_chain:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Service not fully initialized"
        )
    
    try:
        # Retrieve relevant documents
        logger.info(f"Processing query: {request.question[:100]}...")
        documents: List[Document] = await asyncio.to_thread(
            retriever.invoke, 
            request.question
        )
        
        # Limit documents if specified
        if request.context_limit:
            documents = documents[:request.context_limit]
        
        # Build context from documents
        context = "\n---\n".join([doc.page_content for doc in documents])
        
        # Generate response using LLM
        response = await asyncio.to_thread(
            llm_chain.invoke,
            {"records": context, "question": request.question}
        )
        
        # Calculate processing time
        processing_time = (time.time() - start_time) * 1000  # Convert to milliseconds
        
        logger.info(f"Query processed successfully in {processing_time:.2f}ms")
        
        return QueryResponse(
            answer=response,
            question=request.question,
            context_count=len(documents),
            processing_time_ms=processing_time,
            timestamp=datetime.utcnow().isoformat()
        )
        
    except asyncio.TimeoutError:
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail="Request timed out"
        )
    except Exception as e:
        logger.error(f"Error processing query: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to process query: {str(e)}"
        )


@app.get(
    "/",
    tags=["Info"],
    summary="API information",
    description="Returns basic information about the API"
)
async def root():
    """Root endpoint with API information."""
    return {
        "service": "Client Tracker Assistant API",
        "version": "1.0.0",
        "docs": "/docs",
        "health": "/health",
        "ready": "/ready"
    }


# Metrics endpoint (basic implementation)
@app.get(
    "/metrics",
    tags=["Monitoring"],
    summary="Basic metrics",
    description="Returns basic service metrics"
)
async def metrics():
    """Basic metrics endpoint for monitoring."""
    uptime = time.time() - app_start_time if app_start_time else 0
    
    return {
        "uptime_seconds": uptime,
        "environment": ENVIRONMENT,
        "timestamp": datetime.utcnow().isoformat()
    }


if __name__ == "__main__":
    # Configure uvicorn for production
    uvicorn.run(
        "api_server:app",
        host="0.0.0.0",
        port=int(os.getenv("PORT", "8000")),
        log_level=LOG_LEVEL.lower(),
        access_log=True,
        reload=ENVIRONMENT == "development",
        workers=1 if ENVIRONMENT == "development" else int(os.getenv("WORKERS", "4"))
    )