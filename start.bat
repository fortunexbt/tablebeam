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
    echo Ollama is required for AI features. Attempting automatic installation...
    echo.
    
    REM Try winget first (Windows 10/11)
    where winget >nul 2>&1
    if %errorlevel% equ 0 (
        echo Installing Ollama via winget...
        winget install Ollama.Ollama
        echo.
    ) else (
        echo Please install Ollama manually:
        echo 1. Download from: https://ollama.com/download/windows
        echo 2. Run the installer
        echo 3. Press Enter to continue...
        pause >nul
    )
    
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
echo.

REM Install requirements with simplified output
echo 📦 Installing packages... This will show minimal output to reduce clutter
echo.
pip install -r src\requirements.txt --no-cache-dir -q --disable-pip-version-check
if %errorlevel% neq 0 (
    echo.
    echo ERROR: Package installation failed! Trying minimal requirements...
    echo.
    pip install -r src\requirements-minimal.txt -q --disable-pip-version-check
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

REM Detect available RAM (Windows)
for /f "tokens=2 delims==" %%i in ('wmic OS get TotalVisibleMemorySize /value ^| find "="') do set /a RAM_KB=%%i
set /a RAM_GB=%RAM_KB% / 1048576

echo [%time%] Detected %RAM_GB%GB RAM

REM Select appropriate models based on RAM
if %RAM_GB% LSS 4 (
    set EMBEDDING_MODEL=all-minilm
    set LLM_MODEL=phi3:mini
    echo Limited RAM detected. Using lightweight models.
) else if %RAM_GB% LSS 8 (
    set EMBEDDING_MODEL=nomic-embed-text
    set LLM_MODEL=llama3.2:3b-instruct-q4_K_M
    echo Moderate RAM detected. Using balanced models.
) else (
    set EMBEDDING_MODEL=mxbai-embed-large
    set LLM_MODEL=mistral:7b-instruct-q4_K_M
    echo Sufficient RAM detected. Using high-quality models.
)

REM Check and download embedding model
ollama list | findstr "%EMBEDDING_MODEL%" >nul 2>&1
if %errorlevel% neq 0 (
    echo Embedding model (%EMBEDDING_MODEL%) not found. Downloading...
    ollama pull %EMBEDDING_MODEL%
    set MODELS_NEEDED=true
)

REM Check and download language model
ollama list | findstr "%LLM_MODEL%" >nul 2>&1
if %errorlevel% neq 0 (
    echo Language model (%LLM_MODEL%) not found. Downloading...
    ollama pull %LLM_MODEL%
    set MODELS_NEEDED=true
)

REM Also ensure we have the basic models for compatibility
ollama list | findstr "llama3.2" >nul 2>&1
if %errorlevel% neq 0 (
    echo Downloading default language model for compatibility...
    ollama pull llama3.2:latest
)

ollama list | findstr "mxbai-embed-large" >nul 2>&1
if %errorlevel% neq 0 (
    echo Downloading default embedding model for compatibility...
    ollama pull mxbai-embed-large
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