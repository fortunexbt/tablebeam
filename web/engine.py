"""Browser entry point for the hosted demo.

Pyodide loads this file next to unmodified copies of the app's modules, so the
answers on the demo page come from the same parser and calculations as the app.
Every function returns plain JSON-ready data for the page script.
"""

from __future__ import annotations

from numbers import Integral, Real
from time import perf_counter
from typing import Any

import pandas as pd

from answer_format import MAX_EXACT_JS_INTEGER, calculation_details, format_value
from data_pipeline import parse_csv_bytes, profile_dataframe
from question_actions import friendly_column, parse_question, suggested_questions
from table_analysis import csv_for_download, summarize_dataframe

EVIDENCE_ROWS = 25
# Above this many values the written-out arithmetic stops being checkable by eye.
MAX_WORKING_VALUES = 12

_table: pd.DataFrame | None = None
_last: dict[str, Any] | None = None


def _cell(value: Any) -> str | None:
    """Exact text for one cell: integers keep every digit, floats round-trip."""
    if value is None or (not isinstance(value, str) and pd.isna(value)):
        return None
    if isinstance(value, Integral):
        return str(int(value))
    if isinstance(value, Real):
        return repr(float(value))
    return str(value)


def _rows(frame: pd.DataFrame, limit: int) -> list[dict[str, Any]]:
    # itertuples keeps each cell's own type; iterrows would coerce mixed rows to float.
    return [
        {"row": int(position) + 1, "cells": [_cell(value) for value in values]}
        for position, *values in frame.head(limit).itertuples(index=True, name=None)
    ]


def load(content: bytes, label: str) -> dict[str, Any]:
    global _table, _last
    started = perf_counter()
    table = parse_csv_bytes(bytes(content), source_label=label)
    profile = profile_dataframe(table)
    _table, _last = table.reset_index(drop=True), None
    return {
        "label": label,
        "rows": profile.row_count,
        "columns": [
            {
                "name": column,
                "friendly": friendly_column(column),
                "numeric": column in profile.numeric_columns,
                "missing": profile.missing_values.get(column, 0),
            }
            for column in profile.columns
        ],
        "warnings": profile.warnings,
        "suggestions": [suggestion.question for suggestion in suggested_questions(table)],
        "ms": round((perf_counter() - started) * 1000, 1),
    }


def ask(question: str) -> dict[str, Any]:
    global _last
    if _table is None:
        raise ValueError("Open a table first.")
    clean = question.strip()
    spec = parse_question(clean, _table)
    if spec is None:
        _last = None
        return {"kind": "needs_ai", "question": clean}

    started = perf_counter()
    result = summarize_dataframe(_table, spec.operation, spec.column, spec.group_by)
    elapsed = (perf_counter() - started) * 1000
    answer = {
        "kind": "calculation", "question": clean, "operation": spec.operation,
        "column": spec.column, "group_by": spec.group_by,
        "selected_rows": len(_table), "total_rows": len(_table), "filter_label": "All rows",
        "missing_values": int(_table[spec.column].isna().sum()) if spec.column else 0,
    }
    _last = {"answer": answer, "result": result}

    group_column = result.columns[0] if spec.group_by is not None else None
    return {
        **answer,
        "parsed": repr(spec),
        "call": (
            f"summarize_dataframe(table, {spec.operation!r}, {spec.column!r}, {spec.group_by!r})"
        ),
        "ms": round(elapsed, 2),
        "details": calculation_details(answer),
        "headline": format_value(result["value"].iloc[0]) if spec.group_by is None else None,
        "result": [
            {
                "group": _cell(row[group_column]) if group_column else None,
                "value": format_value(row["value"]),
                "exact": _cell(row["value"]),
                "rows": int(row["rows"]),
            }
            for _, row in result.astype(object).iterrows()
        ],
        "big_integers": bool(result["value"].map(
            lambda value: isinstance(value, Integral) and abs(int(value)) > MAX_EXACT_JS_INTEGER
        ).any()),
        "columns": list(_table.columns),
    }


def _selection(group_index: int | None) -> tuple[pd.DataFrame, Any, str | None]:
    """The rows behind the last answer, or behind one of its groups."""
    if _last is None or _table is None:
        raise ValueError("Ask a question first.")
    answer, result = _last["answer"], _last["result"]
    if group_index is None:
        return _table, result["value"].iloc[0], None
    key = result.iloc[int(group_index), 0]
    labels = _table[answer["group_by"]]
    rows = _table.loc[labels.isna() if pd.isna(key) else labels.eq(key).fillna(False)]
    return rows, result["value"].iloc[int(group_index)], _cell(key)


def evidence(group_index: int | None = None) -> dict[str, Any]:
    """Rows behind the last answer, or behind one of its groups, with the working."""
    rows, value, group_label = _selection(group_index)
    answer = _last["answer"]

    working = None
    column = answer["column"]
    if column is not None:
        values = [item for item in rows[column].tolist() if not pd.isna(item)]
        if 0 < len(values) <= MAX_WORKING_VALUES:
            terms = [_cell(item) for item in values]
            operation = answer["operation"]
            if operation == "sum":
                working = " + ".join(terms)
            elif operation == "mean":
                working = f"({' + '.join(terms)}) / {len(terms)}"
            else:
                ordered = sorted(values)
                working = f"{answer['operation']} of [{', '.join(_cell(item) for item in ordered)}]"
            working += f" = {_cell(value)}"
    elif len(rows) <= MAX_WORKING_VALUES:
        working = f"{len(rows)} rows counted = {_cell(value)}"

    return {
        "group": group_label,
        "group_index": group_index,
        "count": len(rows),
        "rows": _rows(rows, EVIDENCE_ROWS),
        "working": working,
        "measure": column,
        "group_by": answer["group_by"],
    }


def rows_csv(group_index: int | None = None) -> str:
    """The same rows as a download, written by the app's own CSV export."""
    return csv_for_download(_selection(group_index)[0]).decode("utf-8")
