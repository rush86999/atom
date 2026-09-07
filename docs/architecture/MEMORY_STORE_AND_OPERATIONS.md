# Memory Store & Operational Invariants

> **Status:** Implemented 2026-09-02 after the "agent can't find the email"
> incident chain (store divergence + stale server + Graph KQL rejections).
> **Related code:** `backend/core/lancedb_handler.py` (`_resolve_local_db_path`),
> `backend/core/memory_store_bootstrap.py`, `scripts/restart_backend.sh`,
> `backend/integrations/outlook_service.py` (`sanitize_graph_kql`),
> `backend/core/outbound_identity.py`, `backend/core/auto_dev/` (evolution
> harness: `tool_error_signals`, `reflection_engine`, `guidance`).

---

## TL;DR — the five invariants

1. **ONE memory store, anchored to `backend/`.** Every LanceDB path resolves
   through `LanceDBHandler._resolve_local_db_path`. Never `lancedb.connect()`
   a CWD-relative path.
2. **`create_all` only sees imported models.** Any new `Base` subclass in a
   lazily-imported module must be imported in the startup lifespan *before*
   `Base.metadata.create_all`.
3. **The API server does NOT run `--reload`.** After editing backend code,
   run `scripts/restart_backend.sh` — testing against a stale server
   produces false bug reports (two in one day, 2026-09-02).
