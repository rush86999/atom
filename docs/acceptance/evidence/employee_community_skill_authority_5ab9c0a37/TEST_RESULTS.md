# Community-skill authority repair — test results

Executed source: `5ab9c0a37f0f80fe99f29175bfa726d6ecfcd3fa`  
Repair product: `f751fd80f265b2de44231a040cd85dac35a37d8f`  
Prior submitted source: `5eb3cf626` (product `f8477493c`, evidence
`5efb59b75`)  
Accepted admin base: `9d73552d249ae8ec5b05af77546faf9621bbcd47`  
Runtime: real scratch SQLite with fresh sessions and two-session authority
interleaving; no live code sandbox/model/provider.

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

Result: **46 passed** (`focused-314.log`). The same command with `$PY311`
gives **46 passed** (`focused-311.log`).

This is the prior 42 controls plus 4 authority-change twins.

## Affected skill / registry / review / audit selection

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

Result: **272 passed, 4 failed baseline** on both Python 3.14 and 3.11
(`affected-314.log`, `affected-311.log`).

The same selection on `9d73552d2` (without the new contract file) gives **234
passed, the same 4 failed** (`baseline-314.log`, `baseline-311.log`). The
failure lists are byte-identical; the branch adds 38 passing controls.

### The 4 baseline failures

All four are pre-existing missing-module import errors in
`tests/test_round22_marketplace_security.py`:

- `TestPackageRoutesRequireAuth::test_approve_package_requires_auth`
- `TestPackageRoutesRequireAuth::test_install_packages_requires_auth`
- `TestMarketplaceInstallRequiresAuth::test_install_marketplace_skill_requires_auth`
- `TestPackageRoutesNoStrELeak::test_no_str_e_in_http_exceptions`

They concern absent `api.package_routes` / `api.marketplace_routes`, reproduce
on the accepted admin base, and are unrelated to the two skill decision routes.

## Authority-twins coverage

- promote/delete × deactivation/tenant move after the target read, before the
  guarded authority claim;
- each response 401/403/409 with `verification.effect="none"`;
- target row unchanged (`Untrusted`), zero decision audit rows;
- actor resolved from the authoritative `User` row, not the request snapshot;
- frozen id/is_active/status/role/raw tenant bound in the same transaction as
  the target CAS and audit;
- the prior 42 controls remain green.

## Counts

- Focused: 46 passed on both versions.
- Affected: 272 passed + 4 exact baseline failures on both.
- Baseline: 234 passed + the same 4 failures on both.
- New passing controls since the prior submission: 38.
- Selections overlap; totals are not added together.

## Scope

No live skill/code execution, model, provider, credential, spend, send,
download, deployment, PostgreSQL/soak or multi-worker operation. No new table
or migration. The repaired memory/tool-mutation branches are independent and
not merged.
