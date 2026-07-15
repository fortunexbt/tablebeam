#!/usr/bin/env bash

# One command, one web app. The model server is separate and stays local.
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT_DIR"

VENV_DIR="${VENV_DIR:-.venv}"
PYTHON_BIN="${PYTHON_BIN:-python3}"
SKIP_INSTALL=0

usage() {
  cat <<'EOF'
Usage: ./start.sh [--demo] [--lm-studio|--ollama] [--skip-install]

  --demo          Load the included sample_data.csv automatically.
  --lm-studio     Use LM Studio at http://localhost:1234/v1 (default).
  --ollama        Use Ollama's OpenAI-compatible API at http://localhost:11434/v1.
  --skip-install  Reuse the current .venv without installing packages.

Start the selected local server yourself, then this command launches the web UI.
EOF
}

for arg in "$@"; do
  case "$arg" in
    --demo) export START_WITH_DEMO=1 ;;
    --lm-studio) export LLM_BASE_URL="${LLM_BASE_URL:-http://localhost:1234/v1}" ;;
    --ollama) export LLM_BASE_URL="${LLM_BASE_URL:-http://localhost:11434/v1}" ;;
    --skip-install) SKIP_INSTALL=1 ;;
    -h|--help) usage; exit 0 ;;
    *) echo "Unknown option: $arg" >&2; usage >&2; exit 2 ;;
  esac
done

if [[ ! -f src/app.py || ! -f src/requirements.txt ]]; then
  echo "Run this script from the repository root." >&2
  exit 1
fi
command -v "$PYTHON_BIN" >/dev/null 2>&1 || { echo "Python 3.10+ is required." >&2; exit 1; }
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

if [[ "$SKIP_INSTALL" -eq 0 ]] && ! python -c 'import pandas, requests, streamlit' >/dev/null 2>&1; then
  python -m pip install --upgrade pip --disable-pip-version-check
  python -m pip install -r src/requirements.txt --disable-pip-version-check
fi

export LLM_BASE_URL="${LLM_BASE_URL:-http://localhost:1234/v1}"
echo "Starting Tablebeam at http://localhost:8501"
echo "Local model endpoint: $LLM_BASE_URL"
exec streamlit run src/app.py --server.headless false --theme.base=dark
