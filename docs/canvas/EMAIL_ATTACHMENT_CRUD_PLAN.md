# Email Attachment CRUD (User + Agent) & Attachment Ingestion — Plan

Status: proposed · Author: ZCode · Date: 2026-09-01
Scope: email canvas attachments — user CRUD (UI), agent CRUD (governed tools),
send-with-attachments, and agent ingestion of attachment content into the memory index.

---

## 1. Current state (evidence)

What exists today, verified in-repo:

| Piece | State | Where |
|---|---|---|
| Email canvas source of truth | JSON blob appended to `CanvasAudit.details_json`; content is `{to, cc, subject, body}` — no attachments end-to-end | `backend/core/canvas_email_service.py:87-162,396-513` |
| Attachment fields (server) | `EmailMessage`/`EmailDraft`/`AddMessageRequest` already accept `attachments: List[Dict]` but nothing populates/renders them | `canvas_email_service.py:31-74`, `api/canvas_email_routes.py:56,199-218` |
| Attachment fields (frontend types) | `EmailAttachment {attachment_id, filename, file_type, size, url?}` and `EmailCanvasData.attachments` declared, never rendered | `frontend-nextjs/components/canvas/types/index.ts:61-100` |
| Registry | EMAIL canvas declares an `attachment_preview` component that is not implemented | `backend/core/canvas_type_registry.py:122-139` |
| Outlook download | `OutlookService.get_attachment_content(user_id, message_id, attachment_id)` works (Graph `GET /me/messages/{id}/attachments/{id}`) but **no route exposes it**; missing the normalized `get_attachment_metadata`/`download_attachment` wrappers | `backend/integrations/outlook_service.py:660-678` |
| Gmail download | `get_attachment_content` + `get_attachment_metadata` + `download_attachment` all exist | `backend/integrations/gmail_service.py:431,1000,1017` |
| Outlook ingestion gap | `core/ingestion_pipeline.py` calls `get_attachment_metadata`/`download_attachment`; Outlook lacks both → silent `AttributeError` → body-only fallback. **Outlook binary attachment ingestion is broken today** | `core/ingestion_pipeline.py:958-1115` (calls at 1004, 1060) |
| Attachment storage | **None.** Received bytes are deliberately stripped before persistence (`contentBytes`/`data` removed in `_index_attachments`); only metadata + `extracted_text` flag survive in the comms store | `integrations/atom_communication_ingestion_pipeline.py:2471-2528`, tests in `backend/tests/test_outlook_attachment_ingestion.py` |
| Binary text extraction | Docling + `AutoDocumentIngestionService.process_file_bytes` give a complete bytes→`documents`-table path (parse → redact → stable doc_id → vector upsert → PG mirror) — unused for email attachments in the live pipeline | `core/auto_document_ingestion.py:116-172,511-701`, `core/docling_processor.py:40,129` |
| Live polling pipeline | Text-only extraction (`_TEXT_ATTACHMENT_EXTENSIONS`, 512KB/20k-char caps); pdf/docx/xlsx/images get metadata only ("cheap in-process extraction doesn't exist" — but it does, via Docling) | `atom_communication_ingestion_pipeline.py:62-71,96,2184-2226,2226+` |
| Real-time email path | Graph webhook → `_fetch_message` returns raw message incl. attachments → `ingest_message` → `_normalize_message` | `integrations/outlook_realtime.py:171-215` |
| Agent tool pattern | `tools/*_tool.py` auto-discovered by `ToolRegistry.discover_tools()` (`registry.py:519`), registered with metadata in `initialize()` (`registry.py:617+`); executed via `MCPService.execute_tool` (`core/mcp_service.py:539`) | `tools/canvas_crud_tool.py`, `tools/calendar_tool.py:70,367` |
| Governance | `AgentGovernanceService.ACTION_COMPLEXITY` + `MATURITY_REQUIREMENTS` (`core/agent_governance_service.py:152,719,757`); per-user topics in `core/autonomy_policy.py:50-71,300`; HITL via `AgentProposal` (`core/proposal_service.py:170`) | send gate precedent: `integrations/chat_orchestrator.py:1856-1923` |
| Canvas write pattern | ownership check → append `CanvasAudit` row (user_id/agent_id/session_id) → WS broadcast `canvas:update` on `user:{id}` | `tools/canvas_crud_tool.py:25,260-320` |
| Auth | `Depends(get_current_user)`; ownership via `_get_owned_email_canvas_or_error` / `_verify_canvas_owner` | `api/canvas_email_routes.py:18-37` |
| Path anchoring bug class | any new `data/` path must anchor to `backend/` (pattern: `core/lancedb_handler.py:70-82`) | unanchored stragglers: `core/office_service.py:50` etc. |

