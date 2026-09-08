import csv
from io import StringIO

import pandas as pd
import pytest

from table_analysis import (
    FilterSpec,
    TableAnalysisError,
    csv_for_download,
    filter_dataframe,
    group_result_column,
    summarize_dataframe,
)


@pytest.fixture
def frame():
    return pd.DataFrame(
        {"team": ["West", "East", "West", None, "Empty"], "sales": [10.0, 20.0, 30.0, 5.0, None]},
        index=[8, 2, 11, 4, 7],
    )


@pytest.mark.parametrize("operation,expected", [("count", 5), ("sum", 65), ("mean", 16.25), ("median", 15), ("min", 5), ("max", 30)])
def test_complete_table_summary(frame, operation, expected):
    result = summarize_dataframe(frame, operation, "sales")
    assert result.to_dict("records") == [{"value": expected, "rows": 5}]


def test_count_needs_no_measure_and_includes_missing(frame):
    assert summarize_dataframe(frame, "count").iloc[0].to_dict() == {"value": 5, "rows": 5}
    assert summarize_dataframe(frame, "count", "team").iloc[0]["value"] == 5


@pytest.mark.parametrize("operation", ["sum", "mean", "median", "min", "max"])
def test_all_missing_numeric_results_are_null(operation):
    source = pd.DataFrame({"sales": pd.Series([None, None], dtype="Float64")})
    result = summarize_dataframe(source, operation, "sales")
    assert pd.isna(result.loc[0, "value"])
    assert result.loc[0, "rows"] == 2


def test_grouped_summary_includes_missing_groups_and_missing_measures(frame):
    result = summarize_dataframe(frame, "sum", "sales", "team")
    assert result.columns.tolist() == ["team", "value", "rows"]
    assert result["value"].iloc[:3].tolist() == [40, 20, 5]
    assert result["rows"].tolist() == [2, 1, 1, 1]
    assert pd.isna(result.loc[2, "team"])
    assert result.loc[3, "team"] == "Empty"
    assert pd.isna(result.loc[3, "value"])


def test_grouped_count_and_ties_preserve_first_appearance(frame):
    result = summarize_dataframe(frame, "count", group_by="team")
    assert result["value"].tolist() == [2, 1, 1, 1]
    assert result["team"].iloc[:2].tolist() == ["West", "East"]
    assert pd.isna(result.loc[2, "team"])
    assert result.loc[3, "team"] == "Empty"


@pytest.mark.parametrize("name", ["value", "rows", "group"])
def test_group_names_do_not_collide_with_aggregate_columns(name):
    source = pd.DataFrame({name: [1, 1, 2]})
    result = summarize_dataframe(source, "sum", name, name)
    assert result.columns.tolist() == [group_result_column(name), "value", "rows"]
    assert result["value"].tolist() == [2, 2]
    assert result["rows"].tolist() == [2, 1]
    assert result.iloc[:, 0].tolist() == [1, 2]


def test_categorical_groups_include_missing_but_not_unused_categories():
    source = pd.DataFrame({"team": pd.Categorical(["A", None], categories=["A", "B"]), "sales": [2, 3]})
    result = summarize_dataframe(source, "sum", "sales", "team")
    assert len(result) == 2
    assert pd.isna(result.loc[0, "team"])
    assert result["value"].tolist() == [3, 2]


def test_integer_sum_does_not_silently_overflow():
    source = pd.DataFrame({"team": ["A", "A"], "sales": [2**63 - 1, 2**63 - 1]})
    assert summarize_dataframe(source, "sum", "sales").loc[0, "value"] == 2**64 - 2
    assert summarize_dataframe(source, "sum", "sales", "team").loc[0, "value"] == 2**64 - 2


@pytest.mark.parametrize("operation", ["sum", "mean", "median", "min", "max"])
def test_aggregates_reject_infinity(operation):
    with pytest.raises(TableAnalysisError, match="finite"):
        summarize_dataframe(pd.DataFrame({"sales": [1.0, float("inf")]}), operation, "sales")


