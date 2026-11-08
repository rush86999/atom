## Follow-up review

Reviewed `FOLLOWUP_3be.diff` plus the relevant follow-up source sections of `FOLLOWUP_3be__backend__core__assignment_executor.py` and `FOLLOWUP_3be__backend__api__assignment_routes.py`. No tests were run.

### Prior findings status

1. **Stale assignment-level `waiting` after clarification-only rejection — addressed.**
   The rejection branch now writes `waiting`/`conflicts` only when `step is not None` (`assignment_executor.py` follow-up diff, rejection hunk). Clarification-only questions keep only the assignment-level receipt, and the new test asserts `not plan.get("waiting")` after both rejection and acceptance.

2. **Wrong-step fallback for a declared binding — addressed for step identity.**
   `_gap_question_binding_valid` (`FOLLOWUP_3be__backend__core__assignment_executor.py:1771-1789`) checks:
   - declared `step_id` equals the actual step id;
   - declared `source_operation` exists, belongs to the same assignment, and points at the actual step.

   It is used in `resolve_gap` before settlement, again inside the CAS `compute`, and in `_compute_gap_external_response` (`4811`-era hunk). The new contradictory-binding test covers both `step_id` and `source_operation` for both answer routes.

3. **Explicit-plan answer opting into model work — addressed for the opt-in gate.**
   `_answer_model_enabled` (`FOLLOWUP_3be__backend__api__assignment_routes.py:1094-1100`) rejects `use_model is False`, and otherwise allows only `started_from == "employee_objective"` or an explicit `use_model is True`. Both answer routes now use it.

   The remaining open-question difference from the recovery seam is not a confirmed defect: `_advance_employee_work` (`1094`-era file, lines `1139-1148`) deliberately allows independent ready operations while an open obligation blocks only its dependent scope. That is an explicit policy in the inspected source, not the prior “no open questions” guard.

4. **Advancing after any non-early gap result — addressed.**
   `resolve_assignment_gap` now returns immediately unless `result.get("status") == "resolved"` before calling `executor.resume` and `_advance_employee_work`.

### Concrete remaining defects / gaps

1. **The CAS recheck fails open when the question disappears.**
   In the new `resolve_gap` `compute` hunk:
   ```python
   fresh_question = next((
       item for item in (record.get("task_revision") or {}).get("unresolved") or []
       if item.get("question_id") == question_id), {})
   if not _gap_question_binding_valid(
           record, assignment, fresh_question,
           _step_for_gap_question(assignment, fresh_question)):
       raise AssignmentError(...)
   ```
   If the question no longer exists, `fresh_question` is `{}`. `_gap_question_binding_valid` sees no declared `step_id`/`source_operation` and returns `True`. The CAS therefore does not fail closed on a vanished question, even though the transition still names `question_id`. Whether `mutate_assignment_and_task` independently rejects a resolution for a missing question was not verified, so the downstream effect is untested, but the binding recheck itself is vacuous in that case.

2. **`source_operation` validation does not require the operation to be the current/live wait.**
   `_gap_question_binding_valid` (`1771-1789`) validates only `assignment_id` and `step_id`. It does not check operation status or whether the declared operation is `_operation_id_for_step(record, step)`. If `_operation_by_id` can return historical operations from the same step, a stale operation from an earlier attempt passes validation. Settlement then uses the step’s current operation (`_operation_id_for_step(record, step)` in `_compute_gap_external_response`), so a reply bound to an old same-step wait could supersede the current wait. The new tests cover a *different* step/operation, not a stale generation on the same step. Whether `_operation_by_id` exposes historical operations was not inspected, so this is a concrete validation gap with an untested trigger.

3. **Binding validation now runs before exact-replay matching.**
   `_compute_gap_external_response` validates the declared binding before the receipt-replay block. `_find_gap_reply_target` intentionally returns settled questions for replay (`1792-1800`), but if the declared step or operation is no longer resolvable after settlement, an exact replay can return `"unmatched"` instead of the idempotent receipt result. This is a concrete ordering change; whether step removal/operation pruning occurs in normal replay paths was not verified.

### Unverified boundaries

- `_operation_by_id` history/current-operation semantics were not inspected.
- `mutate_assignment_and_task` behavior for a missing question was not inspected.
- No runtime/test execution was performed, and no test-pass claim is made.