import json
import subprocess

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
        if url.endswith("/models"):
            return FakeResponse({"data": [{"id": "loaded-model"}]})
        if url.endswith("/api/tags"):
            return FakeResponse({"models": [{"name": "llama3.2", "size": 123}]})
        raise AssertionError(url)


class OllamaSession(FakeSession):
    def get(self, url, **kwargs):
        if url.endswith("/models"):
            return FakeResponse({"data": []})
        return super().get(url, **kwargs)


def test_lm_studio_probe_merges_loaded_and_downloaded_models(monkeypatch):
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
    assert commands == [["lms", "ls", "--llm", "--json"], ["lms", "ps", "--json"]]


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
