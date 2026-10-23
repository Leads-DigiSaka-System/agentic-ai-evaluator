# File Placement Guide — Saan Ilalagay ang Bawat File

Reference para sa pag-transfer ng files sa bagong modular structure. Ikaw na ang mag-transfer; ito ang mapa kung saan ilalagay ang bawat file.

---

## 1. Buong Proposed Folder Structure (Target)

```
agentic-ai-evaluator/
├── config/                          # (Optional) env at deployment
│   ├── env.example
│   └── deploymentenv.txt
├── data/                             # Sample/seed data — HINDI LILIPAT
├── actual_data/                      # Actual uploads — HINDI LILIPAT
├── docker/
│   └── README.md                     # — HINDI LILIPAT
├── docs/                             # (Optional) lahat ng documentation
│   ├── PROJECT_ANALYSIS_AND_CODE_MAP.md
│   ├── WORKFLOW_DOCUMENTATION.md
│   └── FOLDER_STRUCTURE.md
├── scripts/                          # (Optional) setup at start scripts
│   ├── setup_postgres_memory.py
│   ├── start_docker.bat
│   ├── start_docker.sh
│   ├── start_production.bat
│   └── start_production.sh
├── test/                             # Current tests — later lipat sa tests/unit/
│   └── ...
├── tests/                            # Target test structure (may unit/, integration/)
│   ├── unit/
│   │   ├── test_chatbot/
│   │   ├── test_workflow/
│   │   └── ...
│   └── integration/
├── src/
│   ├── api/                          # HTTP layer lang
│   │   ├── deps/                     # Security, user/cooperative context
│   │   │   ├── security.py
│   │   │   ├── user_context.py
│   │   │   └── cooperative_context.py
│   │   └── routes/                   # Lahat ng router files
│   │       ├── agent.py
│   │       ├── upload.py
│   │       ├── search.py
│   │       ├── storage.py
│   │       ├── list.py
│   │       ├── progress.py
│   │       ├── cache.py
│   │       ├── worker.py
│   │       ├── delete_extract.py
│   │       └── chat_router.py        # (from chatbot/chat/)
│   │
│   ├── core/                         # Config, constants, errors
│   │   ├── config.py
│   │   ├── constants.py
│   │   └── errors.py
│   │
│   ├── domain/                       # (Optional) shared models
│   │   └── workflow/
│   │       ├── state.py
│   │       └── models.py
│   │
│   ├── agents/                       # CrewAI — RENAME from Agents
│   │   ├── evaluation_crew.py
│   │   └── output_evaluator.py
│   │
│   ├── workflow/                     # — HINDI LILIPAT (stay as-is)
│   │   ├── graph.py
│   │   ├── state.py
│   │   ├── models.py
│   │   ├── routers.py
│   │   └── nodes/
│   │
│   ├── chatbot/                      # — HINDI LILIPAT (stay as-is)
│   │   ├── bot/
│   │   ├── chat/
│   │   ├── tools/
│   │   ├── memory/
│   │   ├── prompts/
│   │   └── formatter/
│   │
│   ├── ingestion/                    # RENAME from Upload
│   │   ├── multiple_handler.py
│   │   ├── form_extractor.py
│   │   └── file_validator.py
│   │
│   ├── infrastructure/               # DB, embeddings, redis, postgres
│   │   ├── vector_store/             # from database/
│   │   │   ├── analysis_dense_retriever.py
│   │   │   ├── analysis_search.py
│   │   │   ├── collection.py
│   │   │   ├── delete.py
│   │   │   ├── dense_retriever.py
│   │   │   ├── hybrid_search.py
│   │   │   ├── insert_analysis.py
│   │   │   ├── insert.py
│   │   │   ├── list_reports.py
│   │   │   ├── score_utils.py
│   │   │   └── sparse_retriever.py
│   │   ├── embeddings/               # from generator/ (except redis_pool)
│   │   │   ├── embedding.py
│   │   │   ├── encoder.py
│   │   │   ├── model_loader.py
│   │   │   └── qdrant_load.py
│   │   ├── redis/
│   │   │   └── redis_pool.py
│   │   └── postgres/
│   │       ├── postgres_pool.py
│   │       └── postgres_memory_schema.py
│   │
│   ├── services/                     # — HINDI LILIPAT
│   │   ├── cache_service.py
│   │   └── storage_service.py
│   │
│   ├── monitoring/                   # — HINDI LILIPAT
│   │   ├── trace/
│   │   ├── session/
│   │   └── scores/
│   │
│   ├── workers/                      # — HINDI LILIPAT
│   │   └── workers.py
│   │
│   ├── prompts/                      # RENAME from prompt (workflow prompts)
│   │   ├── analysis_template.py
│   │   ├── graph_suggestion_template.py
│   │   ├── prompt_helper.py
│   │   └── prompt_template.py
│   │
│   ├── formatter/                    # — HINDI LILIPAT
│   │   ├── chunking.py
│   │   ├── formatter.py
│   │   └── json_helper.py
│   │
│   └── shared/                       # from utils/ (except config, constants, errors, postgres_pool)
│       ├── logging/
│       │   ├── clean_logger.py
│       │   ├── safe_logger.py
│       │   └── simple_clean_logging.py
│       ├── retry_helper.py
│       ├── llm_helper.py
│       ├── gemini_helper.py
│       ├── openrouter_helper.py
│       ├── llm_factory.py
│       ├── file_validator.py
│       ├── season_detector.py
│       ├── user_friendly_errors.py
│       ├── langfuse_utils.py
│       ├── limiter_config.py
│       └── postgres_pool.py           # or put under infrastructure/postgres/
│
├── main.py                           # — ROOT, huwag ilipat
├── gunicorn_config.py
├── Dockerfile
├── docker-compose.yml
├── pyproject.toml
├── uv.lock
├── requirements.txt
├── pytest.ini
├── README.md
├── FOLDER_STRUCTURE.md
├── FILE_PLACEMENT_GUIDE.md           # (ito)
└── .gitignore
```

