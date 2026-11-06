# Document-ingestion settings — test results

Executed source: `b9c94929fecd55eab4827bcdf201c6694ac228cf`  
Product source: `0aa16ce762f45af9bf47dcb45bceb6910604b2ed`  
Accepted admin base: `9d73552d249ae8ec5b05af77546faf9621bbcd47`  
Runtime: real scratch SQLite with fresh sessions; no live provider/sync/upload.

Every command ran from the backend root with:

```sh
export PYTHONDONTWRITEBYTECODE=1
export TESTING=1
export PYTHONPATH=$PWD
PY314=/Users/rushiparikh/projects/atom/backend/venv314/bin/python
PY311=python3.11
```

## Focused gate

```sh
$PY314 -B -m pytest -p no:randomly \
  tests/test_document_settings_decision_contract.py \
  tests/test_covpush_w80b_api_routes.py::TestDocIngestionSettings \
  tests/test_document_ingestion_routes_coverage.py \
  -q --tb=short
```

Result: **111 passed** (`focused-314.log`). The same command with `$PY311`
gives **111 passed** (`focused-311.log`).

This is 26 new decision controls plus the rewritten settings route coverage
classes.

## Affected document-ingestion / audit selection

```sh
$PY314 -B -m pytest -p no:randomly \
  tests/test_document_settings_decision_contract.py \
  tests/test_covpush_w80b_api_routes.py::TestDocIngestionSettings \
  tests/test_document_ingestion_routes_coverage.py \
  tests/api/test_document_ingestion_routes.py \
  tests/test_auto_document_ingestion.py \
  tests/test_ingestion_tables.py \
  tests/test_ingestion_profile_service.py \
  tests/test_ingestion_status_routes.py \
  tests/test_hybrid_ingestion_persistence.py \
  tests/test_document_scope_authority.py \
  tests/test_audit_logger.py \
  tests/test_covpush_w103_audit_logger.py \
  -q --tb=short
```

Result: **278 passed** on both Python 3.14 and 3.11
(`affected-314.log`, `affected-311.log`).

The same selection on the accepted admin base `9d73552d2` (without the new
contract file) gives **252 passed on both versions**
(`baseline-314.log`, `baseline-311.log`). The branch adds exactly 26 passing
controls; there are no baseline failures in this selection.

## Coverage matrix

- Active user creates a new workspace-scoped settings row; one audit receipt.
- Existing row merge changes only supplied fields; `file_types`, folders,
  size/frequency and hybrid ingestion columns are preserved.
- Same integration in another workspace is unchanged.
- Only `integration_id` and an already-matching request -> 200 no-change /
  effect none, no audit.
- Stale peer edit before the claim -> 409 `STALE_TARGET`, peer value preserved,
  zero audit.
- Same-operation replay -> `already_applied`, one receipt; changed material ->
  409 `OPERATION_CONFLICT`; later revision -> `committed_unverified`.
- Actor deactivation/tenant move after the row read -> effect-none refusal,
  row unchanged, zero audit.
- Audit constraint rollback -> 409 `not_applied`, effect none, row unchanged.
- Post-commit readback -> 503 `committed_unverified`, effect committed.
- Lost confirmation -> 503 `effect_unknown` with original identity; no
  exception text.
- 12 audit-tamper variants never certify.
- Raw folder paths are absent from audit metadata, descriptions and logs.
- Anonymous request -> 401 with no row/audit.

## Counts

- Focused: 111 passed on both versions.
- Affected: 278 passed on both versions.
- Baseline: 252 passed on both versions.
- New passing controls: 26.
- Selections overlap; totals are not added together.

## Scope

No read/sync/upload/parse/memory-removal/LanceDB changes and no live provider,
credential, spend, send, download or deployment operation. No new table or
migration. The existing `ingestion_settings` row and `AuditLog` are reused.
PostgreSQL runtime/soak and multi-worker qualification remain open. The
submitted review/memory/skill/agent/goal branches are independent and not
merged.
