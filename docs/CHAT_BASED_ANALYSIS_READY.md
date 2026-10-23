# Future: Chat-Based Analysis (Getting Ready)

**Direction:** Ang analysis flow ay **mababago din** — magiging **chat-based** na (user talks to the agent in chat, asks for analysis, follow-ups, decisions, etc.). **Hindi pa natin i-implement ngayon;** nagre-ready na tayo para hindi mahirap i-integrate later.

See also: [DECISION_MAKING_HUMAN_IN_LOOP_PLAN.md](./DECISION_MAKING_HUMAN_IN_LOOP_PLAN.md) for the main plan.

---

## 11.1 What "Chat-Based Analysis" Implies (Later)

- User may **conversation** with the system: upload or reference a report, then ask "Summarize this," "Should we contact the farmer?," "Schedule a meeting with TPS."
- Analysis at decision-making ay pwedeng **triggered from chat** (e.g. tool: "run_analysis", "get_recommended_actions") instead of only from the current upload → pipeline → result flow.
- Same **outputs** (analysis result, recommended_actions, drafts) dapat usable from both: (1) current pipeline response, (2) chat tool responses.

## 11.2 What to Ready Now (No Build Yet)

So that chat-based analysis is easy to add later:

| Area | Ready now | Why |
|------|-----------|-----|
| **State & models** | Keep `ProcessingState` and report/analysis shapes **independent** of "how" they were triggered (upload vs chat). Same `analysis_result`, `recommended_actions` structure. | Chat can reuse same types and storage. |
| **Agent response shape** | Same contract for "report + recommended_actions" whether from `/agent` upload or (later) from a chat tool that runs the workflow. | Frontend/chat can show analysis and decisions the same way. |
| **Decision node** | Design so it can be run with **state from pipeline** or (later) **state built from chat context** (e.g. report_id + cached analysis). | One decision node for both flows. |
| **Chatbot** | Existing chat already has tools (search, etc.). Later we add tools like "run analysis on this report" or "get recommended actions" that call the same services. | No doc change now; just keep chat as the future entry point for analysis. |
| **APIs** | Decisions API and approval flow use `cache_id` / report identity, not "upload session" only. | Chat can pass same ids when it triggers or shows decisions. |

## 11.3 Summary

- **Ngayon:** Same plan as in the main doc — decision node, recommended_actions, approve-then-send, email/meeting automation. No chat-based analysis yet.
- **Getting ready:** Keep interfaces (state, response shape, decision output, APIs) **reusable** so that when we switch or add **chat-based analysis**, we only add chat tools and maybe a different trigger; we don't redesign the whole analysis or decision flow.

Pag ready na tayo mag-implement ng chat-based analysis, ang dagdag na trabaho ay mostly: **chat tools** that call the same workflow/services and return the same shapes.

---

## How the Existing Nodes Help Chat-Based Flow

The workflow nodes we have are **reusable** for chat-based analysis. Chat can trigger the same logic by building state and calling the workflow (or individual nodes).

| Node | What it does | Use in chat-based flow |
|------|----------------|--------------------------|
| **extract** | PDF/image → extracted markdown, file validation | Chat tool: "Process this file" → run workflow from extract; or "Re-extract from cache" if we store raw file. |
| **validate_content** | LLM checks if content is product demo / trial | Chat: "Is this a valid demo?" → run validate_content with state from cache; or run full pipeline. |
| **analyze** | LLM structured analysis (product, cooperator, metrics, yield, feedback) | Chat: "Summarize this report" / "Get analysis" → return cached analysis or re-run analyze from extracted content. |
| **evaluate_analysis** | Quality gate: is analysis good enough? | Chat: "Check analysis quality" or internal step when re-running from a given stage. |
| **suggest_graphs** | LLM suggests charts (types + chart_data) from analysis | Chat: "Suggest charts for this report" → run with state containing analysis_result; output is graph_suggestions (JSON specs, not images yet). |
| **evaluate_graphs** | Quality gate: are graph suggestions good enough? | Internal step when generating or re-generating graphs from chat. |
| **chunk** | Chunk markdown for vector store | Chat: "Prepare for storage" or when user approves storage from chat. |
| **handle_errors** | Centralized error handling | Same; any path that hits an error goes here. |
| **decision (planned)** | Recommended actions (email tech, email farmer, schedule meeting) | Chat: "What should we do next?" / "Get recommended actions" → run decision node on state with analysis + chunks; return recommended_actions. |

