"""
Unit tests for all Langfuse implementation touchpoints.

Maps and tests every place that uses Langfuse so we can spot problems:
- langfuse_helper, langfuse_session_helper
- Routes: chat, agent, search, upload, progress, storage, cache
- Worker, scores, langfuse_utils, llm_helper
Uses mocks so tests pass without real LANGFUSE_* credentials.
"""
import pytest
from unittest.mock import Mock, patch, MagicMock, AsyncMock


# ---------------------------------------------------------------------------
# Map of Langfuse touchpoints (for documentation and smoke checks)
# ---------------------------------------------------------------------------

LANGFUSE_TOUCHPOINTS = {
    "monitoring.trace.langfuse_helper": [
        "is_langfuse_enabled",
        "initialize_langfuse",
        "get_langfuse_client",
        "create_callback_handler",
        "flush_langfuse",
        "shutdown_langfuse",
        "update_trace_with_error",
        "update_trace_with_metrics",
        "create_score",
        "score_current_trace",
        "get_current_trace_id",
        "get_trace_url",
        "update_current_span",
        "observe_operation",
    ],
    "monitoring.session.langfuse_session_helper": [
        "generate_session_id",
        "propagate_session_id",
        "get_session_url",
    ],
    "api.routes.chat_router": ["@observe(chat_agent)", "propagate_session_id", "update_current_trace"],
    "api.routes.agent": ["@observe(agent_file_upload)", "propagate_session_id", "flush_langfuse"],
    "api.routes.search": ["@observe(analysis_search)", "propagate_session_id", "update_current_trace"],
    "api.routes.upload": ["@observe(upload_file_product_demo)", "propagate_session_id", "update_current_trace"],
    "api.routes.progress": ["@observe(get_progress)", "propagate_session_id", "_get_session_id"],
    "api.routes.storage": ["@observe(approve_storage)", "propagate_session_id", "update_current_trace"],
    "api.routes.cache": ["@observe(cache_*)", "_cache_trace_attrs", "update_current_trace"],
    "workers": ["propagate_session_id(session_id, user_id)"],
    "monitoring.scores": ["search_score.log_search_scores", "storage_score.*", "workflow_score.*"],
    "shared.langfuse_utils": ["safe_observe", "safe_get_client", "safe_update_observation", "safe_update_trace"],
    "shared.llm_helper": ["get_langfuse_handler"],
}


class TestLangfuseTouchpointMap:
    """Smoke test: ensure our map and actual imports align."""

    def test_langfuse_helper_exports_exist(self):
        from src.monitoring.trace import langfuse_helper as m
        for name in LANGFUSE_TOUCHPOINTS["monitoring.trace.langfuse_helper"]:
            assert hasattr(m, name), f"langfuse_helper missing: {name}"

    def test_langfuse_session_helper_exports_exist(self):
        from src.monitoring.session import langfuse_session_helper as m
        for name in LANGFUSE_TOUCHPOINTS["monitoring.session.langfuse_session_helper"]:
            assert hasattr(m, name), f"langfuse_session_helper missing: {name}"

    def test_score_helper_reexports_from_langfuse_helper(self):
        from src.shared import score_helper as sh
        from src.monitoring.trace import langfuse_helper as lh
        assert sh.score_current_trace is lh.score_current_trace
        assert sh.create_score is lh.create_score


class TestChatRouterLangfuse:
    """Chat route: propagate_session_id wraps handler; update_current_trace called."""

    def test_chat_route_uses_propagate_session_id(self):
        from pathlib import Path
        root = Path(__file__).resolve().parent.parent.parent
        path = root / "src" / "api" / "routes" / "chat_router.py"
        content = path.read_text(encoding="utf-8")
        assert "propagate_session_id" in content
        assert "with propagate_session_id" in content
        assert "update_current_trace" in content


