# ORCH-07 — governed fleet-routing decision and exact outcome join

Status: **submitted for independent verification.** This is the bounded
ORCH-07 controlled-consumer slice from the accepted ORCH-01 line. It proves the
real `AtomMetaAgent.execute` fleet branch writes the governed decision row under
the authenticated execution/tenant/workspace and joins the finalized outcome to
that exact row. ORCH-02's response-consumption outcome remains separate/open.

## Executed source

| Item | Value |
|---|---|
| Branch | `codex/orch07-fleet-audit-20261105` |
| Accepted ORCH-01 source | `943fb32d7` |
| Executed source | `b9ba56995` |
| Tree at execution | clean (`0 modified, 0 untracked`) |
| Runtime | real scratch SQLite; doubled NLU/fleet transport; controlled ReAct answer |
| Live model/provider/browser calls | none |

The accepted ORCH-01 branch remains at `943fb32d7`; this slice is on its own
successor branch.

## Consumer path

```
AtomMetaAgent.execute
  -> execute_unaudited
     -> NaturalLanguageEngine.classify_route (doubled: ONE_OFF)
     -> fleet-eligible branch
        -> route_with_governance (doubled FleetAdmiral transport)
        -> record_fleet_decision (real audit writer)
     -> shadow: Queen->ReAct finalize
     -> enforced: recruitment-summary return (outcome joined before return)
        -> record_fleet_execution_outcome (real exact join)
```

The test does not manufacture the audit row or call the writer directly for
the consumer proof. It runs the normal public agent entry and lets the real
fleet branch/finalize write and join the row. The fleet transport is doubled;
scope, persistence, audit and outcome joining are real.

## Contract

### Scope authority

- `AtomMetaAgent` now persists `workspace_id` on the authenticated
  `AgentExecution` row.
- `record_fleet_decision` resolves the `AgentExecution` by `execution_id` and
  uses its tenant/workspace/agent as the audit scope. Caller scope cannot
  override it.
- A caller scope that conflicts with the execution row is recorded as
  `decision_source="scope_conflict"` with an explicit error; the authoritative
  execution scope is retained.
- A missing/incomplete execution is recorded as `scope_unverified`, never as a
  default scope, and cannot receive a calibration-eligible outcome.

### Truthful decision row

- Chain, roster, selected-specialist count, `recruitment_succeeded`, `enforced`
  (shadow vs live), error and scope are persisted.
- The enforced path currently returns a recruitment summary without specialist
  execution. It is joined as a **non-success** (`success=False`) with an explicit
  `without specialist execution` error; it is not certified as a fleet win.
- Shadow recruitment falls through to Queen->ReAct; its joined success is the
  incumbent baseline, and the row remains `enforced=False`.
- Finalization records the actually served model/provider from the accepted
  BYOK route attribution, not a hardcoded `meta_agent/internal`. An attempted or
  absent route is not reported as served.

### Exact outcome join

- Finalization captures the exact audit row id and passes it with the
  execution/tenant/workspace to `record_fleet_execution_outcome`.
- The join verifies the audit row's execution, tenant and workspace against the
  authenticated `AgentExecution`; a different execution cannot complete or
  overwrite it.
- The join is first-writer-wins: the first finalized outcome is applied; a
  duplicate with the same success is `already_applied`; a stale/different writer
  is `conflict` and leaves the row unchanged.
- A fresh session sees the same joined outcome.

### Calibration/automation

- Calibration counts only rows with `success` populated; pending and
  scope-unverified rows are excluded.
- Workload stats now expose `enforced_n` and `shadow_n` so shadow-only data is
  visible as baseline, not as a live-fleet win.
- The automation pass commits its approval/revocation rows; without that, the
  queue/audit action was flushed but never durable.
- In the default `approve` mode, healthy shadow-only data queues a consent
  approval; it does not silently apply force-enforce.

## Controls

- **Controlled consumer: 7 passed on Python 3.14 and 3.11**
  (`consumer-314.log`, `consumer-311.log`):
  shadow scoped decision + exact outcome; enforced recruitment-only non-success;
  exact/idempotent/stale outcome joins; scope conflict/missing execution;
  pending/scope-unverified calibration exclusion; shadow-only consent queue;
  attempted-route non-provenance.
- **Focused fleet/audit gate: 65 passed on both versions**
  (`focused-314.log`, `focused-311.log`).
- **Affected fleet/orchestration selection: 264 passed, 5 exact baseline
  failures on both versions** (`affected-314.log`, `affected-311.log`). The 5
  are pre-existing fleet-deadlock source checks and Round-20 route-security
  checks, identical at `943fb32d7` (`baseline-5-943fb32d7-314.log`,
  `baseline-5-943fb32d7-311.log`).

## Boundaries

- No live model, provider, credential, spend, send, download, deployment,
  browser or real sandbox operation.
- The FleetAdmiral transport is doubled; recruitment quality is not qualified
  here.
- ORCH-02 response consumption (recruited specialists' work reaching the
  user-visible response) remains open and is not claimed.
- PostgreSQL runtime/soak, multi-worker qualification and whole-app ORACLE-01
  remain open.
- Accepted admin/auth-2FA/canvas/feedback/wait/employee/ORCH-01 and the
  submitted memory/evolution repairs remain independent.

## Artifacts

`consumer-*.log`, `focused-*.log`, `affected-*.log`,
`baseline-5-943fb32d7-*.log`, `source-tree.txt`, `README.md`,
`TEST_RESULTS.md`, `verification.json`, `routes.json`. `MANIFEST.json` records
the SHA-256 of every artifact and source file.
