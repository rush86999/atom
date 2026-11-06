# Verified full agent replacement (PUT) — scope, material and receipt

Status: **submitted for independent verification.** PR
[#681](https://github.com/rush86999/atom/pull/681). No merge or deployment was
performed.

## Confirmed finding on base main `33b8d6472`

A tenant-A `workspace_admin` replaced a tenant-B agent:

```
PUT /api/agents/foreign-agent
status 200
body {"success":true,"data":{"agent_id":"foreign-agent"},...,"message":"Agent Hijacked replaced successfully"}
foreign_agent_name Hijacked
foreign_agent_category hijacked
```

Log: `cross-tenant-repro-base.log`. The route loaded by id only, wrote
name/description/category/configuration/schedule directly and committed. There
was no tenant/workspace scope, exact-prior CAS, operation id, receipt, replay
or readback.

## Executed source

| Item | Value |
|---|---|
| Branch | `codex/oracle01-agent-replace-20261106-v2` |
| Base main | `33b8d6472605b7fbb4c84a9e21286c3d168b7d5c` |
| Executed source | `7503171eca9d27915d2911fb2fc0cc961bde9b8b` |
| Runtime | real scratch SQLite; no live model/provider |

The repair reuses the merged agent-decision engine (`update/promote/delete/
run`), including its current-authority claim, audit/replay machinery and
tenant/workspace visibility policy.

## Route and contract

| Method | Path | Handler | Service |
|---|---|---|---|
| PUT | `/api/agents/{agent_id}` | `api.agent_routes.replace_agent` | `core.agent_decision_write_service.replace_agent` |

### Authority and scope

- Route permission remains `AGENT_MANAGE` plus `get_current_user`.
- The service re-reads the current `User`, requires active status and
  `WORKSPACE_ADMIN+`, and claims `is_active`/`status`/`role`/raw tenant/raw
  workspace in the replacement transaction.
- Reuses the merged agent visibility policy: foreign tenant/workspace -> 404;
  workspace-bound actor below ADMIN only same/legacy workspace; ADMIN+ may
  cross workspaces inside the tenant; unscoped/platform actor keeps the
  global-legacy policy.

### Exact effect

- Required `name` and `category`; optional `description`, `configuration` and
  `schedule_config` replace existing values only when supplied, preserving the
  documented PUT behavior.
- The guarded UPDATE binds id, tenant, workspace, prior name, description,
  category, configuration, schedule_config, status and enabled. A concurrent
  edit returns 409 `STALE_TARGET` with the peer preserved.
- One `AuditLog` receipt commits in the same transaction. It stores keyed
  material digests, not raw configuration, schedule or secrets.
- Matching replacement returns 200 no-change/effect none with no audit.
- Same operation/material replays `already_applied`; changed material is a 409
  `OPERATION_CONFLICT`; confirmed rollback is 409 `not_applied` with
  `effect=none`; missing readback is 503 `committed_unverified`.
- The scheduler is updated only after a verified commit, only once, and never
  on replay/no-change. A scheduler failure is logged after the committed DB
  effect; it does not relabel the replacement as rolled back.

## Verification

| Gate | Candidate | Main `33b8d6472` |
|---|---|---|
| Focused, Python 3.14 | **72 passed** | — |
| Focused, Python 3.11 | **72 passed** | — |
| Affected, 3.14 | **368 passed, 3 skipped, 2 failed** | 358 passed, 3 skipped, 2 failed |
| Affected, 3.11 | **350 passed, 1 failed** | 340 passed, 1 failed |

The candidate adds **10 replacement controls** and introduces **zero new
failures**. Shared baseline identities:

- `tests/test_covpush_w29_governance.py::TestRegistry::test_register_new_agent` (both)
- `tests/contract/test_agent_api_contract.py::TestAgentListContract::test_get_agents_invalid_pagination` (3.14 only; 3.11 lacks `schemathesis`)

## Boundaries

- No live model, provider, credential, spend, send, download, deployment or
  scheduler execution.
- No new table or migration; PostgreSQL/soak and multi-worker remain
  unqualified.
- No merge or deployment; code-owner review remains required.
