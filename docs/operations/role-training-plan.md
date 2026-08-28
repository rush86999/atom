# Role-based first-training plan: mini-canvas lessons per common small-business role

**Companion to:** `atom-self-hosted-pilot-instructions.md` (§1b data flow, Zoho section)
**Status (2026-08-27):** chat + /approvals review is LIVE; per-role mini-canvas
rendering is specified here and uses the existing canvas tool suite — implementation
is the next step.

---

## What the trainee experience is

A new hire starts as **STUDENT**: every automated action is blocked into a
training proposal, and the supervisor runs "first sessions" with it — real
tasks on real ingested data, supervised and scored.

A **session = one mini-canvas + 2–4 tasks on role-relevant records**, where:

- The **mentor** (atom_main, or a graduated same-domain agent) proposes the
  lesson: concrete tasks pinned to exact ingested records — editable by the
  supervisor before running.
- The hire executes in the training chat; each artifact it produces renders as
  a **mini-canvas card** on a session canvas (one canvas per session):
  - **email card** (`canvas_email_tool`) — draft outreach/replies
  - **docs card** (`canvas_docs_tool`) — summaries, plans, policies
  - **sheets card** (`canvas_sheets_tool`) — reconciliations, segment tables,
    aging buckets
- Every interaction lands in `CanvasAudit` bound to the training session
  (chat-session attribution is wired) → the episode's canvas context IS the
  scoring evidence. Supervisor scores on /approvals against what they see.

Trust progression per domain: STUDENT (observe/draft-only) → INTERN (may
propose actions, approval per action) → SUPERVISED/AUTONOMOUS, thresholds
auto-tuned per domain history (`promotion_policy_service`).

---

## Per-role plans

### 1. Sales / SDR (pilot — implemented)

- **Data:** Zoho CRM leads/deals (sync), Outlook threads (poller), OneDrive
  Cold Calling list, Zoho Flow pushes ("New Inbound" leads).
- **Mini-canvas:** lead card (company, contact, status) + email-draft card +
  call-priority list.
- **First session:** qualify newest lead → draft opening email → draft
  follow-up for second lead. *(This is the live pilot flow.)*

### 2. Finance / Bookkeeping (next — data already ingested)

- **Data:** WorkDrive `Accounting/` team folder — bills PDFs (LINK, Day & Ross,
  Roper Whitney…), bank statements, "Gary Payable" xlsx, AR aging folders
  (>30/60/90 days); Zoho Books invoices; OneDrive COGS/Cash Flow sheets.
- **Mini-canvas:** **reconciliation sheet** (bills PDF ↔ payment ↔ bank line,
  match/no-match flags) + AP-aging table + exception cards (amount mismatches).
- **First session:** "Reconcile these 3 bills from Accounting/Bills Checked
  against this month's payments; flag anything >30 days" — mentor supplies 3
  pre-matched examples from its own record.
- **Trust boundary (hard):** never send payments; drafts prepared for human
  execution. RUN-without-asking grows to *full reconciliation passes*, never
  money movement.

### 3. Operations / Coordination

- **Data:** Zoho Projects tasks, inventory items + sales orders (sync), work
  orders in H Drive (CNC/machine docs), Telegram escalations.
- **Mini-canvas:** order/job status tracker card + task board snapshot +
  shortage/al-flag cards.
- **First session:** "Summarize open production orders by stage; flag the two
  oldest stalled ones with a recommended nudge."

### 4. Marketing

- **Data:** SEMA leads list (OneDrive), product notes / price policy facts
  (business_facts), website content, campaign history (Outlook sent).
- **Mini-canvas:** copy-doc card (announcement/campaign draft) + audience
  segment table pulled from CRM filters.
- **First session:** "Draft the February customer update from the price-policy
  fact sheet; segment the audience list into distributors vs end users."

### 5. Support

- **Data:** support@ Outlook threads (CC patterns in real mail), service
  appointments (Zoho), Knowledge documents, ticket integrations if connected.
- **Mini-canvas:** ticket-thread card + response-draft card + knowledge-ref
  chips.
- **First session:** "Pick the most recent unresolved customer email, summarize
  the issue, draft a response citing one knowledge doc."

### 6. HR / Admin (light)

- **Data:** Docs canvas + templates, calendar, roster spreadsheets (OneDrive).
- **Mini-canvas:** checklist-doc card (onboarding/offboarding steps) +
  schedule summary.
- **First session:** "Assemble an onboarding checklist for the next hire from
  the standard template."

---

## Implementation notes (what exists / what's next)

| Piece | State |
|---|---|
| Typed canvases (email/docs/sheets) with audit | exists |
| Guidance broadcast (real-time op visibility) | exists, default-on |
| Session-bound canvas attribution | done (this week) |
| Chat + /approvals scoring loop | live |
| Mentor lesson anchored to role-tagged records | live |
| **Session mini-canvas rendering per role** | **implemented (2026-08-28)** — `core/role_template_registry.py` spawns the typed-canvas set at session start (`ChatSession` FK-safe row + `Canvas` + `CanvasAudit` stamped with the session id); `/approvals` renders the canvases as visual cards |
| Role templates as data | `ROLE_TEMPLATES` in `core/role_template_registry.py` — {canvas_set, default_tasks, trusted_scope} per role; bookkeeper hard boundary `never: [send_payment]` |

Role templates above are data files waiting to happen: `{domain} → {canvas
set, default tasks, trusted scope}` — the training proposal already carries
everything needed to pick one.
