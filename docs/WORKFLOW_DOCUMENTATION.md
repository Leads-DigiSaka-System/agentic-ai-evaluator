# Agentic AI Evaluator - Workflow & Technical Documentation

## Overview
Agentic AI for Product Demo Trials Evaluation - A FastAPI-based application for evaluating agricultural product demo trials using AI-powered analysis with multi-agent evaluation systems.

---

## 🏗️ Tech Stack

### Core Framework
- **FastAPI** - Web framework and API server
- **Python 3.12+** - Programming language
- **UV** - Package manager (faster alternative to pip)

### AI/ML Stack
- **LangGraph** - Workflow orchestration and state management
- **CrewAI** - Multi-agent evaluation system (4 specialized agents)
- **LangChain** - LLM framework and tooling
- **Google Gemini** - Primary LLM provider (gemini-1.5-flash, gemini-1.5-pro)
- **OpenRouter** - Alternative LLM provider (for chat agent)
- **HuggingFace Transformers** - Embedding models
- **Sentence Transformers** - Text embeddings

### Vector Database & Search
- **Qdrant** - Vector database for semantic search
- **Hybrid Search** - Combines dense (semantic) + sparse (keyword) retrieval
- **TF-IDF** - Sparse vector encoding for keyword search

### Data Storage
- **PostgreSQL** - Conversation memory and persistent storage
- **Redis** - Background job queue (ARQ workers)
- **Qdrant** - Vector storage for documents and analysis reports

### Observability & Monitoring
- **Langfuse** - LLM observability and tracing
- **Custom Logging** - Structured logging with clean formatting

### Additional Tools
- **Pypdf** - PDF extraction
- **Pandas** - Data manipulation
- **Docker** - Containerization
- **Gunicorn** - Production WSGI server

---

## 🤖 Models Used

### LLM Models (Inference)
1. **Google Gemini**
   - Primary: `gemini-1.5-flash` (fast, cost-effective)
   - Large: `gemini-1.5-pro` (for complex analysis)
   - Used for: Analysis, evaluation, content validation, graph suggestions

2. **OpenRouter Models**
   - Default: `meta-llama/llama-3.3-70b-instruct:free`
   - Used for: Chat agent conversations
   - Alternative: Can use other models via OpenRouter

### Embedding Models
- **Configurable via `EMBEDDING_MODEL` env var**
- Default: `BAAI/bge-small-en-v1.5` (384 dimensions)
- Alternatives:
  - `sentence-transformers/all-MiniLM-L6-v2` (384 dim)
  - `BAAI/bge-base-en-v1.5` (768 dim, better quality)
- Used for: Dense vector embeddings in Qdrant

### Sparse Encoding
- **TF-IDF Vectorizer** - For keyword-based search
- Stored in: `tfidf_vectorizer.pkl`
- Used for: Sparse vector retrieval in hybrid search

---

## 📊 Workflow Architecture

### Main Processing Workflow (LangGraph)

```
1. EXTRACT
   ↓
2. VALIDATE_CONTENT (NEW - LLM validates if it's a product demo)
   ↓
3. ANALYZE (LLM analyzes agricultural demo data)
   ↓
4. EVALUATE_ANALYSIS (Multi-agent evaluation of analysis quality)
   ↓
5. SUGGEST_GRAPHS (LLM suggests visualization charts)
   ↓
6. EVALUATE_GRAPHS (Multi-agent evaluation of graph suggestions)
   ↓
7. CHUNK (Split content for vector storage)
   ↓
8. END (Storage handled separately via API)
```

### Workflow Nodes

1. **Extraction Node** (`extraction_node`)
   - Extracts content from uploaded PDFs
   - Validates file format
   - Converts to markdown

2. **Content Validation Node** (`content_validation_node`)
   - LLM validates if document is a product demo trial
   - Filters out irrelevant documents
   - Prevents processing non-demo documents

3. **Analysis Node** (`analysis_node`)
   - Universal adaptive analyzer
   - Detects product type, metrics, assessment intervals
   - Generates structured analysis JSON
   - Uses `gemini-1.5-pro` for complex analysis

4. **Evaluation Node** (`evaluation_node`)
   - **Multi-Agent System (CrewAI)**:
     - Context Analyst - Assesses document quality
     - Quality Assessor - Evaluates output quality
     - Strategy Planner - Determines next steps
     - Decision Coordinator - Makes final decision
   - Returns confidence score (0.0-1.0)
   - Decision: `store`, `re_analyze`, or `suggest_graphs`

5. **Graph Suggestion Node** (`graph_suggestion_node`)
   - LLM suggests appropriate charts/visualizations
   - Based on analysis results

