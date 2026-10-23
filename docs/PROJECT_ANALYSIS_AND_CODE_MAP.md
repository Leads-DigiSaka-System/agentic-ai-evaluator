# Agentic AI Evaluator — Project Analysis & Code Map

## 1. Project Overview

- **Type:** FastAPI app for agricultural product demo trial evaluation
- **Flow:** PDF/Image upload → LangGraph workflow (extract → validate → analyze → evaluate → graphs → chunk) → Qdrant storage → Search/Chat
- **Stack:** FastAPI, LangGraph, CrewAI, Qdrant, Redis (ARQ), PostgreSQL (optional), Langfuse

---

## 2. Entry Points & Routers

| Entry | File | Purpose |
|-------|------|--------|
| **App entry** | `main.py` | FastAPI app, CORS, routers, health, shutdown |
| **Upload (legacy)** | `src/router/upload.py` | `POST /api/upload-file-product-demo` — simple PDF → extract → chunk → Qdrant |
| **Agent (main)** | `src/router/agent.py` | `POST /api/agent` — full workflow (extract → validate → analyze → evaluate → graphs → chunk), sync or background (ARQ) |
| **Search** | `src/router/search.py` | `POST /api/analysis-search` — hybrid search over analysis collection |
| **Storage** | `src/router/storage.py` | Save cached agent output to Qdrant (form + analysis) |
| **List** | `src/router/list.py` | List reports (from Qdrant analysis collection) |
| **Progress** | `src/router/progress.py` | `GET /api/progress/{job_id}` — background job status |
| **Chat** | `src/chatbot/chat/chat_router.py` | `POST /api/chat` — conversational agent with tools |
| **Delete** | `src/router/delete_extract.py` | Delete by form_id or flush collection |
| **Cache / Worker** | `src/router/cache.py`, `src/router/worker.py` | Cache and worker debug/admin |

**Router registration (main.py):**
- Lines 204–214: `app.include_router(...)` for all routers; all under `require_api_key` except health.

---

## 3. Request Flow: Upload → Workflow → Storage

```
POST /api/agent (src/router/agent.py)
    │
    ├─ background=False → MultiReportHandler.process_multi_report_pdf()
    │       │
    │       └─ src/Upload/multiple_handler.py
    │           • extract_pdf_with_gemini (or pre-extracted markdown)
    │           • build state → processing_workflow.invoke()
    │
    └─ background=True → ARQ enqueue "process_file_background"
            └─ src/workers/workers.py → same process_multi_report_pdf()
```

**Workflow definition:**
- **File:** `src/workflow/graph.py`
- **Flow:** `extract` → `validate_content` → `analyze` → `evaluate_analysis` → `suggest_graphs` → `evaluate_graphs` → `chunk` → END
- **Nodes:** `src/workflow/nodes/nodes.py` (extract, chunk, error), `analysis.py`, `evaluation_node.py`, `graph_suggestion_node.py`, `validation_node.py`
- **Routing:** `src/workflow/routers.py` (route_after_extract, route_after_content_validation, etc.)

**After workflow:** Chunks + analysis result in state. Storage to Qdrant is **not** inside the graph; it’s triggered by:
- **Explicit save:** `POST /api/storage` (src/router/storage.py) using cache_id from agent response, or
- **Legacy path:** `src/router/upload.py` inserts chunks only (no full workflow).

**Qdrant usage in this flow:**
- **Form chunks:** `src/database/insert.py` — `QdrantOperations`, uses `QDRANT_LOCAL_URI`, `QDRANT_COLECTION_DEMO`
- **Analysis records:** `src/database/insert_analysis.py` — `analysis_storage`, uses `QDRANT_COLLECTION_ANALYSIS`
- Both get URL from **`src/utils/config.py`** (`QDRANT_LOCAL_URI` from env `Qdrant_Localhost`).

---

## 4. Qdrant Connection — Where It’s Used

Config (single source of URL):

- **File:** `src/utils/config.py`
- **Lines 22–25:** `Qdrant_Localhost` → `QDRANT_LOCAL_URI_RAW`, `QDRANT_API_KEY`, `QDRANT_COLECTION_DEMO`, `QDRANT_COLLECTION_ANALYSIS`
- **Lines 28–50:** `_normalize_qdrant_url()`, `QDRANT_LOCAL_URI` (no hardcoded localhost)

Code that connects to Qdrant (all use config above):

