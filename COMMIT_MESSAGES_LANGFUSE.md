# Three commits: Implementation → Test → Demo

Read from **Commit 1** through **Commit 3**. Each commit has its own files to stage and commit message.

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
refactor(langfuse): Sessions/Users propagation, scores, and helpers

Implementation and refactor for Langfuse: Sessions/Users on dashboard,
score logging, and shared helpers.

- langfuse_session_helper: generate_session_id, propagate_session_id,
  truncate 200 chars; warning when propagate_attributes is unavailable (Langfuse v3).
- langfuse_helper: init, get_client, update_current_trace, score APIs
  (create_score, score_current_trace, get_current_trace_id), flush/shutdown,
  LangChain callback; deprecation notes for langfuse_utils.
- score_helper: re-export of create_score, score_current_trace,
  get_current_trace_id from langfuse_helper (single place for score APIs).
- monitoring/scores: search_score, storage_score, workflow_score — log
  scores to Langfuse trace (relevance, data_quality, significance, etc.).
- Routes (chat_router, agent, progress, search, storage, upload): at the
  start of each request call update_current_trace(user_id=..., session_id=..., tags=...);
  wrap handler in with propagate_session_id(session_id, user_id=...)
  so all observations inherit session_id and user_id.
- workers: Langfuse tracing in worker tasks.

Langfuse Sessions and Users tabs require trace-level user_id/session_id
and propagation to child observations; applied across all routes and worker.
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
test(langfuse): unit tests, mocks, and contract tests for Langfuse

- conftest: module-level mocks (psycopg2, arq, langfuse get_client/observe/
  propagate_attributes, langchain_google_genai, postgres_pool, llm_helper)
  so unit tests run offline without real DB/Redis/Langfuse/HuggingFace.
- test_langfuse_sessions_users: contract tests — verify that chat, search,
  upload route source has update_current_trace(..., user_id=..., session_id=...)
  and with propagate_session_id(session_id, user_id=...); mock fixtures only.
- test_langfuse_implementation: LANGFUSE_TOUCHPOINTS and tests that check
  langfuse_helper, langfuse_session_helper, and routes/worker use
  propagate_session_id and update_current_trace; config exports LANGFUSE_*.
- test_langfuse_session_helper, test_langfuse_helper, test_langfuse_scores,
  test_langfuse_utils, test_langfuse_routes, test_langfuse_worker,
  test_llm_helper_langfuse, test_score_helper: unit tests for helpers,
  scores, and integration points.
- test_langfuse_tracing: tracing and span behavior (live test in Commit 3).
- test_chat_agent: fix langchain.memory package stub (LangChain 0.3) and mock
  analysis_search to avoid HuggingFace load.
- test_conversation_store: patch target to langfuse_session_helper.generate_session_id.
- test_postgres_memory: stub ConversationBufferMemory chat_memory and fix
  test_load_respects_max_messages_limit (LIMIT query assertion).
```

---

## Commit 3 — Demo

**Files to stage:**

- `scripts/seed_langfuse_demo.py`

**Commit message:**

```
chore(langfuse): demo seed script for Sessions/Users on dashboard

- scripts/seed_langfuse_demo.py: loads .env, initializes Langfuse,
  creates one span with update_current_trace(user_id="demo_user",
  session_id="demo_session", tags=["demo","seed","script"]), flush;
  prints trace ID, URL, user_id, session_id.
- To see Sessions and Users in Langfuse dashboard: run
  uv run python scripts/seed_langfuse_demo.py (requires LANGFUSE_PUBLIC_KEY,
  LANGFUSE_SECRET_KEY in .env). One-off demo or verification without full API.
- Live test (test_live_trace_appears_in_langfuse_dashboard in
  test_langfuse_tracing.py) also sends user_id/session_id on trace;
  run: uv run pytest tests/unit/test_langfuse_tracing.py -v -m langfuse_live.
```

---

**Commit order:** 1 (implementation) → 2 (test) → 3 (demo).
