# Fleet integrated repair — test results

Executed source: `68c5bf960` on `codex/fleet-b9-581-integrated-repair-20261105`
(ORCH-07 `b9ba56995`, ORCH-02 `581654d21`, accepted ORCH-01 `943fb32d7`).
Runtime: real scratch SQLite, doubled NLU/specialist transport. No live
model/provider/browser/sandbox operation.

## Integrated verifier probes

```sh
TESTING=1 PYTHONPATH=$PWD python -B -m pytest -p no:randomly \
  /private/tmp/test_verifier_orch07_b9_bindings.py \
  /private/tmp/test_verifier_orch02_581_contracts.py -q --tb=short
```

| Version | Result | Log |
|---|---|---|
| Python 3.14 | **19 passed** | `probes-314.log` |
| Python 3.11 | **19 passed** | `probes-311.log` |

The in-repo twins are
`tests/test_orch07_fleet_binding_contract.py` and
`tests/test_orch02_fleet_contract.py`; both pass in the gates below.

## ORCH-07 gate

```sh
TESTING=1 PYTHONPATH=$PWD python -B -m pytest -p no:randomly \
  tests/test_orch07_fleet_audit_consumer.py \
  tests/unit/test_fleet_routing_stats.py \
  tests/unit/test_fleet_routing_audit_wire.py \
  tests/unit/test_fleet_router_automation.py \
  tests/unit/test_fleet_routing_wire.py \
  tests/test_contribution_credit_p4.py -q --tb=short
```

| Version | Result | Log |
|---|---|---|
| Python 3.14 | **65 passed** | `orch07-gate-314.log` |
| Python 3.11 | **65 passed** | `orch07-gate-311.log` |

## ORCH-02 gate

```sh
TESTING=1 PYTHONPATH=$PWD python -B -m pytest -p no:randomly \
  tests/test_orch02_specialist_response.py \
  tests/test_orch07_fleet_audit_consumer.py \
  tests/unit/test_fleet_routing_stats.py \
  tests/unit/test_fleet_routing_audit_wire.py \
  tests/unit/test_fleet_router_automation.py \
  tests/unit/test_fleet_routing_wire.py \
  tests/test_contribution_credit_p4.py \
  tests/test_fleet_admiral.py \
  tests/test_agent_fleet_service.py -q --tb=short
```

| Version | Result | Log |
|---|---|---|
| Python 3.14 | **116 passed** | `orch02-gate-314.log` |
| Python 3.11 | **116 passed** | `orch02-gate-311.log` |

The original 114 controls plus the adapted enforced-finalization twin and the
explicit generic-domain positive twin.

## Affected fleet/orchestration/chat/outcome selection

```sh
TESTING=1 PYTHONPATH=$PWD python -B -m pytest -p no:randomly \
  tests/test_orch07_fleet_audit_consumer.py \
  tests/test_orch02_specialist_response.py \
  tests/test_orch07_fleet_binding_contract.py \
  tests/test_orch02_fleet_contract.py \
  tests/unit/test_fleet_routing_stats.py \
  tests/unit/test_fleet_routing_audit_wire.py \
  tests/unit/test_fleet_router_automation.py \
  tests/unit/test_fleet_routing_wire.py \
  tests/test_contribution_credit_p4.py \
  tests/test_fleet_admiral.py \
  tests/test_agent_fleet_service.py \
  tests/test_covpush_fleet.py \
  tests/test_fleet_orchestration_deadlock_fixes.py \
  tests/test_fleet_orchestration_deadlocks.py \
  tests/test_round20_agent_fleet_security.py \
  tests/test_covpush_w92f_fleet_router_routes.py \
  tests/test_chat_orchestrator.py \
  tests/test_covpush_w109_chat_orchestrator.py \
  tests/test_covpush_w115_chat_orchestrator.py \
  tests/test_covpush_w92_chat_routes.py -q --tb=short
```

| Version | Result | Log |
|---|---|---|
| Python 3.14 | **516 passed, 11 baseline failures** | `affected-314.log` |
| Python 3.11 | **515 passed, 11 baseline failures + 1 order-sensitive chat failure** | `affected-311.log` |

The 11 baseline failures are identical at `581654d21` on both versions
(`baseline-affected-314.log`, `baseline-affected-311.log`; base 495 passed, 11
failed):

- 3 `tests/test_fleet_orchestration_deadlocks.py::TestFleetOrchestrationDeadlockBugs`
- 2 `tests/test_round20_agent_fleet_security.py::TestMaturityRoutesNoUserIdFromQuery`
- 6 pre-existing chat controls (`test_lkgp_sticky_hint_exception_swallowed`,
  `test_db_fallback`, four `TestRoutingStats` controls)

On 3.11 the combined order additionally shows
`test_covpush_w115_chat_orchestrator.py::TestGetQwenResponse::test_success_with_history`
failing. It passes alone (`w115-alone-311.log`) and passes with the new contract
files plus all chat files; it is a pre-existing order-sensitive chat-history
control, not a fleet regression.

## Negative/positive coverage

- Outcome peer winner preserved; exact duplicate acknowledged; different
  boolean material refused.
- Missing/changed execution agent cannot certify; complete-scope positive twins
  apply.
- `scope_unverified` rows excluded from workload/recruitment calibration.
- Prior handler route not reported for an unserved current call; served route
  positive twin records the request-owned route.
- Foreign chain read/write refused; same-tenant chain executes.
- Opaque task case and changed roster domain do not reuse cache; exact task and
  roster do.
- Cancelled chain does not revive completed cache; completed cache still replays.
- Empty capabilities refused for domain-specific work; explicit generic route
  remains supported.
- Contradictory `success=False/status=completed` and
  `success=True/status=budget_exceeded` are failures.
- Enforced success/failure/cancellation finalize `AgentExecution` with terminal
  status/completed_at; one canonical execution id reaches the audit bracket.

## Boundaries

No live model/provider/credential/spend/send/download/deployment, no real
sandbox. Live model quality, PostgreSQL/soak, multi-worker and whole-app
ORACLE-01 remain open.
