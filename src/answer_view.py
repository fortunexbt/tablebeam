"""A single answer, with the calculation and its evidence one step away."""

from __future__ import annotations

from html import escape
from numbers import Integral
import re
from typing import Any

import pandas as pd
import streamlit as st

from table_analysis import csv_for_download


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


def plain_markdown(value: Any) -> str:
    """Keep table and question text literal when used in Markdown labels."""
    return re.sub(r"([\\`*_{}\[\]()#+.!|>~-])", r"\\\1", escape(str(value), quote=False))


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


def chart_spec(plot: pd.DataFrame) -> dict:
    """A compact horizontal chart with direct value labels and no legend."""
    return {
        "height": max(110, min(660, 34 * len(plot))),
        "padding": {"top": 5, "left": 0, "bottom": 0, "right": 100},
        "encoding": {
            "y": {
                "field": "group_label", "type": "nominal", "sort": plot["group_label"].tolist(),
                "title": None, "axis": {"domain": False, "ticks": False, "labelPadding": 10, "labelLimit": 210},
            },
            "x": {
                "field": "amount", "type": "quantitative", "title": None,
                "axis": {"domain": False, "ticks": False, "grid": True, "format": "~s"},
                "scale": {"zero": True},
            },
            "tooltip": [
                {"field": "group_label", "type": "nominal", "title": "Group"},
                {"field": "value_label", "type": "nominal", "title": "Result"},
            ],
        },
        "layer": [
            {"mark": {"type": "bar", "color": "#3558d4", "cornerRadiusEnd": 3, "size": 21}},
            {
                # One aligned result column stays outside every bar, including
                # negative bars, and away from the group labels on the left.
                "mark": {"type": "text", "align": "left", "baseline": "middle", "dx": 12, "fontSize": 12},
                "encoding": {
                    "x": {"value": "width"},
                    "text": {"field": "display_label", "type": "nominal"},
                },
            },
        ],
        "config": {"view": {"stroke": None}, "axis": {"labelFontSize": 12, "gridColor": "#edf0f5"}},
    }


def _indented_block(value: Any) -> str:
    # Backticks in a cell cannot close an indented Markdown code block.
    return "\n".join("    " + line for line in str(value).splitlines()) or "    (empty)"


def ai_answer_markdown(answer: dict) -> str:
    """Export the answer with the exact profile, coverage, and supplied rows."""
    parts = [
        "# " + plain_markdown(answer["question"]).replace("\n", " "),
        "Model-generated answer. Check the sources before relying on its claims.",
        escape(str(answer.get("text", "")), quote=False),
        "## Sources used",
        plain_markdown(answer.get("coverage", "")),
    ]
    for source in answer.get("sources", []):
        citation = plain_markdown(source.get("citation", "Source")).replace("\n", " ")
        row = plain_markdown(source.get("row_number", "unknown")).replace("\n", " ")
        parts += [f"### {citation} · row {row}", _indented_block(source.get("content", ""))]
    parts += ["## Table profile supplied to the model", _indented_block(answer.get("profile", ""))]
    return "\n\n".join(parts) + "\n"


def _render_calculation(answer: dict) -> None:
    result = answer["result"]
    if answer["selected_rows"] == 0:
        st.info("No rows match this condition")
        return
    if answer.get("group_by") is None:
        # Selecting the series first avoids mixed-row coercion by pandas.
        value = result["value"].iloc[0] if not result.empty else None
        st.metric(label="Result", value=format_value(value))
    else:
        plot = chart_data(result)
        if plot is None:
            st.dataframe(display_result(result), use_container_width=True, hide_index=True)
        elif plot.empty:
            st.metric(label="Result", value="No values")
        else:
            st.vega_lite_chart(plot, chart_spec(plot), use_container_width=True)
        if plot is not None:
            valued_groups = int(result["value"].notna().sum())
            missing_groups = len(result) - valued_groups
            notices = []
            if len(plot) < valued_groups:
                notices.append(f"Top {len(plot):,} of {valued_groups:,} groups with values.")
            if missing_groups:
                notices.append(f"{missing_groups:,} {'group has' if missing_groups == 1 else 'groups have'} no values.")
            if notices:
                st.caption(" ".join(notices) + f" Download the answer for all {len(result):,} groups.")
    st.download_button(
        "Download answer", csv_for_download(result), "tablebeam-answer.csv", "text/csv", key="answer_download",
    )
    with st.expander("How this was calculated", expanded=False):
        st.markdown(plain_markdown(calculation_details(answer)), unsafe_allow_html=False)
        if requires_integer_text(result["value"]):
            st.caption("Large integers are shown as text to preserve every digit.")
        st.dataframe(display_result(result), use_container_width=True, hide_index=True)
    selected_data = answer.get("selected_data")
    if selected_data is not None:
        with st.expander("View rows used", expanded=False):
            st.caption(f"First {min(50, len(selected_data)):,} of {len(selected_data):,} rows used.")
            st.dataframe(display_result(selected_data.head(50)), use_container_width=True, hide_index=True)
            st.download_button(
                "Download rows used", csv_for_download(selected_data), "tablebeam-rows-used.csv", "text/csv",
                key="answer_rows_download",
            )


def _render_ai(answer: dict) -> None:
    st.markdown(answer.get("text", ""), unsafe_allow_html=False)
    st.caption("AI answer · " + answer.get("coverage", "Check the sources"))
    st.download_button(
        "Download answer", ai_answer_markdown(answer), "tablebeam-answer.md", "text/markdown", key="answer_download",
    )
    with st.expander("Check the sources", expanded=False):
        st.markdown(plain_markdown(answer.get("coverage", "")), unsafe_allow_html=False)
        for source in answer.get("sources", []):
            st.markdown(plain_markdown(f"{source.get('citation', 'Source')} · row {source.get('row_number', 'unknown')}"), unsafe_allow_html=False)
            st.code(source.get("content", ""), language="text")
        st.markdown("**Table profile supplied to the model**")
        st.code(answer.get("profile", ""), language="text")


def render_answer(answer: dict) -> None:
    """Render one calculation or AI answer using the app's answer schema."""
    with st.container(key="answer_card", border=True):
        st.subheader(plain_markdown(answer["question"]))
        if answer["kind"] == "calculation":
            st.caption(f"Calculated from {answer['selected_rows']:,} of {answer['total_rows']:,} rows")
            _render_calculation(answer)
        elif answer["kind"] == "ai":
            _render_ai(answer)
        else:
            raise ValueError(f"Unknown answer kind: {answer['kind']!r}")
