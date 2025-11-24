# ============================================================================
# Multi-Stage Production Dockerfile for Agentic AI Evaluator
# Optimized for minimal size using UV package manager
# ============================================================================

# ============================================================================
# Stage 1: Builder Stage
# Purpose: Install dependencies and build Python packages
# ============================================================================
FROM python:3.12-slim AS builder

WORKDIR /app

# Install system dependencies required for building Python packages
# - gcc, g++: Required for compiling C extensions (e.g., cryptography, numpy)
# - libffi-dev: Required for packages that use ctypes/FFI
# - curl: For downloading UV installer (fallback method)
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    g++ \
    libffi-dev \
    curl \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# Install UV package manager
# Using pip with increased timeout for network reliability
# UV is much faster than pip for dependency resolution and installation
RUN pip install --no-cache-dir --default-timeout=300 --retries=5 uv

# Set UV timeout for large package downloads (torch, transformers, etc.)
# 900 seconds = 15 minutes for very large packages
ENV UV_HTTP_TIMEOUT=900

# Copy dependency files first (Docker layer caching optimization)
# This allows Docker to cache the dependency installation layer
# Only re-installs dependencies when pyproject.toml or uv.lock changes
COPY pyproject.toml uv.lock ./

# Install all dependencies using UV
# --frozen: Uses exact versions from uv.lock (reproducible builds)
# This creates a virtual environment at .venv with all packages
RUN uv sync --frozen

# Replace CUDA PyTorch with CPU-only version to save ~15-20GB
# This is safe because we don't use GPU (Google Gemini API + CPU embeddings)
RUN uv pip uninstall -y torch torchvision torchaudio 2>/dev/null || true && \
    uv pip install --index-url https://download.pytorch.org/whl/cpu \
        torch torchvision torchaudio --no-deps || true

# Remove NVIDIA CUDA packages (saves ~2-3GB)
RUN find /app/.venv -type d -name "*nvidia*" -exec rm -rf {} + 2>/dev/null || true && \
    find /app/.venv -type d -name "*cuda*" -exec rm -rf {} + 2>/dev/null || true

# Clean up unnecessary files to reduce image size
# Remove Python cache files, test directories, and documentation
RUN find /app/.venv -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true && \
    find /app/.venv -type f -name "*.pyc" -delete && \
    find /app/.venv -type f -name "*.pyo" -delete && \
    find /app/.venv -type d -name "tests" -exec rm -rf {} + 2>/dev/null || true && \
    find /app/.venv -type d -name "test" -exec rm -rf {} + 2>/dev/null || true && \
    # Clean up pip/uv cache
    rm -rf /root/.cache/uv /root/.cache/pip 2>/dev/null || true

# ============================================================================
# Stage 2: Runtime Stage
# Purpose: Minimal production image with only runtime dependencies
# ============================================================================
FROM python:3.12-slim

WORKDIR /app

# Install minimal runtime dependencies only
# - bash: Required for shell scripts and process management
# - procps: For pgrep command (ARQ worker healthcheck)
# No build tools needed in runtime stage (gcc, g++, etc. removed)
RUN apt-get update && apt-get install -y --no-install-recommends \
    bash \
    procps \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean \
    && rm -rf /usr/share/man/* \
    && rm -rf /usr/share/doc/*

# Copy the virtual environment from builder stage
# This contains all Python packages pre-installed and ready to use
COPY --from=builder /app/.venv /app/.venv

# Copy application code
# .dockerignore should exclude unnecessary files (cache, tests, etc.)
COPY . .

# Clean up application-level cache and unnecessary files
# Keep .venv (we need it!), but remove other unnecessary files
RUN find /app -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true && \
    find /app -type f -name "*.pyc" -delete && \
    find /app -type f -name "*.pyo" -delete && \
    rm -rf /app/.git /app/venv /app/env 2>/dev/null || true && \
    find /app -type f -name "*.md" ! -name "README.md" -delete 2>/dev/null || true && \
    rm -rf /app/test /app/tests 2>/dev/null || true

# Create non-root user for security
# Running as root in containers is a security risk
RUN useradd -m -u 1000 appuser && \
    chown -R appuser:appuser /app

# Set PATH to include .venv/bin so we can use installed packages directly
# This allows us to use "uvicorn" instead of "/app/.venv/bin/uvicorn"
ENV PATH="/app/.venv/bin:$PATH"

# Force CPU-only for PyTorch (prevents CUDA initialization)
# This ensures we don't accidentally try to use GPU and reduces memory usage
ENV CUDA_VISIBLE_DEVICES=""
ENV TORCH_DEVICE="cpu"

# Expose FastAPI port
EXPOSE 8000

# Switch to non-root user
USER appuser

# Default command: Run FastAPI with Uvicorn
# Can be overridden in docker-compose.yml or docker run command
# Using "main:app" because FastAPI app is defined in main.py as "app"
CMD ["uv", "run", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]

