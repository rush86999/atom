# Community-skill consolidation — test results

Executed source: `bd43da6446f71fb0237c64c189f9e25f0b028d95`  
Base main: `d860072a787e6460d83260e9cb629cfa5d5ea14b`  
Prepared branch tip (provenance): `4e25a2836820eb4ae17286876c1788a0ade5791f`

Every command ran from `backend/` with:

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
  tests/test_community_skill_write_contract.py \
  tests/test_covpush_w104_gaps_b.py::TestSkillRoutes \
  -q --tb=short
```

| Version | Result | Log |
|---|---|---|
| Python 3.14 | **38 passed** | `focused-314.log` |
| Python 3.11 | **38 passed** | `focused-311.log` |

The file contains main's original contract controls plus 8 new authority
controls (6 promote/delete change twins and 2 stale-entry resolution twins).

## Affected skill / registry / review / audit selection

```sh
$PY314 -B -m pytest -p no:randomly \
  tests/test_community_skill_write_contract.py \
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
  -q --tb=line
```

| Tree | Python | Passed | Failed | Log |
|---|---|---|---|---|
| Candidate `bd43da644` | 3.14 | **264** | 4 | `affected-314.log` |
| Candidate `bd43da644` | 3.11 | **264** | 4 | `affected-311.log` |
| Main `d860072a7` | 3.14 | 254 | 6 | `baseline-main-314.log` |
| Main `d860072a7` | 3.11 | 254 | 6 | `baseline-main-311.log` |

The candidate's 4 failures are byte-identical to the baseline's first 4:

- `TestPackageRoutesRequireAuth::test_approve_package_requires_auth`
- `TestPackageRoutesRequireAuth::test_install_packages_requires_auth`
- `TestMarketplaceInstallRequiresAuth::test_install_marketplace_skill_requires_auth`
- `TestPackageRoutesNoStrELeak::test_no_str_e_in_http_exceptions`

All four are pre-existing missing-module import errors in
`tests/test_round22_marketplace_security.py` (`api.package_routes` /
`api.marketplace_routes`), unrelated to the two community-skill routes.

Main additionally fails:

- `TestSkillRoutes::test_promote_skill`
- `TestSkillRoutes::test_delete_skill`

A two-test baseline run on main is in `baseline-main-route-unit.log`
(**2 failed**). The route-unit fixture now supplies the authorized DB row read
by main's guard and exercises the routed wrapper, so both pass on the
candidate.

## Delta

- Candidate vs main: **+10 passing controls**, **−2 baseline failures**, same
  4 baseline failure identities.
- Scope of new controls: 8 authority controls plus the 2 repaired route-unit
  tests.
- No test was removed from main's coverage: the removed
  `test_skill_review_write_contract.py` belonged to the removed parallel
  engine; its semantic controls live in main's community contract, and the
  unique authority controls were ported.

## Commands for the route-unit baseline

```sh
$PY314 -B -m pytest -p no:randomly \
  tests/test_covpush_w104_gaps_b.py::TestSkillRoutes::test_promote_skill \
  tests/test_covpush_w104_gaps_b.py::TestSkillRoutes::test_delete_skill \
  -q --tb=line
```

Result on main `d860072a7`: **2 failed, 0 passed**.
