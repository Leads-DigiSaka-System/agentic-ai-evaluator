# Evaluator Agent: Decision-Making + Human-in-the-Loop — Implementation Plan

**Based on supervisor direction:**  
*"Evaluator agent may have decision-making (e.g. contact technical team / auto email / farmers). Essence of the agent is decision-making but human-in-the-loop — confirm first before going ahead to email them. Concerned parties: tech team, TPS, demo partners (farmers). Auto-generate and schedule meetings to discuss trial results."*

---

## 1. Supervisor Requirements (Summary)

| Requirement | Description |
|-------------|-------------|
| **Decision-making** | Agent decides *what to do* with a trial: e.g. contact technical team, send email to farmers, schedule meeting with TPS/demo partners. |
| **Human-in-the-loop** | No automatic sending. User must **confirm** before any action (e.g. "Go ahead, email them"). |
| **Concerned parties** | Tech team, TPS (Technical/Product Support?), demo partners (farmers). |
| **Auto-generate** | Auto-generate *suggestions*: who to contact, draft emails, "schedule a meeting to discuss trial results." |
| **Execution after approval** | After user confirms: send email, create meeting, etc. |

---

## 2. Current State vs Desired State

### What Exists Today

- **Pipeline:** Extract → Validate content → Analyze → Evaluate analysis → Suggest graphs → Evaluate graphs → Chunk → END.
- **Evaluation:** Quality gates only (analysis/graph good enough?). No "what to do next" decisions.
- **Human-in-the-loop:** Only **storage approval** (approve/reject storing to Qdrant via `POST /api/storage/approve-simple`).
- **Contact data:** Analysis has `basic_info.cooperator`, `basic_info.contact`; stored in Qdrant. No notion of "tech team," "TPS," or "demo partner" as roles.
- **No email, no notifications, no meeting scheduling.**

### What We Need

1. **Decision layer** — After evaluation/chunk, a node that outputs *recommended actions* (contact tech, email farmer, schedule TPS meeting, etc.).
2. **Pending decisions store** — Store recommended actions keyed by report/cache so the UI can show "Pending actions" and user can approve/reject/edit.
3. **Human approval for actions** — API (and UI) to list pending decisions, approve/reject, and optionally trigger execution.
4. **Execution layer** — When user approves: send email, create calendar event (or link to external scheduler).
5. **Recipient/role model** — Map "tech team," "TPS," "farmers/demo partners" to contact info (config or from analysis).

---

## 3. High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  EXISTING WORKFLOW (unchanged until chunk)                                   │
│  extract → validate_content → analyze → evaluate_analysis → suggest_graphs  │
│  → evaluate_graphs → chunk → END                                            │
└─────────────────────────────────────────────────────────────────────────────┘
                                        │
                                        ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  NEW: DECISION NODE (after chunk, before END — or as post-processing)         │
│  Input: analysis_result, content_validation, output_evaluation, chunks       │
│  Output: recommended_actions[] (e.g. notify_tech, email_farmer,              │
│          schedule_meeting_tps, schedule_meeting_farmer)                      │
│  + suggested_recipients, draft_content (email subject/body, meeting title)   │
└─────────────────────────────────────────────────────────────────────────────┘
                                        │
                                        ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  NEW: PENDING DECISIONS (stored by cache_id / report_id)                     │
│  - List pending actions per report                                           │
│  - User can: Approve / Reject / Edit (e.g. change recipients, edit draft)    │
└─────────────────────────────────────────────────────────────────────────────┘
                                        │
                        User confirms "Go ahead, email them" / "Schedule meeting"
                                        ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  NEW: EXECUTION (only after human approval)                                  │
│  - Email service: send to tech team / TPS / farmer (cooperator contact)      │
│  - Scheduling: create event or return link (e.g. Calendly / Calendar API)   │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 4. What We Need to Build (Deep Breakdown)

### 4.1 Decision Node (Workflow)

- **Placement:** After `chunk` (new node `decide_actions`) then END; or run as **post-processing** when building the agent response (so no graph change if you prefer).
- **Inputs from state:**  
  `analysis_result` (basic_info.cooperator, contact, product, location, cooperator_feedback, executive_summary),  
  `content_validation`, `output_evaluation`, `graph_suggestions`, `chunks`.
