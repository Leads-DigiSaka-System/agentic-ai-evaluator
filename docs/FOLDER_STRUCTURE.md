# Agentic AI Evaluator — Modular Folder Structure (Senior AI Engineer)

This document defines a **modular, scalable folder structure** for the Agentic AI Evaluator project. It follows industry best practices for Python/FastAPI projects and keeps clear boundaries between API, domain, infrastructure, and shared code.

---

## 1. Design Principles

| Principle | Description |
|-----------|-------------|
| **Separation of concerns** | API layer (HTTP) is separate from domain and infrastructure. |
| **Single responsibility** | Each package has one clear purpose (e.g. `api/` = routes & deps, `infrastructure/` = DB, cache, external services). |
| **Consistent naming** | Lowercase with underscores (PEP 8); no mixed case (`Agents` → `agents`, `Upload` → `ingestion`). |
| **Testability** | Tests mirror source layout; domain and services are easy to unit test without FastAPI. |
| **Scalability** | New features map to clear places (new router → `api/`, new agent → `agents/` or `chatbot/`). |
| **Discoverability** | New engineers can infer where code lives (e.g. “Qdrant” → `infrastructure/vector_store/`). |

---

## 2. Proposed Root Layout

```
agentic-ai-evaluator/
├── .github/                    # CI/CD, issue templates (optional)
├── config/                     # Config files (env examples, deployment)
│   ├── env.example
│   └── deploymentenv.txt
├── data/                       # Seed/sample data (existing)
├── actual_data/                # Real/sample uploads (existing)
├── docker/                     # Docker Compose files, Dockerfile helpers
│   ├── README.md
│   └── docker-compose.qdrant.yml  # (if split from root)
├── docs/                       # All project documentation
│   ├── PROJECT_ANALYSIS_AND_CODE_MAP.md
│   ├── WORKFLOW_DOCUMENTATION.md
│   └── FOLDER_STRUCTURE.md     # This doc
├── scripts/                    # One-off and run scripts
│   ├── setup_postgres_memory.py
│   ├── start_docker.bat
│   ├── start_docker.sh
│   ├── start_production.bat
│   └── start_production.sh
├── tests/                      # Test suite (mirror src layout)
│   ├── conftest.py
│   ├── unit/
│   │   ├── test_chatbot/
│   │   ├── test_workflow/
│   │   ├── test_database/
│   │   └── test_agents/
│   └── integration/
├── src/
│   ├── api/                    # HTTP layer only
│   ├── core/                   # Config, constants, errors
│   ├── domain/                 # Shared models/schemas (optional)
│   ├── agents/                 # CrewAI evaluation agents
│   ├── workflow/               # LangGraph pipeline
│   ├── chatbot/                # Chat agent (LangChain)
│   ├── ingestion/              # Upload + extraction
│   ├── infrastructure/         # DB, cache, embeddings, Redis, Postgres
│   ├── services/               # App services (cache, storage)
│   ├── monitoring/             # Observability (Langfuse, scores)
│   ├── workers/                # Background jobs (ARQ)
│   ├── prompts/                # LLM prompts (workflow/analysis)
│   ├── formatter/              # Chunking, formatting, JSON
│   └── shared/                 # Cross-cutting utils (logging, retry, LLM helpers)
├── main.py                     # FastAPI app entry (keep at root)
├── gunicorn_config.py
├── Dockerfile
├── docker-compose.yml
├── pyproject.toml
├── uv.lock
├── requirements.txt
├── pytest.ini
├── README.md
└── .gitignore
```

---

## 3. Detailed `src/` Layout (Target)

### 3.1 `src/api/` — HTTP layer

- **Purpose:** FastAPI routers and dependencies only. No business logic, no direct DB access (use services/infrastructure).
- **Current → Proposed:**
  - `src/router/*` → `src/api/routes/` (or `src/api/v1/routes/` for versioning)
  - `src/chatbot/chat/chat_router.py` → `src/api/routes/chat.py` or keep under `chatbot/` and mount from `main.py`
  - `src/deps/*` → `src/api/deps/` (security, user_context, cooperative_context)

