import asyncio

import pandas as pd
import pytest
from fastapi.testclient import TestClient

import api_server
from assistant_core import LocalTable, ProviderError


class FakeProvider:
    def __init__(self):
        self.ready = True
        self.error = None
        self.calls = []

    def status(self):
        # Synchronous provider I/O must run outside the API's event loop.
        with pytest.raises(RuntimeError, match="no running event loop"):
            asyncio.get_running_loop()
        return {
            "ready": self.ready,
            "models": ["test-model"] if self.ready else [],
            "error": None if self.ready else "No model loaded",
        }

    def ask(self, question, table, limit):
        self.calls.append((question, table, limit))
        if self.error:
            raise self.error
        return "Acme is active [Source 1].", table.search(question, limit=limit)


@pytest.fixture
def api(monkeypatch):
    # Ignore any developer's DATA_SOURCE and local model configuration.
    monkeypatch.setattr(api_server, "DATA_SOURCE", "")
    monkeypatch.setattr(api_server, "table", None)
    monkeypatch.setattr(api_server, "client", None)
    with TestClient(api_server.app) as http:
        yield http


@pytest.fixture
def configured(api, monkeypatch):
    table = LocalTable(pd.DataFrame({"company": ["Beta", "Acme"], "status": ["Churned", "Active"]}))
    provider = FakeProvider()
    monkeypatch.setattr(api_server, "table", table)
    monkeypatch.setattr(api_server, "client", provider)
    return api, table, provider


def test_health_does_not_require_data_or_a_model(api):
    response = api.get("/health")

    assert response.status_code == 200
    assert response.json()["status"] == "healthy"
    assert response.json()["uptime_seconds"] >= 0
    assert response.json()["timestamp"]


def test_query_requires_configured_data(api):
    response = api.post("/api/v1/query", json={"question": "What is Acme status?"})

    assert response.status_code == 503
    assert "DATA_SOURCE" in response.json()["detail"]


@pytest.mark.parametrize("question", ["", "   ", "\t\n", "x" * (api_server.MAX_QUERY_LENGTH + 1)])
def test_query_rejects_invalid_questions_before_calling_provider(configured, question):
    api, _, provider = configured

    response = api.post("/api/v1/query", json={"question": question})

    assert response.status_code == 422
    assert provider.calls == []


@pytest.mark.parametrize("limit", [0, 21])
def test_query_rejects_invalid_source_limits(configured, limit):
    api, _, provider = configured

    response = api.post("/api/v1/query", json={"question": "Acme", "limit": limit})

    assert response.status_code == 422
    assert provider.calls == []


def test_query_trims_question_and_preserves_source_provenance(configured):
    api, table, provider = configured

    response = api.post("/api/v1/query", json={"question": "  What is Acme status?\n", "limit": 1})

    assert response.status_code == 200
    payload = response.json()
    assert payload["question"] == "What is Acme status?"
    assert payload["answer"] == "Acme is active [Source 1]."
    assert payload["sources"] == [{
        "citation": "[Source 1]",
        "row_number": 2,
        "content": "row_number=2; company: Acme; status: Active",
    }]
    assert payload["processing_time_ms"] >= 0
    assert payload["timestamp"]
    assert provider.calls == [("What is Acme status?", table, 1)]


@pytest.mark.parametrize(
    ("error", "status_code"),
    [(ProviderError("Model unavailable"), 502), (ValueError("Question exceeds the context limit"), 422)],
)
def test_query_maps_provider_and_core_validation_errors(configured, error, status_code):
    api, _, provider = configured
    provider.error = error

    response = api.post("/api/v1/query", json={"question": "What is Acme status?"})

    assert response.status_code == status_code
    assert response.json()["detail"] == str(error)


def test_readiness_reports_missing_configuration(api):
    response = api.get("/ready")

    assert response.status_code == 503
    detail = response.json()["detail"]
    assert detail["checks"] == {"data_source": False, "local_model": False}
    assert detail["provider"]["ready"] is False


def test_readiness_checks_provider_outside_event_loop(configured):
    api, _, _ = configured

    response = api.get("/ready")

    assert response.status_code == 200
    assert response.json()["ready"] is True
    assert response.json()["checks"] == {"data_source": True, "local_model": True}
    assert response.json()["provider"]["models"] == ["test-model"]


def test_readiness_reports_unavailable_provider(configured):
    api, _, provider = configured
    provider.ready = False

    response = api.get("/ready")

    assert response.status_code == 503
    detail = response.json()["detail"]
    assert detail["checks"] == {"data_source": True, "local_model": False}
    assert detail["provider"]["error"] == "No model loaded"
