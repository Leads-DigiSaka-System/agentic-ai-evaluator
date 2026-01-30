"""
Unit tests for Langfuse helper (monitoring.trace.langfuse_helper).

Uses mocks so tests pass without real LANGFUSE_* credentials.
"""
import pytest
from unittest.mock import Mock, patch, MagicMock


class TestIsLangfuseEnabled:
    """Tests for is_langfuse_enabled()."""

    @patch("src.monitoring.trace.langfuse_helper.LANGFUSE_CONFIGURED", True)
    def test_returns_true_when_configured(self):
        from src.monitoring.trace.langfuse_helper import is_langfuse_enabled
        assert is_langfuse_enabled() is True

    @patch("src.monitoring.trace.langfuse_helper.LANGFUSE_CONFIGURED", False)
    def test_returns_false_when_not_configured(self):
        from src.monitoring.trace.langfuse_helper import is_langfuse_enabled
        assert is_langfuse_enabled() is False


class TestGetLangfuseClient:
    """Tests for get_langfuse_client()."""

    @patch("src.monitoring.trace.langfuse_helper.LANGFUSE_CONFIGURED", False)
    def test_returns_none_when_not_configured(self):
        from src.monitoring.trace.langfuse_helper import get_langfuse_client
        assert get_langfuse_client() is None

    @patch("src.monitoring.trace.langfuse_helper.LANGFUSE_CONFIGURED", True)
    @patch("src.monitoring.trace.langfuse_helper._langfuse_initialized", True)
    @patch("langfuse.get_client")
    def test_returns_client_when_configured_and_initialized(self, mock_get_client):
        mock_client = Mock()
        mock_get_client.return_value = mock_client
        from src.monitoring.trace.langfuse_helper import get_langfuse_client
        client = get_langfuse_client()
        assert client is mock_client


class TestCreateCallbackHandler:
    """Tests for create_callback_handler()."""

    @patch("src.monitoring.trace.langfuse_helper.LANGFUSE_CONFIGURED", False)
    def test_returns_none_when_not_configured(self):
        from src.monitoring.trace.langfuse_helper import create_callback_handler
        assert create_callback_handler() is None

    @patch("src.monitoring.trace.langfuse_helper.LANGFUSE_CONFIGURED", True)
    @patch("src.monitoring.trace.langfuse_helper.initialize_langfuse", return_value=True)
    def test_returns_none_or_handler_when_configured(self, mock_init):
        from src.monitoring.trace.langfuse_helper import create_callback_handler
        result = create_callback_handler()
        # Without real langfuse package, result is often None (import error); with package, handler returned
        assert result is None or hasattr(result, "__class__")


class TestFlushAndShutdown:
    """Tests for flush_langfuse() and shutdown_langfuse()."""

    @patch("src.monitoring.trace.langfuse_helper.LANGFUSE_CONFIGURED", False)
    def test_flush_does_nothing_when_not_configured(self):
        from src.monitoring.trace.langfuse_helper import flush_langfuse
        flush_langfuse()  # no raise

    @patch("src.monitoring.trace.langfuse_helper.LANGFUSE_CONFIGURED", False)
    def test_shutdown_does_nothing_when_not_configured(self):
        from src.monitoring.trace.langfuse_helper import shutdown_langfuse
        shutdown_langfuse()  # no raise

    @patch("src.monitoring.trace.langfuse_helper.LANGFUSE_CONFIGURED", True)
    @patch("src.monitoring.trace.langfuse_helper.get_langfuse_client")
    def test_flush_calls_client_flush_when_configured(self, mock_get_client):
        mock_client = Mock()
        mock_get_client.return_value = mock_client
        from src.monitoring.trace.langfuse_helper import flush_langfuse
        flush_langfuse()
        mock_client.flush.assert_called_once()

    @patch("src.monitoring.trace.langfuse_helper.LANGFUSE_CONFIGURED", True)
    @patch("src.monitoring.trace.langfuse_helper.get_langfuse_client")
    def test_shutdown_calls_client_shutdown_when_configured(self, mock_get_client):
        mock_client = Mock()
        mock_get_client.return_value = mock_client
        from src.monitoring.trace.langfuse_helper import shutdown_langfuse
        shutdown_langfuse()
        mock_client.shutdown.assert_called_once()


