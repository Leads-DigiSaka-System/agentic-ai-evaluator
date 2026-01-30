"""
Unit tests for Langfuse integration in shared.llm_helper (get_langfuse_handler).
"""
import pytest
from unittest.mock import Mock, patch

# Load module so patch("src.shared.llm_helper.LANGFUSE_CONFIGURED") can resolve (conftest mocks langchain_google_genai)
import src.shared.llm_helper  # noqa: F401


class TestGetLangfuseHandler:
    """Tests for get_langfuse_handler()."""

    @patch("src.shared.llm_helper.LANGFUSE_CONFIGURED", False)
    def test_returns_none_when_not_configured(self):
        import src.shared.llm_helper as m
        m._langfuse_handler = None  # reset singleton for test
        from src.shared.llm_helper import get_langfuse_handler
        assert get_langfuse_handler() is None

    @patch("src.shared.llm_helper.LANGFUSE_CONFIGURED", True)
    @patch("src.shared.llm_helper._langfuse_handler", None)
    @patch("langfuse.langchain.CallbackHandler")
    @patch("src.monitoring.trace.langfuse_helper.initialize_langfuse", return_value=True)
    def test_returns_handler_when_configured_and_import_ok(self, mock_init, mock_handler_class):
        import src.shared.llm_helper as m
        m._langfuse_handler = None
        mock_instance = Mock()
        mock_handler_class.return_value = mock_instance
        from src.shared.llm_helper import get_langfuse_handler
        result = get_langfuse_handler()
        assert result is mock_instance
        mock_init.assert_called()
        mock_handler_class.assert_called_once()
        m._langfuse_handler = None

    def test_get_langfuse_handler_is_callable(self):
        from src.shared.llm_helper import get_langfuse_handler
        assert callable(get_langfuse_handler)
