"""Run one calculation spec through each executor and an exact reference.

A spec is (operation, measure column, group column). Every executor reads the
same CSV bytes with its own defaults, the way a person or an agent would use
it without hand-tuning:

- Tablebeam: the browser demo's engine (web/engine.py) asked the documented
  question form, so its parser, CSV reader and calculation are all exercised.
- pandas: ``pd.read_csv`` then the Series or GroupBy method of the same name.
- SQLite: the sqlite3 shell's ``.import`` into a new table, which stores every
  field as TEXT, then SUM/AVG/MEDIAN/MIN/MAX/COUNT(*).
- DuckDB: ``read_csv`` auto-detection, then the same SQL aggregates.

Values come back as Python numbers or strings, keyed by normalised group
label. The reference parses each cell the way the manifest says a person
reads it and aggregates with exact fractions.
"""

from __future__ import annotations

import csv
import io
import math
import re
import sqlite3
import sys
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from fractions import Fraction
from numbers import Integral, Real
from pathlib import Path
from typing import Any

import duckdb
import pandas as pd

REPO = Path(__file__).resolve().parent.parent
sys.path[:0] = [str(REPO / "src"), str(REPO / "web")]

import engine  # noqa: E402  (web/engine.py, the demo's entry point)

ALL = "(all rows)"
OPERATIONS = ("count", "sum", "mean", "median", "min", "max")
QUESTION_WORDS = {"sum": "Total", "mean": "Average", "median": "Median", "min": "Minimum", "max": "Maximum"}
SQL_FUNCTIONS = {"count": "COUNT", "sum": "SUM", "mean": "AVG", "median": "MEDIAN", "min": "MIN", "max": "MAX"}
_INTEGER_TEXT = re.compile(r"[+-]?[0-9]+")
_DECIMAL_TEXT = re.compile(r"[+-]?([0-9]+|[0-9]{1,3}(,[0-9]{3})+)(\.[0-9]+)?")
RELATIVE_TOLERANCE = Fraction(1, 10**12)


@dataclass(frozen=True)
class Spec:
    operation: str
    column: str | None = None
    group_by: str | None = None

    def question(self) -> str:
        """The README's documented wording for this calculation."""
        if self.operation == "count":
            base = "How many rows are there?" if self.group_by is None else "Count rows"
        else:
            base = f"{QUESTION_WORDS[self.operation]} {' '.join(self.column.split())}"
        return base if self.group_by is None else f"{base} by {' '.join(self.group_by.split())}"

    def label(self) -> str:
        text = self.operation + (f"({self.column})" if self.column else "(rows)")
        return text + (f" by {self.group_by}" if self.group_by else "")


@dataclass
class Outcome:
    """``values`` maps group key to value; ``error`` marks a refusal."""

    values: dict[str | None, Any] = field(default_factory=dict)
    error: str | None = None
    extra: dict[str, Any] = field(default_factory=dict)


def group_key(value: Any) -> str | None:
    """One spelling per group label, so executors' key types compare equal."""
    if value is None or value is pd.NA or value is pd.NaT:
        return None
    if isinstance(value, bool) or type(value).__name__ == "bool_":
        return "true" if value else "false"
    if isinstance(value, Integral):
        return str(int(value))
    if isinstance(value, Real):
        if math.isnan(value):
            return None
        return str(int(value)) if float(value).is_integer() else repr(float(value))
    text = str(value).strip()
    if not text:
        return None
    if text.casefold() in {"true", "false"}:
        return text.casefold()
    if _INTEGER_TEXT.fullmatch(text):
        return str(int(text))
    return text


def number(value: Any) -> Fraction | None:
    """The exact value of a numeric result; None if it is not a finite number."""
    if isinstance(value, bool) or type(value).__name__ == "bool_":
        return None
    if isinstance(value, (Integral, Fraction)):
        return Fraction(value)
    if isinstance(value, Decimal):
        return Fraction(value) if value.is_finite() else None
    if isinstance(value, Real):
        return Fraction(float(value)) if math.isfinite(value) else None
    if isinstance(value, str) and _DECIMAL_TEXT.fullmatch(value):
        # MIN and MAX over text return a cell itself; a plain numeral, with or
        # without thousands commas, is read as the number it spells.
        return Fraction(Decimal(value.replace(",", "")))
    return None


