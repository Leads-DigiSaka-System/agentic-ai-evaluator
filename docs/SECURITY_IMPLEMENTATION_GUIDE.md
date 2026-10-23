# Security Implementation Guide — agentic-ai-evaluator

Phased implementation guide to close the security gaps vs agentic-ai-survey. Implement in order; each phase builds on the previous.

---

## Overview by Phase

| Phase | Scope | Est. time |
|-------|--------|------------|
| **Phase 1** | ENVIRONMENT + config (foundation) | ~15 min |
| **Phase 2** | Multiple API keys + dev bypass | ~20 min |
| **Phase 3** | CORS by environment | ~10 min |
| **Phase 4** | Rate limit toggle | ~15 min |
| **Phase 5** | Health check masking + Qdrant client fix | ~15 min |
| **Phase 6** | Input validation (shared) | ~30 min |

---

## Phase 1: ENVIRONMENT and config

**Goal:** Add `ENVIRONMENT` (development / staging / production) and CORS origins config so later phases can branch on it.

### 1.1 Add to `src/core/config.py`

**Location:** After `CONNECTION_WEB` / `CONNECTION_MOBILE` (around line 60).

```python
# Environment (development | staging | production)
ENVIRONMENT = os.getenv("ENVIRONMENT", "development").strip().lower()
if ENVIRONMENT not in ("development", "staging", "production"):
    ENVIRONMENT = "development"

# CORS: use same list as CONNECTION_WEB for allowed origins; production will restrict to this
CORS_ORIGINS_STR = os.getenv("CORS_ORIGINS") or os.getenv("CONNECTION_WEB", "http://localhost:3000,http://localhost:8501")
CORS_ORIGINS = [o.strip() for o in CORS_ORIGINS_STR.split(",") if o.strip()]
# Default if empty
if not CORS_ORIGINS:
    CORS_ORIGINS = ["http://localhost:3000", "http://localhost:8501"]
```

- Use `CORS_ORIGINS` in Phase 3 for production CORS.
- Use `ENVIRONMENT` in Phase 2 (API key), Phase 3 (CORS), Phase 5 (health masking).

### 1.2 Add to `config/env.example` (and `.env`)

```env
# Environment: development | staging | production
ENVIRONMENT=development

# CORS allowed origins (comma-separated). Used in production; dev can allow all via code.
CORS_ORIGINS=http://localhost:3000,http://localhost:8501
```

### 1.3 Checklist

- [ ] `ENVIRONMENT` in config, default `development`.
- [ ] `CORS_ORIGINS` in config (from env or fallback).
- [ ] `config/env.example` updated.

---

## Phase 2: Multiple API keys and development bypass

**Goal:** Support `API_KEYS` (comma-separated) and, in development only, allow requests when no keys are set.

### 2.1 Add to `src/core/config.py`

**Location:** Near top, after other API/env vars (or after `LANGFUSE_*`). Add:

```python
# API Key: single key (backward compatible)
API_KEY = os.getenv("API_KEY", "")

# Multiple API keys (comma-separated) for production; fallback to API_KEY if API_KEYS not set
_api_keys_raw = os.getenv("API_KEYS", API_KEY or "")
API_KEYS = [k.strip() for k in _api_keys_raw.split(",") if k.strip()] if _api_keys_raw else ([API_KEY] if API_KEY else [])
```

- Keep existing `API_KEY` usage elsewhere until security dependency is updated; then use `API_KEYS` in `require_api_key`.

### 2.2 Update `src/api/deps/security.py`

Replace the file with logic that uses `API_KEYS` and `ENVIRONMENT`:

