# Docker Deployment Guide

## Overview

This project uses a **multi-stage Docker build** optimized for production deployment with:
- **UV** package manager for fast, reliable dependency management
- **FastAPI** with **Uvicorn** for the API server
- **ARQ** for background task processing
- **Minimal image size** through multi-stage builds and cleanup

## Architecture

```
┌─────────────────────────────────────────┐
│         Docker Container                 │
│  ┌──────────────┐  ┌──────────────┐   │
│  │   FastAPI    │  │  ARQ Worker  │   │
│  │  (Uvicorn)   │  │  (Background) │   │
│  │  Port: 8000  │  │               │   │
│  └──────────────┘  └──────────────┘   │
└─────────────────────────────────────────┘
         │                    │
         └────────┬───────────┘
                  │
    ┌─────────────┼─────────────┐
    │             │             │
┌───▼───┐  ┌─────▼─────┐  ┌────▼────┐
│Qdrant │  │  Redis    │  │Langfuse │
│(Ext)  │  │  (Ext)    │  │  (Ext)  │
└───────┘  └───────────┘  └─────────┘
```

**Note**: Qdrant, Redis, and Langfuse are deployed separately and connected via environment variables.

## Dockerfile Explanation

### Stage 1: Builder Stage

```dockerfile
FROM python:3.12-slim AS builder
```

**Why**: Creates a temporary build environment with all build tools. This stage is discarded after copying the virtual environment.

**Key Steps**:
1. **Install build dependencies**: `gcc`, `g++`, `libffi-dev` - Required for compiling Python packages with C extensions
2. **Install UV**: Fast Python package manager (much faster than pip)
3. **Copy dependency files**: `pyproject.toml` and `uv.lock` for reproducible builds
4. **Install dependencies**: `uv sync --frozen` installs all packages into `.venv`
5. **Cleanup**: Removes cache files, tests, and documentation to reduce size

### Stage 2: Runtime Stage

```dockerfile
FROM python:3.12-slim
```

**Why**: Minimal runtime image with only essential dependencies. Much smaller than builder stage.

**Key Steps**:
1. **Copy virtual environment**: Only the `.venv` directory from builder (contains all packages)
2. **Copy application code**: Your source code
3. **Cleanup**: Remove unnecessary files from application
4. **Create non-root user**: Security best practice
5. **Set PATH**: Allows direct use of installed packages
6. **Default command**: Runs FastAPI with Uvicorn

### Why Multi-Stage Build?

- **Size reduction**: Build tools (gcc, g++, etc.) are not included in final image
- **Security**: Fewer packages = smaller attack surface
- **Speed**: Smaller images pull and start faster
- **Best practice**: Industry standard for production Docker images

## Build & Run Instructions

### 1. Build the Docker Image

```bash
# Build the image
docker build -t agentic-ai-evaluator:latest .

# Or with a specific tag
docker build -t agentic-ai-evaluator:v1.0.0 .
```

### 2. Run FastAPI Container

```bash
# Run FastAPI server
docker run -d \
  --name agentic-fastapi \
  -p 8000:8000 \
  --env-file .env \
  agentic-ai-evaluator:latest

# Or override the command
docker run -d \
  --name agentic-fastapi \
  -p 8000:8000 \
  --env-file .env \
  agentic-ai-evaluator:latest \
  uv run uvicorn main:app --host 0.0.0.0 --port 8000 --workers 4
```

### 3. Run ARQ Worker Container

```bash
# Run ARQ worker
docker run -d \
  --name agentic-arq-worker \
  --env-file .env \
  agentic-ai-evaluator:latest \
  uv run arq src.workers.workers.WorkerSettings
```

### 4. Using Docker Compose (Recommended)

```bash
# Start both FastAPI and ARQ worker
docker-compose up -d

# View logs
docker-compose logs -f

# Stop services
docker-compose down

# Rebuild and restart
docker-compose up -d --build
```

## Environment Variables

Create a `.env` file with required configuration:

```bash
# API Security
API_KEY=your-secure-api-key

# Google Gemini
GEMINI_APIKEY=your-gemini-key
GEMINI_MODEL=gemini-1.5-flash

# Qdrant (External)
Qdrant_Localhost=http://your-qdrant-host:6333
QDRANT_API_KEY=your-qdrant-key
Qdrant_Form=form_collection
Qdrant_Analysis_Report=analysis_collection

# Redis (External - for ARQ)
REDIS_URL=redis://your-redis-host:6379/0

# Langfuse (External - optional)
LANGFUSE_PUBLIC_KEY=your-public-key
LANGFUSE_SECRET_KEY=your-secret-key
LANGFUSE_HOST=https://cloud.langfuse.com

# Embedding Model
EMBEDDING_MODEL=BAAI/bge-small-en-v1.5
```

## API and ARQ Worker Structure

### FastAPI Application