def is_missing(value: Any) -> bool:
    if value is None or value is pd.NA:
        return True
    return isinstance(value, Real) and not isinstance(value, Integral) and math.isnan(value)


def decimal_places(value: Fraction) -> int | None:
    """Digits after the point in a terminating decimal; None if it repeats."""
    for places in range(31):
        if (10**places) % value.denominator == 0:
            return places
    return None


def classify(value: Any, reference: Fraction | None, operation: str) -> str:
    """exact, rounded or wrong.

    A count, total, minimum or maximum must round to the truth at the
    truth's own number of decimals: an integer needs every digit and an
    amount in cents needs every cent. An average or median may differ from
    the truth by float noise, a relative error of at most 1e-12. A close
    result is exact when it is the truth itself or the double nearest to it,
    and rounded otherwise.
    """
    if reference is None:
        return "exact" if is_missing(value) else "wrong"
    if is_missing(value):
        return "wrong"
    exact = number(value)
    if exact is None:
        return "wrong"
    places = None if operation in {"mean", "median"} else decimal_places(reference)
    if places is not None:
        close = round(exact, places) == reference
    else:
        close = abs(exact - reference) <= abs(reference) * RELATIVE_TOLERANCE
    if not close:
        return "wrong"
    nearest = exact == reference or (isinstance(value, float) and value == float(reference))
    return "exact" if nearest else "rounded"


def worst(labels: list[str]) -> str:
    for label in ("wrong", "rounded"):
        if label in labels:
            return label
    return "exact"


def compare(outcome: Outcome, reference: dict[str | None, Fraction | None], operation: str) -> dict[str, Any]:
    """Score one executor's whole answer: every group must be present and right."""
    if outcome.error is not None:
        return {"status": "refused", "detail": outcome.error}
    groups = {key: classify(outcome.values.get(key), value, operation) for key, value in reference.items()}
    unexpected = sorted((key for key in outcome.values if key not in reference), key=str)
    missing = sorted((key for key in reference if key not in outcome.values), key=str)
    status = "wrong" if unexpected or missing else worst(list(groups.values()))
    return {
        "status": status,
        "wrong_groups": sorted((key for key, label in groups.items() if label == "wrong"), key=str),
        "unexpected_groups": unexpected,
        "missing_groups": missing,
    }


def text(value: Any) -> str:
    """Stable spelling of any executor output for the results files."""
    if value is None or value is pd.NA:
        return "missing"
    if isinstance(value, Fraction):
        if value.denominator == 1:
            return str(value.numerator)
        decimal = Decimal(value.numerator) / Decimal(value.denominator)
        exact = Fraction(decimal) == value
        return f"{decimal:.30g}" + ("" if exact else "...")
    if isinstance(value, bool) or type(value).__name__ == "bool_":
        return str(bool(value))
    if isinstance(value, Integral):
        return str(int(value))
    if isinstance(value, float) or type(value).__name__.startswith("float"):
        return repr(float(value))
    if isinstance(value, Decimal):
        return f"Decimal({value})"
    shown = str(value)
    return repr(shown if len(shown) <= 60 else shown[:57] + "...")


# Executors ------------------------------------------------------------------


def run_tablebeam(content: bytes, label: str, spec: Spec) -> Outcome:
    try:
        engine.load(content, label)
    except ValueError as exc:
        return Outcome(error=f"load: {exc}")
    return ask_tablebeam(spec.question(), expected=spec)


def ask_tablebeam(question: str, expected: Spec | None = None) -> Outcome:
    """Ask the loaded table; keep the parsed spec and answer for provenance."""
    try:
        answer = engine.ask(question)
    except ValueError as exc:
        return Outcome(error=f"calculation: {exc}")
    if answer["kind"] != "calculation":
        return Outcome(error="parser: question not in a supported form")
    parsed = Spec(answer["operation"], answer["column"], answer["group_by"])
    values = {
        (ALL if parsed.group_by is None else group_key(row["group"])): exact_cell(row["exact"])
        for row in answer["result"]
    }
    return Outcome(values=values, extra={
        "parsed": parsed, "misparsed": expected is not None and parsed != expected, "answer": answer,
    })


