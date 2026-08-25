# Ontology Draft Promotion Automation

> **Status**: Implemented (shadow-first, consent-gated). Default mode `off`.
> Mirrors the fleet-router / stage-router / trust-calibration automation
> pattern: `off | notify | approve | auto`, evidence-thresholded, revocation
> always automatic, manual decisions never overridden.

## Problem

Auto-discovered entity types — `EntityTypeDefinition` rows created with
`is_active=False` by schema discovery on integration syncs
(`resolve_or_create_draft` in `hybrid_data_ingestion`), OpenIE discovery
(`openie_schema_discovery`), and single-entity linking — are invisible to
the active ontology schema: `OntologyService._load_schema` filters
`is_active=True`, the API list hides inactive rows by default, and the
promotion path is a manual `PATCH … {"is_active": true}`. Nothing notices
drafts: discovered types rot as invisible dead rows (journey trace, gap
**O1** of `tests/core/test_ontology_journey_gaps.py`).

## Design

`core/ontology/ontology_draft_automation.py` runs an evidence + consent
pass over every discovered draft. All evidence is SQL-computable and
deterministic — no LLM calls, no new producers.

### Evidence model

| Signal | Definition | Meaning |
|---|---|---|
| `node_count` | `GraphNode` rows in the tenant whose type label matches the draft's slug, metadata `discovered_type`, display name, or the record-type suffix of the composite `{workspace}_{integration}_{type}` slug format | live graph usage |
| `workspace_count` | distinct workspaces among matching nodes | breadth |
| `evolved` / `new_evolution` | `version >= 2`, measured against the version recorded in the type's **latest** automation action | re-discovery: the idempotent discoverer saw the type again with a different shape |
| `sample_count` | discovery metadata `sample_count` (LLM-discovery producers set it) | discovery confidence, when present |
| `age_days` | days since creation | a type minutes old is one ingestion burst, not a recurring type |
| `stale_days` | days since the last **schema change** (version snapshot; falls back to creation) | revocation staleness — `updated_at` is deliberately avoided because the automation's own writes (is_active flip, metadata stamps) fire it |

### Certification

- **promote** when `(node_count >= MIN_NODES OR new_evolution) AND
  age_days >= MIN_AGE_DAYS` and `sample_count >= MIN_SAMPLES` when
  `sample_count` is present.
- **revoke** (ALWAYS automatic) when a previously-applied type has
  `node_count == 0`, no new evolution since promotion, and
  `stale_days >= REVOKE_STALE_DAYS` — the evidence that justified the
  promotion evaporated.
- `new_evolution` is measured since the last decision, so a revoked type
  cannot ride its stale `version >= 2` straight back in; it must be
  discovered again with a new shape (or acquire graph usage).

### Consent modes

| Mode | Behavior |
|---|---|
| `off` | pass is a no-op; `/status` still reports the census (routes stay usable to flip the mode) |
| `notify` | record a `notified` ledger row + admin notification (cooldown-deduped); never activates |
| `approve` | record an `approval` row + notification; admin applies via `POST /api/v1/ontology-drafts/approve/{action_id}` |
| `auto` | eligible drafts activate immediately; ledger records everything |

### Never touches manual decisions

- The entity-type `PATCH` route stamps `metadata_json["manual_decisions"]`
  (`{is_active, at, by}`) whenever a human passes `is_active` explicitly
  (`EntityTypeService.record_manual_decision`).
- A manual decision newer than the type's last automation action wins
  outright — the pass skips the type (promotion *and* revocation).
- A retirement (`is_active=False`) shelves re-promotion until a newer human
  decision.
- System types (`is_system=True`) are never in scope.

## Ledger

`ontology_draft_actions` (model `OntologyDraftAction`, migration
`20260826_add_ontology_draft_automation_actions.py`) — monotonic-integer PK
(SQLite `created_at` has second granularity), one row per automation
decision with `verdict` (`promote|revoke`), `state`
(`approval|applied|rejected|revoked|notified`), and the exact
`evidence_json` the verdict was computed from. The row is both the approval
queue and the audit trail.

## API

Admin-gated (`WORKSPACE_ADMIN`/`SUPER_ADMIN`) under
`/api/v1/ontology-drafts`:

- `GET  /status` — census + automation state
- `GET/POST /automation` — mode/interval (rejects invalid mode with 422)
- `POST /run-now` — force one pass (skips interval cooldown)
- `GET  /pending` — queued approvals
- `POST /approve/{id}` / `POST /reject/{id}` — admin consent

## Configuration

Resolution: env var wins > `runtime_settings` DB row (UI) > default, via
`core.runtime_settings.get_setting` — all registered in the settings
catalog under **Ontology Drafts**.

| Env var | Default | Meaning |
|---|---|---|
| `ATOM_ONTOLOGY_DRAFT_AUTO_ENFORCE` | `off` | `off|notify|approve|auto` |
| `ATOM_ONTOLOGY_DRAFT_AUTO_INTERVAL_MIN` | `60` | pass cadence |
| `ATOM_ONTOLOGY_DRAFT_AUTO_MIN_NODES` | `3` | graph-usage evidence floor |
| `ATOM_ONTOLOGY_DRAFT_AUTO_MIN_AGE_DAYS` | `2` | minimum draft age to promote |
| `ATOM_ONTOLOGY_DRAFT_AUTO_MIN_SAMPLES` | `3` | sample-count floor (when present) |
| `ATOM_ONTOLOGY_DRAFT_AUTO_REVOKE_STALE_DAYS` | `14` | unused + undiscovered → revoke |
| `ATOM_ONTOLOGY_DRAFT_AUTO_NOTIFY_COOLDOWN_HOURS` | `24` | notify dedupe window |

The background worker loop in `main_api_app` starts only when the mode is
not `off` (default `off` = no loop, no side effects). The admin surface is
always available.

## Tests

`backend/tests/test_ontology_draft_automation.py` (17): off no-op, auto
promote via usage + via re-discovery, age floor, approve queue + admin
apply/reject, notify cooldown, automatic revocation (auto AND approve
modes), revoked type needs new evolution to return, manual retirement
shelved, manual decision defers auto-revoke, system types out of scope,
census, sample-count floor, route 422, PATCH stamp.
