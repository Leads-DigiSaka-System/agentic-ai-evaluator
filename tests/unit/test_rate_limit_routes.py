"""
Contract tests for rate limiting on API routes.

Verifies that route modules use @limiter.limit("...") and request: Request
on the expected endpoints (per RATE_LIMIT_MAP). Uses source inspection to avoid
importing heavy route dependencies.
"""
import pytest
from pathlib import Path


# Expected (file path relative to project root, pattern to find, limit string)
# Format: (path, decorator_pattern, limit_value)
RATE_LIMIT_CONTRACTS = [
    ("src/api/routes/upload.py", '@limiter.limit("20/hour")', "20/hour"),
    ("src/api/routes/progress.py", '@limiter.limit("60/minute")', "60/minute"),
    ("src/api/routes/list.py", '@limiter.limit("60/minute")', "60/minute"),
    ("src/api/routes/agent.py", '@limiter.limit("10/minute")', "10/minute"),
    ("src/api/routes/search.py", '@limiter.limit("60/minute")', "60/minute"),
    ("src/api/routes/storage.py", '@limiter.limit("10/minute")', "10/minute"),
    ("src/api/routes/chat_router.py", '@limiter.limit("30/minute")', "30/minute"),
    ("src/api/routes/chat_router.py", '@limiter.limit("60/minute")', "60/minute"),
    ("src/api/routes/chat_router.py", '@limiter.limit("10/minute")', "10/minute"),
    ("src/api/routes/cache.py", '@limiter.limit("10/minute")', "10/minute"),
    ("src/api/routes/cache.py", '@limiter.limit("5/minute")', "5/minute"),
    ("src/api/routes/cache.py", '@limiter.limit("60/minute")', "60/minute"),
    ("src/api/routes/cache.py", '@limiter.limit("30/minute")', "30/minute"),
    ("src/api/routes/worker.py", '@limiter.limit("30/minute")', "30/minute"),
    ("src/api/routes/delete_extract.py", '@limiter.limit("10/minute")', "10/minute"),
    ("src/api/routes/delete_extract.py", '@limiter.limit("5/minute")', "5/minute"),
]


class TestRateLimitDecoratorOnRoutes:
    """Contract tests: route files must contain expected @limiter.limit(...)."""

    @pytest.fixture(scope="class")
    def project_root(self):
        return Path(__file__).resolve().parent.parent.parent

    def test_upload_has_20_per_hour_limit(self, project_root):
        path = project_root / "src" / "api" / "routes" / "upload.py"
        content = path.read_text(encoding="utf-8")
        assert '@limiter.limit("20/hour")' in content, "upload.py should have @limiter.limit('20/hour')"
        assert "request: Request" in content or "request:Request" in content.replace(" ", ""), \
            "upload.py should have request: Request for rate limiter"

    def test_progress_has_60_per_minute_limit(self, project_root):
        path = project_root / "src" / "api" / "routes" / "progress.py"
        content = path.read_text(encoding="utf-8")
        assert '@limiter.limit("60/minute")' in content
        assert "request: Request" in content or "request:Request" in content.replace(" ", "")

    def test_list_has_60_per_minute_limit_on_both_endpoints(self, project_root):
        path = project_root / "src" / "api" / "routes" / "list.py"
        content = path.read_text(encoding="utf-8")
        assert content.count('@limiter.limit("60/minute")') >= 2, "list.py should have 60/minute on list and stats"
        assert "request: Request" in content or "request:Request" in content.replace(" ", "")

    def test_agent_has_10_per_minute_limit(self, project_root):
        path = project_root / "src" / "api" / "routes" / "agent.py"
        content = path.read_text(encoding="utf-8")
        assert '@limiter.limit("10/minute")' in content
        assert "request: Request" in content or "request:Request" in content.replace(" ", "")

    def test_search_has_60_per_minute_limit(self, project_root):
        path = project_root / "src" / "api" / "routes" / "search.py"
        content = path.read_text(encoding="utf-8")
        assert '@limiter.limit("60/minute")' in content
        assert "request: Request" in content or "request:Request" in content.replace(" ", "")

    def test_storage_has_10_per_minute_limit(self, project_root):
        path = project_root / "src" / "api" / "routes" / "storage.py"
        content = path.read_text(encoding="utf-8")
        assert '@limiter.limit("10/minute")' in content
        assert "request: Request" in content or "request:Request" in content.replace(" ", "")

    def test_chat_router_has_rate_limits(self, project_root):
        path = project_root / "src" / "api" / "routes" / "chat_router.py"
        content = path.read_text(encoding="utf-8")
        assert '@limiter.limit("30/minute")' in content
        assert '@limiter.limit("60/minute")' in content
        assert '@limiter.limit("10/minute")' in content
        assert "request: Request" in content or "request:Request" in content.replace(" ", "")

    def test_cache_has_expected_limits(self, project_root):
        path = project_root / "src" / "api" / "routes" / "cache.py"
        content = path.read_text(encoding="utf-8")
        assert '@limiter.limit("10/minute")' in content
        assert '@limiter.limit("5/minute")' in content
        assert '@limiter.limit("60/minute")' in content
        assert '@limiter.limit("30/minute")' in content
        assert "request: Request" in content or "request:Request" in content.replace(" ", "")

    def test_worker_has_30_per_minute_limit(self, project_root):
        path = project_root / "src" / "api" / "routes" / "worker.py"
        content = path.read_text(encoding="utf-8")
        assert '@limiter.limit("30/minute")' in content
        assert content.count('@limiter.limit("30/minute")') >= 3, "worker should have 30/minute on health, metrics, jobs"
        assert "request: Request" in content or "request:Request" in content.replace(" ", "")

    def test_delete_extract_has_10_and_5_per_minute_limits(self, project_root):
        path = project_root / "src" / "api" / "routes" / "delete_extract.py"
        content = path.read_text(encoding="utf-8")
        assert '@limiter.limit("10/minute")' in content
        assert '@limiter.limit("5/minute")' in content
        assert "request: Request" in content or "request:Request" in content.replace(" ", "")


class TestRateLimitContractsSummary:
    """Each route file that should have rate limiting imports limiter."""

    @pytest.fixture(scope="class")
    def project_root(self):
        return Path(__file__).resolve().parent.parent.parent

    @pytest.mark.parametrize("route_file", [
        "src/api/routes/upload.py",
        "src/api/routes/progress.py",
        "src/api/routes/list.py",
        "src/api/routes/agent.py",
        "src/api/routes/search.py",
        "src/api/routes/storage.py",
        "src/api/routes/chat_router.py",
        "src/api/routes/cache.py",
        "src/api/routes/worker.py",
        "src/api/routes/delete_extract.py",
    ])
    def test_route_file_imports_limiter(self, project_root, route_file):
        path = project_root / Path(route_file)
        content = path.read_text(encoding="utf-8")
        assert "limiter" in content, f"{route_file} should use limiter (from limiter_config)"
        assert "limiter_config" in content or "from src.shared.limiter_config import limiter" in content, \
            f"{route_file} should import limiter from limiter_config"
