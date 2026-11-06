# Controlled agent-run admission — scoped authority, exact material and durable job

Status: **submitted for independent verification.** PR
[#675](https://github.com/rush86999/atom/pull/675), targeting `main` and
carrying the green #673 delete source `46dc253a1` as a dependency. The PR diff
therefore includes both agent-mutation families until #673 merges. No merge or
deployment was performed.

## Confirmed finding on base main `f8706fb48`

A tenant-A **member** started a tenant-B agent:

```
POST /api/agents/foreign-agent/run
status 200
body {"success":true,"data":{"agent_id":"foreign-agent"},"message":"Agent execution started"}
dispatch_calls [('foreign-agent', {})]
```

Log: `cross-tenant-repro-base.log` (execution stubbed; no live model call).
The route loaded the target by id only, had no tenant/workspace scope, created
no durable job or receipt, and relied on a stale `SELECT FOR UPDATE` /
`agent.status` check that never transitioned the row.

## Executed source

| Item | Value |
|---|---|
| Branch | `codex/oracle01-agent-run-20261106` |
| Stacked on | #673 evidence tip `46dc253a1` (delete source `e34de29d5`) |
| Underlying main | `f8706fb48569e77df21801df1cc23a8d7b61ba17` |
| Executed source | `1a76d7151105d8e7c845b0f7512a4bbf0e576f52` |
| Runtime | real scratch SQLite; execution stubbed in tests; no live model/provider |

The run admission reuses the merged agent-decision authority/scope/audit
machinery; it is not a second approval or agent engine.

## Route and contract

| Method | Path | Handler | Service |
|---|---|---|---|
| POST | `/api/agents/{agent_id}/run` | `api.agent_routes.run_agent` | `core.agent_decision_write_service.admit_agent_run` |

### Authority and scope

- Route permission remains `AGENT_RUN` plus `get_current_user`.
- The service re-reads the current `User`, requires active status, and claims
  `is_active`/`status`/`role`/raw tenant/workspace inside the admission
  transaction. The authority floor is `MEMBER` (the route permission already
  establishes `AGENT_RUN`).
- Reuses the agent visibility policy: member same-workspace or legacy
  workspace-less; ADMIN+ cross-workspace inside the tenant; foreign tenant or
  workspace -> 404; unscoped platform actor keeps global-legacy policy.
- Deprecated/paused -> 400 `AGENT_INVALID_STATE`; running or an existing
  active `AgentJob` -> 409 `ALREADY_RUNNING`.

### Durable effect

- Exact prior `AgentRegistry` material is claimed, including configuration and
  enabled, and the row transitions to `running` with one guarded UPDATE. A
  concurrent edit -> 409 `STALE_TARGET` with the peer preserved.
- One `AgentJob` row (id, tenant, agent, status `running`, operation id +
  parameters digest) and one `AuditLog` receipt are committed in the same
  transaction. Neither stores raw parameters or configuration.
- The route dispatches the existing execution only after the admission
  transaction commits. The job lifecycle wrapper marks the job
  running/success/failed and restores the prior agent status when the
  execution finishes.
- Same operation/parameters replays `already_applied` without a second
  dispatch; changed parameters -> 409 `OPERATION_CONFLICT`; confirmed rollback
  -> 409 `not_applied` with `effect=none`; missing readback -> 503
  `committed_unverified`.
- Readback requires the durable job to exist with the same operation id.

## Verification

| Gate | Candidate | #673 base |
|---|---|---|
| Focused, Python 3.14 | **67 passed** | — |
| Focused, Python 3.11 | **67 passed** | — |
| Affected, 3.14 | **358 passed, 3 skipped, 2 failed** | 346 passed, 3 skipped, 2 failed |
| Affected, 3.11 | **340 passed, 1 failed** | 328 passed, 1 failed |

The candidate adds **12 admission controls** and introduces **zero new
failures**. Shared baseline identities:

- `tests/test_covpush_w29_governance.py::TestRegistry::test_register_new_agent` (both)
- `tests/contract/test_agent_api_contract.py::TestAgentListContract::test_get_agents_invalid_pagination` (3.14 only; 3.11 lacks `schemathesis`)

## Limits

- A process death between admission commit and dispatch leaves a running job
  and the agent in `running` state; stale-job reconciliation is not part of
  this controlled slice.
- Actual agent execution, model/provider calls, spend and external sends remain
  held separately.
- No new table or migration; PostgreSQL/soak and multi-worker remain
  unqualified.
- No merge or deployment.
