# Org Ingestion Sharing — Plan

> **Status:** **ALL PHASES IMPLEMENTED** (backend, Aug 16, 2026) — Phases 0–2, 2b
> (memory bundle), and 3 (org ingestion hub). **Setup/ops runbook:
> [ORG_SHARING_SETUP.md](ORG_SHARING_SETUP.md)** (topology, key ceremony, egress
> policy, rotation, validation checklist). Flags: `ATOM_ORG_SHARING_ENABLED`
> (default **off**), `ATOM_ORG_HUB_ENABLED` (hub side), `ATOM_ORG_HUB_URL` +
> `ATOM_ORG_HUB_API_KEY` (member pull loop).
> Implemented surface: `core/org_sharing_crypto.py` (Ed25519 sign/verify + key
> registry), `core/ingestion_profile_service.py` (Phase 1 config profiles),
> `core/org_data_bundle_service.py` (Phase 2 data bundles + Phase 2b graph/text
> sections), `core/org_hub_service.py` (Phase 3 delta bundles + member pull),
> Phase 0 persistence in `core/hybrid_data_ingestion.py` (→ `ingestion_settings`),
> routes in `api/data_ingestion_routes.py` (`/org-key`, `/profile/{export,import}`,
> `/bundle/{export,import}`, `/hub/bundles`, `/hub/pull`), migration
> `20260816_org_ingestion_sharing`, models `OrgPublicKey` / `IngestionProfileImport`
> / `BundleExport` / `BundleImport`.
> **Audience:** members of the same organization, each running Atom locally (Personal
> Edition: local Docker + SQLite + embedded LanceDB). Not cross-org, not marketplace,
> not SaaS multi-tenancy.

---

## 1. Problem

Org members run independent Atom instances. Each instance connects to the **same
upstream org sources** (one Salesforce org, one Slack workspace, one Google Workspace
domain), so today every member who wants CRM/context data must independently connect,
authorize, and re-ingest the same records — duplicated API quota, duplicated storage,
and divergent copies that drift out of sync.

Meanwhile the pipeline **code** is already shared (same repo), and the platform already
moves *templates* between instances (workflow templates, mini-app share tokens, skill
marketplace). What does not exist is any mechanism to share ingestion **configuration**
or ingested **data** between instances. Verified negatives:

- `HybridDataIngestionService` sync configs and usage stats are **in-memory dicts**
  (`core/hybrid_data_ingestion.py:152-153`) — lost on restart, never persisted, never
  exportable.
- No export/import endpoint exists for `ingestion_settings`, `IngestedDocument`s,
  LanceDB contents, or discovered entities anywhere in `backend/api/`.
- Federation routes (`api/routes/federation_routes.py`) are identity primitives only,
  explicitly in-memory and non-persistent. The marketplace hub moves skills/agents/
  workflows — never ingested data.

## 2. What "shareable" decomposes into

| Layer | Shareable? | Mechanism |
|---|---|---|
| Pipeline code | Already shared | Same open-source repo on every instance |
| Pipeline config (sources, entity types, frequencies, folder rules) | Yes — Phase 1 ✅ | Versioned JSON **Ingestion Profile**, credential-stripped |
| Ingested data (normalized records, entities, GraphRAG nodes) | Yes, opt-in — Phase 2 ✅ (records); Phase 2b (GraphRAG + raw text, proposed) | Signed JSONL **Org Data Bundle**, re-embedded on import |
| Episodic memory / chat / turn facts | **No — permanently out of scope** | Identity-bound: drives per-agent graduation and trust gating (see Phase 2b table) |
| Continuous org-wide sync | Optional — Phase 3 | **Org Ingestion Hub** (one designated instance) |

Established in-repo patterns this plan reuses rather than reinvents:

- Credential-stripped JSON export/import: `core/workflow_template_system.py:375-402`
  + `core/blueprint_sanitizer.strip_credentials` (P5 Blueprint Security).
- Share-token distribution: mini-app `POST /share` + `POST /by-token/{token}/install`
  (`api/mini_app_routes.py:332,368`).
- Import idempotency: `document_ingestions` unique `(workspace_id, doc_id)`
  (`core/models.py:10969-10983`).
- Sensitivity classification for outbound gating: P4 data-taint tracker
  (`core/data_taint_tracker.py`), `sensitivity` column already on `IngestedDocument`.
- Per-workspace physical storage: `backend/data/atom_memory/{workspace_id}` (anchored to `backend/` — never CWD-relative; see `MEMORY_STORE_AND_OPERATIONS.md`)
  (`core/lancedb_handler.py:1530-1572`).

## 3. Target architecture (org model)

