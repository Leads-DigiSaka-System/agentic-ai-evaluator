"""
Unit tests for Langfuse session helper (monitoring.session.langfuse_session_helper).

Tests generate_session_id, propagate_session_id, get_session_url.
Uses mocks so tests pass without real Langfuse.
"""
import pytest
from unittest.mock import Mock, patch, MagicMock


class TestGenerateSessionId:
    """Tests for generate_session_id()."""

    def test_returns_string_with_prefix(self):
        from src.monitoring.session.langfuse_session_helper import generate_session_id
        sid = generate_session_id(prefix="chat")
        assert isinstance(sid, str)
        assert sid.startswith("chat-")
        assert len(sid) > len("chat-")

    def test_unique_per_call(self):
        from src.monitoring.session.langfuse_session_helper import generate_session_id
        a = generate_session_id(prefix="s")
        b = generate_session_id(prefix="s")
        assert a != b

    def test_under_200_chars(self):
        from src.monitoring.session.langfuse_session_helper import generate_session_id
        sid = generate_session_id(prefix="x")
        assert len(sid) <= 200


class TestPropagateSessionId:
    """Tests for propagate_session_id() context manager."""

    @patch("src.monitoring.session.langfuse_session_helper.LANGFUSE_CONFIGURED", False)
    def test_yields_without_error_when_langfuse_disabled(self):
        from src.monitoring.session.langfuse_session_helper import propagate_session_id
        with propagate_session_id("session-123"):
            pass

    @patch("src.monitoring.session.langfuse_session_helper.LANGFUSE_CONFIGURED", True)
    @patch("src.monitoring.session.langfuse_session_helper.LANGFUSE_SESSION_AVAILABLE", True)
    @patch("src.monitoring.session.langfuse_session_helper.propagate_attributes")
    def test_calls_propagate_attributes_with_session_id_and_user_id(self, mock_propagate):
        cm = MagicMock()
        mock_propagate.return_value = cm
        from src.monitoring.session.langfuse_session_helper import propagate_session_id
        with propagate_session_id("sess-1", user_id="user-1"):
            pass
        mock_propagate.assert_called_once()
        call_kw = mock_propagate.call_args[1]
        assert call_kw.get("session_id") == "sess-1"
        assert call_kw.get("user_id") == "user-1"


class TestGetSessionUrl:
    """Tests for get_session_url()."""

    @patch("src.monitoring.session.langfuse_session_helper.LANGFUSE_CONFIGURED", False)
    def test_returns_none_when_not_configured(self):
        from src.monitoring.session.langfuse_session_helper import get_session_url
        assert get_session_url("sess-1") is None

    @patch("src.monitoring.session.langfuse_session_helper.LANGFUSE_CONFIGURED", True)
    @patch("src.core.config.LANGFUSE_HOST", "https://cloud.langfuse.com")
    def test_returns_url_when_configured(self):
        from src.monitoring.session.langfuse_session_helper import get_session_url
        url = get_session_url("sess-abc")
        assert url is not None
        assert "sessions" in url
        assert "sess-abc" in url
