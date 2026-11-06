# Agent update/promote decisions — test results

Executed source: `5bebaaba96e728d6f4d0c66652095c1375c48b42`  
Product source: `af511bef0823051accefa415a48f065b9dffc3bf`  
Accepted admin base: `9d73552d249ae8ec5b05af77546faf9621bbcd47`  
Runtime: real scratch SQLite with fresh sessions; no live agent/model/provider.

Every command ran from the backend root with:

```sh
export PYTHONDONTWRITEBYTECODE=1
export TESTING=1
export PYTHONPATH=$PWD
PY314=/Users/rushiparikh/projects/atom/backend/venv314/bin/python
PY311=python3.11
```

## Focused agent decision gate

```sh
$PY314 -B -m pytest -p no:randomly \
  tests/test_agent_decision_contract.py \
  -q --tb=short
```

Result: **34 passed** (`focused-314.log`). The same command with `$PY311` gives
**34 passed** (`focused-311.log`).

## Affected agent / registry / audit selection

```sh
$PY314 -B -m pytest -p no:randomly \
  tests/test_agent_decision_contract.py \
  tests/unit/api/test_agent_routes.py \
  tests/test_agent_routes_coverage.py \
  tests/contract/test_agent_api_contract.py \
  tests/test_agent_delete_cascade.py \
  tests/test_covpush_agents.py \
  tests/test_agent_action_audit.py \
  tests/unit/test_agent_governance_service.py \
  tests/unit/governance/test_agent_governance_coverage.py \
  tests/test_governance_graduation_integration.py \
  -q --tb=short
```

Result (3.14): **429 passed, 3 skipped, 27 failed baseline**
(`affected-314.log`). The same selection on `9d73552d2` (without the new
contract file) gives **395 passed, 3 skipped, the same 27 failed**
(`baseline-314.log`). The failure lists are byte-identical; the branch adds 34
passing controls.

For 3.11, the contract file is excluded because the 3.11 environment lacks
`schemathesis` (the contract conftest cannot import). The remaining selection
gives **411 passed, 26 failed baseline** (`affected-311.log`); the same
selection on `9d73552d2` gives **377 passed, the same 26 failed**
(`baseline-311.log`). Failure lists are byte-identical.

### Baseline failures

The 27 (3.14) / 26 (3.11) failures are pre-existing and unrelated to the two
decision routes:

- `test_covpush_agents.py` agent gateway message and request-manager controls;
- `test_unit/api/test_agent_routes.py::TestDeleteAgent::test_delete_agent_success`;
- `test_unit/test_agent_governance_service.py` maturity/cache controls;
- `test_contract/test_agent_api_contract.py::TestAgentListContract::test_get_agents_invalid_pagination`
  on 3.14 only.

They reproduce exactly on the accepted admin base.

## Coverage matrix

- workspace_admin and admin twins; member and team-lead refusal.
- Missing, cross-tenant and cross-workspace targets -> 404, no effect.
- Update name/description/capabilities/promotion_episode_floor; empty or
  matching update -> no-change/effect none.
- Promote non-autonomous -> autonomous; already autonomous -> no-change;
  same-operation replay -> already_applied.
- Stale peer edit before the claim -> 409, peer preserved.
- Same operation + changed material -> 409; later revision ->
  committed_unverified.
- Deactivation or tenant/workspace move after the target read -> effect-none
  refusal, target unchanged, zero audit.
- Audit constraint rollback -> 409 not_applied/effect none.
- Post-commit readback -> 503 committed_unverified.
- Lost confirmation -> 503 effect_unknown with identity; no exception text.
- 16 audit-tamper variants never certify.
- No raw capability/config/secret in audit metadata, descriptions or logs.

## Counts

- Focused: 34 passed on both versions.
- Affected 3.14: 429 passed + 27 exact baseline failures.
- Affected 3.11: 411 passed + 26 exact baseline failures.
- Baseline 3.14: 395 passed + same 27; baseline 3.11: 377 passed + same 26.
- New passing controls: 34.
- Selections overlap; totals are not added together.

## Scope

No live agent execution, model, provider, credential, spend, send, download,
deployment, PostgreSQL/soak or multi-worker operation. No new table or
migration. Delete/run/teach/feedback/replace remain out of scope. Repaired
memory/tool-mutation/skill branches are independent.
