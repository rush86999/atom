# LEAD_NEXT — Agent2 code-only restore-scope handoff

## Frozen checkpoint

- Worktree: `/private/tmp/atom-oracle-refresh-20261107`
- Branch: `codex/operations-isolated-restore-20261107`
- Commit: `22f501599331dd6a6d00009097b338599513b586`
- Parent: `cd4b9f51d5a14ca9ebf3296f1187564a752b9614` (`cd4b9f51d`)
- Push: `origin/codex/operations-isolated-restore-20261107` is at `22f501599`.
- Commit is scoped to exactly three files. `opencode.jsonc` remains untracked and
  was never staged. No private archives/logs/secrets were staged.

## Files changed in the frozen commit

1. `scripts/deployment/assignment_successor_2026-10-30_fda4f2dc9/restore_support.py`
   - `_restore_scope` resolves the restore event tenant with the same
     exact-match rule used by `tools.canvas_crud_tool._scope_allows`.
   - A present contradiction between the Canvas row tenant and the current
     content audit tenant raises `RestoreRefused` before publication. Foreign
     content is never re-issued under the Canvas tenant, and a Canvas tenant is
     never re-issued under a foreign audit scope.
   - A missing scope is treated as absent provenance, not a foreign value: the
     other present scope is preserved. Personal Edition's documented `default`
     fallback applies only when both scopes are absent. Opaque ids are not
     lowercased or rewritten.
   - `_restore_event_details` rebuilds the restore-owned event from the current
     content plus an allow-list of non-authority presentation fields
     (`title`, `canvas_type`, `component`, `component_type`, `component_name`,
     `type_pinned`, filtered email `draft`). Historical operation/review/
     evidence/postcondition/success/verification/approval/reviewer/receipt
     material is not copied into the new identity.
   - `restored_from` now includes `restore_event_id` and
     `original_details_sha256` in addition to the source audit id, manifest
     SHA-256, source/target data dirs, and source tenant provenance.
   - Scope validation runs even when the current payload needs no path rebase,
     so a foreign current audit is not published as verified just because its
     bytes were not rewritten.
   - Existing historical `CanvasAudit` rows are never updated or deleted.

2. `scripts/deployment/assignment_successor_2026-10-30_fda4f2dc9/tests/test_release_restore.py`
   - Scope matrix covers same scope, missing audit scope, missing Canvas scope,
     both missing (`default`), `default` combinations, and present
     contradictions in both directions.
   - Minimal-event test proves the new event carries current target-bound
     content plus only allowed presentation fields, keeps the untouched
     historical receipt, and is what real `read_canvas` serves
     (`action_type == "restore"`, new audit id, target office path, title).
   - No-rebase test proves a generic canvas with a foreign current audit also
     refuses before publication.
   - Policy test compares two-present-scope decisions directly with
     `_scope_allows`, including case-sensitive opaque ids.

3. `docs/deployment/assignment_successor_2026-10-30_fda4f2dc9/DEPLOYMENT_RUNBOOK.md`
   - Documents the exact scope rule, refusal-before-publication behavior,
     missing-scope handling, Personal `default` fallback, minimal event payload,
     and `restore_event_id` / `original_details_sha256` provenance.

`git diff --check` was clean before commit. The pushed commit is the normal
checkpoint; no additional code is pending in the worktree.

## Controls root should run (gated; not run by this worker)

Use the mandatory shared gate, fresh scratch DB/data/office/email/Lance/output
paths, and source binding. Do not reuse prior intermediate temp copies.

1. New/changed restore contract tests in
   `scripts/deployment/assignment_successor_2026-10-30_fda4f2dc9/tests/test_release_restore.py`:
   - `test_restore_scope_matrix_refuses_only_present_contradictions`
   - `test_restore_event_is_minimal_truthful_and_keeps_canvas_readable`
   - `test_restore_refuses_foreign_current_scope_even_without_path_rebase`
   - `test_restore_scope_refusal_matches_actual_canvas_write_policy`
   - `test_restore_appends_truthful_event_and_preserves_all_original_audit_rows`
2. Permanent root 6 binding/interleaving test
   `.../tests/test_lead_restore_binding_interleavings.py`, especially
   `test_foreign_historical_audit_cannot_be_reissued_under_current_canvas_tenant`
   and `test_original_audit_complete_rows_preserved_and_current_canvas_rebased`.
3. Strengthened root 3 wrapper and
   `.../tests/test_lead_restore_integrity.py` (effective post-validation peer
   tampering must be reached and refused; signature errors are not tamper
   detection).
4. Old source 5 effective-binding positive path, to confirm the event append and
   original-row immutability still hold.
5. New root 9 / native matrix at this exact commit, plus existing restore tests,
   under the shared gate. Root owns canonical evidence/PR.

## Prior non-qualifying test context

The previous direct `pytest` run bypassed the mandatory shared gate and created
~4 GiB of unit copies that filled disk. All six copies are cold-archived with
file/link bytes and raw tool records verified; source/DB/worlds/original
negatives were untouched. The previous native 3 outcome remains **unknown**;
no test exit was inferred from a piped `tail`, and those intermediate counts are
not qualification. No tests were executed by this code-only worker at
`22f501599`.

## Child smoke state

The private child smoke prepared under
`operations_isolated_restore_4bae4c480` remains **UNRUN**. It was not launched
from this worker.

## Remaining risks / open points

- No execution evidence exists for `22f501599` yet. Do not treat this handoff as
  a pass, acceptance, or qualification claim.
- The event allow-list intentionally drops non-authority metadata outside the
  traced read paths. If a non-office document/email canvas ever receives a
  restore event because it carries a rebased `file_path`, consumers that read
  other top-level `details_json` metadata directly (for example docs `layout`/
  `enable_comments`, email `thread_id`/`source`) would see the minimal event.
  Current restore event creation is gated on current content with an office
  binding/path, so this should be checked against the actual office consumer
  shape in the root matrix.
- Scope validation is inside the office-mapping/canvases block. Local restores
  always produce an office mapping, but this is not a validation of unrelated
  tables.
- When both scopes are absent, the `default` tenant must exist for a clean
  foreign-key world. The test fixture ensures it; Personal Edition bootstrap
  provides it in production.
- All app/ops completion remains OPEN. Root claim-audit / ORACLE inventory
  worker 92294 is separate; its handoffs and branches were not edited.
