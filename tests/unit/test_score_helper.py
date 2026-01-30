"""
Unit tests for Langfuse score helper (shared.score_helper).

Re-exports from monitoring.trace.langfuse_helper; tests verify API and mocked behavior.
"""
import pytest
from unittest.mock import Mock, patch


class TestScoreHelperReExports:
    """Test that score_helper re-exports the expected functions."""

    def test_create_score_importable(self):
        from src.shared.score_helper import create_score
        assert callable(create_score)

    def test_score_current_trace_importable(self):
        from src.shared.score_helper import score_current_trace
        assert callable(score_current_trace)

    def test_get_current_trace_id_importable(self):
        from src.shared.score_helper import get_current_trace_id
        assert callable(get_current_trace_id)

    def test_get_current_trace_id_same_as_langfuse_helper(self):
        from src.shared.score_helper import get_current_trace_id as score_get_id
        from src.monitoring.trace.langfuse_helper import get_current_trace_id as helper_get_id
        assert score_get_id is helper_get_id


class TestCreateScore:
    """Tests for create_score() via score_helper (delegates to langfuse_helper)."""

    @patch("src.monitoring.trace.langfuse_helper.LANGFUSE_CONFIGURED", False)
    def test_does_nothing_when_not_configured(self):
        from src.shared.score_helper import create_score
        create_score("test_score", 0.9, trace_id="trace-1")  # no raise

    @patch("src.monitoring.trace.langfuse_helper.LANGFUSE_CONFIGURED", True)
    @patch("src.monitoring.trace.langfuse_helper.get_langfuse_client")
    def test_calls_client_create_score_when_configured(self, mock_get_client):
        mock_client = Mock()
        mock_get_client.return_value = mock_client
        from src.shared.score_helper import create_score
        create_score("quality", 0.85, trace_id="trace-abc", data_type="NUMERIC", comment="ok")
        mock_client.create_score.assert_called_once()
        kwargs = mock_client.create_score.call_args[1]
        assert kwargs["name"] == "quality"
        assert kwargs["value"] == 0.85
        assert kwargs["trace_id"] == "trace-abc"
        assert kwargs["data_type"] == "NUMERIC"
        assert kwargs["comment"] == "ok"


class TestScoreCurrentTrace:
    """Tests for score_current_trace() via score_helper."""

    @patch("src.monitoring.trace.langfuse_helper.LANGFUSE_CONFIGURED", False)
    def test_does_nothing_when_not_configured(self):
        from src.shared.score_helper import score_current_trace
        score_current_trace("test", 1.0)  # no raise

    @patch("src.monitoring.trace.langfuse_helper.LANGFUSE_CONFIGURED", True)
    @patch("src.monitoring.trace.langfuse_helper.get_langfuse_client")
    def test_calls_score_current_trace_or_create_score_when_configured(self, mock_get_client):
        mock_client = Mock()
        mock_client.score_current_trace = Mock()
        mock_get_client.return_value = mock_client
        from src.shared.score_helper import score_current_trace
        score_current_trace("success", 1.0, data_type="BOOLEAN")
        mock_client.score_current_trace.assert_called_once()
        kwargs = mock_client.score_current_trace.call_args[1]
        assert kwargs["name"] == "success"
        assert kwargs["value"] == 1.0
        assert kwargs["data_type"] == "BOOLEAN"


class TestGetCurrentTraceIdFromScoreHelper:
    """Tests for get_current_trace_id() from score_helper."""

    @patch("src.monitoring.trace.langfuse_helper.LANGFUSE_CONFIGURED", False)
    def test_returns_none_when_not_configured(self):
        from src.shared.score_helper import get_current_trace_id
        assert get_current_trace_id() is None

    @patch("src.monitoring.trace.langfuse_helper.LANGFUSE_CONFIGURED", True)
    @patch("src.monitoring.trace.langfuse_helper.get_langfuse_client")
    def test_returns_trace_id_from_client(self, mock_get_client):
        mock_client = Mock()
        mock_client.get_current_trace_id = Mock(return_value="trace-xyz")
        mock_get_client.return_value = mock_client
        from src.shared.score_helper import get_current_trace_id
        assert get_current_trace_id() == "trace-xyz"