- **Logic (LLM or rules):**
  - Decide *types* of actions: e.g. `notify_technical_team`, `email_demo_partner`, `schedule_meeting_tps`, `schedule_meeting_demo_partner`.
  - Optional: severity/priority (e.g. low data quality → suggest tech review).
  - For each action: suggested recipients (role + contact if available), draft subject/body for email, draft meeting title/agenda.
- **Output:** Append to state or to a **decisions** structure keyed by cache_id:
  - `recommended_actions`: list of `{ action_type, reason, suggested_recipients[], draft_email?, draft_meeting? }`.
- **State change:** Add to `ProcessingState` (or a separate store):
  - `recommended_actions: Optional[List[Dict]]`
  - Optionally `decision_summary: Optional[str]` for UI.

**Files to touch:**  
`src/domain/workflow/state.py` (new fields), `src/workflow/graph.py` (add node + edge from chunk → decide_actions → END), new `src/workflow/nodes/decision_node.py`, `src/workflow/routers.py` (route after decision).

---

### 4.2 Pending Decisions Store & API

- **Storage:** Same as storage approval: decisions live with the **cached report**. When agent returns, cache entry includes `recommended_actions`. So:
  - **Option A:** Store `recommended_actions` inside existing cache payload (no new DB). Frontend shows them; approval endpoint accepts which actions to execute.
  - **Option B:** Separate table/Redis key `pending_decisions:{cache_id}` with status (pending / approved / rejected) and execution result.
- **API:**
  - **GET /api/decisions/pending?cache_id=...** — List pending actions for a report (from cache or DB).
  - **POST /api/decisions/approve** — Body: `cache_id`, `action_id` (or list), optional overrides (recipients, draft). Marks approved and optionally triggers execution.
  - **POST /api/decisions/reject** — Body: `cache_id`, `action_id` (or list). Marks rejected.
- **Human-in-the-loop:** No email/meeting is sent until user calls approve with "execute" or a dedicated "execute approved" endpoint.

**Files to touch:**  
`src/api/routes/decisions.py` (new), `src/domain/workflow/models.py` (e.g. `DecisionAction`, `ApproveDecisionsRequest`), `src/services/cache_service.py` (include recommended_actions in cached response if Option A).

---

### 4.3 Recipient / Role Model

- **Roles:** `technical_team`, `tps`, `demo_partner` (farmer/cooperator).
- **Source of addresses:**
  - **Tech team / TPS:** From **config** or env (e.g. `TECH_TEAM_EMAIL`, `TPS_EMAIL` or a JSON map role → email).
  - **Demo partner:** From `analysis_result.basic_info.contact` (and name from `cooperator`). If contact is empty, "schedule meeting" might still be suggested but with a note "Contact not available."
- **Config shape (example):**
  - `DECISION_ACTIONS_ENABLED=true`
  - `TECH_TEAM_EMAIL=...` (or `ROLE_EMAILS={"technical_team": "...", "tps": "..."}`)
  - Optional: per-cooperative overrides later.

**Files to touch:**  
`src/core/config.py`, `.env.example`, new `src/services/recipient_resolver.py` (role + analysis → list of email/name).

---

### 4.4 Email Service

- **Scope:** Send email only **after** user approves (human-in-the-loop).
- **Config:** SMTP or SendGrid/Mailgun etc. (env: `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD`, `FROM_EMAIL`).
- **Input:** Recipients (resolved from role + analysis), subject, body (from draft or user-edited).
- **Security:** No sending from decision node; only from an API that requires approval (and optionally auth).

**Files to touch:**  
`src/core/config.py`, `src/services/email_service.py` (new), `.env.example`.

---

### 4.5 Meeting / Schedule

- **Options:**  
  - **A)** Generate a **link** (e.g. Calendly) with pre-filled title/description (trial result discussion).  
  - **B)** Integrate Google Calendar / Outlook API to create an event.  
  - **C)** Return a **draft** (title, agenda, suggested time) for user to create manually.
- **Minimal first step:** Store in recommended action `draft_meeting: { title, agenda, suggested_recipients }` and either return link or "Copy to calendar" payload; no backend calendar write in v1 if you want to avoid OAuth.

**Files to touch:**  
`src/workflow/nodes/decision_node.py` (output draft), optional `src/services/calendar_service.py` (if integrating an API).

---

