"""Small runtime checks for local Ollama without leaking prompts or data."""

from __future__ import annotations

import os
from typing import Any

import requests


def ollama_status(base_url: str | None = None, timeout: float = 2.0) -> dict[str, Any]:
    """Return connectivity and installed model names for the configured Ollama."""

    base_url = (base_url or os.getenv("OLLAMA_HOST", "http://localhost:11434")).rstrip("/")
    try:
        response = requests.get(f"{base_url}/api/tags", timeout=timeout)
        response.raise_for_status()
        payload = response.json()
        models = payload.get("models", []) if isinstance(payload, dict) else []
        names = [str(model.get("name")) for model in models if isinstance(model, dict) and model.get("name")]
        return {"available": True, "base_url": base_url, "models": names, "error": None}
    except requests.RequestException as exc:
        return {"available": False, "base_url": base_url, "models": [], "error": str(exc)}
    except (TypeError, ValueError) as exc:
        return {"available": False, "base_url": base_url, "models": [], "error": f"Invalid Ollama response: {exc}"}


def model_error_message(model: str, error: Exception, base_url: str | None = None) -> str:
    """Turn common local-model failures into an actionable, privacy-safe message."""

    message = str(error).lower()
    endpoint = (base_url or os.getenv("OLLAMA_HOST", "http://localhost:11434")).rstrip("/")
    if "connection" in message or "connect" in message or "refused" in message:
        return f"Ollama is not reachable at {endpoint}. Start Ollama and try again."
    if "not found" in message or "404" in message or "model" in message and "pull" in message:
        return f"The model '{model}' is not installed. Run: ollama pull {model}"
    return f"The local model could not answer safely: {error}"
