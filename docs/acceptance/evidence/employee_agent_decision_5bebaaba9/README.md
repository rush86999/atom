# ORACLE-01 — verified agent update/promote decisions

Status: **submitted for independent verification.** This is the next bounded
Agent 2 mutation family from the frozen reachable map. It covers exactly the two
agent decision routes below; delete/run/teach/feedback/replace and live agent
execution remain out of scope.

## Executed source

| Item | Value |
|---|---|
| Branch | `codex/oracle01-agent-decision-20261105` |
| Accepted admin base | `9d73552d249ae8ec5b05af77546faf9621bbcd47` |
| Accepted admin product | `5fbb377a4e1eef8fdd0013275cd8b1c9b278cd41` |
| Product source | `af511bef0823051accefa415a48f065b9dffc3bf` |
| Executed source (product + tests) | `5bebaaba96e728d6f4d0c66652095c1375c48b42` |
| Tree at execution | clean (`0 modified, 0 untracked`) |
| Runtime | real scratch SQLite with fresh sessions; no live agent/model/provider |

## Scope

| Method | Path | Handler | Effect |
|---|---|---|---|
| PATCH | `/api/agents/{agent_id}` | `update_agent` | name/description/capabilities/promotion_episode_floor update |
| POST | `/api/agents/{agent_id}/promote` | `promote_agent` | status -> `autonomous` |

## Authority and scope

- Routes retain `require_permission(Permission.AGENT_MANAGE)`
  (WORKSPACE_ADMIN/ADMIN/OWNER/SUPER_ADMIN) and `get_current_user`.
- The service re-reads the current `User` row, requires active status and
  WORKSPACE_ADMIN+, and binds current status/is_active/role/raw tenant/raw
  workspace in a guarded no-op `User` UPDATE in the same transaction as the
  target write and audit.
- Target policy:
  - a real foreign tenant id is treated as not found;
  - tenant-bound actors may manage same-tenant agents and legacy tenant-less
    rows, never a real foreign tenant;
  - a workspace-bound actor below ADMIN may manage only same-workspace or
    legacy workspace-less agents; ADMIN+ may cross workspaces within the
    tenant;
  - an unscoped/platform actor keeps the existing global-legacy policy.
- Cross-tenant/workspace agent ids return 404 with zero effect. Delete/run and
  live execution are outside this family.

## Exact effect contract

### Update

- Fields: name, description, capabilities, promotion_episode_floor.
- Empty update or a request already matching the current row -> 200 no-change /
  `effect=none`, no audit.
- Conditional UPDATE binds id, tenant, workspace, prior name, description,
  capabilities, promotion_episode_floor and status. A peer edit matches zero
  rows -> 409 `STALE_TARGET`; the peer value is preserved.
- Same operation id + same request -> `already_applied`; changed material ->
  409 `OPERATION_CONFLICT`; later revision -> `committed_unverified`.

### Promote

- Sets `status="autonomous"` from any non-autonomous status.
- Already autonomous with a new operation id -> 200 no-change/effect none;
  same-operation replay -> `already_applied`.
- Conditional update binds the exact prior status/material; a peer status/edit
  matches zero rows -> 409.

## Receipt and result states

The existing `AuditLog` table is written in the same transaction. Operation id:
`agent:update|promote:<supplied-or-generated>`. Metadata contains operation id,
action, event type, target id, target tenant/workspace, agent name,
prior/result status, request/prior/result material digests and actor id/role.
No raw configuration, capability list, secret or SQL parameter is stored in the
receipt or logs.

- `verified`: success shape plus additive verification/operation_id/audit_id;
  `effect=committed`.
- `already_applied`: same operation/material; one receipt.
- `no_change`: empty/matching update or already-autonomous promote;
  200/effect=none, no audit.
- `conflict` (409): stale/changed material, changed operation, cross-scope target
  or authority change; `effect=none`.
- `not_applied` (409): confirmed rollback; `effect=none`.
- `committed_unverified` (503): post-commit readback failed/refuted.
- `effect_unknown` (503): lost confirmation; original identity, no exception
  text.

## Caller / parallel-writer map

| Caller or consumer | Action |
|---|---|
| `update_agent` / `promote_agent` routes | verified decision service |
| `AgentGovernanceService.register_or_update_agent` | registration/name/status writer; CAS detects a concurrent change to bound fields |
| graduation/confidence/promotion writers | unrelated fields; promote binds prior status |
| `delete_agent` | out of scope; dependent-row cleanup |
| list/get/run/feedback/teach/stop/replace | unchanged |
| `AuditLog` | additive safe receipt |

## Controls

- **Focused: 34 passed on Python 3.14 and 3.11**
  (`focused-314.log`, `focused-311.log`).
- **Affected agent/registry/audit selection on 3.14: 429 passed, 3 skipped, 27
  exact baseline failures** (`affected-314.log`). Baseline at `9d73552d2`:
  395 passed, 3 skipped, the same 27 (`baseline-314.log`). The branch adds 34
  passing controls; failure lists are identical.
- **Affected selection on 3.11: 411 passed, 26 exact baseline failures**
  (`affected-311.log`). The 3.11 selection excludes the contract file because
  the 3.11 environment lacks `schemathesis`; baseline at `9d73552d2`: 377
  passed, the same 26 (`baseline-311.log`). Failure lists are identical.

The baseline failures are pre-existing agent gateway message tests,
AgentRequestManager, the delete-route control, governance maturity/cache
controls and the 3.14 contract pagination control; they are unrelated to the
two verified decision routes and reproduce on the accepted admin base.

The new matrix covers workspace_admin/admin twins, member/team-lead refusal,
cross-tenant/workspace 404, update/no-op, promote/already-autonomous,
same-operation replay, changed material, later revision, stale peer edits,
authority change, audit rollback/readback/lost confirmation, audit tampering
and capability non-leakage.

## Boundaries

- No delete/run/teach/feedback/replace changes and no live agent execution.
- No live model, provider, credential, spend, send, download or deployment.
- No new table, migration or second agent/approval/authorization engine.
- PostgreSQL runtime/soak, multi-worker serialization and whole-app ORACLE-01
  remain open.
- Repaired review/memory/skill branches are independent and not merged.

## Artifacts

`focused-*.log`, `affected-*.log`, `baseline-*.log`, `source-tree.txt`,
`README.md`, `TEST_RESULTS.md`, `verification.json`, `routes.json`.
`MANIFEST.json` records the SHA-256 of every artifact and source file.
