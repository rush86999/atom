# Local backup / isolated restore — corrected candidate 4bae4c480

Executed source: `4bae4c480024bf2346117e7c661b2c87aca4a969` on
`codex/operations-isolated-restore-20261107`. Parent: `924f5f191` (root's
permanent A/B probe). Predecessor candidate: `a4b56af59`; predecessor
implementation: `d4b313992`.

This packet is the corrected NEXT-02 release-kit candidate. It does **not**
relabel or rewrite the predecessor packet
`docs/acceptance/evidence/operations_isolated_restore_d4b313992`. Root's raw
negative probe that withheld `a4b` is included unchanged.

## Correction (honest, not relabelled)

Root found two field-class failures at `a4b`:

1. **Audit history**: restore rewrote the latest content-bearing
   `CanvasAudit.details_json` (`audit-1`) to the target office path while
   claiming history was preserved. The latest content-bearing row is still
   historical audit material.
2. **Manifest binding**: a peer changed `users.first_name` after manifest
   validation but before `_copy_database`; the target published
   `PEER-UNREVIEWED` with `status=verified`.

The corrected candidate makes `CanvasAudit` append-only and appends one truthful
restore-owned event with new id/provenance while leaving every original row
byte-identical. It binds the database copy to the exact manifest-validated bytes
through a private frozen nofollow image, refusing in-place/inode/path/symlink/
sidecar changes after validation. See `verification.json` and the corrected
runbook.

## Verification at the executed source

- `final-gate.log`: **80 passed**, exit 0, shared bounded gate
  (root 3 + native restore 34 + existing db-safety/kit 43).
- `final-gate-command.json`: exact executed argv.
- `failure-first-4bae4c480.json`: safe synthetic-root failures, exit 2, no
  target effect.
- `root-restore-integrity-negative.{log,spec.json,exit.json}`: predecessor
  `a4b` raw probe, **2 failed, 1 passed**, preserved unchanged.
- `source-hashes.json`: exact file hashes at `4bae4c480`.

## Child backend proof

**Not run.** No child process/world was launched. At the decision point free
space was `4,413,313,024` bytes, only `118,345,728` bytes above the literal
4 GiB floor; the 80-test gate had already consumed more than 700 MB. A full-app
child needs a scratch source world, target, DB/LanceDB and logs, so launching it
would not maintain the required >=4 GiB working margin. `child-backend-not-run.json`
records the blocker; `CHILD_RESTORE_SMOKE_WORKORDER.md`,
`child_restore_seed.py` and `child_restore_readback.py` freeze the exact harness
for root to run after cleanup. No HTTP acceptance is claimed.

Service-level target reads after the original source is renamed/unavailable are
proven in the native matrix (`read_canvas`, document/dataset/goal rows, office
artifact file, and memory-included LanceDB content readback when included).

## Boundaries

Local SQLite only. No live DB/world/provider/account/credential/send/spend/
install/deploy, no acceptance-world relocation, no new backup engine/store/
router/authority lifecycle. Code rollback remains code-only
(`database_restored: false`, `user_data_preserved: true`) and was not run.
Full-app ORACLE/claim scores remain OPEN. Root owns independent review, normal
PR/CI acceptance and merge.
