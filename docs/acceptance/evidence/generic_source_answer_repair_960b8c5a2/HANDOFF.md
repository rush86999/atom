# Handoff — source-answer material/CAS repair

- Worktree: `/private/tmp/atom-task-wait-01-reconciliation-20261107`
- Branch: `codex/generic-source-answer-20261107` (separate successor)
- Stack base: `7d38d2ac9`; source branch remains frozen there.
- Root probes: `c58340b18`; repair source: `960b8c5a2`
- Root negatives preserved: material **1 failed/exit1**, snapshot CAS
  **1 failed/exit1**, findings JSON.
- Clean focused: backend **11 passed**, UI **11 passed**, exit 0.
- Fixes: full text+source digest in durable snapshot; replay/lost-CAS compare it;
  pending claim CASes on observed context_snapshot/action/status. Peer snapshot
  preserved with 409 zero effect.
- Remaining: source-specific actual-process restart order, source-upload-alone
  route confirmation, ordinary UI episode (root).
- No dependency install/live model/provider/account/spend/deploy. Root owns
  PR/CI/review/merge.