---

## 2. Talaan: Current File → Ilalagay Dito

### 2.1 API layer (routers + deps)

| Current path | Ilalagay dito |
|--------------|----------------|
| `src/deps/security.py` | `src/api/deps/security.py` |
| `src/deps/user_context.py` | `src/api/deps/user_context.py` |
| `src/deps/cooperative_context.py` | `src/api/deps/cooperative_context.py` |
| `src/router/agent.py` | `src/api/routes/agent.py` |
| `src/router/upload.py` | `src/api/routes/upload.py` |
| `src/router/search.py` | `src/api/routes/search.py` |
| `src/router/storage.py` | `src/api/routes/storage.py` |
| `src/router/list.py` | `src/api/routes/list.py` |
| `src/router/progress.py` | `src/api/routes/progress.py` |
| `src/router/cache.py` | `src/api/routes/cache.py` |
| `src/router/worker.py` | `src/api/routes/worker.py` |
| `src/router/delete_extract.py` | `src/api/routes/delete_extract.py` |
| `src/chatbot/chat/chat_router.py` | `src/api/routes/chat_router.py` *(optional; pwede ring iwan sa chatbot/chat/)* |

### 2.2 Core (config, constants, errors)

| Current path | Ilalagay dito |
|--------------|----------------|
| `src/utils/config.py` | `src/core/config.py` |
| `src/utils/constants.py` | `src/core/constants.py` |
| `src/utils/errors.py` | `src/core/errors.py` |

### 2.3 Agents (CrewAI) — rename folder `Agents` → `agents`

| Current path | Ilalagay dito |
|--------------|----------------|
| `src/Agents/evaluation_crew.py` | `src/agents/evaluation_crew.py` |
| `src/Agents/output_evaluator.py` | `src/agents/output_evaluator.py` |

*Note: Gumawa ng bagong folder `src/agents/` (lowercase), lipat files, tapos burahin `src/Agents/`.*

### 2.4 Workflow — HINDI LILIPAT

| Current path | Action |
|--------------|--------|
| `src/workflow/*` | **Stay as-is.** Huwag ilipat. |

### 2.5 Chatbot — HINDI LILIPAT

| Current path | Action |
|--------------|--------|
| `src/chatbot/*` | **Stay as-is.** Huwag ilipat. (Kung ililipat mo chat_router sa api/routes, optional lang.) |

