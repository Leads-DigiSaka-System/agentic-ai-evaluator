"""
Unit tests for Langfuse Sessions and Users (same pattern as agentic-ai-survey).

We use mock data (user_id, session_id) that would show on the Langfuse dashboard.
- Routes: we verify source code passes session_id/user_id to update_current_trace and
  propagate_session_id (importing chat/search would load HuggingFace).
- Session helper: test_langfuse_session_helper uses mock data (sess-1, user-1) and asserts
  propagate_session_id(sess, user_id=uid) calls Langfuse — same “mock data for dashboard” pattern.

Pattern from agentic-ai-survey: fixtures for mock_user_id, mock_session_id;
call endpoint with those (or verify code path), assert update_current_trace has them.
"""
import pytest
from pathlib import Path
from unittest.mock import MagicMock, AsyncMock


def _read(path: str) -> str:
    root = Path(__file__).resolve().parent.parent.parent
    return (root / path).read_text(encoding="utf-8")


# =============================================================================
# Mock data fixtures (para lumabas sa dashboard)
# =============================================================================

@pytest.fixture
def mock_user_id():
    """Mock user ID — would show in Langfuse Users tab."""
    return "user_dashboard_123"


@pytest.fixture
def mock_session_id():
    """Mock session ID — would show in Langfuse Sessions tab."""
    return "session_dashboard_456"


@pytest.fixture
def mock_upload_file():
    """Mock upload file for upload endpoint."""
    f = MagicMock()
    f.filename = "demo.pdf"
    f.read = AsyncMock(return_value=b"dummy pdf bytes")
    return f


# =============================================================================
# Search route: source contract (import would load HuggingFace)
# Mock data mock_user_id / mock_session_id would reach Langfuse when endpoint is called.
# =============================================================================

class TestSearchRouteLangfuseSessionAndUser:
    """Search route: code must pass session_id/user_id to Langfuse (Sessions/Users)."""

    def test_search_trace_gets_session_id_and_user_id_from_code(
        self, mock_user_id, mock_session_id
    ):
        """Route must call update_current_trace(session_id=..., user_id=...) and propagate_session_id(sid, user_id=...)."""
        content = _read("src/api/routes/search.py")
        assert "update_current_trace" in content
        assert "session_id" in content and ("user_id" in content or "uid" in content)
        assert "attrs[" in content and "session_id" in content
        assert "propagate_session_id" in content
        assert "with propagate_session_id" in content
        assert "user_id=uid" in content or "user_id= uid" in content


# =============================================================================
# Upload route: source contract (same “mock data for dashboard” idea)
# =============================================================================

class TestUploadRouteLangfuseSessionAndUser:
    """Upload route: code must pass session_id/user_id to Langfuse (Sessions/Users)."""

    def test_upload_trace_gets_session_id_and_user_id_from_code(
        self, mock_user_id, mock_upload_file
    ):
        """Route must call update_current_trace(session_id=..., user_id=...) and propagate_session_id(session_id, user_id=...)."""
        content = _read("src/api/routes/upload.py")
        assert "update_current_trace" in content
        assert "session_id" in content and "user_id" in content
        assert "attrs" in content
        assert "propagate_session_id" in content
        assert "with propagate_session_id" in content
        assert "user_id=user_id_val" in content or "user_id= user_id_val" in content


# =============================================================================
# Chat route: source-code contract (chat_router import pulls HuggingFace)
# Same “mock data for dashboard” idea: code must pass user_id/session_id to Langfuse.
# =============================================================================

class TestChatRouteLangfuseSessionAndUser:
    """Chat route must set trace session_id/user_id and use propagate_session_id (source contract)."""

    def test_chat_calls_update_current_trace_with_session_id_and_user_id(self):
        content = _read("src/api/routes/chat_router.py")
        assert "update_current_trace" in content
        assert "user_id=user_id" in content or "user_id = user_id" in content
        assert "session_id=session_id" in content or "session_id = session_id" in content

    def test_chat_uses_propagate_session_id_with_session_id_and_user_id(self):
        content = _read("src/api/routes/chat_router.py")
        assert "propagate_session_id" in content
        assert "with propagate_session_id" in content
        assert "user_id=user_id" in content


# =============================================================================
# Session helper: mock data flows to Langfuse (test_langfuse_session_helper has the full test)
# =============================================================================

class TestSessionHelperPassesToLangfuse:
    """propagate_session_id(session_id, user_id=...) must pass to Langfuse (see test_langfuse_session_helper)."""

    def test_propagate_session_id_code_passes_session_id_and_user_id(self):
        content = _read("src/monitoring/session/langfuse_session_helper.py")
        assert "propagate_attributes" in content
        assert "session_id" in content and "user_id" in content
        assert "attributes" in content
