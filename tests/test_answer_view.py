"""Answer rendering keeps the main result simple and the evidence exact."""

import csv
from io import StringIO

import altair as alt
import pandas as pd
import pytest
from streamlit.testing.v1 import AppTest

from answer_view import (
    MAX_EXACT_JS_INTEGER,
    ai_answer_markdown,
    calculation_details,
    chart_data,
    chart_spec,
    display_result,
    format_value,
    plain_markdown,
    requires_integer_text,
)
from table_analysis import csv_for_download, summarize_dataframe


def calculation(frame, operation="sum", column="amount", group_by=None, **extra):
    return {
        "kind": "calculation", "question": "What is the total?", "operation": operation,
        "column": column, "group_by": group_by,
        "result": summarize_dataframe(frame, operation, column, group_by),
        "selected_rows": len(frame), "total_rows": len(frame),
        "filter_label": "All rows", "missing_values": int(frame[column].isna().sum()) if column else 0,
        "selected_data": frame, **extra,
    }


def render(answer):
    app = AppTest.from_string(
        "import streamlit as st\n"
        "from answer_view import render_answer\n"
        "if 'answer' in st.session_state:\n"
        "    render_answer(st.session_state.answer)\n"
    ).run()
    app.session_state.answer = answer
    return app.run()


@pytest.mark.parametrize("value", [2**53 + 1, 2**63 - 1, 3 * (2**63 - 1), -(2**70 + 3)])
def test_exact_integer_formatting_display_and_csv_round_trip(value):
    frame = pd.DataFrame({"value": pd.Series([value], dtype=object), "rows": [3]})
    original = frame.copy(deep=True)
    assert format_value(frame["value"].iloc[0]) == f"{value:,}"
    assert display_result(frame)["value"].iloc[0] == str(value)
    exported = list(csv.reader(StringIO(csv_for_download(frame).decode("utf-8-sig"))))
    assert exported == [["value", "rows"], [str(value), "3"]]
    pd.testing.assert_frame_equal(frame, original)


@pytest.mark.parametrize("dtype,value", [("Int64", 2**53 + 1), ("Int64", -(2**63)), ("UInt64", 2**64 - 1)])
def test_nullable_integer_preview_retains_each_digit_and_missing_cell(dtype, value):
    frame = pd.DataFrame({"account_id": pd.Series([value, None, value - 1 if value > 0 else value + 1], dtype=dtype)}, index=[0, 1, 2])
    original = frame.copy(deep=True)
    expected = [str(value), None, str(value - 1 if value > 0 else value + 1)]
    assert display_result(frame)["account_id"].tolist() == expected
    pd.testing.assert_frame_equal(frame, original)


def test_integer_chart_threshold_and_nullable_values():
    assert not requires_integer_text(pd.Series([MAX_EXACT_JS_INTEGER, None], dtype="Int64"))
    assert requires_integer_text(pd.Series([MAX_EXACT_JS_INTEGER + 1, None], dtype="Int64"))
    assert requires_integer_text(pd.Series([-(2**63), None], dtype="Int64"))
    assert format_value(pd.NA) == "No values"
    assert format_value(None) == "No values"


def test_grouped_chart_is_stable_limited_and_uses_fixed_field_names():
    frame = pd.DataFrame({
        "group['unsafe']": ["tied first", "tied second"] + [f"group {i}" for i in range(25)],
        "value": [100, 100] + list(range(25)), "rows": [1] * 27,
    })
    original = frame.copy(deep=True)
    plot = chart_data(frame)
    assert list(plot.columns) == ["group_label", "amount", "value_label", "display_label"]
    assert plot["group_label"].tolist()[:2] == ["tied first", "tied second"]
    assert len(plot) == 20
    spec = chart_spec(plot)
    assert spec["encoding"]["y"]["field"] == "group_label"
    assert spec["encoding"]["x"]["field"] == "amount"
    assert "group['unsafe']" not in str(spec)
    pd.testing.assert_frame_equal(frame, original)


def test_mixed_sign_chart_separates_value_labels_from_bars_and_keeps_exact_tooltips():
    frame = pd.DataFrame({
        "group": ["profit", "break even", "loss"],
        "value": [1_234_567_890_123, 0, -1_234_567_890_123], "rows": [1, 1, 1],
    })
    plot = chart_data(frame)
    assert plot["amount"].tolist() == frame["value"].tolist()
    assert plot["value_label"].tolist() == ["1,234,567,890,123", "0", "-1,234,567,890,123"]
    assert plot["display_label"].tolist() == ["1.2346e+12", "0", "-1.2346e+12"]
    spec = chart_spec(plot)
    # Validate the actual Vega-Lite contract, including the fixed right-edge
    # position that keeps both signs outside the bars and away from group names.
    alt.Chart.from_dict({**spec, "data": {"values": plot.to_dict("records")}}).to_dict(validate=True)
    text_layer = next(layer for layer in spec["layer"] if layer["mark"]["type"] == "text")
    assert text_layer["encoding"]["x"] == {"value": "width"}
    assert text_layer["mark"]["align"] == "left"
    assert text_layer["mark"]["dx"] > 0
    assert spec["encoding"]["tooltip"][1]["field"] == "value_label"


def test_chart_distinguishes_missing_group_from_literal_missing_label():
    frame = pd.DataFrame({"group": [None, "(missing)", "other"], "value": [4, 3, None], "rows": [1, 1, 1]})
    plot = chart_data(frame)
    assert plot["group_label"].is_unique
    assert plot["amount"].tolist() == [4.0, 3.0]


