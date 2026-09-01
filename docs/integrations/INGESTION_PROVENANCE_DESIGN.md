# Ingestion → Agent Training: Real-Time Email, Selective Drive, Provenance

**Positioning (core value proposition):** ingestion is NOT a standalone ETL
service. Every ingested byte exists to make the hire smarter — ingested email
and drive data are **agent training / memory material**, recalled at work time
through the same provenance-tagged memory circuit that carries lessons,
episodes, and facts. The user journey below is written as a training journey:
connect → scope → agent learns the territory → agent pulls what a task needs
→ agent acts under the existing autonomy + HITL gates.

**Provenance research this design builds on:**

- **Spotlighting for indirect prompt injection** (CEUR Vol-3920) — untrusted
  data is *visibly delimited* in the context window so the model can treat it
  as data, never instructions. Already implemented in `core/provenance.py`
  (trust lattice: SYSTEM/USER > MEMORY > TOOL_OUTPUT/FILE/FEDERATION/
  RETRIEVED; tool invocations parsed only from trusted chunks).
- **IntentGuard / Microsoft** (arXiv 2512.00966) — same contract: untrusted
  chunks delimited; tool-call extraction refuses untrusted provenance.
- **Data provenance for RAG / attribution** (lineage + source attribution):
  every retrieved item must carry *where it came from* (system, author,
  fetched-at, external id) so responses are attributable and stale/mistrusted
  sources are downrankable. Atom's `doc_freshness_service` + IngestedDocument
  freshness columns are the local implementation of this.

---

## 1. Gap analysis: email ingestion vs drive ingestion (security · trust · provenance)

| Dimension | Email (Outlook pipeline) | Drive (OneDrive/WorkDrive/Dropbox) | Gap + action |
|---|---|---|---|
| Transport auth | OAuth Mail.Read per user; poller resolves the user's stored token | OAuth per user (Files.Read/All) | Parity. |
| Real-time | 60s polling; Graph-compatible webhook route exists (`/api/integrations/microsoft365/webhook`) but **no subscription lifecycle** (create/renew/persist); the legacy memory webhook requires a custom secret header Graph will never send | None (manual sync) | **Build**: env-tuned poll interval + subscription lifecycle on the compatible route. |
| Scope selection | N/A (mailbox is inherently scoped; dedup by message id) | `IngestionSettings` supports folders/types/size cap, but no UI for M365 and no structure-only mode | **Build**: selective UI + tree mode (below). |
| Content provenance at work time | Comms store rows carry app/sender/timestamp; rendered as `[source: label]` snippets — attribution present, but no explicit untrusted-data spotlighting | Docs carry source/freshness; same rendering | **Build**: spotlight the knowledge leg (untrusted-data banner + per-hit source) per the Provenance lattice. |
| Injection surface | Email bodies are attacker-controlled text → indirect prompt injection via recall. Mitigated only if rendered as spotlighted data | File contents: same class of risk | **Build**: spotlighting (same as above). Tool-invocation extraction already refuses untrusted chunks (`core/provenance.py`). |
| Secrets handling | Raw bodies ingested as-is | `AutoDocumentIngestionService` runs a **secrets redactor** on files | **Gap (email)**: no redaction pass on ingested email bodies. Documented; follow-up to reuse the redactor for comms. |
| Webhook verification | Legacy route: shared-secret header + JWT (incompatible with Graph). M365 route: Graph validationToken echo — **no clientState verification** on notifications | n/a | **Build**: verify `clientState` on every notification; reject mismatches (spoofed-notification guard). |
| Dedup / replay | message-id seen-set + cursor | external_id + modified_at freshness | Parity. |
| Audit | ingestion logs | ingestion logs + CanvasAudit n/a | Parity (acceptable). |
| Agent access control | recall is workspace-scoped; actions gated by autonomy policy + HITL | recall workspace-scoped; NEW agent-initiated file ingestion must respect settings cap + enabled flag | **Build**: tool gates (`drive_ingest_file` respects settings; maturity-gated via tool registry). |
| Tenant/workspace isolation | workspace-scoped LanceDB | workspace-scoped LanceDB + per-workspace settings (fixed 2026-08-30) | Parity. |