4. **Graph `$search` KQL rejects `@` and `.` in free text** (400s). Every
   mailbox search path must go through `sanitize_graph_kql`, and the search
   must supplement live Graph with the ingested mailbox store
   (addresses/nicknames don't match free-text KQL).
5. **Identity and per-install knowledge are DATA, never code.** Sender
   identity, team members, dealer/vendor roles come from the users table +
   installation profile; no person/org names in platform source.

---

## 1. The memory store: one location, one resolver

The embedded LanceDB memory lives at **`backend/data/atom_memory/<workspace>/`**
(workspaces: `default`, `default_shared`, per-user UUIDs). This is
independent of the launch CWD.

| Env var | Meaning | Default |
|---|---|---|
| `LANCEDB_URI` | Base path used by `LanceDBHandler` | `./data/atom_memory` (anchored → `backend/data/atom_memory`) |
| `LANCEDB_URI_BASE` | Base path for per-workspace handlers + file context | `./data/atom_memory` (anchored likewise) |
| `LANCEDB_CLOUD_ENABLED` | Personal Edition: `false` (embedded file store) | `false` |

Relative paths passed to these env vars are anchored to `backend/` by
`_resolve_local_db_path`; absolute and object-store URIs pass through.

### Store layout: local (fresh default) vs external drive

A fresh installation needs **no external drive** — the store is a plain
local directory at `backend/data/atom_memory/` and every feature runs
against it. External storage is an OPT-IN for machines that want heavy
data off the internal disk:

1. **Local (fresh default).** Nothing to configure. `restart_backend.sh`
   keeps DB snapshots under `backend/data/backups/` (last 5) and stays
   silent about external drives.
2. **Drive-hosted via symlink.** Move `backend/data/atom_memory` onto a
   mounted volume and symlink it back
   (`atom_memory -> /Volumes/<drive>/…/atom_memory`). Optionally set
   `ATOM_EXTERNAL_DRIVE=/Volumes/<drive>` so `restart_backend.sh` also
   mirrors DB snapshots to `<drive>/atom-backups/` and
   `scripts/drive_status.sh` knows the layout is drive-hosted.
3. **Explicit env override.** Point `LANCEDB_URI` / `LANCEDB_URI_BASE` at
   any path (or object-store URI) without symlinks.

**Disconnect semantics (drive-hosted only):** the symlink dangles →
construction/import still succeed (guarded mkdir), per-call memory
operations fail loudly, `/api/health` reports `degraded`, and ingestion
"pauses" — the poll loop rolls back fetch cursors when messages fail to
store, so the window is re-walked and mail is ingested once the drive
returns. Recovery on replug is automatic; **no restart needed**, and a
local fallback store is deliberately NOT used (writes there would fork
the store — see the divergence incident in `AGENTS.md`).


**Rules for code:**
- Never call `lancedb.connect()` with a raw relative path — route through
  `LanceDBHandler`, or reuse `_resolve_local_db_path`.
- The components that historically forked the store: the ingestion pipeline
  (now anchored), `agent_file_context` (anchored), `chat_tool_planner`
  address search (anchored). When adding a new store access, reuse the
  resolver.

**Startup reconciliation** (`core/memory_store_bootstrap.reconcile_memory_store`,
run in the lifespan before workers): if a LEGACY CWD-relative store
(`<repo>/data/atom_memory/<ws>`) exists and the anchored workspace has no
tables, the legacy tables + `poll_fetch_state.json` are **adopted**
(copied) into the anchored base. Never overwrites an anchored store that
already has tables (durable store is authoritative). Idempotent. A legacy
root store left behind is a frozen backup — the app no longer reads it.
Divergence is observable via `memory_store_status()`.

## 2. Restarts: `scripts/restart_backend.sh`

The API server runs without `--reload`. Code changes are inert until a
restart, and a stale server **produces false bug reports** — in one day it
caused a fixed Graph 400 to reappear in logs and a user-tested regression
that no longer existed.

```
./scripts/restart_backend.sh          # kill stragglers, start one instance,
                                      # poll /api/health, fail loudly
```

Ad-hoc `kill <pid>` + manual `nohup uvicorn …` is how we ended up with two
instances fighting over :8001 and a zombie app ingesting data without
listening. Use the script.

**Startup ordering that matters** (`main_api_app` lifespan):
1. SQLite schema-drift repair → import late model modules (`core.auto_dev.models`)
   → `Base.metadata.create_all` (dev; Alembic in production)
2. `reconcile_memory_store()`
3. Auto-Dev `ReflectionEngine.register_global()` (turns task-fail events
   into Memento/AlphaEvolver fix candidates)
4. Routers mount (`/api/autodev/…` review surface included)

## 3. Mailbox search: Graph KQL constraints

Graph `$search` free-text 400s on `@` and `.` (and other punctuation) —
and even legal queries do not match sender ADDRESSES or nicknames ("Jason"
never matches "Jacob" Schulz; `jschulz` is only an address local-part).

Rules:
- All `$search` builders go through `sanitize_graph_kql`
  (`integrations/outlook_service.py`): strips everything but word chars,
  whitespace, apostrophes. `jschulz@blumetric.ca` → `jschulz blumetric ca`.
- `$filter contains(...)` string literals escape single quotes (OData `''`).
- Search results supplement live Graph with the **ingested mailbox store**
  (per-term hybrid search + deterministic per-address LanceDB lookup,
  `_search_ingested_by_address`) — the ingested copy carries full content
  and is authoritative for "find the email" questions.
- Swallowed tool errors are recorded as structured
  `AgentExecution.metadata_json["tool_errors"]` (integration chokepoint) —
  never return `[]` on a failure without recording it.
- **Hybrid search is healthy and layered** (`atom_communications`: fastembed
  vectors non-zero, FTS index live). Layering for "find X's email" queries:
  semantic/FTS fusion alone under-ranks rare address tokens, so
  `search_communications` prepends a dedicated FTS query per address-like
  token and filters seeded mock rows; on top of that, the outlook tool
  resolves addresses from the surrounding CONVERSATION (a user says "Jason"
  — the contact is "Jacob" and the address lives in the transcript, not the
  query) and does a deterministic containment lookup
  (`_search_ingested_by_address`). Name-only queries without any address
  anywhere in context remain a genuine limitation — the ontology identity
  layer is the long-term remedy.
- **BYOK vision routing** (`core/llm/byok_handler.py`): image turns pass
  `required_capability="vision"` into provider ranking (image turns also
  bypass streaming) and charge ~1106 tokens to the context estimate for the
  image. Capability lookups are prefix-tolerant for composite BYOK ids
  (`openrouter/openai/gpt-4o` → `openai/gpt-4o` → `gpt-4o`) in both the
  pricing-cache check and the ModelCatalog filter — without this, BYOK
  vision models were classified text-only and image turns panic-fell back
  to GPT-4o on a key the user may not have. Cost attribution needs no
  change: provider `usage.prompt_tokens` already includes image tokens.
- **Email tables survive ingestion** (`_html_to_text_with_tables`): HTML
  data tables become markdown in the stored content (FTS/vector/LLM
  readable — pipes are unambiguous to agents) and structured rows ride in
  `metadata["tables"]` (max 5 tables × 30 rows). Single-column tables
  (Outlook signature/layout tables) are skipped. Agents rebuild real HTML
  tables in the email canvas from the markdown (canvas editor is taught;
  tables survive the sanitizer and the send path).
- **Agents query this directly**: the planner exposes a `memory` service
  ("ingested workspace memory") on every chat turn — ALWAYS available (no
  external key; never couple it to web-search gating), executed via
  `DocumentsHybridSearch` + the deterministic address lookup over the
  conversation context. Ingestion writes hybrid-ready data at ingest:
  vectors at write time (fastembed), FTS index at table init. Backfill note:
  legacy documents rows may have zero vectors — the lexical leg covers them.

## 4. Outbound identity: per-install data, never code

A fresh installation has a team of members; **each member owns and trains
agents that sign as their owner** (`agent_registry.user_id`), falling back
to the session user, then the installation profile's wizard-entered
`sender_name`. Allowed senders = tenant users + installation-profile
`people[]`, classified by their own role (`dealer`/`vendor` → external;
`internal` → team) with email-domain fallback. The deterministic gate
(`signature_identity_violation` / `signature_signer_status`) hard-fails
off-team signers and softly corrects teammate attributions — in chat
replies (signature scan) and at the integration chokepoint (attribution
param keys: `from`/`as_user`/`assignee`/`organizer`/`owner`…).

**Never hardcode a person, company, or role name in platform code.** New
install reach competence through installation-profile data
(`docs/architecture/INSTALLATION_ADAPTATION_PLAN.md`).

## 5. Evolution harness: triggers and surfaces

Flow: tool error → `record_tool_error` (execution metadata + ring) →
REAL-TIME `trigger_live_tool_fix` when a signature crosses threshold
(AlphaEvolver tool mutation, no episode needed; once per signature/30min) →
episode finalization downgrades tool-error turns to `partial` → fail event →
ReflectionEngine routes patterns (tool → AlphaEvolver, else Memento skill).
All candidates are PENDING; review them in Agent Studio → Auto-Dev Fixes
(`/api/autodev/candidates|approve|reject|tool-errors|guidance`). Guidance
banners + websocket `autodev_guidance` keep the supervisor informed.
Verifier judges run with generous max_tokens (reasoning models truncate
silently otherwise); shadow→enforce flips are eval-gated product decisions.

## 6. Ingest idempotency: the store gate + duplicate-row heal (2026-09-06)

Every write into `atom_communications` funnels through
`LanceDBMemoryManager.ingest_communication` / `ingest_generic_record`
(`ingest_batch` delegates). Two guards run there, both ownership-scoped
(same-owner or unstamped rows block; a DIFFERENT owner's row never does —
same contract as the poll-level `_dedup_messages`):

1. **id guard** (`_stored_row_blocked`) — a row with the same
   `(app_type, id)` already in the shared table blocks the write. Covers
   the Sep 5 multi-process double-poll (seen-id map is per-process; the
   store is the cross-process authority).
2. **content-identity guard** (`_stored_content_blocked`) — same
   `(app_type, sender, recipient, subject, body-hash, timestamp)` under a
   DIFFERENT id also blocks (fetch paths that re-stamp ids). A genuine
   re-send has a new timestamp and still ingests. Fails open: a hiccup
   re-risks a duplicate, never loses mail.

**Duplicate-row heal** (`_heal_duplicate_rows`, called from
`initialize()`): once per store (marker row in `ingestion_metadata`,
`app_type='__store_heal_comms_dedup_v1'`), scans rows with `_rowid`,
groups by the same keys as the guards, deletes redundant rows via precise
`_rowid IN (...)` deletes under `_store_surgery_lock`. Existing installs
converge to fresh-install state; fresh installs pay one empty scan. Deletion
mistakes are recoverable — maintenance keeps 7 days of table versions.

Chat-side, the address lookup in `core/chat_tool_planner.py`
(`_rank_address_hits`) additionally dedupes for PRESENTATION (re-ingested
copies under re-stamped timestamps share content but not row ids).

**Generalization (2026-09-06, later same day):** the ingested-mailbox
supplement is no longer outlook-specific. gmail, slack, teams, discord,
google_chat, telegram, whatsapp and zoho_mail route through the universal
integration path in `core/chat_tool_planner.py`, and their blocks now get
the same ranked ingested-copy rescue — ingested lines LEAD a successful
live search (provider relevance ranking is known to bury participant
messages under unrelated traffic), carry the dead-end when the live search
returns nothing, and fire for ANY service once an email-address fragment
appears in the query or recent history. `_ingested_mailbox_lines` is the
shared helper; the outlook leg calls it too.

**Per-term retries + connected-tool hint (2026-09-06, final pass):** two
more outlook-only techniques generalized. (1) Comm services on the
universal path now retry an empty-success live search ONE TERM AT A TIME
(≤2 calls, longest terms first) — AND-semantics providers (slack, gmail)
zero out when any common token misses; outlook already fanned out per-term
against Graph's OR-ranking. Order on a comm dead-end: deterministic
ingested mailbox → per-term retries → semantic memory → honest dead-end.
(2) The memory-assembler header no longer hardcodes "the outlook tool":
it names the user's ACTUALLY connected mailbox/chat tools
(`_mailbox_tool_hint` via `get_connected_services`, neutral wording when
none), so gmail-only agents are never told to use a tool they don't have.

**Backfill extraction budget (2026-09-06 evening):** a restart-time poll
backfilled 179 never-seen old messages; each fired TWO LLM pipelines
(knowledge extraction + communication intelligence), saturating the event
loop for 30+ minutes — every endpoint starved, which surfaced as the chat
"open in canvas" button silently timing out (`ECONNABORTED` at 30s, the
frontend catch swallowed it). Auto-extraction is now age-budgeted:
`ATOM_KG_EXTRACT_MAX_AGE_DAYS` (default 30, 0 = unlimited). Older backfill
is indexed and searchable but does not fire LLM extraction. The frontend
to-canvas handlers now toast on failure instead of an empty catch.

**Chat-path sync scans off the loop (2026-09-06, generalized):** the
SYNC-OFF-LOOP pattern now covers the shared chat tool planner. The comms
address scan (`_search_ingested_by_address` — full-table walk, ~4s at 3.5k
rows), the exact-token scan, and the documents-table excerpt loader all run
via `asyncio.to_thread`; the excerpt loader is additionally batched to ONE
table load per memory search (it previously re-loaded the full documents
table PER HIT, up to 8 loads per query, on the loop). The loop-stall
regression test (`test_mailbox_lines_offload_keeps_loop_responsive`) fails
if a scan ever goes back on-loop.
