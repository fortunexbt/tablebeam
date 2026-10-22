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
    engine.load((dist / "datasets" / "clients.csv").read_bytes(), "Client accounts")
    engine.ask("Total annual revenue by owner")
    found = engine.evidence(0)
    terms, total = found["working"].split(" = ")
    assert sum(int(term) for term in terms.split(" + ")) == int(total)
    assert len(found["rows"]) == found["count"]


def test_an_unsupported_question_asks_for_the_model_instead_of_guessing(engine, dist):
    engine.load((dist / "datasets" / "clients.csv").read_bytes(), "Client accounts")
    assert engine.ask("which owners are below a health score of 70?")["kind"] == "needs_ai"


def test_the_recorded_example_keeps_the_app_answer_schema(dist):
    answer = json.loads((dist / "recorded-answer.json").read_text())["answer"]
    assert answer["kind"] == "ai"
    assert {"question", "text", "coverage", "sources", "profile"} <= answer.keys()
    assert all({"citation", "row_number", "content"} <= source.keys() for source in answer["sources"])
