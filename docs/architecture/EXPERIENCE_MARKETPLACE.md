# Experience Marketplace

> **Status**: MVP (backend) — agent-driven lesson packs shareable across Atom instances.
> **Feature gate**: `ATOM_EXPERIENCE_MARKETPLACE_ENABLED=true` (default **off** — new surface).

Turns post-run agent memory (episodes, canvas summaries, business facts, graph ontology,
skills) into **signed, sanitized lesson packs** another instance can apply — without
leaking entity identity, credentials, PII, or sensitive rows. Success data is the
training set for maturity routing: a startup runs 53 clean runs, packs its "how",
ships the pack to its portfolio company, and the recipient's agents learn the
playbook + earn the tier — verified credibility, not marketing claims.

Sibling of the Org Ingestion Sharing plan (`ORG_INGESTION_SHARING_PLAN.md`): that plan
shares *org data* (source records, GraphRAG, memory) between instances; this plan
shares *agent experience* (lessons distilled from what the agent did and what the
user decided).

---

## 1. What is in a pack

A pack is a signed envelope (same crypto as org bundles — Ed25519, key at
`./data/org_sharing_key`, registered in `org_public_keys`, fail-closed):

```json
{
  "kind": "atom_experience_pack",
  "pack_version": 1,
  "exported_at": "...",
  "source_agent_id": "...",
  "sensitivity_ceiling": "internal",
  "delta": false,
  "cursor": {"updated_at": "..."},
  "sections": {
    "patterns":       [item, ...],   // distilled episodes (verified outcomes)
    "canvas_lessons": [item, ...],   // LLM canvas summaries (feature #7)
    "facts":          [item, ...],   // verified business facts (LanceDB)
    "ontology":       {"nodes": [...], "edges": [...]},
    "skills":         [item, ...]    // marketplace-public skills only
  }
}
```

Every item is `{item_id, kind, sensitivity, updated_at, payload}` and is idempotently
applied — `(workspace_id, source_agent_id, kind, content_hash)` dedups re-imports.

### 1.1 `patterns` — distilled episodes (sensitivity-gated)

Source: `agent_episodes` for the agent (workspace-scoped), joined with
`agent_reasoning_steps` for the *verified step count* (only `verified` steps
count — mirrors the graduation gate). Each episode becomes a lesson:

```
lesson = sanitize_text(episode.task_description[:500]) + " → outcome: " + outcome
```

- `outcome` in {success, failure, partial} — the *postcondition*: only episodes
  whose sensitivity rating is at-or-below the ceiling export.
- `conditions` — bucketed envelopes from episode `metadata_json` numeric fields
  (amount → `amount:[1K,10K)`, count → `count:[10,100)`, duration → `duration:[10m,1h)`,
  date → `date:2026-Q3`, ratio → `ratio:0.8`). Exact values never export.
- `verified_step_count`, `supervisor_rating`, `aggregate_feedback_score`,
  `step_efficiency`, `confidence`, `maturity_at_time` carried along — the seed
  features for learner-tier promotion.
- Cap `MAX_PATTERNS` (1000).

### 1.2 `canvas_lessons` — canvas summaries (feature #7, per-episode)

The semantic canvas summaries produced by `CanvasSummaryService` (50–100 words,
capturing presentation, decision context, user action) are persisted durably in
`EpisodeSegment.canvas_context` (JSON column, `episode_id` backlink). They answer
"when did a canvas of type X actually move a decision forward?" — exactly the
transferable intuition a second instance wants.

Source query: `EpisodeSegment` rows where `canvas_context` contains a
`presentation_summary`, joined to `agent_episodes` (workspace + agent scope,
outcome). Deduplicated per episode by `(canvas_type, summary)` so N segments
carrying the same context produce one item.

Sanitization (layer 2 of the pack sanitizer):

| Field | Export rule |
|---|---|
| `presentation_summary` | `sanitize_text` — entity registry tokens + PII regex (email/phone/url) |
| `visual_elements`, `canvas_type` | generic component vocabulary — pass through |
| `user_interaction` | pass through (enum-ish strings like "presented to user") |
| `summary_verification` / `summary_source` | pass through — buyers can prefer `verified`+`llm` |
| `summary_richness` | pass through (float) |
| `outcome` | pass through |
| `critical_data_points` | **bucketed** by key guess (amount/count/duration/date/ratio); opaque ids (`workflow_id`, `command`, `file_path`) → **dropped**, not tokenized — they are identities, not lessons |

- `summary_source == "flagged"` episodes still export (tagged), so the buyer can
  see the distribution of flagged vs verified summaries.
