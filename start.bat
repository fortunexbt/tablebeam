@echo off
setlocal EnableExtensions
cd /d "%~dp0"

if not defined VENV_DIR set "VENV_DIR=.venv"
set "SKIP_INSTALL=0"

:parse_args
if "%~1"=="" goto prepare
if "%~1"=="--demo" (
  set "START_WITH_DEMO=1"
  goto next_arg
)
if "%~1"=="--lm-studio" (
  set "LLM_PROVIDER=LM Studio"
  goto next_arg
)
if "%~1"=="--ollama" (
  set "LLM_PROVIDER=Ollama"
  goto next_arg
)
if "%~1"=="--start-server" (
  set "AUTO_START_PROVIDER=1"
  goto next_arg
)
if "%~1"=="--start-model" (
  set "AUTO_START_PROVIDER=1"
  goto next_arg
)
if "%~1"=="--skip-install" (
  set "SKIP_INSTALL=1"
  goto next_arg
)
if "%~1"=="--help" goto help
if "%~1"=="-h" goto help
echo Unknown option: %~1
call :usage
exit /b 2

:next_arg
shift
goto parse_args

:prepare
if not exist "src\app.py" goto missing_repo
if not exist "src\requirements.txt" goto missing_repo
if not exist "src\check_dependencies.py" goto missing_repo

set "VENV_PYTHON=%VENV_DIR%\Scripts\python.exe"
if exist "%VENV_PYTHON%" goto check_environment
if exist "%VENV_DIR%" goto invalid_environment

if defined PYTHON_BIN goto create_environment
set "PYTHON_BIN=py"
where py >nul 2>&1 || set "PYTHON_BIN=python"

:create_environment
"%PYTHON_BIN%" -c "import sys; sys.exit('Python 3.10+ is required' if sys.version_info < (3, 10) else 0)"
if errorlevel 1 (
  echo Python 3.10+ is required. Install Python or set PYTHON_BIN to its executable.
  exit /b 1
)
echo Creating Python environment in %VENV_DIR%...
"%PYTHON_BIN%" -m venv "%VENV_DIR%"
if errorlevel 1 exit /b 1
if not exist "%VENV_PYTHON%" goto invalid_environment

:check_environment
"%VENV_PYTHON%" -c "import sys; sys.exit('The selected environment requires Python 3.10+. Set VENV_DIR to a new environment directory.' if sys.version_info < (3, 10) else 0)"
if errorlevel 1 exit /b 1
"%VENV_PYTHON%" src\check_dependencies.py
if not errorlevel 1 goto launch
if "%SKIP_INSTALL%"=="1" (
  echo Missing or incompatible dependencies; --skip-install prevents updates. Rerun without --skip-install.
  exit /b 1
)

echo Installing required Python dependencies; this can take a minute...
set "PIP_FLAGS=--disable-pip-version-check --no-input --default-timeout=30 --retries=3 --prefer-binary"
if "%TABLEBEAM_PIP_VERBOSE%"=="1" set "PIP_FLAGS=%PIP_FLAGS% --verbose"
"%VENV_PYTHON%" -m pip install -r src\requirements.txt %PIP_FLAGS%
if errorlevel 1 (
  echo Dependency installation failed. Set TABLEBEAM_PIP_VERBOSE=1 and rerun start.bat for details.
  exit /b 1
)
"%VENV_PYTHON%" src\check_dependencies.py
if errorlevel 1 (
  echo Dependencies are still incompatible after installation. See the version errors above.
  exit /b 1
)
echo Dependencies ready.

:launch
if not defined LLM_PROVIDER set "LLM_PROVIDER=LM Studio"
if not defined LLM_BASE_URL (
  if "%LLM_PROVIDER%"=="Ollama" (
    set "LLM_BASE_URL=http://localhost:11434/v1"
  ) else (
    set "LLM_BASE_URL=http://localhost:1234/v1"
  )
)
echo Starting Tablebeam at http://localhost:8501
echo Local model endpoint: %LLM_BASE_URL%
"%VENV_PYTHON%" -m streamlit run src\app.py --server.headless false --theme.base=light
exit /b %ERRORLEVEL%

:missing_repo
echo Run start.bat from a complete Tablebeam repository.
exit /b 1

:invalid_environment
echo The environment at %VENV_DIR% has no usable Scripts\python.exe. Existing files were preserved.
echo Repair it with Python 3.10+: python -m venv "%VENV_DIR%", or set VENV_DIR to a new directory.
exit /b 1

:help
call :usage
exit /b 0

:usage
echo Usage: start.bat [--demo] [--lm-studio^|--ollama] [--start-server] [--skip-install]
echo.
echo   --demo          Load the included sample_data.csv automatically.
echo   --lm-studio     Use LM Studio at http://localhost:1234/v1 by default.
echo   --ollama        Use Ollama at http://localhost:11434/v1 by default.
echo   --start-server  Ask Tablebeam to start the selected local provider.
echo   --skip-install  Reuse the selected environment without installing packages.
exit /b 0
