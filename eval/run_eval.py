"""Evaluate Tablebeam's deterministic engine against independent executors.

    python eval/run_eval.py

Reads only the pinned files under eval/inputs/ (checked against
manifest.json) and writes eval/results.json and eval/results.md. Two runs
with the versions in eval/requirements.txt produce byte-identical files.
No model is loaded or called: only the parser and calculations are measured.
"""

from __future__ import annotations

import csv
import hashlib
import io
import json
import math
import platform
import re
import sqlite3
import sys
import warnings
from decimal import ROUND_DOWN, ROUND_HALF_EVEN, ROUND_HALF_UP, Context, Decimal, localcontext
from fractions import Fraction
from pathlib import Path
from typing import Any

import duckdb
import numpy
import pandas as pd

from executors import (
    ALL, EXECUTORS, Outcome, Spec, aggregate, ask_tablebeam, classify, compare, duckdb_reference,
    engine, group_key, number, reference, run_pandas, run_sqlite, run_duckdb, source_records, text,
)

ROOT = Path(__file__).resolve().parent
INPUTS = ROOT / "inputs"
# pandas' default missing-value spellings (pandas.read_csv, na_values).
PANDAS_MISSING = {
    "", "#N/A", "#N/A N/A", "#NA", "-1.#IND", "-1.#QNAN", "-NaN", "-nan", "1.#IND", "1.#QNAN",
    "<NA>", "N/A", "NA", "NULL", "NaN", "None", "n/a", "nan", "null",
}
SQL_COLUMN = re.compile(r"\bc\d+(?:_[a-z0-9_]+)?\b")
NUMERAL = re.compile(r"[+-]?(\d+(\.\d*)?|\.\d+)([eE][+-]?\d+)?")
GOLD_NUMBER = re.compile(r"[$£€]?(-?\d{1,3}(?:,\d{3})+|-?\d+)(\.\d+)?(?:st|nd|rd|th|\+)?(?:\s.*)?")


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def wilson(successes: int, total: int) -> list[float] | None:
    """95% Wilson score interval, rounded to four decimals."""
    if total == 0:
        return None
    z = 1.959963984540054
    p = successes / total
    centre = (p + z * z / (2 * total)) / (1 + z * z / total)
    margin = z * math.sqrt(p * (1 - p) / total + z * z / (4 * total * total)) / (1 + z * z / total)
    return [round(max(0.0, centre - margin), 4), round(min(1.0, centre + margin), 4)]


def rate(successes: int, total: int) -> dict[str, Any]:
    return {"count": successes, "n": total, "rate": round(successes / total, 4) if total else None,
            "ci95": wilson(successes, total)}


# Ground truth for WikiTableQuestions ------------------------------------------


def squall_truth(record: dict) -> Any:
    """Run the annotated SQL in DuckDB over SQUALL's parsed columns.

    SQUALL's own evaluator (eval/evaluator.js) adds ``agg = 0`` and NOT NULL
    for every referenced column, which drops summary rows such as "Total".
    """
    columns = record["sql_columns"]
    types = {"INTEGER": "BIGINT", "REAL": "DOUBLE", "TEXT": "VARCHAR"}
    names = sorted(columns)
    connection = duckdb.connect()
    try:
        connection.execute("SET threads = 1")
        connection.execute("CREATE TABLE w (" + ", ".join(f"{n} {types[columns[n]['type']]}" for n in names) + ")")
        connection.executemany(f"INSERT INTO w VALUES ({', '.join('?' * len(names))})",
                               list(zip(*(columns[n]["data"] for n in names))))
        referenced = sorted(set(SQL_COLUMN.findall(record["sql"])))
        sql = record["sql"]
        if referenced:
            sql += " where agg = 0 and " + " and ".join(f"{name} is not null" for name in referenced)
        return connection.execute(sql).fetchone()[0]
    finally:
        connection.close()


def pandas_truth(record: dict) -> Any:
    """The same aggregate written in pandas, as an independent cross-check."""
    frame = pd.DataFrame({name: column["data"] for name, column in record["sql_columns"].items()})
    operation, target = re.match(r"select (\w+) \( (\S+) \) from w", record["sql"]).groups()
    if target == "*":
        return len(frame)
    values = frame.loc[pd.to_numeric(frame["agg"]).eq(0), target].dropna()
    if operation == "count":
        return len(values)
    if values.empty:
        return None
    result = getattr(values, {"avg": "mean"}.get(operation, operation))()
    return result.item() if hasattr(result, "item") else result