### 2.6 Ingestion — rename folder `Upload` → `ingestion`

| Current path | Ilalagay dito |
|--------------|----------------|
| `src/Upload/multiple_handler.py` | `src/ingestion/multiple_handler.py` |
| `src/Upload/form_extractor.py` | `src/ingestion/form_extractor.py` |
| `src/Upload/file_validator.py` | `src/ingestion/file_validator.py` |

*Note: May laman na ang `src/ingestion/` (__init__.py lang). Ilagay ang 3 files dito, tapos burahin `src/Upload/`.*

### 2.7 Infrastructure — vector_store (from database)

| Current path | Ilalagay dito |
|--------------|----------------|
| `src/database/analysis_dense_retriever.py` | `src/infrastructure/vector_store/analysis_dense_retriever.py` |
| `src/database/analysis_search.py` | `src/infrastructure/vector_store/analysis_search.py` |
| `src/database/collection.py` | `src/infrastructure/vector_store/collection.py` |
| `src/database/delete.py` | `src/infrastructure/vector_store/delete.py` |
| `src/database/dense_retriever.py` | `src/infrastructure/vector_store/dense_retriever.py` |
| `src/database/hybrid_search.py` | `src/infrastructure/vector_store/hybrid_search.py` |
| `src/database/insert_analysis.py` | `src/infrastructure/vector_store/insert_analysis.py` |
| `src/database/insert.py` | `src/infrastructure/vector_store/insert.py` |
| `src/database/list_reports.py` | `src/infrastructure/vector_store/list_reports.py` |
| `src/database/score_utils.py` | `src/infrastructure/vector_store/score_utils.py` |
| `src/database/sparse_retriever.py` | `src/infrastructure/vector_store/sparse_retriever.py` |
| `src/database/postgres_memory_schema.py` | `src/infrastructure/postgres/postgres_memory_schema.py` *(or vector_store kung mas gusto mo)* |

### 2.8 Infrastructure — embeddings (from generator)

| Current path | Ilalagay dito |
|--------------|----------------|
| `src/generator/embedding.py` | `src/infrastructure/embeddings/embedding.py` |
| `src/generator/encoder.py` | `src/infrastructure/embeddings/encoder.py` |
| `src/generator/model_loader.py` | `src/infrastructure/embeddings/model_loader.py` |
| `src/generator/qdrant_load.py` | `src/infrastructure/embeddings/qdrant_load.py` |

### 2.9 Infrastructure — redis

| Current path | Ilalagay dito |
|--------------|----------------|
| `src/generator/redis_pool.py` | `src/infrastructure/redis/redis_pool.py` |

### 2.10 Infrastructure — postgres

| Current path | Ilalagay dito |
|--------------|----------------|
| `src/utils/postgres_pool.py` | `src/infrastructure/postgres/postgres_pool.py` |

### 2.11 Services — HINDI LILIPAT

| Current path | Action |
|--------------|--------|
| `src/services/cache_service.py` | **Stay as-is.** |
| `src/services/storage_service.py` | **Stay as-is.** |

### 2.12 Monitoring — HINDI LILIPAT

| Current path | Action |
|--------------|--------|
| `src/monitoring/*` | **Stay as-is.** |

### 2.13 Workers — HINDI LILIPAT

| Current path | Action |
|--------------|--------|
| `src/workers/workers.py` | **Stay as-is.** |

### 2.14 Prompts (workflow) — rename folder `prompt` → `prompts`

| Current path | Ilalagay dito |
|--------------|----------------|
| `src/prompt/analysis_template.py` | `src/prompts/analysis_template.py` |
| `src/prompt/graph_suggestion_template.py` | `src/prompts/graph_suggestion_template.py` |
| `src/prompt/prompt_helper.py` | `src/prompts/prompt_helper.py` |
| `src/prompt/prompt_template.py` | `src/prompts/prompt_template.py` |

*Note: May `src/prompts/` na (__init__.py lang). Ilagay ang 4 files dito, tapos burahin `src/prompt/`.*

### 2.15 Formatter — HINDI LILIPAT

| Current path | Action |
|--------------|--------|
| `src/formatter/*` | **Stay as-is.** |

