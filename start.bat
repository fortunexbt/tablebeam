@echo off
setlocal
cd /d "%~dp0"

if not exist "src\app.py" (
  echo Run start.bat from the repository root.
  exit /b 1
)

where py >nul 2>&1
if %errorlevel% equ 0 (set "PYTHON=py") else (set "PYTHON=python")
%PYTHON% --version >nul 2>&1
if %errorlevel% neq 0 (
  echo Python 3.10+ is required: https://python.org
  exit /b 1
)

if not exist ".venv\Scripts\python.exe" %PYTHON% -m venv .venv
call .venv\Scripts\activate.bat

python -c "import streamlit, langchain_chroma, langchain_ollama, psutil" >nul 2>&1
if %errorlevel% neq 0 (
  python -m pip install --upgrade pip --disable-pip-version-check
  python -m pip install -r src\requirements.txt --disable-pip-version-check
)

where ollama >nul 2>&1
if %errorlevel% neq 0 (
  echo Ollama is required. Install it from https://ollama.com/download/windows
  exit /b 1
)

curl.exe --fail --silent --max-time 2 http://localhost:11434/api/tags >nul 2>&1
if %errorlevel% neq 0 start "Ollama" /b ollama serve
timeout /t 3 /nobreak >nul

ollama list | findstr /b /c:"mxbai-embed-large" >nul 2>&1
if %errorlevel% neq 0 ollama pull mxbai-embed-large
ollama list | findstr /b /c:"llama3.2" >nul 2>&1
if %errorlevel% neq 0 ollama pull llama3.2

echo Starting Streamlit at http://localhost:8501
streamlit run src\app.py --server.headless true --theme.base=dark --theme.primaryColor="#3182ce"
