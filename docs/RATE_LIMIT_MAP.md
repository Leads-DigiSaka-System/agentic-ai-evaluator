# Rate Limiting Map — agentic-ai-evaluator

Full project map: where rate limiting is applied today and where it should be applied for Phase 4.

---

## 1. Current setup

- **Library:** SlowAPI  
- **Config:** `src/shared/limiter_config.py` — single `Limiter(key_func=get_remote_address)`  
- **Main:** `app.state.limiter = limiter`, `app.add_exception_handler(RateLimitExceeded, ...)`, `app.add_middleware(SlowAPIMiddleware)`  
- **Phase 4:** Add `RATE_LIMIT_ENABLED` in config; only add exception handler + middleware when enabled.

---

## 2. Endpoints with rate limit (current)

| Router        | Method | Path                     | Current limit   | Cost / use case        |
|---------------|--------|--------------------------|-----------------|-------------------------|
| **chat_router** | POST   | `` (chat)               | 30/minute       | Expensive (LLM)        |
| **chat_router** | GET    | /history                | 60/minute       | Simple read            |
| **chat_router** | GET    | /stats                  | 60/minute       | Simple read            |
| **chat_router** | POST   | /reset                  | 10/minute       | Normal                 |
| **chat_router** | DELETE | /cache                  | 10/minute       | Normal / destructive   |
| **agent**       | POST   | /agent                  | 10/minute       | Expensive (workflow)   |
| **search**      | POST   | /analysis-search        | 60/minute       | Normal (vector search) |
| **storage**     | POST   | /storage/approve-simple | 10/minute       | Normal                 |

**Note:** SlowAPI needs `request: Request` in the endpoint signature for `@limiter.limit()` to work. All of the above already have `request: Request` where the decorator is used.

---

## 3. Endpoints without rate limit (should have)

### 3.1 Upload (expensive — file + processing)

| Method | Path                         | File / line              | Recommendation   | Reason                    |
|--------|------------------------------|---------------------------|------------------|---------------------------|
| POST   | /api/upload-file-product-demo | `src/api/routes/upload.py` | **20/hour**      | File + extraction; heavy |

- **Add:** `@limiter.limit("20/hour")` and `request: Request` in the handler.

### 3.2 Progress (normal read)

| Method | Path              | File / line               | Recommendation | Reason           |
|--------|-------------------|----------------------------|----------------|------------------|
| GET    | /api/progress/{job_id} | `src/api/routes/progress.py` | **60/minute**  | Polling / read   |

- **Add:** `@limiter.limit("60/minute")` and `request: Request`.

### 3.3 List / reports (simple read)

| Method | Path               | File / line            | Recommendation | Reason    |
|--------|--------------------|-------------------------|----------------|-----------|
| GET    | /api/reports/list  | `src/api/routes/list.py` | **60/minute**  | List read |
| GET    | /api/reports/stats | `src/api/routes/list.py` | **60/minute**  | Stats read|

- **Add:** `@limiter.limit("60/minute")` and `request: Request` on both.

### 3.4 Cache (admin / debug — normal to strict)

| Method | Path               | File / line             | Recommendation | Reason              |
|--------|--------------------|--------------------------|----------------|---------------------|
| POST   | /api/cache/cleanup | `src/api/routes/cache.py` | **10/minute**  | Manual cleanup      |
| DELETE | /api/cache/clear-all | `src/api/routes/cache.py` | **5/minute**   | Destructive; strict |
| GET    | /api/cache/stats   | `src/api/routes/cache.py` | **60/minute**  | Read                |
| GET    | /api/cache/memory  | `src/api/routes/cache.py` | **30/minute**  | Read                |
| GET    | /api/cache/{cache_id} | `src/api/routes/cache.py` | **60/minute**  | Read                |
| DELETE | /api/cache/{cache_id} | `src/api/routes/cache.py` | **10/minute**  | Destructive         |

- **Add:** corresponding `@limiter.limit(...)` and `request: Request` on each.

### 3.5 Worker (admin / monitoring)

