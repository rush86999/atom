# GOAL-02 focused test results

Corrected source checkpoint: `0839733ceb4ea0f4513b967a1db1bfb46625d760`
Original checkpoint: `e0469141c884bfd37ebd152ade00f1e13b91fe91`
Baseline: `248a2329623b433e68104c4d89d2965683d81013`
Interpreter: `/Users/rushiparikh/projects/atom/backend/venv314/bin/python`

## Review finding (preserved negative)

At original checkpoint `e0469141c`, `GoalService.utility_ranking` ordered
`created_at ASC` and applied `limit(100)`. The independent reviewer probe with
100 older achieved runs plus a newer best run (target minimize
`human_interventions`, older 10 / latest 0, explicit timestamps, same
goal/workspace/constraints-clean) returned the wrong winner because the best
101st row was omitted.

Correction at `0839733ce` removes the hidden candidate cap: every terminal run
for the scoped goal/workspace participates. Ordering is stable input order only.
No pagination was added, so no coverage is hidden.

## Corrected focused run

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
  -q --tb=short --junitxml=.../focused-review2-junit.xml
```

Result: **111 passed, 0 failed, 0 skipped** in 14.17s.

The new file contributes 31 controls; the existing six files contribute the 80
controls that also pass on the baseline.

## New/changed GOAL-02 controls (31)

| Area | Controls |
|---|---|
| Explicit target | 9 malformed/absent definitions rejected before persistence; create persists; clear removes |
| Durability | target + ranking survive fresh engine/service; `Objective` injection |
| Ranking | maximize and minimize ordering; failed/cancelled cannot win |
| **Coverage boundary** | **101 terminal candidates: latest/best wins; invalid 101st included but withheld** |
| Evidence validity | missing, NaN/Inf, numeric string, bool, fractional, negative, `10**400` huge int |
| Gates | explicit `constraints_ok=False` withheld; unknown evidence has no rank |
| Scope | other goals and other workspaces excluded |
| Satisfaction separation | manual criterion stays active while utility winner exists |
| Production consumers | `GoalService.evaluate`; `GoalRunService._evaluate_goal`; `GoalRunRouter._build_prompt` |
| Flag parity | `ATOM_OBJECTIVE_LOOP_ENABLED=false` still returns no loop objective |
| API boundary | supervisor PUT/DELETE, member read, member write 403, malformed 422 |

## Coverage-boundary detail

`test_complete_coverage_beyond_the_old_hundred_run_cap`:

- 100 older achieved runs, `human_interventions=10`, explicit timestamps.
- 101st/latest achieved run, `human_interventions=0`.
- Result: `eligible_count == 101`, ranking length 101, winner
  `run-latest-best`, utility `0.0`.

`test_invalid_latest_candidate_beyond_cap_cannot_win`:

- Same 100 older valid runs.
- 101st/latest achieved run has `human_interventions=-1`.
- Result: complete coverage includes it but it is `metric_unknown`, rank `None`;
  a known completed older run wins; `eligible_count == 100`.

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
The review fix does not touch that path, so the existing baseline results are
reused.

## Evidence type

Controlled deterministic consumer tests. No model/provider call, no live DB, no
cloud/account/credential/send/spend/download/deployment action was performed.
No raw runtime logs are uploaded; only test JUnit and summary text.