@pytest.mark.filterwarnings("ignore:overflow encountered:RuntimeWarning")
def test_floating_point_aggregate_overflow_is_rejected():
    with pytest.raises(TableAnalysisError, match="overflowed"):
        summarize_dataframe(pd.DataFrame({"sales": [1e308, 1e308]}), "sum", "sales")


def test_grouped_overflow_cannot_be_misreported_as_missing_data():
    source = pd.DataFrame({"team": ["A"] * 3, "sales": [1e308, 1e308, -1e308]})
    with pytest.raises(TableAnalysisError, match="overflowed"):
        summarize_dataframe(source, "mean", "sales", "team")


@pytest.mark.parametrize("operation,expected", [("mean", 20), ("median", 20), ("min", 10), ("max", 30)])
def test_grouped_operations_and_all_null_group(operation, expected):
    source = pd.DataFrame({"team": ["A", "A", "B"], "sales": [10.0, 30.0, None]})
    result = summarize_dataframe(source, operation, "sales", "team")
    assert result.loc[0, "value"] == expected
    assert result.loc[0, "rows"] == 2
    assert pd.isna(result.loc[1, "value"])
    assert result.loc[1, "rows"] == 1


def test_nullable_integer_group_sum_preserves_all_missing_group():
    source = pd.DataFrame({"team": ["A", "A", "B"], "sales": pd.Series([None, None, 4], dtype="Int64")})
    result = summarize_dataframe(source, "sum", "sales", "team")
    assert result.loc[0, "value"] == 4
    assert pd.isna(result.loc[1, "value"])


def test_filters_work_with_duplicate_row_indices():
    source = pd.DataFrame({"sales": [1, 2, 3]}, index=[1, 1, 2])
    result = filter_dataframe(source, [FilterSpec("sales", "gt", 1)])
    assert result.index.tolist() == [1, 2]
    assert result["sales"].tolist() == [2, 3]


def test_malformed_requests_are_reported_as_validation_errors(frame):
    actions = [
        lambda: filter_dataframe(frame, None),
        lambda: filter_dataframe(frame, ["not a filter"]),
        lambda: filter_dataframe(frame, [FilterSpec("sales", [], 1)]),
        lambda: summarize_dataframe(frame, []),
        lambda: filter_dataframe([1, 2, 3], []),
    ]
    for action in actions:
        with pytest.raises(TableAnalysisError):
            action()


def test_filters_apply_together_preserve_indices_and_do_not_mutate(frame):
    original = frame.copy(deep=True)
    result = filter_dataframe(frame, [FilterSpec("team", "contains", "WEST"), FilterSpec("sales", "gt", 10)])
    assert result.index.tolist() == [11]
    result.loc[11, "sales"] = 0
    pd.testing.assert_frame_equal(frame, original)
    pd.testing.assert_frame_equal(filter_dataframe(frame, []), frame)


@pytest.mark.parametrize("op,value,indices", [("eq", 20, [2]), ("ne", 20, [8, 11, 4]), ("gt", 20, [11]), ("ge", 20, [2, 11]), ("lt", 10, [4]), ("le", 10, [8, 4]), ("is_missing", None, [7]), ("not_missing", None, [8, 2, 11, 4])])
def test_numeric_filter_operators(frame, op, value, indices):
    assert filter_dataframe(frame, [FilterSpec("sales", op, value)]).index.tolist() == indices


def test_text_comparisons_exclude_missing_and_contain_literal_characters():
    source = pd.DataFrame({"text": ["A.[x]", "a.*", "abc", None]})
    assert filter_dataframe(source, [FilterSpec("text", "contains", ".*")]).index.tolist() == [1]
    assert filter_dataframe(source, [FilterSpec("text", "contains", "a.[X]")]).index.tolist() == [0]
    assert filter_dataframe(source, [FilterSpec("text", "eq", "abc")]).index.tolist() == [2]
    assert filter_dataframe(source, [FilterSpec("text", "ne", "abc")]).index.tolist() == [0, 1]


def test_nullable_bool_and_datetime_filters():
    source = pd.DataFrame({"flag": pd.Series([True, False, None], dtype="boolean"), "day": pd.to_datetime(["2026-01-01", "2026-01-03", None])})
    assert filter_dataframe(source, [FilterSpec("flag", "eq", False)]).index.tolist() == [1]
    assert filter_dataframe(source, [FilterSpec("day", "ge", "2026-01-02")]).index.tolist() == [1]
    with pytest.raises(TableAnalysisError, match="timezone"):
        filter_dataframe(source, [FilterSpec("day", "gt", "2026-01-02T00:00:00Z")])


