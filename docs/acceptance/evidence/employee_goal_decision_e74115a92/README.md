# ORACLE-01 — verified goal-run supervision and cancellation decisions

Status: **submitted for independent verification.** This is the next bounded
Agent 2 mutation family from the frozen reachable map. It covers two supervisor
decisions on a goal run; plan/advance/resume/execute and live agent/model
operation remain out of scope.

## Executed source

| Item | Value |
|---|---|
| Branch | `codex/oracle01-agent-decision-20261105` |
| Accepted admin base | `9d73552d249ae8ec5b05af77546faf9621bbcd47` |
| Accepted admin product | `5fbb377a4e1eef8fdd0013275cd8b1c9b278cd41` |
| Product source | `96d838d5cdc6001242a43402eab5a52b758ac646` |
| Executed source (product + tests) | `e74115a92a6529910c24b0fe92833c1c5e48c539` |
| Tree at execution | clean (`0 modified, 0 untracked`) |
| Runtime | real scratch SQLite with fresh sessions; no live model/agent/provider |

## Scope

| Method | Path | Handler | Effect |
|---|---|---|---|
| POST | `/api/goal-runs/{run_id}/mode` | `set_supervision_mode` | `supervision_mode` + `material_revision` |
| POST | `/api/goal-runs/{run_id}/cancel` | `cancel_goal_run` | `status="cancelled"`, clear `waiting_on`, append decision log, `material_revision` |

## Authority and scope

- Mode retains `_require_supervisor` (TEAM_LEAD+). Cancel retains
  `_require_run_access` (run owner or supervisor) and the same workspace
  resolver.
- The service re-reads the current `User` row, requires active status, and binds
  current status/role/raw tenant in a guarded no-op `User` UPDATE in the
  decision transaction.
- The target is loaded by `(run_id, workspace_id)` where the workspace comes
  from the existing request resolver. Cross-workspace ids are 404.
- Mode needs TEAM_LEAD+; cancel permits the run's `created_by` owner or
  TEAM_LEAD+.

## Exact effect contract

### Mode

- Validates against `SUPERVISION_MODES` (422 otherwise).
- Already in the requested mode -> 200 no-change / `effect=none`, no audit.
- Conditional UPDATE binds id, workspace, `material_revision`, prior status and
  prior mode; sets the new mode and `material_revision = prior + 1`.
- A concurrent material writer bumps the revision; the loser gets 409
  `STALE_TARGET`, the peer state remains.

### Cancel

- Uses the existing `GOAL_RUN_TRANSITIONS` table; terminal/illegal status ->
  409 `UNSUPPORTED_STATUS`.
- Conditional UPDATE binds id, workspace, prior revision and prior status; sets
  `cancelled`, clears `waiting_on`, appends a `cancelled` decision-log entry, and
  bumps `material_revision`.
- Same-operation tombstone replay -> `already_applied`; stale/competing cancel
  -> 409 with the peer state preserved.

## Receipt and result states

The existing `AuditLog` table is written in the same transaction. Operation id:
`goal-run:mode|cancel:<supplied-or-generated>`. Metadata contains operation id,
action, event type, target id/workspace, prior/result status/mode/revision,
request/prior/result digests and actor id/role/tenant. No raw plan, parameters,
decision log, secret or SQL parameter is stored in the receipt or logs.

- `verified`: success plus additive verification/operation_id/audit_id.
- `already_applied`: same operation/material; one receipt.
- `no_change`: already-requested mode; 200/effect=none, no audit.
- `conflict` (409): invalid transition, stale revision/material, changed
  operation or authority change.
- `not_applied` (409): confirmed local rollback; `effect=none`.
- `committed_unverified` (503): post-commit readback failed/refuted.
- `effect_unknown` (503): lost confirmation; original identity, no exception
  text.

## Caller / parallel-writer map

| Caller or consumer | Action |
|---|---|
| `set_supervision_mode` / `cancel_goal_run` routes | verified decision service |
| `GoalRunService` mode/cancel methods | retained for internal/test callers; routes no longer use them |
| plan/parameters/cursor/wait/resume writers | all advance `material_revision`; a concurrent write makes the decision stale |
| `AuditLog` | additive safe receipt |
| plan/advance/resume/execute | unchanged and out of scope |

## Controls

- **Focused: 27 passed on Python 3.14 and 3.11**
  (`focused-314.log`, `focused-311.log`).
- **Affected goal-run selection: 148 passed on both versions**
  (`affected-314.log`, `affected-311.log`).
- **Baseline at `9d73552d2` (without the new contract file): 121 passed on both**
  (`baseline-314.log`, `baseline-311.log`). The branch adds exactly 27 passing
  controls; there are no baseline failures in this selection.

The new matrix covers supervisor/owner/cross-workspace authority, invalid and
no-change modes, revision races, replay/changed material/later revision,
cancellation transitions, audit rollback/readback/lost confirmation, audit
tampering and authority change.

## Boundaries

- No plan/advance/resume/execute/checkpoint changes and no live agent/model
  execution.
- No new table, migration or second goal/approval/authorization engine.
- PostgreSQL runtime/soak, multi-worker serialization and whole-app ORACLE-01
  remain open.
- Repaired review/memory/skill/agent branches are independent and not merged.

## Artifacts

`focused-*.log`, `affected-*.log`, `baseline-*.log`, `source-tree.txt`,
`README.md`, `TEST_RESULTS.md`, `verification.json`, `routes.json`.
`MANIFEST.json` records the SHA-256 of every artifact and source file.
