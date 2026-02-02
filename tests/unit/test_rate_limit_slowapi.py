"""
Unit tests for SlowAPI rate limiting behavior.

Uses a minimal FastAPI app with SlowAPI to verify that exceeding the limit
returns 429 and that the exception handler is applied.
"""
import pytest
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware


@pytest.fixture
def minimal_rate_limited_app():
    """Create a minimal FastAPI app with SlowAPI and one route limited to 2/minute."""
    limiter = Limiter(key_func=get_remote_address)
    app = FastAPI()
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
    app.add_middleware(SlowAPIMiddleware)

    @app.get("/limited")
    @limiter.limit("2/minute")
    def limited_endpoint(request: Request):
        return {"ok": True}

    return app


class TestSlowAPIReturns429WhenLimitExceeded:
    """Verify that SlowAPI returns 429 when rate limit is exceeded."""

    def test_first_two_requests_succeed(self, minimal_rate_limited_app):
        client = TestClient(minimal_rate_limited_app)
        r1 = client.get("/limited")
        r2 = client.get("/limited")
        assert r1.status_code == 200
        assert r2.status_code == 200
        assert r1.json() == {"ok": True}
        assert r2.json() == {"ok": True}

    def test_third_request_within_minute_returns_429(self, minimal_rate_limited_app):
        client = TestClient(minimal_rate_limited_app)
        client.get("/limited")
        client.get("/limited")
        r3 = client.get("/limited")
        assert r3.status_code == 429, "Exceeding rate limit must return 429 Too Many Requests"
        # SlowAPI default handler may return detail as string or nested; we only require 429
        try:
            data = r3.json()
            if isinstance(data, dict):
                detail = data.get("detail", data.get("message", ""))
                if isinstance(detail, str) and detail:
                    assert "limit" in detail.lower() or "rate" in detail.lower()
        except Exception:
            pass  # 429 status is the main contract
