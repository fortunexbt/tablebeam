"""Local lifecycle controls for LM Studio and Ollama.

The UI talks to both providers through their documented local interfaces. The
controller only starts local processes after an explicit user action (or the
opt-in ``AUTO_START_MODEL=1`` launcher flag); it never installs software or
downloads model weights silently.
"""

from __future__ import annotations

import os
import platform
import shutil
from urllib.parse import urlparse
import subprocess
from dataclasses import dataclass
from typing import Any, Callable, Optional

import requests


def valid_server_address(address: str) -> bool:
    """Accept a complete HTTP endpoint before making it actionable."""
    try:
        parsed = urlparse(address)
        return bool(parsed.scheme in {"http", "https"} and parsed.hostname
                    and not parsed.query and not parsed.fragment and parsed.port != 0)
    except ValueError:
        return False


@dataclass(frozen=True)
class ProviderModel:
    """A model known to a local provider."""

    model_id: str
    label: str
    loaded: bool = False
    installed: bool = True
    size_bytes: Optional[int] = None
    available: bool = False


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
    def ready_models(self) -> tuple[ProviderModel, ...]:
        # Some servers (notably Ollama) load installed models on request.
        return tuple(model for model in self.models if model.loaded or model.available)

    @property
    def ready(self) -> bool:
        return self.server_online and bool(self.ready_models)


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

    @property
    def native_root(self) -> str:
        return self.base_url[:-3] if self.base_url.endswith("/v1") else self.base_url

    @property
    def controls_local_server(self) -> bool:
        return valid_server_address(self.base_url) and urlparse(self.base_url).hostname in {"localhost", "127.0.0.1", "::1"}

    def _openai_models(self) -> tuple[bool, list[str], Optional[str]]:
        ok, payload, error = self._get_json(f"{self.base_url}/models")
        if not ok:
            return False, [], error
        items = payload.get("data") if isinstance(payload, dict) else None
        if not isinstance(items, list):
            return False, [], "Invalid provider response: expected a model list."
        models = [str(item["id"]) for item in items if isinstance(item, dict) and item.get("id")]
        return True, models, None

    def _ollama_models(self) -> Optional[list[ProviderModel]]:
        ok, payload, _ = self._get_json(f"{self.native_root}/api/tags")
        items = payload.get("models") if isinstance(payload, dict) else None
        if not ok or not isinstance(items, list):
            return None
        ps_ok, ps, _ = self._get_json(f"{self.native_root}/api/ps")
        running = ps.get("models", []) if ps_ok and isinstance(ps, dict) else []
        running = running if isinstance(running, list) else []
        loaded = {str(item.get("name") or item.get("model")) for item in running if isinstance(item, dict)}
        return [
            ProviderModel(
                model_id=str(item["name"]), label=str(item["name"]),
                loaded=str(item["name"]) in loaded, available=True,
                size_bytes=item.get("size") if isinstance(item.get("size"), int) else None,
            )
            for item in items if isinstance(item, dict) and item.get("name")
        ]

    def _lmstudio_models(self) -> Optional[list[ProviderModel]]:
        # OpenAI /v1/models includes downloaded models when LM Studio's JIT
        # loading is enabled. Its native API is the authority for loaded state,
        # including when Tablebeam runs in Docker or on another machine.
        ok, payload, _ = self._get_json(f"{self.native_root}/api/v1/models")
        items = payload.get("models") if isinstance(payload, dict) else None
        if ok and isinstance(items, list):
            models = []
            for item in items:
                if not isinstance(item, dict) or item.get("type") != "llm" or not item.get("key"):
                    continue
                instances = item.get("loaded_instances", [])
                instances = instances if isinstance(instances, list) else []
                identifiers = [str(instance["id"]) for instance in instances if isinstance(instance, dict) and instance.get("id")]
                label = str(item.get("display_name") or item["key"])
                if identifiers:
                    models.extend(ProviderModel(identifier, label, loaded=True) for identifier in identifiers)
                else:
                    models.append(ProviderModel(str(item["key"]), label))
            return models
        ok, payload, _ = self._get_json(f"{self.native_root}/api/v0/models")
        items = payload.get("data") if isinstance(payload, dict) else None
        if ok and isinstance(items, list) and all(isinstance(item, dict) and "state" in item for item in items):
            return [
                ProviderModel(str(item["id"]), str(item["id"]), loaded=item.get("state") == "loaded")
                for item in items if item.get("id") and item.get("type") in {"llm", "vlm"}
            ]
        return None

    def probe(self) -> ProviderState:
        """Discover requestable models without changing model/server state."""
        server_online, served_models, server_error = self._openai_models()
        native = self._ollama_models() if self.provider == "Ollama" else self._lmstudio_models()
        # A generic compatible endpoint has no native memory-state API. Its
        # advertised models are requestable, not asserted to be loaded in RAM.
        models = native if native is not None else [
            ProviderModel(model_id, model_id, available=True) for model_id in served_models
        ]
        ordered = tuple(sorted(models, key=lambda model: (not model.loaded, model.label.lower(), model.model_id)))
        ready = server_online and any(model.loaded or model.available for model in ordered)
        if ready:
            message = "Server online · model ready"
        elif server_online:
            message = "Server online · load a model"
        else:
            message = "Server offline"
        return ProviderState(
            provider=self.provider, base_url=self.base_url, server_online=server_online,
            models=ordered, cli_available=self.controls_local_server and self._command_available(),
            message=message, error=None if server_online else server_error,
        )

    def start_server(self) -> CommandResult:
        """Start the provider server, or open its desktop app as a fallback."""

        if not valid_server_address(self.base_url):
            return CommandResult(False, "", "Enter a valid http:// or https:// server address first.")
        if not self.controls_local_server:
            return CommandResult(False, "", "Start the provider on the machine hosting this server, then find models again.")
        if self._command_available():
            if self.provider == "Ollama":
                return self._start_background([self.cli_name, "serve"])
            command = [self.cli_name, "server", "start"]
            if self.provider == "LM Studio":
                port = urlparse(self.base_url).port
                if port is not None:
                    command.extend(["--port", str(port)])
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
        if not valid_server_address(self.base_url):
            return CommandResult(False, "", "Enter a valid http:// or https:// server address first.")
        if not self.controls_local_server:
            return CommandResult(False, "", "Load the model in the provider on the machine hosting this server, then find models again.")
        if not self._command_available():
            return CommandResult(False, "", f"Load the model in {self.provider}, then find models again.")
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
