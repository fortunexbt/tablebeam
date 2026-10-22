"""Plain answer formatting shared by the Streamlit view and the browser demo."""

from __future__ import annotations

from numbers import Integral
from typing import Any

import pandas as pd


MAX_CHART_GROUPS = 20
MAX_EXACT_JS_INTEGER = 2**53 - 1
OPERATION_NAMES = {
    "count": "Count rows",
    "sum": "Sum",
    "mean": "Average",
    "median": "Median",
    "min": "Minimum",
    "max": "Maximum",
}


def format_value(value: Any) -> str:
    """Format the answer without ever converting exact integers to floats."""
    if pd.isna(value):
        return "No values"
    if isinstance(value, Integral):
        return f"{value:,}"
    if isinstance(value, float) and value.is_integer():
        return f"{value:,.0f}"
    return f"{value:,.6g}"


def format_chart_value(value: Any) -> str:
    """Keep the visible result column compact; tooltips retain the full label."""
    label = format_value(value)
    return label if len(label) <= 12 else f"{value:.5g}"


def requires_integer_text(values: pd.Series) -> bool:
    """Avoid JavaScript rounding and Arrow overflow for oversized integers."""
    return any(
        isinstance(value, Integral) and abs(int(value)) > MAX_EXACT_JS_INTEGER
        for value in values.dropna()
    )


def display_result(frame: pd.DataFrame) -> pd.DataFrame:
    """Return a display-only copy; downloads keep the original numeric values."""
    display = frame.copy()
    for column in display.columns:
        if requires_integer_text(display[column]):
            # Series.map may coerce nullable integers to floats before calling
            # the formatter. Iteration retains the original integer scalars.
            display[column] = pd.Series(
                [None if pd.isna(value) else str(value) for value in display[column]],
                index=display.index, dtype=object,
            )
    return display


def calculation_details(answer: dict) -> str:
    """Describe the exact operation, scope, and missing-value semantics."""
    operation = answer["operation"]
    column = answer.get("column")
    group = answer.get("group_by")
    selected = answer["selected_rows"]
    total = answer["total_rows"]
    scope = answer.get("filter_label", "All rows")
    if operation == "count":
        calculation = "Count rows. Every selected row is counted, including rows with missing cells."
    else:
        missing = answer.get("missing_values", 0)
        calculation = (
            f"{OPERATION_NAMES.get(operation, operation)} of {column}. "
            f"{missing:,} missing {'value is' if missing == 1 else 'values are'} excluded from the calculation. "
            "When every value is missing, the result is No values."
        )
    if group is not None:
        calculation += f" Calculated separately for each {group}; missing group labels are included."
    return (
        f"{calculation}\n\n"
        f"Rows used: {selected:,} of {total:,}. Condition: {scope}. "
        "Every selected row is included; this is not a sample.\n\n"
        "The result table and download retain the full calculation precision. "
        "Numbers in the headline or chart may be rounded for readability. "
        "The rows column is the number of source rows, including missing values."
    )


def chart_data(result: pd.DataFrame) -> pd.DataFrame | None:
    """Build fixed chart fields, preserving stable rank and exact integers.

    None means the values require a text table. Empty data means no group has
    a value. Column names from the source never become Vega expressions.
    """
    if requires_integer_text(result["value"]):
        return None
    grouped = result.sort_values("value", ascending=False, kind="stable", na_position="last")
    grouped = grouped.loc[grouped["value"].notna()].head(MAX_CHART_GROUPS)
    group_column = next(column for column in result.columns if column not in {"value", "rows"})
    labels = ["(missing)" if pd.isna(value) else str(value) for value in grouped[group_column]]
    if len(set(labels)) != len(labels):
        # A literal '(missing)' value and a missing group are distinct groups.
        labels = [f"{index + 1}. {label}" for index, label in enumerate(labels)]
    values = list(grouped["value"])
    return pd.DataFrame({
        "group_label": labels,
        "amount": values,
        "value_label": [format_value(value) for value in values],
        "display_label": [format_chart_value(value) for value in values],
    })