6. **Chunking Node** (`chunking_node`)
   - Splits content into chunks for vector storage
   - Prepares for embedding and storage in Qdrant

### Conditional Routing

- **After Extract**: → Validate Content or Handle Errors
- **After Validation**: → Analyze or Handle Errors
- **After Analysis**: → Evaluate Analysis or Handle Errors
- **After Analysis Evaluation**: → Suggest Graphs, Retry Analysis, or Handle Errors
- **After Graph Suggestion**: → Evaluate Graphs or Handle Errors
- **After Graph Evaluation**: → Chunk, Retry Graphs, or Handle Errors
- **After Chunk**: → END or Handle Errors

---

## 🔄 Multi-Agent Evaluation System (CrewAI)

### Evaluation Crew Structure

**4 Specialized Agents:**

1. **Document Context Analyst**
   - Role: Analyze document type, data quality, extraction completeness
   - Focus: Agricultural documents, data completeness, source vs extraction issues

2. **Output Quality Evaluator**
   - Role: Evaluate analysis accuracy, completeness, reliability
   - Focus: Agricultural metrics, calculations, statistical significance

3. **Processing Strategy Advisor**
   - Role: Determine optimal next steps based on quality assessment
   - Focus: Retry decisions, quality vs efficiency balance

4. **Evaluation Decision Coordinator**
   - Role: Synthesize team input into final decision
   - Output: JSON with confidence, feedback, decision, issue_type

### Evaluation Process

1. **Context Analysis Task** - Assess document quality
2. **Quality Assessment Task** - Evaluate output (analysis or graphs)
3. **Strategic Planning Task** - Determine next action
4. **Final Decision Task** - Coordinate and return JSON decision

### Confidence Scoring
- **0.8-1.0**: Excellent quality → Proceed
- **0.6-0.8**: Good quality → Acceptable
- **0.4-0.6**: Moderate quality → Consider retry
- **0.0-0.4**: Poor quality → Retry recommended

---

## 💾 Data Storage & Collections

### Qdrant Collections

1. **Form Collection** (`Qdrant_Form`)
   - Stores: Extracted form content chunks
   - Vectors: Dense (embedding) + Sparse (TF-IDF)
   - Metadata: form_id, form_title, form_type, date_of_insertion, user_id

2. **Analysis Collection** (`Qdrant_Analysis_Report`)
   - Stores: Analysis reports and summaries
   - Vectors: Dense + Sparse
   - Metadata: analysis_id, related_form_id, user_id

### PostgreSQL Tables
- **Conversation Memory** - Chat agent conversation history
- **Session Management** - User session tracking

### Redis
- **ARQ Job Queue** - Background processing tasks
- **Caching** - Agent instances, query embeddings

---

## 🔍 Search System

### Hybrid Search Architecture

**Dense Retriever (Semantic)**
- Uses: Embedding model (e.g., BAAI/bge-small-en-v1.5)
- Finds: Semantically similar documents
- Weight: 0.7 (default)

**Sparse Retriever (Keyword)**
- Uses: TF-IDF vectorizer
- Finds: Keyword matches
- Weight: 0.3 (default)

**Ensemble Retriever**
- Combines: Dense + Sparse results
- Ranks: By weighted scores
- Returns: Top-K results

### Search Features
- User ID filtering (data isolation)
- Configurable weights
- Score normalization
- Retriever comparison tools

---

## 📈 Data Flow

### Upload & Processing Flow

```
1. User uploads PDF
   ↓
2. File validation (format, size)
   ↓
3. PDF extraction → Markdown
   ↓
4. Content validation (LLM check)
   ↓
5. Analysis (LLM structured analysis)
   ↓
6. Evaluation (Multi-agent quality check)
   ↓
7. Graph suggestions (if analysis passes)
   ↓
8. Graph evaluation (Multi-agent check)
   ↓
9. Chunking (for vector storage)
   ↓
10. Embedding (dense + sparse vectors)
    ↓
11. Storage in Qdrant (form + analysis collections)
```

### Search Flow

```
1. User query
   ↓
2. Query embedding (dense)
   ↓
3. Query TF-IDF encoding (sparse)
   ↓
4. Hybrid search (dense + sparse)
   ↓
5. User ID filtering
   ↓
6. Result ranking & scoring
   ↓
7. Return top-K results
```

---

## 🧪 Train-Test-Validation Split

**Note:** This system is primarily an **evaluation/processing system**, not a traditional ML training system. However:

