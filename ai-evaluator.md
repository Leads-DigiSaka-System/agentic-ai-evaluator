# AI Evaluator

## Complete Project Explanation and Architecture

This document explains what the `agentic-ai-evaluator` project currently does, why it is considered agentic, how its components communicate, where data is stored, how RAG works in this project, and which capabilities are current versus planned.

The explanations below are based on the current source code. Future ideas are labeled clearly so they are not confused with implemented features.

---

## 1. Executive Summary

The AI Evaluator is a backend system for processing and analyzing agricultural product demo or field-trial reports.

Its current primary input is a PDF or image. It:

1. validates the uploaded file;
2. extracts its content using Gemini;
3. validates whether the content is an agricultural demo or trial;
4. converts the extracted content into a structured agricultural analysis;
5. evaluates the quality of that analysis;
6. retries the analysis when the quality is insufficient;
7. generates chart suggestions and chart data;
8. evaluates the chart suggestions and retries them when needed;
9. chunks the extracted content;
10. caches the complete result for review;
11. stores the approved chunks and analysis in Qdrant;
12. exposes search and chat APIs over the stored reports.

The project is more than a one-shot prompt because it has:

- a stateful LangGraph workflow;
- multiple specialized nodes;
- LLM-based quality decisions;
- deterministic routing based on those decisions;
- controlled retries;
- tools for search, comparison, trends, statistics, and report retrieval;
- memory for multi-turn chat;
- background processing;
- storage approval;
- observability through Langfuse.

The current system performs workflow decisions such as:

- Is the document valid?
- Is the analysis good enough?
- Should analysis be retried?
- Are the graph suggestions good enough?
- Should graph generation be retried?
- Can processing continue or should it stop?

It does **not yet** implement business-action decisions such as automatically contacting the technical team, emailing farmers, or scheduling meetings. Those are planned extensions, not current behavior.

---

## 2. The Problem the Project Solves

Agricultural demo reports can arrive as:

- digital PDFs;
- scanned PDFs;
- photographs of forms;
- handwritten or partially handwritten reports;
- files containing one or multiple trial reports.

Manually processing these files is difficult because the information is often inconsistent. Product names, dates, locations, treatments, measurements, cooperator feedback, and trial results may appear in different places or formats.

The AI Evaluator standardizes this process by converting raw documents into:

- validated trial content;
- structured report data;
- calculated or extracted performance information;
- data-quality indicators;
- executive summaries;
- recommendations and observations;
- chart-ready specifications;
- searchable vector records;
- conversational answers grounded in stored reports.

---

## 3. Current Scope

### 3.1 Implemented now

- PDF and image upload.
- File-format and file-integrity validation.
- Gemini-based extraction from PDFs and images.
- Single-report and multi-report handling.
- LLM content validation.
- Structured agricultural trial analysis.
- Analysis quality evaluation through CrewAI multi-agent evaluation when enabled (`USE_CREWAI = True` in `src/Agents/output_evaluator.py`), with single-agent fallback.
- Automatic analysis retry, with a limit.
- Chart suggestion generation as JSON chart specifications.
- Chart suggestion quality evaluation.
- Automatic graph regeneration, with a limit.
- Markdown chunking.
- Synchronous processing.
- Redis/ARQ background processing.
- Temporary Redis cache for completed outputs.
- Human approval before permanent Qdrant storage on the `/api/agent` → Redis cache → `/api/storage/approve-simple` path. The legacy `/api/upload-file-product-demo` endpoint still writes form chunks to Qdrant immediately and bypasses approval.
- Two Qdrant collections: content chunks and structured analyses.
- Dense semantic search over the analysis collection for chat tools and `/api/analysis-search`. Form chunks are stored with dense + sparse vectors, but no current API or chat tool queries that hybrid form index.
- Chat agent with 33 data tools (memory helper tools exist in source but are not currently bound into `_get_all_tools()`).
- PostgreSQL-backed conversation memory.
- API-key security, rate limits, cooperative filtering, and user tracking.
- Langfuse traces, sessions, metadata, and scores.
- Docker support for the API and worker; infrastructure services can run separately.

### 3.2 Not implemented yet

- A business decision node for contacting technical teams, TPS, or farmers.
- Automatic email sending.
- Automatic meeting scheduling.
- Human approval for emails or meetings.
- Actual PNG/SVG rendering of chart suggestions.
- An image-generation model for report illustrations.
- Replacement of the document input with a business SQL/database API as the main evaluator input.
- A dedicated external MCP server for this project.

### 3.3 Important distinction

The project currently has **quality decision-making**, not yet **business-action decision-making**.

Quality decision-making controls the workflow:

```text
analysis is weak -> retry analysis
graphs are weak -> regenerate graph suggestions
content is invalid -> stop with an error
output is acceptable -> continue
```

Future business-action decision-making would look like:

```text
trial result needs technical review -> recommend contacting technical team
farmer feedback contains concerns -> recommend follow-up
multiple stakeholders are needed -> recommend a meeting
```

---

## 4. High-Level System Architecture

