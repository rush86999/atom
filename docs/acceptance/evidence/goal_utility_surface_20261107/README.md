# Goal utility surface — scoped reads + enabled Activity consumer

**Scope:** NEXT-01 (GOAL-02) finite repair. This closes the peer-workspace
direct-read leak and exposes the existing persisted utility target/ranking on
the enabled Goal Runs detail surface. It does **not** change the historical
143-claim score, the PR707/PR715 backend acceptance, or make utility a
completion signal.

**Source:** `37d1b8200` on `codex/goal-utility-surface-20261107`, based on
`cf5e98191` (merged main; runtime tree equal to audited `8ed44fabe`) plus the
root permanent probe `6a597bf31`.

## Root defect preserved

Root reproduced at `8ed44fabe`:

- `GET /api/goals/g-1` with a peer-workspace user → 200 and the goal title;
- `GET /api/goals/g-1/utility` with a peer-workspace user → 200 and the target
  shape.

Raw predecessor evidence:
`predecessor-root-goal-read-scope-negative.log` and
`predecessor-root-goal-read-scope-negative.exit.json` (2 failed, 2 passed;
actual exit 1). The permanent probe is
`backend/tests/test_lead_goal_reads_workspace_scope.py`.

## Repair

- `GoalService.get_goal` now defaults to the service workspace, matching
  `list_goals`. `get_utility_target` and `utility_ranking` inherit the same
  default.
- Trusted internal callers that deliberately need an unscoped lookup can pass
  `workspace_scoped=False`; no production caller does so today. The opt-out is
  covered by a test so it cannot silently disappear.
- Personal/null/default behaviour is preserved through the existing
  `resolve_workspace_id` fallback: a user with `workspace_id=None` resolves to
  `default` and reads a goal stored in `default`; it cannot read a `ws` goal.
- Writes continue to use the existing `goal_write_service` CAS/authority
  receipts. A peer-workspace supervisor gets 404 on set/clear; a current DB
  role change governs the mutation, not the request snapshot.

## UI

On `/goal-runs/[id]`:

- any signed-in member sees the persisted target and deterministic ranking;
- `team_lead+` can set/clear the existing validated target
  (`human_interventions|steps_executed|replan_count` ×
  `minimize|maximize`, source `goal_run`);
- no target → explicit no-target state;
- target with no eligible completed run → explicit no-eligible state;
- failed/cancelled/unknown candidates are listed as withheld with their reason;
- load failure → explicit error + retry, never a fabricated target;
- save/clear reloads the ranking; utility never changes status/progress.

The UI calls the existing `/api/goals/{id}/utility` endpoints. No new router,
store, review engine, model call, provider setup or utility-driven completion
was added.

## Executed checks

All backend pytest commands went through
`/private/tmp/atom-agent-cli/run_bounded_test_gate.py --profile bounded` with
the shared lock. Each run used a fresh unique `mktemp` scratch directory,
`TESTING=1`, synthetic `SECRET_KEY`, and no live DB/provider/model.

| Check | Result | Artifact |
|---|---|---|
| Root scope probe + GOAL-02 + goal write authority + projection boundaries | **79 passed, 3 skipped** | `backend-goal-scope-and-writes.log`, exit `backend-goal-scope-and-writes.exit.txt` |
| Goal run service/loop/routes/journey + agent objective consumers | **70 passed** | `backend-consumers.log`, `backend-consumers.exit.txt` |
| Goal Run detail component tests | **25 passed** | `frontend-detail.log`, `frontend-detail.exit.txt` |
| TypeScript `tsc --noEmit` | **exit 0** | `typescript.log`, `typescript.exit.txt` |

The 3 skips are the pre-existing documented redundant nullable-metadata matrix
cases in `test_goal_write_authority_contract.py`; they are not dropped or
suppressed.

Frontend deps were **not installed**. The worktree used the existing
`/private/tmp/atom-browser-capture-frozen-20261107/frontend-nextjs/node_modules`
via a gitignored symlink; Jest 30.3.0 and the worktree's `tsc` were used
directly. Provenance is in `verification.json`.

## Boundaries / non-claims

- No live model inference, provider/account/credential, send/spend, browser
  campaign, PostgreSQL, multi-worker or soak claim.
- Single-tenant app; the workspace check is a supported user/workspace
  safeguard, not a new SaaS tenant boundary.
- PR707/PR715 backend acceptance remains at its actual source; this evidence
  does not rescore it.
- ORCH/docs-export/backup proposals are untouched.

## Review handoff

Root owns ordinary UI acceptance, PR creation and CI. This branch is a coherent
code+test checkpoint, not self-acceptance.