def exact_cell(cell: str | None) -> Any:
    """Read back web/engine.py's exact cell text: an int keeps every digit."""
    if cell is None:
        return None
    return int(cell) if _INTEGER_TEXT.fullmatch(cell) else float(cell)


def run_pandas(path: Path, spec: Spec) -> Outcome:
    try:
        frame = pd.read_csv(path)
        if spec.group_by is None:
            value = len(frame) if spec.operation == "count" else getattr(frame[spec.column], spec.operation)()
            return Outcome(values={ALL: value.item() if hasattr(value, "item") else value})
        grouped = frame.groupby(spec.group_by, dropna=False, sort=False)
        series = grouped.size() if spec.operation == "count" else getattr(grouped[spec.column], spec.operation)()
        return Outcome(values={group_key(key): value.item() if hasattr(value, "item") else value
                               for key, value in series.items()})
    except Exception as exc:  # noqa: BLE001  (any failure is the executor refusing)
        return Outcome(error=f"{type(exc).__name__}: {str(exc).splitlines()[0][:120] if str(exc) else ''}")


def _quote(name: str) -> str:
    return '"' + name.replace('"', '""') + '"'


def _aggregate_sql(spec: Spec, table: str) -> str:
    measure = "*" if spec.operation == "count" else _quote(spec.column)
    aggregate = f"{SQL_FUNCTIONS[spec.operation]}({measure})"
    if spec.group_by is None:
        return f"SELECT {aggregate} FROM {table}"
    group = _quote(spec.group_by)
    return f"SELECT {group}, {aggregate} FROM {table} GROUP BY {group}"


def _rows_to_outcome(rows: list[tuple], spec: Spec) -> Outcome:
    if spec.group_by is None:
        return Outcome(values={ALL: rows[0][0]})
    return Outcome(values={group_key(key): value for key, value in rows})


def run_sqlite(content: bytes, spec: Spec) -> Outcome:
    """sqlite3 shell `.import --csv` into a new table: TEXT columns, '' kept."""
    try:
        records = [row for row in csv.reader(io.StringIO(content.decode("utf-8-sig"), newline="")) if row]
        header, body = records[0], records[1:]
        width = len(header)
        connection = sqlite3.connect(":memory:")
        connection.execute(f"CREATE TABLE t ({', '.join(_quote(name) + ' TEXT' for name in header)})")
        # .import fills short records with NULL and drops extra fields.
        connection.executemany(
            f"INSERT INTO t VALUES ({', '.join('?' * width)})",
            [(row + [None] * width)[:width] for row in body],
        )
        return _rows_to_outcome(connection.execute(_aggregate_sql(spec, "t")).fetchall(), spec)
    except Exception as exc:  # noqa: BLE001
        return Outcome(error=f"{type(exc).__name__}: {str(exc).splitlines()[0][:120]}")


def run_duckdb(path: Path, spec: Spec) -> Outcome:
    connection = duckdb.connect()
    try:
        # One thread keeps floating-point aggregation order, and so reruns, identical.
        connection.execute("SET threads = 1")
        connection.execute("CREATE TABLE t AS SELECT * FROM read_csv(?)", [str(path)])
        return _rows_to_outcome(connection.execute(_aggregate_sql(spec, "t")).fetchall(), spec)
    except Exception as exc:  # noqa: BLE001
        return Outcome(error=f"{type(exc).__name__}: {str(exc).splitlines()[0][:120]}")
    finally:
        connection.close()


EXECUTORS = ("tablebeam", "pandas", "sqlite", "duckdb")


def run_all(path: Path, spec: Spec) -> dict[str, Outcome]:
    content = path.read_bytes()
    return {
        "tablebeam": run_tablebeam(content, path.name, spec),
        "pandas": run_pandas(path, spec),
        "sqlite": run_sqlite(content, spec),
        "duckdb": run_duckdb(path, spec),
    }