```text
                              CLIENTS
                  Web UI / Mobile App / API Client
                                  |
                                  v
                     +-------------------------+
                     |      FastAPI API        |
                     |       main.py           |
                     +-------------------------+
                       |        |         |
              upload   |        | search  | chat
                       v        v         v
              +-----------+  +------+  +----------------+
              | /api/agent|  |Search|  | Chat Agent     |
              +-----------+  +------+  | + 33 tools     |
                    |           |       +----------------+
                    |           |              |
        +-----------+-----------+              |
        |           |                          v
        |           v               +-----------------------------+
        |    dense analysis search  | Qdrant analysis collection |
        |                           +-----------------------------+
        |
        +-- background=false ------------------+
        |                                      |
        | background=true                      |
        v                                      v
 +---------------+       +------------------+  |
 | Redis / ARQ   |------>| ARQ Worker       |  |
 | job queue     |       | workers.py       |  |
 +---------------+       +------------------+  |
                                 |             |
                                 +------+------+
                                        v
                     +-------------------------+
                     | LangGraph Workflow      |
                     | extract -> validate ->  |
                     | analyze -> evaluate ->  |
                     | graphs -> evaluate ->   |
                     | chunk                   |
                     +-------------------------+
                                 |
                                 v
                      +----------------------+
                      | Redis result cache   |
                      | pending_storage      |
                      +----------------------+
                                 |
                         user approves/rejects
                                 |
                                 v
                     +--------------------------+
                     | Storage Service          |
                     +--------------------------+
                       |                      |
                       v                      v
             +------------------+   +---------------------+
             | Qdrant form      |   | Qdrant analysis    |
             | chunk collection |   | collection          |
             +------------------+   +---------------------+

Both sync and background `/api/agent` paths run the same LangGraph workflow.
Background only changes enqueue/poll; sync invokes the workflow in-process.

 Supporting services:
 - Gemini / OpenRouter: LLM calls
 - Embedding model: dense vectors
 - TF-IDF: sparse vectors for content chunks on write
 - PostgreSQL: conversation memory
 - Langfuse: observability, traces, sessions, and scores
```

---

## 5. Architectural Layers

### 5.1 API layer

Location: `src/api/`

Responsibilities:

- exposes HTTP endpoints;
- validates requests;
- applies API-key authentication;
- applies rate limits;
- reads `X-User-ID` and `X-Cooperative`;
- invokes workflows, services, search, and chat;
- returns HTTP responses and user-friendly errors.

### 5.2 Domain layer

Location: `src/domain/workflow/`

Responsibilities:

- defines `ProcessingState`;
- defines request and response models;
- establishes the data contract shared by workflow nodes and services.

### 5.3 Workflow layer

Location: `src/workflow/`

Responsibilities:

- defines the LangGraph state machine;
- registers workflow nodes;
- routes execution conditionally;
- controls retries;
- handles errors.

### 5.4 Ingestion layer

Location: `src/ingestion/`

Responsibilities:

- validates PDF and image files;
- saves uploads to temporary files;
- extracts text/markdown with Gemini;
- detects single versus multiple reports;
- prepares workflow state.

### 5.5 Agent and LLM layer

Locations:

- `src/Agents/` (import path `src.agents`)
- `src/shared/llm_helper.py`
- `src/shared/llm_factory.py`
- `src/shared/gemini_helper.py`
- `src/shared/openrouter_helper.py`

Responsibilities:

- invokes Gemini or OpenRouter;
- evaluates workflow outputs;
- creates structured JSON from LLM responses;
- supports Langfuse instrumentation.

### 5.6 Chat layer

Location: `src/chatbot/`

Responsibilities:

- exposes a conversational interface;
- chooses and invokes tools;
- searches stored reports;
- performs report comparison and trend operations;
- loads and saves conversation history;
- produces Taglish, Filipino, or English responses.

### 5.7 Service layer

Location: `src/services/`

Responsibilities:

- caches completed outputs in Redis;
- prepares storage payloads;
- stores chunks and structured analysis;
- separates workflow processing from permanent storage.

### 5.8 Infrastructure layer

Location: `src/infrastructure/`

Responsibilities:

- Qdrant connection, insertion, listing, deletion, and retrieval;
- dense and sparse embeddings;
- Redis connection pooling;
- PostgreSQL connection pooling and memory schemas.

### 5.9 Monitoring layer

Location: `src/monitoring/`

Responsibilities:

- initializes Langfuse;
- groups operations by session and user;
- records workflow, search, and storage scores;
- flushes traces during request completion and shutdown.

---

## 6. Main File-Processing Flow

### 6.1 Request

Primary endpoint:

```http
POST /api/agent
```

Required or expected context:

- multipart file;
- `X-API-Key`;
- `X-User-ID`;
- `X-Cooperative`;
- optional `background=true`;
- optional `priority=high|normal|low` for background processing.

Supported file formats include:

- PDF;
- PNG;
- JPG;
- JPEG.

### 6.2 Initial API processing

`src/api/routes/agent.py`:

1. reads the uploaded bytes;
2. validates the filename and content;
3. creates a Langfuse session ID;
4. associates the request with the user;
5. chooses synchronous or background execution.

### 6.3 Synchronous execution

With `background=false`:

```text
/api/agent
  -> MultiReportHandler.process_multi_report_pdf()
  -> LangGraph workflow
  -> normalize response
  -> save output temporarily in Redis
  -> return result + cache_id
```

### 6.4 Background execution

With `background=true`:

```text
/api/agent
  -> enqueue process_file_background in Redis
  -> return job_id immediately
  -> ARQ worker processes the file
  -> worker writes progress to Redis
  -> worker caches completed output
  -> client polls /api/progress/{job_id}
```

The evaluator Redis instance is configured through `REDIS_URL` or:

```env
REDIS_HOST=localhost
REDIS_PORT=6380
REDIS_DB=0
```

The ARQ worker is started with:

```powershell
uv run arq src.workers.workers.WorkerSettings
```

### 6.5 Single versus multiple reports

`MultiReportHandler` extracts the uploaded file and tries to split it into individual reports.

Splitting uses:

