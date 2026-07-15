"""Optional HTTP wrapper around the same small core used by Tablebeam."""

from __future__ import annotations

import asyncio
import os
import time
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Any, Optional

import uvicorn
from fastapi import FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from assistant_core import LocalTable, OpenAICompatibleClient, ProviderError


DATA_SOURCE = os.getenv("DATA_SOURCE", "")
MAX_QUERY_LENGTH = int(os.getenv("MAX_QUERY_LENGTH", "2000"))
table: Optional[LocalTable] = None
client: Optional[OpenAICompatibleClient] = None
started_at = time.time()


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


class QueryRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=MAX_QUERY_LENGTH)
    limit: int = Field(default=8, ge=1, le=20)


class QueryResponse(BaseModel):
    answer: str
    question: str
    sources: list[dict[str, Any]]
    processing_time_ms: float
    timestamp: str


@asynccontextmanager
async def lifespan(_: FastAPI):
    global table, client
    if DATA_SOURCE:
        table = LocalTable.from_source(DATA_SOURCE)
        client = OpenAICompatibleClient()
    yield


app = FastAPI(
    title="Tablebeam",
    description="A small local-first API for CSV and Google Sheet questions.",
    version="2.0.0",
    lifespan=lifespan,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[item.strip() for item in os.getenv("CORS_ORIGINS", "http://localhost:8501").split(",") if item.strip()],
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type", "X-Request-ID"],
)


@app.get("/health")
async def health() -> dict[str, Any]:
    return {"status": "healthy", "uptime_seconds": round(time.time() - started_at, 2), "timestamp": now()}


@app.get("/ready")
async def ready() -> dict[str, Any]:
    provider = client.status() if client else {"ready": False, "models": [], "error": "DATA_SOURCE is not configured"}
    checks = {"data_source": table is not None, "local_model": bool(provider["ready"])}
    if not all(checks.values()):
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail={"checks": checks, "provider": provider})
    return {"ready": True, "checks": checks, "provider": provider, "timestamp": now()}


@app.post("/api/v1/query", response_model=QueryResponse)
async def query(request: QueryRequest) -> QueryResponse:
    if table is None or client is None:
        raise HTTPException(status_code=503, detail="Set DATA_SOURCE and start a local model server first.")
    started = time.perf_counter()
    try:
        answer, sources = await asyncio.to_thread(client.ask, request.question, table, request.limit)
    except ProviderError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    response = QueryResponse(
        answer=answer,
        question=request.question,
        sources=[source.as_dict() for source in sources],
        processing_time_ms=round((time.perf_counter() - started) * 1000, 2),
        timestamp=now(),
    )
    return response


@app.get("/")
async def root() -> dict[str, str]:
    return {"service": "Tablebeam", "docs": "/docs", "health": "/health", "ready": "/ready"}


if __name__ == "__main__":
    uvicorn.run("api_server:app", host="0.0.0.0", port=int(os.getenv("PORT", "8000")))
