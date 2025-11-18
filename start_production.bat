@echo off
REM Production startup script for Agentic AI Evaluator (Windows)
REM Usage: start_production.bat
REM NOTE: Gunicorn doesn't work on Windows, using Uvicorn instead

echo 🚀 Starting Agentic AI Evaluator in Production Mode (Windows)...

REM Check if .env file exists
if not exist .env (
    echo ❌ Error: .env file not found!
    echo Please create a .env file with required environment variables.
    exit /b 1
)

REM Set default Uvicorn settings if not provided
if "%UVICORN_HOST%"=="" set UVICORN_HOST=0.0.0.0
if "%UVICORN_PORT%"=="" set UVICORN_PORT=8000
if "%UVICORN_WORKERS%"=="" (
    REM Calculate workers: CPU_COUNT * 2 + 1
    for /f "tokens=2 delims==" %%i in ('wmic cpu get NumberOfCores /value ^| findstr "="') do set CORES=%%i
    set /a UVICORN_WORKERS=%CORES% * 2 + 1
)
if "%UVICORN_LOG_LEVEL%"=="" set UVICORN_LOG_LEVEL=info

echo 📊 Configuration:
echo    Host: %UVICORN_HOST%
echo    Port: %UVICORN_PORT%
echo    Workers: %UVICORN_WORKERS%
echo    Log Level: %UVICORN_LOG_LEVEL%
echo.
echo ⚠️  Note: Using Uvicorn (Gunicorn is Unix-only)
echo.

echo ✅ Starting Uvicorn server...
echo.

REM Start Uvicorn with multiple workers (production mode)
uv run uvicorn main:app --host %UVICORN_HOST% --port %UVICORN_PORT% --workers %UVICORN_WORKERS% --log-level %UVICORN_LOG_LEVEL%

