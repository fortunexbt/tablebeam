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
Usage: ./start.sh [--demo] [--lm-studio|--ollama] [--start-server] [--skip-install]

  --demo          Load the included sample_data.csv automatically.
  --lm-studio     Use LM Studio at http://localhost:1234/v1 (default).
  --ollama        Use Ollama's OpenAI-compatible API at http://localhost:11434/v1.
  --start-server  Ask Tablebeam to start the selected local provider on launch.
  --skip-install  Reuse the current .venv without installing packages.

Start the selected local server yourself, then this command launches the web UI.
EOF
}

for arg in "$@"; do
  case "$arg" in
    --demo) export START_WITH_DEMO=1 ;;
    --lm-studio) export LLM_PROVIDER="LM Studio" ;;
    --ollama) export LLM_PROVIDER="Ollama" ;;
    --start-server|--start-model) export AUTO_START_PROVIDER=1 ;;
    --skip-install) SKIP_INSTALL=1 ;;
    -h|--help) usage; exit 0 ;;
    *) echo "Unknown option: $arg" >&2; usage >&2; exit 2 ;;
  esac
done

if [[ ! -f src/app.py || ! -f src/requirements.txt || ! -f src/check_dependencies.py ]]; then
  echo "Run this script from the repository root." >&2
  exit 1
fi
VENV_PYTHON="$VENV_DIR/bin/python"
if [[ ! -e "$VENV_DIR" && ! -L "$VENV_DIR" ]]; then
  command -v "$PYTHON_BIN" >/dev/null 2>&1 || { echo "Python 3.10+ is required." >&2; exit 1; }
  "$PYTHON_BIN" -c 'import sys; sys.exit("Python 3.10+ is required" if sys.version_info < (3, 10) else 0)'
  echo "Creating Python environment in $VENV_DIR..."
  "$PYTHON_BIN" -m venv "$VENV_DIR"
fi
if [[ ! -x "$VENV_PYTHON" ]]; then
  echo "The environment at $VENV_DIR has no usable bin/python. Existing files were preserved." >&2
  echo "Repair it with Python 3.10+: python3 -m venv \"$VENV_DIR\", or set VENV_DIR to a new directory." >&2
  exit 1
fi
"$VENV_PYTHON" -c 'import sys; sys.exit("The selected environment requires Python 3.10+. Set VENV_DIR to a new environment directory." if sys.version_info < (3, 10) else 0)'

if ! "$VENV_PYTHON" src/check_dependencies.py; then
  if [[ "$SKIP_INSTALL" -eq 1 ]]; then
    echo "Missing or incompatible dependencies; --skip-install prevents updates. Rerun without --skip-install." >&2
    exit 1
  fi
  echo "Installing required Python dependencies (this can take a minute)..."
  PIP_FLAGS=(--disable-pip-version-check --no-input --default-timeout=30 --retries=3 --prefer-binary)
  if [[ "${TABLEBEAM_PIP_VERBOSE:-0}" == "1" ]]; then
    PIP_FLAGS+=(--verbose)
  fi
  if ! "$VENV_PYTHON" -m pip install -r src/requirements.txt "${PIP_FLAGS[@]}"; then
    echo "Dependency installation failed. Retry with TABLEBEAM_PIP_VERBOSE=1 ./start.sh for details." >&2
    exit 1
  fi
  if ! "$VENV_PYTHON" src/check_dependencies.py; then
    echo "Dependencies are still incompatible after installation. See the version errors above." >&2
    exit 1
  fi
  echo "Dependencies ready."
fi

export LLM_PROVIDER="${LLM_PROVIDER:-LM Studio}"
if [[ -z "${LLM_BASE_URL:-}" ]]; then
  if [[ "$LLM_PROVIDER" == "Ollama" ]]; then
    export LLM_BASE_URL="http://localhost:11434/v1"
  else
    export LLM_BASE_URL="http://localhost:1234/v1"
  fi
fi
echo "Starting Tablebeam at http://localhost:8501"
echo "Local model endpoint: $LLM_BASE_URL"
exec "$VENV_PYTHON" -m streamlit run src/app.py --server.headless false --theme.base=light
