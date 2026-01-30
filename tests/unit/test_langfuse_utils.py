"""
Unit tests for shared.langfuse_utils (safe_observe, safe_get_client, safe_update_observation, safe_update_trace).
"""
import pytest
from unittest.mock import Mock, patch


class TestSafeObserve:
    """Tests for safe_observe() decorator."""

    @patch("src.shared.langfuse_utils.LANGFUSE_AVAILABLE", False)
    def test_returns_noop_decorator_when_not_available(self):
        from src.shared.langfuse_utils import safe_observe
        @safe_observe(name="my_func")
        def my_func():
            return 42
        assert my_func() == 42
        assert my_func.__name__ == "my_func"

    @patch("src.shared.langfuse_utils.LANGFUSE_AVAILABLE", True)
    @patch("src.shared.langfuse_utils._observe_decorator")
    def test_uses_real_observe_when_available(self, mock_observe):
        mock_observe.return_value = lambda f: f
        from src.shared.langfuse_utils import safe_observe
        @safe_observe(name="x")
        def f():
            pass
        mock_observe.assert_called_once_with(name="x")


class TestSafeGetClient:
    """Tests for safe_get_client()."""

    @patch("src.shared.langfuse_utils.LANGFUSE_AVAILABLE", False)
    def test_returns_none_when_not_available(self):
        from src.shared.langfuse_utils import safe_get_client
        assert safe_get_client() is None

    @patch("src.shared.langfuse_utils.LANGFUSE_AVAILABLE", True)
    @patch("src.shared.langfuse_utils._get_client_func")
    def test_returns_client_when_available(self, mock_get):
        mock_client = Mock()
        mock_get.return_value = mock_client
        from src.shared.langfuse_utils import safe_get_client
        assert safe_get_client() is mock_client

    @patch("src.shared.langfuse_utils.LANGFUSE_AVAILABLE", True)
    @patch("src.shared.langfuse_utils._get_client_func", side_effect=Exception("network"))
    def test_returns_none_on_exception(self, _mock_get):
        from src.shared.langfuse_utils import safe_get_client
        assert safe_get_client() is None


class TestSafeUpdateObservation:
    """Tests for safe_update_observation()."""

    @patch("src.shared.langfuse_utils.LANGFUSE_CONFIGURED", False)
    def test_returns_false_when_not_configured(self):
        from src.shared.langfuse_utils import safe_update_observation
        assert safe_update_observation(metadata={"x": 1}) is False

    def test_returns_false_when_metadata_empty(self):
        from src.shared.langfuse_utils import safe_update_observation
        assert safe_update_observation(metadata=None) is False
        assert safe_update_observation(metadata={}) is False

    @patch("src.shared.langfuse_utils.LANGFUSE_CONFIGURED", True)
    @patch("src.shared.langfuse_utils.safe_get_client")
    def test_returns_true_and_calls_update_when_configured(self, mock_get_client):
        mock_client = Mock()
        mock_get_client.return_value = mock_client
        from src.shared.langfuse_utils import safe_update_observation
        result = safe_update_observation(metadata={"key": "value"})
        assert result is True
        mock_client.update_current_observation.assert_called_once_with(metadata={"key": "value"})


class TestSafeUpdateTrace:
    """Tests for safe_update_trace()."""

    @patch("src.shared.langfuse_utils.LANGFUSE_CONFIGURED", False)
    def test_returns_false_when_not_configured(self):
        from src.shared.langfuse_utils import safe_update_trace
        assert safe_update_trace(metadata={"x": 1}) is False

    @patch("src.shared.langfuse_utils.LANGFUSE_CONFIGURED", True)
    @patch("src.shared.langfuse_utils.safe_get_client")
    def test_returns_true_and_calls_update_trace_when_configured(self, mock_get_client):
        mock_client = Mock()
        mock_get_client.return_value = mock_client
        from src.shared.langfuse_utils import safe_update_trace
        result = safe_update_trace(metadata={"step": 1}, tags=["a"])
        assert result is True
        mock_client.update_current_trace.assert_called_once()
        kw = mock_client.update_current_trace.call_args[1]
        assert kw.get("metadata") == {"step": 1}
        assert kw.get("tags") == ["a"]