---

## 2. Design decisions

### D1 — Storage: mailbox-authoritative for received, staged store for outbound

The durable store for a *received* attachment is the mailbox (Graph/Gmail). Re-fetch
on demand; never persist received bytes. This follows the repo principle that the
durable store is authoritative and avoids a second divergent copy (and respects the
existing "raw contentBytes never reaches storage" guarantee in
`test_outlook_attachment_ingestion.py`).

Outbound/draft attachments have no mailbox home until send, so they need a small
**staged file store**: `backend/data/email_attachments/{user_id}/{canvas_id}/`
(env: `ATOM_EMAIL_ATTACHMENT_DIR`), anchored with a
`_resolve_local_db_path`-style helper (copy from `core/lancedb_handler.py:70-82` —
do NOT resolve against CWD). Files are named `{attachment_id}` on disk (display
filename only in metadata — kills path traversal). Staged bytes are deleted on
send success, explicit removal, or canvas delete; a startup sweep removes orphans
older than N days.

### D2 — Attachment reference schema (canvas JSON)

One shape everywhere (frontend `EmailAttachment`, canvas `details_json`, WS frames,
send request). Extend the already-declared frontend type:

```jsonc
{
  "attachment_id": "AAMk...",          // provider id, or staged id "staged_{uuid}"
  "message_id": "AAMk...",             // null for staged/outbound
  "provider": "outlook",               // outlook | gmail | local (staged)
  "filename": "Q3_report.pdf",
  "content_type": "application/pdf",
  "size": 482133,
  "is_inline": false,
  "origin": "received",                // received | staged | agent_added
  "ingestion": {                       // null until ingested
    "status": "indexed",               // indexed | skipped | unsupported | pending
    "doc_id": "ext_<sha1>",            // documents-table doc id
    "ingested_at": "..."
  },
  "added_by": { "actor": "user", "user_id": "...", "agent_id": null },
  "created_at": "..."
}
```

No new SQL table. Canvas state already lives as the `CanvasAudit.details_json`
blob; attachments ride in `content.attachments` (mirrors how `thread_id`,
`draft`, `messages` already live there). `POST /api/canvas/email/{id}/message`
already accepts attachment dicts — align its shape to this schema.

### D3 — Ingestion lands in the `documents` table, not the comms store

The comms store (`atom_communications`) has no `user_id` filter column and keeps
only attachment summaries. Attachment *text* goes through
`AutoDocumentIngestionService.process_file_bytes` into the `documents` table with:

- `doc_id = ext_{sha1(integration_id:message_id:attachment_id)}` → stable, so
  `core/vector_upsert.upsert_document` dedups re-ingests (`skipped_unchanged`).
- metadata: `source_type: "email_attachment"`, `integration_id`,
  `external_id: {message_id}:{attachment_id}`, `email_subject`, `email_from`,
  `email_received_at`, `source_url` (Graph webLink / Gmail thread URL),
  `file_name/file_type/file_size`, `source_content_hash`.
- extra_columns: `freshness_status="fresh"`, `source_modified_at`,
  `source_url` (required by the freshness filter in `LanceDBHandler.search`).

This makes attachments first-class citizens of the hybrid recall path
(`DocumentsHybridSearch` → `memory_context_assembler._knowledge_leg` provenance
spotlight) with zero recall-side changes.

### D4 — Agent surface = one tool, actions inside; gated like canvas edits

A single auto-discovered `backend/tools/email_attachment_tool.py` exposing
`list / get_text / attach / remove / ingest` actions, registered in
`ToolRegistry.initialize()`. Read actions are STUDENT-level; `attach`/`remove`
map to `update_canvas` complexity (2); *sending* with attachments inherits the
existing `send_email` gate (complexity 3 + `email_policy`) — attaching to a draft
is reversible, sending is not, so the hard gate stays on send. New autonomy topic
`email_attachment` in `autonomy_policy.TOPICS` (mode `auto_if_mature`) so users
can pin it to `human_always`.

