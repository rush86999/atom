# Employee G5 final integration — 2026-11-04

This index ties the final batch together. Product code has not changed since
`62fa207647`; the later commits are evidence only. Each evidence bundle below
is self-contained and binds its source hashes to the exact ref it executed.

## Accepted in this batch

| Behavior | Evidence | Result |
|---|---|---|
| Employee decides the work from an authorized source and the requested DOCX output | `employee_g5_ui_requested_artifact_c7a265c37/` | 22/22 checks; quote **370.00 USD**, artifact `a6b8fffd...` |
| Same job, real revised workbook version (A 100→120, B 50→55) | `employee_g5_integrated_change_62fa207647/` | 18/18 checks; model chose `quote_calculation` again, quote **425.00 USD**, prior quote/artifact and unrelated note retained |
| Cancellation / late-response / controlled lost-confirmation regression on the integrated source | `employee_g5_regression_b4c29e2b6d9e/` | remaining **18/18**, uncertainty **11/11**, clean serving identity |

### Model-attributable choices

- Phase 1: the served local model (`llama3.1:8b`, `source=model`,
  `technical_fallback=false`) chose `quote_calculation`; the compiler derived
  line rows from the read workbook and the artifact rendered from the verified
  receipt.
- Phase 2: after the revised version arrived, the model chose
  `quote_calculation` again and bound `source_step_id=source-3` (the new
  version) in its raw parsed request. The compiler added new steps under a new
  plan revision; the previous quote (`370.00`, same operation id) and the
  unrelated note read (`source-2`, same operation id and result) were
  untouched.
- Deterministic mechanics (step ids, dependencies, receipt verification,
  artifact rendering, supersession handling) are labelled as such and are not
  presented as model decisions.

## Checks performed across the batch

- 370 focused backend tests passed, including the new evidence-change and
  evidence-reassessment controls, proof binding, patch invariants, two-domain
  quote/procurement and negative-twin qualification coverage.
- The two artifact DOCX files were downloaded through the UI and API; UI and
  API bytes are identical and match the recorded SHA-256.
- The current changed document contains `425.00` and no longer prints the
  superseded `370.00`; the old value remains in durable history.
- Evidence checkers: artifact bundle 19/19, integrated change 22/22,
  regression 14/14 (`verify_evidence_from_git.py`).

## Bounded gaps kept open

- **Independent useful work during a durable wait** is still only demonstrated
  by the previously accepted deterministic branch mechanics. The current
  employee contract exposes evidence reads and typed business work, not a
  model-created wait; the regression bundle therefore does not claim that
  behavior as adaptive. Full G5 remains open.
- Artifact presentation is an internal report-style DOCX, not polished
  customer-quote design; the guided/manual artifact path remains separate.
- No live/cloud provider, credential, consent, send, spend or deployment
  authority was used. Historical `111/123`, planner `5/5`, goal router `1/2`
  and alignment gap `3.0` are unchanged.
