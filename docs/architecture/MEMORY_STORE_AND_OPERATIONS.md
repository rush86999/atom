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