## 5. Data Model Additions

### 5.1 ProcessingState (or cache payload)

```python
# In state or in cached report
recommended_actions: Optional[List[Dict[str, Any]]]
# Each item:
# {
#   "id": "uuid",
#   "action_type": "notify_technical_team" | "email_demo_partner" | "schedule_meeting_tps" | "schedule_meeting_demo_partner",
#   "reason": "str",
#   "suggested_recipients": [{"role": "technical_team"|"tps"|"demo_partner", "email": "...", "name": "..."}],
#   "draft_email": {"subject": "...", "body": "..."} | null,
#   "draft_meeting": {"title": "...", "agenda": "..."} | null,
#   "status": "pending" | "approved" | "rejected",
#   "executed_at": null | "iso datetime"
# }
```

### 5.2 API Request/Response

- **Approve request:** `cache_id`, `action_ids[]`, `execute: bool`, optional `overrides: { subject?, body?, recipients? }`.
- **Response:** Success, and if `execute=true`, result of send/schedule (e.g. `email_sent: true`, `meeting_link: "..."`).

---

## 6. What Needs to Be Ready (Checklist)

### 6.1 Configuration & Environment

- [ ] **Feature flag:** e.g. `DECISION_ACTIONS_ENABLED=true` so decision node and decision API can be toggled.
- [ ] **Role emails:** Tech team and TPS emails (env or config JSON). Demo partner comes from analysis.
- [ ] **Email:** SMTP or provider credentials (for execution after approval).
- [ ] **Optional:** Calendar provider and credentials if you implement create-event in backend.

### 6.2 Backend Readiness

- [ ] **Decision node** implemented and wired (graph or post-process).
- [ ] **Cache** includes `recommended_actions` in agent response so frontend can show "Suggested actions."
- [ ] **Decisions API** (list pending, approve, reject) with user/cache isolation (same as storage: by user_id/cache_id).
- [ ] **Recipient resolver** (role + analysis → recipients).
- [ ] **Email service** called only from approve+execute path.
- [ ] **Meeting:** At least draft in recommended_actions; optional link or calendar create.

### 6.3 Frontend / UX (So Human-in-the-Loop Works)

- [ ] After agent returns, show **"Recommended actions"** (e.g. "Email technical team," "Schedule meeting with demo partner").
- [ ] For each action: show reason, suggested recipients, draft email/meeting.
- [ ] User can **edit** draft (subject, body, recipients) before approving.
- [ ] Buttons: **Approve & send** / **Approve & schedule** / **Reject**.
- [ ] Only on "Approve & send" (or "Approve & schedule") does the backend send email or create/link meeting.

### 6.4 Operational

- [ ] **Logging:** Log when decisions are generated, when user approves/rejects, when email/schedule is executed (without logging full PII in plain text).
- [ ] **Langfuse:** Optionally trace decision node and decision approval as separate spans.
- [ ] **Error handling:** If email fails after approval, return clear error and optionally keep action as "approved but failed" for retry.

---

## 7. Phased Implementation (Suggested)

| Phase | Scope | Outcome |
|-------|--------|--------|
| **1** | Decision node + state/cache | Agent returns `recommended_actions` with action_type, reason, suggested_recipients, draft_email/draft_meeting. No execution. |
| **2** | Decisions API (list, approve, reject) + UI | User sees pending actions and can approve/reject (no send yet). |
| **3** | Recipient resolver + config | Resolve tech/TPS/demo partner emails from config and analysis. |
| **4** | Email service + "Approve & send" | On approve with execute, send email. Human-in-the-loop preserved. |
| **5** | Meeting draft + link or calendar | Draft meeting in actions; add "Copy to calendar" or Calendly link or calendar API. |

---

## 8. Summary: How It Will Work

1. **Agent runs** (existing pipeline). After chunk, **decision node** runs and fills `recommended_actions` (notify tech, email farmer, schedule meeting with TPS/demo partner) with reasons and drafts.
2. **Response** to frontend includes `recommended_actions` (and cache_id as today). Frontend shows "Suggested actions — please review."
3. **User reviews** each action (recipients, draft email/meeting), can edit.
4. **User confirms:** "Go ahead, email them" / "Schedule meeting" via Approve + execute. No automatic send without this step.
5. **Backend** resolves recipients (tech, TPS from config; farmer from analysis contact), sends email or creates/returns meeting link only after approval.