**Trust summary:** email is the *higher-frequency, higher-injection-risk*
channel (attacker-authored content arrives unprompted); drive is the
*higher-volume* channel (size/cost risk). The controls mirror that: email
gets real-time + injection spotlighting; drive gets selective scoping +
structure-first ingestion (see the file below the tree, never the whole
drive).

## 2. User journey (training-first) + UI/UX

**J1 — Connect (once).** Settings → Microsoft 365 → Connect (existing OAuth).
Landing state explains the model in one line: *"Atom learns your work
territory: it reads your inbox in near-real-time and maps your drive
structure — file contents are pulled only when a task needs them."*

**J2 — Scope (the size lever).** Settings → **Data for your agents**
(new panel per connector):
- Toggle: inbox ingestion on/off; poll cadence shown (Webhook ⚡ when public
  URL configured, else Ns polling).
- Drive: **"Map structure"** button → ingests the full folder/file LISTING
  (paths, sizes, modified dates — kilobytes, not gigabytes). Progress +
  counts shown.
- Drive contents scope: folder checkboxes (from the mapped tree), file-type
  chips, per-file size cap, auto-sync toggle. Default: **structure mapped,
  contents OFF** — the agent knows what exists; it pulls contents on demand.

**J3 — Agent works (real time).** An inbound email arrives (webhook ⚡ or
next poll) → ingested → the linked hire recalls it in the very next turn
(provenance-spotlighted: source, sender, when). Communication intelligence
modes (suggest/draft/auto_send — default suggest) can pre-draft a reply that
lands in the existing HITL approval flow. Autonomy policy still gates any
send.

**J4 — Agent pulls what a task needs.** "Summarize the Q3 contracts" → the
hire calls `drive_search_tree` (search the mapped structure), picks the
relevant files, calls `drive_ingest_file` per file (size-cap enforced,
contents ingested + provenance-stamped), then answers with per-file
attribution. The user watches this happen in the agent trace — training by
working.

**UX surfaces:**
- `Settings → Data for your agents` panel (new; per-connector sections:
  Outlook inbox, OneDrive). Reuses the existing settings API; Zoho WorkDrive
  panel remains as-is.
- Agent tools surface in the existing trace UI (no new chrome).

## 3. Build map

| Piece | Where |
|---|---|
| Drive tree (structure) ingestion + picker + counts | `core/drive_tree_ingestion.py`, `api/document_ingestion_routes.py` |
| Agent tools `drive_search_tree` / `drive_ingest_file` | `tools/drive_tool.py` (tool registry; maturity-gated) |
| Real-time email: poll env + Graph subscription lifecycle + clientState check | `integrations/atom_communication_ingestion_pipeline.py`, `integrations/microsoft365_routes.py`, `integrations/microsoft365_service.py` |
| Provenance spotlighting of the knowledge leg | `core/memory_context_assembler.py` |
| Selective-ingestion UI | `frontend-nextjs/components/Settings/OneDriveIngestion.tsx` |

## 4. Research findings incorporated (web-sourced 2026-09-01)

**Temporal staleness / expired facts (hybrid search):**
- The field's converging pattern is *bi-temporal validity*: give every fact a
  lifetime rather than treating it as permanently true — Zep's Graphiti
  ("give every fact in our knowledge graph an expiration date") and the
  CIKM'25 "When Facts Expire" benchmark; arXiv 2510.13590 shows RAG largely
  ignores the temporal nature of facts and degrades on stale knowledge.
- The "changed fact = NEW fact, not an edit" retrofit pattern (treating a
  changed source as a new entry, old one superseded) matches what Atom's
  freshness service already does (content-hash → `stale`, re-ingest creates a
  fresh copy, old vector row removed, GraphRAG edges stamped superseded).
