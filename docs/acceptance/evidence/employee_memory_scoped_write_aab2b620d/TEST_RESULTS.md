# ORACLE-01 scoped memory — test results

Executed source: `aab2b620df3e740c6c255c6a869e72fcc7eb4af7`  
Product source: `4a32ce30b03a47163fdd790297a96108d2c5c70f`  
Accepted admin base: `9d73552d249ae8ec5b05af77546faf9621bbcd47`
(runtime `5fbb377a4e1eef8fdd0013275cd8b1c9b278cd41`)  
Runtime: real scratch SQLite with fresh sessions; no model/provider/browser
operation.

Every command ran from the backend root with:

```sh
export PYTHONDONTWRITEBYTECODE=1
export TESTING=1
export PYTHONPATH=$PWD
PY314=/Users/rushiparikh/projects/atom/backend/venv314/bin/python
PY311=python3.11
```

## Focused memory gate

```sh
$PY314 -B -m pytest -p no:randomly \
  tests/test_memory_write_contract.py \
  tests/test_covpush_w10d_routes.py::TestMemoryRoutes \
  tests/test_covpush_w10d_routes_b.py::TestMemoryTail \
  tests/test_covpush_w79a_api_routes.py::TestMemoryRoutes \
  tests/unit/api/test_memory_routes.py \
  tests/test_round26_memory_security.py \
  -q --tb=short
```

Result: **74 passed** (`focused-314.log`). The same command with `$PY311`
gives **74 passed** (`focused-311.log`).

This is 25 new failure-first controls plus the existing real-DB memory route
controls and the auth-inspection controls.

## Affected memory / TenantSetting / audit selection

```sh
$PY314 -B -m pytest -p no:randomly \
  tests/test_memory_write_contract.py \
  tests/test_covpush_w10d_routes.py \
  tests/test_covpush_w10d_routes_b.py \
  tests/test_covpush_w79a_api_routes.py \
  tests/unit/api/test_memory_routes.py \
  tests/test_round26_memory_security.py \
  tests/test_memory_store_bootstrap.py \
  tests/test_memory_integration.py \
  tests/test_memory_symmetry_fixes.py \
  tests/test_memory_context_assembler.py \
  tests/test_memory_epistemic_provenance_scoping.py \
  tests/test_memory_p2.py \
  tests/test_memory_consolidation.py \
  tests/core/test_memory_consolidation_bughunt.py \
  tests/integration/services/test_memory_consolidation_multi_tenant.py \
  tests/test_admin_write_contract.py \
  tests/test_admin_write_contract_matrix.py \
  tests/test_admin_budget_routes.py \
  tests/test_budget_enforcement_service.py \
  tests/test_budget_control.py \
  tests/test_covpush_w104_spend_aggregation.py \
  tests/test_audit_logger.py \
  tests/test_covpush_w103_audit_logger.py \
  tests/test_integration_audit.py \
  -q --tb=short
```

Result: **690 passed, 1 skipped, 7 failed baseline** on both Python 3.14 and
3.11 (`affected-314.log`, `affected-311.log`).

The same selection on the accepted admin base `9d73552d2` gives **665 passed,
1 skipped, the same 7 failed** (`baseline-affected-95f7-314.log`,
`baseline-affected-95f7-311.log`). The failure lists are byte-identical; this
branch adds exactly 25 passing controls.

### The 7 baseline failures

- 6 unrelated `tests/test_covpush_w79a_api_routes.py` MiniApp/Office controls:
  `TestMiniAppRoutes::test_approve_success`,
  `TestMiniAppRoutes::test_approve_staff_success`,
  `TestOfficeRoutes::test_present_success_generates_canvas`,
  `TestOfficeRoutes::test_present_uses_token_identity`,
  `TestOfficeRoutes::test_sync_update_failure_400`,
  `TestOfficeRoutes::test_sync_update_success`.
- 1 pre-existing
  `tests/integration/services/test_memory_consolidation_multi_tenant.py::test_memory_consolidation_tenant_isolation`
  `AgentMemory` consolidation control.

The memory route class in the same w79a file is green, and the new focused
contract file is green. None of the 7 failures is in
`core/memory_write_service.py`, `api/memory_routes.py` or the scoped read
helpers.

## Counts

- Focused memory gate: 74 passed on both versions.
- Affected selection: 690 passed + 1 skipped + 7 exact baseline failures on
  both versions.
- Baseline at `9d73552d2`: 665 passed + 1 skipped + the same 7 failures on both.
- New passing controls: 25.
- Selections overlap; totals are not added together.

## Coverage matrix

- Anonymous requests refused; no row, no audit.
- User/tenant/agent isolation for store, read, search, context and delete;
  same key in different scopes is independent.
- Store insert and update; exact response fields; fresh-session durable read.
- Stale prior value refuses 409 and preserves the peer value.
- Same-operation replay is `already_applied` with one receipt; changed
  material is `OPERATION_CONFLICT`; later revision is
  `committed_unverified`.
- Context merge preserves fields, composes updates, replays idempotently, and
  refuses a competing merge without losing peer fields.
- Delete success, tombstone replay, missing 404 and stale delete preservation.
- Audit constraint rollback is 409 `not_applied`, `effect=none`, with target
  and audit absent.
- Post-commit readback is 503 `committed_unverified`, `effect=committed`.
- Lost confirmation is 503 `effect_unknown`, identity, `do_not_repeat`, no
  exception text.
- 12 audit-tamper variants are never certified.
- Raw memory value, metadata and key are absent from audit metadata,
  descriptions and captured logs.
- Existing governance wrappers and 401/200/404/409 status shapes remain
  compatible.

## Scope

No live model, provider, credential, spend, send, download, deployment,
administrator/account/budget or PostgreSQL/soak operation was used. No new
table or migration was added; the existing `TenantSetting` and `AuditLog` are
reused. The accepted admin base is `9d73552d2` (runtime `5fbb377a4`); the
submitted tool-mutation review branch is independent and not merged.