```python
"""
API Key authentication for FastAPI.
Supports multiple API keys (API_KEYS) and optional development bypass when no keys are set.
"""
import logging
from typing import Optional

from fastapi import Security, HTTPException, status
from fastapi.security.api_key import APIKeyHeader

from src.core.config import API_KEYS, ENVIRONMENT

logger = logging.getLogger(__name__)

API_KEY_NAME = "X-API-Key"
api_key_header = APIKeyHeader(name=API_KEY_NAME, auto_error=False)


def require_api_key(api_key: Optional[str] = Security(api_key_header)) -> str:
    if not API_KEYS:
        if ENVIRONMENT == "development":
            logger.warning("API key validation disabled in development (no API keys configured)")
            return "development-bypass"
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Server API key not configured",
            headers={"WWW-Authenticate": "API key"},
        )

    if not api_key or not api_key.strip():
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing API key",
            headers={"WWW-Authenticate": "API key"},
        )

    key = api_key.strip()
    if key not in API_KEYS:
        logger.warning(f"Invalid API key attempted: {key[:10]}...")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing API key",
            headers={"WWW-Authenticate": "API key"},
        )
    return key
```

- Ensure `src.core.config` exposes `API_KEYS` and `ENVIRONMENT` (Phase 1).

### 2.3 Update `config/env.example`

```env
# Single key (backward compatible)
API_KEY=your-secure-api-key-here

# Optional: multiple keys (comma-separated) — if set, overrides single API_KEY for validation
# API_KEYS=key1,key2,key3
```

### 2.4 Checklist

- [ ] `API_KEYS` and `API_KEY` in config.
- [ ] `require_api_key` uses `API_KEYS` and allows dev bypass when no keys.
- [ ] Existing routers still use `Depends(require_api_key)`; no change needed in main.py.

---

## Phase 3: CORS by environment

**Goal:** In production, restrict CORS to `CORS_ORIGINS`; in non-production, allow all origins (or keep same list — choose one).

### 3.1 Update `main.py`

**Imports:** Use config for CORS and environment:

```python
from src.core.config import CONNECTION_WEB, CORS_ORIGINS, ENVIRONMENT
```

**CORS middleware:** Replace the current `CORSMiddleware` block with:

```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS if ENVIRONMENT == "production" else ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

- Production: strict `CORS_ORIGINS`.
- Non-production: `["*"]` (or use `CORS_ORIGINS` if you prefer no wildcard in dev).

### 3.2 Checklist

- [ ] `ENVIRONMENT` and `CORS_ORIGINS` from Phase 1.
- [ ] CORS uses `CORS_ORIGINS` in production and `["*"]` (or chosen list) otherwise.

---

## Phase 4: Rate limit toggle

**Goal:** Add `RATE_LIMIT_ENABLED` so rate limiting can be turned off (e.g. for tests or local dev).

### 4.1 Add to `src/core/config.py`

```python
# Rate limiting: set to false to disable (e.g. local dev or tests)
RATE_LIMIT_ENABLED = os.getenv("RATE_LIMIT_ENABLED", "true").strip().lower() == "true"
```

### 4.2 Add `src/shared/rate_limit.py` (optional decorator pattern like survey)

Create a small helper so routes can stay unchanged when limiter is disabled:

```python
"""
Rate limit helper: apply limit only when RATE_LIMIT_ENABLED is True.
"""
from functools import wraps
from typing import Optional

from slowapi import Limiter
from slowapi.util import get_remote_address

from src.core.config import RATE_LIMIT_ENABLED

limiter = Limiter(key_func=get_remote_address)
_limiter_instance: Optional[Limiter] = limiter if RATE_LIMIT_ENABLED else None


def get_limiter() -> Optional[Limiter]:
    return _limiter_instance


def limit(limit_string: str):
    """Decorator that applies rate limit only when RATE_LIMIT_ENABLED is True."""
    def decorator(func):
        if _limiter_instance:
            return _limiter_instance.limit(limit_string)(func)
        return func
    return decorator
```

- If you prefer to keep using a single limiter in `main.py`, skip this file and do 4.3 only.

### 4.3 Update `main.py` so limiter is conditional

**Current:** `from src.shared.limiter_config import limiter` and `app.state.limiter = limiter`.

**Change:**

1. In config, ensure `RATE_LIMIT_ENABLED` is defined (Phase 4.1).
2. In `main.py`:

```python
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

