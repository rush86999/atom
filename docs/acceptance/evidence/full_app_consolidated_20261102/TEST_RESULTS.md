# Consolidated test results

## Normal-app journey (17 checks)

| # | Check | Expected | Actual | Result |
|---|---|---|---|---|
| 1 | promoted document lesson is explicit and source-bound | proposal 200, promote 200, status promoted | proposal=200, promote=200 | PASS |
| 2 | quote receipt starts an ordinary assignment | run id; prepared assignment waiting | run_id=122a8387-56b3-4e94-9324-1830a313d175, status=waiting | PASS |
| 3 | real backend restart preserves the prepared action | backend PID changes and health returns | backend 78405 -> 79036; frontend 78465 -> 79056 | PASS |
| 4 | prepared action survives restart without dispatch | same operation id + payload digest; still awaiting approval; remote null | op=442a74d6-2dfe-4bf5-a4bf-b2ad740f4987; payload=5c44a7f4af94e2189ee1df667f7d5b35f24dc9a6f2e6d1f73d1b03df2628ea2a; identical=True | PASS |
| 5 | quote assignment completes after action approval | completed with receipt, artifact, guard and action steps | status=completed; steps=['receipt', 'artifact', 'guard-publish', 'action-publish'] | PASS |
| 6 | quote document artifact is attached | deliverable with path and sha256 | artifact=/private/tmp/atom-consolidated-clean/backend/data/acceptance_worlds/full-app-consolidated-20261102/data/assignments/canvas-3c65d2b0-788e-48c7-80cb-c9842829c537-e3f7ea6d.docx | PASS |
| 7 | quote document contains the server total and provenance | 350.00 and Receipt digest | 37252 bytes; total+Receipt | PASS |
| 8 | quote document consumes the promoted lesson | Normal style Georgia 18 | font=Georgia, size=18.0 | PASS |
| 9 | declared registered action has readback evidence | applied with non-empty remote id | remote_id=0c327289-abca-4182-ae4c-1e6838d9e019 | PASS |
| 10 | duplicate continuation does not dispatch the action again | refused; same remote id; audit count 1 -> 1 | approve=404; audit 1 -> 1; remote same=True | PASS |
| 11 | source change produces a new server receipt | rebind 2 rows; line_total 450.00 | rows=2; aggregates={'line_total': '450.00'} | PASS |
| 12 | old source receipt is refused after the change | 409 stale_revision | status=409; error=stale_revision | PASS |
| 13 | service proposal completes with a document artifact | completed with deliverable | status=completed | PASS |
| 14 | service document carries the CAD total and lesson | 630.00 CAD, Receipt, Georgia 18 | 37248 bytes; font=Georgia 18.0 | PASS |
| 15 | exception queue completes with a document artifact | completed with deliverable | status=completed | PASS |
| 16 | exception document carries the counts and lesson | exception_id 3, amount 170.00, Receipt, Georgia 18 | 37233 bytes; font=Georgia 18.0 | PASS |
| 17 | cancelled action assignment is terminal | 200 and cancelled | status=200; cancelled | PASS |

Result: **passed**, 17/17 checks.

## Suites

| Suite | Command | Result | Log |
|---|---|---|---|
| Backend combined matrix (24 files) | `TESTING=1 pytest <24 files> -q` | **428 passed** | `backend-tests.log` |
| Frontend canvas panels | `jest CanvasCapabilityAssessment CanvasCapabilityDerive CanvasCapabilityRules --runInBand` | **7 passed** | `frontend-tests.log` |

## Effect counts

- `canvas.present_markdown` remote id: `0c327289-abca-4182-ae4c-1e6838d9e019`; `canvas_audit` rows: **1 before duplicate, 1 after**; duplicate approval `404`.
- Pending action `442a74d6-2dfe-4bf5-a4bf-b2ad740f4987`, payload `5c44a7f4…`, status `awaiting_approval`, `remote_id=null` before and after restart.
- Documents: quote `bb80c677…` (350.00), service `dadc880f…` (630.00 CAD), exception `b873c87e…` (3 / 170.00); all Georgia 18.
- Oracle registry union: 9 verifiers (6 connected, tasks.create, trigger_workflow, canvas.present_markdown).