def gold_number(answers: list[str]) -> tuple[Fraction, int] | None:
    """A single numeric WikiTableQuestions answer and its decimal places.

    Annotators wrote some numbers with a currency sign, an ordinal suffix or
    truncated decimals; those spellings still name the number.
    """
    if len(answers) != 1:
        return None
    match = GOLD_NUMBER.fullmatch(answers[0].strip())
    if not match:
        return None
    whole, fraction = match.group(1).replace(",", ""), match.group(2) or ""
    return Fraction(Decimal(whole + fraction)), max(len(fraction) - 1, 0)


def agrees_with_gold(value: Any, gold: tuple[Fraction, int] | None) -> bool:
    exact = number(value)
    if gold is None or exact is None:
        return False
    target, places = gold
    with localcontext() as context:
        context.prec = 60
        decimal = Decimal(exact.numerator) / Decimal(exact.denominator)
        quantum = Decimal(1).scaleb(-places)
        return any(Fraction(decimal.quantize(quantum, rounding=mode)) == target
                   for mode in (ROUND_HALF_EVEN, ROUND_HALF_UP, ROUND_DOWN))


# Provenance ------------------------------------------------------------------


def blank(record: list[str]) -> bool:
    return all(cell in PANDAS_MISSING for cell in record)


def cell_matches(shown: str | None, source: str) -> bool:
    """A displayed cell spells the source cell's value."""
    if shown is None:
        return source in PANDAS_MISSING
    if shown == source:
        return True
    if shown in {"True", "False"}:
        return source.strip().casefold() == shown.casefold()
    if NUMERAL.fullmatch(shown) and NUMERAL.fullmatch(source.strip()):
        return Fraction(Decimal(shown)) == Fraction(Decimal(source.strip()))
    return False


def export_matches(shown: str | None, exported: str) -> bool:
    """The download spells the displayed cell, allowing its formula guard."""
    if shown is None:
        return exported == ""
    return exported in {shown, "'" + shown} or cell_matches(shown, exported)


def working_value(working: str, operation: str) -> tuple[Fraction, list[Fraction]] | None:
    """Evaluate the evidence panel's written-out arithmetic exactly."""
    left, _, _ = working.rpartition(" = ")
    if operation == "count":
        return Fraction(int(left.split()[0])), []
    if operation == "sum":
        terms = left.split(" + ")
    elif operation == "mean":
        terms = left[1:left.rindex(")")].split(" + ")
    else:
        terms = left[left.index("[") + 1:left.rindex("]")].split(", ")
    values = [Fraction(Decimal(term)) for term in terms]
    return aggregate(operation, values, len(values)), values


