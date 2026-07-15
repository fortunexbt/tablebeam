"""The small, provider-neutral core used by both the web app and API.

There is intentionally no vector database or model-specific SDK here. Rows are
searched locally with a deterministic lexical ranker, then sent to any local
server that implements the OpenAI-compatible API (LM Studio or Ollama).
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from io import BytesIO
from typing import Any, Optional

import pandas as pd
import requests

from data_pipeline import DataProfile, load_data, normalize_dataframe, profile_dataframe, profile_for_prompt


TOKEN_RE = re.compile(r"[\w'-]+", re.UNICODE)
STOPWORDS = {
    "a", "about", "and", "are", "can", "do", "does", "for", "from", "how",
    "in", "is", "me", "of", "on", "please", "show", "the", "to", "what",
    "which", "with", "would", "you", "your",
}


@dataclass(frozen=True)
class RowSource:
    """A source row that can be displayed and cited in an answer."""

    citation: str
    row_number: int
    content: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "citation": self.citation,
            "row_number": self.row_number,
            "content": self.content,
        }


class ProviderError(RuntimeError):
    """A local OpenAI-compatible provider could not answer."""


class LocalTable:
    """Validated table plus a tiny deterministic local search index."""

    def __init__(self, dataframe: pd.DataFrame):
        self.dataframe = normalize_dataframe(dataframe)
        self.profile: DataProfile = profile_dataframe(self.dataframe)
        self._rows = [self._format_row(index, row) for index, row in self.dataframe.iterrows()]

    @classmethod
    def from_source(cls, source: str) -> "LocalTable":
        return cls(load_data(source))

    @classmethod
    def from_csv_bytes(cls, content: bytes) -> "LocalTable":
        try:
            frame = pd.read_csv(BytesIO(content), encoding="utf-8-sig", on_bad_lines="error")
        except (UnicodeDecodeError, pd.errors.ParserError, ValueError) as exc:
            raise ValueError(f"Could not read CSV: {exc}") from exc
        return cls(frame)

    def _format_row(self, index: Any, row: pd.Series) -> str:
        values = [f"{column}: {row[column]}" for column in self.dataframe.columns if pd.notna(row[column])]
        return f"row_number={int(index) + 1}; " + "; ".join(values)

    def numeric_summary(self) -> pd.DataFrame:
        """Return deterministic aggregate facts for numeric columns."""

        numeric = self.dataframe.select_dtypes(include="number")
        if numeric.empty:
            return pd.DataFrame(columns=["column", "count", "mean", "median", "min", "max"])
        summary = numeric.agg(["count", "mean", "median", "min", "max"]).T.reset_index()
        summary.columns = ["column", "count", "mean", "median", "min", "max"]
        for column in ["mean", "median", "min", "max"]:
            summary[column] = summary[column].round(2)
        return summary

    def prompt_profile(self) -> str:
        """Format deterministic table facts for the local model."""

        facts = profile_for_prompt(self.profile)
        summary = self.numeric_summary()
        if not summary.empty:
            facts += "\nNumeric summary:\n" + summary.head(20).to_string(index=False)
        return facts

    def search(self, question: str, limit: int = 8) -> list[RowSource]:
        """Return the most relevant rows without any external service."""

        terms = [term for term in TOKEN_RE.findall(question.lower()) if term not in STOPWORDS]
        scored: list[tuple[int, int, str]] = []
        for index, row_text in enumerate(self._rows):
            haystack = row_text.lower()
            score = sum(haystack.count(term) for term in terms)
            scored.append((score, index, row_text))

        # Generic questions still need context. A stable first-page sample is
        # more honest than pretending semantic search found something special.
        if not terms or max(score for score, _, _ in scored) == 0:
            ordered = scored
        else:
            ordered = sorted(scored, key=lambda item: (-item[0], item[1]))

        sources: list[RowSource] = []
        for position, (_, index, content) in enumerate(ordered[: max(1, min(limit, 20))], start=1):
            sources.append(RowSource(f"[Source {position}]", index + 1, content))
        return sources


class OpenAICompatibleClient:
    """Minimal client for LM Studio, Ollama, and compatible local servers."""

    def __init__(
        self,
        base_url: Optional[str] = None,
        model: Optional[str] = None,
        api_key: Optional[str] = None,
        timeout: float = 120.0,
        session: Optional[requests.Session] = None,
    ):
        self.base_url = (base_url or os.getenv("LLM_BASE_URL", "http://localhost:1234/v1")).rstrip("/")
        self.model = model or os.getenv("LLM_MODEL", "auto")
        self.api_key = api_key if api_key is not None else os.getenv("LLM_API_KEY", "")
        self.timeout = timeout
        self.session = session or requests.Session()

    @property
    def _headers(self) -> dict[str, str]:
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        return headers

    def models(self) -> list[str]:
        response = self.session.get(f"{self.base_url}/models", headers=self._headers, timeout=2)
        response.raise_for_status()
        payload = response.json()
        items = payload.get("data", []) if isinstance(payload, dict) else []
        return [str(item["id"]) for item in items if isinstance(item, dict) and item.get("id")]

    def status(self) -> dict[str, Any]:
        try:
            models = self.models()
            return {"ready": bool(models), "models": models, "error": None}
        except requests.RequestException as exc:
            return {"ready": False, "models": [], "error": str(exc)}
        except (KeyError, TypeError, ValueError) as exc:
            return {"ready": False, "models": [], "error": f"Invalid provider response: {exc}"}

    def ask(self, question: str, table: LocalTable, limit: int = 8) -> tuple[str, list[RowSource]]:
        sources = table.search(question, limit=limit)
        context = "\n\n".join(f"{source.citation} {source.content}" for source in sources)
        profile = table.profile
        system = (
            "You are a careful spreadsheet analyst. Answer only from the supplied rows and profile. "
            "Do not invent values. If the sample does not support the answer, say so. "
            "Cite row-level claims with [Source N] and aggregate profile claims with [Profile]. "
            "Keep the answer concise and say when an exact calculation is not supported."
        )
        user = (
            f"Profile facts [Profile]:\n{table.prompt_profile()}\n"
            f"Retrieved rows:\n{context}\n\nQuestion: {question.strip()}"
        )
        model = self.model
        try:
            if model == "auto":
                available = self.models()
                if not available:
                    raise ProviderError("No model is loaded in the local provider.")
                model = available[0]
            response = self.session.post(
                f"{self.base_url}/chat/completions",
                headers=self._headers,
                json={
                    "model": model,
                    "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
                    "temperature": 0.1,
                    "stream": False,
                },
                timeout=self.timeout,
            )
            response.raise_for_status()
            payload = response.json()
            answer = payload["choices"][0]["message"]["content"].strip()
            if not answer:
                raise ProviderError("The local provider returned an empty answer.")
            return answer, sources
        except ProviderError:
            raise
        except requests.RequestException as exc:
            raise ProviderError(
                f"Could not reach the local model at {self.base_url}. "
                "Start LM Studio's local server or check LLM_BASE_URL."
            ) from exc
        except (KeyError, IndexError, TypeError, ValueError) as exc:
            raise ProviderError(f"The local provider returned an invalid response: {exc}") from exc