### 2.16 Shared (from utils — except core at postgres_pool)

| Current path | Ilalagay dito |
|--------------|----------------|
| `src/utils/clean_logger.py` | `src/shared/logging/clean_logger.py` |
| `src/utils/safe_logger.py` | `src/shared/logging/safe_logger.py` |
| `src/utils/simple_clean_logging.py` | `src/shared/logging/simple_clean_logging.py` |
| `src/utils/retry_helper.py` | `src/shared/retry_helper.py` |
| `src/utils/llm_helper.py` | `src/shared/llm_helper.py` |
| `src/utils/gemini_helper.py` | `src/shared/gemini_helper.py` |
| `src/utils/openrouter_helper.py` | `src/shared/openrouter_helper.py` |
| `src/utils/llm_factory.py` | `src/shared/llm_factory.py` |
| `src/utils/file_validator.py` | `src/shared/file_validator.py` |
| `src/utils/season_detector.py` | `src/shared/season_detector.py` |
| `src/utils/user_friendly_errors.py` | `src/shared/user_friendly_errors.py` |
| `src/utils/langfuse_utils.py` | `src/shared/langfuse_utils.py` |
| `src/utils/limiter_config.py` | `src/shared/limiter_config.py` |

*Note: `config.py`, `constants.py`, `errors.py` → core/. `postgres_pool.py` → infrastructure/postgres/.*

---

## 3. Root-level files (optional lipat)

| Current path | Optional ilalagay dito |
|--------------|------------------------|
| `env.example` | `config/env.example` |
| `deploymentenv.txt` | `config/deploymentenv.txt` |
| `PROJECT_ANALYSIS_AND_CODE_MAP.md` | `docs/PROJECT_ANALYSIS_AND_CODE_MAP.md` |
| `WORKFLOW_DOCUMENTATION.md` | `docs/WORKFLOW_DOCUMENTATION.md` |
| `FOLDER_STRUCTURE.md` | `docs/FOLDER_STRUCTURE.md` |
| `setup_postgres_memory.py` | `scripts/setup_postgres_memory.py` |
| `start_docker.bat` | `scripts/start_docker.bat` |
| `start_docker.sh` | `scripts/start_docker.sh` |
| `start_production.bat` | `scripts/start_production.sh` |
| `start_production.sh` | `scripts/start_production.sh` |

*Kung ililipat mo ang docs/scripts/config, i-update ang README at mga path kung may reference.*

---

## 4. Tests

| Current path | Optional ilalagay dito |
|--------------|------------------------|
| `test/conftest.py` | `tests/conftest.py` (or `tests/unit/conftest.py`) |
| `test/test_chatbot/*` | `tests/unit/test_chatbot/*` |
| `test/test_simple.py` | `tests/unit/test_simple.py` |

*Pagkatapos mag-lipat, i-update ang `pytest.ini` at imports.*

---

## 5. Mga folder na HINDI LILIPAT (stay as-is)

- `src/workflow/`
- `src/chatbot/`
- `src/services/`
- `src/monitoring/`
- `src/workers/`
- `src/formatter/`
- `data/`, `actual_data/`
- `docker/`
- Root: `main.py`, `Dockerfile`, `docker-compose.yml`, `pyproject.toml`, `README.md`, `gunicorn_config.py`, etc.

---

## 6. Paalala pagkatapos mag-transfer

1. **Imports:** Lahat ng `from src.xxx` ay dapat i-update sa bagong path (e.g. `from src.deps.security` → `from src.api.deps.security`, `from src.utils.config` → `from src.core.config`).
2. **main.py:** I-update ang router includes at anumang import mula sa router/deps/utils/database/generator/Upload/prompt/Agents.
3. **pytest:** Kung nilipat ang tests, i-update ang `pytest.ini` at `conftest.py` paths.
4. **Run tests:** `uv run pytest` bago at pagkatapos ng bawat batch ng lipat.

Kung gusto mo, pwede mong gawin unang batch: **agents**, **ingestion**, **prompts** (rename + move), tapos **api** (deps + routes), tapos **core**, tapos **infrastructure**, tapos **shared**. Good luck sa pag-transfer.
