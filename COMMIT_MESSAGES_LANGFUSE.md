# Tatlong commit: Implementation → Test → Demo

Basahin mula **Commit 1** hanggang **Commit 3**. Bawat commit may sariling files to stage at commit message.

---

## Commit 1 — Implementation / Refactor

**Files to stage:**

- `src/api/routes/agent.py`
- `src/api/routes/progress.py`
- `src/api/routes/search.py`
- `src/api/routes/storage.py`
- `src/api/routes/upload.py`
- `src/api/routes/chat_router.py`
- `src/monitoring/scores/search_score.py`
- `src/monitoring/scores/storage_score.py`
- `src/monitoring/scores/workflow_score.py`
- `src/monitoring/session/langfuse_session_helper.py`
- `src/monitoring/trace/langfuse_helper.py`
- `src/shared/score_helper.py`
- `src/workers/workers.py`

**Commit message:**

```
refactor(langfuse): Sessions/Users propagation, scores, at helpers

Implementation at refactor para sa Langfuse: Sessions/Users sa dashboard,
score logging, at shared helpers.

- langfuse_session_helper: generate_session_id, propagate_session_id,
  truncate 200 chars; warning kung wala ang propagate_attributes (Langfuse v3).
- langfuse_helper: init, get_client, update_current_trace, score APIs
  (create_score, score_current_trace, get_current_trace_id), flush/shutdown,
  LangChain callback; deprecation notes para sa langfuse_utils.
- score_helper: re-export ng create_score, score_current_trace,
  get_current_trace_id mula langfuse_helper (single place para sa score APIs).
- monitoring/scores: search_score, storage_score, workflow_score — naglo-log
  ng scores sa Langfuse trace (relevance, data_quality, significance, etc.).
- Routes (chat_router, agent, progress, search, storage, upload): sa simula
  ng request tawag update_current_trace(user_id=..., session_id=..., tags=...);
  handler naka-balot sa with propagate_session_id(session_id, user_id=...)
  para ma-inherit ng lahat ng observations ang session_id at user_id.
- workers: Langfuse tracing sa worker tasks.

Sessions at Users tabs sa Langfuse kailangan ng trace-level user_id/session_id
at propagation sa child observations; ito ang in-apply sa lahat ng routes at worker.
```

---

## Commit 2 — Test

**Files to stage:**

- `tests/unit/conftest.py`
- `tests/unit/test_langfuse_sessions_users.py`
- `tests/unit/test_langfuse_implementation.py`
- `tests/unit/test_langfuse_session_helper.py`
- `tests/unit/test_langfuse_helper.py`
- `tests/unit/test_langfuse_scores.py`
- `tests/unit/test_langfuse_utils.py`
- `tests/unit/test_langfuse_tracing.py`
- `tests/unit/test_langfuse_routes.py`
- `tests/unit/test_langfuse_worker.py`
- `tests/unit/test_llm_helper_langfuse.py`
- `tests/unit/test_chat_agent.py`
- `tests/unit/test_conversation_store.py`
- `tests/unit/test_postgres_memory.py`
- `tests/unit/test_score_helper.py`

**Commit message:**

```
test(langfuse): unit tests, mocks, at contract tests para sa Langfuse

- conftest: module-level mocks (psycopg2, arq, langfuse get_client/observe/
  propagate_attributes, langchain_google_genai, postgres_pool, llm_helper)
  para tumakbo ang unit tests nang offline, walang real DB/Redis/Langfuse/HuggingFace.
- test_langfuse_sessions_users: contract tests — nag-verify na ang chat, search,
  upload route source ay may update_current_trace(..., user_id=..., session_id=...)
  at with propagate_session_id(session_id, user_id=...); mock fixtures lang.
- test_langfuse_implementation: LANGFUSE_TOUCHPOINTS at tests na nag-check
  na langfuse_helper, langfuse_session_helper, at routes/worker ay gumagamit
  ng propagate_session_id at update_current_trace; config exports LANGFUSE_*.
- test_langfuse_session_helper, test_langfuse_helper, test_langfuse_scores,
  test_langfuse_utils, test_langfuse_routes, test_langfuse_worker,
  test_llm_helper_langfuse, test_score_helper: unit tests para sa helpers,
  scores, at integration points.
- test_langfuse_tracing: tracing at span behavior (live test nasa Commit 3).
- test_chat_agent: fix langchain.memory package stub (LangChain 0.3) at mock
  analysis_search para walang HuggingFace load.
- test_conversation_store: patch target sa langfuse_session_helper.generate_session_id.
- test_postgres_memory: stub ConversationBufferMemory chat_memory at fix
  test_load_respects_max_messages_limit (LIMIT query assertion).
```

---

## Commit 3 — Demo

**Files to stage:**

- `scripts/seed_langfuse_demo.py`

**Commit message:**

```
chore(langfuse): demo seed script para sa Sessions/Users sa dashboard

- scripts/seed_langfuse_demo.py: nag-load ng .env, nag-init ng Langfuse,
  gumawa ng isang span na may update_current_trace(user_id="demo_user",
  session_id="demo_session", tags=["demo","seed","script"]), flush;
  nag-print ng trace ID, URL, user_id, session_id.
- Para makita sa Langfuse dashboard ang Sessions at Users: run
  uv run python scripts/seed_langfuse_demo.py (kailangan LANGFUSE_PUBLIC_KEY,
  LANGFUSE_SECRET_KEY sa .env). One-off demo o pag-verify nang walang buong API.
- Live test (test_live_trace_appears_in_langfuse_dashboard sa
  test_langfuse_tracing.py) nag-send din ng user_id/session_id sa trace;
  run: uv run pytest tests/unit/test_langfuse_tracing.py -v -m langfuse_live.
```

---

**Order ng commit:** 1 (implementation) → 2 (test) → 3 (demo).
