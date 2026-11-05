# Feedback annotation CAS — stale writers cannot erase a committed failure

2026-11-04, America/Toronto.

**Status: the confirmed concurrent-write race is repaired at a frozen source
and requalified at controlled scratch-DB scope.** Business annotations are now
database-enforced compare-and-swap writes. A stale positive or pending
evaluator can no longer overwrite a committed `wrong_evidence_selection`
failure, and a committed failure remains visible to the capability selector.

| Item | Value |
|---|---|
| Repaired source | `6cdc50cc7c6a6434f891adce2f598575092a18cf` |
| Predecessor boundary source | `e4f3733c1` (preserved) |
| Original proof | `employee_business_feedback_2ab959fc0` (preserved) |
| Feedback / interleaving / probe controls | **33 passed** (3.11.16 and 3.14) |
| Verifier-neighborhood regression | **373 passed** (3.11.16 and 3.14) |
| Broad affected regression | **473 passed** (3.11.16 and 3.14) |
| Independent race probes | **2/2 passed** (3.11 and 3.14) |
| Original three boundary probes | **3/3 passed** (3.11 and 3.14) |
| CAS proof | `feedback-cas-proof.json` |

## The confirmed race

The verifier forced a real post-read/pre-write interleaving with separate
sessions:

1. A weak evaluator SELECTs the transport row and pauses.
2. A second session commits `wrong_evidence_selection` (`success=false`,
   `quality_satisfied=false`, verdict rank 5).
3. The weak evaluator resumes and writes from its stale ORM snapshot.

`SELECT FOR UPDATE` has no locking effect on SQLite, and a dirty ORM assignment
updates by primary key. The stale positive writer could replace the failure with
`business_satisfied`; the stale pending writer could replace it with
`business_outcome=unresolved`, which `parse_evidence_rows` skips — hiding the
failure from routing evidence entirely.

## The repair

Business annotations now use a database-enforced CAS, not a row lock and not a
process-local lock.

- Every business annotation carries a monotonic `evaluation_revision` in
  `prompt_features`.
- The conditional `UPDATE` matches on:
  - immutable receipt: `id`, `routing_result_id`, tenant, model;
  - persisted quality fields: `success`, `quality_satisfied`,
    `user_satisfaction`;
  - JSON binding: provider, workspace, profile, profile version;
  - the observed `evaluation_revision`.
- Zero matched rows means a concurrent writer won. The transaction is rolled
  back, the authoritative row is reloaded, binding and verdict precedence are
  rechecked, and a stronger failure may retry within a bounded 3-attempt loop.
  A stale positive or pending writer returns `skipped_verdict`; a changed
  binding returns `refused_*`.
- The CAS is the only business-state write. The loaded ORM object is expired
  before commit so no dirty flush can issue an unconditional primary-key update.
- The routing evidence cache is invalidated only for a committed annotation.
  A conflict/refusal is never reported as `annotated`.
- Legacy fabrication/correction annotation behavior is unchanged.
- SQLite and PostgreSQL predicates are implemented; **only SQLite was
  exercised**. PostgreSQL remains unqualified.

## Finite proof matrix

`feedback-cas-proof.json` records:

| Case | Result |
|---|---|
| Stale positive vs committed failure | weak `skipped_verdict`; final row `failed`, verdict `wrong_evidence_selection`; selector sees 1 semantic failure |
| Stale pending vs committed failure | weak `skipped_verdict`; final row `failed`; selector still sees the failure |
| Stronger failure vs committed positive | positive `annotated`, failure `annotated`; final row failure |
| Duplicate same verdict | first `annotated`, second `skipped_verdict`; incident id stable |
| Changed binding during evaluation | weak `refused_workspace`; binding change preserved; no business outcome written |
| Original three boundary probes | wrong workspace, wrong tenant, child-task receipt all pass |

## Verification

Frozen `git archive 6cdc50cc7 backend` extraction, scratch SQLite and doubled
transport only:

- **33** feedback/interleaving/independent-probe tests passed on Python 3.11.16
  and 3.14.
- **373** verifier-neighborhood tests passed on both versions.
- **473** broad affected tests passed on both versions.
- The verifier's two forced-interleaving probes passed 2/2 on both.
- The original three boundary probes passed 3/3 on both.
- The 3.11 full-probe invocation needs `-p no:randomly` to avoid a
  `pytest_randomly`/thinc seeding error at setup; the probes themselves pass.

Artifacts:

- `feedback-cas-proof.json` — fresh-session interleaving states and selector
  evidence.
- `proof.py` — deterministic reproducer (no live model).
- `focused-311.log`, `focused-314.log` — 33 feedback/interleaving/probe
  controls.
- `affected-311.log`, `affected-314.log` — 373 verifier-neighborhood tests.
- `frozen-affected-311.log`, `frozen-affected-314.log` — 473 broad affected
  tests.
- `interleaving-311.log`, `interleaving-314.log` — 2/2 independent race probes.
- `boundaries-311.log`, `boundaries-314.log` — 3/3 original boundary probes.
- `test_verifier_feedback_interleaving_e4f.py`,
  `test_verifier_feedback_boundaries_2ab.py` — reproduced independent probes.
- `MANIFEST.json` — source/artifact hashes.

## Boundaries

Scratch SQLite and doubled provider transport only. No live model inference,
provider, credential, spend, download or deployment. The predecessor boundary
proof `employee_feedback_boundary_e4f3733c1` and the original
`employee_business_feedback_2ab959fc0` proof are preserved unchanged. PostgreSQL
concurrency is not claimed. General adaptive judgment, served multi-model
comparison, live breadth and soak remain separate limitations. Historical
`111/123`, planner `5/5`, goal router `1/2` and alignment gap `3.0` are
unchanged.
