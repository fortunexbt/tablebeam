import json
import subprocess

import pytest


from provider_control import ProviderController


class FakeResponse:
    def __init__(self, payload):
        self.payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self.payload


class FakeSession:
    def get(self, url, **kwargs):
        if url.endswith("/api/v1/models"):
            return FakeResponse({"models": [
                {"type": "llm", "key": "downloaded-model", "loaded_instances": []},
                {"type": "llm", "key": "loaded-model", "loaded_instances": [{"id": "loaded-model"}]},
            ]})
        if url.endswith("/models"):
            return FakeResponse({"data": [{"id": "loaded-model"}]})
        if url.endswith("/api/tags"):
            return FakeResponse({"models": [{"name": "llama3.2", "size": 123}]})
        if url.endswith("/api/ps"):
            return FakeResponse({"models": []})
        raise AssertionError(url)


class OllamaSession(FakeSession):
    def get(self, url, **kwargs):
        if url.endswith("/models"):
            return FakeResponse({"data": []})
        return super().get(url, **kwargs)


def test_lm_studio_probe_uses_native_loaded_and_downloaded_models(monkeypatch):
    commands = []

    def runner(args, **kwargs):
        commands.append(args)
        if args[1:3] == ["ls", "--llm"]:
            return subprocess.CompletedProcess(args, 0, json.dumps({"models": [{"modelKey": "downloaded-model"}]}), "")
        return subprocess.CompletedProcess(args, 0, json.dumps({"models": [{"identifier": "loaded-model"}]}), "")

    monkeypatch.setattr("provider_control.shutil.which", lambda name: "/usr/local/bin/lms")
    state = ProviderController("LM Studio", "http://localhost:1234/v1", session=FakeSession(), command_runner=runner).probe()

    assert state.server_online is True
    assert [model.model_id for model in state.loaded_models] == ["loaded-model"]
    assert {model.model_id for model in state.models} == {"loaded-model", "downloaded-model"}
    assert commands == []  # Local CLI state must not be confused with the selected HTTP server.


def test_ollama_start_uses_documented_serve_command(monkeypatch):
    captured = []

    class FakeProcess:
        pid = 42

    def popen(args, **kwargs):
        captured.append(args)
        return FakeProcess()

    monkeypatch.setattr("provider_control.shutil.which", lambda name: "/usr/local/bin/ollama")
    monkeypatch.setattr("provider_control.subprocess.Popen", popen)
    result = ProviderController("Ollama", "http://localhost:11434/v1").start_server()

    assert result.ok is True
    assert captured == [["ollama", "serve"]]
    assert "42" in result.output


def test_lm_studio_start_recovers_when_daemon_is_stopped(monkeypatch):
    captured = []

    def runner(args, **kwargs):
        captured.append(args)
        if args[1:3] == ["server", "start"]:
            code = 1 if captured.count(["lms", "server", "start", "--port", "1234"]) == 1 else 0
            return subprocess.CompletedProcess(args, code, "", "daemon is not running" if code else "started")
        return subprocess.CompletedProcess(args, 0, "daemon started", "")

    monkeypatch.setattr("provider_control.shutil.which", lambda name: "/usr/local/bin/lms")
    result = ProviderController("LM Studio", "http://localhost:1234/v1", command_runner=runner).start_server()

    assert result.ok is True
    assert captured == [
        ["lms", "server", "start", "--port", "1234"],
        ["lms", "daemon", "up"],
        ["lms", "server", "start", "--port", "1234"],
    ]


def test_ollama_probe_uses_native_installed_model_endpoint():
    state = ProviderController("Ollama", "http://localhost:11434/v1", session=OllamaSession()).probe()

    assert state.server_online is True
    assert state.models[0].model_id == "llama3.2"


class RoutesSession:
    def __init__(self, routes):
        self.routes = routes

    def get(self, url, **kwargs):
        return FakeResponse(self.routes.get(url, {}))


def test_downloaded_lmstudio_models_and_embeddings_are_not_reported_ready():
    root = "http://localhost:1234"
    session = RoutesSession({
        f"{root}/v1/models": {"data": [{"id": "chat"}, {"id": "embedding"}]},
        f"{root}/api/v1/models": {"models": [
            {"type": "llm", "key": "chat", "loaded_instances": []},
            {"type": "embedding", "key": "embedding", "loaded_instances": [{"id": "embedding"}]},
        ]},
    })
    state = ProviderController("LM Studio", f"{root}/v1", session=session).probe()
    assert state.server_online
    assert not state.ready
    assert not state.loaded_models
    assert [model.model_id for model in state.models] == ["chat"]


