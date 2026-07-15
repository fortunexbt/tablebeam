"""Local Chroma retrieval backed by validated spreadsheet rows."""

from __future__ import annotations

import hashlib
import logging
import os
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any, List

import pandas as pd

from data_pipeline import (
    DataProfile,
    load_data,
    profile_dataframe,
    source_fingerprint,
)

try:  # Keep deterministic ingestion importable before optional AI packages install.
    from langchain_core.documents import Document
except ImportError:  # pragma: no cover - exercised only in minimal environments.
    @dataclass
    class Document:  # type: ignore[no-redef]
        page_content: str
        metadata: dict[str, Any]
        id: str | None = None


logger = logging.getLogger(__name__)


def analyze_dataframe(df: pd.DataFrame) -> DataProfile:
    """Return a profile and log only aggregate facts."""

    profile = profile_dataframe(df)
    logger.info("Loaded %s rows and %s columns", profile.row_count, profile.column_count)
    return profile


def load_client_data(source: str) -> pd.DataFrame:
    """Load and validate a local CSV or public Google Sheet."""

    return load_data(source)


def detect_primary_key(df: pd.DataFrame) -> str:
    """Choose a readable row identifier for source labels."""

    if df.empty or len(df.columns) == 0:
        raise ValueError("Cannot detect a row identifier in an empty dataset.")
    columns_lower = {str(col).strip().lower(): col for col in df.columns}
    for name in ("id", "name"):
        if name in columns_lower:
            return str(columns_lower[name])
    for keyword in ("client", "company", "customer", "account"):
        for lower, original in columns_lower.items():
            if keyword in lower:
                return str(original)
    for column in df.columns:
        non_null = df[column].dropna()
        if len(non_null) and non_null.nunique(dropna=True) / len(df) >= 0.8:
            return str(column)
    return str(df.columns[0])


def _document_id(primary_key: str, value: Any, row_index: Any) -> str:
    raw = f"{primary_key}\0{value}\0{row_index}".encode("utf-8", errors="replace")
    return f"row_{hashlib.sha256(raw).hexdigest()[:20]}"


def create_documents(df: pd.DataFrame) -> List[Document]:
    """Convert rows to searchable documents while preserving source row indices."""

    primary_key = detect_primary_key(df)
    documents: List[Document] = []
    for row_index, row in df.iterrows():
        parts: list[str] = []
        metadata: dict[str, Any] = {"row_index": int(row_index)}
        for column in df.columns:
            value = row[column]
            if pd.isna(value):
                continue
            value_text = str(value)
            parts.append(f"{column}: {value_text}")
            metadata[str(column)] = value_text
        primary_value = row.get(primary_key)
        doc_id = _document_id(primary_key, primary_value, row_index)
        documents.append(Document(page_content=", ".join(parts), metadata=metadata, id=doc_id))
    return documents


def _collection_name(data_source: str) -> str:
    return f"data_{source_fingerprint(data_source)}"


def _document_fingerprint(documents: List[Document]) -> str:
    digest = hashlib.sha256()
    for document in documents:
        digest.update(str(getattr(document, "id", "")).encode())
        digest.update(getattr(document, "page_content", "").encode("utf-8", errors="replace"))
    return digest.hexdigest()[:16]


def setup_chroma_store(
    documents: List[Document],
    data_source: str,
    force_refresh: bool = False,
    k: int = 5,
    embedding_model: str = "mxbai-embed-large",
):
    """Create or reuse a Chroma store, invalidating stale model/data caches."""

    try:
        from langchain_chroma import Chroma
        from langchain_ollama import OllamaEmbeddings
    except ImportError as exc:
        raise RuntimeError(
            "AI dependencies are not installed. Run ./start.sh or "
            "pip install -r src/requirements.txt."
        ) from exc

    db_root = Path(os.getenv("VECTOR_DB_PATH", "./chroma_db_clients"))
    collection_name = _collection_name(data_source)
    db_location = db_root / collection_name
    db_location.mkdir(parents=True, exist_ok=True)
    model_file = db_location / ".embedding_model"
    data_file = db_location / ".data_fingerprint"
    current_data = _document_fingerprint(documents)
    stored_model = model_file.read_text().strip() if model_file.exists() else None
    stored_data = data_file.read_text().strip() if data_file.exists() else None
    needs_rebuild = force_refresh or stored_model != embedding_model or stored_data != current_data

    if needs_rebuild and db_location.exists():
        shutil.rmtree(db_location)
        db_location.mkdir(parents=True, exist_ok=True)

    embeddings = OllamaEmbeddings(
        model=embedding_model,
        base_url=os.getenv("OLLAMA_HOST", "http://localhost:11434"),
    )
    try:
        vector_store = Chroma(
            collection_name=collection_name,
            persist_directory=str(db_location),
            embedding_function=embeddings,
        )
        collection_empty = vector_store._collection.count() == 0
        if needs_rebuild or collection_empty:
            if documents:
                vector_store.add_documents(documents, ids=[doc.id for doc in documents])
            model_file.write_text(embedding_model)
            data_file.write_text(current_data)
    except Exception:
        # A partially written local cache should never make the dataset unusable.
        # Rebuild once; do not loop or silently swallow the second failure.
        if db_location.exists():
            shutil.rmtree(db_location)
        db_location.mkdir(parents=True, exist_ok=True)
        vector_store = Chroma(
            collection_name=collection_name,
            persist_directory=str(db_location),
            embedding_function=embeddings,
        )
        if documents:
            vector_store.add_documents(documents, ids=[doc.id for doc in documents])
        model_file.write_text(embedding_model)
        data_file.write_text(current_data)

    return vector_store.as_retriever(search_kwargs={"k": max(1, min(k, 20))})


def get_retriever(
    data_source: str = "sample_data.csv",
    force_refresh: bool = False,
    embedding_model: str = "mxbai-embed-large",
):
    """Load a source and return its local Chroma retriever."""

    df = load_client_data(data_source)
    analyze_dataframe(df)
    documents = create_documents(df)
    return setup_chroma_store(
        documents,
        data_source,
        force_refresh=force_refresh,
        embedding_model=embedding_model,
    )