```
src/api/
├── __init__.py
├── deps/
│   ├── __init__.py
│   ├── security.py
│   ├── user_context.py
│   └── cooperative_context.py
└── routes/
    ├── __init__.py
    ├── agent.py
    ├── upload.py
    ├── search.py
    ├── storage.py
    ├── list.py
    ├── progress.py
    ├── cache.py
    ├── worker.py
    ├── delete_extract.py
    └── chat_router.py
```

### 3.2 `src/core/` — Config and core concerns

- **Purpose:** Configuration loading/validation, app-wide constants, and shared error types. No FastAPI, no I/O.
- **Current → Proposed:**
  - `src/utils/config.py` → `src/core/config.py`
  - `src/utils/constants.py` → `src/core/constants.py`
  - `src/utils/errors.py` → `src/core/errors.py`

```
src/core/
├── __init__.py
├── config.py
├── constants.py
└── errors.py
```

### 3.3 `src/domain/` — Domain models (optional)

- **Purpose:** Shared DTOs, state models, and schema-like objects used across workflow, chatbot, and API. Keeps domain logic independent of frameworks.
- **Current → Proposed:**
  - `src/workflow/state.py`, `src/workflow/models.py` can stay in `workflow/` or be re-exported from `domain/workflow/` if other modules need them.

```
src/domain/
├── __init__.py
└── workflow/
    ├── __init__.py
    ├── state.py
    └── models.py
```

### 3.4 `src/agents/` — CrewAI evaluation agents

- **Purpose:** Multi-agent evaluation (CrewAI). Single place for “evaluation crew” and related agents.
- **Current → Proposed:**
  - `src/Agents/` → `src/agents/` (lowercase; rename folder)

```
src/agents/
├── __init__.py
├── evaluation_crew.py
└── output_evaluator.py
```

### 3.5 `src/workflow/` — LangGraph pipeline

- **Purpose:** Document processing pipeline (extract → validate → analyze → evaluate → graphs → chunk). Keep as-is; already well structured.
- **Current:** No change.

```
src/workflow/
├── __init__.py
├── graph.py
├── state.py
├── models.py
├── routers.py
└── nodes/
    ├── __init__.py
    ├── nodes.py
    ├── analysis.py
    ├── evaluation_node.py
    ├── graph_suggestion_node.py
    └── validation_node.py
```

### 3.6 `src/chatbot/` — Chat agent (LangChain)

- **Purpose:** Conversational agent, tools, memory, prompts. Keep current structure.
- **Current:** No change.

```
src/chatbot/
├── __init__.py
├── bot/
├── chat/
├── tools/
├── memory/
├── prompts/
└── formatter/
```

### 3.7 `src/ingestion/` — Upload and extraction

- **Purpose:** File upload handling, PDF/image extraction, validation. Clear name (replaces “Upload”).
- **Current → Proposed:**
  - `src/Upload/` → `src/ingestion/` (rename folder and fix imports)

```
src/ingestion/
├── __init__.py
├── multiple_handler.py
├── form_extractor.py
└── file_validator.py
```

### 3.8 `src/infrastructure/` — External systems

- **Purpose:** All connections to external systems: Qdrant, Redis, Postgres, embedding models. Keeps “plumbing” in one place.
- **Current → Proposed:**
  - `src/database/*` (Qdrant + analysis search) → `src/infrastructure/vector_store/`
  - `src/generator/embedding.py`, `encoder.py`, `model_loader.py`, `qdrant_load.py` → `src/infrastructure/embeddings/` (and optional `qdrant_load` in `vector_store/`)
  - `src/generator/redis_pool.py` → `src/infrastructure/redis/`
  - `src/utils/postgres_pool.py`, `src/database/postgres_memory_schema.py` → `src/infrastructure/postgres/`

