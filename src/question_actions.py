"""Recognize a small, unambiguous set of whole-table questions locally.

This is deliberately not a natural-language query engine. A question must
match one complete supported form and name existing columns; unsupported
wording is left for the caller to explain or send to an optional model.
"""

from __future__ import annotations

from dataclasses import dataclass
import re

import pandas as pd


@dataclass(frozen=True)
class Calculation:
    operation: str
    column: str | None = None
    group_by: str | None = None


@dataclass(frozen=True)
class SuggestedQuestion:
    label: str
    question: str


_OPERATIONS = {
    "total": "sum",
    "sum": "sum",
    "sum of": "sum",
    "average": "mean",
    "average of": "mean",
    "median": "median",
    "minimum": "min",
    "maximum": "max",
}
_COUNT_PHRASES = ("how many rows are there", "count rows")
_QUESTION_WRAPPERS = ("what is the ", "what is ", "show me the ", "show me ", "calculate the ", "calculate ")


def friendly_column(name: str) -> str:
    """Humanize separators while preserving the header's spelling and casing."""

    return " ".join(re.sub(r"[_-]+", " ", name).split())


def _normalize(text: str) -> str:
    return " ".join(text.split()).casefold()


def _column_aliases(df: pd.DataFrame) -> dict[str, str | None]:
    # None marks a collision even if only one of its columns is numeric.
    # A data type must never silently decide which same-named field was meant.
    aliases: dict[str, str | None] = {}
    for column in df.columns:
        if not isinstance(column, str):
            continue
        for alias in {_normalize(column), _normalize(friendly_column(column))}:
            if alias:
                if alias in aliases and aliases[alias] != column:
                    aliases[alias] = None
                else:
                    aliases[alias] = column
    return aliases


def _question_forms(question: str) -> set[str]:
    # Keep both literal and punctuation-stripped readings. A header ending in
    # '?' must not silently shadow another header without that punctuation.
    question = _normalize(question)
    forms = {question}
    while question.endswith("?"):
        question = question[:-1].rstrip()
        forms.add(question)
    # Unwrap once, keeping the original forms in play. A literal header such
    # as "show me total sales" can otherwise silently change a grouped query.
    for form in tuple(forms):
        for wrapper in _QUESTION_WRAPPERS:
            if form.startswith(wrapper):
                forms.add(form[len(wrapper):])
    return forms


def _real_numeric(series: pd.Series) -> bool:
    return (
        pd.api.types.is_numeric_dtype(series.dtype)
        and not pd.api.types.is_bool_dtype(series.dtype)
        and not pd.api.types.is_complex_dtype(series.dtype)
    )


def parse_question(question: str, df: pd.DataFrame) -> Calculation | None:
    """Return an exact calculation only for a complete, unambiguous question.

    Supported forms are ``Count rows``, ``How many rows are there?``, and
    ``Total / Sum [of] / Average [of] / Median / Minimum / Maximum <column>``.
    Each accepts ``by <group>``; ``<column> by <group>`` means a numeric sum.
    A single ``What is [the] / Show me [the] / Calculate [the]`` wrapper is
    optional and is checked alongside the original, literal interpretation.
    Case, whitespace, and terminal question marks are insignificant, unless
    they would make the choice of actual column ambiguous. No filters,
    partial matches, inferred column names, or generated code are supported.
    """

    if not isinstance(question, str) or not isinstance(df, pd.DataFrame) or not df.columns.is_unique:
        return None
    aliases = _column_aliases(df)
    matches: set[Calculation] = set()
    ambiguous = False

    def add(operation: str, column_alias: str | None = None, group_alias: str | None = None) -> None:
        nonlocal ambiguous
        requested = [alias for alias in (column_alias, group_alias) if alias is not None]
        if not all(alias in aliases for alias in requested):
            return
        if any(aliases[alias] is None for alias in requested):
            ambiguous = True
            return
        matches.add(Calculation(
            operation,
            aliases[column_alias] if column_alias is not None else None,
            aliases[group_alias] if group_alias is not None else None,
        ))

    def add_expression(operation: str, expression: str, *, allow_ungrouped: bool) -> None:
        if allow_ungrouped:
            add(operation, expression)
        # Consider every split, because "by" can also occur in a header.
        for separator in re.finditer(r"(?= by )", expression):
            add(operation, expression[:separator.start()], expression[separator.start() + 4:])

    for form in _question_forms(question):
        for phrase in _COUNT_PHRASES:
            if form == phrase:
                add("count")
            elif form.startswith(phrase + " by "):
                add("count", group_alias=form[len(phrase + " by "):])
        for prefix, operation in _OPERATIONS.items():
            if form.startswith(prefix + " "):
                add_expression(operation, form[len(prefix) + 1:], allow_ungrouped=True)
        add_expression("sum", form, allow_ungrouped=False)

    if ambiguous or len(matches) != 1:
        return None
    result = next(iter(matches))
    if result.operation != "count" and not _real_numeric(df[result.column]):
        return None
    return result


