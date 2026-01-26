# Agentic AI Evaluator

> **Enterprise-grade AI system for automated agricultural product demo trial evaluation and analysis**

[![Python 3.12+](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/downloads/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.116+-green.svg)](https://fastapi.tiangolo.com/)
[![License](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)

## 📋 Table of Contents

- [Overview](#overview)
- [Key Features](#key-features)
- [Architecture](#architecture)
- [Technology Stack](#technology-stack)
- [Quick Start](#quick-start)
- [Installation](#installation)
- [Configuration](#configuration)
- [API Documentation](#api-documentation)
- [Development](#development)
- [Deployment](#deployment)
- [Troubleshooting](#troubleshooting)
- [Contributing](#contributing)

---

## 🎯 Overview

**Agentic AI Evaluator** is a production-ready, enterprise-grade system designed to automate the evaluation and analysis of agricultural product demo trials. Built with modern AI/ML technologies, it processes PDF documents, extracts structured data, performs intelligent analysis, and provides actionable insights through a conversational interface.

### Core Capabilities

- **Intelligent Document Processing**: Automated extraction and analysis of agricultural demo trial PDFs
- **Multi-Agent Evaluation System**: CrewAI-powered quality assessment with 4 specialized agents
- **Hybrid Vector Search**: Semantic + keyword search for comprehensive data retrieval
- **Conversational AI Agent**: Natural language interface with 27 specialized tools for data querying
- **Real-time Quality Scoring**: Confidence-based evaluation with automatic retry logic
- **Multi-User Support**: Cooperative-based data isolation and user session management

### Use Cases

- **Agricultural Research**: Automated analysis of field trial data
- **Product Development**: Performance evaluation and comparison
- **Data Management**: Centralized storage and retrieval of trial reports
- **Business Intelligence**: Conversational querying of agricultural data

---

## ✨ Key Features

### 🤖 Multi-Agent Evaluation System

**CrewAI-powered quality assessment** with 4 specialized agents:

1. **Document Context Analyst** - Assesses document type, data quality, and extraction completeness
2. **Output Quality Evaluator** - Evaluates analysis accuracy, completeness, and reliability
3. **Processing Strategy Advisor** - Determines optimal next steps based on quality assessment
4. **Evaluation Decision Coordinator** - Synthesizes team input into final decisions

**Benefits:**
- Collaborative decision-making for higher accuracy
- Confidence scoring (0.0-1.0) for quality assessment
- Intelligent retry logic based on quality thresholds
- Context-aware evaluation for different document types

### 🔍 Hybrid Vector Search

**Combines semantic and keyword search** for optimal retrieval:

- **Dense Retriever**: Semantic similarity using embedding models (default: 70% weight)
- **Sparse Retriever**: Keyword matching using TF-IDF (default: 30% weight)
- **Configurable Weights**: Adjustable search balance per query
- **User Isolation**: Cooperative-based data filtering

**Supported Models:**
- Embeddings: `BAAI/bge-small-en-v1.5`, `sentence-transformers/all-MiniLM-L6-v2`, `BAAI/bge-base-en-v1.5`
- Sparse: TF-IDF vectorizer with custom vocabulary

### 💬 Conversational AI Agent

**27 specialized tools** for comprehensive data querying:

- **11 Basic Search Tools**: Product, location, crop, cooperator, season, improvement range, sentiment, etc.
- **16 Advanced Search Tools**: Form type, date range, metric type, confidence level, data quality, yield status, etc.
- **3 List Tools**: Report listing, statistics, report retrieval
- **3 Analysis Tools**: Product comparison, summary generation, trend analysis
- **3 Memory Tools**: Conversation history management

**Features:**
- Natural language querying in Taglish/Filipino/English
- Context-aware responses with follow-up suggestions
- PostgreSQL-backed conversation memory
- Multi-provider LLM support (OpenRouter, Gemini)

### 📊 Intelligent Workflow Processing

**8-stage LangGraph workflow** with conditional routing:

```
Extract → Validate Content → Analyze → Evaluate Analysis 
→ Suggest Graphs → Evaluate Graphs → Chunk → End
```

**Quality Gates:**
- Content validation (LLM checks if document is a product demo)
- Analysis evaluation (multi-agent quality assessment)
- Graph evaluation (visualization quality check)
- Automatic retry with max 2 attempts

### 🔐 Enterprise Features

- **Multi-User Support**: User ID-based data isolation
- **Cooperative Isolation**: Cooperative-based access control
- **API Security**: API key authentication
- **Rate Limiting**: Configurable per-endpoint limits
- **Observability**: Langfuse integration for LLM tracing
- **Background Processing**: ARQ workers for async job processing
- **Caching**: LRU cache for agent instances and query results

---

## 🏗️ Architecture

### System Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    FastAPI Application                        │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐     │
│  │   Upload     │  │   Agent      │  │    Chat      │     │
│  │   Router     │  │   Router     │  │   Router     │     │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘     │
│         │                 │                  │              │
│         │                 │                  │              │
│         │                 │         ┌────────▼────────┐     │
│         │                 │         │  Chat Agent    │     │
│         │                 │         │  (LangChain)   │     │
│         │                 │         └────────┬────────┘     │
│         │                 │                  │              │
│         │                 │         ┌────────▼────────┐     │
│         │                 │         │  30 Tools      │     │
│         │                 │         │  (Search,      │     │
│         │                 │         │   Analysis,    │     │
│         │                 │         │   Memory)      │     │
│         │                 │         └────────┬────────┘     │
│         │                 │                  │              │
│         └────────┬─────────┴──────────────────┘             │
│                  │                                          │
│         ┌────────▼────────┐                                │
│         │  LangGraph      │                                │
│         │  Workflow       │                                │
│         │  Engine         │                                │
│         └────────┬────────┘                                │
│                  │                                          │
│    ┌─────────────┼─────────────┐                           │
│    │             │             │                           │
│ ┌──▼──┐    ┌─────▼─────┐  ┌───▼───┐                       │
│ │CrewAI│   │   LLM     │  │Embed  │                       │
│ │Agents│   │ (Gemini)  │  │Model  │                       │
│ └──────┘   └───────────┘  └───────┘                       │
└─────────────────────────────────────────────────────────────┘
         │                    │                    │
         └──────────┬─────────┴──────────┬─────────┘
                    │                     │
    ┌───────────────┼─────────────────────┼───────────────┐
    │               │                     │               │
┌───▼───┐    ┌──────▼──────┐      ┌──────▼──────┐  ┌─────▼────┐
│Qdrant │    │  PostgreSQL │      │   Redis    │  │ Langfuse │
│Vector │    │   Memory    │      │   ARQ Jobs │  │  Tracing │
│  DB   │    │              │      │            │  │          │
└───────┘    └──────────────┘      └────────────┘  └──────────┘
     ▲                ▲                    │
     │                │                    │
     └────────────────┴────────────────────┘
                      │
              (Tools access databases
               for search & retrieval)
```

### Workflow Architecture

```
┌─────────┐
│ Extract │  Extract PDF content to markdown
└────┬────┘
     │
     ▼
┌─────────────────┐
│ Validate Content│  LLM validates if document is product demo
└────────┬────────┘
     │
     ▼
┌──────────┐
│ Analyze │  LLM performs structured analysis
└────┬────┘
     │
     ▼
┌──────────────────┐
│ Evaluate Analysis│  Multi-agent quality assessment
└────────┬─────────┘
     │
     ▼
┌──────────────────┐
│ Suggest Graphs   │  LLM suggests visualizations
└────┬─────────────┘
     │
     ▼
┌──────────────────┐
│ Evaluate Graphs  │  Multi-agent quality assessment
└────┬─────────────┘
     │
     ▼
┌─────────┐
│  Chunk  │  Split content for vector storage
└────┬────┘
     │
     ▼
┌───────┐
│  END  │  Storage handled separately
└───────┘
```

### Data Flow

```
PDF Upload
    │
    ▼
Extraction (Gemini Vision)
    │
    ▼
Content Validation (LLM)
    │
    ▼
Analysis (Gemini Pro)
    │
    ▼
Multi-Agent Evaluation (CrewAI)
    │
    ▼
Graph Suggestions (Gemini)
    │
    ▼
Embedding Generation (HuggingFace)
    │
    ▼
Vector Storage (Qdrant)
    │
    ▼
Search & Retrieval (Hybrid Search)
```

### Tools & Capabilities

The system includes **30 specialized tools** for comprehensive data querying and analysis:

#### Basic Search Tools (11)
- **search_analysis_tool** - Unified search across all analysis fields
- **search_by_product_tool** - Search by product name
- **search_by_location_tool** - Search by location/farm site
- **search_by_crop_tool** - Search by crop type/variety
- **search_by_cooperator_tool** - Search by cooperator name
- **search_by_season_tool** - Search by season (wet/dry)
- **search_by_improvement_range_tool** - Search by improvement percentage range
- **search_by_sentiment_tool** - Search by cooperator feedback sentiment
- **search_by_product_category_tool** - Search by product category (herbicide, foliar, etc.)
- **search_by_performance_significance_tool** - Search by performance significance level
- **search_by_applicant_tool** - Search by applicant name

#### Advanced Search Tools (16)
- **search_by_form_type_tool** - Search by form/document type
- **search_by_date_range_tool** - Search by application/planting date range
- **search_by_metric_type_tool** - Search by metric type (rating, percentage, count, measurement)
- **search_by_confidence_level_tool** - Search by confidence level (high/medium/low)
- **search_by_data_quality_tool** - Search by data quality score
- **search_by_control_product_tool** - Search by control product used
- **search_by_speed_of_action_tool** - Search by speed of action (fast/moderate/slow)
- **search_by_yield_status_tool** - Search by yield data availability
- **search_by_yield_improvement_range_tool** - Search by yield improvement range
- **search_by_measurement_intervals_tool** - Search by measurement intervals (3 DAA, 7 DAA, etc.)
- **search_by_metrics_detected_tool** - Search by specific metrics detected
- **search_by_risk_factors_tool** - Search by identified risk factors
- **search_by_opportunities_tool** - Search by identified opportunities
- **search_by_recommendations_tool** - Search by recommendations provided
- **search_by_key_observation_tool** - Search by key observations
- **search_by_scale_info_tool** - Search by rating scale information

#### List & Retrieval Tools (3)
- **list_reports_tool** - List all available reports with pagination
- **get_stats_tool** - Get aggregated statistics across all reports
- **get_report_by_id_tool** - Retrieve specific report by ID

#### Analysis Tools (3)
- **compare_products_tool** - Compare performance across multiple products
- **generate_summary_tool** - Generate comprehensive summary of selected reports
- **get_trends_tool** - Analyze trends over time or across locations

#### Memory Tools (3)
- **read_conversation_memory** - Read conversation history
- **write_to_conversation_memory** - Store conversation context
- **get_conversation_summary** - Get summary of conversation

**Tool Features:**
- All tools support cooperative-based data filtering
- Multi-parameter filtering (AND logic)
- Natural language query parsing
- Automatic parameter extraction from queries
- Context-aware tool selection

---

## 🛠️ Technology Stack

### Core Framework
- **FastAPI 0.116+** - Modern, fast web framework for building APIs
- **Python 3.12+** - Latest Python features and performance
- **UV** - Fast Python package manager (10-100x faster than pip)

### AI/ML Stack
- **LangGraph 0.6+** - Workflow orchestration and state management
- **CrewAI 0.186+** - Multi-agent collaboration framework
- **LangChain 0.3+** - LLM application framework
- **Google Gemini** - Primary LLM (gemini-1.5-flash, gemini-1.5-pro)
- **OpenRouter** - Alternative LLM provider (Llama 3.3 70B Instruct)
- **HuggingFace Transformers** - Embedding models
- **Sentence Transformers** - Text embeddings

### Vector Database & Search
- **Qdrant 1.15+** - Vector database for semantic search
- **TF-IDF** - Sparse vector encoding for keyword search
- **LangChain EnsembleRetriever** - Hybrid search implementation

### Data Storage
- **PostgreSQL** - Conversation memory and persistent storage
- **Redis 5.3+** - Background job queue (ARQ workers)
- **Qdrant** - Vector storage for documents and analysis reports

### Observability
- **Langfuse 3.8+** - LLM observability and tracing
- **Custom Logging** - Structured logging with clean formatting

### Additional Tools
- **Pypdf 6.0+** - PDF extraction
- **Pandas 2.3+** - Data manipulation
- **Docker** - Containerization
- **Gunicorn** - Production WSGI server
- **Uvicorn** - ASGI server

---

## 🚀 Quick Start

### Prerequisites

- **Python 3.12+** installed
- **Docker** installed and running (for Qdrant)
- **Git** installed

### 1. Clone Repository

```bash
git clone <repository-url>
cd agentic-ai-evaluator
```

### 2. Install UV Package Manager

**Windows:**
```powershell
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```

**macOS/Linux:**
```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

**Or via pip:**
```bash
pip install uv
```

### 3. Install Dependencies

```bash
uv sync
```

This creates a virtual environment (`.venv`) and installs all dependencies from `uv.lock`.

### 4. Start Qdrant (Vector Database)

```bash
docker compose -f docker/docker-compose.qdrant.yml up -d
```

Verify Qdrant is running:
```bash
curl http://localhost:6333/
# Or open in browser: http://localhost:6333/dashboard
```

### 5. Configure Environment Variables

Copy `env.example` to `.env` and fill in your values:

```bash
cp env.example .env
```

**Minimum required variables:**
```env
API_KEY=your-secure-api-key-here
GEMINI_APIKEY=your-gemini-api-key
GEMINI_MODEL=gemini-1.5-flash
Qdrant_Localhost=http://localhost:6333
Qdrant_Form=form_collection
Qdrant_Analysis_Report=analysis_collection
EMBEDDING_MODEL=BAAI/bge-small-en-v1.5
REDIS_HOST=localhost
REDIS_PORT=6380
```

### 6. Run Application

```bash
uv run python main.py
```

The API will be available at `http://localhost:8000`

### 7. Verify Installation

```bash
# Health check
curl http://localhost:8000/api/health

# API documentation
# Open in browser: http://localhost:8000/docs
```

---

## 📦 Installation

### Detailed Setup Guide

#### Step 1: System Requirements

- **Python**: 3.12 or higher
- **Docker**: 20.10+ (for Qdrant)
- **Memory**: 4GB+ RAM recommended
- **Disk**: 2GB+ free space

#### Step 2: Install UV

UV is a fast Python package manager that we use for dependency management.

**Verify installation:**
```bash
uv --version
```

#### Step 3: Install Dependencies

```bash
# Install all dependencies (creates .venv automatically)
uv sync

# Verify installation
uv pip list
```

#### Step 4: Setup Qdrant

**Option A: Docker Compose (Recommended)**
```bash
docker compose -f docker/docker-compose.qdrant.yml up -d
```

**Option B: Docker Run**
```bash
docker run -d \
  --name qdrant \
  -p 6333:6333 \
  -p 6334:6334 \
  -v qdrant_storage:/qdrant/storage \
  qdrant/qdrant:latest
```

**Verify Qdrant:**
```bash
curl http://localhost:6333/
# Should return: {"title":"qdrant - vector search engine","version":"..."}
```

#### Step 5: Setup Redis (Optional, for background jobs)

**Local Redis:**
```bash
# Install Redis (varies by OS)
# macOS: brew install redis
# Ubuntu: sudo apt-get install redis-server

# Start Redis
redis-server --port 6380
```

**Or use Docker:**
```bash
docker run -d --name redis -p 6380:6379 redis:latest
```

#### Step 6: Setup PostgreSQL (Optional, for chat memory)

**Local PostgreSQL:**
```bash
# Install PostgreSQL (varies by OS)
# macOS: brew install postgresql
# Ubuntu: sudo apt-get install postgresql

# Create database
createdb agentic_ai_evaluator
```

**Or use Docker:**
```bash
docker run -d \
  --name postgres \
  -e POSTGRES_PASSWORD=yourpassword \
  -e POSTGRES_DB=agentic_ai_evaluator \
  -p 5433:5432 \
  postgres:latest
```

---

## ⚙️ Configuration

### Environment Variables

Create a `.env` file in the root directory. See `env.example` for a complete template.

#### Required Configuration

```env
# API Security
API_KEY=your-secure-api-key-here

# Google Gemini API
GEMINI_APIKEY=your-gemini-api-key
GEMINI_MODEL=gemini-1.5-flash
GEMINI_LARGE=gemini-1.5-pro

# Qdrant Vector Database
Qdrant_Localhost=http://localhost:6333
Qdrant_Form=form_collection
Qdrant_Analysis_Report=analysis_collection
QDRANT_API_KEY=  # Optional, for Qdrant Cloud

# Embedding Model
EMBEDDING_MODEL=BAAI/bge-small-en-v1.5

# Redis (for background jobs)
REDIS_HOST=localhost
REDIS_PORT=6380
REDIS_DB=0
REDIS_PASSWORD=
```

#### Optional Configuration

```env
# OpenRouter (for chat agent)
OPENROUTER_API_KEY=your-openrouter-key
OPENROUTER_MODEL=meta-llama/llama-3.3-70b-instruct:free

# PostgreSQL (for chat memory)
POSTGRES_HOST=localhost
POSTGRES_PORT=5433
POSTGRES_DB=agentic_ai_evaluator
POSTGRES_USER=postgres
POSTGRES_PASSWORD=

# Langfuse (observability)
LANGFUSE_PUBLIC_KEY=your-public-key
LANGFUSE_SECRET_KEY=your-secret-key
LANGFUSE_HOST=https://cloud.langfuse.com

# Search Settings
SEARCH_TOP_K=5
MAX_SEARCH_TOP_K=100
DENSE_WEIGHT=0.7
SPARSE_WEIGHT=0.3

# Quality Thresholds
CONFIDENCE_GOOD=0.7
CONFIDENCE_ACCEPTABLE=0.4
GRAPH_CONFIDENCE_GOOD=0.7

# Retry & Timeout
MAX_RETRY_ATTEMPTS=3
LLM_TIMEOUT_SECONDS=60
REQUEST_TIMEOUT_SECONDS=300
```

### Configuration Validation

The application validates configuration on startup. Check logs for any missing or invalid configuration:

```bash
uv run python main.py
# Look for: ✅ Configuration validation passed
```

---

## 📚 API Documentation

### Base URL

```
http://localhost:8000
```

### Authentication

All API endpoints (except health checks) require API key authentication:

```bash
curl -H "X-API-Key: your-api-key" http://localhost:8000/api/...
```

### Main Endpoints

#### 1. File Upload & Processing

**Upload and process PDF file:**
```http
POST /api/agent
Content-Type: multipart/form-data
X-API-Key: your-api-key
X-User-ID: user-123
X-Cooperative: cooperative-name

file: <PDF file>
background: false (optional, default: false)
priority: normal (optional: high, normal, low)
```

**Response:**
```json
{
  "reports": [
    {
      "analysis_result": {...},
      "graph_suggestions": {...},
      "cache_id": "uuid",
      "session_id": "uuid"
    }
  ]
}
```

**Background Processing:**
```http
POST /api/agent?background=true&priority=high
```

**Response:**
```json
{
  "status": "queued",
  "job_id": "uuid",
  "session_id": "uuid",
  "progress_url": "/api/progress/{job_id}"
}
```

#### 2. Search

**Hybrid search in analysis reports:**
```http
POST /api/analysis-search
Content-Type: application/json
X-API-Key: your-api-key
X-Cooperative: cooperative-name

{
  "query": "products in Zambales",
  "top_k": 5
}
```

**Response:**
```json
{
  "query": "products in Zambales",
  "total_results": 3,
  "results": [
    {
      "id": "uuid",
      "score": 0.85,
      "content": "...",
      "form_id": "uuid",
      "form_title": "Demo Report.pdf",
      "analysis_data": {...}
    }
  ]
}
```

#### 3. Chat Agent

**Conversational querying:**
```http
POST /chat
Content-Type: application/json
X-API-Key: your-api-key
X-User-ID: user-123
X-Cooperative: cooperative-name

{
  "message": "Ano ang products sa Zambales?",
  "thread_id": "uuid" (optional)
}
```

**Response:**
```json
{
  "response": "Ang mga produkto sa Zambales ay...",
  "thread_id": "uuid",
  "suggestions": [
    "Pwede niyo pong itanong 'Ano ang performance ng products?'"
  ]
}
```

#### 4. Storage

**Save processed results:**
```http
POST /api/storage
Content-Type: application/json
X-API-Key: your-api-key
X-User-ID: user-123

{
  "cache_id": "uuid",
  "form_title": "Demo Report.pdf"
}
```

#### 5. Progress Tracking

**Check background job progress:**
```http
GET /api/progress/{job_id}
X-API-Key: your-api-key
```

**Response:**
```json
{
  "status": "completed",
  "progress": 100,
  "result": {...}
}
```

### Interactive API Documentation

FastAPI provides interactive API documentation:

- **Swagger UI**: `http://localhost:8000/docs`
- **ReDoc**: `http://localhost:8000/redoc`

### Health Checks

```http
GET /api/health
```

**Response:**
```json
{
  "status": "ok",
  "timestamp": "2024-...",
  "checks": {
    "database": {
      "status": "ok",
      "collections_count": 2
    },
    "llm": {
      "status": "ok"
    }
  }
}
```

---

## 💻 Development

### Project Structure

```
agentic-ai-evaluator/
├── src/
│   ├── Agents/              # Multi-agent evaluation (CrewAI)
│   ├── chatbot/            # Chat agent system
│   │   ├── bot/            # Agent implementation
│   │   ├── chat/           # Chat router
│   │   ├── tools/          # 27 specialized tools
│   │   ├── memory/         # Conversation memory
│   │   └── prompts/        # System prompts
│   ├── database/           # Qdrant operations, search
│   ├── formatter/          # Data formatting, chunking
│   ├── generator/          # Embeddings, model loading
│   ├── monitoring/         # Langfuse tracing, scoring
│   ├── prompt/             # LLM prompt templates
│   ├── router/             # FastAPI route handlers
│   ├── services/           # Cache, storage services
│   ├── Upload/             # File upload handlers
│   ├── utils/              # Utilities, config, helpers
│   ├── workflow/           # LangGraph workflow
│   └── workers/            # Background workers (ARQ)
├── data/                   # Data files and PDFs
├── cache/                  # Cache directory
├── test/                   # Test files
├── docker/                 # Docker configurations
├── main.py                 # FastAPI application entry
├── pyproject.toml          # Project dependencies
├── uv.lock                 # Locked dependencies
└── README.md               # This file
```

### Running in Development Mode

```bash
# Run with auto-reload
uv run python main.py

# Or use uvicorn directly
uv run uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

### Running Tests

```bash
# Run all tests
uv run pytest

# Run with coverage
uv run pytest --cov=src --cov-report=html
```

### Code Quality

```bash
# Format code (if using black)
uv run black src/

# Lint code (if using ruff)
uv run ruff check src/
```

### Adding Dependencies

```bash
# Add a new dependency
uv add package-name

# Add development dependency
uv add --dev package-name

# Update all dependencies
uv sync --upgrade
```

---

## 🚢 Deployment

### Docker Deployment

#### Build Docker Image

```bash
docker build -t agentic-ai-evaluator:latest .
```

#### Run with Docker Compose

```bash
# Production
docker compose up -d

# Development (with hot reload)
docker compose -f docker/docker-compose.dev.yml up -d
```

#### Environment Variables in Docker

Set environment variables in `docker-compose.yml` or use `.env` file:

```yaml
environment:
  - API_KEY=${API_KEY}
  - GEMINI_APIKEY=${GEMINI_APIKEY}
  # ... other variables
```

### Production Deployment

#### Using Gunicorn (Linux/macOS)

```bash
# Start production server
./start_production.sh

# Or manually
gunicorn -c gunicorn_config.py main:app
```

#### Using Uvicorn (Windows)

```bash
# Start production server
./start_production.bat

# Or manually
uv run uvicorn main:app --host 0.0.0.0 --port 8000 --workers 4
```


#### Docker Hub

```bash
# Build and push
docker build -t your-username/agentic-ai-evaluator:latest .
docker push your-username/agentic-ai-evaluator:latest
```

### Background Workers (ARQ)

Start ARQ worker for background job processing:

```bash
uv run arq src.workers.workers.WorkerSettings
```

Or use Docker Compose (included in `docker-compose.yml`).

---

## 🔧 Troubleshooting

### Common Issues

#### 1. UV Command Not Found

**Problem:** `uv: command not found`

**Solution:**
- Restart your terminal after installation
- Or add UV to your PATH manually
- Or use `pip install uv` as fallback

#### 2. Qdrant Connection Failed

**Problem:** Cannot connect to Qdrant

**Solution:**
```bash
# Check if Qdrant is running
docker ps | grep qdrant

# Check Qdrant logs
docker logs qdrant

# Verify port is not in use
netstat -ano | findstr 6333  # Windows
lsof -i :6333                # macOS/Linux
```

#### 3. Import Errors

**Problem:** Module not found errors

**Solution:**
```bash
# Ensure dependencies are installed
uv sync

# Verify virtual environment
ls .venv  # Should exist

# Reinstall dependencies
rm -rf .venv
uv sync
```

#### 4. API Key Authentication Failed

**Problem:** 401 Unauthorized errors

**Solution:**
- Check `.env` file has `API_KEY` set
- Verify API key in request header: `X-API-Key: your-key`
- Check API key matches exactly (no extra spaces)

#### 5. LLM API Errors

**Problem:** Gemini API errors

**Solution:**
- Verify `GEMINI_APIKEY` is set correctly
- Check API key is valid and has quota
- Review `LLM_TIMEOUT_SECONDS` setting
- Check network connectivity

#### 6. Redis Connection Failed

**Problem:** ARQ worker cannot connect to Redis

**Solution:**
```bash
# Check Redis is running
redis-cli -h localhost -p 6380 ping

# Verify Redis configuration in .env
REDIS_HOST=localhost
REDIS_PORT=6380
```

#### 7. Memory Issues

**Problem:** Out of memory errors

**Solution:**
- Reduce `ARQ_MAX_JOBS` in `.env`
- Reduce `POSTGRES_POOL_MAX`
- Use smaller embedding model
- Increase system RAM

### Getting Help

1. Check logs: `docker logs qdrant` and FastAPI console output
2. Review configuration: Ensure all required env vars are set
3. Check health endpoint: `curl http://localhost:8000/api/health`
4. Review Langfuse traces (if configured) for LLM debugging

---

## 🤝 Contributing

### Development Workflow

1. **Fork the repository**
2. **Create a feature branch**: `git checkout -b feature/your-feature`
3. **Make changes** and test thoroughly
4. **Commit changes**: `git commit -m "Add feature: description"`
5. **Push to branch**: `git push origin feature/your-feature`
6. **Create Pull Request**

### Code Style

- Follow PEP 8 Python style guide
- Use type hints where possible
- Add docstrings to functions and classes
- Write tests for new features

### Testing

```bash
# Run all tests
uv run pytest

# Run specific test file
uv run pytest test/test_specific.py

# Run with verbose output
uv run pytest -v
```

---

## 📄 License

This project is licensed under the MIT License - see the LICENSE file for details.



**Built with ❤️ for agricultural data analysis**
