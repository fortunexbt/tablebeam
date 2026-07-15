from dataclasses import dataclass

import pandas as pd

from assistant_core import LocalTable, OpenAICompatibleClient


def test_local_search_is_deterministic_and_returns_citations():
    table = LocalTable(pd.DataFrame({"company": ["Acme", "Beta"], "status": ["Active", "Churned"]}))
    sources = table.search("What is Acme status?")
    assert sources[0].row_number == 1
    assert sources[0].citation == "[Source 1]"


def test_numeric_summary_is_deterministic_and_prompt_ready():
    table = LocalTable(pd.DataFrame({"company": ["Acme", "Beta"], "revenue": [10, 30]}))
    summary = table.numeric_summary()
    assert summary.loc[0, "mean"] == 20.0
    assert "Numeric summary" in table.prompt_profile()


@dataclass
class FakeResponse:
    payload: dict

    def raise_for_status(self):
        return None

    def json(self):
        return self.payload


class FakeSession:
    def get(self, url, **kwargs):
        return FakeResponse({"data": [{"id": "local-model"}]})

    def post(self, url, **kwargs):
        assert url.endswith("/chat/completions")
        assert "[Source 1]" in kwargs["json"]["messages"][1]["content"]
        assert "Numeric summary" in kwargs["json"]["messages"][1]["content"]
        return FakeResponse({"choices": [{"message": {"content": "Acme is active [Source 1]."}}]})


def test_openai_compatible_client_works_with_lm_studio_shape():
    table = LocalTable(pd.DataFrame({"company": ["Acme"], "status": ["Active"], "revenue": [10]}))
    client = OpenAICompatibleClient(base_url="http://localhost:1234/v1", model="auto", session=FakeSession())
    answer, sources = client.ask("What is Acme status?", table)
    assert answer == "Acme is active [Source 1]."
    assert sources[0].content.startswith("row_number=1")