This keeps **decision-making** in the agent and **human-in-the-loop** (confirm before email/meeting) as requested, and uses existing analysis data (cooperator, contact) plus config for tech/TPS to auto-generate suggestions and drafts.

---

## 9. Next Steps

1. Confirm roles and contact sources (tech team, TPS, demo partner) and where emails will be configured.
2. Choose: decision node inside graph vs post-processing when building agent response.
3. Implement Phase 1 (decision node + recommended_actions in state/cache).
4. Add GET/POST decisions API and recipient resolver (Phases 2–3).
5. Add email service and wire to approve+execute (Phase 4).
6. Add meeting draft/link (Phase 5) and frontend flows for review/approve.

If you want, the next concrete step can be: **add only the decision node and `recommended_actions` to state and cache** (Phase 1) with a minimal LLM prompt that outputs 0–3 suggested actions based on analysis and validation.

---

**Future (getting ready):** Ang analysis ay magiging **chat-based** din later; hindi pa ngayon. Para ready na tayo, see [CHAT_BASED_ANALYSIS_READY.md](./CHAT_BASED_ANALYSIS_READY.md) — what to keep reusable so chat-based analysis is easy to add later.

---

## 10. How to Automate Emails, Meetings, and Contacting (Follow-up)

This section describes **concrete ways** to automate sending emails, scheduling meetings, and contacting people **after** human approval (or, optionally, in a more fully automated mode).

### 10.1 When Does “Automation” Run?

| Mode | When it runs | Use case |
|------|----------------|----------|
| **Approve-then-send** | User clicks “Approve & send” → backend immediately sends email / creates meeting | Human-in-the-loop (recommended first). |
| **Batch after approval** | User approves multiple actions → one API call executes all (e.g. “Send all 3 emails”). | Fewer clicks; still one human confirmation. |
| **Scheduled / cron** | A job runs periodically (e.g. “Send all approved-but-not-yet-sent actions” or “Remind TPS of pending trials”). | Follow-ups, reminders, digest emails. |
| **Fully automatic** | No approval: agent decision → auto-send (not recommended until you have strong safeguards). | Only if policy later allows; out of scope for initial design. |

Recommendation: Start with **approve-then-send** (and optional batch). Add **scheduled** later for reminders or digests.

---

### 10.2 Automating Email

**Flow:** User approves action → backend resolves recipients → fills template (if any) → sends via a provider.

**Options:**

| Option | Pros | Cons | Config / Env |
|--------|------|------|--------------|
| **SMTP (e.g. Gmail, company server)** | No extra cost, works everywhere | Rate limits, deliverability, may need “Less secure app” or App Password | `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD`, `FROM_EMAIL` |
| **SendGrid** | Good deliverability, API, templates | Account + API key | `SENDGRID_API_KEY`, `FROM_EMAIL` |
| **Mailgun** | API, templates, logs | Account + API key | `MAILGUN_API_KEY`, `MAILGUN_DOMAIN` |
| **Resend** | Simple API, developer-friendly | Newer | `RESEND_API_KEY` |
| **AWS SES** | Cheap, scalable | AWS setup, verification | `AWS_ACCESS_KEY`, `AWS_SECRET`, `AWS_REGION`, `FROM_EMAIL` |

**Implementation pattern:**

1. **Email service module** (e.g. `src/services/email_service.py`):
   - `send_email(to: list[str], subject: str, body_html: str, body_text: str | None)`.
   - Inside: choose provider from config (e.g. `EMAIL_PROVIDER=sendgrid`), call their SDK or HTTP API.
2. **Templates (optional):** Store templates (e.g. Jinja2 or simple `.html`) for “Trial result summary for tech team,” “Invitation to discuss trial with demo partner.” Merge with context: `report_number`, `cooperator`, `product`, `executive_summary` snippet.
3. **Trigger:** Called from the “approve + execute” endpoint when `action_type` is `email_*` and user approved with `execute=true`.

**Python libraries:** `sendgrid`, `boto3` (SES), or `smtplib` + `email` for SMTP. Use one interface in your code so you can switch providers via config.

---

### 10.3 Automating Meetings / Scheduling

