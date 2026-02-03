"""
Unit tests for prompt management (Langfuse + local fallback).

- Unit tests: mocked, no real Langfuse needed. Test fallback and compile behavior.
- Live test: @pytest.mark.langfuse_live — creates a trace in Langfuse so you can
  see prompt-management usage in the dashboard.

Run only unit tests (default):
  pytest tests/unit/test_prompt_management.py -v

Run live test (see trace in Langfuse dashboard):
  pytest tests/unit/test_prompt_management.py -v -m langfuse_live
"""
import os
import pytest
from unittest.mock import Mock, patch, MagicMock


class TestPromptManagementFallback:
    """When Langfuse is disabled or prompt missing, fallback is used."""

    @patch("src.prompts.prompt_management.LANGFUSE_CONFIGURED", False)
    def test_get_prompt_text_uses_fallback_when_langfuse_disabled(self):
        from src.prompts.prompt_management import get_prompt_text

        result = get_prompt_text(
            "any-name",
            fallback_template="Hello {name}",
            variables={"name": "World"},
        )
        assert result == "Hello World"

    @patch("src.prompts.prompt_management.LANGFUSE_CONFIGURED", False)
    def test_get_system_prompt_for_chat_agent_uses_fallback_when_disabled(self):
        from src.prompts.prompt_management import get_system_prompt_for_chat_agent

        result = get_system_prompt_for_chat_agent()
        assert isinstance(result, str)
        assert len(result) > 100
        assert "Agricultural" in result or "agricultural" in result or "Leads Agri" in result

    @patch("src.prompts.prompt_management.LANGFUSE_CONFIGURED", True)
    @patch("src.prompts.prompt_management._get_prompt_from_langfuse", return_value=None)
    def test_get_prompt_text_uses_fallback_when_langfuse_returns_none(self, mock_get):
        from src.prompts.prompt_management import get_prompt_text

        result = get_prompt_text(
            "agricultural-demo-analysis",
            fallback_template="Data: {markdown_data}",
            variables={"markdown_data": "sample"},
        )
        assert result == "Data: sample"
        mock_get.assert_called_once()
        call_kw = mock_get.call_args[1]
        assert call_kw["type"] == "text"
        assert mock_get.call_args[0][0] == "agricultural-demo-analysis"

    @patch("src.prompts.prompt_management.LANGFUSE_CONFIGURED", True)
    @patch("src.prompts.prompt_management._get_prompt_from_langfuse", return_value=None)
    def test_get_prompt_chat_messages_uses_fallback_when_langfuse_returns_none(self, mock_get):
        from src.prompts.prompt_management import get_prompt_chat_messages

        fallback = "You are a helpful assistant."
        messages = get_prompt_chat_messages(
            "chat-agent-system",
            fallback_system_content=fallback,
            variables={},
        )
        assert len(messages) == 1
        assert messages[0]["role"] == "system"
        assert messages[0]["content"] == fallback
        mock_get.assert_called_once()
        assert mock_get.call_args[1]["type"] == "chat"
    def test_get_prompt_text_empty_variables(self):
        from src.prompts.prompt_management import get_prompt_text

        with patch("src.prompts.prompt_management.LANGFUSE_CONFIGURED", False):
            result = get_prompt_text(
                "x",
                fallback_template="No vars here",
                variables=None,
            )
        assert result == "No vars here"


