# Handoff — source authority safety contract

- Worktree: `/private/tmp/atom-task-wait-01-reconciliation-20261107`
- Branch: `codex/task-wait-01-reconciliation-20261107`
- Committed source: `d6cb06ff71f3ead5baa996d9b6a183871ba4a134`
- Parent: `6e776dff0`; root permanent tests `b8c7d995a`; main `36fa4ce39`
- No post-fix pytest exit is claimed: the bounded gate returned exit 126
  permission denied before dispatch. Root must run the command in README.
- Static compile at the committed source: exit 0 (`compile.log`).
- Root negatives preserved: `root-source-unavailable-negative.log` (2 failed),
  `root-upload-removed-negative.log` (1 failed).
- G1/G4 tests and G3 proposal retained; no broad UI or new engine/store/router/
  budget. 143 claims and historical scores unchanged.
- No live model/provider/browser/account/credential/send/spend/install.

Do not bypass the 4 GiB/disk or permission gate. The integration worker may
still hold the lock; the gate serializes.
