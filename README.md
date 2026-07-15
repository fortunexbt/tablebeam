# Spreadsheet Q&A Assistant

A local-first Streamlit app for exploring CSV files and public Google Sheets with a local Ollama model. It profiles the data before indexing it, validates the input boundary, and shows the retrieved source rows alongside every generated answer.

## Quick start

Prerequisites: Python 3.10+ and [Ollama](https://ollama.com/download) installed and available on the machine.

```bash
git clone https://github.com/smokingfive/client-tracker-assistant.git
cd client-tracker-assistant
./start.sh --demo
```

The launcher creates `.venv`, installs the pinned Python dependencies only when they are missing, starts a local Ollama process when needed, pulls `mxbai-embed-large` and `llama3.2` if they are missing, and opens the app at <http://localhost:8501>. Use `./start.sh --skip-model-pull` to launch the UI without downloading models.

Useful options:

```bash
./start.sh --help
./start.sh --skip-install --skip-model-pull
```

Windows users can use `start.bat`, then open the shown local URL.

## Use the app

1. Click **Try the built-in demo** or upload a UTF-8 CSV.
2. Review the row/column counts, missing values, duplicate count, and preview.
3. Ask a question using one of the suggested prompts or the chat box.
4. Expand **Sources** to inspect the exact retrieved rows. The model is instructed to cite them as `[Source N]`.

Google Sheets are loaded through the public CSV export endpoint. The sheet must be viewable by anyone with the link; this is the explicit network path in an otherwise local workflow.

## Run manually

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r src/requirements.txt
ollama serve
ollama pull mxbai-embed-large
ollama pull llama3.2
streamlit run src/app.py
```

The REST API is optional. To use it, configure a source explicitly:

```bash
export DATA_SOURCE=/absolute/path/to/data.csv
export OLLAMA_MODEL=llama3.2
python src/api_server.py
```

It exposes `/health`, `/ready`, and `POST /api/v1/query`. Without `DATA_SOURCE`, the API stays alive for health checks but correctly reports that it is not ready for queries.

## Container

Build and run the Streamlit container while using Ollama on the host:

```bash
docker build -t spreadsheet-qa .
docker run --rm -p 8501:8501 \
  --add-host=host.docker.internal:host-gateway \
  -e OLLAMA_HOST=http://host.docker.internal:11434 \
  -v spreadsheet-qa-data:/data \
  spreadsheet-qa
```

The image does not package Ollama models. This keeps image builds predictable and makes the local-model boundary explicit.

## Tests and checks

```bash
pytest -q
python -m py_compile src/*.py
bash -n start.sh
```

The deterministic ingestion, profiling, Google Sheets parsing, and citation formatting tests run without Ollama or Chroma. A full answer smoke run additionally needs the Python dependencies, a running Ollama server, and both models installed.

## Privacy and remaining risks

- CSV data and local model requests stay on the configured machine by default.
- A Google Sheets URL downloads data from Google; Pinecone and Kubernetes material remain optional deployment paths and are not used by the local app.
- Chroma persists embeddings under `VECTOR_DB_PATH` (default `./chroma_db_clients`); protect that directory like the source CSV.
- The assistant is retrieval-grounded but still generative. Verify important totals against the source rows.
- Large spreadsheets may need a future structured-analysis path for exact aggregations instead of relying on top-k semantic retrieval.

## Next release path

1. Add deterministic dataframe operations for sums, filters, grouping, and date ranges.
2. Add an explicit source/session model so multiple datasets can be served safely by the API.
3. Add end-to-end tests with a mocked Ollama endpoint and a small Chroma fixture.
4. Add authentication and a deployment-specific privacy review before exposing the API beyond localhost.

MIT License.
