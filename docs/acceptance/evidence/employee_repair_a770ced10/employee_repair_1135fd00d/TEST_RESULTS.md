# Employee repair successor — results

Executed source: `1135fd00d` (clean worktree at the integrated run).

## Verified-receipt execution controls

`focused-affected.log` — **209 passed**. The new execution-level matrix:

| Source proof | Dependent action | Observed |
|---|---|---|
| absent verification | not called | `verified_proof_missing`; independent branch applied |
| verification conflict | not called | `verified_proof_refuted` |
| verified with missing field | not called | `verified_proof_missing_fields` |
| verified with truncated coverage | not called | `verified_coverage_truncated` |
| complete explicit verification | called | dependent applied; assignment completed |

These run the real `AssignmentExecutor`, not only the pure readiness predicate.
The durable step result now carries `verification`/`coverage`; readiness also
falls back to the operation receipt's `remote_identity.verification` and
`source.coverage` for restarted/legacy results.

## Other matrices

| Log | Result |
|---|---|
| `backend-integrated.log` | **557 passed** |
| `frontend-integrated.log` | **54 passed** |
| `patch-invariants.log` | **8 passed** |
| `two-domain-campaign.log` | **4 passed** |
| `evidence-contract-probes.log` | **9 passed** |
| `corrected-patch-invariant-probe.log` | **3 passed** |

Patch invariants cover transitive uncertain descendants, fact/teaching/
authority advances without plan revision, concurrent duplicate adoption,
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
