"""Explicit, local calculations over complete tables, without generated code."""

from __future__ import annotations

import csv
import math
import operator
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from io import StringIO
from numbers import Real
from typing import Any

import pandas as pd


class TableAnalysisError(ValueError):
    """A requested calculation or filter is invalid for the table."""


@dataclass(frozen=True)
class FilterSpec:
    column: str
    operator: str
    value: Any = None


_COMPARISONS = {
    "eq": operator.eq,
    "ne": operator.ne,
    "gt": operator.gt,
    "ge": operator.ge,
    "lt": operator.lt,
    "le": operator.le,
}
_OPERATIONS = {"count", "sum", "mean", "median", "min", "max"}


def _validate_table(df: pd.DataFrame) -> None:
    if not isinstance(df, pd.DataFrame):
        raise TableAnalysisError("Expected a pandas DataFrame.")
    if not df.columns.is_unique:
        raise TableAnalysisError("Duplicate column names are ambiguous.")


def _column(df: pd.DataFrame, name: str) -> pd.Series:
    if not isinstance(name, str) or name not in df.columns:
        raise TableAnalysisError(f"Unknown column: {name!r}.")
    return df[name]


def _is_real_numeric(series: pd.Series) -> bool:
    return (
        pd.api.types.is_numeric_dtype(series.dtype)
        and not pd.api.types.is_bool_dtype(series.dtype)
        and not pd.api.types.is_complex_dtype(series.dtype)
    )


def _require_finite(series: pd.Series) -> None:
    if series.isin([float("inf"), float("-inf")]).any():
        raise TableAnalysisError("Numeric values must be finite; remove infinity first.")


def _comparison_value(series: pd.Series, spec: FilterSpec) -> Any:
    value = spec.value
    if _is_real_numeric(series):
        if isinstance(value, bool) or not isinstance(value, (Real, Decimal)):
            raise TableAnalysisError("Numeric filters require a numeric value.")
        if not (value.is_finite() if isinstance(value, Decimal) else math.isfinite(value)):
            raise TableAnalysisError("Numeric filter values must be finite.")
        _require_finite(series)
        return value
    if pd.api.types.is_datetime64_any_dtype(series.dtype):
        if not isinstance(value, (str, date, datetime, pd.Timestamp)):
            raise TableAnalysisError("Date filters require a date or ISO date string.")
        try:
            parsed = pd.Timestamp(value)
        except (TypeError, ValueError, OverflowError) as exc:
            raise TableAnalysisError("Enter a valid date for this filter.") from exc
        if pd.isna(parsed):
            raise TableAnalysisError("Use is_missing to filter missing dates.")
        if (series.dt.tz is None) != (parsed.tzinfo is None):
            raise TableAnalysisError("The filter date must match the column's timezone awareness.")
        return parsed
    if spec.operator not in {"eq", "ne"}:
        raise TableAnalysisError("Ordered comparisons require a numeric or date column.")
    if pd.api.types.is_bool_dtype(series.dtype):
        if not isinstance(value, bool):
            raise TableAnalysisError("Boolean filters require True or False.")
        return value
    if not isinstance(value, str):
        raise TableAnalysisError("Text filters require a string value.")
    if not series.dropna().map(lambda item: isinstance(item, str)).all():
        raise TableAnalysisError("Text filters require a text column.")
    return value


def filter_dataframe(df: pd.DataFrame, filters: list[FilterSpec]) -> pd.DataFrame:
    """Apply AND filters and return a copy with original indices intact.

    Comparisons exclude missing cells, including ``ne``. Use ``is_missing`` or
    ``not_missing`` to select those explicitly. Text matching is literal;
    ``contains`` is case-insensitive, while equality is case-sensitive.
    """

    _validate_table(df)
    if not isinstance(filters, list):
        raise TableAnalysisError("Filters must be a list of FilterSpec values.")
    mask = pd.Series(True, index=df.index, dtype=bool)
    for spec in filters:
        if not isinstance(spec, FilterSpec):
            raise TableAnalysisError("Filters must be FilterSpec values.")
        if not isinstance(spec.operator, str):
            raise TableAnalysisError("Filter operators must be strings.")
        series = _column(df, spec.column)
        if spec.operator == "is_missing":
            match = series.isna()
        elif spec.operator == "not_missing":
            match = series.notna()
        elif spec.operator == "contains":
            if not isinstance(spec.value, str):
                raise TableAnalysisError("Contains filters require a string value.")
            if not series.dropna().map(lambda item: isinstance(item, str)).all():
                raise TableAnalysisError("Contains filters require a text column.")
            match = series.astype("string").str.contains(spec.value, case=False, regex=False, na=False)
        elif spec.operator in _COMPARISONS:
            value = _comparison_value(series, spec)
            if isinstance(value, Decimal):
                # Object comparison preserves fractional thresholds beside
                # integers larger than JavaScript or float64 can represent.
                series = series.astype(object)
            try:
                match = _COMPARISONS[spec.operator](series, value) & series.notna()
            except (TypeError, ValueError) as exc:
                raise TableAnalysisError("This value is incompatible with the selected column.") from exc
        else:
            raise TableAnalysisError(f"Unsupported filter operator: {spec.operator!r}.")
        mask &= match.fillna(False)
    return df.loc[mask].copy()


