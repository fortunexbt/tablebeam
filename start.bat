@echo off
REM 🚀 SPREADSHEET Q&A ASSISTANT - ONE CLICK START
REM This script handles EVERYTHING - just run it!

cls
echo.
echo ╔═══════════════════════════════════════════════════════╗
echo ║                                                       ║
echo ║        📊 SPREADSHEET Q&A ASSISTANT                   ║
echo ║           One-Click Installation ^& Start              ║
echo ║                                                       ║
echo ╚═══════════════════════════════════════════════════════╝
echo.

REM Check if we're in the right directory
if not exist "src\app.py" (
    echo ERROR: Please run this script from the project root directory
    pause
    exit /b 1
)

REM Check Python
echo [%time%] Checking Python installation...
python --version >nul 2>&1
if %errorlevel% neq 0 (
    py --version >nul 2>&1
    if %errorlevel% neq 0 (
        echo ERROR: Python is not installed!
        echo Please install Python 3.9+ from https://python.org
        echo Make sure to check "Add Python to PATH" during installation
        pause
        exit /b 1
    ) else (
        set PYTHON_CMD=py
    )
) else (
    set PYTHON_CMD=python
)
echo ✅ Python found

REM Check/Create virtual environment
if not exist "venv" (
    echo [%time%] Creating virtual environment...
    %PYTHON_CMD% -m venv venv
    echo ✅ Virtual environment created
) else (
    echo ✅ Virtual environment exists
)

REM Activate virtual environment
echo [%time%] Activating virtual environment...
call venv\Scripts\activate.bat

REM Check Ollama FIRST (before slow Python installs)
echo [%time%] Checking for Ollama (required for AI features)...
where ollama >nul 2>&1
if %errorlevel% neq 0 (
    echo.
    echo ERROR: Ollama is not installed!
    echo.
    echo Ollama is required for AI features. Please install it first:
    echo 1. Download from: https://ollama.com/download/windows
    echo 2. Run the installer
    echo 3. Press Enter to continue...
    pause >nul
    
    where ollama >nul 2>&1
    if %errorlevel% neq 0 (
        echo ERROR: Ollama still not found. Please install it and run this script again.
        pause
        exit /b 1
    )
)
echo ✅ Ollama found

REM Install/Update pip
echo [%time%] Updating pip...
python -m pip install --upgrade pip >nul 2>&1

REM Count packages to install
for /f %%i in ('findstr /r /v "^#" src\requirements.txt ^| find /c /v ""') do set TOTAL_PACKAGES=%%i
echo [%time%] Installing %TOTAL_PACKAGES% Python packages...
echo ℹ️  This typically takes 5-15 minutes on first install
echo ℹ️  Progress will be shown below:
echo.

REM Install requirements with progress
echo Starting package installation...
echo (If this hangs for more than 2 minutes, press Ctrl+C and try again)
echo.
pip install -r src\requirements.txt --no-cache-dir
if %errorlevel% neq 0 (
    echo.
    echo ERROR: Package installation failed! Trying minimal requirements...
    echo.
    pip install -r src\requirements-minimal.txt
    if %errorlevel% neq 0 (
        echo.
        echo ERROR: Minimal installation also failed!
        echo Common fixes:
        echo 1. Delete venv\ folder and try again
        echo 2. Check your internet connection
        pause
        exit /b 1
    )
    echo Installed minimal requirements successfully
)

echo ✅ All packages installed

REM Ollama already checked above, just verify it's running

REM Start Ollama if not running
curl -s http://localhost:11434/api/tags >nul 2>&1
if %errorlevel% neq 0 (
    echo [%time%] Starting Ollama...
    start /b ollama serve >nul 2>&1
    timeout /t 5 /nobreak >nul
)
echo ✅ Ollama is running

REM Check for required models
echo [%time%] Checking AI models...
set MODELS_NEEDED=false

ollama list | findstr "llama3.2" >nul 2>&1
if %errorlevel% neq 0 (
    echo Language model not found. Downloading (~2GB, takes 3-10 minutes)...
    echo Progress:
    ollama pull llama3.2
    set MODELS_NEEDED=true
)

ollama list | findstr "mxbai-embed-large" >nul 2>&1
if %errorlevel% neq 0 (
    echo Embedding model not found. Downloading (~400MB, takes 1-3 minutes)...
    echo Progress:
    ollama pull mxbai-embed-large
    set MODELS_NEEDED=true
)

if "%MODELS_NEEDED%"=="true" (
    echo ✅ AI models downloaded successfully
) else (
    echo ✅ AI models already installed
)

REM Final preparation
echo.
echo ════════════════════════════════════════════════════════
echo ✨ Everything is ready! Starting the app...
echo ════════════════════════════════════════════════════════
echo.

REM Launch the app
echo Opening http://localhost:8501 in your browser...
echo.
echo To stop the app, press Ctrl+C
echo.

REM Start Streamlit
streamlit run src\app.py --theme.base="dark" --theme.primaryColor="#3182ce"