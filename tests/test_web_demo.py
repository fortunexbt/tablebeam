"""The browser demo must run the app's code, not a copy that drifted from it."""

import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
DIST = ROOT / "web" / "dist"
COPIED = ["answer_format.py", "data_pipeline.py", "question_actions.py", "table_analysis.py"]


@pytest.fixture(scope="module")
def dist():
    subprocess.run(["bash", str(ROOT / "web" / "build.sh")], check=True, capture_output=True)
    return DIST


@pytest.fixture(scope="module")
def engine(dist):
    sys.path.insert(0, str(dist / "engine"))
    try:
        import engine as module
    finally:
        sys.path.pop(0)
    return module


def test_build_copies_the_app_modules_unchanged(dist):
    for name in COPIED:
        assert (dist / "engine" / name).read_bytes() == (ROOT / "src" / name).read_bytes()
    assert (dist / "engine" / "engine.py").read_bytes() == (ROOT / "web" / "engine.py").read_bytes()


def test_worker_loads_every_module_the_engine_imports(dist):
    worker = (dist / "worker.js").read_text()
    for name in [*COPIED, "engine.py"]:
        assert f'"{name}"' in worker


def test_each_bundled_question_parses_and_answers(engine, dist):
    catalog = json.loads((dist / "catalog.json").read_text())
    assert catalog, "the page needs at least one bundled table"
    for dataset in catalog:
        table = engine.load((dist / "datasets" / dataset["file"]).read_bytes(), dataset["name"])
        assert table["rows"] > 0
        assert table["columns"]
        for question in dataset["questions"]:
            answer = engine.ask(question)
            assert answer["kind"] == "calculation", f"{dataset['file']}: {question!r} fell through"
            assert answer["result"]
            found = engine.evidence(None if answer["group_by"] is None else 0)
            assert found["count"] > 0
            assert engine.rows_csv(None if answer["group_by"] is None else 0).startswith("﻿")


def test_written_out_arithmetic_matches_the_result(engine, dist):
    engine.load((dist / "datasets" / "exoplanets.csv").read_bytes(), "Confirmed exoplanets")
    engine.ask("Average mass earths by discovery method")
    found = engine.evidence(0)
    terms, mean = found["working"].split(" = ")
    total, count = terms.removeprefix("(").split(") / ")
    values = [float(term) for term in total.split(" + ")]
    assert len(values) == int(count)
    assert sum(values) / len(values) == pytest.approx(float(mean), rel=1e-12)
    assert len(found["rows"]) == found["count"]


def test_true_false_groups_keep_their_labels(engine):
    # Montpellier's rent-control file groups by a TRUE/FALSE "meuble" column.
    engine.load(b"meuble,prix\nFALSE,12.7\nTRUE,15.1\nFALSE,13.0\n", "furnished")
    answer = engine.ask("Count rows by meuble")
    assert sorted(row["group"] for row in answer["result"]) == ["False", "True"]
    first = engine.evidence(0)
    assert first["group"] in {"False", "True"}
    assert {row["cells"][0] for row in first["rows"]} == {first["group"]}


def test_an_unsupported_question_asks_for_the_model_instead_of_guessing(engine, dist):
    engine.load((dist / "datasets" / "penguins.csv").read_bytes(), "Palmer penguins")
    assert engine.ask("which penguins are heavier than 5000 g?")["kind"] == "needs_ai"


def test_every_bundled_table_names_its_source(dist):
    for dataset in json.loads((dist / "catalog.json").read_text()):
        assert dataset["credit"] and dataset["url"].startswith("https://")
