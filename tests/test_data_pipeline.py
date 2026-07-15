import pandas as pd
import pytest

from data_pipeline import DataValidationError, load_data, normalize_dataframe, profile_dataframe


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
        load_data("/tmp/definitely-not-a-client-tracker-file.csv")


def test_demo_dataset_profiles_date_like_columns():
    profile = profile_dataframe(load_data("sample_data.csv"))
    assert "last_contacted" in profile.date_like_columns