### D5 — LLM never sees raw bytes; attachment text is untrusted provenance

Agent-facing `get_text` returns size-capped extracted text wrapped in the
existing provenance trust lattice (`core/provenance.ProvenanceTagger.retrieved`,
same treatment as `_knowledge_leg`) — attachment content is retrieved data, never
instructions. Raw bytes are only ever streamed to the human's browser via the
download route.

---

## 3. CRUD matrix

| Op | User (UI) | Agent (tool) | Notes |
|---|---|---|---|
| **Create** | Upload file into compose/draft canvas (staged); attachment chips persist in canvas JSON | `attach` — stage a workspace file or reference an ingested doc into the draft | Received attachments are created by ingestion/send-sync, not by either actor |
| **Read** | Chip list, preview (extracted-text excerpt), download (stream-through proxy) | `list`, `get_text` (extracted text, capped) | Download of received = provider proxy; staged = disk |
| **Update** | Replace attachment (remove + add) on drafts; re-ingest | `remove` + `attach`; `ingest` (force re-extract; upsert dedups unchanged) | No in-place rename in v1 (Graph attachment rename is PATCH-able later) |
| **Delete** | Remove staged attachment (deletes bytes) / detach received attachment from canvas view | `remove` — same semantics, HITL-gated per D4 | Deleting a mailbox attachment in place is not a Graph capability; "delete" for received = detach from view |
| **Send** | Send button on a draft with attachments → provider upload then send | `_execute_send_email` path with attachments in proposal payload | Draft-based send (D6) |
| **Ingest** | "Add to memory" button on a chip → on-demand ingest | `ingest` action | Also automatic for received attachments per §4 |

### D6 — Send mechanics: draft-based, not `sendMail` inline

Graph `sendMail` with inline `attachments` caps around 3 MB total. Reliable path:
create draft → `POST .../messages/{id}/attachments` per file (upload session for
>3 MB) → `POST .../messages/{id}/send`. Gmail: multipart RFC 822 via the existing
send path. Extend `OutlookService.send_email` / `GmailService.send_email` with an
`attachments: List[Dict]` param (raw `{filename, content_bytes_b64, content_type}`
for staged files). `SendEmailRequest` grows `attachments: Optional[List[AttachmentRef]]`.
App-level cap: 20 MB/attachment, 10 attachments (env-overridable), consistent with
pipeline-B's `MAX_{ID}_ATTACHMENT_SIZE_MB=10` default.

---

## 4. Ingestion design

### 4a. Fix the broken Outlook branch (smallest change, biggest win)

Add thin wrappers to `backend/integrations/outlook_service.py` mirroring
`gmail_service.py:1000-1017`:

- `get_attachment_metadata(user_id, message_id)` → list `{id, name, size, contentType}`
  (Graph `GET /me/messages/{id}/attachments?$select=id,name,size,contentType,isInline`)
- `download_attachment(user_id, message_id, attachment_id)` → delegate to
  `get_attachment_content` (line 660)

This alone un-breaks the Docling branch in `core/ingestion_pipeline.py:958-1115`
for Outlook (it currently AttributeErrors into body-only fallback). Flag the
behavior change in `notes/AGENT_COORDINATION.md` — it changes what gets indexed
for every Outlook webhook/historical sync.

### 4b. Binary attachments in the live polling + realtime pipelines

In `atom_communication_ingestion_pipeline._normalize_message` (after
`_index_attachments`), for each attachment with binary extensions
(pdf/doc(x)/ppt(x)/xls(x)/images) and bytes already present from
`_expand_outlook_attachments` / `_expand_gmail_attachments`:

1. Budget guards: reuse `MAX_{OUTLOOK|GMAIL}_ATTACHMENTS_PER_EMAIL=5` and
   `MAX_{ID}_ATTACHMENT_SIZE_MB=10` semantics; run Docling in an executor with a
   per-poll budget (pipeline A already budgets attachment expands at 20/page).
2. `AutoDocumentIngestionService.process_file_bytes(content, file_name,
   source=f"email:{message_id}", user_id, workspace_id,
   external_id=f"{message_id}:{attachment_id}", extra_metadata=<D3 fields>)`.
3. Strip raw bytes exactly as today (`_index_attachments` invariant preserved);
   record `ingestion.status` + `doc_id` in the attachment dict.
