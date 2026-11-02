# Test results — full-app batch (frozen source `6f697cd9d`)

## Campaign (15 checks)

| # | Check | Expected | Actual | Result |
|---|---|---|---|---|
| 1 | promoted document lesson is explicit and source-bound | proposal 200, promote 200, status promoted | proposal=200, promote=200 | PASS |
| 2 | quote receipt starts an ordinary assignment | run id issued; prepared assignment is waiting, not dispatched | run_id=88bd8bd2-5dd4-465a-94af-85c6f50e3df9, status=waiting | PASS |
| 3 | real backend restart preserves the prepared action | backend PID changes and health returns | backend 57863 -> 58171, frontend 57936 -> 58187 | PASS |
| 4 | prepared action survives restart without dispatch | action-publish still awaiting_approval | action-publish awaiting_approval | PASS |
| 5 | quote assignment completes after action approval | status completed with all four steps | status=completed, steps=['receipt', 'artifact', 'guard-publish', 'action-publish'] | PASS |
| 6 | quote document artifact is attached | deliverable has artifact_path and sha256 | artifact=/private/tmp/atom-full-app/backend/data/acceptance_worlds/full-app-quote-20261102/data/assignments/canvas-b0aa6c22-4c75-49a1-8601-8f6ea4c88056-53616e9c.docx | PASS |
| 7 | quote document contains the server total and provenance | 350.00 and Receipt digest in the DOCX | 37253 bytes; total and Receipt present | PASS |
| 8 | quote document consumes the promoted lesson | Normal style Georgia, 18 pt | font=Georgia, size_pt=18.0 | PASS |
| 9 | declared registered action has readback evidence | step applied and a non-empty remote_id | status=applied, remote_id=e33a850a-a213-481c-8cb8-f31059ea2a07 | PASS |
| 10 | duplicate continuation does not dispatch the action again | approval refused; remote_id unchanged | approve_status=404, before=e33a850a-a213-481c-8cb8-f31059ea2a07, after=e33a850a-a213-481c-8cb8-f31059ea2a07 | PASS |
| 11 | source change produces a new server receipt | rebind 2 rows; line_total 450.00 | row_count=2, aggregates={'line_total': '450.00'} | PASS |
| 12 | old source receipt is refused after the change | 409 stale_revision | status=409, error=stale_revision | PASS |
| 13 | service proposal completes with a document artifact | completed with a deliverable | status=completed | PASS |
| 14 | exception queue completes with a document artifact | completed with a deliverable | status=completed | PASS |
| 15 | cancelled action assignment is terminal | 200 and assignment cancelled | status=200, assignment=cancelled | PASS |

Result: **passed**, 15/15 checks.

## Baseline canvas journey (17 checks)

| # | Check | Result |
|---|---|---|
| 1 | industrial quote created and bound through the UI | PASS |
| 2 | industrial quote derives server total 350.00 USD | PASS |
| 3 | typed receipt starts an ordinary assignment | PASS |
| 4 | industrial quote exposes table view and derive operation | PASS |
| 5 | industrial quote fields and revision survive reload | PASS |
| 6 | service proposal created and bound through the UI | PASS |
| 7 | service proposal derives server total 630.00 CAD | PASS |
| 8 | service proposal derives in CAD through the same panel | PASS |
| 9 | exception queue created with a targeted missing amount | PASS |
| 10 | same queue derivation resumes after the answer | PASS |
| 11 | exception queue counts and groups by status | PASS |
| 12 | exception queue exposes derive and selection, not a sales quote | PASS |
| 13 | exception queue history and fields survive reload | PASS |
| 14 | old answer refuses after source replacement | PASS |
| 15 | replacement source receives a new question | PASS |
| 16 | replacement source completes only through its new question | PASS |
| 17 | no browser page errors | PASS |

Result: **passed**, 17/17 checks.

## Suites

| Suite | Command | Result | Log |
|---|---|---|---|
| Backend affected (16 files) | `pytest <16 files> -q` with `TESTING=1` | **325 passed** | `backend-tests.log` |
| Frontend canvas panels | `jest CanvasCapabilityAssessment CanvasCapabilityDerive CanvasCapabilityRules --runInBand` | **7 passed** | `frontend-tests.log` |
| Reconciliation control | `pytest tests/test_canvas_assignment_integration.py::test_uncertain_effect_reconciles_with_one_provider_draft -q` | **1 passed** | `reconciliation-control.log` |

## Effect count cross-check

- The campaign dispatched `canvas.present_markdown` exactly once; the operation projection reported remote id `e33a850a-a213-481c-8cb8-f31059ea2a07` before and after the duplicate approval attempt.
- The duplicate approval returned `404`, so no continuation path could dispatch again.
- Service (`3bc48625…`, `630.00 CAD`) and exception (`e51ed8ae…`, `3` exceptions / `170.00`) documents were read back from the durable world and independently hashed; both are Georgia 18 pt.
- The reconciliation control created one draft, reported an uncertain outcome, then settled to `applied`; the fake provider still held exactly one draft.