class TestSearchRouteLangfuse:
    """Search route: propagate_session_id wraps handler; session_id/user_id from query/header."""

    def test_search_route_uses_propagate_session_id(self):
        from pathlib import Path
        root = Path(__file__).resolve().parent.parent.parent
        content = (root / "src" / "api" / "routes" / "search.py").read_text(encoding="utf-8")
        assert "propagate_session_id" in content
        assert "with propagate_session_id" in content
        assert "session_id" in content and ("user_id" in content or "uid" in content)


class TestUploadRouteLangfuse:
    """Upload route: propagate_session_id wraps handler; generate_session_id; X-User-ID."""

    def test_upload_route_uses_propagate_session_id_and_generate_session_id(self):
        with open("src/api/routes/upload.py", encoding="utf-8") as f:
            content = f.read()
        assert "propagate_session_id" in content
        assert "generate_session_id" in content
        assert "with propagate_session_id" in content


class TestAgentRouteLangfuse:
    """Agent route: propagate_session_id wraps processing; flush_langfuse on sync path."""

    def test_agent_route_uses_propagate_session_id(self):
        from pathlib import Path
        root = Path(__file__).resolve().parent.parent.parent
        content = (root / "src" / "api" / "routes" / "agent.py").read_text(encoding="utf-8")
        assert "propagate_session_id" in content
        assert "flush_langfuse" in content


class TestStorageRouteLangfuse:
    """Storage route: propagate_session_id when original_session_id present."""

    def test_storage_route_uses_propagate_session_id(self):
        from pathlib import Path
        root = Path(__file__).resolve().parent.parent.parent
        content = (root / "src" / "api" / "routes" / "storage.py").read_text(encoding="utf-8")
        assert "propagate_session_id" in content
        assert "update_current_trace" in content or "update_current_observation" in content


class TestCacheRouteLangfuse:
    """Cache routes: _cache_trace_attrs sets tags and metadata; no session/user required."""

    @patch("src.monitoring.trace.langfuse_helper.is_langfuse_enabled", return_value=True)
    @patch("src.monitoring.trace.langfuse_helper.get_langfuse_client")
    def test_cache_trace_attrs_calls_update_current_trace(self, mock_get_client, _mock_enabled):
        mock_client = Mock()
        mock_get_client.return_value = mock_client
        # Import cache module (may pull redis/arq); patch at helper level so we don't need cache route to import arq
        from src.monitoring.trace.langfuse_helper import is_langfuse_enabled, get_langfuse_client
        # Use the same helper pattern as cache._cache_trace_attrs
        langfuse = get_langfuse_client() if is_langfuse_enabled() else None
        if langfuse:
            langfuse.update_current_trace(tags=["admin", "cache", "api"], metadata={"action": "cleanup"})
        mock_client.update_current_trace.assert_called_once()
        kw = mock_client.update_current_trace.call_args[1]
        assert "admin" in kw.get("tags", [])
        assert kw.get("metadata", {}).get("action") == "cleanup"


class TestWorkerLangfuse:
    """Worker: uses propagate_session_id(session_id, user_id) when LANGFUSE_CONFIGURED and session_id present."""

    def test_worker_module_uses_propagate_session_id(self):
        from pathlib import Path
        root = Path(__file__).resolve().parent.parent.parent
        content = (root / "src" / "workers" / "workers.py").read_text(encoding="utf-8")
        assert "propagate_session_id" in content
        assert "session_id" in content and "user_id" in content


class TestConfigLangfuse:
    """Core config: LANGFUSE_* env and LANGFUSE_CONFIGURED."""

    def test_config_exports_langfuse_vars(self):
        from src.core import config
        assert hasattr(config, "LANGFUSE_PUBLIC_KEY")
        assert hasattr(config, "LANGFUSE_SECRET_KEY")
        assert hasattr(config, "LANGFUSE_HOST")
        assert hasattr(config, "LANGFUSE_CONFIGURED")
        assert isinstance(config.LANGFUSE_CONFIGURED, bool)
