# Agentic AI Evaluator

Agentic AI for Product Demo Trials Evaluation - A FastAPI-based application for evaluating product demo trials using AI-powered analysis.

## Table of Contents

- [Prerequisites](#prerequisites)
- [Step 1: Install UV](#step-1-install-uv)
- [Step 2: Clone Repository](#step-2-clone-repository)
- [Step 3: Install Dependencies with UV](#step-3-install-dependencies-with-uv)
- [Step 4: Setup Qdrant with Docker](#step-4-setup-qdrant-with-docker)
- [Step 5: Verify Qdrant is Running](#step-5-verify-qdrant-is-running)
- [Step 6: Configure Environment Variables](#step-6-configure-environment-variables)
- [Step 7: Run FastAPI Application with UV](#step-7-run-fastapi-application-with-uv)
- [Step 8: Verify FastAPI is Running](#step-8-verify-fastapi-is-running)
- [Troubleshooting](#troubleshooting)

---

## Prerequisites

Before starting, ensure you have:

- **Python 3.12+** installed
- **Docker** installed and running
- **Git** installed

---

## Step 1: Install UV

UV is a fast Python package manager that we'll use to manage dependencies and run the application.

### Windows

Open PowerShell and run:

```powershell
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```

**Or** install via pip:

```bash
pip install uv
```

After installation, close and reopen your terminal, then verify:

```bash
uv --version
```

### macOS / Linux

Run the installation script:

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

**Or** install via pip:

```bash
pip install uv
```

After installation, reload your shell or restart your terminal, then verify:

```bash
uv --version
```

For more installation options, visit: https://github.com/astral-sh/uv

---

## Step 2: Clone Repository

Clone the repository to your local machine:

```bash
git clone <repository-url>
cd agentic-ai-evaluator
```

---

## Step 3: Install Dependencies with UV

This step will create a virtual environment and install all project dependencies using the locked versions from `uv.lock`.

### Install Dependencies

Run the following command:

```bash
uv sync
```

**What this command does:**
- Creates a virtual environment (`.venv`) if it doesn't exist
- Installs all dependencies listed in `pyproject.toml`
- Uses the exact versions specified in `uv.lock` for reproducibility
- Ensures a consistent environment across different machines

**Expected output:**
```
Using Python 3.12.x
Creating virtual environment at: .venv
Installing dependencies from lock file
...
Successfully installed [all packages]
```

### Understanding UV Lock

The `uv.lock` file ensures that everyone gets the exact same versions of dependencies. When you run `uv sync`, it reads this lock file and installs those specific versions, making your setup reproducible.

### Verify Installation

Check that dependencies are installed:

```bash
# List installed packages
uv pip list

# Or activate the virtual environment and check
# On Windows:
.venv\Scripts\activate
# On macOS/Linux:
source .venv/bin/activate

pip list
```

---

## Step 4: Setup Qdrant with Docker

Qdrant is the vector database that stores embeddings for the application. We'll set it up using Docker.

### Option A: Using Docker Compose (Recommended)

This is the easiest method - it handles everything automatically:

```bash
docker compose -f docker/docker-compose.qdrant.yml up -d
```

**What this does:**
- Pulls the Qdrant Docker image (if not already present)
- Creates and starts a Qdrant container
- Sets up persistent storage volume
- Configures health checks
- Exposes ports 6333 (HTTP) and 6334 (gRPC)

### Option B: Build Custom Qdrant Image

If you want to use the custom Dockerfile with additional healthchecks:

**1. Build the custom image:**

```bash
docker build -f docker/Dockerfile.qdrant -t qdrant-custom:latest .
```

**2. Run the custom image:**

```bash
docker run -d \
  --name qdrant \
  -p 6333:6333 \
  -p 6334:6334 \
  -v qdrant_storage:/qdrant/storage \
  qdrant-custom:latest
```

### Option C: Use Official Image Directly

Quick start with the official Qdrant image:

```bash
docker run -d \
  --name qdrant \
  -p 6333:6333 \
  -p 6334:6334 \
  -v qdrant_storage:/qdrant/storage \
  qdrant/qdrant:latest
```

### Check Docker Container Status

Verify the container is running:

```bash
docker ps
```

You should see a container named `qdrant` with status "Up".

### View Qdrant Logs

If you want to see what's happening:

```bash
# For docker compose
docker compose -f docker/docker-compose.qdrant.yml logs -f

# For direct docker run
docker logs -f qdrant
```

---

## Step 5: Verify Qdrant is Running

### Method 1: Check via Command Line

Test the Qdrant HTTP API:

```bash
curl http://localhost:6333/
```

**Expected response:**
```json
{
  "title": "qdrant - vector search engine",
  "version": "..."
}
```

### Method 2: Check via Web Browser (Recommended)

Open your web browser and navigate to:

```
http://localhost:6333/dashboard
```

**What you should see:**
- Qdrant Dashboard interface
- Server status and version information
- Ability to view collections and points

**If you see the dashboard:** ✅ Qdrant is running correctly!

**If you don't see the dashboard:**
- Check if Docker is running: `docker ps`
- Check Qdrant logs: `docker logs qdrant`
- Ensure port 6333 is not being used by another application

### Method 3: Check Container Health

```bash
docker inspect qdrant --format='{{.State.Health.Status}}'
```

Should return: `healthy`

---

## Step 6: Configure Environment Variables

Create a `.env` file in the root directory with your configuration:

```bash
# Create .env file (on Windows use: copy NUL .env)
touch .env
```

Then edit the `.env` file and add your configuration:

```env
# Google Gemini API Configuration
GEMINI_MODEL=your_gemini_model
GEMINI_APIKEY=your_gemini_api_key

# Qdrant Vector Database Configuration
Qdrant_Localhost=http://localhost:6333
Qdrant_Form=your_form_collection_name
Qdrant_Analysis_Report=your_analysis_collection_name

# Embedding Model Configuration
EMBEDDING_MODEL=your_embedding_model_name

# CORS Configuration (optional)
CONNECTION_WEB=http://localhost:8501
CONNECTION_MOBILE=your_mobile_connection_url

# Optional Configuration (with defaults)
MAX_FILE_SIZE_MB=50
SEARCH_TOP_K=5
MAX_SEARCH_TOP_K=100
DENSE_WEIGHT=0.7
SPARSE_WEIGHT=0.3
MAX_RETRY_ATTEMPTS=2
LLM_TIMEOUT_SECONDS=60
REQUEST_TIMEOUT_SECONDS=300
CONFIDENCE_GOOD=0.7
CONFIDENCE_ACCEPTABLE=0.4
GRAPH_CONFIDENCE_GOOD=0.7
LOG_LEVEL=INFO
DEBUG=false
```

**Important:** Replace the placeholder values with your actual:
- Gemini API key and model name
- Qdrant collection names
- Embedding model name

---

## Step 7: Run FastAPI Application with UV

Now that everything is set up, run the FastAPI application using UV.

### Method 1: Run Directly with UV (Recommended)

UV can run Python scripts within the virtual environment automatically:

```bash
uv run python main.py
```

**What this does:**
- Automatically activates the virtual environment
- Runs `main.py` with all dependencies from `.venv`
- Starts the FastAPI server with auto-reload enabled

**Expected output:**
```
INFO:     Started server process [xxxxx]
INFO:     Waiting for application startup.
INFO:     Application startup complete.
INFO:     Uvicorn running on http://0.0.0.0:8000 (Press CTRL+C to quit)
```

### Method 2: Activate Virtual Environment Manually

If you prefer to work within an activated environment:

**On Windows:**
```bash
.venv\Scripts\activate
python main.py
```

**On macOS / Linux:**
```bash
source .venv/bin/activate
python main.py
```

### Method 3: Run with Uvicorn Directly (Production Mode)

For production or if you need more control:

```bash
uv run uvicorn main:app --host 0.0.0.0 --port 8000
```

---

## Step 8: Verify FastAPI is Running

### Method 1: Check Root Endpoint

Open your browser or use curl:

```bash
curl http://localhost:8000/
```

**Expected response:**
```json
{
  "message": "Agentic AI Evaluation API is running"
}
```

### Method 2: Check Health Endpoint

This endpoint verifies that both the API and Qdrant are working:

```bash
curl http://localhost:8000/api/health
```

**Or open in browser:**
```
http://localhost:8000/api/health
```

**Expected response:**
```json
{
  "status": "ok",
  "timestamp": "2024-...",
  "checks": {
    "database": {
      "status": "ok",
      "collections": 0
    },
    "llm": {
      "status": "ok"
    }
  }
}
```

### Method 3: Access API Documentation

FastAPI automatically generates interactive API documentation:

**Swagger UI:**
```
http://localhost:8000/docs
```

**ReDoc:**
```
http://localhost:8000/redoc
```

---

## Troubleshooting

### UV Issues

**Problem:** `uv: command not found`
- **Solution:** Restart your terminal after installation, or add UV to your PATH

**Problem:** `uv sync` fails
- **Solution:** Ensure Python 3.12+ is installed: `python --version`
- **Solution:** Try updating UV: `pip install --upgrade uv`

### Qdrant Issues

**Problem:** Qdrant container won't start
- **Solution:** Check if port 6333 is already in use: `netstat -ano | findstr 6333` (Windows) or `lsof -i :6333` (macOS/Linux)
- **Solution:** Check Docker is running: `docker ps`
- **Solution:** View error logs: `docker logs qdrant`

**Problem:** Cannot access Qdrant dashboard
- **Solution:** Verify container is running: `docker ps | grep qdrant`
- **Solution:** Check firewall settings
- **Solution:** Try `http://127.0.0.1:6333/dashboard` instead of `localhost`

### FastAPI Issues

**Problem:** Import errors when running `uv run python main.py`
- **Solution:** Ensure `uv sync` completed successfully
- **Solution:** Verify virtual environment exists: `ls .venv` (macOS/Linux) or `dir .venv` (Windows)

**Problem:** Connection refused when accessing API
- **Solution:** Check if FastAPI is actually running (look for "Uvicorn running" message)
- **Solution:** Verify port 8000 is not in use by another application
- **Solution:** Check `.env` file exists and has correct Qdrant URL

**Problem:** Health check shows database error
- **Solution:** Ensure Qdrant is running and accessible
- **Solution:** Verify `Qdrant_Localhost=http://localhost:6333` in `.env` file

### General Issues

**Problem:** Dependencies conflict
- **Solution:** Delete `.venv` folder and run `uv sync` again
- **Solution:** Ensure `uv.lock` file is up to date (should be committed to repo)

---

## Quick Start Summary

For experienced users, here is the condensed setup:

```bash
# 1. Install UV (if not installed)
pip install uv

# 2. Clone and navigate
git clone <repository-url>
cd agentic-ai-evaluator

# 3. Install dependencies
uv sync

# 4. Start Qdrant
docker compose -f docker-compose.qdrant.yml up -d

# 5. Verify Qdrant (open in browser)
# http://localhost:6333/dashboard

# 6. Create .env file with your configuration

# 7. Run FastAPI
uv run python main.py

# 8. Verify API (open in browser)
# http://localhost:8000/docs
```

---

## Additional Resources

### Project Structure

```
agentic-ai-evaluator/
├── src/
│   ├── Agents/          # AI agent evaluators
│   ├── database/        # Vector database operations
│   ├── formatter/       # Data formatting utilities
│   ├── generator/       # Embedding and model loaders
│   ├── prompt/          # Prompt templates
│   ├── router/          # FastAPI route handlers
│   ├── services/        # Service layer
│   ├── Upload/          # File upload handlers
│   ├── utils/           # Utility functions
│   └── workflow/        # Workflow and graph definitions
├── data/                # Data files and PDFs
├── cache/               # Cache directory
├── main.py              # Application entry point
├── pyproject.toml       # Project configuration
├── uv.lock              # Locked dependencies
├── docker/
│   ├── Dockerfile.qdrant    # Qdrant Dockerfile
│   └── docker-compose.qdrant.yml  # Docker Compose for Qdrant
└── requirements.txt     # Alternative requirements (for compatibility)
```

### Useful Commands

**UV Commands:**
```bash
# Add a new dependency
uv add package-name

# Add development dependency
uv add --dev package-name

# Update all dependencies
uv sync --upgrade

# Run any Python script
uv run python script.py

# Run any command in the venv
uv run <command>
```

**Docker Commands:**
```bash
# Start Qdrant
docker compose -f docker/docker-compose.qdrant.yml up -d

# Stop Qdrant
docker compose -f docker/docker-compose.qdrant.yml down

# View logs
docker compose -f docker/docker-compose.qdrant.yml logs -f

# Remove container and data
docker compose -f docker/docker-compose.qdrant.yml down -v
```

---

## Notes

- This project uses **uv** as the primary package manager for faster and more reliable dependency resolution
- The `requirements.txt` file is maintained for compatibility but `pyproject.toml` with `uv.lock` is the source of truth
- Ensure Qdrant vector database is running and accessible before starting the application
- Google Gemini API key is required for LLM functionality
- The application runs with auto-reload enabled in development mode

---

## Support

For issues or questions:
1. Check the [Troubleshooting](#troubleshooting) section
2. Review the logs: `docker logs qdrant` and FastAPI console output
3. Verify all prerequisites are met
4. Ensure environment variables are correctly configured
