# Tablebeam

![Tablebeam banner](assets/tablebeam-banner.jpg)

**Ask a local model about your tables.**

Tablebeam is a small, private-by-default web app for CSV files and public Google Sheets. It validates and profiles your table locally, retrieves the most relevant rows, and sends only that context to an OpenAI-compatible local model such as [LM Studio](https://lmstudio.ai/) or [Ollama](https://ollama.com/).

[![Tests](https://github.com/fortunexbt/tablebeam/actions/workflows/test.yml/badge.svg)](https://github.com/fortunexbt/tablebeam/actions/workflows/test.yml)
[![License: MIT](https://img.shields.io/badge/license-MIT-22d3ee.svg)](LICENSE)
[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-0f172a.svg)](https://www.python.org/)

## Why Tablebeam

- **One command:** launch a working demo without a database, embedding download, or model SDK.
- **Local-first:** LM Studio is the default; Ollama and other OpenAI-compatible servers work too.
- **Traceable:** answers include expandable source rows with `[Source N]` citations.
- **Honest:** deterministic ingestion and row search stay separate from generative answers.
- **Small:** Streamlit, pandas, requests, and an optional FastAPI wrapper.

## Start in two minutes

1. In LM Studio, download a chat model and start **Developer → Local Server**.
2. Run Tablebeam:

   ```bash
   git clone https://github.com/fortunexbt/tablebeam.git
   cd tablebeam
   ./start.sh --demo
   ```

The launcher creates `.venv`, installs the small dependency set when needed, and opens <http://localhost:8501>. The first install prints progress and uses bounded retries so a network problem fails clearly instead of appearing frozen. The demo uses `sample_data.csv`; upload your own CSV or paste a public Google Sheets URL in the sidebar.

For extra installer diagnostics, use `TABLEBEAM_PIP_VERBOSE=1 ./start.sh --demo`.

To have Tablebeam attempt to start the selected local provider on launch:

```bash
./start.sh --demo --start-server
```

This uses LM Studio's `lms` CLI or Ollama's `ollama serve` when available. It never installs software or downloads model weights without an explicit model action.

Windows:

```bat
start.bat --demo
```

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

LM Studio and Ollama normally need no API key. If your server requires one, set `LLM_API_KEY` or enter it in the sidebar.

The sidebar now exposes the provider state, discovered local models, a model selector, **Start server**, **Refresh**, and **Load model** controls. For LM Studio, it uses `lms ls`, `lms ps`, `lms server start`, and `lms load`. For Ollama, it uses `/api/tags`, `ollama serve`, and `ollama pull`. `--start-model` remains accepted as a backwards-compatible alias for `--start-server`.

## How it works

1. Validate headers, row limits, empty rows, and malformed CSV data.
2. Show a compact profile: shape, column types, missing values, duplicates, and warnings.
3. Rank rows with a deterministic lexical search — no vector database or embedding service.
4. Send the profile, selected rows, and question to the local model.
5. Display the answer beside the exact retrieved rows.

For exact totals, joins, or complex grouping, use a dataframe or SQL workflow. Tablebeam is optimized for quick, inspectable questions over small-to-medium tables.

## Google Sheets

The sheet must be shared as **Anyone with the link → Viewer**. Paste its URL into the sidebar and click **Load data**. Google is the only external data fetch in the normal workflow; the downloaded table and model request stay on the configured machine.

## Optional API

The web app is the primary interface. For scripts or local integrations, start the optional API with an explicit source:

```bash
export DATA_SOURCE=/absolute/path/to/data.csv
export LLM_BASE_URL=http://localhost:1234/v1
export LLM_MODEL=your-loaded-model
python src/api_server.py
```

It exposes `/health`, `/ready`, and `POST /api/v1/query`. It never downloads a model and remains unavailable for queries until `DATA_SOURCE` is set.

## Docker

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
pytest -q
python -m py_compile src/*.py
bash -n start.sh
```

The tests use fake provider responses, so they do not require LM Studio or Ollama.

## Privacy

CSV data stays local. A Google Sheets URL is the explicit network path. Tablebeam sends only the selected rows and deterministic profile to the configured model endpoint; check that server's own logging and retention settings for stricter privacy requirements.

MIT licensed. See [LICENSE](LICENSE).