| Method | Path               | File / line              | Recommendation | Reason     |
|--------|--------------------|---------------------------|----------------|------------|
| GET    | /api/worker/health | `src/api/routes/worker.py` | **30/minute**  | Health     |
| GET    | /api/worker/metrics| `src/api/routes/worker.py` | **30/minute**  | Metrics    |
| GET    | /api/worker/jobs   | `src/api/routes/worker.py` | **30/minute**  | Job list   |

- **Add:** `@limiter.limit("30/minute")` and `request: Request` on each.

### 3.6 Delete (destructive — strict)

| Method | Path                    | File / line                  | Recommendation | Reason        |
|--------|-------------------------|------------------------------|----------------|---------------|
| DELETE | /api/delete/{form_id}   | `src/api/routes/delete_extract.py` | **10/minute**  | Single delete |
| DELETE | /api/delete-all/{collection_name} | `src/api/routes/delete_extract.py` | **5/minute**   | Full collection |

- **Add:** `@limiter.limit("10/minute")` and `@limiter.limit("5/minute")` respectively, and `request: Request`.

### 3.7 Chat (no limit today)

| Method | Path        | File / line            | Recommendation | Reason   |
|--------|-------------|-------------------------|----------------|----------|
| GET    | /chat/health| `src/api/routes/chat_router.py` | **60/minute**  | Health  |

- **Add:** `@limiter.limit("60/minute")` and `request: Request` if you want to cap health checks.

---

## 4. Endpoints that can stay unlimited (optional)

- **main.py:** `GET /`, `GET /api/health` — often left unlimited for load balancers and monitoring.  
- **main.py:** `GET /api/qdrant/check` — debug; can add **30/minute** if exposed.

---

## 5. Recommended limits by category (for Phase 4)

| Category        | Limit         | Use case                          |
|-----------------|---------------|-----------------------------------|
| **Expensive**   | 5–20/hour     | Upload, heavy workflow (e.g. agent) |
| **Expensive**   | 10/minute     | Chat, agent POST, reset, storage  |
| **Normal**      | 30/minute     | Search, progress, worker, cache memory |
| **Simple read** | 60/minute     | History, stats, list, reports, cache stats, cache/{id} |
| **Destructive** | 5–10/minute   | Delete, cache clear-all, cache cleanup |

---

## 6. Summary: where to apply rate limiting

### Already limited (keep as-is for Phase 4)

- `chat_router`: POST `` (30/min), GET /history (60/min), GET /stats (60/min), POST /reset (10/min), DELETE /cache (10/min)  
- `agent`: POST /agent (10/min)  
- `search`: POST /analysis-search (60/min)  
- `storage`: POST /storage/approve-simple (10/min)  

### Add limit (and `request: Request` where missing)

1. **upload.py** — POST /upload-file-product-demo → **20/hour**  
2. **progress.py** — GET /progress/{job_id} → **60/minute**  
3. **list.py** — GET /list, GET /stats → **60/minute** each  
4. **cache.py** — cleanup **10/min**, clear-all **5/min**, stats **60/min**, memory **30/min**, get status **60/min**, delete by id **10/min**  
5. **worker.py** — GET /worker/health, /worker/metrics, /worker/jobs → **30/minute** each  
6. **delete_extract.py** — DELETE /delete/{form_id} **10/min**, DELETE /delete-all/{collection_name} **5/min**  
7. **chat_router** — GET /health (optional) → **60/minute**  

### No change (optional to limit later)

- main.py: `/`, `/api/health`, `/api/qdrant/check`  

---

## 7. Phase 4 implementation order

1. Add **RATE_LIMIT_ENABLED** and conditional middleware/handler in **main.py** (see SECURITY_IMPLEMENTATION_GUIDE Phase 4).  
2. Optionally add limits to the “Add limit” list above (upload, progress, list, cache, worker, delete, chat health).  
3. For each new limit: ensure the route has `request: Request` and add `@limiter.limit("X/minute")` (or `"X/hour"`) **above** the route decorator, and that `limiter` is imported from `src.shared.limiter_config`.

This document is the single source of truth for **where** rate limiting is and should be applied in the project.
