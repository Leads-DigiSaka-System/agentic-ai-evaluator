# Prompt Management (Langfuse)

The app uses **Langfuse Prompt Management** with a **local fallback**: if a prompt is not in Langfuse (or Langfuse is not configured), the in-code prompt is used.

## How it works

- **`src/prompts/prompt_management.py`**  
  - `get_prompt_text(name, fallback_template, variables)` – text prompts (analysis, graph suggestion, validation).  
  - `get_prompt_chat_messages(name, fallback_system_content, variables)` – chat prompts.  
  - `get_system_prompt_for_chat_agent()` – chat agent system prompt (name: `chat-agent-system`).

- **Where prompts are used**
  - **Chat agent**: system prompt from Langfuse `chat-agent-system` (chat) or local `get_chat_agent_system_prompt()`.
  - **Analysis node**: `agricultural-demo-analysis` (text, variable: `markdown_data`).
  - **Graph suggestion node**: `graph-suggestion` (text, variable: `analysis_data`).
  - **Validation node**: `content-validation` (text, variable: `extracted_content`).

## One-time seed (recommended)

To create/update prompts in Langfuse from the current in-code prompts:

```bash
uv run python scripts/seed_prompts_langfuse.py
```

Requires `.env`: `LANGFUSE_PUBLIC_KEY`, `LANGFUSE_SECRET_KEY`, and optionally `LANGFUSE_HOST`.  
This creates/updates prompts with label **production** so the app will use them on the next fetch.

## Using Langfuse UI

1. Open **Prompt Management** in the Langfuse dashboard.
2. Edit prompts (e.g. `chat-agent-system`, `agricultural-demo-analysis`).  
   - Use **Variables** with double braces, e.g. `{{markdown_data}}`, `{{analysis_data}}`, `{{extracted_content}}`.
3. Save; new versions are created. Assign the **production** label to the version you want the app to use.
4. The app uses **production** by default; no code change or deploy needed.

## Versioning and labels

- **production** – used by the app when no label/version is specified.
- **latest** – points to the newest version (optional).
- You can use custom labels (e.g. `staging`) and pass `label="staging"` in code if you add that option later.

## Optional: fetch by version or label

In code you can pass `label` or `version` to the prompt helpers (e.g. for A/B tests or staging):

```python
from src.prompts.prompt_management import get_system_prompt_for_chat_agent

# Production (default)
system_prompt = get_system_prompt_for_chat_agent()

# Specific label
system_prompt = get_system_prompt_for_chat_agent(label="staging")

# Specific version
system_prompt = get_system_prompt_for_chat_agent(version=2)
```

## Caching

Langfuse SDK caches prompts client-side, so repeated fetches do not add latency. After you update a prompt in the UI and set **production**, the app will pick up the new version on the next fetch (subject to cache TTL).
