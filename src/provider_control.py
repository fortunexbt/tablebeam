"""Local lifecycle controls for LM Studio and Ollama.

The UI talks to both providers through their documented local interfaces. The
controller only starts local processes after an explicit user action (or the
opt-in ``AUTO_START_MODEL=1`` launcher flag); it never installs software or
downloads model weights silently.
"""

from __future__ import annotations

import json
import os
import platform
import shutil
import subprocess
from dataclasses import dataclass
from typing import Any, Callable, Optional

import requests


@dataclass(frozen=True)
class ProviderModel:
    """A model known to a local provider."""

    model_id: str
    label: str
    loaded: bool = False
    installed: bool = True
    size_bytes: Optional[int] = None


@dataclass(frozen=True)
class ProviderState:
    """A user-facing snapshot of server, CLI, and model state."""

    provider: str
    base_url: str
    server_online: bool
    models: tuple[ProviderModel, ...]
    cli_available: bool
    message: str
    error: Optional[str] = None

    @property
    def loaded_models(self) -> tuple[ProviderModel, ...]:
        return tuple(model for model in self.models if model.loaded)

    @property
    def ready(self) -> bool:
        return self.server_online and bool(self.loaded_models)


@dataclass(frozen=True)
class CommandResult:
    """Result of a safe, fixed local command."""

    ok: bool
    output: str
    error: Optional[str] = None


_BACKGROUND_JOBS: dict[str, subprocess.Popen[Any]] = {}
CommandRunner = Callable[..., subprocess.CompletedProcess[str]]