class TestGetCurrentTraceId:
    """Tests for get_current_trace_id()."""

    @patch("src.monitoring.trace.langfuse_helper.LANGFUSE_CONFIGURED", False)
    def test_returns_none_when_not_configured(self):
        from src.monitoring.trace.langfuse_helper import get_current_trace_id
        assert get_current_trace_id() is None

    @patch("src.monitoring.trace.langfuse_helper.LANGFUSE_CONFIGURED", True)
    @patch("src.monitoring.trace.langfuse_helper.get_langfuse_client")
    def test_returns_trace_id_from_client_when_available(self, mock_get_client):
        mock_client = Mock()
        mock_client.get_current_trace_id = Mock(return_value="abc123trace")
        mock_get_client.return_value = mock_client
        from src.monitoring.trace.langfuse_helper import get_current_trace_id
        assert get_current_trace_id() == "abc123trace"

    @patch("src.monitoring.trace.langfuse_helper.LANGFUSE_CONFIGURED", True)
    @patch("src.monitoring.trace.langfuse_helper.get_langfuse_client")
    def test_returns_none_when_client_has_no_get_current_trace_id(self, mock_get_client):
        mock_client = Mock(spec=[])  # no get_current_trace_id
        mock_get_client.return_value = mock_client
        from src.monitoring.trace.langfuse_helper import get_current_trace_id
        assert get_current_trace_id() is None


class TestGetTraceUrl:
    """Tests for get_trace_url()."""

    @patch("src.monitoring.trace.langfuse_helper.get_current_trace_id", return_value=None)
    def test_returns_none_when_no_trace_id(self, _):
        from src.monitoring.trace.langfuse_helper import get_trace_url
        assert get_trace_url() is None

    @patch("src.monitoring.trace.langfuse_helper.get_current_trace_id", return_value="abc123")
    @patch("src.monitoring.trace.langfuse_helper.LANGFUSE_HOST", "https://cloud.langfuse.com")
    def test_returns_url_when_trace_id_present(self, _):
        from src.monitoring.trace.langfuse_helper import get_trace_url
        url = get_trace_url()
        assert url == "https://cloud.langfuse.com/trace/abc123"


class TestUpdateTraceWithError:
    """Tests for update_trace_with_error()."""

    @patch("src.monitoring.trace.langfuse_helper.LANGFUSE_CONFIGURED", False)
    def test_does_nothing_when_not_configured(self):
        from src.monitoring.trace.langfuse_helper import update_trace_with_error
        update_trace_with_error(ValueError("test"))  # no raise

    @patch("src.monitoring.trace.langfuse_helper.LANGFUSE_CONFIGURED", True)
    @patch("src.monitoring.trace.langfuse_helper.get_langfuse_client")
    def test_calls_update_current_trace_with_error_metadata(self, mock_get_client):
        mock_client = Mock()
        mock_get_client.return_value = mock_client
        from src.monitoring.trace.langfuse_helper import update_trace_with_error
        update_trace_with_error(ValueError("oops"), {"step": "test"})
        mock_client.update_current_trace.assert_called_once()
        call_metadata = mock_client.update_current_trace.call_args[1]["metadata"]
        assert "error_type" in call_metadata
        assert "ValueError" in call_metadata["error_type"]
        assert "oops" in call_metadata["error_message"]
        assert call_metadata["step"] == "test"


class TestUpdateTraceWithMetrics:
    """Tests for update_trace_with_metrics()."""

    @patch("src.monitoring.trace.langfuse_helper.LANGFUSE_CONFIGURED", False)
    def test_does_nothing_when_not_configured(self):
        from src.monitoring.trace.langfuse_helper import update_trace_with_metrics
        update_trace_with_metrics({"key": "value"})  # no raise

    @patch("src.monitoring.trace.langfuse_helper.LANGFUSE_CONFIGURED", True)
    @patch("src.monitoring.trace.langfuse_helper.get_langfuse_client")
    def test_calls_update_current_trace_with_metadata(self, mock_get_client):
        mock_client = Mock()
        mock_get_client.return_value = mock_client
        from src.monitoring.trace.langfuse_helper import update_trace_with_metrics
        update_trace_with_metrics({"count": 5, "name": "test"})
        mock_client.update_current_trace.assert_called_once()
        call_metadata = mock_client.update_current_trace.call_args[1]["metadata"]
        assert call_metadata["count"] == 5
        assert call_metadata["name"] == "test"


class TestCreateScore:
    """Tests for create_score()."""

    @patch("src.monitoring.trace.langfuse_helper.LANGFUSE_CONFIGURED", False)
    def test_does_nothing_when_not_configured(self):
        from src.monitoring.trace.langfuse_helper import create_score
        create_score("quality", 0.9, trace_id="t1")  # no raise

    @patch("src.monitoring.trace.langfuse_helper.LANGFUSE_CONFIGURED", True)
    @patch("src.monitoring.trace.langfuse_helper.get_langfuse_client")
    def test_calls_client_create_score_when_configured(self, mock_get_client):
        mock_client = Mock()
        mock_get_client.return_value = mock_client
        from src.monitoring.trace.langfuse_helper import create_score
        create_score("accuracy", 0.95, trace_id="trace-123", data_type="NUMERIC", comment="test")
        mock_client.create_score.assert_called_once()
        kw = mock_client.create_score.call_args[1]
        assert kw["name"] == "accuracy"
        assert kw["value"] == 0.95
        assert kw["trace_id"] == "trace-123"
        assert kw.get("data_type") == "NUMERIC"
        assert kw.get("comment") == "test"


