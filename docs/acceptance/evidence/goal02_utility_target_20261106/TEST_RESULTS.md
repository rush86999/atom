# GOAL-02 focused test results

Source checkpoint: `e0469141c884bfd37ebd152ade00f1e13b91fe91`
Baseline: `248a2329623b433e68104c4d89d2965683d81013`
Interpreter: `/Users/rushiparikh/projects/atom/backend/venv314/bin/python`

## Focused changed-source run

Command (from `backend/`):

```bash
python -m pytest \
  tests/test_goal_utility_target.py \
  tests/test_goal_run_service.py \
  tests/test_goal_journey_gaps.py \
  tests/test_goal_run_routes.py \
  tests/core/test_agent_objective.py \
  tests/core/test_agent_environment_harness.py \
  tests/test_goal_run_loop.py \
  -q --tb=short --junitxml=.../focused-junit.xml
```

Result: **109 passed, 0 failed, 0 skipped** in 13.84s.

The new file contributes 29 controls; the existing six files contribute the 80
controls that also pass on the baseline.

## New GOAL-02 controls (29)

| Area | Controls |
|---|---|
| Explicit target | 9 malformed/absent definitions rejected before persistence; create persists; clear removes |
| Durability | target + ranking survive fresh engine/service; `Objective` injection |
| Ranking | maximize and minimize ordering; failed/cancelled cannot win |
| Evidence validity | missing, NaN/Inf, numeric string, bool, fractional, negative, `10**400` huge int |
| Gates | explicit `constraints_ok=False` withheld; unknown evidence has no rank |
| Scope | other goals and other workspaces excluded |
| Satisfaction separation | manual criterion stays active while utility winner exists |
| Production consumers | `GoalService.evaluate`; `GoalRunService._evaluate_goal`; `GoalRunRouter._build_prompt` |
| Flag parity | `ATOM_OBJECTIVE_LOOP_ENABLED=false` still returns no loop objective |
| API boundary | supervisor PUT/DELETE, member read, member write 403, malformed 422 |

## Baseline comparison for unrelated failures

`tests/test_objective_evidence_flow.py` does not import any changed module.

| Tree | Result | JUnit |
|---|---|---|
| Changed source `e0469141c` | 12 failed, 41 passed | `changed-objective-evidence-junit.xml` |
| Baseline `248a23296` | 12 failed, 41 passed | `baseline-objective-evidence-junit.xml` |

Both trees fail the same 12 pre-existing canvas/orchestrator nodes:

- `test_orchestrator_persists_comparison_as_task_outcome`
- `test_authorized_source_backed_edit_is_read_back_verified`
- `test_mail_evidence_lookup_builds_a_structured_edit_contract`
- `test_evidence_postcondition_rejects_currency_and_basis_mismatch`
- `test_postcondition_rejects_a_different_qualified_price_column`
- `test_duplicate_target_rows_do_not_satisfy_a_postcondition`
- `test_failed_readback_is_not_reported_as_a_successful_update`
- `test_missing_expected_postcondition_blocks_write`
- `test_task_outcome_records_verified_canvas_mutation`
- `test_outcome_builder_accepts_task_defined_review_schema`
- `test_outcome_builder_rejects_refusal_for_task_defined_review`
- `test_outcome_builder_keeps_order_review_as_a_regression`

These are recorded as unrelated baseline failures, not GOAL-02 regressions.

## Evidence type

Controlled deterministic consumer tests. No model/provider call, no live DB, no
cloud/account/credential/send/spend/download/deployment action was performed.