**Ways to use nodes from chat:**

1. **Run full workflow** — Chat tool receives file or `cache_id`; backend runs the same graph (e.g. from extract or from a middle step). Response shape same as current `/agent` (reports + optional recommended_actions).
2. **Run from a step** — If we have cached state (e.g. analysis_result for report X), a chat tool can run only `suggest_graphs` or only `decision_node` and return that step’s output. Requires loading state from cache/DB by report_id or cache_id.
3. **Read-only** — Chat tools that only read: "Get analysis for report X," "Get recommended actions for report X" → no node run, just fetch from cache/API and return. Good for fast answers.

So the **nodes we created are useful for the chat-based flow** — we don’t duplicate logic; we expose the same workflow (or sub-steps) as tools the chat agent can call.

---

## AI-Generated Images: Backend API vs MCP

Two different cases:

### 1. Charts / graphs from our data (no image-gen model)

We already have **graph_suggestions** (JSON: chart type, labels, datasets). To get an **image** (PNG/SVG) and send it to an API:

- **Backend only:** Add a **chart rendering service** that turns `graph_suggestions` into an image (e.g. matplotlib, Plotly, Chart.js headless, or a charting API). Then your backend uploads that image to your API or external service (e.g. storage, email attachment, report builder).
- **MCP not required** for this: the flow is backend → render → HTTP to API. No need for the AI to "create" the image; the AI produced the *data*, and code turns it into an image.

### 2. AI/model creates an image (e.g. diagram, illustration, generated chart)

When the **AI itself** generates an image (e.g. DALL·E, Imagen, or a multimodal model that outputs an image), and we want to **transfer that image to an API** (our backend, storage, or third-party):

- **Option A — Backend calls image-gen API:** Your backend calls an image-generation API (OpenAI images, Gemini imagen, etc.) with a prompt, gets back image URL or bytes, then POSTs that image to your or another API. No MCP. Good when the trigger is "user clicked Generate" or a backend job.
- **Option B — MCP for tool-calling:** Use **MCP (Model Context Protocol)** when the **model/agent** (e.g. in a client or Cursor) is the one generating the image and needs to "hand off" to your system. MCP can expose a **tool** such as:
  - `create_chart_image(spec)` — server renders chart from spec, returns image URL or bytes.
  - `upload_generated_image(image_bytes, target_url)` — client/model has image bytes (e.g. from an image-gen API it called) and wants to send them to your API; MCP server does the HTTP upload.
  So the **model** invokes the tool; the MCP server (your code or a small service) performs the actual transfer to your API. Use this when the **AI is in a different process** (e.g. Cursor, another agent runtime) and you want a standard way for it to "give" the image to your backend/API.

**When to use which:**

| Scenario | Prefer | Why |
|----------|--------|-----|
| Render chart from `graph_suggestions` and send to our API | Backend service | Data already in our state; no model outputting image. |
| Backend job: "Generate summary image for report" | Backend calls image-gen API, then our API | Single control flow in backend. |
| User in chat: "Generate a diagram for this trial" and we want the agent to send it to our API | MCP tool (e.g. `upload_generated_image`) | Agent has the image (or a URL); MCP tool does the transfer. |
| Cursor or external agent produces an image and must push to our API | MCP | Standard protocol for tools; our MCP server implements the API call. |

**Summary:** For **charts from our data** → backend rendering + API call is enough. For **AI-created images** that must be **transferred to an API**, use **MCP** when the image is produced by a model/agent in another process that needs to call a "send this image to API" tool; otherwise a backend step that calls an image-gen API and then your API is enough.