### Evaluation Approach
- **No explicit train/test/val splits** - This is a production evaluation system
- **Quality evaluation** happens in real-time via multi-agent system
- **Confidence scoring** (0.0-1.0) determines quality thresholds

### Data Handling
- **Incoming data**: Processed on-demand (no pre-training)
- **Stored data**: Used for retrieval and reference
- **Evaluation**: Real-time quality assessment per document

### Quality Thresholds (Configurable)
- `CONFIDENCE_GOOD=0.7` - Good quality threshold
- `CONFIDENCE_ACCEPTABLE=0.4` - Acceptable quality threshold
- `GRAPH_CONFIDENCE_GOOD=0.7` - Graph quality threshold

### Retry Logic
- **Max attempts**: 2 (configurable via `MAX_RETRY_ATTEMPTS`)
- **Retry triggers**: Low confidence scores (< 0.4-0.6)
- **Retry decisions**: Made by Strategy Planner agent

---

## 🔐 Security & Multi-User Support

### API Security
- **API Key Authentication** - Required for all endpoints
- **User ID Isolation** - Data filtered by user_id
- **Rate Limiting** - Via SlowAPI middleware

### Multi-User Features
- **User ID tracking** - Throughout workflow
- **Data isolation** - Search results filtered by user_id
- **Session management** - PostgreSQL-backed sessions
- **Cache per user** - Agent instances cached per user

---

## 📝 Configuration

### Required Environment Variables

```env
# API Security
API_KEY=your-secure-api-key

# LLM Providers
GEMINI_APIKEY=your-gemini-key
GEMINI_MODEL=gemini-1.5-flash
GEMINI_LARGE=gemini-1.5-pro

OPENROUTER_API_KEY=your-openrouter-key
OPENROUTER_MODEL=meta-llama/llama-3.3-70b-instruct:free

# Vector Database
Qdrant_Localhost=http://localhost:6333
Qdrant_Form=form_collection
Qdrant_Analysis_Report=analysis_collection

# Embeddings
EMBEDDING_MODEL=BAAI/bge-small-en-v1.5

# Redis (for background jobs)
REDIS_HOST=localhost
REDIS_PORT=6380

# PostgreSQL (optional, for chat memory)
POSTGRES_HOST=localhost
POSTGRES_PORT=5433
POSTGRES_DB=agentic_ai_evaluator
POSTGRES_USER=postgres
POSTGRES_PASSWORD=

# Observability (optional)
LANGFUSE_PUBLIC_KEY=your-key
LANGFUSE_SECRET_KEY=your-secret
```

### Optional Configuration
- `MAX_RETRY_ATTEMPTS=3` - LLM retry attempts
- `LLM_TIMEOUT_SECONDS=60` - LLM timeout
- `DENSE_WEIGHT=0.7` - Hybrid search dense weight
- `SPARSE_WEIGHT=0.3` - Hybrid search sparse weight
- `SEARCH_TOP_K=5` - Default search results count

---

## 🚀 API Endpoints

### Main Endpoints
- `POST /api/upload` - Upload and process PDFs
- `POST /api/agent` - Trigger agent workflow
- `GET /api/search` - Hybrid search
- `GET /api/list` - List stored reports
- `POST /api/storage` - Store processed results
- `GET /api/health` - Health check
- `GET /api/qdrant/check` - Qdrant connection check

### Chat Endpoints
- `POST /chat` - Chat with agent
- `GET /chat/history` - Get conversation history

---

## 📦 Project Structure

```
agentic-ai-evaluator/
├── src/
│   ├── Agents/              # Multi-agent evaluation (CrewAI)
│   ├── chatbot/            # Chat agent system
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
├── main.py                 # FastAPI application entry
├── pyproject.toml          # Project dependencies
└── docker/                 # Docker configurations
```

---

## 🔄 Key Features

1. **Multi-Agent Evaluation** - 4 specialized agents for quality assessment
2. **Hybrid Search** - Semantic + keyword search
3. **Adaptive Analysis** - Universal analyzer for any agricultural demo
4. **Real-time Quality Scoring** - Confidence-based evaluation
5. **Retry Logic** - Intelligent retry based on quality assessment
6. **Multi-User Support** - User isolation and session management
7. **Observability** - Langfuse tracing and monitoring
8. **Production Ready** - Docker, Gunicorn, PostgreSQL support

---

## 📚 Additional Notes

- **No traditional ML training** - System uses pre-trained models (Gemini, embeddings)
- **Real-time evaluation** - Quality assessment happens per document
- **Configurable thresholds** - Quality thresholds via environment variables
- **Extensible** - Easy to add new agents, models, or evaluation criteria

---

*Last Updated: Based on current codebase analysis*

