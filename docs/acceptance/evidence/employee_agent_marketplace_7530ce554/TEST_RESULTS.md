# Agent-marketplace publication — test results

Executed source: `7530ce554af4dc8ae3695ab016650e0bcf6479f4`  
Product source: `fb5091069f7ce55882bfb85c23dac2d26a6730eb`  
Accepted admin base: `9d73552d249ae8ec5b05af77546faf9621bbcd47`  
Runtime: real scratch SQLite; no external SaaS/network/model/provider call.

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
  tests/test_agent_marketplace_publish_contract.py \
  -q --tb=short
```

Result: **23 passed** (`focused-314.log`). The same command with `$PY311`
gives **23 passed** (`focused-311.log`).

## Affected marketplace / packaging / runtime / audit selection

```sh
$PY314 -B -m pytest -p no:randomly \
  tests/test_agent_marketplace_publish_contract.py \
  tests/test_agent_marketplace_goal_runs.py \
  tests/test_agent_marketplace_service.py \
  tests/test_marketplace_packaging_redaction.py \
  tests/core/test_marketplace_runtime.py \
  tests/test_covpush_w69_marketplace.py \
  tests/test_covpush_w69_skill_marketplace.py \
  tests/test_marketplace_satellite.py \
  tests/test_covpush_w109_marketplace_usage.py \
  tests/test_audit_logger.py \
  tests/test_covpush_w103_audit_logger.py \
  -q --tb=short
```

Result: **211 passed, 7 skipped, 24 failed baseline** on both Python 3.14 and
3.11 (`affected-314.log`, `affected-311.log`).

The same selection on the accepted admin base `9d73552d2` (without the new
contract file) gives **188 passed, 7 skipped, the same 24 failed** on both
versions (`baseline-314.log`, `baseline-311.log`). The failure lists are
byte-identical; the branch adds exactly 23 passing controls.

### The 24 baseline failures

- 23 in `tests/test_covpush_w69_marketplace.py` workflow-marketplace router
  controls, pre-existing on the accepted base from their existing app/fixture
  setup.
- `tests/test_agent_marketplace_service.py::TestSkillInstallation::test_install_agent_handles_template_not_found`
  already fails with the `int(Mock)` template-not-found path.

They reproduce exactly on the accepted admin base and are unrelated to the
verified publication route.

## Coverage matrix

- Owner member and admin publish; member non-owner 403; anonymous 401.
- Listing fields, source tenant, author, price, public/approved/active flags and
  the platform-computed verified record.
- Raw system prompt/description/name are absent from audit metadata,
  descriptions and logs.
- Missing agent 404; marketplace-managed 409; paid gate 409 with the existing
  achieved-run explanation.
- Paid listing with an achieved run succeeds; free listing always succeeds.
- Same-operation replay `already_applied`; changed price/description 409;
  missing listing `committed_unverified`.
- Source agent rename before the claim -> 409 `STALE_SOURCE`, peer agent
  preserved, no listing/audit.
- Actor deactivation or admin demotion before the claim -> effect-none.
- Audit constraint rollback -> listing and audit rolled back, 409 `not_applied`.
- Post-commit readback -> 503 `committed_unverified`.
- Lost confirmation -> 503 `effect_unknown` with original identity; no
  exception text.
- 11 audit-tamper variants never certify.

## Counts

- Focused: 23 passed on both versions.
- Affected: 211 passed + 7 skipped + 24 exact baseline failures on both.
- Baseline: 188 passed + 7 skipped + the same 24 failures on both.
- New passing controls: 23.
- Selections overlap; totals are not added together.

## Scope

No push-to-SaaS, remote install, browse, sale-readiness or listing-read changes
and no external SaaS/network/model/provider/credential/spend/send/download/
deployment operation. No new table or migration. The existing `AgentTemplate`,
`AuditLog` and packaging service are reused. PostgreSQL runtime/soak and
multi-worker qualification remain open. The submitted review/memory/skill/
agent/goal/document/workflow-template branches are independent and not merged.
