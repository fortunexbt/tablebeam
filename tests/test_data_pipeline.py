import pandas as pd
import pytest

from data_pipeline import (
    DataValidationError,
    load_data,
    normalize_dataframe,
    parse_csv_bytes,
    profile_dataframe,
)


def test_normalize_strips_headers_and_drops_empty_rows():
    frame = pd.DataFrame([[" Acme ", 10], [None, None]], columns=[" name ", "revenue"])
    normalized = normalize_dataframe(frame)
    assert normalized.columns.tolist() == ["name", "revenue"]
    assert normalized.to_dict("records") == [{"name": " Acme ", "revenue": 10.0}]


def test_duplicate_headers_are_rejected():
    with pytest.raises(DataValidationError, match="Duplicate column"):
        normalize_dataframe(pd.DataFrame([[1, 2]], columns=["name", " name "]))


def test_profile_contains_actionable_aggregate_facts():
    frame = pd.DataFrame({"id": [1, 2, 2, 3], "segment": ["A", "A", "A", None], "revenue": [1.0, 2.0, 2.0, 3.0]})
    profile = profile_dataframe(frame)
    assert profile.row_count == 4
    assert profile.numeric_columns == ["id", "revenue"]
    assert profile.date_like_columns == []
    assert profile.missing_values["segment"] == 1
    assert profile.duplicate_rows == 1
    assert profile.warnings


def test_load_data_rejects_missing_files():
    with pytest.raises(DataValidationError, match="not found"):
        load_data("/tmp/definitely-not-a-tablebeam-file.csv")


def test_demo_dataset_profiles_date_like_columns():
    profile = profile_dataframe(load_data("sample_data.csv"))
    assert "last_contacted" in profile.date_like_columns


@pytest.mark.parametrize(
    ("content", "message"),
    [
        (b"name,name\nAcme,Beta\n", "Duplicate column"),
        (b"name, name \nAcme,Beta\n", "Duplicate column"),
        (b"name,\nAcme,10\n", "Column 2 has no name"),
        (b'" "\nAcme\nBeta\n', "Column 1 has no name"),
        (b"name,revenue\nAcme,10,extra\n", "3 fields"),
        (b"name,revenue\nAcme\n", "1 fields"),
        ("name,revenue\n\u2003\nAcme,10\n".encode(), "1 fields"),
        (b'name,revenue\n"Acme,10\n', "Could not read CSV"),
        (b"name\n\xff\n", "UTF-8"),
        (b"name\nAcme\x00hidden\n", "null bytes"),
    ],
)
def test_csv_rejects_malformed_original_records_before_pandas(content, message, monkeypatch):
    def must_not_parse(*args, **kwargs):
        pytest.fail("Malformed CSV must be rejected before pandas can reinterpret it")

    monkeypatch.setattr(pd, "read_csv", must_not_parse)
    with pytest.raises(DataValidationError, match=message):
        parse_csv_bytes(content)


def test_csv_preserves_bom_quoted_values_newlines_and_numeric_inference():
    content = '\ufeff name ,amount,note\r\n" Acme, Inc. ",10,"first\r\nsecond"\r\nBeta,,ok\r\n'.encode()
    frame = parse_csv_bytes(content)
    assert frame.columns.tolist() == ["name", "amount", "note"]
    assert frame.loc[0, "name"] == " Acme, Inc. "
    assert frame.loc[0, "note"] == "first\r\nsecond"
    assert frame.loc[0, "amount"] == 10
    assert pd.isna(frame.loc[1, "amount"])


def test_csv_skips_blank_physical_lines_and_drops_empty_data_rows():
    frame = parse_csv_bytes(b"\n  \nname,value\n\nAcme,10\n,\n \n")
    assert frame.to_dict("records") == [{"name": "Acme", "value": 10.0}]


@pytest.mark.parametrize("content", [b"", b"\n \n", b"name,value\n", b"name,value\n,\n"])
def test_csv_rejects_empty_tables(content):
    with pytest.raises(DataValidationError, match="no columns|no non-empty rows"):
        parse_csv_bytes(content)


@pytest.mark.parametrize(
    ("content", "limits", "message"),
    [
        (b"name\nAcme\n", {"max_bytes": 3}, "safe limit"),
        (b"name\nAcme\nBeta\n", {"max_rows": 1}, "safe limit of 1 rows"),
    ],
)
def test_csv_limits_apply_before_dataframe_allocation(content, limits, message, monkeypatch):
    def must_not_parse(*args, **kwargs):
        pytest.fail("Oversized CSV must be rejected before dataframe allocation")

    monkeypatch.setattr(pd, "read_csv", must_not_parse)
    with pytest.raises(DataValidationError, match=message):
        parse_csv_bytes(content, **limits)


def test_file_loading_uses_raw_header_validation(tmp_path):
    path = tmp_path / "duplicate.csv"
    path.write_bytes(b"name,name\nAcme,Beta\n")
    with pytest.raises(DataValidationError, match="Duplicate column"):
        load_data(str(path))


def test_file_loading_applies_custom_row_limit(tmp_path):
    path = tmp_path / "rows.csv"
    path.write_bytes(b"name\nAcme\nBeta\n")
    with pytest.raises(DataValidationError, match="safe limit of 1 rows"):
        load_data(str(path), max_rows=1)


def test_csv_boolean_column_with_missing_cells_retains_boolean_type():
    from data_pipeline import parse_csv_bytes
    frame = parse_csv_bytes(b"id,flag\n1,true\n2,\n3,false\n")
    assert str(frame["flag"].dtype) == "boolean"
    assert bool(frame.loc[0, "flag"]) is True
    assert pd.isna(frame.loc[1, "flag"])
    assert bool(frame.loc[2, "flag"]) is False


@pytest.mark.parametrize("value", [2**53 + 1, 2**63 - 1, -(2**63), 2**64 - 1])
def test_csv_nullable_integers_keep_exact_values_through_calculation_and_export(value):
    from table_analysis import csv_for_download, summarize_dataframe

    frame = parse_csv_bytes(f"amount,team\n{value},A\n,B\n".encode())
    assert pd.api.types.is_integer_dtype(frame["amount"])
    assert int(frame.loc[0, "amount"]) == value
    assert pd.isna(frame.loc[1, "amount"])
    for operation in ["sum", "min", "max"]:
        result = summarize_dataframe(frame, operation, "amount")
        assert int(result.loc[0, "value"]) == value
        assert str(value) in csv_for_download(result).decode("utf-8-sig")
    grouped = summarize_dataframe(frame, "sum", "amount", "team")
    assert int(grouped.loc[grouped["team"] == "A", "value"].iloc[0]) == value
    assert pd.isna(grouped.loc[grouped["team"] == "B", "value"].iloc[0])
    assert str(value) in csv_for_download(frame).decode("utf-8-sig")


def test_csv_keeps_out_of_range_integer_values_as_text():
    frame = parse_csv_bytes(f"amount,team\n{2**64},A\n,B\n".encode())
    assert frame.loc[0, "amount"] == str(2**64)
    assert pd.isna(frame.loc[1, "amount"])


def test_csv_integer_dtype_selection_uses_standard_missing_values():
    frame = parse_csv_bytes(f"amount,team\n{-(2**63)},A\nNA,B\n".encode())
    assert int(frame.loc[0, "amount"]) == -(2**63)
    assert pd.isna(frame.loc[1, "amount"])
