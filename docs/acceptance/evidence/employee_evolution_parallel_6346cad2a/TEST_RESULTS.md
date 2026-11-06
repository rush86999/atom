# Tool-mutation sandbox lineage/freshness repair — test results

Executed source: `6346cad2a` (prior submitted `eaba0cb8f` / tests `e4816e59c`
/ evidence `5dc4f1b0f`). Runtime: scratch SQLite with fresh sessions and a
doubled sandbox. No live code sandbox, model, provider or browser operation.

## Verifier probes

`/private/tmp/test_verifier_evolution_e481_parallel.py` — changed lineage plus
stale-session approved/rejected:

| Version | Result | Log |
|---|---|---|
| Python 3.14 | **3 passed** | `verifier-probes-314.log` |

## Focused gate

Command (same selection on both versions):

```
TESTING=1 PYTHONPATH=$PWD python -B -m pytest -p no:randomly \
  tests/test_evolution_review_tool_mutations.py \
  tests/test_evolution_sandbox_parallel_contract.py \
  tests/test_autodev_review_routes.py \
  tests/test_covpush_w100_gaps_f.py::TestSandboxExecuteMutationGap \
  -q --tb=short
```

| Version | Result | Log |
|---|---|---|
| Python 3.14 | **58 passed** | `focused-314.log` |
| Python 3.11 | **58 passed** | `focused-311.log` |

The 58 are the original 47 decision/route/sandbox-gap controls plus 11 new
parallel-writer controls.

## Affected review/audit selection

```
TESTING=1 PYTHONPATH=$PWD python -B -m pytest -p no:randomly \
  tests/test_evolution_review_tool_mutations.py \
  tests/test_evolution_sandbox_parallel_contract.py \
  tests/test_autodev_review_routes.py \
  tests/test_covpush_w100_gaps_f.py::TestSandboxExecuteMutationGap \
  tests/test_reviewed_improvement_apply.py \
  tests/test_reviewed_improvement_boundaries.py \
  tests/test_reviewed_skill_agent_consumption.py \
  tests/test_memento_candidate_review.py \
  tests/test_audit_logger.py \
  tests/test_covpush_w103_audit_logger.py -q --tb=short
```

| Version | Result | Log |
|---|---|---|
| Python 3.14 | **104 passed** | `affected-review-audit-314.log` |
| Python 3.11 | **104 passed** | `affected-review-audit-311.log` |

## Affected evolution selection

```
TESTING=1 PYTHONPATH=$PWD python -B -m pytest -p no:randomly \
  tests/test_auto_dev \
  tests/test_evolution_sandbox_parallel_contract.py \
  tests/test_agent_evolution_loop.py \
  tests/test_evolution_governance.py \
  tests/test_evolution_pipeline.py \
  tests/test_covpush_w64b_evolution_loop.py \
  tests/test_covpush_w83_evolution.py \
  tests/test_covpush_w104_self_evolution.py \
  tests/test_harness_evolution_api.py -q --tb=short
```

| Version | Result | Log |
|---|---|---|
| Python 3.14 | **304 passed, 29 skipped, 1 baseline failure** | `affected-evolution-314.log` |
| Python 3.11 | **304 passed, 29 skipped, 1 baseline failure** | `affected-evolution-311.log` |

The failure is
`tests/test_auto_dev/test_reflection_engine.py::TestReflectionEnginePatternDetection::test_identifies_repeated_failure_patterns`,
identical at the accepted base (`baseline-evolution-314.log`,
`baseline-evolution-311.log`).

## Parallel-writer controls

| Contract | Control |
|---|---|
| Changed lineage during worker | `test_changed_lineage_during_worker_is_skipped` |
| Unchanged/null lineage twin | `test_unchanged_null_lineage_twin_passes` |
| Changed code during worker | `test_changed_code_during_worker_is_skipped` |
| Changed prior error during worker | `test_changed_prior_error_during_worker_is_skipped` |
| Stale approved/rejected before dispatch | `test_stale_session_reloads_review_before_dispatch` |
| Reviewer during worker wins CAS | `test_reviewer_during_worker_wins_result_cas` |
| Pending/failed valid twins | `test_pending_twin_executes_once_and_passes`, `test_failed_twin_executes_once_and_passes` |
| Missing/foreign target | `test_missing_or_foreign_target_does_not_dispatch` |

## Boundaries

No live sandbox, model, provider, credential, spend, send, download or
deployment operation. No new status/operation/cancellation engine. PostgreSQL
runtime/soak and multi-worker qualification remain open.