- the explicit separator `### REPORT_END ###`; or
- multiple level-one Markdown headings; or
- one complete report if no clear separator exists.

For a single report, the full workflow runs over the original file.

For multiple reports, extraction happens once. Each report's pre-extracted Markdown is passed into its own workflow state. Cross-report graph suggestions may also be generated.

---

## 7. LangGraph Workflow Architecture

Definition: `src/workflow/graph.py`

```text
START
  |
  v
extract
  |
  +-- fatal extraction/file error --> handle_errors --> END
  |
  v
validate_content
  |
  +-- not an agricultural demo --> handle_errors --> END
  |
  v
analyze
  |
  +-- fatal analysis error --> handle_errors --> END
  |
  v
evaluate_analysis
  |
  +-- retry required and attempts < 2 --> analyze
  |
  v
suggest_graphs
  |
  +-- fatal graph error --> handle_errors --> END
  |
  v
evaluate_graphs
  |
  +-- retry required and attempts < 2 --> suggest_graphs
  |
  v
chunk
  |
  +-- no chunks --> handle_errors --> END
  |
  v
END
```

Storage is intentionally outside the graph.

### 7.1 `extract`

Files:

- `src/workflow/nodes/nodes.py`
- `src/ingestion/form_extractor.py`
- `src/ingestion/file_validator.py` (format/integrity during extract)

API-level upload checks use `src/shared/file_validator.py` before the workflow starts.

Responsibilities:

- validate the uploaded format inside the extract path;
- extract PDF or image content through Gemini;
- produce Markdown;
- collect file metadata;
- support pre-extracted Markdown for multi-report files;
- record validation and errors in state.

Outputs:

- `extracted_markdown`;
- `file_validation`;
- `metadata`;
- errors when applicable.

### 7.2 `validate_content`

File: `src/workflow/nodes/validation_node.py`

Responsibilities:

- determine whether content is a product demo or trial report;
- reject invoices, letters, unrelated documents, and invalid content;
- provide confidence, reasoning, detected elements, and feedback.

Outputs:

- `is_valid_content`;
- `content_validation`.

### 7.3 `analyze`

Files:

- `src/workflow/nodes/nodes.py`
- `src/workflow/nodes/analysis.py`
- `src/prompts/analysis_template.py`

Responsibilities:

- identify the form type;
- send extracted content to Gemini;
- request structured JSON;
- normalize the result;
- generate a fallback deterministic summary if the LLM omits one.

Important analysis fields include:

- status;
- product category;
- metrics detected;
- measurement intervals;
- data quality;
- basic information;
- treatment comparison;
- performance analysis;
- statistical assessment;
- trend analysis;
- yield analysis;
- cooperator feedback;
- risk factors;
- opportunities;
- recommendations;
- executive summary.

### 7.4 `evaluate_analysis`

Files:

- `src/workflow/nodes/evaluation_node.py`
- `src/Agents/output_evaluator.py`
- `src/Agents/evaluation_crew.py`

Responsibilities:

- inspect the generated analysis;
- when CrewAI is available and enabled, run a four-agent evaluation crew:
  - Document Context Analyst;
  - Output Quality Evaluator;
  - Processing Strategy Advisor;
  - Evaluation Decision Coordinator;
- return confidence, feedback, decision, and issue type;
- distinguish fixable analysis problems from source limitations;
- set `needs_reanalysis`;
- increment retry attempts;
- fall back to a safe proceed/store result if evaluation fails.

Possible issue types:

- `fixable_analysis`;
- `source_limitation`;
- `graph_issue`;
- `no_issue`.

A source limitation does not automatically mean the workflow failed. It can mean that information is genuinely absent from the uploaded report.

Important current detail:

- Analysis and graph evaluation share one `evaluation_attempts` counter. Analysis retries can reduce the remaining retry budget for graph regeneration.

### 7.5 `suggest_graphs`

Files:

- `src/workflow/nodes/graph_suggestion_node.py`
- `src/prompts/graph_suggestion_template.py`

Responsibilities:

- read structured analysis;
- suggest appropriate visualizations;
- produce chart titles, types, descriptions, labels, datasets, and data sources;
- keep the output grounded in analysis values.

Important limitation:

> The current output is a chart specification in JSON. The project does not yet render this specification into a PNG, JPEG, or SVG image.

### 7.6 `evaluate_graphs`

Uses the same evaluation node but detects that graph suggestions now exist.

Responsibilities:

- evaluate chart relevance, completeness, data quality, and usefulness;
- set `needs_regraph`;
- retry graph generation if needed;
- stop retrying after the configured workflow limit.

### 7.7 `chunk`

Files:

- `src/workflow/nodes/nodes.py`
- `src/formatter/chunking.py`

Responsibilities:

- split extracted Markdown into storage/search chunks;
- calculate chunk metrics;
- prepare content for embedding and Qdrant insertion.

### 7.8 `handle_errors`

Responsibilities:

- preserve accumulated errors;
- log each error;
- terminate the workflow safely.

---

## 8. Why the Project Is Agentic

The evaluator is agentic because the LLM does not merely produce one final text response.

The system has:

1. **State** — every node reads and updates shared `ProcessingState`.
2. **Specialized capabilities** — extraction, validation, analysis, evaluation, graph generation, and chunking.
3. **Quality judgment** — an evaluation agent judges whether output is acceptable.
4. **Conditional routing** — routers select the next step from state flags.
5. **Retries** — analysis and graph generation can repeat.
6. **Tool use** — the chat agent selects among 33 tools.
7. **Memory** — chat history is stored and loaded by thread.
8. **External systems** — it interacts with Gemini/OpenRouter, Qdrant, Redis, PostgreSQL, and Langfuse.