class TestPromptManagementFromLangfuse:
    """When Langfuse returns a prompt object, it is used (mocked)."""

    @patch("src.prompts.prompt_management.LANGFUSE_CONFIGURED", True)
    @patch("src.prompts.prompt_management._get_prompt_from_langfuse")
    def test_get_prompt_text_uses_langfuse_compiled_when_available(self, mock_get):
        mock_prompt = Mock()
        mock_prompt.compile.return_value = "Compiled from Langfuse: FOO"
        mock_get.return_value = mock_prompt

        from src.prompts.prompt_management import get_prompt_text

        result = get_prompt_text(
            "agricultural-demo-analysis",
            fallback_template="Fallback {markdown_data}",
            variables={"markdown_data": "ignored"},
        )
        assert result == "Compiled from Langfuse: FOO"
        mock_prompt.compile.assert_called_once_with(markdown_data="ignored")

    @patch("src.prompts.prompt_management.LANGFUSE_CONFIGURED", True)
    @patch("src.prompts.prompt_management._get_prompt_from_langfuse")
    def test_get_prompt_chat_messages_uses_langfuse_compiled_list(self, mock_get):
        mock_prompt = Mock()
        mock_prompt.compile.return_value = [
            {"role": "system", "content": "From Langfuse system"},
            {"role": "user", "content": "Hello"},
        ]
        mock_get.return_value = mock_prompt

        from src.prompts.prompt_management import get_prompt_chat_messages

        messages = get_prompt_chat_messages(
            "chat-agent-system",
            fallback_system_content="Fallback",
            variables={},
        )
        assert len(messages) == 2
        assert messages[0]["role"] == "system" and messages[0]["content"] == "From Langfuse system"
        assert messages[1]["role"] == "user" and messages[1]["content"] == "Hello"

    @patch("src.prompts.prompt_management.LANGFUSE_CONFIGURED", True)
    @patch("src.prompts.prompt_management._get_prompt_from_langfuse")
    def test_get_system_prompt_for_chat_agent_uses_langfuse_system_content(self, mock_get):
        mock_prompt = Mock()
        mock_prompt.compile.return_value = [{"role": "system", "content": "Langfuse system prompt"}]
        mock_get.return_value = mock_prompt

        from src.prompts.prompt_management import get_system_prompt_for_chat_agent

        result = get_system_prompt_for_chat_agent()
        assert result == "Langfuse system prompt"

    @patch("src.prompts.prompt_management.LANGFUSE_CONFIGURED", True)
    @patch("src.prompts.prompt_management._get_prompt_from_langfuse")
    def test_get_prompt_text_falls_back_on_compile_error(self, mock_get):
        mock_prompt = Mock()
        mock_prompt.compile.side_effect = ValueError("Missing variable")
        mock_get.return_value = mock_prompt

        from src.prompts.prompt_management import get_prompt_text

        result = get_prompt_text(
            "graph-suggestion",
            fallback_template="Analysis: {analysis_data}",
            variables={"analysis_data": "[]"},
        )
        assert result == "Analysis: []"


# ---------------------------------------------------------------------------
# Live test: creates a trace in Langfuse so you can see prompt management in the dashboard.
# Run: pytest tests/unit/test_prompt_management.py -v -m langfuse_live
# ---------------------------------------------------------------------------

@pytest.mark.langfuse_live
def test_live_prompt_management_appears_in_langfuse_dashboard():
    """
    With LANGFUSE_* set in .env, this test creates a real trace that uses prompt
    management. Open the Langfuse dashboard and look for the trace
    "prompt_management_live_test" to confirm prompt management is wired.
    """
    from pathlib import Path
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).resolve().parent.parent.parent / ".env")

    pk = os.getenv("LANGFUSE_PUBLIC_KEY")
    sk = os.getenv("LANGFUSE_SECRET_KEY")
    if not pk or not sk:
        pytest.skip("LANGFUSE_PUBLIC_KEY and LANGFUSE_SECRET_KEY required for live test")

    from src.monitoring.trace.langfuse_helper import (
        initialize_langfuse,
        get_langfuse_client,
        flush_langfuse,
        get_current_trace_id,
        get_trace_url,
    )
    from src.prompts.prompt_management import (
        get_system_prompt_for_chat_agent,
        get_prompt_text,
    )

    assert initialize_langfuse() is True
    client = get_langfuse_client()
    assert client is not None

    trace_id_inside = None
    url_inside = None
    user_id = "prompt_mgmt_test_user"
    session_id = "prompt_mgmt_test_session"

    with client.start_as_current_observation(as_type="span", name="prompt_management_live_test") as span:
        try:
            client.update_current_trace(
                user_id=user_id,
                session_id=session_id,
                tags=["pytest", "prompt_management", "live_test"],
                metadata={"source": "test_prompt_management.py", "marker": "langfuse_live"},
            )
        except Exception:
            pass

        # Use prompt management (from Langfuse if seeded, else fallback)
        system_prompt = get_system_prompt_for_chat_agent()
        text_prompt = get_prompt_text(
            "agricultural-demo-analysis",
            fallback_template="Input: {markdown_data}",
            variables={"markdown_data": "[live test sample]"},
        )

        span.update(
            input={
                "test": "prompt_management_live",
                "prompt_names_used": ["chat-agent-system", "agricultural-demo-analysis"],
                "system_prompt_length": len(system_prompt),
                "text_prompt_preview": text_prompt[:80] + "..." if len(text_prompt) > 80 else text_prompt,
            },
            metadata={
                "user_id": user_id,
                "session_id": session_id,
                "prompt_management": True,
            },
        )
        trace_id_inside = get_current_trace_id()
        url_inside = get_trace_url()
        span.update(output={"status": "ok", "prompts_retrieved": 2})

    flush_langfuse()

    assert trace_id_inside, "Expected a trace id from live Langfuse span"
    assert url_inside and "/trace/" in url_inside, f"Expected trace URL, got {url_inside!r}"
    # Sa dashboard: hanapin ang trace name "prompt_management_live_test" at tingnan ang input/metadata
    # para makita na nagamit ang prompt management (chat-agent-system at agricultural-demo-analysis).