from src.core.config import RATE_LIMIT_ENABLED

if RATE_LIMIT_ENABLED:
    limiter = Limiter(key_func=get_remote_address)
else:
    limiter = Limiter(key_func=get_remote_address)  # still need instance for app.state
    # Disable limits by not adding SlowAPIMiddleware or by using a no-op; simplest is to add middleware but set very high default
    # Alternative: only add SlowAPIMiddleware when RATE_LIMIT_ENABLED so @limiter.limit() is effectively no-op when limiter not in app.state
```

Simpler approach: keep current `limiter_config.py` as-is, and in `main.py`:

- Only add `app.state.limiter = limiter` and `app.add_exception_handler(RateLimitExceeded, ...)` and `app.add_middleware(SlowAPIMiddleware)` when `RATE_LIMIT_ENABLED` is True.
- When False, don’t add the middleware and don’t set `app.state.limiter`; ensure routes that use `limiter.limit(...)` don’t assume `app.state.limiter` exists (or use a no-op limiter).

**Recommended minimal change:**

- Add `RATE_LIMIT_ENABLED` to config.
- In `main.py`: always set `app.state.limiter` (so routes using `@limiter.limit(...)` don’t break). Only add the rate-limit exception handler and SlowAPIMiddleware when `RATE_LIMIT_ENABLED` so limits are enforced only then:

```python
from src.core.config import RATE_LIMIT_ENABLED
from src.shared.limiter_config import limiter

app.state.limiter = limiter
if RATE_LIMIT_ENABLED:
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
    app.add_middleware(SlowAPIMiddleware)
```

- When `RATE_LIMIT_ENABLED` is False, SlowAPIMiddleware is not added, so SlowAPI does not enforce limits; the decorators remain and do nothing. No change needed in route files.

### 4.4 Add to `config/env.example`

```env
# Set to false to disable rate limiting (e.g. local dev or tests)
RATE_LIMIT_ENABLED=true
```

### 4.5 Checklist

- [ ] `RATE_LIMIT_ENABLED` in config.
- [ ] main.py only adds rate limit middleware/handler when enabled.
- [ ] env.example updated.

---

## Phase 5: Health check masking and Qdrant client

**Goal:** In production, don’t expose full exception messages in health endpoints; use Qdrant client with `QDRANT_USE_API_KEY` in main.

### 5.1 Helper for safe error message

In `main.py` (or a small helper), define:

```python
def _health_error_message(e: Exception) -> str:
    from src.core.config import ENVIRONMENT
    if ENVIRONMENT == "production":
        return "Connection failed"
    return str(e)
```

### 5.2 Update `/api/health` in `main.py`

- Use `QDRANT_USE_API_KEY` and `QDRANT_API_KEY` when building `QdrantClient` (same pattern as elsewhere):

```python
from src.core.config import QDRANT_LOCAL_URI, QDRANT_USE_API_KEY, QDRANT_API_KEY

if QDRANT_USE_API_KEY:
    client = QdrantClient(url=QDRANT_LOCAL_URI, api_key=QDRANT_API_KEY, timeout=10)
else:
    client = QdrantClient(url=QDRANT_LOCAL_URI, timeout=10)
```

- For each `except` block that currently does `"error": str(e)`, use:

```python
"error": _health_error_message(e)
```

So production only sees a generic message.

### 5.3 Update `/api/qdrant/check` in `main.py`

- Replace `QDRANT_API_KEY` with `QDRANT_USE_API_KEY` + `QDRANT_API_KEY` when creating `QdrantClient` (same as health).
- If this endpoint returns exception details to the client, in production replace `str(e)` (or equivalent) with `_health_error_message(e)`.

### 5.4 Checklist

- [ ] `_health_error_message(e)` used for all health-check error responses.
- [ ] Production gets generic message; non-production gets full message.
- [ ] Health and qdrant check use `QDRANT_USE_API_KEY` for Qdrant client.

---

## Phase 6: Input validation (shared)

**Goal:** Add a small shared validation module and use it for chat message and search query (and optionally other body/query params).

### 6.1 Create `src/shared/validation.py`

```python
"""
Shared input validation and sanitization for security.
Use for request body strings (e.g. chat message, search query).
"""
import re
import logging
from typing import Optional