def provenance(content: bytes, outcome: Outcome) -> list[str]:
    """Check that each figure's rows, scope and arithmetic reproduce it.

    Must run right after the question is asked, while the demo engine still
    holds that answer.
    """
    answer, parsed = outcome.extra["answer"], outcome.extra["parsed"]
    header, records = source_records(content)
    kept = [record for record in records if not blank(record)]
    failures: list[str] = []
    if answer["filter_label"] != "All rows" or not answer["selected_rows"] == answer["total_rows"] == len(kept):
        failures.append(f"scope: {answer['filter_label']} covers {answer['selected_rows']} of "
                        f"{answer['total_rows']} rows; the source has {len(kept)}")
    indices = [None] if parsed.group_by is None else range(len(answer["result"]))
    for index in indices:
        row = answer["result"][0 if index is None else index]
        where = "all rows" if index is None else f"group {row['group']!r}"
        evidence = engine.evidence(index)
        exported = list(csv.reader(io.StringIO(engine.rows_csv(index).lstrip("﻿"), newline="")))
        exported_header, exported_rows = exported[0], exported[1:]
        if exported_header != [("'" + name if name[:1] in "=+-@" else name) for name in header]:
            failures.append(f"{where}: download header differs from the source header")
        if not evidence["count"] == len(exported_rows) == row["rows"]:
            failures.append(f"{where}: shows {evidence['count']} rows, downloads {len(exported_rows)}, "
                            f"result says {row['rows']}")

        if parsed.group_by is None:
            selected = list(range(len(kept)))
        else:
            position = header.index(parsed.group_by)
            key = group_key(row["group"])
            selected = [i for i, record in enumerate(kept)
                        if group_key(None if record[position] in PANDAS_MISSING else record[position]) == key]
        if len(selected) != row["rows"]:
            failures.append(f"{where}: the source has {len(selected)} matching rows, the answer used {row['rows']}")
        shown_rows = [item["row"] - 1 for item in evidence["rows"]]
        if shown_rows != selected[:len(shown_rows)]:
            failures.append(f"{where}: displayed row numbers {shown_rows[:5]}... are not the first matching rows")
        for item, exported_row in zip(evidence["rows"], exported_rows):
            source = kept[item["row"] - 1] if item["row"] - 1 < len(kept) else None
            if source is None or not all(map(cell_matches, item["cells"], source)):
                failures.append(f"{where}: displayed row {item['row']} differs from source row {item['row']}")
            if not all(map(export_matches, item["cells"], exported_row)):
                failures.append(f"{where}: displayed row {item['row']} differs from its download")

        if parsed.column is None:
            recomputed = Fraction(len(exported_rows))
        else:
            position = header.index(parsed.column)
            cells = [exported_row[position].lstrip("'") for exported_row in exported_rows]
            recomputed = aggregate(parsed.operation, [Fraction(Decimal(c)) if c else None for c in cells], len(cells))
        value = outcome.values[ALL if parsed.group_by is None else group_key(row["group"])]
        if classify(value, recomputed, parsed.operation) == "wrong":
            failures.append(f"{where}: the downloaded rows give {text(recomputed)}, the answer shows {text(value)}")
        if evidence["working"]:
            worked, terms = working_value(evidence["working"], parsed.operation)
            if classify(value, worked, parsed.operation) == "wrong":
                failures.append(f"{where}: the working {evidence['working']!r} does not equal the answer")
            if parsed.column is not None and sorted(terms) != sorted(
                    Fraction(Decimal(c)) for c in cells if c):
                failures.append(f"{where}: the working lists values other than the rows used")
            if evidence["working"].rpartition(" = ")[2] != row["exact"]:
                failures.append(f"{where}: the working's result differs from the result table")
    return failures


def headline_issues(outcome: Outcome, truth: dict[str | None, Fraction | None]) -> list[str]:
    """A correct value must also display as the truth rounded the same way.

    Wrong values are already counted as wrong; this isolates the rounding
    between the exact result and the number a person reads.
    """
    issues = []
    parsed = outcome.extra["parsed"]
    for row in outcome.extra["answer"]["result"]:
        key = ALL if parsed.group_by is None else group_key(row["group"])
        if key not in truth or classify(outcome.values[key], truth[key], parsed.operation) == "wrong":
            continue
        expected = expected_display(truth[key])
        if row["value"] not in expected:
            issues.append(f"{key}: shows {row['value']}, the exact value rounds to {' or '.join(sorted(expected))}")
    return issues


def expected_display(value: Fraction | None) -> set[str]:
    """answer_format.format_value's output if it rounded the exact value.

    Six significant digits, half-even or half-up; a double holding those six
    digits prints them back exactly with the same ``,.6g`` format.
    """
    if value is None:
        return {"No values"}
    if value.denominator == 1:
        return {f"{value.numerator:,}"}
    with localcontext(Context(prec=80)):
        exact = Decimal(value.numerator) / Decimal(value.denominator)
    return {f"{float(Context(prec=6, rounding=mode).plus(exact)):,.6g}" for mode in (ROUND_HALF_EVEN, ROUND_HALF_UP)}


# Splits ----------------------------------------------------------------------


def explain(outcome: Outcome, columns: list[dict], spec: Spec | None) -> Outcome:
    """Name the usual reason the parser declines a documented question."""
    if spec is not None and spec.column and outcome.error and outcome.error.startswith("parser:"):
        if any(column["name"] == spec.column and not column["numeric"] for column in columns):
            outcome.error = f"parser: {spec.column!r} is not a numeric column"
    return outcome


