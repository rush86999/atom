# Support statement — release candidate `ae0c2fda3`

**Status:** candidate-bound support statement; **not deployed**. Three
authorized attempts were executed. The third reached the product smoke and
failed functional checks; automatic code rollback restored the pilot.
**Candidate source:** `ae0c2fda3` (includes spreadsheet `e14d3efdd` and
trained-review fixes through `ae0c2fda3`).
**Pilot:** `c912375de`, PID `19046`, healthy after automatic rollback.
**Served acceptance base:** `c0c0d2e87` for the four review checks; combined
served smoke on the candidate source `ae0c2fda3`.

## What is supported

For the tested candidate/configuration, the candidate supports:

- **Spreadsheet totals and gaps.** Served scratch smoke: PO Register approved
  rows → CAD **8050.00** (3 rows, qty 10) and USD **3999.96** (1 row, qty 4);
  Adjustments approved rows → known subtotal **−700.00 CAD**, gap **0055** at
  **C5**, complete/grand total withheld. Source hashes unchanged.
- **Taught policy review with a scoped correction.** O-1010 → **Process**
  before correction; **Escalate** after correction, citing **M. Chen /
  2026-10-25**; **Escalate** with the same directive after a real restart;
  O-1001 remains **Process**.
- **Evidence-bound decisions.** Reviews are certified from a structured
  `review_result` block bound to the requested subject, source identity,
  retrieval operation, current decision execution and task policy. Raw fenced
  machine blocks are hidden; the validated block is rendered.
- **Matching machine outcome and history.** Response outcome, persisted
  task outcome and assistant history agree on the tested turns.
- **Zero unintended writes.** Canvas audit is setup-only (`create`,
  `agent_attached`, `data_loaded`); `task_operation_records=0`; `tasks=0`; no
  outbound/send/edit/approve.
- **Planner-enabled retrieval without supplied rows** for the tested review
  asks.

## Visible limitations

- **Confirmation-path qualification.** The four review checks and the combined
  smoke completed through pending task → short confirmation → review. This
  does **not** establish first-request completion or recovery-after-timeout
  completion.
- **Five-order latency** still reaches the product's fixed turn budget
  (`budget=95.0s`); the broader five-order campaign remains backlog.
- **Unknown-header confirmation UX / required-input filters** remain the
  disclosed spreadsheet limitation. Filter-language expansion was not combined
  with role correction.
- **General policy transfer** beyond the tested order and vendor-risk controls
  is not claimed.
- **Judgment quality** is bounded by the tested teaching/records; the
  mechanism is domain-independent, but the tested behavior is not a universal
  capability claim.
- **Decision-turn vs read provenance.** `review_result.execution_id` is the
  decision/delivery turn; the read's provenance rides
  `source_execution_ids`/`resumed_read`. Saved/recovered reads can be reviewed;
  this is not a claim that every review read the file in the same execution.
- **Successful-path smoke only.** The served smoke exercises successful
  reviews. The failure-path envelope (uncertified review → failed) and the
  post-generation message-replacement invalidation are covered by focused
  local controls, not by a served failure smoke.
- **Scratch evidence.** The existing product smoke is scratch-world evidence,
  not a pilot/deployment soak.
- **Live gate failed on the third attempt after product turns.** Setup passed
  and PO totals passed; Adjustments content passed but its confirmed turn was
  `outcome_unconfirmed`; O-1010/O-1001 review turns returned
  `turn_budget_exceeded` or `turn_failed_no_result` with no structured review;
  the repeated O-1001 returned a deterministic read without a structured
  review. Automatic code rollback was healthy. This is candidate-bound live
  smoke evidence; no broad product claim is made. No fourth attempt has run.
- **Smoke data persists.** The live gate creates a named agent/canvas and
  uniquely named workbook uploads; rollback preserves them rather than erasing
  post-cutover work.
- **No automatic DB restore.** Code rollback keeps the database. Restore is
  manual only for demonstrated corruption, after preserving the post-cutover
  DB/WAL/SHM.
- **Exit guard added after failure.** Unexpected exits after pilot shutdown now
  invoke rollback; pre-shutdown failures do not restart the pilot; committed
  attempts do not roll back. Fake-release guard tests pass; no second live
  attempt has run.
- **Confirmation helper parity.** Both confirmation paths now send exactly
  `go ahead` in the original session; the branch test passes against the
  development and packaged helpers and the frozen candidate classifier. This
  is a harness correction, not a product change.
- **Candidate not deployed.** Pilot remains `c912375de`.

## Explicit non-claims

- No claim of five-order latency resolution.
- No claim of general policy transfer.
- No claim that the earlier supplied-row behavioral result was autonomous
  workbook retrieval.
- No deployment approval by this statement. The one authorized reversible
  attempt failed before product smoke and was manually recovered; a second
  attempt requires new authorization.