The architecture deliberately separates:

```text
LLM judgment: "Is this output good enough?"
                       |
                       v
deterministic router: "Which node should run next?"
```

This separation makes routing easier to test and prevents the LLM from directly controlling arbitrary code execution.

---

## 9. Processing State

Main model: `src/domain/workflow/state.py`

The workflow state contains four groups of information.

### 9.1 Input

- `file_path`;
- `file_name`;
- `file_content`;
- `_tracking_id`;
- `_user_id`.

The storage route also injects `_cooperative` when rebuilding state for permanent storage.

### 9.2 Outputs

- `extracted_markdown`;
- `form_type`;
- `analysis_result`;
- `graph_suggestions`;
- `chunks`.

### 9.3 Workflow controls

- `current_step`;
- `errors`;
- `file_validation`;
- `is_valid_content`;
- `content_validation`;
- `output_evaluation`;
- `needs_reanalysis`;
- `needs_regraph`;
- `evaluation_attempts`;
- `last_evaluation_summary`.

### 9.4 Storage controls

- `storage_approved`;
- `storage_prepared`;
- `storage_data`;
- `storage_preview`;
- `storage_approval_request`.

---

## 10. Output Structure

A processed report returns information similar to:

```json
{
  "status": "success",
  "total_reports": 1,
  "reports": [
    {
      "report_number": 1,
      "file_name": "trial-report.pdf",
      "form_id": "",
      "form_type": "agricultural demo form",
      "extracted_content": "...",
      "analysis": {
        "basic_info": {},
        "performance_analysis": {},
        "yield_analysis": {},
        "cooperator_feedback": {},
        "recommendations": [],
        "executive_summary": "..."
      },
      "graph_suggestions": {
        "suggested_charts": []
      },
      "chunks": [],
      "processing_metrics": {},
      "errors": [],
      "validation": {},
      "storage_status": "ready_for_approval"
    }
  ],
  "cross_report_analysis": {},
  "analysis_storage_status": "ready_for_approval",
  "cache_id": "..."
}
```

The exact analysis fields vary according to the agricultural form and available data.

---

## 11. Cache and Storage Approval

For the main `/api/agent` path, completed analysis is **not immediately stored permanently**. The legacy `/api/upload-file-product-demo` endpoint is different: it extracts, chunks, and inserts form chunks into Qdrant immediately, with no LangGraph analysis and no storage approval.

### 11.1 Temporary cache

File: `src/services/cache_service.py`

The result is saved to Redis with:

- a generated `cache_id`;
- creation timestamp;
- complete agent response;
- status `pending_storage`;
- optional session ID;
- user ID;
- automatic TTL.

User-scoped Redis keys have this form:

```text
agent:cache:{user_id}:{cache_id}
```

### 11.2 Approval endpoint

```http
POST /api/storage/approve-simple
```

Body:

```json
{
  "cache_id": "...",
  "approved": true
}
```

If rejected:

- the result is not stored;
- the cache is deleted;
- Langfuse records the rejection.

If approved:

- cache ownership is verified;
- report data is converted back into storage state;
- `StorageService` prepares chunk and analysis payloads;
- both Qdrant collections are written;
- for a successful single-report store, the cache is deleted immediately;
- for multi-report batch approval, the route currently returns `status: completed`, while cache deletion only triggers on `status == "success"`, so successful batch caches can remain until TTL expiry.

Chunk and analysis inserts are separate writes. They are not transactional; one can succeed while the other fails.

This is the current human-in-the-loop control in the project. It applies to permanent storage, not yet to email or meeting actions.

---

## 12. Qdrant and RAG Architecture

Qdrant is the project's vector database.

### 12.1 Collection 1: form/content chunks

Environment variable:

```env
Qdrant_Form=<collection-name>
```

Purpose:

- stores chunks of extracted report content;
- stores metadata such as form ID, product, location, cooperator, user, and cooperative;
- supports dense semantic and sparse keyword vectors.

Vector types:

- `dense`: embedding vector;
- `sparse`: TF-IDF vector represented in Qdrant format.

### 12.2 Collection 2: analysis records

Environment variable:

```env
Qdrant_Analysis_Report=<collection-name>
```

Purpose:

- stores one searchable structured record per analysis;
- stores a dense embedding of `summary_text`;
- stores structured payload fields used by filters and tools.

Examples of stored payload fields:

- form ID;
- filename;
- form type;
- applicant;
- cooperator;
- product;
- location;
- crop;
- dates and season;
- performance metrics;
- confidence;
- trend information;
- yield information;
- product category;
- feedback sentiment;
- data-quality score;
- full analysis;
- graph suggestions;
- executive summary;
- risks;
- opportunities;
- recommendations;
- user ID;
- cooperative.

Both collections are automatically created when insertion requires them and they do not yet exist.

### 12.3 What is stored in RAG

RAG is not a separate mysterious source of information. The information originates from processed reports.

```text
uploaded PDF/image
      |
      v
extracted text + structured analysis
      |
      v
chunks and searchable summary
      |
      v
embeddings
      |
      v
Qdrant collections
```

What enters the RAG store:

- text chunks from extracted reports;
- searchable summary text created from structured analysis;
- metadata and filterable agricultural fields;
- full structured analysis as payload;
- chart suggestions as payload.

### 12.4 Purpose of RAG

When a user asks a semantic question, RAG finds the most relevant stored records instead of sending every report to the LLM.