class ProviderController:
    """Control one local provider without shell interpolation."""

    def __init__(
        self,
        provider: str,
        base_url: str,
        *,
        api_key: str = "",
        session: Optional[requests.Session] = None,
        command_runner: Optional[CommandRunner] = None,
    ):
        if provider not in {"LM Studio", "Ollama"}:
            raise ValueError(f"Unsupported local provider: {provider}")
        self.provider = provider
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.session = session or requests.Session()
        self.command_runner = command_runner or subprocess.run

    @property
    def cli_name(self) -> str:
        return "lms" if self.provider == "LM Studio" else "ollama"

    @property
    def _headers(self) -> dict[str, str]:
        headers = {"Accept": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        return headers

    def _command_available(self) -> bool:
        return shutil.which(self.cli_name) is not None

    def _run(self, args: list[str], *, timeout: float = 12) -> CommandResult:
        try:
            result = self.command_runner(
                args,
                capture_output=True,
                text=True,
                timeout=timeout,
                check=False,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            return CommandResult(False, "", str(exc))
        output = (result.stdout or "").strip()
        error = (result.stderr or "").strip() or None
        return CommandResult(result.returncode == 0, output, error)

    def _start_background(self, args: list[str]) -> CommandResult:
        """Start a long-lived local process without blocking the Streamlit run."""

        try:
            process = subprocess.Popen(
                args,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True,
            )
        except OSError as exc:
            return CommandResult(False, "", str(exc))
        return CommandResult(True, f"Started {self.provider} server (pid {process.pid}).")

    def _get_json(self, url: str, *, timeout: float = 2) -> tuple[bool, Any, Optional[str]]:
        try:
            response = self.session.get(url, headers=self._headers, timeout=timeout)
            response.raise_for_status()
            return True, response.json(), None
        except requests.RequestException as exc:
            return False, {}, str(exc)
        except ValueError as exc:
            return False, {}, f"Invalid provider response: {exc}"

    def _openai_models(self) -> tuple[bool, list[str], Optional[str]]:
        ok, payload, error = self._get_json(f"{self.base_url}/models")
        if not ok:
            return False, [], error
        items = payload.get("data", []) if isinstance(payload, dict) else []
        models = [str(item["id"]) for item in items if isinstance(item, dict) and item.get("id")]
        return True, models, None

    def _ollama_models(self) -> list[ProviderModel]:
        root = self.base_url[:-3] if self.base_url.endswith("/v1") else self.base_url
        ok, payload, _ = self._get_json(f"{root}/api/tags")
        if not ok or not isinstance(payload, dict):
            return []
        models: list[ProviderModel] = []
        for item in payload.get("models", []):
            if not isinstance(item, dict) or not item.get("name"):
                continue
            models.append(
                ProviderModel(
                    model_id=str(item["name"]),
                    label=str(item["name"]),
                    installed=True,
                    size_bytes=item.get("size") if isinstance(item.get("size"), int) else None,
                )
            )
        return models

    def _lmstudio_models(self) -> tuple[list[ProviderModel], list[str]]:
        if not self._command_available():
            return [], []
        installed_result = self._run(["lms", "ls", "--llm", "--json"])
        loaded_result = self._run(["lms", "ps", "--json"])
        installed: list[ProviderModel] = []
        loaded: list[str] = []
        if installed_result.ok:
            try:
                payload = json.loads(installed_result.output)
                items = payload if isinstance(payload, list) else payload.get("models", [])
                for item in items:
                    if not isinstance(item, dict):
                        continue
                    model_id = item.get("modelKey") or item.get("path") or item.get("key")
                    if model_id:
                        installed.append(
                            ProviderModel(
                                model_id=str(model_id),
                                label=str(item.get("displayName") or model_id),
                                installed=True,
                                size_bytes=item.get("sizeBytes") if isinstance(item.get("sizeBytes"), int) else None,
                            )
                        )
            except (TypeError, ValueError, json.JSONDecodeError):
                pass
        if loaded_result.ok:
            try:
                payload = json.loads(loaded_result.output)
                items = payload if isinstance(payload, list) else payload.get("models", [])
                for item in items:
                    if isinstance(item, dict):
                        model_id = item.get("identifier") or item.get("modelKey") or item.get("path")
                        if model_id:
                            loaded.append(str(model_id))
            except (TypeError, ValueError, json.JSONDecodeError):
                pass
        return installed, loaded

    def probe(self) -> ProviderState:
        """Return server and model state without starting anything."""

        server_online, served_models, server_error = self._openai_models()
        models: dict[str, ProviderModel] = {
            model_id: ProviderModel(model_id=model_id, label=model_id, loaded=True)
            for model_id in served_models
        }
        if self.provider == "Ollama":
            for model in self._ollama_models():
                existing = models.get(model.model_id)
                models[model.model_id] = model if existing is None else ProviderModel(
                    model_id=model.model_id,
                    label=model.label,
                    loaded=existing.loaded,
                    installed=True,
                    size_bytes=model.size_bytes,
                )
        else:
            installed, loaded = self._lmstudio_models()
            for model in installed:
                existing = models.get(model.model_id)
                models[model.model_id] = model if existing is None else ProviderModel(
                    model_id=model.model_id,
                    label=model.label,
                    loaded=existing.loaded,
                    installed=True,
                    size_bytes=model.size_bytes,
                )
            for model_id in loaded:
                existing = models.get(model_id)
                models[model_id] = existing or ProviderModel(model_id=model_id, label=model_id, loaded=True)
        ordered = tuple(sorted(models.values(), key=lambda model: (not model.loaded, model.label.lower())))
        if server_online and served_models:
            message = "Server online · model ready"
        elif server_online:
            message = "Server online · load a model"
        elif self._command_available():
            message = f"{self.cli_name} found · server offline"
        else:
            message = "Provider not running"
        return ProviderState(
            provider=self.provider,
            base_url=self.base_url,
            server_online=server_online,
            models=ordered,
            cli_available=self._command_available(),
            message=message,
            error=None if server_online else server_error,
        )

    def start_server(self) -> CommandResult:
        """Start the provider server, or open its desktop app as a fallback."""

        if self._command_available():
            if self.provider == "Ollama":
                return self._start_background([self.cli_name, "serve"])
            command = [self.cli_name, "server", "start"]
            if self.provider == "LM Studio":
                port = self.base_url.rsplit(":", 1)[-1].split("/", 1)[0]
                if port.isdigit():
                    command.extend(["--port", port])
            result = self._run(command, timeout=20)
            if result.ok or self.provider != "LM Studio":
                return result
            # `lms` can be installed while its background daemon is stopped.
            # Bring that daemon up once, then retry the requested server start.
            daemon = self._run([self.cli_name, "daemon", "up"], timeout=12)
            if daemon.ok:
                return self._run(command, timeout=20)
            return result

        system = platform.system()
        if system == "Darwin":
            app_name = "LM Studio" if self.provider == "LM Studio" else "Ollama"
            try:
                subprocess.Popen(["open", "-a", app_name], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                return CommandResult(True, f"Opened {app_name}. Start its local server if it is not already running.")
            except OSError as exc:
                return CommandResult(False, "", str(exc))
        return CommandResult(False, "", f"Install {self.cli_name} or start {self.provider} manually.")

    def load_model(self, model_id: str) -> CommandResult:
        """Start a model-load/download job after the user explicitly chooses it."""

        model_id = model_id.strip()
        if not model_id:
            return CommandResult(False, "", "Choose a model first.")
        if not self._command_available():
            return CommandResult(False, "", f"Install {self.cli_name} to load models from Tablebeam.")
        command = [self.cli_name, "load", model_id] if self.provider == "LM Studio" else [self.cli_name, "pull", model_id]
        job_key = f"{self.provider}:{model_id}"
        existing = _BACKGROUND_JOBS.get(job_key)
        if existing is not None and existing.poll() is None:
            return CommandResult(True, "A model job is already running.")
        try:
            _BACKGROUND_JOBS[job_key] = subprocess.Popen(
                command,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True,
            )
        except OSError as exc:
            return CommandResult(False, "", str(exc))
        return CommandResult(True, f"Started {self.provider} model job for {model_id}.")

    def model_job(self, model_id: str) -> Optional[dict[str, Any]]:
        job = _BACKGROUND_JOBS.get(f"{self.provider}:{model_id}")
        if job is None:
            return None
        code = job.poll()
        return {"running": code is None, "returncode": code}


def provider_defaults(provider: str) -> tuple[str, str]:
    """Return the standard OpenAI-compatible URL and native CLI name."""

    if provider == "Ollama":
        return "http://localhost:11434/v1", "ollama"
    return "http://localhost:1234/v1", "lms"
