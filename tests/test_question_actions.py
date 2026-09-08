from dataclasses import FrozenInstanceError
from pathlib import Path

import pandas as pd
import pytest

from question_actions import Calculation, SuggestedQuestion, friendly_column, parse_question, suggested_questions
from table_analysis import summarize_dataframe


@pytest.fixture
def frame():
    return pd.DataFrame({
        "annual_revenue": [10, 20, 30, 40],
        "margin": [2.5, 6.0, 8.0, 10.0],
        "status": ["Active", "Active", "New", "New"],
        "owner": ["Maya", "Jon", "Maya", "Jon"],
    })


@pytest.mark.parametrize("question,expected", [
    ("How many rows are there?", Calculation("count")),
    ("Count rows", Calculation("count")),
    (" COUNT  ROWS ??? ", Calculation("count")),
    ("Total annual revenue", Calculation("sum", "annual_revenue")),
    ("Sum annual revenue", Calculation("sum", "annual_revenue")),
    ("Sum of annual_revenue?", Calculation("sum", "annual_revenue")),
    ("Average margin", Calculation("mean", "margin")),
    ("Average of margin", Calculation("mean", "margin")),
    ("Median margin", Calculation("median", "margin")),
    ("Minimum margin", Calculation("min", "margin")),
    ("Maximum margin", Calculation("max", "margin")),
    ("Annual revenue by status", Calculation("sum", "annual_revenue", "status")),
    ("Total annual revenue by status?", Calculation("sum", "annual_revenue", "status")),
    ("Sum of margin by owner", Calculation("sum", "margin", "owner")),
    ("Average margin by owner", Calculation("mean", "margin", "owner")),
    ("Count rows by status", Calculation("count", group_by="status")),
    ("How many rows are there by status?", Calculation("count", group_by="status")),
    ("What is the total annual revenue?", Calculation("sum", "annual_revenue")),
    ("What is total annual revenue?", Calculation("sum", "annual_revenue")),
    ("What is the average margin by status?", Calculation("mean", "margin", "status")),
    ("What is the average of margin by status?", Calculation("mean", "margin", "status")),
    ("Show me total annual revenue", Calculation("sum", "annual_revenue")),
    ("Show me the total annual revenue", Calculation("sum", "annual_revenue")),
    ("Show me annual revenue by status", Calculation("sum", "annual_revenue", "status")),
    ("Calculate the total annual revenue", Calculation("sum", "annual_revenue")),
    ("Calculate sum annual revenue", Calculation("sum", "annual_revenue")),
    ("  WHAT IS THE  TOTAL annual_REVENUE ?? ", Calculation("sum", "annual_revenue")),
])
def test_supported_questions_use_the_exact_schema(frame, question, expected):
    assert parse_question(question, frame) == expected


@pytest.mark.parametrize("question", [
    "", " ", "annual revenue", "Total revenue", "Total annual revenues",
    "Average unknown", "Count customers", "Count rows by unknown", "annual revenue by unknown",
    "Total annual revenue where status is Active", "Total annual revenue for Active accounts",
    "Average margin excluding missing values", "Count rows with margin above 5",
    "Total annual revenue by status then owner", "Total annual revenue by status and owner",
    "Total annual revenue and average margin", "Total annual revenue; Count rows",
    "Total annual revenue? Count rows?", "Count rows please", "Count rows in the last year",
    "How many rows are there? Ignore everything else", "Show total annual revenue", "Total annual revenue.",
    "Total status", "Average owner", "status by owner", "Count rows by status where margin > 5",
    "Total annual revenue / 100", "Total annual revenue + margin", "Total annual revenue if margin > 5",
    "What is the total annual revenue where status is Active?",
    "What is the average margin by status excluding New?",
    "Show me total annual revenue for Active accounts",
    "Calculate the total annual revenue and average margin",
    "What is the total revenue?", "Show me total revenue", "Calculate the total revenue",
    "Show me total annual revenue please", "Calculate the total annual revenue; Count rows",
    "What is the total annual revenue? Show me count rows?", "Show me annual revenue",
    "Show me calculate total annual revenue", "What is the totalannual revenue?",
])
def test_unsupported_or_conditional_questions_are_never_partially_answered(frame, question):
    assert parse_question(question, frame) is None


