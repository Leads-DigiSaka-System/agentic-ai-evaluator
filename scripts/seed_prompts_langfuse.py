"""
Seed Langfuse Prompt Management with current in-code prompts.

Run once (or after changing prompts in code) to push prompts to Langfuse:
  uv run python scripts/seed_prompts_langfuse.py

Requires .env: LANGFUSE_PUBLIC_KEY, LANGFUSE_SECRET_KEY, LANGFUSE_HOST (optional).
Prompts created/updated:
- chat-agent-system (chat) — system message for agricultural chat agent
- agricultural-demo-analysis (text) — variable: markdown_data
- graph-suggestion (text) — variable: analysis_data
- content-validation (text) — variable: extracted_content
"""
import sys
from pathlib import Path

root = Path(__file__).resolve().parent.parent
if str(root) not in sys.path:
    sys.path.insert(0, str(root))

from dotenv import load_dotenv
load_dotenv(root / ".env")

from src.monitoring.trace.langfuse_helper import (
    initialize_langfuse,
    get_langfuse_client,
    flush_langfuse,
)
from src.chatbot.prompts.system_prompt import get_chat_agent_system_prompt
from src.prompts.analysis_template import analysis_prompt_template_structured
from src.prompts.graph_suggestion_template import graph_suggestion_prompt
from src.prompts.prompt_template import content_validation_template


def _to_langfuse_template(template_str: str, variable_names: list[str]) -> str:
    """Convert LangChain-style {var} to Langfuse {{var}} for the given variable names."""
    out = template_str
    for name in variable_names:
        out = out.replace("{" + name + "}", "{{" + name + "}}")
    return out


def main():
    if not initialize_langfuse():
        print("Langfuse not configured. Set LANGFUSE_PUBLIC_KEY and LANGFUSE_SECRET_KEY in .env")
        sys.exit(1)

    client = get_langfuse_client()
    if not client:
        print("Could not get Langfuse client.")
        sys.exit(1)

    labels = ["production"]

    # 1. Chat agent system prompt (chat type)
    system_content = get_chat_agent_system_prompt()
    client.create_prompt(
        name="chat-agent-system",
        type="chat",
        prompt=[{"role": "system", "content": system_content}],
        labels=labels,
    )
    print("Created/updated prompt: chat-agent-system (chat)")

    # 2. Agricultural demo analysis (text, variable: markdown_data)
    analysis_tpl = analysis_prompt_template_structured()
    analysis_prompt_str = _to_langfuse_template(analysis_tpl.template, ["markdown_data"])
    client.create_prompt(
        name="agricultural-demo-analysis",
        type="text",
        prompt=analysis_prompt_str,
        labels=labels,
    )
    print("Created/updated prompt: agricultural-demo-analysis (text)")

    # 3. Graph suggestion (text, variable: analysis_data)
    graph_tpl = graph_suggestion_prompt()
    graph_prompt_str = _to_langfuse_template(graph_tpl.template, ["analysis_data"])
    client.create_prompt(
        name="graph-suggestion",
        type="text",
        prompt=graph_prompt_str,
        labels=labels,
    )
    print("Created/updated prompt: graph-suggestion (text)")

    # 4. Content validation (text, variable: extracted_content)
    validation_tpl = content_validation_template()
    validation_prompt_str = _to_langfuse_template(validation_tpl.template, ["extracted_content"])
    client.create_prompt(
        name="content-validation",
        type="text",
        prompt=validation_prompt_str,
        labels=labels,
    )
    print("Created/updated prompt: content-validation (text)")

    flush_langfuse()
    print("Done. Prompts seeded to Langfuse (label: production).")
    print("You can edit and version them in Langfuse UI > Prompt Management.")


if __name__ == "__main__":
    main()