Runtime RAG for search and chat retrieves from the **analysis** collection via dense embeddings. Form-chunk hybrid search modules exist, but they are not on the live `/api/analysis-search` or chat-tool request path.

Example:

```text
User: "Which trials showed fast action but had negative farmer feedback?"

1. The query is embedded.
2. Qdrant finds semantically similar analysis records (dense search).
3. Cooperative and structured filters restrict access/results.
4. Only the best matching reports are returned.
5. The chat agent explains those results.
```

SQL/database filtering and RAG are not mutually exclusive:

- SQL or payload filters are best for exact fields, IDs, dates, and locations.
- Vector retrieval is best for meaning, concepts, observations, and natural-language similarity.

In the current codebase, the searchable trial records are stored in Qdrant rather than fetched from an external business SQL database at query time.

---

## 13. Search Architecture

Primary endpoint:

```http
POST /api/analysis-search
```

Request:

```json
{
  "query": "rice trials in Nueva Ecija",
  "top_k": 5
}
```

Flow:

```text
request
  -> validate query and top_k
  -> create/propagate Langfuse session
  -> dense search over Qdrant analysis collection
  -> apply cooperative filter and score thresholds
  -> calculate search metrics
  -> return ranked results
```

Important current behavior:

- `/api/analysis-search` and the chat search tools call `analysis_searcher`, which performs dense retrieval over the analysis collection.
- `LangChainHybridSearch` exists for the form/chunk collection, but it is not the active path used by `/api/analysis-search` or chat tools.

Active search infrastructure for `/api/analysis-search` and chat tools:

- `src/infrastructure/vector_store/analysis_search.py`;
- `src/infrastructure/vector_store/analysis_dense_retriever.py`.

Related but not on the live analysis-search path:

- `src/infrastructure/vector_store/hybrid_search.py`;
- `src/infrastructure/vector_store/dense_retriever.py`;
- `src/infrastructure/vector_store/sparse_retriever.py`.

---

## 14. Chat Architecture

Primary endpoint:

```http
POST /api/chat
```

The chat interface is a separate capability from document processing, but both use the same stored report data.

### 14.1 Chat request flow

```text
user message
  -> /api/chat
  -> load or create session/thread
  -> load recent conversation history from PostgreSQL
  -> get/create cooperative-bound LangChain agent
  -> LLM chooses tools
  -> tools query Qdrant analysis data
  -> agent formats a conversational response
  -> save user/assistant messages to PostgreSQL
  -> return answer, tools used, sources, and follow-up questions
```

### 14.2 Tool architecture

The current `AgentExecutor` receives 33 tools:

- 11 basic search tools;
- 16 advanced search tools;
- 3 list/retrieval tools;
- 3 analysis tools.

Basic search examples:

- search all analysis fields;
- search by product;
- location;
- crop;
- cooperator;
- season;
- improvement range;
- sentiment;
- product category;
- performance significance;
- applicant.

Advanced search examples:

- form type;
- date range;
- metric type;
- confidence;
- data quality;
- control product;
- speed of action;
- yield status;
- yield improvement;
- measurement intervals;
- metrics detected;
- risk factors;
- opportunities;
- recommendations;
- key observations;
- scale information.

Analysis and retrieval tools:

- list reports;
- get statistics;
- retrieve report by ID;
- compare products;
- generate summaries;
- analyze trends.

Memory tools exist in `src/chatbot/tools/memory_tools.py`, but they are not part of the current `_get_all_tools()` list passed to the active `AgentExecutor`. Conversation memory is instead loaded and saved directly by `invoke_agent`.

### 14.3 Chat LLM

The chat agent supports:

- OpenRouter;
- Gemini.

The current `create_chat_agent` default is OpenRouter.

### 14.4 Conversation memory

PostgreSQL stores:

- conversation threads;
- messages;
- timestamps;
- session activity.

Only a bounded number of recent messages are loaded into the model context to reduce token usage.

If PostgreSQL is unavailable during startup, the application logs a fallback message and can use in-memory behavior where supported.

---

## 15. API Architecture

All API routers except public health/root endpoints are registered with API-key authentication.

### 15.1 Core processing

- `POST /api/agent` — full evaluator workflow, synchronous or background.
- `POST /api/upload-file-product-demo` — legacy extract/chunk path that inserts form chunks into Qdrant immediately (no LangGraph analysis, no storage approval).

### 15.2 Search and reporting

- `POST /api/analysis-search` — dense search over structured analyses.
- Report listing routes are defined in `src/api/routes/list.py` with router prefix `/api/reports` and then mounted again under `/api` in `main.py`.
- Because of that double prefix, the currently generated paths are:
  - `GET /api/api/reports/list`
  - `GET /api/api/reports/stats`
- The intended paths are likely `/api/reports/list` and `/api/reports/stats`; the double `/api` is a current routing inconsistency.

### 15.3 Storage

- `POST /api/storage/approve-simple` — approve or reject permanent storage.

### 15.4 Background jobs

- `GET /api/progress/{job_id}` — retrieve job progress/result.
- `GET /api/worker/health` — worker health information.
- `GET /api/worker/metrics` — worker metrics.
- `GET /api/worker/jobs` — inspect jobs.

### 15.5 Chat

- `POST /api/chat` — conversational query.
- `GET /api/chat/history` — conversation history.
- `GET /api/chat/stats` — conversation statistics.
- `GET /api/chat/health` — chat subsystem health.
- `POST /api/chat/reset` — reset a conversation.
- `DELETE /api/chat/cache` — clear cached chat agents.

### 15.6 Cache administration

