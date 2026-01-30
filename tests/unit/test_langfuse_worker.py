"""
Unit tests for worker Langfuse usage (propagate_session_id with session_id from API).

Tests that the worker is documented to use the same session_id as the API (not a new workflow_session_id).
We test the expected call pattern without importing the full worker (which pulls in heavy deps).
"""
import pytest
from unittest.mock import Mock, patch, MagicMock


class TestWorkerPropagateSessionId:
    """Worker uses session_id (from API) and user_id in propagate_session_id - same session as upload."""

    def test_propagate_session_id_call_pattern_matches_api_session(self):
        # Worker code: with propagate_session_id(session_id, user_id=user_id or ""):
        # So the first arg is session_id (from API), second is user_id. Verify the pattern.
        from src.monitoring.session.langfuse_session_helper import propagate_session_id
        session_id_from_api = "file_upload_user1-abc-uuid"
        user_id = "user-1"
        with patch("src.monitoring.session.langfuse_session_helper.LANGFUSE_CONFIGURED", True):
            with patch("src.monitoring.session.langfuse_session_helper.LANGFUSE_SESSION_AVAILABLE", True):
                with patch("src.monitoring.session.langfuse_session_helper.propagate_attributes") as mock_prop:
                    cm = MagicMock()
                    mock_prop.return_value = cm
                    with propagate_session_id(session_id_from_api, user_id=user_id):
                        pass
                    mock_prop.assert_called_once()
                    assert mock_prop.call_args[1]["session_id"] == session_id_from_api
                    assert mock_prop.call_args[1]["user_id"] == user_id