def _looks_like_identifier(name: str) -> bool:
    separated = re.sub(r"(?<=[a-z0-9])(?=[A-Z])", " ", name)
    words = re.findall(r"[a-z0-9]+", separated.casefold())
    identifiers = {"id", "ids", "identifier", "identifiers", "uuid", "guid", "sku", "key", "code"}
    return bool(
        identifiers.intersection(words)
        or (len(words) > 1 and words[-1] in {"number", "no"})
        or " ".join(words) in {"zip", "zipcode", "postcode", "phone", "telephone", "row number"}
    )


def _suggestible_name(name: object) -> bool:
    # Suggestions are concise UI copy. Unusual headers remain usable in typed
    # questions, but markup, control characters, and long prose stay off chips.
    return (
        isinstance(name, str)
        and 0 < len(friendly_column(name)) <= 60
        and not any(ord(char) < 32 for char in name)
        and not any(char in name for char in "<>`*[]{}\\")
        and not name.lstrip().startswith(("=", "+", "@"))
    )


def _grouping_columns(df: pd.DataFrame) -> list[str]:
    candidates: list[tuple[int, int, int, str]] = []
    for index, column in enumerate(df.columns):
        if not _suggestible_name(column) or _looks_like_identifier(column):
            continue
        series = df[column]
        categorical = isinstance(series.dtype, pd.CategoricalDtype)
        boolean = pd.api.types.is_bool_dtype(series.dtype)
        text = pd.api.types.is_string_dtype(series.dtype)
        if not (categorical or boolean or text):
            continue
        if text and not all(isinstance(value, str) for value in series.dropna()):
            continue
        try:
            cardinality = series.nunique(dropna=True)
        except TypeError:
            continue
        # A nearly unique list of names is not an informative default chart.
        if not 2 <= cardinality <= 12 or (len(df) > 3 and cardinality == series.count()):
            continue
        priority = {"status": 0, "owner": 1}.get(_normalize(friendly_column(column)), 2)
        candidates.append((priority, cardinality, index, column))
    return [column for _, _, _, column in sorted(candidates)]


def suggested_questions(df: pd.DataFrame) -> list[SuggestedQuestion]:
    """Offer at most three useful, parseable questions using only column names.

    Real numeric measures are preferred in schema order, excluding headers
    that clearly denote identifiers. Groups use small categorical columns,
    preferring status and owner. Cell contents are never copied into a prompt.
    """

    if not isinstance(df, pd.DataFrame) or not df.columns.is_unique:
        return []
    count = SuggestedQuestion("How many rows are there?", "How many rows are there?")
    groups = _grouping_columns(df)
    for column in df.columns:
        if not _suggestible_name(column) or _looks_like_identifier(column) or not _real_numeric(df[column]):
            continue
        if df[column].isin([float("inf"), float("-inf")]).any():
            continue
        name = friendly_column(column)
        total = f"Total {name}"
        if parse_question(total, df) != Calculation("sum", column):
            continue
        suggestions = [SuggestedQuestion(total, total)]
        for group in groups:
            question = f"{name[:1].upper()}{name[1:]} by {friendly_column(group)}"
            if parse_question(question, df) == Calculation("sum", column, group):
                suggestions.append(SuggestedQuestion(question, question))
                break
        if len(suggestions) == 1:
            average = f"Average {name}"
            if parse_question(average, df) == Calculation("mean", column):
                suggestions.append(SuggestedQuestion(average, average))
        return suggestions + [count]
    suggestions = [count]
    for group in groups:
        question = f"Count rows by {friendly_column(group)}"
        if parse_question(question, df) == Calculation("count", group_by=group):
            suggestions.append(SuggestedQuestion(question, question))
            break
    return suggestions