- `POST /api/cache/cleanup`;
- `DELETE /api/cache/clear-all`;
- `GET /api/cache/stats`;
- `GET /api/cache/memory`;
- `GET /api/cache/{cache_id}`;
- `DELETE /api/cache/{cache_id}`.

These are marked in `main.py` as debugging/admin routes and should be restricted appropriately in production.

### 15.7 Deletion

- `DELETE /api/delete/{form_id}`;
- `DELETE /api/delete-all/{collection_name}`.

### 15.8 Health and diagnostics

- `GET /`;
- `GET /api/health`;
- `GET /api/qdrant/check`.

Interactive documentation:

- Swagger: `http://localhost:8000/docs`;
- ReDoc: `http://localhost:8000/redoc`.

---

## 16. Redis Architecture

Redis has three related responsibilities:

1. ARQ background job queue.
2. Background progress and tracking keys.
3. Temporary agent-output cache before storage approval.

Important key patterns include:

```text
arq:tracking:{job_id}
arq:user:{job_id}
arq:session:{job_id}
arq:progress:{tracking_id}
agent:cache:{user_id}:{cache_id}
```

The evaluator Redis may be separate from the Redis used internally by a self-hosted Langfuse deployment. In local development, the evaluator is commonly configured on port `6380`, while a separately deployed Langfuse Redis may use `6379`.

---

## 17. PostgreSQL Architecture

PostgreSQL is currently used for chat conversation memory, not for the primary trial analysis store.

It supports:

- conversation threads;
- persistent chat messages;
- session timeout checks;
- multi-turn context.

Relevant files:

- `src/infrastructure/postgres/postgres_pool.py`;
- `src/infrastructure/postgres/postgres_memory_schema.py`;
- `src/chatbot/memory/postgres_memory.py`;
- `src/chatbot/memory/conversation_store.py`.

Default local configuration:

```env
POSTGRES_HOST=localhost
POSTGRES_PORT=5433
POSTGRES_DB=agentic_ai_evaluator
POSTGRES_USER=postgres
POSTGRES_PASSWORD=
```

---

## 18. LLM and Prompt Architecture

### 18.1 Gemini

Gemini is used for:

- PDF/image understanding and extraction;
- content validation;
- structured agricultural analysis;
- graph suggestions;
- workflow output evaluation, depending on evaluator/provider configuration.

### 18.2 OpenRouter

OpenRouter is primarily available for the chat agent and agent LLM factory.

### 18.3 Prompt management

Local prompt templates live under `src/prompts/` and `src/chatbot/prompts/`.

The project can load managed prompts from Langfuse, with local templates as fallback.

Examples:

- `agricultural-demo-analysis`;
- `graph-suggestion`;
- chat system prompt.

This allows prompt changes to be managed without removing a safe local fallback.

---

## 19. Langfuse Observability

Langfuse is optional. The application continues without it if the keys are missing or initialization fails.

Configuration:

```env
LANGFUSE_PUBLIC_KEY=...
LANGFUSE_SECRET_KEY=...
LANGFUSE_HOST=http://localhost:3000
```

For Langfuse Cloud:

```env
LANGFUSE_HOST=https://cloud.langfuse.com
```

Tracked operations include:

- file upload;
- extraction;
- content validation;
- analysis;
- output evaluation;
- graph generation;
- report processing;
- search;
- chat;
- storage approval;
- background workers.

Metadata can include:

- user ID;
- session ID;
- filename;
- cooperative;
- workflow step;
- analysis confidence;
- data-quality score;
- chart count;
- search relevance;
- storage success or rejection.

Dedicated score modules:

- `src/monitoring/scores/workflow_score.py`;
- `src/monitoring/scores/search_score.py`;
- `src/monitoring/scores/storage_score.py`.

---

## 20. Security and Isolation

### 20.1 API-key authentication

Protected routes use `require_api_key`.

Supported configuration:

```env
API_KEY=...
API_KEYS=key1,key2,key3
```

### 20.2 User isolation

`X-User-ID` is used for:

- cache ownership;
- workflow trace metadata;
- storage ownership checks;
- chat thread identity.

### 20.3 Cooperative isolation

`X-Cooperative` is bound to:

- chat tools;
- search filters;
- stored Qdrant metadata.

This allows users in the same cooperative to query cooperative data while restricting records from other cooperatives.

### 20.4 Rate limiting

SlowAPI limits requests per endpoint. Examples:

- agent uploads: `10/minute`;
- chat: `30/minute`;
- analysis search: `60/minute`;
- storage approval: `10/minute`;
- destructive collection deletion: `5/minute`.

### 20.5 Input validation

The project validates:

- uploaded size, filename, extension, and integrity;
- chat message length;
- search query length;
- IDs and session IDs;
- background priority;
- search `top_k`.

### 20.6 Logging safety

The application uses clean/safe logging and masks health-check details in production where configured.

---

## 21. Deployment Architecture

### 21.1 Local development

Install dependencies:

```powershell
uv sync
```

Run API:

```powershell
uv run uvicorn main:app --host 0.0.0.0 --port 8000
```

Run worker in a second terminal:

```powershell
uv run arq src.workers.workers.WorkerSettings
```

Required infrastructure depends on used features:

- Qdrant: required for storage/search/chat data;
- Redis: required for cache and background jobs;
- PostgreSQL: needed for persistent chat memory;
- Langfuse: optional observability.

### 21.2 Docker deployment

`docker/docker-compose.yml` defines:

- `agentic-fastapi`;
- `agentic-arq-worker`;
- private `app-network`.

Qdrant, Redis, PostgreSQL, and Langfuse are expected to be deployed or configured separately.