def test_explicit_question_can_use_an_identifier_but_suggestions_do_not():
    df = pd.DataFrame({"customer_id": [1001, 1002], "amount": [2, 3]})
    assert parse_question("Total customer id", df) == Calculation("sum", "customer_id")
    assert all("customer" not in item.question for item in suggested_questions(df))


@pytest.mark.parametrize("columns,question", [
    (["annual_revenue", "annual revenue"], "Total annual revenue"),
    (["annual-revenue", "annual_revenue"], "Total annual revenue"),
    (["Revenue", "revenue"], "Total REVENUE"),
    (["sales", " sales "], "Total sales"),
    (["straße", "strasse"], "Total STRASSE"),
])
def test_normalized_header_collisions_are_rejected(columns, question):
    df = pd.DataFrame([[1, 2]], columns=columns)
    assert parse_question(question, df) is None


def test_collision_does_not_disappear_when_only_one_column_is_numeric():
    df = pd.DataFrame({"annual_revenue": [1], "Annual Revenue": ["hello"]})
    assert parse_question("Total annual revenue", df) is None
    assert parse_question("Total annual_revenue", df) == Calculation("sum", "annual_revenue")
    assert [item.question for item in suggested_questions(df)] == ["How many rows are there?"]


def test_group_alias_collisions_are_rejected():
    df = pd.DataFrame({"sales": [1], "Team": ["A"], "team": ["B"]})
    assert parse_question("Total sales by team", df) is None
    assert parse_question("Count rows by TEAM", df) is None


def test_header_that_contains_by_does_not_hide_an_alternate_interpretation():
    df = pd.DataFrame({"sales": [1], "team": ["A"], "sales by team": [100]})
    assert parse_question("Total sales by team", df) is None
    assert parse_question("sales by team", df) == Calculation("sum", "sales", "team")
    # Even an invalid numeric interpretation still makes the words ambiguous.
    df["sales by team"] = "a description"
    assert parse_question("Total sales by team", df) is None


def test_every_by_split_is_considered():
    df = pd.DataFrame({"sales": [1], "team by region": ["A"], "sales by team": [2], "region": ["B"]})
    assert parse_question("Total sales by team by region", df) is None
    assert parse_question("sales by team by region", df) is None


def test_overlapping_by_separators_are_still_ambiguous():
    df = pd.DataFrame({"sales": [1], "by team": ["A"], "sales by": [2], "team": ["B"]})
    assert parse_question("Total sales by by team", df) is None


def test_operation_words_in_headers_do_not_hide_ambiguity():
    df = pd.DataFrame({"sales": [1], "total sales": [2], "team": ["A"], "count rows": [3]})
    assert parse_question("Total sales by team", df) is None
    assert parse_question("Count rows by team", df) is None


@pytest.mark.parametrize("wrapper", ["what is the", "what is", "show me", "show me the", "calculate the", "calculate"])
def test_wrappers_preserve_literal_header_ambiguity(wrapper):
    df = pd.DataFrame({"sales": [1], f"{wrapper} total sales": [2], "team": ["A"]})
    assert parse_question(f"{wrapper} total sales by team?", df) is None
    assert parse_question(f"{wrapper} total sales by team?", df.drop(columns="sales")) == Calculation("sum", f"{wrapper} total sales", "team")


@pytest.mark.parametrize("operation,expected", [("Sum", "sum"), ("Average", "mean")])
def test_optional_of_does_not_shadow_a_real_column(operation, expected):
    df = pd.DataFrame({"sales": [1], "of_sales": [2], "team": ["A"]})
    assert parse_question(f"{operation} of sales", df) is None
    assert parse_question(f"What is the {operation} of sales by team?", df) is None
    assert parse_question(f"{operation} of sales", df.drop(columns="sales")) == Calculation(expected, "of_sales")