def test_chart_omitted_for_huge_integer_and_empty_for_all_missing():
    assert chart_data(pd.DataFrame({"group": ["a"], "value": [2**63 + 1], "rows": [1]})) is None
    plot = chart_data(pd.DataFrame({"group": ["a"], "value": [None], "rows": [1]}))
    assert plot.empty


def test_calculation_details_explain_scope_and_missing_values():
    answer = calculation(pd.DataFrame({"amount": [2, None]}), total_rows=8, filter_label="Status is Active")
    details = calculation_details(answer)
    assert "Sum of amount" in details
    assert "1 missing value is excluded" in details
    assert "Rows used: 2 of 8. Condition: Status is Active" in details
    assert "No values" in details
    counted = calculation(pd.DataFrame({"amount": [None]}), "count")
    assert "Every selected row is counted" in calculation_details(counted)


def test_plain_labels_escape_html_and_markdown_images():
    label = plain_markdown('<img src=x onerror="alert(1)"> ![remote](https://invalid.test/x)')
    assert "<img" not in label
    assert "&lt;img" in label
    assert r"\!\[remote\]\(https://invalid\.test/x\)" in label


def test_ai_export_keeps_provenance_and_source_backticks_inside_code():
    answer = {
        "kind": "ai", "question": "<script>alert(1)</script>",
        "text": "An answer [Source 1]. <script>bad()</script>",
        "coverage": "Matching rows · 1 of 10 rows", "profile": "Rows: 10\n```\n## profile text",
        "sources": [{"citation": "[Source 1]", "row_number": 8, "content": "note: ```\n```\n# fake heading\n<script>bad</script>"}],
    }
    exported = ai_answer_markdown(answer)
    assert "Matching rows · 1 of 10 rows" in exported
    assert r"### \[Source 1\] · row 8" in exported
    assert "    note: ```\n    ```\n    # fake heading\n    <script>bad</script>" in exported
    assert "    Rows: 10\n    ```\n    ## profile text" in exported
    assert "\n<script>" not in exported
    assert "&lt;script&gt;bad()&lt;/script&gt;" in exported


def test_scalar_answer_has_one_metric_and_collapsed_evidence():
    app = render(calculation(pd.DataFrame({"amount": [2**63 - 1, 2**63 - 1]})))
    assert not app.exception
    assert app.metric[0].label == "Result"
    assert app.metric[0].value == "18,446,744,073,709,551,614"
    assert [item.label for item in app.expander] == ["How this was calculated", "View rows used"]
    assert all(not item.proto.expanded for item in app.expander)
    assert app.dataframe[0].value["value"].iloc[0] == "18446744073709551614"


def test_grouped_huge_integer_renders_exact_text_without_arrow_overflow():
    frame = pd.DataFrame({"team": ["A"] * 3, "amount": [2**63 - 1] * 3})
    app = render(calculation(frame, group_by="team"))
    assert not app.exception
    assert app.dataframe[0].value["value"].iloc[0] == "27670116110564327421"
    assert not app.get("arrow_vega_lite_chart")


def test_empty_filter_and_missing_values_are_distinct_states():
    empty = render(calculation(pd.DataFrame({"amount": pd.Series([], dtype="int64")})))
    assert not empty.exception
    assert empty.info[0].value == "No rows match this condition"
    assert not empty.metric
    missing = render(calculation(pd.DataFrame({"amount": pd.Series([None], dtype="Float64")})))
    assert not missing.exception
    assert missing.metric[0].value == "No values"


def test_missing_groups_are_disclosed_without_claiming_twenty_are_plotted():
    frame = pd.DataFrame({
        "team": [f"Team {index}" for index in range(23)],
        "amount": [100, -100] + [None] * 21,
    })
    app = render(calculation(frame, group_by="team"))
    assert not app.exception
    notices = [item.value for item in app.caption]
    assert "21 groups have no values. Download the answer for all 23 groups." in notices
    assert not any("Top" in notice for notice in notices)
    full_result = app.dataframe[0].value
    assert len(full_result) == 23
    assert full_result["value"].isna().sum() == 21


def test_group_limit_counts_groups_with_values_separately_from_missing_groups():
    frame = pd.DataFrame({
        "team": [f"Team {index}" for index in range(27)],
        "amount": list(range(25)) + [None, None],
    })
    app = render(calculation(frame, group_by="team"))
    assert not app.exception
    assert any(
        item.value == "Top 20 of 25 groups with values. 2 groups have no values. Download the answer for all 27 groups."
        for item in app.caption
    )
    assert len(app.dataframe[0].value) == 27


def test_all_missing_grouped_answer_retains_and_discloses_every_group():
    frame = pd.DataFrame({"team": ["A", "B"], "amount": pd.Series([None, None], dtype="Float64")})
    app = render(calculation(frame, group_by="team"))
    assert not app.exception
    assert app.metric[0].value == "No values"
    assert any(item.value == "2 groups have no values. Download the answer for all 2 groups." for item in app.caption)
    assert app.dataframe[0].value["team"].tolist() == ["A", "B"]


def test_question_and_ai_text_cannot_enable_html_rendering():
    app = render({
        "kind": "ai", "question": '<img src=x onerror="alert(1)">',
        "text": '<script>alert("model")</script>', "sources": [], "coverage": "1 of 2 rows", "profile": "Rows: 2",
    })
    assert not app.exception
    assert "&lt;img" in app.subheader[0].value
    assert all(not element.proto.allow_html for element in app.markdown)
    assert [item.label for item in app.expander] == ["Check the sources"]