def group_result_column(group_by: str) -> str:
    """Return the grouping label without colliding with ``value`` or ``rows``."""

    return "group" if group_by in {"value", "rows"} else group_by


def summarize_dataframe(
    df: pd.DataFrame,
    operation: str,
    column: str | None = None,
    group_by: str | None = None,
) -> pd.DataFrame:
    """Calculate complete-table aggregates, optionally including missing groups.

    ``count`` always counts rows. Other operations require a real numeric
    column, ignore missing values, and return null for all-missing inputs.
    ``rows`` counts all contributing rows, including missing numeric values.
    Groups sort by descending value, null last, with first appearance breaking
    ties. Empty grouped results retain the same columns; ungrouped results have
    one row, including when the input has no rows.
    """

    _validate_table(df)
    if not isinstance(operation, str) or operation not in _OPERATIONS:
        raise TableAnalysisError(f"Unsupported summary operation: {operation!r}.")
    groups = _column(df, group_by) if group_by is not None else None
    if column is not None:
        _column(df, column)
    if operation != "count":
        selected = _column(df, column)
        if not _is_real_numeric(selected):
            raise TableAnalysisError("This calculation requires a real numeric column.")
        _require_finite(selected)
        # Python integer addition avoids NumPy's silent fixed-width overflow.
        if operation == "sum" and pd.api.types.is_integer_dtype(selected.dtype):
            selected = selected.astype(object)
    else:
        selected = pd.Series(1, index=df.index, dtype="int64")

    if group_by is None:
        if operation == "count":
            value = len(df)
        elif not selected.notna().any():
            value = None
        elif operation == "sum":
            value = selected.sum(min_count=1)
        else:
            value = getattr(selected, operation)()
        unexpected_null = pd.isna(value) and selected.notna().any()
        result = pd.DataFrame({"value": [value], "rows": [len(df)]})
    else:
        grouped = selected.groupby(groups, sort=False, dropna=False, observed=True)
        rows = grouped.size()
        if operation == "count":
            values = rows
        elif operation == "sum":
            values = grouped.sum(min_count=1)
        else:
            values = getattr(grouped, operation)()
        unexpected_null = (values.isna() & grouped.count().gt(0)).any()
        result = pd.DataFrame({"value": values, "rows": rows})
        result.index.name = group_result_column(group_by)
        result = result.reset_index()

    if unexpected_null or result["value"].isin([float("inf"), float("-inf")]).any():
        raise TableAnalysisError("The calculation overflowed; use smaller numeric values.")
    return result.sort_values("value", ascending=False, kind="stable", na_position="last").reset_index(drop=True)


def _spreadsheet_cell(value: Any) -> Any:
    if isinstance(value, str):
        # Leading whitespace can disguise spreadsheet formulas. Prefix the
        # original string so CSV quoting still preserves commas and newlines.
        if value.startswith(("\t", "\r", "\n")) or value.lstrip().startswith(("=", "+", "-", "@")):
            return "'" + value
        return value
    return "" if pd.isna(value) else value


def csv_for_download(df: pd.DataFrame) -> bytes:
    """Export UTF-8 BOM CSV with formula-safe text cells and headers.

    Numeric values, including negative numbers, keep their numeric spelling.
    The original dataframe is never modified and the row index is not exported.
    """

    _validate_table(df)
    output = StringIO(newline="")
    writer = csv.writer(output)
    writer.writerow([_spreadsheet_cell(str(name)) for name in df.columns])
    writer.writerows([_spreadsheet_cell(value) for value in row] for row in df.itertuples(index=False, name=None))
    return output.getvalue().encode("utf-8-sig")