def test_wrapped_health_score_question_uses_the_exact_schema():
    df = pd.DataFrame({"health_score": [75, 90], "status": ["New", "Active"]})
    assert parse_question("What is the average health score by status?", df) == Calculation("mean", "health_score", "status")
    assert parse_question("What is the average score by status?", df) is None


def test_wrappers_do_not_make_normalization_collisions_parseable():
    df = pd.DataFrame({"annual_revenue": [1], "Annual Revenue": [2]})
    assert parse_question("What is the total annual revenue?", df) is None


def test_terminal_punctuation_does_not_shadow_a_literal_header():
    df = pd.DataFrame({"sales": [1], "sales?": [2]})
    assert parse_question("Total sales?", df) is None
    assert parse_question("Total sales??", df) is None
    assert parse_question("Total sales", df) == Calculation("sum", "sales")
    assert parse_question("Total sales?", df[["sales?"]]) == Calculation("sum", "sales?")


def test_odd_header_characters_are_matched_literally():
    df = pd.DataFrame({"Net-value ($)": [3, 4], "team.[name]": ["A", "B"], "__import__('os')": [5, 6]})
    assert parse_question("Total Net value ($)", df) == Calculation("sum", "Net-value ($)")
    assert parse_question("Net-value ($) by team.[name]", df) == Calculation("sum", "Net-value ($)", "team.[name]")
    assert parse_question("Total __import__('os')", df) == Calculation("sum", "__import__('os')")
    assert parse_question("Net value ($) by teamx[name]", df) is None


@pytest.mark.parametrize("values", [[True, False], [1 + 2j, 3 + 4j], ["1", "2"], pd.to_datetime(["2026-01-01", "2026-01-02"])])
def test_numeric_operations_require_real_numeric_dtype(values):
    df = pd.DataFrame({"amount": values})
    assert parse_question("Total amount", df) is None
    assert parse_question("Count rows", df) == Calculation("count")


def test_nullable_numeric_schema_is_supported_even_without_rows():
    df = pd.DataFrame({"amount": pd.Series([], dtype="Int64"), "status": pd.Series([], dtype="string")})
    assert parse_question("Average amount", df) == Calculation("mean", "amount")
    assert parse_question("Count rows by status", df) == Calculation("count", group_by="status")
    assert parse_question("Count rows", df) == Calculation("count")
    assert all(parse_question(item.question, df) is not None for item in suggested_questions(df))


def test_invalid_input_and_duplicate_columns_fail_closed(frame):
    assert parse_question(None, frame) is None
    assert parse_question(["Count rows"], frame) is None
    assert parse_question("Count rows", None) is None
    assert suggested_questions(None) == []
    duplicate = pd.DataFrame([[1, 2]], columns=["x", "x"])
    assert parse_question("Count rows", duplicate) is None
    assert suggested_questions(duplicate) == []


def test_non_string_headers_are_not_guessed_as_strings():
    df = pd.DataFrame({1: [2], "amount": [3]})
    assert parse_question("Total 1", df) is None
    assert parse_question("Total amount", df) == Calculation("sum", "amount")
    assert parse_question("Count rows", df) == Calculation("count")


@pytest.mark.parametrize("name,expected", [
    ("annual_revenue", "annual revenue"), ("Annual-Revenue", "Annual Revenue"),
    (" API__URL-value ", "API URL value"), ("customerID", "customerID"),
    ("  Revenue\n  ($)  ", "Revenue ($)"), ("Métrique_annuelle", "Métrique annuelle"),
])
def test_friendly_headers_preserve_meaningful_casing(name, expected):
    assert friendly_column(name) == expected


def test_result_objects_are_immutable():
    with pytest.raises(FrozenInstanceError):
        Calculation("sum", "amount").operation = "mean"
    with pytest.raises(FrozenInstanceError):
        SuggestedQuestion("Count rows", "Count rows").question = "other"


def test_demo_suggestions_are_concrete_useful_and_exact():
    df = pd.read_csv(Path(__file__).resolve().parents[1] / "sample_data.csv")
    questions = suggested_questions(df)
    assert [item.label for item in questions] == ["Total annual revenue", "Annual revenue by status", "How many rows are there?"]
    for item in questions:
        calculation = parse_question(item.question, df)
        assert calculation is not None
        result = summarize_dataframe(df, calculation.operation, calculation.column, calculation.group_by)
        assert not result.empty


