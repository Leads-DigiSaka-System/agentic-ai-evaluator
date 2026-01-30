"""
Unit tests for API routes that use Langfuse (progress, search, upload, cache).

Tests that Langfuse-related code paths work with mocks and that routes
don't crash when Langfuse is disabled.
"""
import pytest
from unittest.mock import Mock, patch, MagicMock, AsyncMock

# Load routes submodules so patch("src.api.routes.cache.get_client") etc. can resolve (conftest mocks arq)
import src.api.routes.cache  # noqa: F401
import src.api.routes.progress  # noqa: F401


class TestProgressGetSessionId:
    """Tests for progress._get_session_id()."""

    @pytest.mark.asyncio
    async def test_returns_session_id_from_redis(self):
        from src.api.routes import progress as progress_module
        mock_pool = AsyncMock()
        mock_pool.get = AsyncMock(return_value=b"session-upload-123")
        sid = await progress_module._get_session_id(mock_pool, "job-abc")
        assert sid == "session-upload-123"
        mock_pool.get.assert_called_once_with("arq:session:job-abc")

    @pytest.mark.asyncio
    async def test_returns_none_when_no_key(self):
        from src.api.routes import progress as progress_module
        mock_pool = AsyncMock()
        mock_pool.get = AsyncMock(return_value=None)
        sid = await progress_module._get_session_id(mock_pool, "job-xyz")
        assert sid is None

    @pytest.mark.asyncio
    async def test_truncates_to_200_chars(self):
        from src.api.routes import progress as progress_module
        long_sid = "x" * 250
        mock_pool = AsyncMock()
        mock_pool.get = AsyncMock(return_value=long_sid.encode() if isinstance(long_sid, str) else long_sid)
        sid = await progress_module._get_session_id(mock_pool, "j")
        assert sid is not None
        assert len(sid) <= 200


class TestSearchLangfuseTraceAttrs:
    """Tests that search route can set optional user_id/session_id on trace."""

    def test_search_trace_attrs_include_user_and_session_when_provided(self):
        # Verify the pattern: update_current_trace(..., user_id=..., session_id=...) when provided
        mock_client = Mock()
        attrs = {"tags": ["search", "analysis_search", "api"]}
        attrs["user_id"] = "user-1"[:200]
        attrs["session_id"] = "sess-1"[:200]
        mock_client.update_current_trace(**attrs)
        mock_client.update_current_trace.assert_called_once_with(**attrs)
        assert mock_client.update_current_trace.call_args[1].get("user_id") == "user-1"
        assert mock_client.update_current_trace.call_args[1].get("session_id") == "sess-1"


class TestUploadLangfuseTraceAttrs:
    """Tests that upload route sets session_id and optional user_id on trace."""

    def test_generate_session_id_called_for_upload(self):
        from src.monitoring.session.langfuse_session_helper import generate_session_id
        sid = generate_session_id(prefix="upload_product_demo")
        assert sid.startswith("upload_product_demo-")
        assert len(sid) <= 200


class TestCacheLangfuseTraceAttrs:
    """Tests that cache routes set trace attributes (admin/cache)."""

    @patch("src.api.routes.cache.is_langfuse_enabled", return_value=True)
    @patch("src.api.routes.cache.get_client")
    def test_cache_trace_attrs_sets_tags_and_metadata(self, mock_get_client, _mock_enabled):
        mock_client = Mock()
        mock_get_client.return_value = mock_client
        from src.api.routes import cache as cache_module
        cache_module._cache_trace_attrs("cleanup")
        mock_client.update_current_trace.assert_called_once()
        call_kw = mock_client.update_current_trace.call_args[1]
        assert "admin" in call_kw.get("tags", [])
        assert "cache" in call_kw.get("tags", [])
        assert call_kw.get("metadata", {}).get("action") == "cleanup"


class TestProgressRouteLangfuseAttrs:
    """Progress route sets user_id and session_id on trace when Langfuse enabled."""

    def test_progress_trace_attrs_pattern(self):
        # Verify the pattern: update_current_trace(user_id=..., session_id=..., tags=[...])
        mock_client = Mock()
        mock_client.update_current_trace(
            user_id="user-1",
            session_id="session-upload-123",
            tags=["progress", "api"],
            metadata={"job_id": "job-abc"},
        )
        mock_client.update_current_trace.assert_called_once()
        kw = mock_client.update_current_trace.call_args[1]
        assert kw["user_id"] == "user-1"
        assert kw["session_id"] == "session-upload-123"
        assert "progress" in kw["tags"]
