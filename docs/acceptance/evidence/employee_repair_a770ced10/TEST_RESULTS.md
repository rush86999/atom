# Employee repair — results

Executed source: `a770ced10` (clean worktree at the integrated run).

## Execution-level evidence controls

`focused-affected.log` — **211 passed**. The receipt and Sent Items controls run
the real `AssignmentExecutor`:

| Control | Observed |
|---|---|
| absent verified proof | dependent not called; `verified_proof_missing` |
| conflict/refuted proof | dependent not called; `verified_proof_refuted` |
| verified with missing field | dependent not called; `verified_proof_missing_fields` |
| verified with truncated coverage | dependent not called; `verified_coverage_truncated` |
| complete explicit proof | dependent called; assignment completed |
| provider acceptance only | provider_accepted true; Sent Items unresolved; not completed |
| matching explicit Sent Items readback | Sent Items true; assignment completed |
| mismatched readback (pure outcome control) | Sent Items false |

Durable step results now retain `verification`, `coverage` and `readback`;
readiness also falls back to the operation receipt for restarted results.

## Other matrices

| Log | Result |
|---|---|
| `backend-integrated.log` | **559 passed** |
| `frontend-integrated.log` | **54 passed** |
| `patch-invariants.log` | **8 passed** |
| `two-domain-campaign.log` | **4 passed** |
| `evidence-contract-probes.log` | **9 passed** |
| `corrected-patch-invariant-probe.log` | **3 passed** |

Patch invariants cover transitive uncertain descendants, fact/teaching/
authority state advances without plan revision, concurrent duplicate adoption,
changed-content conflict, restart replay, requirement weakening, unproven
facts, mutation relabelling and forced-CAS callback purity.

The two-domain campaign covers the industrial quote (494.75 feasible; 5-day
limit infeasible) and the procurement corrected 270.00 bill (closed-period
negative).

## Pre-existing failures

`pre-existing-task-lifecycle-at-source.log` records the same four
`test_task_lifecycle.py` failures as the parent/base. They are disclosed, not
counted.

## Boundaries

Deterministic level only. Served-model adaptive choice and ordinary-product
two-domain journey remain unrun. No model inference or live provider action;
historical denominators unchanged.