def outcome_text(outcome: Outcome, keys: list[str | None]) -> dict[str, Any]:
    if outcome.error is not None:
        return {"refused": outcome.error}
    return {str(key): text(outcome.values.get(key)) for key in keys} | (
        {"extra_groups": sorted(str(k) for k in outcome.values if k not in keys)}
        if any(k not in keys for k in outcome.values) else {})


def run_wtq(manifest: dict) -> dict[str, Any]:
    tables = manifest["wtq"]["tables"]
    records = [json.loads(line) for line in (INPUTS / manifest["wtq"]["questions_file"]).read_text("utf-8").splitlines()]
    questions, specs, excluded, provenance_failures, headline = [], [], [], [], []

    for record in records:
        gold = gold_number(record["answer"])
        truth = None
        if record["stratum"] == "supported":
            spec = Spec(record["spec"]["operation"], record["spec"]["column"])
            truth_value, check = squall_truth(record), pandas_truth(record)
            truth = number(truth_value)
            if truth_value is not None and truth is None:
                excluded.append({"id": record["id"], "reason": f"SQL result {text(truth_value)} is not a number"})
                continue
            if classify(check, truth, spec.operation) == "wrong":
                excluded.append({"id": record["id"], "reason": f"DuckDB {text(truth_value)} and pandas {text(check)} disagree"})
                continue
            if not agrees_with_gold(truth_value, gold):
                excluded.append({"id": record["id"], "reason": f"SQL truth {text(truth_value)} does not match the "
                                                             f"WikiTableQuestions answer {record['answer']}"})
                continue

        path = INPUTS / tables[record["table"]]["file"]
        content = path.read_bytes()
        try:
            columns = engine.load(content, path.name)["columns"]
            loaded = None
        except ValueError as exc:
            loaded = f"load: {exc}"

        tracks = {"verbatim": record["question"]}
        if record["stratum"] == "supported":
            tracks["canonical"] = spec.question()
        for track, question in tracks.items():
            outcome = Outcome(error=loaded) if loaded else explain(ask_tablebeam(question), columns,
                                                                  spec if track == "canonical" else None)
            item = {"id": record["id"], "table": record["table"], "stratum": record["stratum"], "track": track,
                    "question": question, "wtq_answer": record["answer"],
                    "truth": text(truth) if record["stratum"] == "supported" else None}
            if outcome.error is not None:
                item["outcome"] = "correct refusal" if record["stratum"] == "unsupported" else "refused"
                item["detail"] = outcome.error
            else:
                parsed = outcome.extra["parsed"]
                item["parsed"] = parsed.label()
                value = outcome.values.get(ALL) if parsed.group_by is None else None
                item["answer"] = text(value) if parsed.group_by is None else f"{len(outcome.values)} groups"
                if record["stratum"] == "supported":
                    right = value is not None and classify(value, truth, spec.operation) != "wrong"
                else:
                    right = parsed.group_by is None and agrees_with_gold(value, gold)
                item["outcome"] = "correct" if right else "wrong"
                for failure in provenance(content, outcome):
                    provenance_failures.append({"split": "wtq", "id": record["id"], "track": track, "failure": failure})
                if record["stratum"] == "supported":
                    for issue in headline_issues(outcome, {ALL: truth}):
                        headline.append({"split": "wtq", "id": record["id"], "track": track, "issue": issue})
            questions.append(item)
            if track == "canonical":
                tablebeam = outcome

        if record["stratum"] != "supported":
            continue
        outcomes = {"tablebeam": tablebeam, "pandas": run_pandas(path, spec),
                    "sqlite": run_sqlite(content, spec), "duckdb": run_duckdb(path, spec)}
        expected = {ALL: truth}
        specs.append({
            "id": record["id"], "table": record["table"], "spec": spec.label(), "reference": text(truth),
            "scores": {name: compare(outcomes[name], expected, spec.operation) for name in EXECUTORS},
            "values": {name: outcome_text(outcomes[name], [ALL]) for name in EXECUTORS},
        })
    return {"questions": questions, "specs": specs, "excluded": excluded,
            "provenance_failures": provenance_failures, "headline": headline}


