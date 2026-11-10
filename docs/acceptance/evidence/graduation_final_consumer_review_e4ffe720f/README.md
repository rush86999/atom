# Graduation final-consumer independent review — e4ffe720f

Read-only independent review of the graduation candidate
`/private/tmp/atom-web-graduation-reviewed-delivery-20261110` at
`e4ffe720f14d2fdf2b77147c6fc1dfbf1627fcdc` (clean tracked tree). No product or
active graduation-UI source was edited. This packet is review evidence only.

## Scope reviewed

- `f8155821f` promotion exact-replay helper and callers
  (`backend/core/agent_decision_write_service.py`).
- `918e7a17c` SAVEPOINT caller-work ownership semantics
  (`backend/core/database.py`).
- The 121-control root proof `31ub0c6n` (cited source-equal; **not rerun**).
- One fresh broader-consumer run of the existing six-file/training selection
  on the current frozen runtime, through the shared gate and scratch DB.

## 121 proof (not rerun)

`/private/tmp/root-graduation-final-permanent-gate-20261110-31ub0c6n/review.json`:

- `capture_head = f8155821f…`, `actual_exit = 0`, `same_source = true`,
  `121 passed` (73 qualification/assessment/notification + 13 lifecycle +
  8 promotion + 27 CI controls).
- Current `e4ffe720f` hashes for all ten captured files are byte-identical
  (`source/source-hashes.json` → `current_vs_121_source_after.all_same=true`).
- Per authorization this accepted gate was not re-executed.

## Broader-consumer run (fresh, once)

Existing runner `/private/tmp/root-run-graduation-savepoint-consumers-20261110.py`
(its own shared-gate invocation, scratch DB before imports, no browser /
provider / send / live DB):

- Reviewed head: `e4ffe720f`
- Result: **`174 passed, 7 failed`**, `actual_exit=1`, `same_source=true`
- `gates/broader-consumers.log`, `gates/broader-consumers.review.json`

### Failure classification (exact IDs)

Previous broader run at `918e7a17c` (`nr3iizzq`): `163 passed, 11 failed`.

Fixed by the later repairs — all four now pass:

- `tests/test_agent_decision_contract.py::test_promote_transitions_replay_and_stale`
- `tests/test_agent_decision_contract.py::test_confirmed_audit_rollback_reports_effect_none[promote]`
- `tests/test_graduation_exam.py::TestManualPromotion::test_manual_promotion_success`
- `tests/test_graduation_exam.py::TestManualPromotion::test_manual_promotion_creates_history`

Remaining 7 — exact IDs match the previous run and the known training
baseline; no new failure:

- `tests/test_student_training_service.py::TestTrainingProposalCreation::test_create_training_proposal_success`
- `tests/test_student_training_service.py::TestTrainingSessionLifecycle::test_approve_training_success`
- `tests/test_student_training_service.py::TestTrainingSessionLifecycle::test_approve_training_with_modifications`
- `tests/test_student_training_service.py::TestTrainingSessionLifecycle::test_approve_training_proposal_not_found`
- `tests/test_student_training_service.py::TestTrainingSessionLifecycle::test_approve_training_invalid_status`
- `tests/test_student_training_service.py::TestTrainingCompletion::test_complete_training_promotes_to_intern`
- `tests/test_student_training_service.py::TestTrainingCompletion::test_complete_training_confidence_boost`

Mechanisms are the same baseline fixture/authority errors (`Mock` attribute
assert, `TrainingAuthorityError: The current user is not active`, `Mock / Mock`
division). `actual_exit=1` is therefore expected from the baseline; this run is
a classification, **not** a green acceptance gate. `new_failure_ids=[]`.

## Source-bound review conclusions

- **f815**: `_promotion_state_material` adds `last_exam_id` and
  `promotion_count` and is used for prior digest, result material, commit
  target check, and the default promotion replay path
  (`audit_expected["action"] == _ACTION_PROMOTE`). `agent_promoted` is the
  only promotion action. All four previously failing promotion/replay controls
  pass. Bounded observation: `promotion_count` is digest/result-checked but
  not a row-CAS column; no concrete counterexample observed.
- **918**: marker is set on the nested/root transaction at flush, transferred
  to the parent on savepoint release, and cleared only at root end; flush
  subtransactions do not fire `after_commit`. The 13 lifecycle controls pass,
  including the three new implicit-flush / `Session.commit` / `Session.close`
  cases. The conservative `owned` classification remains documented, no
  ordinary false-negative observed.

## Evidence map

- `review/f815-promotion-replay.md`
- `review/918-savepoint-and-121.md`
- `gates/broader-consumers.log` — sanitized full pytest log
- `gates/broader-consumers.review.json` — actual exit, source before/after
- `gates/baseline-classification.json` — exact IDs, fixed vs baseline
- `gates/121-proof.sanitized.json` — cited 121 proof summary (not rerun)
- `source/source-hashes.json` — current vs 121 captured source hashes

## Non-claims

No product/UI edit, browser campaign, model/provider/send/live DB, new deps,
CI change, PR, or merge. The 7 baseline failures are preserved, not
suppressed or relabeled. Root owns final acceptance.

## Successor (not part of this packet)

PR830 hosted frontend failure at the same `e4ffe720f` head
(`components/canvas/__tests__/TrainingPanel.test.tsx`, expected “Review needs
refresh” vs received “State: Status unavailable”) is handled as a separate
bounded repair on a separate branch/worktree from `e4`; this read-only review
does not alter it.
