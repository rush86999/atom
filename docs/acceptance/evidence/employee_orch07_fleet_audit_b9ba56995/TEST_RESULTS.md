# ORCH-07 fleet audit — test results

Executed source: `b9ba56995` on `codex/orch07-fleet-audit-20261105` (accepted
ORCH-01 base `943fb32d7`). Runtime: real scratch SQLite, doubled NLU/fleet
transport and a controlled ReAct final answer. No live model/provider/sandbox
call.

## Controlled consumer

`tests/test_orch07_fleet_audit_consumer.py` runs the real
`AtomMetaAgent.execute` path, real `record_fleet_decision` and real
`record_fleet_execution_outcome` against scratch SQLite.

| Version | Result | Log |
|---|---|---|
| Python 3.14 | **7 passed** | `consumer-314.log` |
| Python 3.11 | **7 passed** | `consumer-311.log` |

Covered:

1. Shadow decision row binds the authenticated execution/tenant/workspace,
   chain, two-specialist roster, count, `recruitment_succeeded=True`,
   `enforced=False`, no error; the finalized incumbent outcome joins exactly,
   with the served `controlled-provider/controlled-model` and latency; a fresh
   session sees the same row.
2. Enforced recruitment summary returns the fleet summary but joins
   `success=False` with `without specialist execution`; it is not a fleet win;
   actual model/provider are null.
3. Exact outcome join: first writer `applied`, duplicate `already_applied`,
   different/stale writer `conflict`; row keeps the first outcome. A different
   execution's row cannot be completed by this join.
4. Scope conflict uses the authenticated execution scope and records
   `scope_conflict`; a missing execution is `scope_unverified` and cannot receive
   an outcome.
5. Calibration excludes pending and scope-unverified rows; workload stats show
   one enforced and one shadow row; phase is `collecting`, not an enforced win.
6. Healthy shadow-only data in default `approve` mode queues a consent approval;
   it does not silently apply force-enforce.
7. With no served route attribution, the row's actual model/provider are null;
   an attempted route is not reported as served.

## Focused fleet/audit gate

```
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
| Python 3.14 | **65 passed** | `focused-314.log` |
| Python 3.11 | **65 passed** | `focused-311.log` |

## Affected fleet/orchestration selection

```
TESTING=1 PYTHONPATH=$PWD python -B -m pytest -p no:randomly \
  tests/test_orch07_fleet_audit_consumer.py \
  tests/unit/test_fleet_routing_stats.py \
  tests/unit/test_fleet_routing_audit_wire.py \
  tests/unit/test_fleet_router_automation.py \
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
| Python 3.14 | **264 passed, 5 baseline failures** | `affected-314.log` |
| Python 3.11 | **264 passed, 5 baseline failures** | `affected-311.log` |

The 5 are identical at `943fb32d7`:

- 3 `tests/test_fleet_orchestration_deadlocks.py::TestFleetOrchestrationDeadlockBugs`
  source-check failures.
- 2 `tests/test_round20_agent_fleet_security.py::TestMaturityRoutesNoUserIdFromQuery`
  route-security checks.

Baseline logs: `baseline-5-943fb32d7-314.log`, `baseline-5-943fb32d7-311.log`.

## Boundaries

No live model/provider/credential/spend/send/download/deployment, no real
sandbox, no ORCH-02 response-consumption claim, no PostgreSQL/soak or
whole-app ORACLE-01 claim.