| File | What it does |
|------|----------------|
| `src/database/insert.py` | Form chunks → demo collection; `QdrantClient(url=QDRANT_LOCAL_URI, ...)` |
| `src/database/insert_analysis.py` | Analysis JSON → analysis collection |
| `src/database/analysis_search.py` | Analysis hybrid search; creates `QdrantClient(url=QDRANT_LOCAL_URI, ...)` |
| `src/database/analysis_dense_retriever.py` | Dense retriever for analysis collection (client passed in) |
| `src/database/list_reports.py` | List reports from analysis collection |
| `src/database/delete.py` | Delete by form_id; uses `src/generator/qdrant_load.py` client |
| `src/generator/qdrant_load.py` | Standalone Qdrant client for demo collection (used by delete, etc.) |
| `src/database/hybrid_search.py` | Uses `qdrant_client` from `insert.py` (form collection) |
| `main.py` | Health: `GET /api/health` and `GET /api/qdrant/check` — create `QdrantClient(url=QDRANT_LOCAL_URI, ...)` to check connection |

So: **every Qdrant connection** goes through **`QDRANT_LOCAL_URI`** (and optional `QDRANT_API_KEY`) from **`src/utils/config.py`**. For Docker, you only change `.env` (`Qdrant_Localhost` e.g. to `http://host.docker.internal:6333` or `http://qdrant:6333`).

---

## 5. Chat & Tools

- **Router:** `src/chatbot/chat/chat_router.py` — `POST /api/chat`, uses `create_chat_agent`, `invoke_agent`
- **Agent:** `src/chatbot/bot/chat_agent.py` — builds LangChain agent with 30 tools, cooperative-bound
- **Tools:** `src/chatbot/tools/` — `search_tools.py`, `search_tools_advanced.py`, `list_tools.py`, `analysis_tools.py`, `memory_tools.py`; exported in `__init__.py`
- **Prompts:** `src/chatbot/prompts/system_prompt.py`
- **Memory:** `src/chatbot/memory/` — conversation_store, postgres_memory, etc.

Chat tools call into:
- Analysis search: `src/database/analysis_search.py` (AnalysisHybridSearch) → Qdrant analysis collection
- List/stats: `src/database/list_reports.py` → Qdrant
So chat also uses the same Qdrant config.

---

## 6. Config & Constants

- **Env and app config:** `src/utils/config.py` — Gemini, OpenRouter, Qdrant, Redis, PostgreSQL, Langfuse, etc.
- **App constants:** `src/utils/constants.py` — file size, timeouts, retries, search weights, cache TTL, ARQ settings, workflow limits (e.g. `MAX_EVALUATION_ATTEMPTS`).

---

## 7. Quick Code Finder

| What you need | Where to look |
|---------------|----------------|
| Change Qdrant URL / collections | `src/utils/config.py` (env: `Qdrant_Localhost`, `Qdrant_Form`, `Qdrant_Analysis_Report`) |
| Upload + full workflow | `src/router/agent.py` → `src/Upload/multiple_handler.py` → `src/workflow/graph.py` |
| Workflow nodes (extract, analyze, evaluate, chunk) | `src/workflow/nodes/` (nodes.py, analysis.py, evaluation_node.py, graph_suggestion_node.py, validation_node.py) |
| Insert form chunks to Qdrant | `src/database/insert.py` (QdrantOperations) |
| Insert analysis to Qdrant | `src/database/insert_analysis.py` |
| Analysis search (and chat tools) | `src/database/analysis_search.py`, `src/database/analysis_dense_retriever.py` |
| List reports | `src/database/list_reports.py` |
| Chat endpoint and agent | `src/chatbot/chat/chat_router.py`, `src/chatbot/bot/chat_agent.py` |
| All chat tools | `src/chatbot/tools/` (__init__.py lists them) |
| Health and Qdrant check | `main.py` (`/`, `/api/health`, `/api/qdrant/check`) |
| Background jobs | `src/workers/workers.py` (ARQ), `src/router/progress.py` |
| Rate limits / API key | `src/utils/limiter_config.py`, `src/deps/security.py` |

---

## 8. Docker + Qdrant (Recap)

- **No code change** for Docker: app always uses `QDRANT_LOCAL_URI` from env.
- **Change only `.env`** when running in Docker:
  - Qdrant on host: `Qdrant_Localhost=http://host.docker.internal:6333` (or host IP on Linux)
  - Qdrant in same compose/network: `Qdrant_Localhost=http://qdrant:6333`
- **Documented in:** `docker/README.md` (section “Docker + Qdrant Connection”).

---

*Generated as project analysis and code map for Agentic AI Evaluator.*
