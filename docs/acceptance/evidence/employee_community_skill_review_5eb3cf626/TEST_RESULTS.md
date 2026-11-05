# Community-skill promote/delete — test results

Executed source: `5eb3cf62644e0350e0f487a58dfddc4b00dabbc0`  
Product source: `f8477493c80b198ec236bafa600b9bee230840fd`  
Accepted admin base: `9d73552d249ae8ec5b05af77546faf9621bbcd47`
(runtime `5fbb377a4e1eef8fdd0013275cd8b1c9b278cd41`)  
Runtime: real scratch SQLite; no live code sandbox, model/provider/browser
operation.

Every command ran from the backend root with:

```sh
export PYTHONDONTWRITEBYTECODE=1
export TESTING=1
export PYTHONPATH=$PWD
PY314=/Users/rushiparikh/projects/atom/backend/venv314/bin/python
PY311=python3.11
```

## Focused community-skill gate

```sh
$PY314 -B -m pytest -p no:randomly \
  tests/test_skill_review_write_contract.py \
  tests/test_covpush_w104_gaps_b.py::TestSkillRoutes \
  -q --tb=short
```

Result: **42 passed** (`focused-314.log`). The same command with `$PY311`
gives **42 passed** (`focused-311.log`).

This is 34 new failure-first decision controls plus the existing 8 route
coverage controls.

## Affected skill / marketplace / registry / review / audit selection

```sh
$PY314 -B -m pytest -p no:randomly \
  tests/test_skill_review_write_contract.py \
  tests/test_covpush_w104_gaps_b.py::TestSkillRoutes \
  tests/unit/api/test_skill_routes.py \
  tests/test_round22_marketplace_security.py \
  tests/test_covpush_skill_registry.py \
  tests/test_covpush_w116_skill_registry.py \
  tests/test_skill_registry_service.py \
  tests/core/skills/test_skill_registry_service_coverage.py \
  tests/core/systems/test_skill_registry_coverage.py \
  tests/test_reviewed_improvement_apply.py \
  tests/test_reviewed_skill_agent_consumption.py \
  tests/test_memento_candidate_review.py \
  tests/test_audit_logger.py \
  tests/test_covpush_w103_audit_logger.py \
  -q --tb=short
```

Result: **268 passed, 4 failed baseline** on both Python 3.14 and 3.11
(`affected-314.log`, `affected-311.log`).

The same selection on the accepted admin base `9d73552d2` (without the new
contract file) gives **234 passed, the same 4 failed**
(`baseline-affected-95f7-314.log`, `baseline-affected-95f7-311.log`). The
failure lists are byte-identical; the branch adds exactly 34 passing controls.

### The 4 baseline failures

All four are in `tests/test_round22_marketplace_security.py` and are
pre-existing missing-module import errors:

- `TestPackageRoutesRequireAuth::test_approve_package_requires_auth`
- `TestPackageRoutesRequireAuth::test_install_packages_requires_auth`
- `TestMarketplaceInstallRequiresAuth::test_install_marketplace_skill_requires_auth`
- `TestPackageRoutesNoStrELeak::test_no_str_e_in_http_exceptions`

They fail because `api.package_routes` / `api.marketplace_routes` are absent at
this source; they are unrelated to the two skill decision routes and reproduce
on the accepted admin base.

## Coverage matrix

- TEAM_LEAD and admin valid twins; member/viewer/guest/anonymous refusal.
- Missing community id and cloud execution id -> 404, zero effect.
- Promote `Untrusted` -> `Active`; already `Active` new operation -> 200
  no-change/effect none; same-operation replay -> `already_applied`;
  unsupported status -> 409.
- Delete `Untrusted` and `Active`; tombstone replay; missing 404.
- Same-operation replay and changed material conflict.
- Later status/code/scan/lineage revision cannot be certified.
- Competing/stale peer edit before the claim -> 409, peer row preserved.
- Audit constraint rollback -> 409 `not_applied`, `effect=none`.
- Post-commit readback -> 503 `committed_unverified`, `effect=committed`.
- Lost confirmation -> 503 `effect_unknown`, identity, `do_not_repeat`, no
  exception text.
- 15 audit-tamper variants never certify.
- No raw skill body, generated code, package list, scan payload or secret in
  audit metadata, descriptions or captured logs.
- Existing static auth pin and ordinary route shapes remain compatible.

## Counts

- Focused: 42 passed on both versions.
- Affected: 268 passed + 4 exact baseline failures on both versions.
- Baseline: 234 passed + the same 4 failures on both versions.
- New passing controls: 34.
- Selections overlap; totals are not added together.

## Scope

No live skill/code execution, model, provider, credential, spend, send,
download, deployment, PostgreSQL/soak or multi-worker operation. No new table
or migration. The repaired scoped-memory and tool-mutation branches are
independent and not merged.