def numeric_specs(table: dict) -> list[Spec]:
    specs = []
    for group in [None, *table["groups"]]:
        specs.append(Spec("count", None, group))
        specs.extend(Spec(op, measure, group) for measure in table["measures"] for op in table["operations"])
    return specs


def run_numeric(manifest: dict) -> dict[str, Any]:
    specs, reference_mismatches, provenance_failures, headline = [], [], [], []
    for table in manifest["numeric"]:
        path = INPUTS / table["file"]
        content = path.read_bytes()
        for spec in numeric_specs(table):
            truth = reference(content, spec, table)
            if spec.operation != "median" and duckdb_reference(path, spec, table) != truth:
                reference_mismatches.append({"table": table["file"], "spec": spec.label()})
            try:
                columns = engine.load(content, path.name)["columns"]
                tablebeam = explain(ask_tablebeam(spec.question(), expected=spec), columns, spec)
            except ValueError as exc:
                tablebeam = Outcome(error=f"load: {exc}")
            if tablebeam.error is None:
                if tablebeam.extra["misparsed"]:
                    tablebeam = Outcome(error=f"parser: read the question as {tablebeam.extra['parsed'].label()}")
                else:
                    for failure in provenance(content, tablebeam):
                        provenance_failures.append({"split": "numeric", "id": f"{table['file']} {spec.label()}",
                                                    "failure": failure})
                    for issue in headline_issues(tablebeam, truth):
                        headline.append({"split": "numeric", "id": f"{table['file']} {spec.label()}", "issue": issue})
            outcomes = {"tablebeam": tablebeam, "pandas": run_pandas(path, spec),
                        "sqlite": run_sqlite(content, spec), "duckdb": run_duckdb(path, spec)}
            keys = sorted(truth, key=lambda key: (key is not None, str(key)))
            specs.append({
                "id": f"{table['file']} {spec.label()}", "table": table["file"], "spec": spec.label(),
                "reference": {str(key): text(truth[key]) for key in keys},
                "scores": {name: compare(outcomes[name], truth, spec.operation) for name in EXECUTORS},
                "values": {name: outcome_text(outcomes[name], keys) for name in EXECUTORS},
            })
    return {"specs": specs, "reference_mismatches": reference_mismatches,
            "provenance_failures": provenance_failures, "headline": headline}


# Metrics and report ----------------------------------------------------------


def question_metrics(items: list[dict]) -> dict[str, Any]:
    n = len(items)
    count = lambda *names: sum(item["outcome"] in names for item in items)  # noqa: E731
    return {
        "n": n,
        "accuracy": rate(count("correct", "correct refusal"), n),
        "answered_correctly": rate(count("correct"), n),
        "refusal": rate(count("refused", "correct refusal"), n),
        "wrong": rate(count("wrong"), n),
    }


def executor_metrics(specs: list[dict]) -> dict[str, Any]:
    result = {}
    for name in EXECUTORS:
        statuses = [spec["scores"][name]["status"] for spec in specs]
        n = len(statuses)
        result[name] = {
            "n": n,
            "exact": rate(statuses.count("exact"), n),
            "correct": rate(statuses.count("exact") + statuses.count("rounded"), n),
            "silent_wrong": rate(statuses.count("wrong"), n),
            "refused": rate(statuses.count("refused"), n),
        }
    return result


def percent(entry: dict) -> str:
    if entry["n"] == 0:
        return "n/a"
    low, high = entry["ci95"]
    return f"{entry['rate'] * 100:.1f}% ({low * 100:.1f}–{high * 100:.1f})"


