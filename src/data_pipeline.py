"""Deterministic ingestion, validation, and profiling for spreadsheet data.

This module deliberately has no LLM or vector-store dependency.  Keeping the
data boundary small makes it possible to validate a source before any model is
started and keeps the privacy-sensitive part of the application easy to test.
"""

from __future__ import annotations

import csv
import hashlib
import re
from collections import Counter
from dataclasses import dataclass, asdict
from io import StringIO
from pathlib import Path
from typing import Any, Optional

import pandas as pd

DEFAULT_MAX_ROWS = 250_000
DEFAULT_MAX_BYTES = 100 * 1024 * 1024

# pandas' default CSV missing-value spellings. Integer dtype selection must
# ignore the same markers as the value parser, without treating whitespace as
# a missing cell. Explicit dtypes avoid signed-minimum/unsigned inference bugs.
_CSV_MISSING_VALUES = {
    "", "#N/A", "#N/A N/A", "#NA", "-1.#IND", "-1.#QNAN", "-NaN", "-nan",
    "1.#IND", "1.#QNAN", "<NA>", "N/A", "NA", "NULL", "NaN", "None", "n/a", "nan", "null",
}
_INTEGER_TOKEN = re.compile(r"[+-]?[0-9]+")


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

    # pandas infers boolean CSV columns with blanks as object dtype. Retain
    # their boolean meaning so typed filtering also works with missing cells.
    for column in cleaned.columns:
        values = cleaned[column].dropna()
        if cleaned[column].dtype == object and not values.empty and values.map(lambda value: isinstance(value, bool)).all():
            cleaned[column] = cleaned[column].astype("boolean")

    return cleaned


def parse_csv_bytes(
    content: bytes,
    *,
    max_rows: int = DEFAULT_MAX_ROWS,
    max_bytes: int = DEFAULT_MAX_BYTES,
    source_label: str = "CSV file",
) -> pd.DataFrame:
    """Validate the original CSV before pandas can rename or discard fields.

    The byte and record limits are checked before constructing a dataframe.
    Pandas still performs its usual value and missing-value inference, but only
    after every record has been checked against the original header width.
    """

    if len(content) > max_bytes:
        raise DataValidationError(
            f"{source_label} exceeds the safe limit of "
            f"{max_bytes / (1024 * 1024):g} MB."
        )
    try:
        text = content.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise DataValidationError("CSV must be UTF-8 encoded.") from exc
    if "\x00" in text:
        raise DataValidationError("CSV contains null bytes. Export it as UTF-8 text.")

    # The csv module's default per-field ceiling is lower than pandas'. The
    # complete input is already bounded, so allow cells up to that same limit.
    csv.field_size_limit(max(csv.field_size_limit(), max_bytes))
    stream = StringIO(text, newline="")
    reader = csv.reader(stream, strict=True)
    headers: Optional[list[str]] = None
    integer_columns: list[bool] = []
    integer_bounds: list[Optional[tuple[int, int]]] = []
    row_count = 0
    try:
        while True:
            record_start = stream.tell()
            try:
                record = next(reader)
            except StopIteration:
                break
            # Match pandas' handling of genuinely blank physical records.
            # Quoted empty cells remain records and must have the right width.
            if not text[record_start : stream.tell()].strip(" \t\r\n"):
                continue
            if headers is None:
                headers = [_clean_column_name(value, index) for index, value in enumerate(record)]
                duplicates = [name for name, count in Counter(headers).items() if count > 1]
                if duplicates:
                    raise DataValidationError(
                        "Duplicate column names are ambiguous: " + ", ".join(duplicates)
                    )
                integer_columns = [True] * len(headers)
                integer_bounds = [None] * len(headers)
                continue
            if len(record) != len(headers):
                raise DataValidationError(
                    f"CSV record ending on line {reader.line_num} has {len(record)} fields; "
                    f"the header has {len(headers)}. Check missing separators or quoted commas."
                )
            row_count += 1
            if row_count > max_rows:
                raise DataValidationError(
                    f"{source_label} exceeds the safe limit of {max_rows:,} rows."
                )
            for index, value in enumerate(record):
                if not integer_columns[index] or value in _CSV_MISSING_VALUES:
                    continue
                if not _INTEGER_TOKEN.fullmatch(value.strip()):
                    integer_columns[index] = False
                    continue
                try:
                    integer = int(value)
                except ValueError:
                    # Extremely long numeric-looking strings can exceed
                    # Python's integer digit ceiling; leave them to pandas.
                    integer_columns[index] = False
                    continue
                bounds = integer_bounds[index]
                integer_bounds[index] = (
                    (integer, integer) if bounds is None
                    else (min(bounds[0], integer), max(bounds[1], integer))
                )
    except csv.Error as exc:
        raise DataValidationError(f"Could not read CSV near line {reader.line_num}: {exc}") from exc

    if not headers:
        raise DataValidationError(f"{source_label} has no columns.")
    integer_dtypes = {}
    for index, bounds in enumerate(integer_bounds):
        if integer_columns[index] and bounds is not None:
            minimum, maximum = bounds
            integer_dtypes[index] = (
                "Int64" if -(2**63) <= minimum and maximum < 2**63
                else "UInt64" if 0 <= minimum and maximum < 2**64
                else "string"
            )
    try:
        dataframe = pd.read_csv(
            StringIO(text), encoding="utf-8-sig", on_bad_lines="error", nrows=max_rows + 1,
            # Missing cells must not force exact integers through float64.
            dtype_backend="numpy_nullable",
            dtype=integer_dtypes,
        )
    except (pd.errors.ParserError, ValueError) as exc:
        raise DataValidationError(f"Could not read CSV: {exc}") from exc
    return normalize_dataframe(dataframe, max_rows=max_rows, source_label=source_label)


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

    # The sheet loader shares this module's strict CSV parser. Import only at
    # the source boundary so either module can also be imported independently.
    from gsheet_loader import extract_sheet_id, load_gsheet_as_csv

    if not source or not str(source).strip():
        raise DataValidationError("Choose a CSV file or enter a Google Sheets URL.")

    source = str(source).strip()
    sheet_id = extract_sheet_id(source)
    if source.startswith(("http://", "https://")):
        if not sheet_id or "docs.google.com/spreadsheets" not in source:
            raise DataValidationError("Only Google Sheets URLs are supported for remote sources.")
        return load_gsheet_as_csv(source, max_rows=max_rows, max_bytes=max_bytes)

    if sheet_id and not Path(source).exists():
        return load_gsheet_as_csv(source, max_rows=max_rows, max_bytes=max_bytes)

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
        with path.open("rb") as handle:
            content = handle.read(max_bytes + 1)
    except OSError as exc:
        raise DataValidationError(f"Could not read CSV: {exc}") from exc
    return parse_csv_bytes(content, max_rows=max_rows, max_bytes=max_bytes)


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