```
┌─────────────────────────┐          ┌─────────────────────────┐
│  Member A (local Atom)  │          │  Member B (local Atom)  │
│                         │          │                         │
│  personal sources ──────┼──┐    ┌──┼───── personal sources  │
│  (own credentials)      │  │    │  │   (own credentials)   │
└─────────────────────────┘  │    │  └─────────────────────────┘
                             ▼    ▼
                   ┌──────────────────────┐
                   │  Ingestion Hub       │  (Phase 3; until then
                   │  (designated         │   any member can export)
                   │   member's instance  │
                   │   or small server)   │
                   │                      │
                   │  org sources (one    │
                   │  Salesforce/Slack/   │
                   │  Drive connection,   │
                   │  org service account)│
                   └──────────┬───────────┘
                              │  signed Org Data Bundle (JSONL)
                              │  + Ingestion Profile (JSON)
                              ▼
                   members import → re-embed locally →
                   normal governed ingestion path (audit, GraphRAG, memory)
```

Key principles:

1. **Ingest org-wide sources once** (hub), **re-embed everywhere** (members). Bundles
   carry normalized text + metadata — never embeddings (instances run different
   embedding providers under BYOK; 1536-dim OpenAI vs 384-dim fastembed vectors are
   not interchangeable, `core/lancedb_handler.py:177-180`).
