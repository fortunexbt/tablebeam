# Tablebeam

**Get answers from your spreadsheet.**

Open a CSV, choose a question, and see the answer. Totals and comparisons run on your computer. Connect [LM Studio](https://lmstudio.ai/) or [Ollama](https://ollama.com/) when you want an AI interpretation.

[![Tests](https://github.com/fortunexbt/tablebeam/actions/workflows/test.yml/badge.svg)](https://github.com/fortunexbt/tablebeam/actions/workflows/test.yml)
[![License: MIT](https://img.shields.io/badge/license-MIT-22d3ee.svg)](LICENSE)

## Start

```bash
git clone https://github.com/fortunexbt/tablebeam.git
cd tablebeam
./start.sh --demo
```

The launcher creates `.venv`, checks installed dependency versions, installs or updates what is needed, and opens <http://localhost:8501>. Windows users can run `start.bat --demo`. No model or account is needed to try the example. Use `--skip-install` to check and run an existing environment without installing packages; missing or incompatible dependencies produce repair instructions.

1. Choose a suggested question, such as **Annual revenue by status**, or type **What is the total annual revenue?**
2. Read the number or chart, then **Download answer** if you want to keep it.
3. Use **Change table** to open your own CSV. Uploading opens it immediately. A failed import keeps your current table intact.

A public Google Sheet can be loaded from **Use a Google Sheet instead**. Share it as “Anyone with the link” first; opening it fetches its contents from Google.

## Ask a question

Straightforward, unambiguous calculations work without AI:

- `How many rows are there?`
- `Total annual revenue`
- `Average health score`
- `Annual revenue by status`
- `Count rows by owner`

Use your table’s actual column names; underscores and dashes can be written as spaces. Sum, average, median, minimum, and maximum are supported. Common forms such as “What is the total …?”, “Show me …”, and “Calculate …” work too.

The parser only accepts complete supported questions. It does not guess shortened column names, invent filters, or silently treat an ambiguous question as an exact calculation. Other wording offers an explicit **Ask AI** or **Connect AI** action.

## When you need more control

**Build a calculation** lets you choose the operation and columns directly, optionally comparing groups or limiting rows. Text conditions offer existing values where practical. Click **Calculate** when your choices are ready; changing a control does not silently change a completed answer.

Each new question starts from the full table. A filter belongs to the calculation that created it, and that answer shows the condition and row coverage. The previous five completed answers are available under **Previous answers**. Switching between answers preserves them; changing or clearing the table resets its questions, calculations, and history.

**How this was calculated** contains the exact operation, missing-value rules, result table, and row coverage. **View rows used** shows up to 50 rows and can export all contributing rows. **View data** previews the source and its quality notes.

Count includes every selected row. Numeric operations ignore missing measures; entirely missing measures return “No values.” Missing group labels form their own group. The chart shows up to 20 groups, while the answer download includes all groups. Integer sums and integer filter thresholds preserve precision; charts omit integers beyond their precise numeric range, while result tables and downloads retain them. Floating-point calculations follow pandas arithmetic.

Explicit answer/row downloads are UTF-8 BOM CSV and neutralize formula-like text with an apostrophe prefix. Source row numbers refer to the loaded table after empty rows are removed. CSV files, uploads, and Google Sheets imports require unique nonempty headers, consistent record widths, UTF-8, at most 100 MB, and at most 250,000 rows. Integer columns retain every digit, including when some cells are empty.

## Connect AI only when you need it

Open **AI settings**, choose LM Studio or Ollama, and click **Find local models**. Select a ready model, then return to your question and choose **Ask AI**. LM Studio reports which models are loaded; an unloaded model can be explicitly loaded. Ollama can use an installed model and loads it when asked. Tablebeam does not automatically download a model or turn unsupported wording into a generated answer.

AI sees a retrieved row sample plus the table profile, not necessarily every record. Its answer shows coverage, and **Check the sources** contains the exact rows and profile supplied to the model. The Markdown download keeps that evidence. AI claims should be checked; use built-in calculations for exact numbers.

For automatic provider startup, opt in with `./start.sh --demo --start-server`. This uses the installed provider CLI, never installs software, and accepts the older `--start-model` alias. Installer diagnostics are available with `TABLEBEAM_PIP_VERBOSE=1`.

## Use another local server

Ollama exposes the same API shape:

```bash
ollama serve
ollama pull llama3.2
./start.sh --ollama --demo
```

Any compatible endpoint can be configured directly:

```bash
export LLM_BASE_URL=http://localhost:1234/v1
export LLM_MODEL=your-loaded-model
./start.sh
```

LM Studio and Ollama normally need no API key. If your server requires one, set `LLM_API_KEY` or enter it in **AI settings → Advanced settings**.

Open **AI settings → Find local models** to discover the selected server. Server address, API key, and a custom model ID are under **Advanced settings**. Configured `LLM_BASE_URL` and `LLM_MODEL` are preserved, and closing settings does not discard them. Discovery uses LM Studio's native model API or Ollama's `/api/tags` and `/api/ps`; compatible servers can fall back to `/v1/models`, which reports availability rather than loaded state. Explicit local start/load actions use `lms server start`, `lms load`, `ollama serve`, or `ollama pull`. For a server on another host, Tablebeam gives instructions to manage it there. `--start-model` remains accepted as a backwards-compatible alias for `--start-server`.

## Optional API

The web app is the primary interface. For scripts or local integrations, start the optional API with an explicit source:

```bash
export DATA_SOURCE=/absolute/path/to/data.csv
export LLM_BASE_URL=http://localhost:1234/v1
export LLM_MODEL=your-loaded-model
python src/api_server.py
```

It exposes `/health`, `/ready`, and `POST /api/v1/query` for model Q&A. It never downloads a model and remains unavailable for queries until `DATA_SOURCE` is set. The web interface’s built-in question parser and calculation builder are separate from this model-only endpoint.

## Docker

Run the published multi-architecture release image (2.0.0 predates the unreleased interface changes below):

```bash
docker run --rm -p 8501:8501 \
  --add-host=host.docker.internal:host-gateway \
  -e LLM_BASE_URL=http://host.docker.internal:1234/v1 \
  ghcr.io/fortunexbt/tablebeam:2.0.0
```

Or build it locally:

```bash
docker build -t tablebeam .
docker run --rm -p 8501:8501 \
  --add-host=host.docker.internal:host-gateway \
  -e LLM_BASE_URL=http://host.docker.internal:1234/v1 \
  tablebeam
```

Start LM Studio on the host first. The container runs as a non-root user and does not package models or persistent data.
The image includes a Streamlit health check at `/_stcore/health`.

## Development

```bash
python -m pip install -r requirements-dev.txt
pytest -q
python -m py_compile src/*.py
bash -n start.sh
```

Tests cover CSV boundaries, conservative question parsing, exact calculations, safe result rendering, provider responses, FastAPI behavior, and complete Streamlit workflows. They use fake provider responses and require no LM Studio or Ollama. CI runs Python 3.10–3.12.

See [the changelog](CHANGELOG.md) for the current changes.

## Privacy

CSV ingestion, built-in calculations, evidence previews, and exports run in the Tablebeam process. Loading a public Google Sheet fetches it from Google. **Ask AI** sends the question, selected rows, and deterministic profile to the configured endpoint. Use a local endpoint to keep that context on your machine; a remote endpoint receives it. Provider checks and explicit start/load actions contact the selected provider. No connection is probed automatically during normal exploration, and Streamlit usage telemetry is disabled in the project configuration.

The table is session-scoped, not written to a database. Browser downloads are saved by you. Check your model server’s logging and retention settings for stricter privacy requirements.

MIT licensed. See [LICENSE](LICENSE).
