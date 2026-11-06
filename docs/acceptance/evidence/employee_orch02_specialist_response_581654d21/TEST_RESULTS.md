# ORCH-02 specialist response — test results

Executed source: `581654d21` on `codex/orch02-specialist-response-20261105`
(ORCH-07 base `b9ba56995`, accepted ORCH-01 `943fb32d7`). Runtime: real scratch
SQLite, doubled specialist transport and controlled specialist outputs. No live
model/provider/sandbox call.

## Controlled consumer

`tests/test_orch02_specialist_response.py` runs the real
`AtomMetaAgent.execute` enforced path and the real chat
`_handle_agent_request` mapping.

| Version | Result | Log |
|---|---|---|
| Python 3.14 | **10 passed** | `consumer-314.log` |
| Python 3.11 | **10 passed** | `consumer-311.log` |

Covered:

1. Two recruited specialists execute through the shared `GenericAgent` path;
   the returned `final_output` cites both names and outputs; the exact ORCH-07
   audit row is `success=True`, `enforced=True` with the served route.
2. The real chat handler returns the specialist `final_output` as the
   user-visible `message` with `status=success`.
3. Partial success cites the successful specialist and lists the failed one.
4. All-failed is `specialists_failed`, `success=False`, no fabricated citations,
   audit `success=False`.
5. Missing/foreign specialists are refused before dispatch; no-suitable is
   explicit and audit-false.
6. Disabled specialists are not dispatched.
7. Wrong-capability roster entries are refused before dispatch; the capable
   specialist still runs.
8. Cancellation stops before the next specialist; partial work is preserved and
   the run is explicit non-success.
9. Duplicate continuation returns the cached completed result without a second
   `GenericAgent` call.
10. Empty roster is explicit no-suitable with zero dispatch.

## Focused gate

```
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
| Python 3.14 | **114 passed** | `focused-314.log` |
| Python 3.11 | **114 passed** | `focused-311.log` |

## Affected fleet/orchestration selection

```
TESTING=1 PYTHONPATH=$PWD python -B -m pytest -p no:randomly \
  tests/test_orch02_specialist_response.py \
  tests/test_orch07_fleet_audit_consumer.py \
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
  tests/test_covpush_w92f_fleet_router_routes.py -q --tb=short
```

| Version | Result | Log |
|---|---|---|
| Python 3.14 | **277 passed, 5 baseline failures** | `affected-314.log` |
| Python 3.11 | **277 passed, 5 baseline failures** | `affected-311.log` |

The 5 are identical at `943fb32d7`:

- 3 `tests/test_fleet_orchestration_deadlocks.py::TestFleetOrchestrationDeadlockBugs`
  source checks.
- 2 `tests/test_round20_agent_fleet_security.py::TestMaturityRoutesNoUserIdFromQuery`
  route-security checks.

Baseline logs: `baseline-5-943fb32d7-314.log`, `baseline-5-943fb32d7-311.log`.

## Boundaries

No live model/provider/credential/spend/send/download/deployment, no real
sandbox. The specialist transport is doubled; live model quality is not
qualified. ORCH-07 audit evidence remains at its own source. PostgreSQL/soak
and whole-app ORACLE-01 remain open.
