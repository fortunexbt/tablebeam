"""Citation-aware retrieval and answer formatting shared by UI and API."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable

from data_pipeline import DataProfile, profile_for_prompt


@dataclass(frozen=True)
class AnswerSource:
    citation: str
    row_index: Any
    content: str


@dataclass(frozen=True)
class AnswerResult:
    answer: str
    sources: list[AnswerSource]


def _content(value: Any) -> str:
    if isinstance(value, str):
        return value
    return str(getattr(value, "content", value))


def build_prompt(question: str, documents: Iterable[Any], profile: DataProfile | None = None) -> tuple[str, list[AnswerSource]]:
    """Build a grounded prompt where each retrieved record has a stable citation."""

    sources: list[AnswerSource] = []
    blocks: list[str] = []
    for position, document in enumerate(documents, start=1):
        metadata = getattr(document, "metadata", {}) or {}
        row_index = metadata.get("row_index", "unknown")
        content = str(getattr(document, "page_content", document))
        citation = f"[Source {position}]"
        sources.append(AnswerSource(citation=citation, row_index=row_index, content=content))
        blocks.append(f"{citation} row_index={row_index}\n{content}")

    context = "\n\n---\n\n".join(blocks) or "No matching rows were retrieved."
    prompt = f"""You are a careful spreadsheet analyst working over a private local dataset.

Answer the user's question using only the retrieved rows and the dataset profile below.
Do not invent values, totals, dates, or trends. If the rows do not support an answer,
say that clearly. When making a factual claim, cite the supporting record using the
exact citation labels such as [Source 1]. Distinguish calculated results from values
that appear directly in a row. Keep the answer concise and readable.

Dataset profile:
{profile_for_prompt(profile)}

Retrieved rows:
{context}

User question: {question.strip()}
"""
    return prompt, sources


def answer_question(retriever: Any, llm: Any, question: str, *, limit: int = 5, profile: DataProfile | None = None) -> AnswerResult:
    """Retrieve rows and invoke a local LLM, returning answer plus source records."""

    question = question.strip()
    if not question:
        raise ValueError("Ask a question about the loaded data.")
    if len(question) > 2000:
        raise ValueError("Questions must be 2,000 characters or shorter.")
    documents = list(retriever.invoke(question))[:limit]
    prompt, sources = build_prompt(question, documents, profile)
    answer = _content(llm.invoke(prompt)).strip()
    if not answer:
        answer = "The local model returned an empty answer. Please try a more specific question."
    return AnswerResult(answer=answer, sources=sources)