4. Graceful degradation: if Docling unavailable (`is_available()` false), fall
   back to today's text-only behavior with `status="unsupported"`.

Same hook in the realtime path: `outlook_realtime._fetch_message` already returns
the raw message including attachments before `ingest_message`.

### 4c. On-demand ingest (canvas + agent)

`POST /api/canvas/email/{canvas_id}/attachments/{attachment_id}/ingest` and the
agent `ingest` action both call the same service function used in 4b, fetching
bytes via `download_attachment`. Updates `content.attachments[].ingestion` in the
canvas JSON + WS broadcast, so the chip shows indexed state.

### 4d. Recall

No recall-side changes required (documents table is already in the knowledge leg
with provenance spotlight). Optional follow-up: a `source_type="email_attachment"`
filter in `LanceDBHandler.search` for "search my attachments" queries.

---

## 5. API surface (all `Depends(get_current_user)` + ownership gate)

New/extended routes in `backend/api/canvas_email_routes.py`:

```
GET    /api/canvas/email/{canvas_id}/attachments                          # list (from canvas JSON, enriched)
POST   /api/canvas/email/{canvas_id}/attachments                          # multipart upload → stage (draft/compose only)
GET    /api/canvas/email/{canvas_id}/attachments/{aid}/download           # stream-through (received: provider; staged: disk)
GET    /api/canvas/email/{canvas_id}/attachments/{aid}/preview            # extracted-text excerpt (Docling, cached in ingestion record)
DELETE /api/canvas/email/{canvas_id}/attachments/{aid}                    # staged: delete bytes; received: detach from view
POST   /api/canvas/email/{canvas_id}/attachments/{aid}/ingest             # on-demand ingestion (4c)
POST   /api/canvas/email/send                                             # extend SendEmailRequest with attachments (D6)
```

Upload guards: extension whitelist (reuse `ALLOWED_EXTENSIONS` pattern from
`api/document_ingestion_routes.py:513-522`), 20 MB cap, per-canvas staged-size cap.

---

## 6. Agent tool & governance

**Tool** — `backend/tools/email_attachment_tool.py` (auto-discovered by the
`*_tool.py` glob; explicit registration with metadata in
`ToolRegistry.initialize()` like `_register_canvas_tools`):

```
email_attachment_tool(action: "list"|"get_text"|"attach"|"remove"|"ingest",
                      canvas_id, attachment_id?, file_ref?, user_id, agent_id?, session_id?)
→ {"success": bool, ...}
```

- Every action: ownership check (`_verify_canvas_owner` semantics), append
  `CanvasAudit` row (`action_type="email_attachment_update"`, `actor` =
  agent via `agent_id` vs user NULL — existing provenance convention), WS
  broadcast `{"type":"canvas:update","action":"email_attachments",...}` on
  `user:{user_id}` via `_broadcast_canvas_update`-style helper.
- `get_text` returns capped extracted text in provenance tags (D5), plus
  `{filename, size, content_type, ingested doc_id}` metadata.

**Governance wiring:**

- `AgentGovernanceService.ACTION_COMPLEXITY`: `email_attachment_read: 1`,
  `email_attachment_write: 2` (mirrors `update_canvas: 2`).
- `autonomy_policy.TOPICS`: new `email_attachment` topic, mode `auto_if_mature`
  (user can switch to `human_always` in the existing Autonomy panel).
- Sends with attachments: unchanged `send_email` gate; extend
  `core/email_policy.evaluate_email_action` to factor attachments (count/size;
  external recipients + attachments → same APPROVE/BLOCK tiers) — behavior
  change must be flagged in the coordination doc.
- HITL: when gated, file `AgentProposal` with attachment names/sizes in
  `proposal_data` (pattern: `_create_send_email_proposal`,
  `integrations/chat_orchestrator.py:2039`) so approvers see exactly what would
  be attached; execution via `ProposalService` executor fork.

---

## 7. Frontend

- New `components/canvas/EmailAttachmentStrip.tsx`: chips (filename, size, type
  icon), per-chip actions: download, preview (text excerpt modal), remove
  (drafts), "Add to memory" (ingest status), upload button in compose/draft
  layouts. Render it in **both** hosts:
  - chat-embedded: `components/chat/canvas-host.tsx` `CanvasContent` case
    `"email"` (lines 693-735) — currently To/Subject/Monaco body only;
  - full-page: `components/canvas/CanvasPanel.tsx` (email metadata + body).
