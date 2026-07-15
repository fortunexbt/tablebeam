@echo off
setlocal EnableExtensions
cd /d "%~dp0"

if not exist "src\app.py" (
  echo Run start.bat from the repository root.
  exit /b 1
)

set "PYTHON=py"
where py >nul 2>&1 || set "PYTHON=python"
%PYTHON% --version >nul 2>&1 || (
  echo Python 3.10+ is required.
  exit /b 1
)

set "START_WITH_DEMO="
set "AUTO_START_PROVIDER="
set "LLM_PROVIDER=LM Studio"
set "LLM_BASE_URL=http://localhost:1234/v1"
for %%A in (%*) do (
  if "%%A"=="--demo" set "START_WITH_DEMO=1"
  if "%%A"=="--start-server" set "AUTO_START_PROVIDER=1"
  if "%%A"=="--start-model" set "AUTO_START_PROVIDER=1"
  if "%%A"=="--lm-studio" set "LLM_PROVIDER=LM Studio"
  if "%%A"=="--ollama" set "LLM_BASE_URL=http://localhost:11434/v1"
  if "%%A"=="--ollama" set "LLM_PROVIDER=Ollama"
)

if not exist ".venv\Scripts\python.exe" (
  echo Creating Python environment in .venv...
  %PYTHON% -m venv .venv
)
call .venv\Scripts\activate.bat
python -c "import pandas, requests, streamlit" >nul 2>&1 || (
  echo Installing Python dependencies (first run; this can take a minute)...
  python -m pip install -r src\requirements.txt --disable-pip-version-check --no-input --default-timeout=30 --retries=3 --prefer-binary || (
    echo Dependency installation failed. Check your network connection and try again.
    exit /b 1
  )
  echo Dependencies ready.
)

echo Starting Tablebeam at http://localhost:8501
echo Local model endpoint: %LLM_BASE_URL%
streamlit run src\app.py --server.headless false --theme.base=light
