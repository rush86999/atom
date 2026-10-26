# Independent review — propagation delta, candidate `ae0c2fda3`

**Reviewed delta:** `c0c0d2e87` (validated review propagation) and the
release-hardening follow-up in `ae0c2fda3`.
**Verdict on the reviewed delta:** the happy-path propagation was correct, but
the delta was **not release-safe** under the broad "fail-closed / response,
persistence and history agree" claim. The reviewer identified one blocker and
two high findings, plus medium/low hardening items.

## Findings and resolution

| ID | Finding | Resolution in `ae0c2fda3` |
|---|---|---|
| F1 | An uncertified required review could still ship `success=true` with a non-failed/`completed` outcome while the task outcome said `objective_met=false`. | `align_review_failure` forces envelope `success=false`, `outcome=failed`, records a failed `_recorded_outcome`, and `_finish_chat_execution` aligns the execution status. Local control added. |
| F2 | Current-execution binding was nominal; a prior/recovered read could be certified without preserving provenance. | Evidence carries `source_execution_id`; review results expose `source_execution_ids` and `resumed_read`; precomputed results must match the current decision execution and contract. The claim is decision-turn binding, with read provenance explicit. |
| F3 | A certified review could survive a post-generation message replacement by an honesty gate. | If the rendered validated block is no longer in the delivered text, the review fields are invalidated before response/outcome construction. Local control added. |
| F4 | Generation and outcome could use different structured sources; metadata could say ok while persistence lacked the review. | The precomputed result is accepted only when execution, subjects, allowed decisions and schema match; otherwise the turn fails closed. |
| F5 | A malformed precomputed dict could be trusted on truthiness. | Requires `ok is True`, `review-result-2`, current execution, exact subjects and allowed decisions. |
| F6 | The raw fenced block leaked when validation failed. | The block is stripped unconditionally; the validated block is rendered only when `ok`. |
| F7 | Uncertified assessments were exposed in metadata. | `assessments` is empty when `ok=false`; candidates move to a diagnostic key. |
| Config | Root `.env.example` used `true` while code checks `== "1"`. | Changed to `1`. |

## Remaining reviewer limits

- The served smoke exercises successful reviews. The F1 failure envelope and
  F3 post-generation invalidation are covered by focused local controls, not a
  served failure smoke.
- Five-order latency and general policy transfer remain outside this review.
- F2 is resolved by explicitly defining decision-turn binding and preserving
  read provenance, not by claiming every decision read the file in the same
  execution.

## Verification after fixes

- Focused suite: **602 passed, 23 failed, 2 xfailed** vs frozen baseline
  **557 / 23 / 2**; the same named pre-existing failures.
- Combined served smoke on `ae0c2fda3`: `checks_all_true=true` for spreadsheet
  totals/gaps and the taught review/correction/restart/positive-twin path.