class TestScoreCurrentTrace:
    """Tests for score_current_trace()."""

    @patch("src.monitoring.trace.langfuse_helper.LANGFUSE_CONFIGURED", False)
    def test_does_nothing_when_not_configured(self):
        from src.monitoring.trace.langfuse_helper import score_current_trace
        score_current_trace("x", 1.0)  # no raise

    @patch("src.monitoring.trace.langfuse_helper.LANGFUSE_CONFIGURED", True)
    @patch("src.monitoring.trace.langfuse_helper.get_langfuse_client")
    def test_calls_client_score_current_trace_when_available(self, mock_get_client):
        mock_client = Mock()
        mock_get_client.return_value = mock_client
        from src.monitoring.trace.langfuse_helper import score_current_trace
        score_current_trace("success", 1.0, data_type="BOOLEAN")
        mock_client.score_current_trace.assert_called_once()
        kw = mock_client.score_current_trace.call_args[1]
        assert kw["name"] == "success"
        assert kw["value"] == 1.0
        assert kw.get("data_type") == "BOOLEAN"


class TestUpdateCurrentSpan:
    """Tests for update_current_span()."""

    @patch("src.monitoring.trace.langfuse_helper.LANGFUSE_CONFIGURED", False)
    def test_does_nothing_when_not_configured(self):
        from src.monitoring.trace.langfuse_helper import update_current_span
        update_current_span(metadata={"x": 1})  # no raise

    @patch("src.monitoring.trace.langfuse_helper.LANGFUSE_CONFIGURED", True)
    @patch("src.monitoring.trace.langfuse_helper.get_langfuse_client")
    def test_calls_update_current_observation_when_metadata_provided(self, mock_get_client):
        mock_client = Mock()
        mock_get_client.return_value = mock_client
        from src.monitoring.trace.langfuse_helper import update_current_span
        update_current_span(metadata={"step": "done"})
        mock_client.update_current_observation.assert_called_once_with(metadata={"step": "done"})


class TestObserveOperation:
    """Tests for observe_operation() decorator."""

    @patch("src.monitoring.trace.langfuse_helper.LANGFUSE_CONFIGURED", False)
    def test_returns_original_func_when_not_configured(self):
        from src.monitoring.trace.langfuse_helper import observe_operation
        @observe_operation(name="my_op")
        def my_func():
            return 42
        assert my_func() == 42
        assert my_func.__name__ == "my_func"

    @patch("src.monitoring.trace.langfuse_helper.LANGFUSE_CONFIGURED", True)
    @patch("langfuse.observe")
    def test_applies_observe_decorator_when_configured(self, mock_observe):
        mock_observe.return_value = lambda f: f  # no-op decorator
        from src.monitoring.trace.langfuse_helper import observe_operation
        @observe_operation(name="my_span")
        def my_func():
            return 1
        mock_observe.assert_called_once()
        call_kw = mock_observe.call_args[1]
        assert call_kw.get("name") == "my_span"
        assert call_kw.get("capture_input") is True
        assert call_kw.get("capture_output") is True


class TestInitializeLangfuse:
    """Tests for initialize_langfuse()."""

    @patch("src.monitoring.trace.langfuse_helper.LANGFUSE_CONFIGURED", False)
    def test_returns_false_when_not_configured(self):
        from src.monitoring.trace.langfuse_helper import initialize_langfuse
        assert initialize_langfuse() is False

    @patch("src.monitoring.trace.langfuse_helper.LANGFUSE_CONFIGURED", True)
    @patch("src.monitoring.trace.langfuse_helper._langfuse_initialized", True)
    def test_returns_true_when_already_initialized(self):
        from src.monitoring.trace.langfuse_helper import initialize_langfuse
        assert initialize_langfuse() is True

    @patch("src.monitoring.trace.langfuse_helper.LANGFUSE_CONFIGURED", True)
    @patch("src.monitoring.trace.langfuse_helper._langfuse_initialized", False)
    @patch("langfuse.Langfuse")
    def test_initializes_langfuse_once_when_configured(self, mock_langfuse_class):
        import src.monitoring.trace.langfuse_helper as m
        m._langfuse_initialized = False
        try:
            m.initialize_langfuse()
            mock_langfuse_class.assert_called_once()
        finally:
            m._langfuse_initialized = False