- **Applied here:** (a) the drive tree index stamps per-file
  `source_modified_at` as a top-level filterable column so the existing
  freshness filter covers structure rows too; (b) the knowledge leg renders
  staleness explicitly (a hit whose freshness_status is non-fresh is rendered
  as `STALE/OUTDATED` in the spotlighted block instead of silently mixing in);
  (c) email-derived knowledge is inherently time-boxed — recency is surfaced
  in the rendered line (`as of <date>`), because a fact extracted from a
  2024 email is not a fact about today.

**Real-time email (Microsoft's own recommended pattern):**
- Webhooks signal *that* something changed; **delta queries fetch *what*
  changed** (deltaLink/skipToken) — [Microsoft Learn:
  webhooks](https://learn.microsoft.com/en-us/graph/change-notifications-delivery-webhooks),
  [Connell's delta+webhook pattern](https://www.andrewconnell.com/articles/microsoft-graph-webhook-delta-query/).
- Mail subscriptions expire (max ~3 days) → a renewal loop is mandatory;
  `clientState` validation is the anti-spoofing control
  ([Hookdeck guide](https://hookdeck.com/webhooks/platforms/guide-to-microsoft-graph-webhooks-features-and-best-practices),
  [M365.fm](https://www.m365.fm/blog/the-ultimate-guide-to-managing-microsoft-graph-webhook-subscriptions/)).
- **Applied here:** poll interval env-tunable (fallback channel), Graph
  subscription lifecycle (create/renew, clientState verified, state
  persisted) on the already-Graph-compatible webhook route, delta-style
  fetch via the existing receivedDateTime cursor + seen-id dedup (deltaLink
  upgrade documented as follow-up).

**Selective vs bulk ingestion (agentic RAG consensus):**
- The industry has converged on *keep lightweight references (paths /
  metadata), load content just-in-time*: pre-indexing everything costs
  storage and goes stale; JIT agentic retrieval wins on freshness and
  relevance at the cost of query-time latency
  ([Airbyte: dynamic context retrieval](https://airbyte.com/agentic-data/dynamic-context-retrieval),
  [Xebia: personal RAG without the drag](https://xebia.com/blog/personal-rag-without-the-drag/),
  [Moveworks: from indexing to agentic reasoning](https://www.moveworks.com/us/en/resources/blog/enterprise-search-from-indexing-to-agentic-reasoning),
  [Elastic: context engineering & relevance](https://www.elastic.co/search-labs/blog/context-engineering-relevance-ai-agents-elasticsearch)).
- **Applied here:** structure-first (map the whole tree as kilobyte-scale
  metadata docs), contents just-in-time via the agent's `drive_ingest_file`
  tool, scoped by the user's selective settings. This is agent *training*:
  the hire learns the territory map, then exercises it per task/goal.

**Provenance as a security control (not just citation quality):**
- 2025 literature treats provenance-aware memory as the defense against
  *memory poisoning*: attacker-controlled content (an inbound email) must be
  traceable to its source and must never become trusted instructions
  ([Evidence Tracing & Execution Provenance in LLM Agents, arXiv 2606.04990](https://arxiv.org/html/2606.04990v1),
  [Vectorize: memory poisoning defense in depth](https://vectorize.io/articles/how-to-prevent-ai-memory-poisoning),
  [provenance-aware controls before memory becomes an execution source](https://nhimg.org/articles/memory-poisoning-turns-agent-memory-into-a-durable-attack-surface/)).
  Promptfoo even ships a red-team plugin for fabricated citations
  ([source-attribution plugin](https://www.promptfoo.dev/docs/red-team/plugins/rag-source-attribution/)).
- **Applied here:** the knowledge leg renders every ingested hit inside the
  existing Provenance spotlighting convention (untrusted retrieved data,
  explicit source attribution, staleness flagged), and tool-invocation
  extraction already refuses untrusted chunks. Fabricated-attribution is
  testable later via the same red-team approach.