def markdown(results: dict) -> str:
    lines = [
        "# Tablebeam engine evaluation results",
        "",
        "Generated by `python eval/run_eval.py` from the pinned files in `eval/inputs/`. "
        "Rates show the 95% Wilson interval in brackets. The Evaluation section of the main "
        "README describes the method and its limits.",
        "",
        f"Inputs manifest SHA-256: `{results['inputs_manifest_sha256']}`. "
        + ", ".join(f"{k} {v}" for k, v in results["versions"].items()) + ".",
        "",
        "## 1. Real questions (WikiTableQuestions with SQUALL SQL)",
        "",
        "| Track | n | Accuracy | Answered correctly | Refusal | Wrong answer |",
        "|---|---|---|---|---|---|",
    ]
    for name, metrics in results["questions"]["metrics"].items():
        lines.append(f"| {name} | {metrics['n']} | {percent(metrics['accuracy'])} | "
                     f"{percent(metrics['answered_correctly'])} | {percent(metrics['refusal'])} | "
                     f"{percent(metrics['wrong'])} |")
    lines += ["", "Accuracy counts a correct number or, for an unsupported question, a refusal.", ""]

    for title, key in (("2. Executors on the WikiTableQuestions specs", "wtq"),
                       ("3. Executors on real CSVs with hard number formats", "numeric"),
                       ("4. Executors, both spec sets", "all")):
        lines += [f"## {title}", "", "| Executor | n | Exact | Correct | Silent wrong | Refused |", "|---|---|---|---|---|---|"]
        for name, metrics in results["executors"][key].items():
            lines.append(f"| {name} | {metrics['n']} | {percent(metrics['exact'])} | {percent(metrics['correct'])} | "
                         f"{percent(metrics['silent_wrong'])} | {percent(metrics['refused'])} |")
        lines.append("")
    lines += ["Per table (real CSVs):", "", "| Table | Specs | Tablebeam wrong/refused | pandas wrong/refused | "
              "SQLite wrong/refused | DuckDB wrong/refused |", "|---|---|---|---|---|---|"]
    for table, metrics in results["executors"]["numeric_by_table"].items():
        cells = [f"{m['silent_wrong']['count']}/{m['refused']['count']}" for m in metrics.values()]
        lines.append(f"| {table} | {metrics['tablebeam']['n']} | " + " | ".join(cells) + " |")

    lines += ["", "## 5. Provenance", "",
              f"Answers checked: {results['provenance']['answers_checked']}. Failures: "
              f"{len(results['provenance']['failures'])}.", ""]
    lines += [f"- {f['split']} {f['id']}{' ' + f['track'] if 'track' in f else ''}: {f['failure']}"
              for f in results["provenance"]["failures"]]
    lines += ["", "## 6. Displayed (rounded) values that differ from the exact value rounded", ""]
    lines += [f"- {h['split']} {h['id']}: {h['issue']}" for h in results["headline"]] or ["None."]

    lines += ["", "## 7. Every wrong Tablebeam answer to a real question", ""]
    wrong = [q for q in results["questions"]["items"] if q["outcome"] == "wrong"]
    lines += [f"- {q['id']} ({q['track']}, table {q['table']}): {q['question']!r} parsed as {q['parsed']}, "
              f"answered {q['answer']}, truth {q['truth']}, WikiTableQuestions answer {q['wtq_answer']}"
              for q in wrong] or ["None."]

    lines += ["", "## 8. Every spec where an executor is wrong or the executors disagree", "",
              "Values are the executor's raw result; `refused` gives its error. Grouped specs list wrong groups.", ""]
    for split in ("wtq", "numeric"):
        lines += [f"### {split}", "", "| Spec | Reference | Tablebeam | pandas | SQLite | DuckDB |", "|---|---|---|---|---|---|"]
        for spec in results["specs"][split]:
            statuses = [spec["scores"][name]["status"] for name in EXECUTORS]
            if "wrong" not in statuses and len(set(statuses)) == 1:
                continue
            lines.append(f"| {spec['id']} | {summary_reference(spec)} | "
                         + " | ".join(summary_cell(spec, name) for name in EXECUTORS) + " |")
        lines.append("")
    lines += ["## 9. Questions excluded because the ground truth did not hold", ""]
    lines += [f"- {e['id']}: {e['reason']}" for e in results["questions"]["excluded"]] or ["None."]
    lines += ["", "## 10. Reference cross-check (exact fractions against DuckDB DECIMAL)", ""]
    lines += [f"- {m['table']} {m['spec']}" for m in results["reference_mismatches"]] or ["No disagreement."]
    return "\n".join(line.replace("\n", " ") for line in lines) + "\n"


def summary_reference(spec: dict) -> str:
    reference_values = spec["reference"]
    if isinstance(reference_values, str):
        return reference_values
    return reference_values[ALL] if ALL in reference_values else f"{len(reference_values)} groups"


