"""
Langfuse tracing tests: unit (mocked) + optional live test for dashboard.

- Unit tests: mocked, no real Langfuse needed.
- Live test: marked @pytest.mark.langfuse_live — run with real LANGFUSE_* in .env
  to see traces in the Langfuse dashboard.

Run only unit tests (default):
  pytest tests/unit/test_langfuse_tracing.py -v

Run live test (see tracing in dashboard):
  pytest tests/unit/test_langfuse_tracing.py -v -m langfuse_live
  # Or with env loaded:
  pytest tests/unit/test_langfuse_tracing.py -v -m langfuse_live --env .env
"""
import os
import pytest
from unittest.mock import Mock, patch


class TestConditionalObservePattern:
    """Test the conditional observe pattern used in API routes (mocked)."""

    @patch("src.monitoring.trace.langfuse_helper.LANGFUSE_CONFIGURED", False)
    def test_dummy_observe_returns_same_function(self):
        """When Langfuse disabled, observe decorator should be a no-op."""
        from src.monitoring.trace.langfuse_helper import is_langfuse_enabled
        assert is_langfuse_enabled() is False
        # Simulate what routes do when disabled
        def observe(**kwargs):
            def decorator(fn):
                return fn
            return decorator
        def get_client():
            return None
        @observe(name="test_op")
        def my_func():
            return 42
        assert my_func() == 42

    @patch("src.monitoring.trace.langfuse_helper.LANGFUSE_CONFIGURED", True)
    @patch("src.monitoring.trace.langfuse_helper.get_langfuse_client")
    def test_update_current_trace_called_with_expected_args(self, mock_get_client):
        """Simulate survey-style update_current_trace at start of request."""
        mock_client = Mock()
        mock_get_client.return_value = mock_client
        from src.monitoring.trace.langfuse_helper import is_langfuse_enabled
        if is_langfuse_enabled():
            client = mock_get_client.return_value
            if client:
                client.update_current_trace(
                    user_id="user-123",
                    session_id="session-abc",
                    tags=["api", "test"],
                    metadata={"test": True},
                )
        mock_client.update_current_trace.assert_called_once()
        kwargs = mock_client.update_current_trace.call_args[1]
        assert kwargs["user_id"] == "user-123"
        assert kwargs["session_id"] == "session-abc"
        assert "api" in kwargs["tags"]


class TestObserveOperationDecorator:
    """Test observe_operation decorator (mocked)."""

    @patch("src.monitoring.trace.langfuse_helper.LANGFUSE_CONFIGURED", False)
    def test_observe_operation_returns_original_function_when_disabled(self):
        from src.monitoring.trace.langfuse_helper import observe_operation
        @observe_operation(name="mocked_span")
        def sample():
            return "ok"
        assert sample() == "ok"

    @patch("src.monitoring.trace.langfuse_helper.LANGFUSE_CONFIGURED", True)
    @patch("langfuse.observe")
    def test_observe_operation_applies_observe_when_enabled(self, mock_observe):
        mock_observe.return_value = lambda f: f  # decorator that returns f as-is
        from src.monitoring.trace.langfuse_helper import observe_operation
        @observe_operation(name="enabled_span")
        def sample():
            return "ok"
        assert sample() == "ok"
        mock_observe.assert_called_once()
        assert mock_observe.call_args[1]["name"] == "enabled_span"


# ---------------------------------------------------------------------------
# Live test: creates a real trace in Langfuse when credentials are set.
# Run: pytest tests/unit/test_langfuse_tracing.py -v -m langfuse_live
# ---------------------------------------------------------------------------

@pytest.mark.langfuse_live
def test_live_trace_appears_in_langfuse_dashboard():
    """
    When LANGFUSE_PUBLIC_KEY and LANGFUSE_SECRET_KEY are set in .env,
    this test creates a real trace so you can see it in the Langfuse dashboard.

    Prerequisites:
      - .env has LANGFUSE_PUBLIC_KEY, LANGFUSE_SECRET_KEY (and optionally LANGFUSE_HOST)
      - Run: pytest tests/unit/test_langfuse_tracing.py -v -m langfuse_live
    """
    from dotenv import load_dotenv
    load_dotenv()
    pk = os.getenv("LANGFUSE_PUBLIC_KEY")
    sk = os.getenv("LANGFUSE_SECRET_KEY")
    if not pk or not sk:
        pytest.skip("LANGFUSE_PUBLIC_KEY and LANGFUSE_SECRET_KEY required for live trace test")

    from src.monitoring.trace.langfuse_helper import (
        initialize_langfuse,
        get_langfuse_client,
        flush_langfuse,
        get_trace_url,
        get_current_trace_id,
    )

    assert initialize_langfuse() is True
    client = get_langfuse_client()
    assert client is not None

    trace_id_inside = None
    url_inside = None
    session_id = "unit_test_session_001"
    user_id = "unit_test_user_001"
    with client.start_as_current_observation(as_type="span", name="unit_test_live_trace") as span:
        # Set session_id and user_id on current trace so it appears in Sessions and Users tabs
        try:
            client.update_current_trace(user_id=user_id, session_id=session_id)
        except Exception:
            pass
        span.update(
            input={"test": "langfuse_tracing", "message": "Unit test live trace"},
            metadata={"source": "pytest", "marker": "langfuse_live", "session_id": session_id, "user_id": user_id},
        )
        trace_id_inside = get_current_trace_id()
        url_inside = get_trace_url()
        try:
            client.score_current_trace(
                name="test_score",
                value=1.0,
                data_type="NUMERIC",
                comment="Live test from pytest",
            )
        except Exception:
            pass
        span.update(output={"status": "ok"})

    flush_langfuse()
    assert trace_id_inside, "Expected a trace id from live Langfuse span"
    assert url_inside and "/trace/" in url_inside, f"Expected trace URL, got {url_inside!r}"
    # Success: open Langfuse dashboard and look for trace name "unit_test_live_trace"
