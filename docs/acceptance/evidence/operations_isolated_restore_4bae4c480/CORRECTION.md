# Correction record — predecessor claim vs corrected semantics

## What the predecessor claimed

At `a4b56af592b7b2382af67b7c54825684a4d0c467` (implementation `d4b313992`),
the runbook and evidence packet said restore rewrote only "current managed path
bindings" including "the latest content-bearing CanvasAudit row", and that
historical audit material was not rewritten.

That claim was wrong. The latest content-bearing `CanvasAudit` row is still
historical audit material. Root's probe
`test_restore_preserves_every_original_canvas_audit_byte` showed `audit-1`'s
`details_json` changed from the source office path to the restored target path.

The same predecessor also trusted a fresh stat after manifest validation.
Root's `test_backup_database_swap_after_validation_refuses_before_publication`
changed `users.first_name` to `PEER-UNREVIEWED` after validation; the target
published it with `status=verified`.

Raw files: `root-restore-integrity-negative.log`,
`root-restore-integrity-negative.spec.json`,
`root-restore-integrity-negative.exit.json` (2 failed, 1 passed at `a4b`).

## What this candidate does instead

- Every original `CanvasAudit` row is byte-for-byte immutable. No `UPDATE
  canvas_audit` exists in the restore path.
- Only current writable projections are rebased: known managed path columns,
  assignment operational paths, and `Canvas.content`.
- If `read_canvas` needs a current content-bearing row, restore **appends** a
  new `CanvasAudit` event:
  - new id; `action_type="restore"`;
  - exact canvas/tenant scope;
  - `restored_from` carrying the original audit id, created_at, action type,
    original details SHA-256, manifest SHA-256, source/target provenance;
  - target office binding;
  - old `operation_id`, `evidence_refs`, `postconditions` and `review_status`
    removed; `user_id`/`agent_id` NULL.
- Strict recency is computed from the latest audit row, so the appended event is
  actually served by `read_canvas`.
- The database copy is frozen from the exact manifest-validated bytes through a
  nofollow directory-descriptor walk, re-hashed and identity-checked, then read
  by the SQLite backup API. In-place updates, inode/path/symlink swaps, sidecar
  changes and changes during read are refused.

## Preservation of predecessor evidence

`docs/acceptance/evidence/operations_isolated_restore_d4b313992/` is left
unmodified. This packet does not relabel its wrong claim as correct; it records
the correction and the new executed source.

## Runbook

`docs/deployment/assignment_successor_2026-10-30_fda4f2dc9/DEPLOYMENT_RUNBOOK.md`
now contains the correction and append-only contract. It no longer claims the
latest audit row is rewritten.
