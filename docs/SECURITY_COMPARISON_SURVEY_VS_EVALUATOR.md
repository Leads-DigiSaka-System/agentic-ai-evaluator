# Security Comparison: agentic-ai-survey vs agentic-ai-evaluator

Comparison of production security measures in **agentic-ai-survey** vs **agentic-ai-evaluator**, and what is missing in the evaluator.

---

## 1. API Key Authentication

| Feature | agentic-ai-survey | agentic-ai-evaluator |
|--------|--------------------|------------------------|
| **Single API key** | ✅ `API_KEY` | ✅ `API_KEY` |
| **Multiple API keys** | ✅ `API_KEYS` (comma-separated), validated against list | ❌ Single key only |
| **Header** | ✅ `X-API-Key` | ✅ `X-API-Key` |
| **Development bypass** | ✅ When no keys configured + `ENVIRONMENT=development`, returns `"development-bypass"` | ❌ 500 if `API_KEY` not set |
| **Config source** | `src/shared/utils/config.py` → `API_KEYS` | `src/core/config.py` → `os.getenv("API_KEY")` |

**Missing in evaluator:**
- **Multiple API keys** (`API_KEYS`): support comma-separated keys for different clients/deployments.
- **Development bypass**: when `ENVIRONMENT=development` and no API keys configured, allow requests instead of 500.

---

## 2. CORS

| Feature | agentic-ai-survey | agentic-ai-evaluator |
|--------|--------------------|------------------------|
| **Config** | `ALLOWED_ORIGINS` from env (comma-separated) | `CONNECTION_WEB` from env (comma-separated) → used as list |
| **Production vs dev** | ✅ **Production**: `allow_origins=ALLOWED_ORIGINS`. **Non-production**: `allow_origins=["*"]` | ❌ Same list for all environments (`CONNECTION_WEB`) |
| **ENVIRONMENT** | ✅ `ENVIRONMENT` (development / staging / production) | ❌ Not used |

**Missing in evaluator:**
- **ENVIRONMENT** variable (e.g. `development`, `staging`, `production`).
- **CORS by environment**: in production restrict to `ALLOWED_ORIGINS` / `CORS_ORIGINS`; in development allow `["*"]` if desired.

---

## 3. Rate Limiting

| Feature | agentic-ai-survey | agentic-ai-evaluator |
|--------|--------------------|------------------------|
| **Library** | SlowAPI | SlowAPI |
| **Toggle** | ✅ `RATE_LIMIT_ENABLED` (env) — can disable for tests | ❌ Always on (no env toggle) |
| **Per-endpoint** | ✅ `@rate_limit("5/hour")` etc. on expensive endpoints | ✅ `@limiter.limit("10/minute")` etc. on routes |
| **Storage** | `memory://` or configurable | In-memory (limiter from `limiter_config`) |
| **Expensive endpoints** | e.g. upload `20/hour`, extractor `20/hour`, insight `10/hour`, chat `10/minute` | e.g. agent `10/minute`, chat `10/minute`, search `60/minute` |

**Missing in evaluator:**
- **RATE_LIMIT_ENABLED** (or similar) env toggle to disable rate limiting (e.g. for local/testing).

---

## 4. Qdrant API Key (Security)

| Feature | agentic-ai-survey | agentic-ai-evaluator |
|--------|--------------------|------------------------|
| **Use API key only over HTTPS** | ✅ `_use_api_key = QDRANT_API_KEY and url.startswith("https://")` | ✅ `QDRANT_USE_API_KEY` (only when URL is HTTPS) |

**Status:** ✅ Aligned (evaluator already uses API key only over HTTPS).

---

## 5. Input Validation / Sanitization