The compose file maps the container API to port `8002`. Local direct Uvicorn commonly runs on `8000`.

Current Docker caveats:

- Compose lives under `docker/` and sets `build.context: "."`, so builds run from the Docker directory rather than the repository root unless invoked carefully.
- `env_file: .env` is likewise relative to the Compose file location.
- Startup scripts and README references may still advertise port `8000` or missing compose variants; treat the Compose file itself as the source of truth for published ports and services.

### 21.3 Self-hosted Langfuse

A self-hosted Langfuse deployment is a separate Docker stack with its own:

- web container;
- worker;
- PostgreSQL;
- Redis;
- ClickHouse;
- MinIO.

It should not be confused with the evaluator's own Redis, PostgreSQL, or FastAPI containers.

---

## 22. Project Directory Map

```text
agentic-ai-evaluator/
├── main.py                         FastAPI entry point and router registration
├── pyproject.toml                  Python package and dependencies
├── uv.lock                         Locked dependency versions
├── gunicorn_config.py              Production server configuration
├── ai-evaluator.md                 This architecture document
│
├── src/
│   ├── Agents/
│   │   ├── output_evaluator.py     Evaluates analysis/graph quality
│   │   └── evaluation_crew.py      CrewAI evaluation crew (4 agents)
│   │
│   ├── api/
│   │   ├── deps/
│   │   │   ├── security.py         API-key authentication
│   │   │   ├── user_context.py     X-User-ID handling
│   │   │   └── cooperative_context.py
│   │   └── routes/
│   │       ├── agent.py            Main file-processing endpoint
│   │       ├── upload.py           Legacy/simple upload
│   │       ├── storage.py          Storage approval
│   │       ├── search.py           Analysis search
│   │       ├── chat_router.py      Chat APIs
│   │       ├── progress.py         Background progress
│   │       ├── worker.py           Worker inspection
│   │       ├── cache.py            Cache administration
│   │       ├── list.py             Reports and statistics
│   │       └── delete_extract.py   Qdrant deletion
│   │
│   ├── chatbot/
│   │   ├── bot/chat_agent.py       Tool-calling LangChain agent
│   │   ├── tools/                  Search/list/analysis/memory tools
│   │   ├── prompts/                Chat system prompts
│   │   ├── memory/                 PostgreSQL and in-memory chat memory
│   │   └── formatter/              User-facing result formatting
│   │
│   ├── core/
│   │   ├── config.py               Environment configuration
│   │   ├── constants.py            Limits, timeouts, TTLs, thresholds
│   │   ├── errors.py               Domain/API exceptions
│   │   └── secrets_loader.py       Optional AWS Secrets Manager
│   │
│   ├── domain/workflow/
│   │   ├── state.py                ProcessingState
│   │   └── models.py               Pydantic workflow models
│   │
│   ├── formatter/
│   │   ├── chunking.py             Markdown chunking
│   │   └── json_helper.py          Output validation/normalization
│   │
│   ├── infrastructure/
│   │   ├── embeddings/             Dense and sparse encoders
│   │   ├── vector_store/           Qdrant storage/search
│   │   ├── redis/                  Shared Redis pool
│   │   └── postgres/               PostgreSQL pool and schema
│   │
│   ├── ingestion/
│   │   ├── form_extractor.py       Gemini extraction
│   │   ├── file_validator.py       File validation
│   │   └── multiple_handler.py     Single/multi-report orchestration
│   │
│   ├── monitoring/
│   │   ├── trace/                  Langfuse initialization/helpers
│   │   ├── session/                User/session propagation
│   │   └── scores/                 Workflow/search/storage scores
│   │
│   ├── prompts/
│   │   ├── analysis_template.py
│   │   ├── graph_suggestion_template.py
│   │   └── prompt_management.py
│   │
│   ├── services/
│   │   ├── cache_service.py        Pending-output Redis cache
│   │   └── storage_service.py      Permanent storage orchestration
│   │
│   ├── shared/                     LLM, validation, logging, retry helpers
│   ├── workflow/                   LangGraph graph, routers, state exports
│   └── workers/workers.py          ARQ background worker
│
├── config/
│   ├── env.example                 Environment template
│   └── aws-secret-template.json
├── docker/
│   ├── Dockerfile
│   ├── docker-compose.yml
│   └── README.md
├── scripts/                        Setup, migration, and seed utilities
├── tests/                          Unit and integration tests
├── data/                           Sample/input data
├── actual_data/                    Actual trial files
└── docs/                           Additional project documentation
```

---

## 23. Configuration Groups

Do not commit actual secrets.

### 23.1 AI providers

```env
GEMINI_APIKEY=...
GEMINI_MODEL=...
GEMINI_LARGE=...
OPENROUTER_API_KEY=...
OPENROUTER_MODEL=...
```

### 23.2 Qdrant

```env
Qdrant_Localhost=http://localhost:6333
Qdrant_Form=...
Qdrant_Analysis_Report=...
QDRANT_API_KEY=
EMBEDDING_MODEL=...
```

### 23.3 Evaluator Redis

```env
REDIS_HOST=localhost
REDIS_PORT=6380
REDIS_DB=0
REDIS_PASSWORD=
```

### 23.4 PostgreSQL

```env
POSTGRES_HOST=localhost
POSTGRES_PORT=5433
POSTGRES_DB=agentic_ai_evaluator
POSTGRES_USER=postgres
POSTGRES_PASSWORD=...
```

### 23.5 Langfuse

```env
LANGFUSE_PUBLIC_KEY=...
LANGFUSE_SECRET_KEY=...
LANGFUSE_HOST=http://localhost:3000
```

