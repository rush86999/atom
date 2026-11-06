# Scoped, verified agent deletion

Status: **submitted for independent verification.** PR
[#673](https://github.com/rush86999/atom/pull/673). No merge or deployment was
performed.

## Confirmed finding on base main `f8706fb48`

A tenant-A `workspace_admin` deleted a tenant-B agent:

```
DELETE /api/agents/foreign-agent
status 200
body {"success":true,"data":{"agent_id":"foreign-agent","rows_cleaned":{}},...}
foreign_agent_remaining 0
```

Log: `cross-tenant-repro-base.log`. The route loaded the target by id only;
`require_permission(AGENT_MANAGE)` is role-based, so tenant/workspace isolation
was absent. There was no exact-prior CAS, operation id, receipt, replay or
readback.

## Executed source

| Item | Value |
|---|---|
| Branch | `codex/oracle01-agent-delete-20261106` |
| Base main | `f8706fb48569e77df21801df1cc23a8d7b61ba17` |
| Executed source | `e34de29d53636a5232e126bcba8e5f5aa7af9734` |
| Work order | `/private/tmp/brennan-brief/AGENT2_AGENT_DELETE_WORK_ORDER_20261106.md` |
| Runtime | real scratch SQLite with fresh sessions and committed two-session interleaving; no live model/provider/agent execution |

The repair reuses the merged `core.agent_decision_write_service` authority,
scope, audit and replay machinery rather than creating a second agent engine.

## Route and scope

| Method | Path | Handler | Service |
|---|---|---|---|
| DELETE | `/api/agents/{agent_id}` | `api.agent_routes.delete_agent` | `core.agent_decision_write_service.delete_agent` |

Rename/run/stop/teach/feedback/replace remain out of scope. No new table,
migration or second agent/delete engine. The existing dynamic dependent-row
cleanup and demo bootstrap tombstone are preserved.

## Authority and exact effect

- Route authority remains `require_permission(Permission.AGENT_MANAGE)` plus
  `get_current_user`.
- The service re-reads the current `User`, requires active status and
  `role_level >= WORKSPACE_ADMIN`, and claims current
  `is_active`/`status`/`role`/raw tenant/raw workspace in the delete
  transaction.
- Reuses the merged agent visibility policy:
  - real foreign tenant -> 404, zero effect;
  - tenant-bound actor may manage same-tenant and legacy tenant-less agents;
  - workspace-bound actor below ADMIN only same-workspace or legacy
    workspace-less agents;
  - ADMIN+ may cross workspaces inside the tenant;
  - unscoped/platform actor keeps the existing global-legacy policy.
- `atom_main` -> 400 `CANNOT_DELETE_MAIN_AGENT`; running tasks -> 400
  `AGENT_HAS_RUNNING_TASKS`; both zero effect.
- The exact prior `AgentRegistry` material is claimed before cleanup: id,
  tenant, workspace, name, description, capabilities, promotion floor, status,
  configuration and enabled. A concurrent edit returns 409 `STALE_TARGET`
  with the peer value preserved.
- The existing dynamic cleanup removes every dependent row with an `agent_id`;
  the registry row is deleted; a demo tombstone is upserted in the same
  transaction; one `AuditLog` receipt is added after cleanup (the audit table
  has no `agent_id`, so it is not part of the cascade).
- Fresh-session readback verifies agent absence, zero dependent rows, a
  verified receipt and the tombstone when expected.
- Same operation/material replays `already_applied`; changed target/material
  is 409 `OPERATION_CONFLICT`; confirmed rollback is 409 `not_applied` with
  `effect=none`; missing readback is 503 `committed_unverified`; lost
  confirmation is 503 `effect_unknown` with the original identity.
- No raw configuration, prompt, secret or SQL parameter is stored in the
  receipt or logs.

## Verification

| Gate | Candidate | Main `f8706fb48` |
|---|---|---|
| Focused, Python 3.14 | **53 passed** | — |
| Focused, Python 3.11 | **53 passed** | — |
| Clean affected, 3.14 | **346 passed, 3 skipped, 2 failed** | 332 passed, 3 skipped, 4 failed |
| Clean affected, 3.11 | **328 passed, 1 failed** | 314 passed, 3 failed |

The candidate adds 12 scoped-delete controls and repairs the two delete-route
fixtures; **zero new failures**. The remaining failures are exact pre-existing
identities:

- `tests/contract/test_agent_api_contract.py::TestAgentListContract::test_get_agents_invalid_pagination` (3.14 only)
- `tests/test_covpush_w29_governance.py::TestRegistry::test_register_new_agent` (both)

The 3.11 contract file is excluded because that interpreter lacks
`schemathesis`; the 3.14 affected run includes it. The broad 3.14/3.11 runs
also contain 53 pre-existing `test_agent_control_routes.py` daemon-control
failures in both trees; they are unrelated to this delete route and are not
claimed as repaired.

## Boundaries

- No live model, provider, credential, spend, send, download, deployment or
  agent execution.
- No production role, tenant, provider, audit or cleanup gate weakened.
- No test deleted, skipped or xfailed.
- PostgreSQL runtime/soak and multi-worker remain unqualified.