| Feature | agentic-ai-survey | agentic-ai-evaluator |
|--------|--------------------|------------------------|
| **File upload** | Validation in upload flow | ✅ `FileValidator` (path traversal, dangerous chars, size, MIME) |
| **String/body validation** | ✅ `validation.py`: `sanitize_string`, `validate_message`, path traversal prevention, length limits | ❌ No shared sanitize_string / validate_message for JSON body or query params |
| **Custom ValidationError** | ✅ Raised and handled globally | ✅ Exists in `src.core.errors`; usage more limited |

**Missing in evaluator:**
- **Centralized request/body validation**: e.g. `sanitize_string`, `validate_message`, max length, control-char stripping for chat message, search query, etc. (similar to survey’s `validation.py`).

---

## 6. Health Check (Information Disclosure)

| Feature | agentic-ai-survey | agentic-ai-evaluator |
|--------|--------------------|------------------------|
| **Error message in response** | ✅ **Production**: `error_msg = "Connection failed"` (no `str(e)`). **Non-production**: full `str(e)` | ❌ Always returns full `str(e)` in health checks |

**Missing in evaluator:**
- **Production**: do not expose full exception message in `/api/health` (and similar); return generic message (e.g. `"Connection failed"`) when `ENVIRONMENT=production`.

---

## 7. Config / Environment

| Feature | agentic-ai-survey | agentic-ai-evaluator |
|--------|--------------------|------------------------|
| **ENVIRONMENT** | ✅ `development` / `staging` / `production` | ❌ Not defined |
| **DEBUG / RELOAD / WORKERS / LOG_LEVEL** | ✅ Driven by ENVIRONMENT and env | Partially (e.g. LOG_LEVEL, no global ENVIRONMENT) |
| **CORS origins** | `ALLOWED_ORIGINS` | `CORS_ORIGINS` in constants, `CONNECTION_WEB` in config for app |

**Missing in evaluator:**
- **ENVIRONMENT** (e.g. from `ENVIRONMENT` env) and use it for CORS, health check masking, and optional API key bypass in development.

---

## 8. Summary: What to Add in agentic-ai-evaluator for Production

1. **API keys**
   - Support **multiple API keys** via `API_KEYS` (comma-separated) and validate against list in `require_api_key`.
   - Optional: in **development**, if no API keys are set, allow requests (bypass) instead of 500.

2. **ENVIRONMENT**
   - Add **ENVIRONMENT** (e.g. `development`, `staging`, `production`) and use it in:
     - CORS (production: restrict to allowed origins; dev: optionally `["*"]`).
     - Health check (production: hide detailed errors).
     - Optional: rate limit or API key bypass in dev.

3. **CORS**
   - Use **ENVIRONMENT**: production → strict `ALLOWED_ORIGINS` / `CORS_ORIGINS`; non-production → allow all or same list as now.

4. **Rate limiting**
   - Add **RATE_LIMIT_ENABLED** (or similar) so rate limiting can be turned off (e.g. for tests or local dev).

5. **Health check**
   - In **production**, do not return raw `str(e)` in `/api/health` (and `/api/qdrant/check` if exposed); return generic messages.

6. **Input validation**
   - Add **shared validation** (e.g. `sanitize_string`, `validate_message`, length limits) for request body/query and use it in chat, search, and other endpoints.

7. **Health check Qdrant client**
   - In `main.py` health check (and qdrant check), use **QDRANT_USE_API_KEY** instead of `QDRANT_API_KEY` when building `QdrantClient`, so behavior matches the rest of the app (no API key over HTTP).

---

## Files to Reference (survey)

- `src/deps/api_key.py` — multiple keys, development bypass.
- `src/shared/utils/config.py` — `API_KEYS`, `ENVIRONMENT`, `ALLOWED_ORIGINS`, `RATE_LIMIT_ENABLED`.
- `src/shared/utils/rate_limit.py` — `set_limiter`, `get_limiter`, `@rate_limit(limit)`.
- `src/shared/utils/validation.py` — `sanitize_string`, `validate_message`, path safety.
- `main.py` — CORS by ENVIRONMENT, rate limiter conditional on RATE_LIMIT_ENABLED, health check error masking.
