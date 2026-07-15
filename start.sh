#!/usr/bin/env bash

# Reproducible local launcher. It installs Python packages into .venv, but it
# never installs software or models through an unreviewed remote shell script.
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT_DIR"

VENV_DIR="${VENV_DIR:-.venv}"
PYTHON_BIN="${PYTHON_BIN:-python3}"
SKIP_INSTALL=0
SKIP_MODEL_PULL="${SKIP_MODEL_PULL:-0}"

usage() {
  cat <<'EOF'
Usage: ./start.sh [--demo] [--skip-install] [--skip-model-pull]

  --demo              Open with the tracked sample dataset selected.
  --skip-install      Reuse the existing virtual environment as-is.
  --skip-model-pull   Do not download missing Ollama models.

Ollama must be installed separately. Set OLLAMA_HOST to use a local or
explicitly configured Ollama endpoint.
EOF
}

for arg in "$@"; do
  case "$arg" in
    --demo) export START_WITH_DEMO=1 ;;
    --skip-install) SKIP_INSTALL=1 ;;
    --skip-model-pull) SKIP_MODEL_PULL=1 ;;
    -h|--help) usage; exit 0 ;;
    *) echo "Unknown option: $arg" >&2; usage >&2; exit 2 ;;
  esac
done

if [[ ! -f src/app.py || ! -f src/requirements.txt ]]; then
  echo "Run this script from the repository root." >&2
  exit 1
fi
if ! command -v "$PYTHON_BIN" >/dev/null 2>&1; then
  echo "Python 3.10+ is required. Set PYTHON_BIN or install Python." >&2
  exit 1
fi

"$PYTHON_BIN" - <<'PY'
import sys
if sys.version_info < (3, 10):
    raise SystemExit("Python 3.10+ is required")
PY

if [[ ! -d "$VENV_DIR" ]]; then
  "$PYTHON_BIN" -m venv "$VENV_DIR"
fi
# shellcheck disable=SC1091
source "$VENV_DIR/bin/activate"

if [[ "$SKIP_INSTALL" -eq 0 ]]; then
  if ! python -c 'import streamlit, langchain_chroma, langchain_ollama, psutil' >/dev/null 2>&1; then
    python -m pip install --upgrade pip --disable-pip-version-check
    python -m pip install -r src/requirements.txt --disable-pip-version-check
  fi
fi

OLLAMA_HOST="${OLLAMA_HOST:-http://localhost:11434}"
export OLLAMA_HOST

if [[ "$SKIP_MODEL_PULL" -eq 0 ]]; then
  if ! command -v ollama >/dev/null 2>&1; then
    echo "Ollama is required for local answers. Install it from https://ollama.com/download" >&2
    echo "Then rerun ./start.sh (or use --skip-model-pull to launch the UI first)." >&2
    exit 1
  fi

  if ! curl --fail --silent --show-error --max-time 2 "$OLLAMA_HOST/api/tags" >/dev/null 2>&1; then
    if [[ "$OLLAMA_HOST" != "http://localhost:11434" && "$OLLAMA_HOST" != "http://127.0.0.1:11434" ]]; then
      echo "Ollama is not reachable at $OLLAMA_HOST" >&2
      exit 1
    fi
    echo "Starting local Ollama…"
    ollama serve >/tmp/client-tracker-ollama.log 2>&1 &
    OLLAMA_PID=$!
    trap 'kill "$OLLAMA_PID" 2>/dev/null || true' EXIT
    for _ in $(seq 1 30); do
      if curl --fail --silent --max-time 2 "$OLLAMA_HOST/api/tags" >/dev/null 2>&1; then break; fi
      sleep 1
    done
  fi

  if ! curl --fail --silent --max-time 2 "$OLLAMA_HOST/api/tags" >/dev/null 2>&1; then
    echo "Ollama did not become ready at $OLLAMA_HOST" >&2
    exit 1
  fi

  EMBEDDING_MODEL="${EMBEDDING_MODEL:-mxbai-embed-large}"
  LLM_MODEL="${LLM_MODEL:-llama3.2}"
  installed_models="$(ollama list 2>/dev/null || true)"
  if ! grep -Eq "^${EMBEDDING_MODEL}([[:space:]]|:)" <<<"$installed_models"; then
    echo "Pulling embedding model: $EMBEDDING_MODEL"
    ollama pull "$EMBEDDING_MODEL"
  fi
  if ! grep -Eq "^${LLM_MODEL}([[:space:]]|:)" <<<"$installed_models"; then
    echo "Pulling language model: $LLM_MODEL"
    ollama pull "$LLM_MODEL"
  fi
  export EMBEDDING_MODEL LLM_MODEL
fi

echo "Starting Streamlit at http://localhost:8501"
exec streamlit run src/app.py --server.headless true --theme.base=dark --theme.primaryColor="#3182ce"
