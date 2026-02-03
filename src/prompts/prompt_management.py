"""
Prompt management via Langfuse with local fallback.

When Langfuse is configured and the prompt exists in Langfuse, we fetch and use it
(optionally by label or version). Otherwise we use in-code prompts so the app works
without Langfuse or before prompts are seeded.

Prompt names used in this project (must match Langfuse or seed script):
- chat-agent-system (type: chat) — system message for the agricultural chat agent
- agricultural-demo-analysis (type: text) — variable: markdown_data
- graph-suggestion (type: text) — variable: analysis_data
- content-validation (type: text) — variable: extracted_content
- form-extraction-handwritten (type: text) — no variables (or document context)
- form-extraction-structured (type: text) — no variables
- synthesizer (type: text) — variables: retrieved_context, user_query, chunk_count
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from src.core.config import LANGFUSE_CONFIGURED
from src.monitoring.trace.langfuse_helper import get_langfuse_client, initialize_langfuse
from src.shared.logging.clean_logger import get_clean_logger

logger = get_clean_logger(__name__)


def _get_prompt_from_langfuse(
    name: str,
    *,
    label: Optional[str] = None,
    version: Optional[int] = None,
    type: Optional[str] = None,
):
    """Fetch prompt from Langfuse. Returns None if disabled, missing, or error."""
    if not LANGFUSE_CONFIGURED:
        return None
    try:
        initialize_langfuse()
        client = get_langfuse_client()
        if not client:
            return None
        kwargs = {}
        if label is not None:
            kwargs["label"] = label
        if version is not None:
            kwargs["version"] = version
        if type is not None:
            kwargs["type"] = type
        return client.get_prompt(name, **kwargs)
    except Exception as e:
        logger.debug(f"Langfuse get_prompt {name} failed: {e}")
        return None


def get_prompt_text(
    name: str,
    fallback_template: str,
    variables: Optional[Dict[str, Any]] = None,
    *,
    label: Optional[str] = None,
    version: Optional[int] = None,
) -> str:
    """
    Get a text prompt: from Langfuse if available, else format fallback_template with variables.

    variables: dict for template format (e.g. {"markdown_data": "..."}).
    fallback_template: must use {var} placeholders (single brace) for .format(**variables).
    """
    variables = variables or {}
    prompt_obj = _get_prompt_from_langfuse(name, label=label, version=version, type="text")
    if prompt_obj is not None:
        try:
            return prompt_obj.compile(**variables)
        except Exception as e:
            logger.warning(f"Langfuse prompt {name} compile failed, using fallback: {e}")
    try:
        return fallback_template.format(**variables)
    except KeyError as e:
        logger.warning(f"Fallback template for {name} missing variable: {e}")
        return fallback_template


def get_prompt_chat_messages(
    name: str,
    fallback_system_content: str,
    variables: Optional[Dict[str, Any]] = None,
    *,
    label: Optional[str] = None,
    version: Optional[int] = None,
) -> List[Dict[str, str]]:
    """
    Get chat messages (e.g. [{"role": "system", "content": "..."}]) from Langfuse or fallback.

    For chat prompts in Langfuse, type must be "chat". Fallback is a single system message.
    """
    variables = variables or {}
    prompt_obj = _get_prompt_from_langfuse(name, label=label, version=version, type="chat")
    if prompt_obj is not None:
        try:
            compiled = prompt_obj.compile(**variables)
            if isinstance(compiled, list) and len(compiled) > 0:
                return compiled
            if isinstance(compiled, str):
                return [{"role": "system", "content": compiled}]
        except Exception as e:
            logger.warning(f"Langfuse chat prompt {name} compile failed, using fallback: {e}")
    return [{"role": "system", "content": fallback_system_content.format(**variables)}]


def get_system_prompt_for_chat_agent(
    *,
    label: Optional[str] = None,
    version: Optional[int] = None,
) -> str:
    """
    Get the chat agent system prompt from Langfuse (name: chat-agent-system) or local default.
    """
    from src.chatbot.prompts.system_prompt import get_chat_agent_system_prompt

    fallback = get_chat_agent_system_prompt()
    messages = get_prompt_chat_messages(
        "chat-agent-system",
        fallback_system_content=fallback,
        variables={},
        label=label,
        version=version,
    )
    if not messages:
        return fallback
    for m in messages:
        if m.get("role") == "system" and m.get("content"):
            return m["content"]
    return fallback
