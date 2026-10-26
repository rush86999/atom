# Saved-lookup continuation — 2026-10-26

**Scope:** repair the planner-enabled saved-lookup continuation on the frozen
spreadsheet candidate (`e14d3efdd`), preserving the original failure. This is
a repair branch, not a deployment.

## Preserved failure

`planner_failure_preserved/` under the trained-eval evidence directory holds:

- `atom_run2_verbose_confirmation.db` — pending task stored; verbose
  confirmation follow-ups left the task `pending` and never dispatched a read.
- `atom_run6_no_followup.db` — planner-enabled broad review stored the pending
  task and reported that no search ran.
- `metadata_dump.json` — session/message metadata for the affected sessions.

## Trace

1. **Lookup proposed.** A planner-enabled broad review returned “the lookup
   hasn’t run; it is saved” and stored `_pending_file_task` on the session
   (`status=pending`, `attempts=0`).
2. **Confirmation persisted.** The task stayed on the session and in the
   assistant message metadata.
3. **Follow-up resolves pending operation.** A bare “Go ahead.” was matched:
   `attempts` became 1 and `confirmed_mention` was set. Before the fix the
   task was stamped `operation="re-deliver"`.
4. **First missing transition.** A `re-deliver` requires a persisted result.
   The task was still `pending` and `_pending_file_result` was absent, so the
   re-delivery was a no-op. The ask-turn direct read is suppressed while a
   pending task exists, so no read dispatched. The reply honestly said the
   lookup did not run; the task remained pending.
5. **Fix.** `resume_operation(task, message)` maps a bare approval of a
   still-`pending` task to `operation="re-run"`. The existing resume lane then
   executes the original read. Both operation-stamping sites use the helper;
   the planner is not disabled and no rows are injected into the prompt.
6. **Verified receipt.** With the repair, the bare approval:
   - ran `_direct_confirmed_file_read` against the pending file;
   - marked the task `delivered`;
   - recorded a resolved file identity
     (`trained_eval_orders_20261025.xlsx`, content hash, coverage complete);
   - recorded `tool_outcome: file_scoped_read`, `verified=true`,
     `addresses_requested=true`;
   - returned a source-cited deterministic read answer.

## Evidence

- `lookup_resume_repair_20261026/evidence.json` — repaired run: first turn
  stored pending; second turn delivered; task status `delivered`, attempts 1;
  file-scoped read receipt; assistant metadata `pending_file_result` status
  `retrieved` then `delivered`.
- `lookup_resume_repair_20261026/evidence_run1.json` — earlier dispatch
  attempt before the mention/direct-read changes (kept for comparison).
- `trained_eval_ocgo_20261026/planner_failure_preserved/` — original failure.

## Tests

Focused suite (`test_pending_file_task_resume.py`,
`test_cross_source_followup_routing.py`, `test_dataset_aggregation.py`):

- Repair branch: **301 passed, 11 failed, 2 xfailed**.
- Frozen baseline: **296 passed, 11 failed, 2 xfailed**.
- The 11 failures are the same named pre-existing failures. New tests cover
  pending-approval → re-run, retrieved-approval → re-deliver, explicit re-run,
  and the bare “Go ahead.” resume through the direct read.

## Machine settlement (traced, not patched)

The repaired read response returns `success=true` but `outcome=null`. The
persisted execution record shows:

- `task_outcome.objective_met = null`
- `completion_criteria = [{kind: "source_scoped_retrieval"}]`
- `criterion_results = []`
- `tool_outcomes = [file_scoped_read, verified=true, addresses_requested=true]`
- `success_kinds.task_success = null`, basis `objective_unknown`
- `delivery.deterministic = true`

The null originates in the **resolver**, not in serialization: the resolver
never evaluates the retrieval criterion, even though the read receipt is
verified. It was not patched to `completed`: the read fulfils retrieval, but
the original ask was a policy review and the deterministic projection returned
only part of the row contract. The review obligation is not yet fulfilled.

## Remaining gap

- The resumed item read selected Status/Qty/Unit Price; it did not return the
  full row contract (currency, both approvals, manager exception, notes) needed
  for the policy review.
- A follow-up judgment turn did not receive the persisted read result; it
  reverted to “nothing searched”.
- Therefore the combined evaluation — planner enabled, full workbook rows,
  teaching applied, correction retained across restart, machine outcome and
  history agreeing — is **not yet passed**. The prior trained-agent result
  remains policy-conditioned recommendations and an O-1010-specific correction
  on supplied records; it does not establish autonomous workbook review.
- This repair is **not deployed**; the pilot is the separate `c912375de`
  release.