- Cap `MAX_CANVAS_LESSONS` (1000).

### 1.3 `facts` — verified business facts (best-effort)

Source: LanceDB `business_facts` docs of the workspace (`get_lancedb_handler(...)`).
Best-effort — the Personal Edition LanceDB stub returns nothing, and the section is
then empty. For anything that does export:

- fact text → `sanitize_text` (registry + PII).
- `verification_status` carried (facts are JIT-verified; unverified facts export but
  tagged, mirroring the oracle's `EXTERNAL_VERIFIED` discipline).
- `citations` **stripped** (they name source docs) — only the citation count and a
  `verified` boolean carry across.
- Sensitivity from fact metadata, gated against the ceiling.
- Cap `MAX_FACTS` (2000).

### 1.4 `ontology` — GraphRAG nodes + edges

Same geometry as the org bundle Phase 2b graph section:

- Nodes: `GraphNode` rows for the workspace whose `sensitivity` is at-or-below the
  ceiling; **name → role token** via the entity registry (deterministic per
  workspace, `{type}_{n:03d}`); `description` sanitized; local `graph_node.id` never
  exported — keys are `(name_token, entity_type)`.
- Edges: exported **only when both endpoints survive** the node filter (no stub
  nodes); `relationship_type` kept (ontology vocabulary); `properties` bucketed.
- Communities are never exported (buyer recomputes via Leiden — same rule as
  `ORG_INGESTION_SHARING_PLAN.md` Phase 2b).
- Caps `MAX_NODES` (20k) / `MAX_EDGES` (50k); dropped-edge count reported.

### 1.5 `skills` — marketplace-public skills

Only `is_public=True, is_approved=True` skills (already shareable by contract):
`name`, `description`, `version`, `category`, `tags`, and the skill markdown/code
(capped). No private skills, no unapproved skills, no workspace skills. Cap
`MAX_SKILLS` (100).

### 1.6 What never exports

- Episodic memory / chat history / turn facts (excluded by construction —
  same graduation-trust semantics as org bundles).
- `confidential`/`restricted` rows unless the ceiling is raised (then
  `destination` is **required** — audit accountability).
- Exact amounts, exact ids, entity names, emails/phones/URLs, credentials
  (fail-closed via `strip_credentials`), citations, local UUIDs.

## 2. The sanitizer (layered, fail-closed)

`core/experience_marketplace/sanitizer.py`:

1. **Entity registry** (`ExperienceRoleRegistry`): entity names observed by the agent
   (graph node names + episode entity names) map to deterministic role tokens
   `{type}_{n:03d}`; persisted per `(workspace_id, entity_type, name)` so deltas keep
   the same token. Unknown identity strings fall back to `hash8(type:value)` — a
   string only ever exports tokenized or bucketed, **never verbatim**.
2. **Credential stripping**: reuses `core/blueprint_sanitizer.strip_credentials`
   (fail-closed — if `has_credentials` fires on the assembled pack the export raises).
3. **PII redaction**: email / phone / URL regex → `<email>` / `<phone>` / `<url>`.
4. **Attribute bucketing**: `bucket_value(value, kind)` envelopes.
5. **Leak scan**: after assembly, `scan_for_leak()` re-checks every exported string
   against the original identity set (len ≥ 3, case-insensitive) — any hit aborts
   the export. Same post-export discipline as the org bundle `scan_for_leak`.

## 3. Delta synchronization (cursor)

Cursor persisted in `ingestion_settings.usage_stats_json["experience_cursor"]`
(integration `experience`), per source agent: `{"updated_at": "<iso>"}` — a
coarse timestamp watermark (same semantics as the org hub member cursor). Exports
with `since` carry only items updated after the mark; after a successful export
the service advances the watermark to the max `updated_at` across exported items.
Whole-pack re-import supersedes changed items by timestamp-last-writer-wins on
`(workspace_id, source_agent_id, item_id)`.

Tombstones are not emitted in v1 — `removed` state is out of scope (patterns /
lessons are append-mostly).

## 4. Export / import flows

**Export** (`POST /api/experience-marketplace/pack/export` — CRITICAL, audit):

1. Gate: feature flag + agent existence in workspace.
2. Select items per section (caps, sensitivity filter, optional delta cursor).
3. Sanitize (registry tokens built from ontology + episode entities), bucket,
   strip credentials, leak-scan.
4. Sign `canonical_json(payload)` with the org-signing Ed25519 key; record
   `ExperienceExport` audit row (counts, ceiling, destination, delta).
5. Return envelope `{kind, payload, payload_hash, signature, signed_by}` +
   `excluded_by_sensitivity` + `section_counts`.

**Import** (`POST /api/experience-marketplace/pack/import` — HIGH, audit):

1. Validate kind/version/hash; **verify signature BEFORE parse** (fail closed).
2. `strip_credentials` fail-closed on the payload.
3. Defense-in-depth sensitivity filter against the *declared* ceiling (never higher
   than the declaring pack's).
4. Apply idempotently: `patterns`/`canvas_lessons`/`facts`/`skills` rows upsert on
   `(workspace_id, source_agent_id, item_id)` (content-hash dedup; change =
   update; tombstone list → `superseded_at`). Ontology upserts on
   `(workspace_id, name_token, entity_type)` with sensitivity
   raised-never-lowered (`higher_sensitivity`), edges via key map, unresolved
   endpoints dropped and counted.
5. Record `ExperienceImport` audit row + advance cursor if the pack was a delta.

## 5. Credibility: reputation + tiers

`GET /api/experience-marketplace/reputation/{agent_id}` — the pack-buyer's due
diligence card, computed from local verified evidence:

- maturity (STUDENT/INTERN/SUPERVISED/AUTONOMOUS from verified-run thresholds),
- `episodes_total`, `success_rate`, `outcome_breakdown`,
- `verified_execution_count` (the graduation gate — how many steps the oracle
  confirmed),
- `avg_supervisor_rating`, `avg_feedback_score`, `avg_step_efficiency`,
- `export_count` + `last_episode_at`.

No cross-instance trust: a buyer's own instance computes the card from its local
rows; `verified` flags are per-origin, and import strips "verified" claims unless
the item itself carries oracle evidence. (Same spirit as `capability_graduation_service`
— unverified never inflates.)

## 6. Lifecycle of a shared lesson (post-MVP)

1. Agent runs N tasks in workspace A; oracle-verified steps + episode outcomes
   accrue.
2. An agent (or admin) calls `pack/export` — pack signed at ceiling `internal`
   (default: `confidential`/`restricted` excluded).
3. Workspace B imports; sanitizer tokens land in B's ontology, lessons in B's
   experience store; B's agent now recalls "task class X takes ~amount:[1K,10K) and
   users approve on sheets canvases".
4. B's agent performs next tasks; its own maturation now happens on **both** its
   own verified wins and the imported playbook, but promotion thresholds
   (`agent_graduation_service`) are still local-verified-count based — imported
   experience seeds confidence, never skips the gate.

## 7. Security model

- **Crypto**: Ed25519 via `core/org_sharing_crypto` — same signing key/registry and
  key-file lifecycle (0600, never DB) as org sharing; signature verified before any
  parse on import.
- **P4 taint**: every exported item carries its `sensitivity`; watchers see the
  same `VT_PROVENANCE`-style discipline (P4's outbound gate classes packed data as
  `public|internal|confidential|restricted`; this plan reuses the ladder +
  `classify_sensitivity`, and `higher_sensitivity` for import merges).
- **P5 fail-closed**: `strip_credentials` + `has_credentials` on pack and payload;
  superseded row payloads stripped on read-back (defense in depth).
- **Governance**: export = CRITICAL (deletion-grade accountability — it is an
  exfiltration surface), import = HIGH; both audited (`ExperienceExport` /
  `ExperienceImport`), both honor `destination` (site-of-record accountability).
- **Never**: chat/Episodes memory, turn facts, plaintext identity, exact values,
  local UUIDs, unresolved ontology endpoints (no stubs), `removed` semantics in v1.

## 8. Flags

| Flag | Default | Meaning |
|---|---|---|
| `ATOM_EXPERIENCE_MARKETPLACE_ENABLED` | `false` | master switch (off = routes 503 + service refuses) |
| `ATOM_EXPERIENCE_PACK_MAX_PATTERNS` / `MAX_CANVAS_LESSONS` / `MAX_FACTS` / `MAX_SKILLS` / `MAX_NODES` / `MAX_EDGES` | 1000/1000/2000/100/20000/50000 | per-section caps (monkeypatch-able for tests) |

## 9. Files

| File | Purpose |
|---|---|
| `core/experience_marketplace/sanitizer.py` | role registry, PII redaction, bucketing, leak scan |
| `core/experience_marketplace/pack_service.py` | export/import/cursor/reputation |
| `api/experience_marketplace_routes.py` | `/api/experience-marketplace/*` |
| `core/models.py` | +`ExperienceItem`, `ExperienceRoleRegistry`, `ExperienceExport`, `ExperienceImport` |
| `alembic/versions/20260820_experience_marketplace.py` | guarded DDL (hybrid SQLite-safe) |