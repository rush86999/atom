## Static review report

Reviewed `PUBLIC_CHANGE.diff`, `PUBLIC_PROVENANCE.json`, and the relevant sections of `backend__core__assignment_executor.py`, `backend__api__assignment_routes.py`, `backend__core__employee_proposal.py`, and `backend__core__employee_adaptation.py`. No tests were run.

### Concrete static findings

1. **Clarification-only rejection leaves a stale assignment-level `waiting` block.**
   `assignment_executor.py:4939-4961` sets `item = new_plan` when `step is None` (clarification-only question), then writes `item["waiting"] = waiting_now` and `item["conflicts"]`. The accepted branch at `assignment_executor.py:4980-5017` never clears that top-level `waiting` field. A rejected reply followed by an accepted reply therefore leaves a stale `waiting` projection on the assignment document. The impact depends on whether another consumer reads `assignment["waiting"]`; that consumer was not in this packet.

2. **The new stale-binding check only covers “no step found,” not “wrong step found.”**
   `assignment_executor.py:4811-4819`:
   ```python
   step = _step_for_gap_question(current, question)
   if step is None and (question.get("source_operation") or question.get("step_id")):
       raise _ExternalReplyStop({"status": "unmatched", ...})
   ```
   If `_step_for_gap_question` returns a step by question/gap identity while the question’s declared `step_id` or `source_operation` names a different or missing step, the reply is accepted. The added test at `test_root_clarification_continuation.py:451-477` only covers the case where no step is found at all, so it does not establish that declared bindings are actually matched. Helper behavior is unverified, but the validation in the diff itself does not compare the returned step against the declared binding.

3. **The new gap-resolution adaptation is not gated like the recovery seam.**
   `assignment_routes.py:2690-2701` calls `_advance_employee_work` whenever `provenance.use_model` is not `False`. It does not require `provenance.started_from == "employee_objective"` and does not check for remaining open questions. Compare `assignment_executor.py:3222-3226` and `3242-3243`, where recovery explicitly restricts itself to employee-objective work and refuses when any unresolved question is open. This means an explicit-plan assignment, or an assignment with other open questions, can now receive model adaptation after resolving one gap. Whether `_advance_employee_work` independently guards these cases was not inspected, so this is a concrete code-path asymmetry with unverified runtime impact.

4. **`resolve_assignment_gap` advances after any non-early result, not only `"resolved"`.**
   `assignment_routes.py:2688-2701` returns early only for `"already_resolved"` and `"rejected_candidates"`. Today `resolve_gap` appears to return only `"resolved"` in the remaining path (`assignment_executor.py:4259-4361`), so this is currently latent, but the new adaptation block is not tied to the `"resolved"` status that the diff is meant to handle.

### Unverified boundaries / hypotheses

- `_step_for_gap_question`, `_reopen_resolved_gap_steps`, `_external_reply_receipts`, `_external_reply_replay_result`, `_find_gap_reply_target`, and `_advance_employee_work` were not inspected; findings 2 and 3 depend on them.
- `canonical_sha256` is introduced at `assignment_executor.py:3268`; its import/definition in that module was not verified. If absent, this is a runtime `NameError`.
- `add_unresolved_questions(..., source_operation=...)` at `test_root_clarification_continuation.py:468` was not verified against the task-lifecycle signature.
- `{**resumed, "adaptive_rounds": rounds}` at `assignment_routes.py:2597` and `2700` assumes `executor.resume()` returns a mapping; the `resume` implementation was not inspected.
- The replay path for clarification-only answers depends on `_find_gap_reply_target` returning resolved questions or on the assignment-level receipt being reachable from the non-gap branch; not verified.

No claim is made that any test passed or that any of the above was reproduced at runtime.