2. **Credentials never travel.** Every export path runs `strip_credentials`. Members
   connect their own tokens for personal sources; only the hub holds org source
   connections (an org service account, not a member's personal OAuth).
3. **Org membership ≠ equal access.** Exports are scoped per bundle; restricted/
   confidential rows (P4 classifications: HR, finance, PII) are excluded by default
   and can be shared only in explicitly-scoped sub-bundles (e.g., a finance-team
   bundle).
4. **Imported data is untrusted input.** It re-enters through the existing ingestion
   paths (`memory_handler.add_document`, `graphrag.ingest_document`) so governance,
   audit, and sandbox layers apply as if the member had fetched it themselves.
5. **Local-first.** Phases 1–2 work with no infrastructure: a file sent over any
   channel. Phase 3 adds a live pull; it is optional and never required.

### Trust model

Bundles are **Ed25519-signed with an org key** (out-of-band distribution: admin
generates the keypair, shares the public key with members once). Import verifies the
signature before anything is parsed, and records the exporter's instance fingerprint
in the audit log. The existing federation DIDs/VCs (`api/routes/federation_routes.py`)
are the long-term identity layer; they are in-memory today and NOT a Phase 1–2
dependency — signature verification is sufficient and works offline.

## 4. Phases

### Phase 0 — Persist pipeline state (prerequisite; small)

You cannot export config that evaporates on restart.

- Persist `HybridDataIngestionService.sync_configs` + `usage_stats` to the existing
  `ingestion_settings` table (`core/models.py:2632`) — add columns for
  `entity_types`, `sync_last_n_days`, `max_records_per_sync`, `sync_mode`,
  `usage_stats_json`. Hybrid service reads on init, writes through on change.
- Replace hardcoded `get_workspace_id() → "default"`
  (`api/data_ingestion_routes.py:50`) with `resolve_workspace_id()` from
  `core/personal_scope.py` (per `docs/architecture/TENANT_ID_STRATEGY.md`).
- New columns follow the tenant-consistency rules (all `tenant_id` via
  `resolve_tenant_id()`); Alembic migration required.

**Acceptance:** restart a dev instance with sync enabled for two integrations →
configs and usage counters survive; `GET /api/data-ingestion/usage` reflects them.

### Phase 1 — Ingestion Profile export/import (small–medium)

Share *how* to ingest, not data. An org admin sets up sources once, exports the
profile, members import it.

- New `core/ingestion_profile_service.py`:
  - `build_profile(workspace_id)` → versioned JSON (`profile_version: 1`):
    hybrid sync configs, document-ingestion settings rows, webhook subscriptions
    (URLs + entity types, **never** secrets). Entire payload passed through
    `strip_credentials`; fail-closed (refuse export if `has_credentials()` is true).
  - `apply_profile(profile, workspace_id)` → upserts `ingestion_settings`, registers
    sync configs; conflict policy = profile wins for org-marked sources, local wins
    for personal sources.
- Routes in `api/data_ingestion_routes.py`:
  `GET /api/data-ingestion/profile/export` (read-only),
  `POST /api/data-ingestion/profile/import` (governance: HIGH complexity — changes
  sync behavior — per `core/api_governance.require_governance`).
- Ed25519 sign on export, verify on import (org keypair; `GET /api/data-ingestion/org-key`
  for public-key bootstrap).
- Frontend: Export/Import buttons on the ingestion settings page
  (`frontend-nextjs/` data-ingestion surfaces).

**Acceptance:** export on instance A, import on instance B → B schedules the same
syncs against its **own** credentials; zero secrets in the exported file (assert in
test via `has_credentials`).

### Phase 2 — Org Data Bundle export/import (medium–large; opt-in)

Share normalized org data. Strictly per-source opt-in at export time.

- New `core/org_data_bundle_service.py`:
  - **Export** (`build_bundle(sources, workspace_id, sensitivity_ceiling)`):
    - Emits JSONL from `ingested_documents` / `unified_messages` / GraphRAG
      `graph_nodes`+`graph_edges`, per selected integration.
    - Hard filter: rows with `sensitivity in (restricted, confidential)` are excluded
      unless the exporter explicitly creates a scoped sub-bundle for them (separate
      signed bundle, separate audit row naming the intended audience).
    - Metadata scrubbed via `strip_credentials`; no embeddings; no OAuth artifacts.
    - Caps: max bundle size (start 200 MB) and max records (start 100k), mirroring
      mini-app store caps; stream-write to avoid loading in memory.
  - **Import** (`apply_bundle(bundle, workspace_id)`):
    - Verify signature → parse → for each record: idempotency check via
      `document_ingestions (workspace_id, doc_id)`; skip-if-newer-wins on
      `updated_at`; then re-embed locally and write through the existing
      `add_document` / `graphrag.ingest_document` paths so audit and governance apply.
- Routes: `POST /api/data-ingestion/bundle/export` (governance: **CRITICAL/egress —
  SUPERVISED+ with HITL approval**, since it is an exfiltration surface),
  `POST /api/data-ingestion/bundle/import` (HIGH).
- One `ingestion_audit_logs` row per export/import (source counts, sensitivity
  breakdown, destination label).
- Frontend: share dialog — per-source checkboxes, sensitivity summary, warning when
  a source contains excluded restricted rows.

**Acceptance:** A ingests 500 Salesforce contacts → exports bundle → B imports →
B's GraphRAG and memory return those contacts; re-import is a no-op (dedup);
a synthetic restricted row never appears in any default bundle.

### Phase 2b — Memory bundle: GraphRAG + raw text (IMPLEMENTED, backend Aug 16, 2026)

Extends the Phase 2 bundle envelope with the **agent memory** stores. The memory
stack decomposes cleanly into shareable vs identity-bound:

| Store | Verdict | Reason |
|---|---|---|
| `graph_nodes` / `graph_edges` | **Share** | Rows, not vectors; entities are org facts keyed by `(workspace_id, name, type)` — a natural cross-instance merge key |
| Raw text (`ingested_documents` full content, `knowledge_documents`, `business_facts`) | **Share** | Phase 2 already carries `content_preview`; this adds full text + the knowledge/world-model layer |
| `graph_communities` | **Never export — recompute** | Leiden communities are a property of the *whole local graph* (personal nodes included); the importer re-runs local community detection after merging |
| Episodic memory (`AgentEpisode`, graduation evidence), chat history, turn facts | **Out of scope, permanently** | They drive per-agent maturity graduation and verified-outcome gating — importing another instance's "verified episodes" would let one member's agent graduate on another's evidence, corrupting the trust model. Also the most PII/secret-laden data in the system |

Two model facts shape the wire format (`core/models.py`):

1. `GraphNode.embedding` (pgvector/JSON) is **derived** from `description` — excluded
   from bundles; the importer regenerates it with its own embedding provider (same
   policy as LanceDB vectors).
2. `GraphEdge.source_node_id`/`target_node_id` reference **local UUIDs** — bundles
   cannot carry them. Endpoints are keyed by `(name, type)` and remapped to local
   node ids on import.

#### Bundle envelope v2 (`bundle_version: 2`, backward compatible)

`payload` gains two optional sections alongside `records`; v1 envelopes (records
only) keep importing unchanged.

```jsonc
{
  "kind": "atom_org_data_bundle",
  "payload": {
    "bundle_version": 2,
    "records": [ ... ],          // Phase 2 unchanged
    "graph": {                    // NEW
      "nodes": [
        {"key": ["Acme Corp", "organization"], "description": "...",
         "type": "organization", "properties": {...}, "sensitivity": "internal",
         "source_updated_at": "...", "content_hash": "..."}
      ],
      "edges": [
        {"source_key": ["Alice", "person"], "target_key": ["Acme Corp", "organization"],
         "relationship_type": "works_at", "weight": 1.0, "properties": {}}
      ]
    },
    "texts": {                    // NEW
      "documents": [ {"external_id": "...", "integration_id": "...", "content": "...", ...} ],
      "knowledge_documents": [ {"title": "...", "content": "...", "doc_type": "...", "sensitivity": "..."} ],
      "business_facts": [ {"fact": "...", "citation": "...", "confidence": ..., "sensitivity": "..."} ]
    }
  }
}
```

#### Export (`include: ["records", "graph", "texts"]` on the export request)

- **Graph selection**: nodes filtered by sensitivity ladder (see taint rule below)
  and, where possible, by the same `sources` filter as records — a node is
  attributable to a source via `source_ids` / the documents that mention it.
- **Taint propagation rule**: a node's sensitivity = the **most restrictive**
  sensitivity of the source documents it was extracted from ("person" extracted
  from a restricted HR doc is restricted). Requires a new `graph_nodes.sensitivity`
  column (default `internal`) backfilled from `IngestedDocument.sensitivity` via
  the `source_ids` → `IngestedDocument` linkage; same for `business_facts` if it
  lacks the column.
- Node `properties` and edge `properties` pass through `strip_credentials`
  (properties legitimately hold emails/names — those stay; token-shaped keys go).
- Edges exported only when **both** endpoints pass the sensitivity filter — an edge
  into a restricted node leaks its existence.
- Caps: separate node/edge/text caps (start 50k nodes / 200k edges / 10k text
  docs), same `content_hash` idempotency basis as records.

#### Import

1. Signature + hash verified **before** parse (unchanged, envelope-level).
2. **Nodes**: upsert on `(workspace_id, name, type)`; merge policy = bundle wins if
   `source_updated_at` newer (last-writer-wins on description; `properties`
   shallow-merged, local keys win on conflict); regenerate local embedding; node
   sensitivity = max(local, imported) — import can never *lower* a local
   classification.
3. **Edges**: resolve both endpoint keys against local nodes (auto-creating missing
   endpoints as minimal stub nodes is **rejected** — an edge whose endpoints don't
   resolve is skipped and counted, since stub nodes would fabricate entities the
   importer never saw text for); dedup on `(source, target, relationship_type)`.
4. **Texts**: `documents` fold into the existing records path (full `content`
   replaces the preview basis for dedup hash); `knowledge_documents` /
   `business_facts` upsert by natural key, re-embedded locally.
5. **Recompute**: after merge, trigger the existing community-detection pass
   (`core/graphrag/community_detection.py`) asynchronously — imported communities
   are never trusted.
6. Audit: extend `bundle_exports`/`bundle_imports` with per-section counts
   (`section_counts` JSON column or equivalent) — nodes/edges/texts/records
   reported separately.

#### Acceptance

- A exports a Salesforce-derived graph (500 nodes, 800 edges) → B imports →
  `graph_nodes`/`graph_edges` populated, no stub nodes, embeddings locally
  generated; re-import is a no-op; deleting a node on A and re-exporting with a
  tombstone marks it `freshness_status='removed'` on B.
- A restricted HR document's extracted person-nodes never appear in a
  default-ceiling export (taint propagation test).
- An edge whose target was filtered out by sensitivity is absent from the bundle.
- Episodic memory / chat / turn-fact tables are byte-identical after import.

### Phase 3 — Org Ingestion Hub (IMPLEMENTED, backend Aug 16, 2026)

Continuous sharing instead of passing files. One designated instance (a always-on
member machine or a small server) owns org-source connections and members pull.

- Hub = ordinary Atom instance + `ATOM_ORG_HUB_ENABLED=true` exposing authenticated
  pull endpoints (`GET /api/data-ingestion/hub/bundles?since=<cursor>`) using
  per-member API keys (reuse the `atom_sk_*` GatewayApiKey mechanism,
  `core/models.py` `GatewayApiKey`).
- Members run a scheduled pull (existing background-task pattern from
  `main_api_app.py:538-548`) and apply bundles via the Phase 2 import path.
- Cursor-based incremental sync (monotonic per-source cursor = max source
  `updated_at` + record id); append-only; conflicts impossible by construction
  (hub is the single writer for org sources).
- Personal sources stay fully local and never touch the hub.

**Acceptance:** two-member setup — hub ingests a Slack channel, member B pulls
within one sync interval, sees the messages in memory search; killing the hub
degrades members to stale-but-functional local data (no crashes, no lockouts).

## 5. Data model changes (Alembic migrations, tenant_id per strategy doc)

| Change | Phase |
|---|---|
| `ingestion_settings`: + `entity_types`, `sync_last_n_days`, `max_records_per_sync`, `sync_mode`, `usage_stats_json` | 0 ✅ |
| New `org_keys` (org public-key registry + own keypair fingerprint) | 1 ✅ |
| New `ingestion_profile_imports` (imported profile id/version/audit) | 1 ✅ |
| New `bundle_exports` / `bundle_imports` (hash, source counts, sensitivity breakdown, signature) | 2 ✅ |
| `graph_nodes`: + `sensitivity` (default `internal`) + backfill from source docs; `business_facts`: + `sensitivity` if absent; `bundle_exports`/`bundle_imports`: + `section_counts` JSON | 2b ✅ (facts stay in LanceDB with metadata-borne sensitivity; no SQL column needed) |
| New `hub_api_keys` if not reusing `GatewayApiKey` | 3 ✅ (reused — hub auth is `atom_sk_*` gateway keys via `core/llm/gateway/auth.get_gateway_identity`; member pull cursor persisted in `ingestion_settings.usage_stats_json` under integration `org_hub`) |

All new tables carry `tenant_id` + `workspace_id` and go through
`resolve_tenant_id()` / `resolve_workspace_id()`.

## 6. Security guardrails (all phases, non-negotiable)

1. `strip_credentials` on **every** export path; export fails closed if
   `has_credentials()` detects anything.
2. Sensitivity gate (P4 classifications) — restricted/confidential excluded by default.
3. Signature verification before parse; unverified bundles are rejected and audited.
4. Governance gating: export ≥ HIGH (bundle export SUPERVISED+HITL), import HIGH.
5. Size/record caps; streaming parse (no full-bundle memory load).
6. One audit row per operation; imports enter through governed ingestion paths only —
   imported data never arrives pre-trusted or bypasses GraphRAG/audit.
7. Kill switch `ATOM_ORG_SHARING_ENABLED=false` (default off), matching the
   `ATOM_GATEWAY_ENABLED` / `ATOM_MINIAPP_DB_ENABLED` pattern.

## 7. Testing

- Unit: profile/bundle serialization round-trips; `strip_credentials` invariants;
   signature verify/reject; dedup idempotency; sensitivity filtering (backend/tests,
   follow existing `test_*` conventions).
- Integration: export-on-A/import-on-B using two temp SQLite+LanceDB dirs; restart
  persistence (Phase 0).
- E2E: extend `backend/tests/e2e_ui/` with the share-dialog flow.
- Fuzz-ish: malformed/tampered bundles (bad signature, oversize, duplicate ids).

## 8. Rollout

Feature-flagged per phase; Phase 0 is unconditionally valuable (restart-persistence
bug) and ships first. Phases 1–2 behind `ATOM_ORG_SHARING_ENABLED`. Phase 3 (hub)
ships behind `ATOM_ORG_HUB_ENABLED` (hub side) + `ATOM_ORG_HUB_URL` /
`ATOM_ORG_HUB_API_KEY` / `ATOM_ORG_HUB_SOURCES` / `ATOM_ORG_HUB_SENSITIVITY_CEILING` /
`ATOM_ORG_HUB_PULL_INTERVAL_MIN` (member side; default 15 min) — validation in a real
org is still recommended before a hub goes production. Member cursors persist in
`ingestion_settings.usage_stats_json` (integration `org_hub`) via Phase 0 persistence;
a killed hub degrades members to stale-but-functional local data (the pull loop
retries each interval).

## 9. Open questions

1. Hub hosting in Phase 3 — designated member machine vs. tiny always-on server
   (the repo already ships `docker-compose-personal.yml`; a hub is the same compose
   plus the flag).
2. Sub-bundle scoping vocabulary — teams (`teams` table exists) vs. ad-hoc labels.
3. Whether profiles/bundles may later publish through the SaaS marketplace
   (`core/atom_saas_client.py`) for org-internal distribution, or stay strictly
   peer-to-peer files. (Marketplace is public-facing today; org-private distribution
   would need hub-side ACLs.)
4. Retraction: if a source record is deleted at the origin (GDPR erasure), should
   bundles carry tombstones that members' imports honor? Recommended: yes in
   Phase 2 (cheap now, expensive to retrofit).

## 10. Alternatives considered and rejected

| Alternative | Why rejected |
|---|---|
| Copy LanceDB directories between instances | Embedding provider/dimension mismatch across BYOK instances; no schema versioning; bypasses audit |
| Central SaaS ingestion service | Contradicts local-first/BYOK premise; the org would need to trust external infrastructure with its data |
| Everyone ingests org sources independently (status quo) | Duplicated API quota, storage, and drift — the problem being solved |
| Wait for federation (DIDs/VCs) to mature | It is in-memory and identity-only; signing solves Phase 1–3 offline without blocking on it |