**Flow:** User approves “schedule meeting” → backend either creates an event (Calendar API) or returns a pre-filled link (e.g. Calendly) so the user or recipient can pick a time.

**Options:**

| Option | Pros | Cons | Automation level |
|--------|------|------|-------------------|
| **Calendly (or Cal.com, etc.)** | No OAuth in your app; just generate a link with prefilled title/description | User or recipient still picks time; no event created in your backend | Semi-auto: auto-generate link; human picks time |
| **Google Calendar API** | Create real events in a Google calendar; can add attendees | OAuth2, service account or user consent | Full auto: backend creates event (and can send invite) |
| **Microsoft Graph (Outlook)** | Same for Outlook/Office 365 | OAuth2 / app registration | Full auto |
| **iCal / .ics file** | Generate file; user downloads and adds to any calendar | No automatic invite email from you | Semi-auto: backend generates; user adds to calendar |

**Implementation pattern:**

1. **Draft-only (minimal):** Decision node already outputs `draft_meeting: { title, agenda }`. Frontend shows “Copy to calendar” or “Add to calendar” with a generated `.ics` (e.g. via a library like `icalendar`) — no backend calendar account needed.
2. **Link-based:** Backend builds a Calendly/Cal.com link with query params (e.g. `?title=Trial+Discussion&description=...`) and returns it in the approve response. Recipient opens link and books. No calendar API in your app.
3. **Full auto (Google/Outlook):** A dedicated `calendar_service` (e.g. `src/services/calendar_service.py`) with:
   - Google: service account or OAuth token, use `google-api-python-client` to create events and optionally add attendees (they get invite email from Google/Outlook).
   - Store calendar credentials in env or secrets (e.g. `GOOGLE_CALENDAR_CREDENTIALS_JSON` or refresh token).

**Recommendation:** Start with **draft + .ics** or **Calendly link**; add Google/Outlook when you need true “create event and invite” from the backend.

---

### 10.4 Contacting in General (Unified “Contact” Layer)

“Contacting” can mean email, meeting, SMS, or in-app notification. You can abstract this so the decision node only says “contact this role” and the execution layer chooses the channel.

**Channels:**

| Channel | Typical use | How to automate |
|---------|-------------|------------------|
| **Email** | Tech team, TPS, farmers (if email known) | As in §10.2. |
| **Meeting** | “Schedule a meeting to discuss trial results” | As in §10.3. |
| **SMS** | Farmers / cooperators (if only phone in `contact`) | Twilio, Vonage, or local provider; env: `TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN`, `FROM_PHONE`. Send only after approval. |
| **In-app / push** | Notify internal users (e.g. “New trial needs review”) | Store “notifications” in DB or Redis; frontend polls or uses WebSocket; or use Firebase/SendGrid in-app. |
| **Webhook** | Notify another system (e.g. CRM, task tool) | `POST` to a configured URL with payload (report_id, action_type, summary). |

**Unified execution service:**

- One place (e.g. `src/services/contact_executor.py` or `notification_service.py`) that:
  - Input: approved action (action_type, recipients, draft content, overrides).
  - Resolves final recipients (tech/TPS from config, demo partner from analysis).
  - Dispatches by `action_type` or `channel`:
    - `email_*` → email service;
    - `schedule_meeting_*` → calendar service or link generator;
    - `sms_*` → SMS provider (optional);
    - `webhook` → HTTP POST (optional).
- All automation (email, meeting, SMS, webhook) goes through this layer so logging, retries, and “approved but failed” handling are in one place.

---

### 10.5 Summary: Automation Checklist

| What | How to automate | Trigger |
|------|------------------|--------|
| **Emails** | Email service (SMTP / SendGrid / etc.) + optional templates | After user “Approve & send” (or batch approve). |
| **Meetings** | Calendly link or .ics draft first; later Google/Outlook API to create events | After user “Approve & schedule”; backend returns link or creates event. |
| **Contacting in general** | Unified executor that routes to email / meeting / SMS / webhook by action type | Same approval flow; add channels incrementally. |
| **Reminders / digests** | Cron or queue job that sends “pending trials for tech” or “meeting reminder” | Scheduled; can use same email (and later calendar) services. |

Keeping **human-in-the-loop** means: automation runs **after** the user confirms (approve-then-send). Optional later: “batch approve all” and “scheduled follow-up emails” using the same services.