```
src/infrastructure/
├── __init__.py
├── vector_store/
│   ├── __init__.py
│   ├── client.py          # Qdrant client factory (from qdrant_load)
│   ├── insert.py
│   ├── insert_analysis.py
│   ├── analysis_search.py
│   ├── analysis_dense_retriever.py
│   ├── list_reports.py
│   ├── delete.py
│   ├── hybrid_search.py
│   ├── sparse_retriever.py
│   ├── dense_retriever.py
│   ├── collection.py
│   ├── score_utils.py
│   └── postgres_memory_schema.py  # or under postgres/
├── embeddings/
│   ├── __init__.py
│   ├── embedding.py
│   ├── encoder.py
│   ├── model_loader.py
│   └── qdrant_load.py
├── redis/
│   ├── __init__.py
│   └── redis_pool.py
└── postgres/
    ├── __init__.py
    ├── postgres_pool.py
    └── postgres_memory_schema.py
```

### 3.9 `src/services/` — Application services

- **Purpose:** Cache and storage services used by API and workers. Keep as-is.
- **Current:** No change.

```
src/services/
├── __init__.py
├── cache_service.py
└── storage_service.py
```

### 3.10 `src/monitoring/` — Observability

- **Purpose:** Langfuse tracing, session helpers, scoring. Keep as-is.
- **Current:** No change.

```
src/monitoring/
├── __init__.py
├── trace/
├── session/
└── scores/
```

### 3.11 `src/workers/` — Background jobs

- **Purpose:** ARQ workers and job definitions. Keep as-is.
- **Current:** No change.

```
src/workers/
├── __init__.py
└── workers.py
```

### 3.12 `src/prompts/` — LLM prompts (workflow)

- **Purpose:** Prompt templates for analysis, graph suggestion, etc. (Not chatbot prompts; those stay in `chatbot/prompts/`.)
- **Current → Proposed:**
  - `src/prompt/` → `src/prompts/` (plural; rename folder)

```
src/prompts/
├── __init__.py
├── analysis_template.py
├── graph_suggestion_template.py
├── prompt_helper.py
└── prompt_template.py
```

### 3.13 `src/formatter/` — Formatting and chunking

- **Purpose:** Chunking, JSON helpers, formatters used by workflow and API. Keep as-is.
- **Current:** No change.

```
src/formatter/
├── __init__.py
├── chunking.py
├── formatter.py
└── json_helper.py
```

### 3.14 `src/shared/` — Cross-cutting utilities

- **Purpose:** Logging, retry, rate limiting, LLM factory/helpers, validators. No business logic.
- **Current → Proposed:**
  - `src/utils/*` (except config, constants, errors, postgres_pool) → `src/shared/` (e.g. `clean_logger.py`, `retry_helper.py`, `llm_helper.py`, `gemini_helper.py`, `openrouter_helper.py`, `llm_factory.py`, `file_validator.py`, `season_detector.py`, `user_friendly_errors.py`, `langfuse_utils.py`, `limiter_config.py`, `safe_logger.py`, `simple_clean_logging.py`)

```
src/shared/
├── __init__.py
├── logging/
│   ├── __init__.py
│   ├── clean_logger.py
│   ├── safe_logger.py
│   └── simple_clean_logging.py
├── retry_helper.py
├── llm_helper.py
├── gemini_helper.py
├── openrouter_helper.py
├── llm_factory.py
├── file_validator.py
├── season_detector.py
├── user_friendly_errors.py
├── langfuse_utils.py
├── limiter_config.py
└── postgres_pool.py   # or move to infrastructure/postgres/
```

---

## 4. Current vs Proposed Mapping (Quick Reference)

