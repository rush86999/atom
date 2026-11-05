# Pending/grounding capability classification — grounding is not business success

2026-11-04, America/Toronto.

**Status: the classification regression is repaired at a frozen source and
requalified at controlled scratch-DB scope.** An unresolved/pending/unknown
business result plus only a positive `grounding_ok`/`grounding_passed` marker is
now unknown to the capability selector — not a satisfactory sample. Real
negative judgements stay observable, and explicit validated/satisfied outcomes
still contribute.

| Item | Value |
|---|---|
| Repaired source | `f091904cee0ba84bfe4bd0d97813b3cb9b65c445` |
| Predecessor shared CAS | `c1cd3bea5` / executed `4e98ec5ab` (preserved) |
| Original proof | `employee_business_feedback_2ab959fc0` (preserved) |
| Classification controls | **7 passed** |
| Feedback/classification/probe controls | **47 passed** (3.11.16 and 3.14) |
| Broad affected regression | **483 passed** (3.11.16 and 3.14) |
| Independent pending-quality probe | **1/1 passed** |
| Classification proof | `classification-proof.json` |

## The regression

The previous parser exception allowed ANY verdict to bypass the
unresolved/pending exclusion. A `grounding_ok` marker then let the general
success predicate use the transport `success`/`quality_satisfied` flags, so an
unresolved employee wait gained `samples=1, successes=1, quality_successes=1`.
Grounding proves evidential support; it is not a useful business decision or a
satisfied objective.

## The repair

`parse_evidence_rows` now distinguishes real negative judgements from positive
grounding markers using the existing verdict categories in
`fabrication_accounting.py`:

- unresolved/pending/unknown business result + **only** `grounding_ok` or
  `grounding_passed` → row is excluded from capability samples (unknown, not a
  negative result);
- unresolved/pending/unknown + fabrication, ignored evidence, business failure
  or unsafe action → row remains observable as a non-success sample and keeps
  its fabrication/business-failure semantics;
- explicit server-validated decision success (`business_outcome=satisfied`,
  `scope=decision`) → contributes;
- genuinely satisfied result (`business_outcome=satisfied`, `scope=result`) →
  contributes;
- legacy rows WITHOUT a business-outcome marker → unchanged compatibility
  behavior.

The durable row is never rewritten or deleted. Grounding/fabrication accounting
still consumes the same row.

## Proof matrix

`classification-proof.json` records each case against the durable row,
capability evidence and fabrication/grounding accounting separately:

| Case | Capability evidence | Accounting |
|---|---|---|
| Pending + `grounding_ok` | samples 0, successes 0 | grounded_ok 1 |
| Pending + `grounding_passed` | samples 0, successes 0 | grounded_ok 1 |
| Pending + `unsupported_figures` | samples 1, successes 0 | fabricated 1 |
| Pending + business failure | samples 1, successes 0, semantic_failures 1 | — |
| Validated wait decision | samples 1, successes 1 | — |
| Satisfied business result | samples 1, successes 1 | — |
| Legacy grounding, no business marker | samples 1, successes 1 | grounded_ok 1 |

## Verification

Frozen `git archive f091904ce backend` extraction, scratch SQLite and doubled
transport only:

- **7** classification controls passed.
- **47** feedback/classification/interleaving/probe controls passed on Python
  3.11.16 and 3.14.
- **483** broad affected tests passed on both versions.
- The independent pending-quality probe passed 1/1.
- The 3.11 full-probe invocation uses `-p no:randomly` to avoid a
  `pytest_randomly`/thinc seeding error at setup; the probes themselves pass.

Artifacts:

- `classification-proof.json` — per-case durable row, capability evidence and
  accounting.
- `proof.py` — deterministic reproducer (no live model).
- `classification-tests.log` — 7 classification controls.
- `focused-311.log`, `focused-314.log` — 47 controls.
- `broad-311.log`, `broad-314.log` — 483 broad affected tests.
- `verifier-probe.log` — independent pending-quality probe.
- `test_verifier_pending_grounding_quality_4e98.py` — reproduced probe.
- `MANIFEST.json` — source/artifact hashes.

## Boundaries

Scratch SQLite and doubled transport only. No live model inference, provider,
credential, spend, download or deployment. PostgreSQL runtime qualification is
not claimed. The shared-CAS acceptance, predecessor proofs and the accepted
wait-policy lane are preserved. Capable Flash remains first-class; this is
classification integrity, not a reason to prefer a larger or more expensive
model. Historical `111/123`, planner `5/5`, goal router `1/2` and alignment gap
`3.0` are unchanged.
