# Shared business/legacy feedback CAS — one monotonic evaluation per generation

2026-11-04, America/Toronto.

**Status: the shared-writer gap is repaired at a frozen source and requalified
at controlled scratch-DB scope.** Business and legacy grounding/fabrication
annotations now use one database-enforced CAS and one `evaluation_revision`.
Neither writer can erase the other's committed verdict from a stale snapshot.

| Item | Value |
|---|---|
| Repaired source (shared CAS) | `c1cd3bea5` |
| Final executed source | `4e98ec5ab` (test isolation `8b0fb2f0b`; insert-before-cache `4e98ec5ab`) |
| Predecessor CAS source | `6cdc50cc7` (preserved) |
| Original proof | `employee_business_feedback_2ab959fc0` (preserved) |
| Feedback/interleaving/probe controls | **39 passed** (3.11.16 and 3.14) |
| Broad affected regression | **476 passed** (3.11.16 and 3.14) |
| Legacy cross-writer probes | **3/3 passed** (3.11 and 3.14) |
| Original race probes | **2/2 passed** (3.11 and 3.14) |
| Original boundary probes | **3/3 passed** (3.11 and 3.14) |
| Shared-writer proof | `feedback-shared-cas-proof.json` |

## The shared-writer gap

`LLMRoutingFeedback` still had two annotation implementations:

- business writes used the CAS and advanced `evaluation_revision`;
- grounding/fabrication writes used an unconditional ORM update and did not
  advance the revision.

A committed legacy verdict could therefore be erased by a stale business
pending writer when quality fields did not change. Conversely, a legacy writer
that read before a business failure could overwrite the business verdict and
drop its revision. Comparing quality alone cannot detect JSON-only changes.

## The repair

Both writers now use the same CAS primitive.

- A common monotonic `evaluation_revision` is advanced by every annotation.
- The CAS predicate compares the observed snapshot: row id, generation id,
  model, tenant snapshot, `success`, `quality_satisfied`,
  `user_satisfaction`, and the revision.
- Business writes additionally compare their exact employee binding
  (tenant/workspace/provider/profile/version). Legacy grounding/fabrication
  keeps its established generation+model binding and does **not** require
  employee-specific fields.
- Zero matched rows → rollback, reload the authoritative row, recheck binding
  and verdict precedence, and retry only a genuinely stronger judgement within
  a bounded 3-attempt loop.
- A pending business marker skips if the row already carries **any** verdict
  (grounding, fabrication, evidence or business).
- A legacy standalone verdict insert starts revision 1; legacy writes never
  reset or drop a business revision.
- The CAS is the only evaluation-state write; the dirty ORM object is expired,
  and the evidence cache is invalidated only after a committed annotation.
  Standalone-row inserts commit before the cache reset as well.
- `parse_evidence_rows` no longer lets an unresolved business marker hide a row
  that already carries a legacy verdict.

## Order/isolation follow-up

The verifier's broad run exposed one order-sensitive failure: an earlier
schema-settlement control intentionally forced a local connection failure, and
the process-global health monitor opened the circuit breaker for the seeded
local route, leaving a later context-capacity control with an empty pool. The
control now uses a test-local `ProviderHealthMonitor`; the workload-control
fixture also clears BYOK pair memos/cooldowns. The 476-test broad run now
passes on Python 3.11.16 and 3.14 without weakening any production eligibility
gate.

Legacy authorization/binding and verdict semantics are preserved. Transport
measurements and unrelated feature metadata are kept.

## Forced cross-writer proof

`feedback-shared-cas-proof.json` records:

| Case | Result |
|---|---|
| Pending business vs committed `grounding_ok` | weak `skipped_verdict`; final verdict `grounding_ok`; accounting `grounded_ok=1` |
| Pending business vs committed `unsupported_figures` | weak `skipped_verdict`; final verdict `unsupported_figures`; accounting `fabricated=1` |
| Stale legacy `grounding_ok` vs committed business failure | weak `skipped_verdict`; final verdict `wrong_evidence_selection`; selector still sees the semantic failure |
| Original stale positive/pending vs failure | still pass |
| Stronger failure vs positive, duplicate idempotence, changed binding | still pass |
| Original three scope/task-boundary probes | still pass |

## Test isolation

The BYOK handler keeps process-wide pair memos/cooldowns. A broad run could
reach the context-capacity control after another suite benched the seeded local
pair, making the pool look empty. `test_workload_capability_routing.py` now has
an autouse fixture that clears the shared TEST memos/cooldowns before and after
each test. The explicit order check (`test_assignment_routes.py` then the
context-floor control) passes **65/65**. No production eligibility gate or
context assertion was lowered.

## Verification

Frozen `git archive c1cd3bea5 backend` extraction, scratch SQLite and doubled
transport only:

- **39** feedback/interleaving/cross-writer/probe tests passed on Python 3.11.16
  and 3.14.
- **476** broad affected tests passed on both versions.
- The verifier's three legacy cross-writer probes passed 3/3 on both.
- The original 2/2 race probes and 3/3 boundary probes still pass on both.
- The 3.11 full-probe invocation uses `-p no:randomly` to avoid a
  `pytest_randomly`/thinc seeding error at setup; the probes themselves pass.

Artifacts:

- `feedback-shared-cas-proof.json` — fresh-session cross-writer states,
  accounting and selector evidence.
- `proof.py` — deterministic reproducer (no live model).
- `feedback-interleaving-tests-311.log`, `...-314.log` — 39 controls.
- `frozen-affected-311.log`, `...-314.log` — 476 broad affected tests.
- `test_verifier_feedback_legacy_cas_6cdc.py`,
  `test_verifier_feedback_interleaving_e4f.py`,
  `test_verifier_feedback_boundaries_2ab.py` — reproduced independent probes.
- `MANIFEST.json` — source/artifact hashes.

## Boundaries

Scratch SQLite and doubled transport only. No live model inference, provider,
credential, spend, download or deployment. PostgreSQL CAS predicates are
implemented but **not runtime-qualified**. The predecessor CAS/boundary proofs
and the accepted wait-policy lane are preserved unchanged. General adaptive
judgment, served multi-model comparison, live breadth and soak remain separate
limitations. Historical `111/123`, planner `5/5`, goal router `1/2` and
alignment gap `3.0` are unchanged.
