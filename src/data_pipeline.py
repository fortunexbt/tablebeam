"""Deterministic ingestion, validation, and profiling for spreadsheet data.

This module deliberately has no LLM or vector-store dependency.  Keeping the
data boundary small makes it possible to validate a source before any model is
started and keeps the privacy-sensitive part of the application easy to test.
"""

from __future__ import annotations

import hashlib
import os
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any, Iterable, Optional

import pandas as pd

from gsheet_loader import extract_sheet_id, load_gsheet_as_csv


DEFAULT_MAX_ROWS = 250_000
DEFAULT_MAX_BYTES = 100 * 1024 * 1024


class DataValidationError(ValueError):
    """Raised when a source cannot be safely analyzed."""


@dataclass(frozen=True)
class DataProfile:
    """Small, serializable summary shown to users and supplied to the UI."""

    row_count: int
    column_count: int
    columns: list[str]
    numeric_columns: list[str]
    categorical_columns: list[str]
    date_like_columns: list[str]
    missing_values: dict[str, int]
    duplicate_rows: int
    memory_mb: float
    warnings: list[str]

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def _clean_column_name(value: Any, position: int) -> str:
    name = str(value).strip()
    if not name:
        raise DataValidationError(
            f"Column {position + 1} has no name. Add a header before loading the file."
        )
    return name


def normalize_dataframe(
    df: pd.DataFrame,
    *,
    max_rows: int = DEFAULT_MAX_ROWS,
    source_label: str = "data source",
) -> pd.DataFrame:
    """Validate and normalize a dataframe without changing user values."""

    if not isinstance(df, pd.DataFrame):
        raise DataValidationError(f"{source_label} did not produce tabular data.")

    if len(df) > max_rows:
        raise DataValidationError(
            f"{source_label} has {len(df):,} rows; the safe limit is {max_rows:,}."
        )

    cleaned = df.copy()
    cleaned.columns = [_clean_column_name(col, i) for i, col in enumerate(cleaned.columns)]
    duplicates = cleaned.columns[cleaned.columns.duplicated()].tolist()
    if duplicates:
        raise DataValidationError(
            "Duplicate column names are ambiguous: " + ", ".join(map(str, duplicates))
        )

    if cleaned.shape[1] == 0:
        raise DataValidationError(f"{source_label} has no columns.")

    # Empty rows are not useful retrieval records and commonly appear after a
    # spreadsheet's formatted range. Keep the columns so the profile remains
    # faithful to the source.
    cleaned = cleaned.dropna(how="all").reset_index(drop=True)
    if cleaned.empty:
        raise DataValidationError(f"{source_label} has no non-empty rows.")

    return cleaned


def profile_dataframe(df: pd.DataFrame) -> DataProfile:
    """Return useful, non-generative facts about a normalized dataframe."""

    warnings: list[str] = []
    missing = {str(column): int(df[column].isna().sum()) for column in df.columns}
    numeric = [str(column) for column in df.select_dtypes(include="number").columns]
    categorical = [
        str(column)
        for column in df.columns
        if pd.api.types.is_object_dtype(df[column])
        or isinstance(df[column].dtype, pd.CategoricalDtype)
        or pd.api.types.is_bool_dtype(df[column])
        or pd.api.types.is_string_dtype(df[column])
    ]

    date_like: list[str] = []
    for column in df.columns:
        if column in numeric:
            continue
        if pd.api.types.is_datetime64_any_dtype(df[column]):
            date_like.append(str(column))
        elif pd.api.types.is_string_dtype(df[column]):
            parsed = pd.to_datetime(df[column], errors="coerce", format="mixed")
            if len(df) and parsed.notna().mean() >= 0.9:
                date_like.append(str(column))

    for column, count in missing.items():
        if count == len(df):
            warnings.append(f"'{column}' is entirely empty.")
    if missing and max(missing.values()) / len(df) >= 0.5:
        warnings.append("At least one column is missing values in half or more of its rows.")
    if len(df) > 1 and df.duplicated().sum():
        warnings.append(f"{int(df.duplicated().sum()):,} duplicate rows detected.")

    memory_mb = float(df.memory_usage(deep=True).sum() / (1024 * 1024))
    return DataProfile(
        row_count=int(len(df)),
        column_count=int(len(df.columns)),
        columns=[str(column) for column in df.columns],
        numeric_columns=numeric,
        categorical_columns=categorical,
        date_like_columns=date_like,
        missing_values=missing,
        duplicate_rows=int(df.duplicated().sum()),
        memory_mb=round(memory_mb, 2),
        warnings=warnings,
    )


def profile_for_prompt(profile: Optional[DataProfile]) -> str:
    """Format only deterministic profile facts for an LLM prompt."""

    if profile is None:
        return "No profile is available."
    return (
        f"Rows: {profile.row_count:,}\n"
        f"Columns: {', '.join(profile.columns)}\n"
        f"Numeric columns: {', '.join(profile.numeric_columns) or 'none'}\n"
        f"Categorical columns: {', '.join(profile.categorical_columns) or 'none'}\n"
        f"Missing values: {profile.missing_values}\n"
        f"Duplicate rows: {profile.duplicate_rows:,}"
    )


def load_data(
    source: str,
    *,
    max_rows: int = DEFAULT_MAX_ROWS,
    max_bytes: int = DEFAULT_MAX_BYTES,
) -> pd.DataFrame:
    """Load a local CSV or a public Google Sheet, then validate it."""

    if not source or not str(source).strip():
        raise DataValidationError("Choose a CSV file or enter a Google Sheets URL.")

    source = str(source).strip()
    sheet_id = extract_sheet_id(source)
    if source.startswith(("http://", "https://")):
        if not sheet_id or "docs.google.com/spreadsheets" not in source:
            raise DataValidationError("Only Google Sheets URLs are supported for remote sources.")
        df = load_gsheet_as_csv(source)
        return normalize_dataframe(df, max_rows=max_rows, source_label="Google Sheet")

    if sheet_id and not Path(source).exists():
        df = load_gsheet_as_csv(source)
        return normalize_dataframe(df, max_rows=max_rows, source_label="Google Sheet")

    path = Path(source).expanduser()
    if not path.is_file():
        raise DataValidationError(f"CSV file not found: {path}")
    if path.stat().st_size > max_bytes:
        raise DataValidationError(
            f"CSV file is {path.stat().st_size / (1024 * 1024):.1f} MB; "
            f"the safe limit is {max_bytes / (1024 * 1024):.0f} MB."
        )
    if path.suffix.lower() != ".csv":
        raise DataValidationError("Please provide a CSV file.")

    try:
        df = pd.read_csv(path, encoding="utf-8-sig", on_bad_lines="error")
    except UnicodeDecodeError as exc:
        raise DataValidationError("CSV must be UTF-8 encoded.") from exc
    except (pd.errors.ParserError, OSError, ValueError) as exc:
        raise DataValidationError(f"Could not read CSV: {exc}") from exc
    return normalize_dataframe(df, max_rows=max_rows, source_label="CSV file")


def source_fingerprint(source: str, df: Optional[pd.DataFrame] = None) -> str:
    """Create a stable cache key without including raw data in a log message."""

    path = Path(source).expanduser()
    if path.is_file():
        stat = path.stat()
        material = f"file:{path.resolve()}:{stat.st_size}:{stat.st_mtime_ns}"
    else:
        material = f"remote:{source.strip()}"
    if df is not None:
        material += f":{len(df)}:{','.join(map(str, df.columns))}"
    return hashlib.sha256(material.encode("utf-8")).hexdigest()[:16]
