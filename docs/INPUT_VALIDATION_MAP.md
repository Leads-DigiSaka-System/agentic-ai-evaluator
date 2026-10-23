# Input Validation Map — agentic-ai-evaluator

Analysis of all user-controlled inputs and where limits/validation are needed so the system is protected from abuse and oversized input.

---

## 1. Summary

| Area | Input | Current state | Action (Phase 6+) |
|------|--------|----------------|--------------------|
| **Chat** | `message` (body) | ✅ Pydantic: min_length=1, max_length=5000, validator | Optional: use shared `validate_message` for consistency |
| **Chat** | `session_id` (body/query) | ⚠️ No max length | Optional: max 200 chars |
| **Search** | `query` (body) | ❌ No min/max length | **Required:** add `validate_search_query` (max 500, min 1) |
| **Search** | `top_k` (body) | ✅ Validated 1–MAX_SEARCH_TOP_K | — |
| **Upload / Agent** | `file` | ✅ file_validator: type, size (MAX_FILE_SIZE_MB), filename | — |
| **Delete** | `form_id` (path) | ⚠️ No max length | Optional: max 200 chars |
| **Delete** | `collection_name` (path) | ⚠️ No max length | Optional: max 200 chars |
| **Cache** | `cache_id` (path) | ⚠️ No max length | Optional: max 200 chars |
| **Storage** | `cache_id`, `approved` (body) | ⚠️ cache_id no max length | Optional: cache_id max 200 |
| **Headers** | X-Cooperative, X-User-ID | ⚠️ Not empty only | Optional: max 200 chars |
| **Chat history/stats** | `session_id` (query), `limit` (query) | ✅ limit 1–100 | Optional: session_id max 200 |
| **Agent** | `priority` (query) | ⚠️ Raw from query_params | Optional: validate enum (high/normal/low) |

---

## 2. Phase 6 (required for “limit per input”)

1. **Create `src/shared/validation.py`**
   - `sanitize_string()` — trim, control chars, min/max length.
   - `validate_message(message, max_length=5000, min_length=1)` — for chat.
   - `validate_search_query(query, max_length=500, min_length=1)` — for search.

2. **Search route (`src/api/routes/search.py`)**
   - **Must add:** validate `body.query` with `validate_search_query()` (or add Pydantic `min_length=1`, `max_length=500` and optionally call shared validator). Right now `query` has no length limit.

3. **Chat route (`src/api/routes/chat_router.py`)**
   - Already has Pydantic limits. Optionally call shared `validate_message()` for consistency and single place to tune limits.

4. **Global handler in `main.py`**
   - **Must add:** `@app.exception_handler(ValidationError)` → return 400 with `detail` so all validation errors respond consistently.

5. **`src.core.errors.ValidationError`**
   - Already exists and is used by file_validator and others.

---

## 3. Optional hardening (after Phase 6)

- **Path params:** `form_id`, `collection_name`, `cache_id` — reject or truncate if length > 200 (or 256).
- **Headers:** `X-Cooperative`, `X-User-ID` — max length 200 in deps (cooperative_context, user_context).
- **Body:** `SimpleStorageApprovalRequest.cache_id` — Pydantic `Field(..., max_length=200)`.
- **Query:** `session_id` in chat history/stats — max length 200.
- **Agent:** `priority` — allow only `high` | `normal` | `low` (from constants).

---

## 4. Already protected

- **Chat message:** Pydantic + validator (1–5000 chars).
- **File upload:** `src/shared/file_validator.py` + `MAX_FILE_SIZE_MB` in constants.
- **Search top_k:** Pydantic validator (1–MAX_SEARCH_TOP_K).
- **Chat history limit:** Query(50, ge=1, le=100).
- **Delete confirm:** Must pass `confirm=true` for delete-all.

---

## 5. Checklist for Phase 6

- [x] `src/shared/validation.py` with `sanitize_string`, `validate_message`, `validate_search_query`, `validate_id`, `validate_session_id`, `validate_header_value`.
- [x] Search route: validate `query` (max 500, min 1) via `validate_search_query`.
- [x] Chat route: use `validate_message` for consistency.
- [x] `main.py`: global `ValidationError` exception handler → 400.
- [x] (Optional) Path params: `form_id`, `collection_name`, `cache_id` max 200 via `validate_id`.
- [x] (Optional) Headers: X-Cooperative, X-User-ID max 200 via `validate_header_value`.
- [x] (Optional) `SimpleStorageApprovalRequest.cache_id` max 200 (Pydantic Field).
- [x] (Optional) Chat: `session_id` max 200 (ChatRequest Field + validate_id/validate_session_id in history, stats, reset, clear cache).
- [x] (Optional) Agent: `priority` enum (high | normal | low).