def test_lmstudio_reports_the_loaded_instance_identifier():
    root = "http://host.docker.internal:1234"
    session = RoutesSession({
        f"{root}/v1/models": {"data": [{"id": "my-session-model"}]},
        f"{root}/api/v1/models": {"models": [
            {"type": "llm", "key": "publisher/model", "loaded_instances": [{"id": "my-session-model"}]},
        ]},
    })
    state = ProviderController("LM Studio", f"{root}/v1", session=session).probe()
    assert state.ready
    assert [model.model_id for model in state.ready_models] == ["my-session-model"]


def test_lmstudio_v0_fallback_preserves_memory_state():
    root = "http://localhost:1234"
    session = RoutesSession({
        f"{root}/v1/models": {"data": [{"id": "cold"}, {"id": "hot"}]},
        f"{root}/api/v0/models": {"data": [
            {"id": "cold", "type": "llm", "state": "not-loaded"},
            {"id": "hot", "type": "vlm", "state": "loaded"},
        ]},
    })
    state = ProviderController("LM Studio", f"{root}/v1", session=session).probe()
    assert [model.model_id for model in state.loaded_models] == ["hot"]


def test_ollama_installed_models_are_requestable_but_not_claimed_loaded():
    state = ProviderController("Ollama", "http://localhost:11434/v1", session=OllamaSession()).probe()
    assert state.ready
    assert not state.loaded_models
    assert [model.model_id for model in state.ready_models] == ["llama3.2"]


def test_ollama_running_state_comes_from_ps():
    root = "http://localhost:11434"
    session = RoutesSession({
        f"{root}/v1/models": {"data": [{"id": "a"}, {"id": "b"}]},
        f"{root}/api/tags": {"models": [{"name": "a"}, {"name": "b"}]},
        f"{root}/api/ps": {"models": [{"name": "b"}]},
    })
    state = ProviderController("Ollama", f"{root}/v1", session=session).probe()
    assert [model.model_id for model in state.loaded_models] == ["b"]
    assert len(state.ready_models) == 2


def test_compatible_server_models_are_available_without_local_cli_inventory(monkeypatch):
    monkeypatch.setattr("provider_control.shutil.which", lambda name: "/usr/bin/lms")
    def unexpected(*args, **kwargs):
        raise AssertionError("A remote provider must never use local CLI state")
    session = RoutesSession({"https://models.example/v1/models": {"data": [{"id": "chat"}]}})
    controller = ProviderController("LM Studio", "https://models.example/v1", session=session, command_runner=unexpected)
    state = controller.probe()
    assert state.ready
    assert not state.loaded_models
    assert not state.cli_available
    assert not controller.start_server().ok
    assert not controller.load_model("chat").ok


@pytest.mark.parametrize("payload", [{"data": None}, {"data": "bad"}, []])
def test_invalid_model_inventory_fails_cleanly(payload):
    session = RoutesSession({"http://localhost:1234/v1/models": payload})
    state = ProviderController("LM Studio", "http://localhost:1234/v1", session=session).probe()
    assert not state.ready
    assert not state.server_online
    assert "model list" in state.error


@pytest.mark.parametrize("address", [
    "http://[broken", "http://localhost:bad/v1", "http://localhost:70000/v1",
    "http://localhost:0/v1", "ftp://localhost/v1", "http://localhost/v1?bad=1",
    "http://localhost/v1#bad",
])
def test_malformed_address_cannot_start_a_local_process(address, monkeypatch):
    def unexpected(*args, **kwargs):
        raise AssertionError("Malformed addresses must not execute local commands")
    monkeypatch.setattr("provider_control.subprocess.Popen", unexpected)
    monkeypatch.setattr("provider_control.shutil.which", lambda name: "/usr/bin/lms")
    controller = ProviderController("LM Studio", address, command_runner=unexpected)
    assert not controller.controls_local_server
    assert not controller.start_server().ok
    assert not controller.load_model("chat").ok