- Types: extend `EmailAttachment` in `components/canvas/types/index.ts:94-100`
  to the D2 schema.
- WS: hosts already apply guarded `canvas:update` frames; handle
  `action:"email_attachments"` with the same `lastSavedSigRef` echo-guard.
- Autosave: attachments live in canvas `content`, so the existing idle-debounced
  `PUT /api/canvas/{id}` (`hooks/useCanvasAutosave.ts`) carries them — but the
  upload/download routes remain the bytes path.

---

## 8. Implementation phases

**Phase 1 — Provider plumbing** (no UI)
1. `OutlookService.get_attachment_metadata`/`download_attachment` wrappers.
2. Attachment-capable send: `OutlookService.send_email(attachments=...)`
   (draft → add attachment → send, upload session >3 MB);
   `GmailService.send_email(attachments=...)` multipart.
3. Unit tests vs mocked Graph/Gmail payloads (capture real payload shapes first —
   evidence over plausibility).

**Phase 2 — Ingestion**
4. Un-break `core/ingestion_pipeline.py` Outlook branch (falls out of 1).
5. Docling binary path in polling + realtime pipelines (4b), byte-strip invariant
   kept, status recorded.
6. Shared `ingest_email_attachment(...)` service function + on-demand route (4c).
7. Tests: idempotent re-ingest (upsert `skipped_unchanged`), Docling-missing
   degradation, budget caps; verify rows land in `documents` with provenance and
   surface in hybrid search spotlight.

**Phase 3 — Canvas API + staged storage**
8. Anchored staged-attachment store + cleanup sweep (D1).
9. Attachment CRUD routes (§5) + `SendEmailRequest`/`send_email` service
   extension + canvas JSON `attachments` persistence + WS broadcast.
10. Route tests: auth, ownership, size/extension guards, staged lifecycle
    (send deletes staged bytes).

**Phase 4 — Agent tool + governance**
11. `tools/email_attachment_tool.py` + registry registration.
12. `ACTION_COMPLEXITY` entries, `autonomy_policy` topic, `email_policy`
    attachment factor, HITL proposal payload.
13. Orchestrator: allow the planner/action path to invoke the tool for
    "attach X", "what's in the attachment", "remove the attachment".

**Phase 5 — Frontend**
14. `EmailAttachmentStrip` in both hosts + types + WS handling + upload/download.

**Phase 6 — Verification & trail**
15. End-to-end at the UI boundary (AGENTS.md §2): receive mail with attachment →
    chip appears; user downloads; agent attaches to draft; gated send proposal →
    approve → attachment arrives in real mailbox; ingest → recall answers
    questions about the PDF content with provenance spotlight; restart app →
    staged drafts survive, received attachments still resolve.
16. Unit tests for every heuristic (extension gates, caps, sanitization).
17. Update `notes/AGENT_COORDINATION.md` (start/finish, behavior flags:
    Outlook indexing change, `email_policy` change, new WS action).

---

## 9. Risks / watch items

- **Graph send inline limit (~3 MB)** → draft-based send is mandatory, not optional (D6).
- **Docling is an optional dependency** (`requirements-docling.txt`; commented out
  in `requirements.txt:70`) → all paths must degrade to today's metadata-only
  behavior without it.
- **Pipeline A latency**: Docling in the poller must be budgeted/executed off-loop;
  keep text-only fast path for text extensions.
- **Two Outlook services** (`integrations/` vs `consolidated/`): build on
  `integrations/outlook_service.py` (registry-mapped, `core/integration_registry.py:62`).
- **Path anchoring**: the staged store must anchor to `backend/` or we resurrect
  the root-vs-backend divergence bug class.
- **Coordination**: uncommitted work exists in `pages/canvas/[id].tsx` and
  `ChatInterface.tsx` (session continuity). Attachment work mostly touches
  `canvas-host.tsx`/`CanvasPanel.tsx`/`canvas_email_routes.py`, but re-check
  `git status` and the coordination doc before starting Phase 5.

## 10. Out of scope (v1)

- Editing attachment *content* in the canvas (office_service round-trip) — later.
- Inline image rendering (`is_inline`/`content_id` carried but not rendered).
- Attachment-level share/permissions beyond canvas ownership.
- Gmail-side label-driven ingestion changes (existing channels suffice).