def test_empty_filter_and_summary_results_keep_schema(frame):
    empty = filter_dataframe(frame, [FilterSpec("sales", "gt", 100)])
    assert empty.empty
    assert empty.columns.tolist() == frame.columns.tolist()
    assert summarize_dataframe(empty, "count").to_dict("records") == [{"value": 0, "rows": 0}]
    assert pd.isna(summarize_dataframe(empty, "sum", "sales").loc[0, "value"])
    grouped = summarize_dataframe(empty, "sum", "sales", "team")
    assert grouped.empty
    assert grouped.columns.tolist() == ["team", "value", "rows"]


@pytest.mark.parametrize("operation,column,group", [("average", "sales", None), ("sum", None, None), ("mean", "team", None), ("count", None, "absent"), ("sum", "absent", None), ("count", "absent", None)])
def test_invalid_summary_inputs_raise_clear_errors(frame, operation, column, group):
    with pytest.raises(TableAnalysisError):
        summarize_dataframe(frame, operation, column, group)


@pytest.mark.parametrize("spec", [FilterSpec("absent", "eq", 1), FilterSpec("sales", "eval", "1+1"), FilterSpec("sales", "eq", "20"), FilterSpec("sales", "eq", True), FilterSpec("sales", "gt", float("nan")), FilterSpec("sales", "gt", float("inf")), FilterSpec("team", "gt", "West"), FilterSpec("team", "eq", None), FilterSpec("team", "contains", 10), FilterSpec("sales", "contains", "1")])
def test_invalid_filter_inputs_raise_clear_errors(frame, spec):
    with pytest.raises(TableAnalysisError):
        filter_dataframe(frame, [spec])


def test_duplicate_headers_and_incompatible_measure_types_are_rejected():
    duplicate = pd.DataFrame([[1, 2]], columns=["a", "a"])
    for action in [lambda: filter_dataframe(duplicate, []), lambda: summarize_dataframe(duplicate, "count"), lambda: csv_for_download(duplicate)]:
        with pytest.raises(TableAnalysisError, match="Duplicate"):
            action()
    for values in [[True, False], [1 + 2j, 2 + 3j]]:
        with pytest.raises(TableAnalysisError, match="real numeric"):
            summarize_dataframe(pd.DataFrame({"measure": values}), "sum", "measure")


def test_csv_export_is_bom_encoded_formula_safe_and_round_trips_quotes():
    source = pd.DataFrame({"=danger": ["=SUM(1,2)", "+1", "-12", "@command", "  =cmd", "\ttext", "\rtext", "\ntext", 'He said "hello", café', None], "number": [-2.5] * 10}, index=range(10, 20))
    original = source.copy(deep=True)
    exported = csv_for_download(source)
    assert exported.startswith(b"\xef\xbb\xbf")
    rows = list(csv.reader(StringIO(exported.decode("utf-8-sig"))))
    assert rows[0] == ["'=danger", "number"]
    assert [row[0] for row in rows[1:9]] == ["'=SUM(1,2)", "'+1", "'-12", "'@command", "'  =cmd", "'\ttext", "'\rtext", "'\ntext"]
    assert rows[9][0] == 'He said "hello", café'
    assert rows[10][0] == ""
    assert all(row[1] == "-2.5" for row in rows[1:])
    pd.testing.assert_frame_equal(source, original)


def test_empty_csv_keeps_headers():
    source = pd.DataFrame(columns=["safe", "+header"])
    assert csv_for_download(source).decode("utf-8-sig") == "safe,'+header\r\n"


def test_decimal_threshold_preserves_large_integer_boundary():
    from decimal import Decimal
    frame = pd.DataFrame({"n": [9007199254740992, 9007199254740993]})
    selected = filter_dataframe(frame, [FilterSpec("n", "gt", Decimal("9007199254740992.5"))])
    assert selected["n"].tolist() == [9007199254740993]