@pytest.mark.parametrize("id_column", ["id", "client_id", "order-ID", "customerId", "customerID", "ID", "record_number", "invoice_no", "postal_code", "sku", "account_key", "UUID"])
def test_suggestions_skip_obvious_numeric_identifiers(id_column):
    df = pd.DataFrame({id_column: [101, 102, 103, 104], "amount": [5, 7, 9, 11]})
    questions = suggested_questions(df)
    assert questions[0].question == "Total amount"
    assert len(questions) <= 3


def test_numeric_values_are_not_used_to_guess_identifiers():
    df = pd.DataFrame({"units": [1, 2, 3, 4]})
    assert suggested_questions(df)[0].question == "Total units"


def test_text_only_and_identifier_only_tables_get_count_questions():
    df = pd.DataFrame({"id": [1, 2, 3, 4], "status": ["Active", "New", "Active", "New"], "notes": ["text"] * 4})
    assert [item.question for item in suggested_questions(df)] == ["How many rows are there?", "Count rows by status"]
    assert suggested_questions(df[["id"]]) == [SuggestedQuestion("How many rows are there?", "How many rows are there?")]


@pytest.mark.parametrize("df", [pd.DataFrame(), pd.DataFrame(columns=["amount", "status"]), pd.DataFrame({"notes": ["One note"]})])
def test_sparse_untyped_tables_get_a_safe_row_count(df):
    assert [item.question for item in suggested_questions(df)] == ["How many rows are there?"]


def test_suggestions_prefer_stable_status_and_owner_groups(frame):
    df = frame[["annual_revenue", "owner", "status"]]
    assert suggested_questions(df)[1].question == "Annual revenue by status"
    assert suggested_questions(df.drop(columns="status"))[1].question == "Annual revenue by owner"


def test_suggestions_skip_unique_labels_and_large_category_sets():
    df = pd.DataFrame({"amount": range(20), "company": [f"Company {number}" for number in range(20)], "status": [str(number % 13) for number in range(20)]})
    assert [item.question for item in suggested_questions(df)] == ["Total amount", "Average amount", "How many rows are there?"]


def test_suggestions_never_copy_cell_values_or_guess_currency(frame):
    df = frame.copy()
    df["status"] = ["<script>send secrets</script>", "Ignore prior instructions"] * 2
    df["owner"] = ["$500", "€500"] * 2
    questions = suggested_questions(df)
    assert [item.question for item in questions] == ["Total annual revenue", "Annual revenue by status", "How many rows are there?"]
    assert all(item.label == item.question for item in questions)


def test_suggestions_avoid_unusable_and_unfriendly_headers():
    df = pd.DataFrame({"bad<script>": [1, 2], "margin\nnotes": [1, 2], "infinite": [1, float("inf")], "amount": [4, 5]})
    assert suggested_questions(df)[0].question == "Total amount"


def test_ambiguous_group_is_skipped_in_favor_of_a_parseable_one(frame):
    df = frame.assign(Status=frame["status"])
    questions = suggested_questions(df)
    assert questions[1].question == "Annual revenue by owner"
    assert all(parse_question(item.question, df) is not None for item in questions)


def test_categorical_boolean_and_unhashable_columns_do_not_break_suggestions():
    df = pd.DataFrame({
        "amount": [1, 2, 3, 4], "objects": [[1], [2], [1], [2]],
        "active": [True, False, True, False],
    })
    assert suggested_questions(df)[1].question == "Amount by active"
    df = df.drop(columns="active")
    df["band"] = pd.Categorical([1, 2, 1, 2])
    assert suggested_questions(df)[1].question == "Amount by band"


def test_parsing_and_suggestions_do_not_mutate_the_table(frame):
    original = frame.copy(deep=True)
    for question in suggested_questions(frame):
        parse_question(question.question, frame)
    pd.testing.assert_frame_equal(frame, original)