# Exact reference for the real-number tables ----------------------------------


def source_records(content: bytes) -> tuple[list[str], list[list[str]]]:
    """Header and records, skipping physically blank lines like every executor."""
    records = [row for row in csv.reader(io.StringIO(content.decode("utf-8-sig"), newline="")) if row]
    return records[0], records[1:]


def read_cell(cell: str, missing: list[str], decimal_separator: str) -> Fraction | None:
    cell = cell.strip()
    if cell in missing:
        return None
    if decimal_separator != ".":
        cell = cell.replace(decimal_separator, ".")
    try:
        return Fraction(Decimal(cell))
    except InvalidOperation as exc:
        raise ValueError(f"reference cannot read {cell!r}") from exc


def aggregate(operation: str, values: list[Fraction | None], rows: int) -> Fraction | None:
    if operation == "count":
        return Fraction(rows)
    present = sorted(value for value in values if value is not None)
    if not present:
        return None
    if operation == "sum":
        return sum(present, Fraction(0))
    if operation == "mean":
        return sum(present, Fraction(0)) / len(present)
    if operation == "median":
        middle = len(present) // 2
        return present[middle] if len(present) % 2 else (present[middle - 1] + present[middle]) / 2
    return present[0] if operation == "min" else present[-1]


def reference(content: bytes, spec: Spec, table: dict) -> dict[str | None, Fraction | None]:
    header, records = source_records(content)
    measure = header.index(spec.column) if spec.column else None
    group = header.index(spec.group_by) if spec.group_by else None
    buckets: dict[str | None, list[Fraction | None]] = {}
    for record in records:
        key = ALL if group is None else group_key(record[group])
        value = None if measure is None else read_cell(record[measure], table["missing"], table["decimal_separator"])
        buckets.setdefault(key, []).append(value)
    return {key: aggregate(spec.operation, values, len(values)) for key, values in buckets.items()}


def duckdb_reference(path: Path, spec: Spec, table: dict) -> dict[str | None, Fraction | None]:
    """Cross-check the exact reference with DuckDB's DECIMAL(38, s) arithmetic.

    Covers count, sum, min and max exactly, and mean as an exact sum over a
    count. Median has no exact DECIMAL form in DuckDB and is not cross-checked.
    """
    connection = duckdb.connect()
    try:
        connection.execute("SET threads = 1")
        connection.execute("CREATE TABLE raw AS SELECT * FROM read_csv(?, all_varchar = true)", [str(path)])
        nulls = ", ".join("'" + token.replace("'", "''") + "'" for token in table["missing"])
        if spec.column:
            cell = f"trim({_quote(spec.column)})"
            if table["decimal_separator"] != ".":
                cell = f"replace({cell}, '{table['decimal_separator']}', '.')"
            scale = connection.execute(
                f"SELECT coalesce(max(length(split_part({cell}, '.', 2))), 0) FROM raw "
                f"WHERE {cell} NOT IN ({nulls})").fetchone()[0]
            measure = f"CAST(CASE WHEN {cell} IN ({nulls}) THEN NULL ELSE {cell} END AS DECIMAL(38, {scale}))"
        else:
            measure = "1"
        group = f"{_quote(spec.group_by)}" if spec.group_by else f"'{ALL}'"
        aggregate_sql = {
            "count": "count(*)", "sum": f"sum({measure})", "min": f"min({measure})", "max": f"max({measure})",
            "mean": f"sum({measure}) || '/' || count({measure})",
        }[spec.operation]
        rows = connection.execute(f"SELECT {group}, {aggregate_sql} FROM raw GROUP BY ALL").fetchall()
    finally:
        connection.close()
    result = {}
    for key, value in rows:
        if spec.operation == "mean":
            total, _, count = (value or "/").partition("/")
            value = Fraction(Decimal(total)) / int(count) if total else None
        result[ALL if spec.group_by is None else group_key(key)] = number(value) if value is not None else None
    return result
