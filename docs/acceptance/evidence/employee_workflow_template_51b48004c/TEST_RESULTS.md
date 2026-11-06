# Workflow-template create/update — test results

Executed source: `51b48004cdacace1a077865c3ee8fd6edbff8b50`  
Product source: `5fbd5c8f51449ed3fa6323a304713c04161d3491`  
Accepted admin base: `9d73552d249ae8ec5b05af77546faf9621bbcd47`  
Runtime: real scratch SQLite and temporary template directory; no live
workflow/model/provider.

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
  tests/test_workflow_template_decision_contract.py \
  -q --tb=short
```

Result: **27 passed** (`focused-314.log`). The same command with `$PY311`
gives **27 passed** (`focused-311.log`).

## Affected template / route / audit selection

```sh
$PY314 -B -m pytest -p no:randomly \
  tests/test_workflow_template_decision_contract.py \
  tests/test_workflow_template_routes_coverage.py \
  tests/test_workflow_templates.py \
  tests/test_workflow_template_system.py \
  tests/unit/test_workflow_template_manager.py \
  tests/test_covpush_w103_workflow_templates.py \
  tests/test_covpush_w109_workflow_templates.py \
  tests/test_covpush_w64c_industry_templates.py \
  tests/test_industry_workflow_templates.py \
  tests/test_personal_starter_templates.py \
  tests/test_personal_template_seeding.py \
  tests/test_role_template_registry.py \
  tests/test_template_readiness_endpoint.py \
  tests/test_user_templates_endpoints.py \
  tests/test_covpush_user_templates.py \
  tests/test_audit_logger.py \
  tests/test_covpush_w103_audit_logger.py \
  tests/test_round40_remaining_auth_sweep.py \
  tests/test_covpush_w79c_api_routes.py \
  -q --tb=short
```

Result: **646 passed, 14 skipped, 40 failed baseline** on both Python 3.14 and
3.11 (`affected-314.log`, `affected-311.log`).

The same selection on the accepted admin base `9d73552d2` (without the new
contract file) gives **619 passed, 14 skipped, the same 40 failed** on both
versions (`baseline-314.log`, `baseline-311.log`). The failure lists are
byte-identical; the branch adds exactly 27 passing controls.

### The 40 baseline failures

- 38 in `tests/test_covpush_w79c_api_routes.py`: the file's shared client
  supplies a `MagicMock` user without a real role/DB row, so the pre-existing
  permission dependency refuses template routes.
- `TestImportExportTemplate::test_import_template_valid`: a `MagicMock` author
  email is passed into `WorkflowTemplate`.
- `TestUpdateTemplate::test_update_template_steps`: expects the legacy `id`
  step key while the model exposes `step_id`.

They reproduce exactly on the accepted admin base and are unrelated to the
verified create/update service.

## Coverage matrix

- TEAM_LEAD and admin create/update; member 403; anonymous 401.
- Create writes one file and one audit receipt; raw name/description/tags/
  steps/parameters are absent from metadata, descriptions and logs.
- Create generates a fresh id, rejects an existing id with the peer file
  unchanged, replays idempotently, conflicts on changed material and reports a
  missing target as `committed_unverified`.
- Update changes only name/description/steps/inputs/tags; duration recalculates;
  unrelated template material is preserved.
- Matching update -> 200 no-change/effect none, no audit.
- Empty update -> 422 (preserved); missing id -> 404.
- Stale peer edit before the claim -> 409, peer file preserved, zero audit.
- Same-operation replay `already_applied`; changed material 409; later revision
  `committed_unverified`.
- Authority deactivation/demotion after the read -> effect-none refusal, file
  unchanged, zero audit.
- Audit constraint rollback -> prior file byte-restored or new file removed,
  409 `not_applied`, effect none.
- Post-commit readback -> 503 `committed_unverified`.
- Lost confirmation -> 503 `effect_unknown` with original identity; no
  exception text.
- 10 audit-tamper variants never certify.
- Path-traversal id -> 404, zero effect.

## Counts

- Focused: 27 passed on both versions.
- Affected: 646 passed + 14 skipped + 40 exact baseline failures on both.
- Baseline: 619 passed + 14 skipped + the same 40 failures on both.
- New passing controls: 27.
- Selections overlap; totals are not added together.

## Scope

No read/list/search/instantiate/execute/import/delete/rate/export changes and no
live workflow/agent/model/provider/credential/spend/send/download/deployment
operation. No new table or migration. The existing template JSON store and
`AuditLog` are reused. PostgreSQL runtime/soak and multi-worker qualification
remain open. The submitted review/memory/skill/agent/goal/document branches are
independent and not merged.