**Entry Point**: `main.py`
- FastAPI app instance: `app = FastAPI()`
- Routers: All under `/api` prefix
- Health check: `GET /api/health`
- Root endpoint: `GET /`

**Command**:
```bash
uv run uvicorn main:app --host 0.0.0.0 --port 8000
```

**Why UV Run?**
- Automatically uses the virtual environment (`.venv`)
- No need to activate venv manually
- Consistent across all environments

### ARQ Worker

**Configuration**: `src.workers.workers.WorkerSettings`
- Class name must be `WorkerSettings` (ARQ requirement)
- Functions: `[process_file_background]`
- Redis connection: From `REDIS_URL` environment variable
- Retry mechanism: Built-in with configurable retries

**Command**:
```bash
uv run arq src.workers.workers.WorkerSettings
```

**Worker Functions**:
- `process_file_background`: Processes uploaded files in background
- Progress tracking: Updates Redis with job progress
- Error handling: Automatic retries on failure

## Production Best Practices

### 1. Use Gunicorn for Production (Optional)

For better performance and worker management:

```dockerfile
# In Dockerfile, change CMD to:
CMD ["uv", "run", "gunicorn", "-c", "gunicorn_config.py", "main:app"]
```

Or in docker-compose.yml:
```yaml
command: ["uv", "run", "gunicorn", "-c", "gunicorn_config.py", "main:app"]
```

### 2. Resource Limits

Add to docker-compose.yml:
```yaml
services:
  fastapi:
    deploy:
      resources:
        limits:
          cpus: '2'
          memory: 2G
        reservations:
          cpus: '1'
          memory: 1G
```

### 3. Health Checks

Already configured in docker-compose.yml:
- FastAPI: Checks `/api/health` endpoint
- ARQ Worker: Checks if process is running

### 4. Logging

Logs go to stdout/stderr (Docker best practice):
```bash
# View logs
docker logs agentic-fastapi
docker logs agentic-arq-worker

# Follow logs
docker logs -f agentic-fastapi
```

### 5. Scaling

Scale ARQ workers independently:
```bash
docker-compose up -d --scale arq-worker=3
```

### 6. Security

- ✅ Non-root user (`appuser`)
- ✅ Minimal base image (`python:3.12-slim`)
- ✅ No unnecessary packages
- ✅ Environment variables for secrets (not hardcoded)

## Troubleshooting

### Build Fails with Timeout

**Problem**: Large packages (torch, transformers) timeout during download

**Solution**: Already handled with `UV_HTTP_TIMEOUT=900` (15 minutes)

### Container Won't Start

**Problem**: Missing environment variables

**Solution**: Ensure `.env` file exists and has all required variables

### ARQ Worker Can't Connect to Redis

**Problem**: Redis URL incorrect or Redis not accessible

**Solution**: 
1. Verify `REDIS_URL` in `.env`
2. Ensure Redis is accessible from container
3. Check network connectivity

### FastAPI Can't Connect to Qdrant

**Problem**: Qdrant URL incorrect or Qdrant not accessible

**Solution**:
1. Verify `Qdrant_Localhost` in `.env`
2. Ensure Qdrant is accessible from container
3. Check firewall/network rules

## Image Size Optimization

The multi-stage build achieves:
- **Builder stage**: ~2-3GB (includes build tools)
- **Runtime stage**: ~1.5-2GB (only runtime dependencies)
- **Savings**: ~500MB-1GB by excluding build tools

Further optimization possible:
- Use `python:3.12-alpine` (smaller, but may have compatibility issues)
- Remove test files and documentation
- Use `--no-cache` for pip/uv (already done)

## Monitoring

### Health Checks

```bash
# Check FastAPI health
curl http://localhost:8000/api/health

# Check container health
docker ps  # Shows health status
```

### Logs

```bash
# FastAPI logs
docker logs agentic-fastapi

# ARQ worker logs
docker logs agentic-arq-worker

# Both with timestamps
docker-compose logs -f --timestamps
```

## Deployment

### Docker Hub

```bash
# Tag image
docker tag agentic-ai-evaluator:latest yourusername/agentic-ai-evaluator:latest

# Push to Docker Hub
docker push yourusername/agentic-ai-evaluator:latest
```

### Cloud Platforms

Works with:
- **Railway**: Use Dockerfile, set environment variables
- **Render**: Use Dockerfile, set environment variables
- **AWS ECS/Fargate**: Use Dockerfile, configure task definition
- **Google Cloud Run**: Use Dockerfile, set environment variables
- **Azure Container Instances**: Use Dockerfile, set environment variables

## Summary

This Docker setup provides:
- ✅ Production-ready multi-stage build
- ✅ Minimal image size
- ✅ Fast dependency installation with UV
- ✅ Separate FastAPI and ARQ worker containers
- ✅ Health checks and monitoring
- ✅ Security best practices
- ✅ Easy scaling and deployment