### 23.6 API and web security

```env
ENVIRONMENT=development
API_KEY=...
RATE_LIMIT_ENABLED=true
CORS_ORIGINS=http://localhost:3000,http://localhost:8501
```

---

## 24. Example End-to-End Scenario

### Scenario: process and query a trial

1. User uploads `Nueva-Ecija-Rice-Trial.pdf` to `/api/agent`.
2. API validates the upload.
3. Gemini extracts the report into Markdown.
4. Content-validation node confirms it is a trial report.
5. Analysis node extracts:
   - product;
   - crop;
   - location;
   - cooperator;
   - control and treatment values;
   - improvement;
   - yield;
   - feedback;
   - recommendations.
6. Evaluation node checks the analysis.
7. If weak but fixable, analysis is retried.
8. Graph node proposes a performance chart and yield comparison.
9. Evaluation checks the chart specifications.
10. Content is chunked.
11. API returns the result and `cache_id`.
12. User reviews the result.
13. User approves `/api/storage/approve-simple`.
14. Chunks and structured analysis are embedded and saved in Qdrant.
15. Later, user asks in `/api/chat`:

```text
"Ano ang performance ng rice trials sa Nueva Ecija?"
```

16. Chat agent selects a location/search tool.
17. Tool retrieves cooperative-authorized reports from Qdrant.
18. Agent explains the stored results and may suggest follow-up questions.

---

## 25. Current Limitations and Technical Risks

### 25.1 Graph output is not yet an image

The workflow creates chart specifications, not rendered files. A future renderer could use:

- Plotly;
- Matplotlib;
- Vega-Lite;
- Chart.js through a rendering service.

### 25.2 External SQL/API data is not yet the evaluator's main input

The current evaluator workflow expects files or pre-extracted Markdown. Supporting an external business database through an API will require an adapter that maps database records into a stable evaluator input contract.

### 25.3 Business-action decisions are planned

Email, meeting, and contact decisions described in planning documents are not part of the current workflow graph.

### 25.4 Two persistent information systems serve different purposes

- Qdrant stores searchable trial content and analysis.
- PostgreSQL stores chat memory.

They should not be treated as interchangeable.

### 25.5 Redis availability is required for more than background jobs

Even synchronous processing saves completed output to Redis for storage approval. Without Redis, processing may finish but cache creation and approval flow can fail or degrade.

### 25.6 Infrastructure versions must remain compatible

Qdrant client and server versions should remain within the compatibility range reported by the Qdrant SDK.

### 25.7 Debug/admin routes need production restrictions

Cache, worker, and destructive deletion routes have API-key protection and rate limits, but production deployments should use stricter authorization and network controls for administrative endpoints.

### 25.8 Analysis search is dense-first today

Despite hybrid-search code existing for form chunks, `/api/analysis-search` and chat tools currently retrieve from the dense analysis collection and then apply cooperative and field filters.

### 25.9 Analysis embedding size is hard-coded to 768

Analysis storage and dense-retriever collection creation use vector size `768`. The embedding model configured in `.env` must emit 768 dimensions, or insertion/search can fail. Example configs that recommend a 384-dimension model are incompatible with this hard-coded size unless the model is changed.

### 25.10 Background priority is informational only

`priority=high|normal|low` is accepted and stored in the job ID, but it does not currently change ARQ queue order.

### 25.11 Fine-grained worker progress is incomplete

A progress helper exists, but the background worker does not emit step-by-step progress during processing. Clients often see incomplete progress until the final result appears.

### 25.12 Report list route prefix is inconsistent

`list.py` already uses prefix `/api/reports`, and `main.py` mounts it under `/api` again, producing `/api/api/reports/...` paths.

---

## 26. Recommended Future Architecture

The following is a safe evolution path, not current functionality.

### Phase 1: stabilize current evaluator

- fix infrastructure reproducibility;
- align Qdrant client/server versions;
- add integration tests for upload -> approval -> search;
- document exact deployment commands;
- verify worker, Redis, PostgreSQL, Qdrant, and Langfuse health.

### Phase 2: render graph specifications

```text
graph_suggestions JSON
  -> chart renderer
  -> PNG/SVG or hosted image URL
  -> chat/report/API response
```

### Phase 3: support database/API input

Create an input adapter:

```text
external database API
  -> normalized trial record
  -> evaluator analysis/evaluation/graph services
```

The database should remain the source of truth. Only selected, bounded data should be sent to the LLM.

### Phase 4: reuse nodes as independent services

Refactor node logic into reusable domain services so it can be invoked by:

- the current file workflow;
- a database/API workflow;
- a chat tool;
- scheduled jobs.

### Phase 5: add business-action decision support

Add a separate decision layer after analysis:

```text
analysis
  -> recommend actions
  -> user review/approval
  -> email/calendar/contact execution
```

This keeps quality routing separate from real-world side effects.

---

## 27. Final Project Definition

The most accurate current description is:

> **AI Evaluator is an agentic agricultural trial-processing and knowledge system. It converts PDF/image demo reports into validated structured analyses and chart-ready specifications, evaluates and retries its own outputs, stores approved results as searchable Qdrant records, and provides search and conversational access through a tool-calling chat agent with persistent memory and full observability.**

Its unique value is not only generating text. Its value is the complete controlled pipeline:

```text
raw trial document
  -> extraction
  -> validation
  -> structured analysis
  -> self-evaluation
  -> controlled retry
  -> chart-ready data
  -> chunking
  -> approval
  -> searchable knowledge
  -> conversational access
```

That is the current architecture and purpose of the project.
