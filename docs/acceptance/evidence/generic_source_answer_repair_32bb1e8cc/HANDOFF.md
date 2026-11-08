# Handoff — source-answer material/CAS/restart repair

- Worktree: `/private/tmp/atom-task-wait-01-reconciliation-20261107`
- Branch: `codex/generic-source-answer-20261107` (separate successor)
- Stack base: `7d38d2ac9`; source branch remains frozen there.
- Root probes: `c58340b18`; executed repair source: `32bb1e8cc`
- Root negatives preserved: material **1 failed/exit1**, snapshot CAS
  **1 failed/exit1**, findings JSON.
- Clean focused on committed source: backend **20 passed**, UI **11 passed**,
  exit 0.
- Fixes: full text+source digest in durable snapshot; replay/lost-CAS compare it;
  pending claim CASes on observed context_snapshot/action/status. Peer snapshot
  preserved with 409 zero effect.
- Real-process rows: source answer after restart, accepted source crash before
  claim recovered once, upload-alone inert, result withheld until verified.
- Remaining: the single ordinary UI source-selection episode (root-owned).
- No dependency install/live model/provider/account/spend/deploy. Root owns
  PR/CI/review/merge.