from src.core.errors import ValidationError

logger = logging.getLogger(__name__)


def sanitize_string(
    value: str,
    max_length: Optional[int] = None,
    min_length: int = 0,
    remove_control_chars: bool = True,
    trim_whitespace: bool = True,
) -> str:
    if not isinstance(value, str):
        raise ValidationError(f"Expected string, got {type(value).__name__}")
    if remove_control_chars:
        allowed = {9, 10, 13, 32}
        value = "".join(c for c in value if ord(c) >= 32 or ord(c) in allowed)
    if trim_whitespace:
        value = value.strip()
    if len(value) < min_length:
        raise ValidationError(f"Input must be at least {min_length} characters")
    if max_length and len(value) > max_length:
        logger.warning("Input truncated from %d to %d characters", len(value), max_length)
        value = value[:max_length]
    return value


def validate_message(message: str, max_length: int = 5000, min_length: int = 0) -> str:
    return sanitize_string(message, max_length=max_length, min_length=min_length)


def validate_search_query(query: str, max_length: int = 500, min_length: int = 0) -> str:
    return sanitize_string(query, max_length=max_length, min_length=min_length)
```

- Ensure `src.core.errors.ValidationError` exists and is used in your global exception handler so clients get 400 with a clear message.

### 6.2 Use in chat route

In `src/api/routes/chat_router.py`, where the request body is read (e.g. `message`):

- Before using the message, call:

```python
from src.shared.validation import validate_message

# e.g. after getting message from body
message = validate_message(message, max_length=5000, min_length=1)
```

- Catch `ValidationError` and return 400 (or let FastAPI/global handler do it if ValidationError is mapped).

### 6.3 Use in search route

In `src/api/routes/search.py`, for the search `query`:

```python
from src.shared.validation import validate_search_query

# after getting query from body
query = validate_search_query(query, max_length=500, min_length=1)
```

### 6.4 Optional: global exception handler for ValidationError

In `main.py`, if not already present:

```python
from src.core.errors import ValidationError

@app.exception_handler(ValidationError)
async def validation_exception_handler(request, exc: ValidationError):
    from fastapi.responses import JSONResponse
    return JSONResponse(
        status_code=400,
        content={"detail": str(exc)},
    )
```

### 6.5 Checklist

- [ ] `src/shared/validation.py` with `sanitize_string`, `validate_message`, `validate_search_query`.
- [ ] Chat route validates message length and content.
- [ ] Search route validates query.
- [ ] ValidationError returns 400 (global or per-route).

---

## Env summary (add to `config/env.example`)

```env
# --- Security & environment ---
ENVIRONMENT=development
CORS_ORIGINS=http://localhost:3000,http://localhost:8501
API_KEY=your-secure-api-key-here
# API_KEYS=key1,key2
RATE_LIMIT_ENABLED=true
```

---

## Verification

After each phase:

1. Run app: `uv run uvicorn main:app`
2. Call health: `GET /api/health` (no key needed).
3. Call protected endpoint without key: expect 401 (or dev bypass in Phase 2 when no keys).
4. Call with valid key: expect 200.
5. Set `ENVIRONMENT=production` and `CORS_ORIGINS` and test CORS and health error masking.

---

## Reference

- Comparison doc: `docs/SECURITY_COMPARISON_SURVEY_VS_EVALUATOR.md`
- Survey API key: `agentic-ai-survey/src/deps/api_key.py`
- Survey config: `agentic-ai-survey/src/shared/utils/config.py` (API_KEYS, ENVIRONMENT, RATE_LIMIT_ENABLED, ALLOWED_ORIGINS)
- Survey validation: `agentic-ai-survey/src/shared/utils/validation.py`