def summary_cell(spec: dict, name: str) -> str:
    score, values = spec["scores"][name], spec["values"][name]
    if score["status"] == "refused":
        return "refused: " + score["detail"].replace("|", "/")[:80]
    if ALL in values:
        shown = values[ALL]
    else:
        wrong = score["wrong_groups"] + score["missing_groups"] + score["unexpected_groups"]
        shown = f"{len(wrong)} groups wrong" + (": " + ", ".join(
            f"{key}={values.get(str(key), 'absent')}" for key in wrong[:3]) if wrong else "")
    return f"{score['status']}: {shown}".replace("|", "/")


def main() -> None:
    warnings.simplefilter("ignore")
    manifest_path = INPUTS / "manifest.json"
    manifest = json.loads(manifest_path.read_text("utf-8"))
    pinned = [(manifest["wtq"]["questions_file"], manifest["wtq"]["questions_sha256"])]
    pinned += [(t["file"], t["sha256"]) for t in manifest["wtq"]["tables"].values()]
    pinned += [(t["file"], t["sha256"]) for t in manifest["numeric"]]
    changed = [name for name, digest in pinned if sha256(INPUTS / name) != digest]
    if changed:
        raise SystemExit(f"Pinned inputs changed: {changed[:5]}")

    wtq, numeric = run_wtq(manifest), run_numeric(manifest)
    items = wtq["questions"]
    pick = lambda stratum, track: [q for q in items if q["stratum"] in stratum and q["track"] == track]  # noqa: E731
    by_table = {}
    for table in manifest["numeric"]:
        by_table[table["file"]] = executor_metrics([s for s in numeric["specs"] if s["table"] == table["file"]])
    answers = sum(q["outcome"] in {"correct", "wrong"} for q in items)
    answers += sum(s["scores"]["tablebeam"]["status"] != "refused" for s in numeric["specs"])
    results = {
        "inputs_manifest_sha256": sha256(manifest_path),
        "versions": {
            "python": platform.python_version(), "pandas": pd.__version__, "numpy": numpy.__version__,
            "duckdb": duckdb.__version__, "sqlite": sqlite3.sqlite_version,
        },
        "questions": {
            "metrics": {
                "verbatim, supported": question_metrics(pick({"supported"}, "verbatim")),
                "verbatim, unsupported": question_metrics(pick({"unsupported"}, "verbatim")),
                "verbatim, all": question_metrics(pick({"supported", "unsupported"}, "verbatim")),
                "documented wording, supported": question_metrics(pick({"supported"}, "canonical")),
            },
            "items": items,
            "excluded": wtq["excluded"],
        },
        "executors": {
            "wtq": executor_metrics(wtq["specs"]),
            "numeric": executor_metrics(numeric["specs"]),
            "all": executor_metrics(wtq["specs"] + numeric["specs"]),
            "numeric_by_table": by_table,
        },
        "provenance": {"answers_checked": answers,
                       "failures": wtq["provenance_failures"] + numeric["provenance_failures"]},
        "headline": wtq["headline"] + numeric["headline"],
        "specs": {"wtq": wtq["specs"], "numeric": numeric["specs"]},
        "reference_mismatches": numeric["reference_mismatches"],
    }
    (ROOT / "results.json").write_text(json.dumps(results, ensure_ascii=False, indent=1, sort_keys=True) + "\n", "utf-8")
    (ROOT / "results.md").write_text(markdown(results), "utf-8")
    for name, metrics in results["questions"]["metrics"].items():
        print(f"{name}: n={metrics['n']} accuracy {percent(metrics['accuracy'])} "
              f"refusal {percent(metrics['refusal'])} wrong {percent(metrics['wrong'])}")
    for key in ("wtq", "numeric"):
        for name, metrics in results["executors"][key].items():
            print(f"{key} {name}: exact {percent(metrics['exact'])} correct {percent(metrics['correct'])} "
                  f"silent wrong {percent(metrics['silent_wrong'])} refused {percent(metrics['refused'])}")
    print(f"provenance failures {len(results['provenance']['failures'])} of {answers} answers; "
          f"display mismatches {len(results['headline'])}; excluded {len(wtq['excluded'])}")


if __name__ == "__main__":
    main()