| Current location | Proposed location |
|------------------|-------------------|
| `src/router/*` | `src/api/routes/*` |
| `src/deps/*` | `src/api/deps/*` |
| `src/utils/config.py` | `src/core/config.py` |
| `src/utils/constants.py` | `src/core/constants.py` |
| `src/utils/errors.py` | `src/core/errors.py` |
| `src/Agents/` | `src/agents/` |
| `src/Upload/` | `src/ingestion/` |
| `src/database/*` | `src/infrastructure/vector_store/*` |
| `src/generator/*` | `src/infrastructure/embeddings/` + `src/infrastructure/redis/` |
| `src/utils/postgres_pool.py`, DB schema | `src/infrastructure/postgres/*` |
| `src/prompt/` | `src/prompts/` |
| `src/utils/*` (rest) | `src/shared/*` |
| Root: `env.example`, `deploymentenv.txt` | `config/` (optional) |
| Root: `PROJECT_ANALYSIS*.md`, `WORKFLOW*.md` | `docs/` |
| Root: `setup_postgres_memory.py`, `start_*.sh/bat` | `scripts/` |
| `test/` | `tests/` with `unit/`, `integration/` |

---

## 5. Migration Strategy (Phased)

### Phase 1 — Non-breaking (do first)

1. Create new directories and `__init__.py` (scaffold) as in Section 3.
2. Move documentation to `docs/`: `PROJECT_ANALYSIS_AND_CODE_MAP.md`, `WORKFLOW_DOCUMENTATION.md`, `FOLDER_STRUCTURE.md`.
3. Move scripts to `scripts/`: `setup_postgres_memory.py`, `start_docker.*`, `start_production.*`.
4. Optionally move `env.example` and `deploymentenv.txt` to `config/` and update README.
5. Rename `test/` → `tests/` and add `unit/`, `integration/` if desired (update `pytest.ini`/imports if needed).

No import changes yet; app still runs from current layout.

### Phase 2 — Naming and low-risk moves

1. Rename `src/Agents` → `src/agents` (update all imports).
2. Rename `src/Upload` → `src/ingestion` (update all imports).
3. Rename `src/prompt` → `src/prompts` (update all imports).

Run tests and smoke checks after each rename.

### Phase 3 — API and core

1. Move `src/deps/*` → `src/api/deps/` and update imports (e.g. `from src.api.deps.security import require_api_key`).
2. Move `src/router/*` → `src/api/routes/` and update `main.py` to include routers from `src.api.routes`.
3. Move `src/utils/config.py`, `constants.py`, `errors.py` → `src/core/` and update all imports across the repo.

### Phase 4 — Infrastructure and shared

1. Move database and generator code into `src/infrastructure/` (vector_store, embeddings, redis, postgres) and update imports.
2. Move remaining `src/utils/*` into `src/shared/` (and optionally `shared/logging/`) and update imports.

After each phase, run the full test suite and manual API checks.

---

## 6. What Stays at Root

- `main.py` — FastAPI app entry (standard for uvicorn/gunicorn).
- `Dockerfile`, `docker-compose.yml` — Standard placement.
- `pyproject.toml`, `uv.lock`, `requirements.txt`, `pytest.ini`, `README.md`, `.gitignore` — Standard.
- `gunicorn_config.py` — Often kept at root.
- `data/`, `actual_data/` — Can stay at root or live under `config/`/`data/`; document in README.
- Artifacts (e.g. `tfidf_vectorizer.pkl`) — Prefer a single path (e.g. `data/` or `cache/`) and document; add to `.gitignore` if generated.

---

## 7. Summary

- **API** = routers + deps only.
- **Core** = config, constants, errors.
- **Domain** = optional shared models.
- **Agents / Workflow / Chatbot / Ingestion** = feature modules (agents, workflow, chatbot, ingestion).
- **Infrastructure** = vector_store, embeddings, redis, postgres.
- **Services** = cache, storage.
- **Monitoring / Workers** = observability and background jobs.
- **Prompts / Formatter** = workflow prompts and formatting.
- **Shared** = logging, retry, LLM helpers, validators.

This layout keeps the project modular, testable, and ready for growth (new routes, new agents, new storage backends) while aligning with common Python/FastAPI conventions.
