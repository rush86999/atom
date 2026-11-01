# 12-goal reconciliation — merged candidate 2026-10-31

**Candidate:** merged README + employee-execution fixes, accepted product
source `a49b854ce660` (evidence head `d3e8ba961`; guided rule authoring in
`bc164fb96632`; accepted product source `b7ee7ee22`). The post-repair journey
and 24-sheet evidence executed on `31ba9725e02a`; the unforced teaching and
guided-rule smokes on `bc164fb96632`; both authorized live qualifications
executed on `0aa6105e4872` and verified after restart at `74464af69f98`.
Configuration: isolated local world, `core` profile, single worker, controlled
outbox; one authorized live read-only source and one authorized live send.

Evidence classes:

- **current-browser** — exercised through the normal product UI in this round;
- **current-tests** — focused tests on this candidate;
- **controlled** — controlled outbox / bounded local provider;
- **historical** — preserved but source-bound to an earlier candidate;
- **external** — requires owner credentials/authorization or a different host.

| # | Goal | Status on this candidate | Evidence class | Remaining gap |
|---|---|---|---|---|
| 1 | Create/select employee, teach, work in a different domain | passed: post-repair normal-app journey on clean `31ba9725e02a` (teach, conflict, qualification, upload, mapping, wait, real backend restart, resume, DOCX 550.00 Arial 11; revised dataset 500.00 Calibri 14) | current-browser | arbitrary domains/schemas not claimed |
| 2 | Teach method/context/qualification/effective period/conflict/format/protocol/correction | passed: all taught through Training; conflict and missing qualification refused, expired lesson excluded, revised lesson applied only to new work; unforced teaching smoke on the stock build 9/9 (no force/DOM shortcut, lesson survived reload) | current-browser + current-tests | arbitrary prose not deterministic |
| 3 | Resolve unfamiliar columns/units; correct mapping; resume | passed: `Price → Gross Amount`, `Price → Net Amount`; mapping gap resolved; same run resumed after restart | current-browser + current-tests | arbitrary schemas not claimed |
| 4 | Upload/connect authorized data and retrieve | **live Microsoft read-only passed**: normal resolver, `/me` identity `rish@brennan.ca`, genuine Outlook workbook attachment, 8/8 rows/216700, product materialization, assignment retrieval, restart/reopen; normal product `email_ingest_message` API also refreshed the connector catalog and returned 216700.00 (`part-a-connector/`); local upload and 24-sheet evidence remain | current-browser (live + local) | declared attachment only; no write/other-connector claim |
| 5 | Large/multi-sheet workbooks and formulas | passed: 24-sheet workbook (500 data rows, 547 catalog rows, leading-zero IDs, blanks); 25-row assignment retrieval 1725.00 without supplied rows; `B2 2→5` recalculated `D2=55`, `Summary!B2=1758`, `B22=34533`; export byte-identical; restart/reopen shows 24 sheets and persisted values (`employee-execution-large-workbook/`) | current-browser | arbitrary Excel functions/macros/charts not claimed |
| 6 | Create canvas, bind data, calculate, edit, export, reload | passed: normal-app canvas 290 → edit 110 → 325, XLSX export, `revision 2 · 4 rows` | current-browser | arbitrary controls/formulas not claimed |
| 7 | Grounded selection/calculation and substantive assessment | calculations current; **deterministic rules qualified** (18/18 V1, 19/19 V3, safe abstention); deterministic rule authoring exercised through the normal canvas capability panel (`employee-execution-deterministic-rule-authoring/`) and the **guided editor** (selects/inputs, no JSON, server-validated, 13/13; `employee-execution-guided-rule-authoring/`); model-dependent judgment **failed** | current-tests + current-browser | model judgment unqualified; deterministic only for rule-expressible policies |
| 8 | Editable DOCX/PPTX and email draft | DOCX passed; controlled outbox one line; PPTX prior renderer evidence; one authorized real send provider-accepted with exact Sent Items (`live_qualification_20261101/part-b/`) | current-browser + controlled + live | recipient inbox delivery not claimed; PPTX visual/chart not claimed |
| 9 | User-created canvases inherit supported capabilities | passed: guided manifest authoring in the normal panel (field mapping, editable fields, ordered rules), CSV bind, deterministic assess, exact-content approval, decisions/export; plus the earlier manifest install/edit/reload run | current-browser | table adapter only |
| 10 | Long-running multi-source, missing info, browser close, restart, delayed response, changed teaching, cancellation, uncertainty | passed: wait → close → backend PID change → same run resumed → correlated response; teaching revision stayed pinned; revised lesson applied to new work; prior boundaries/reconciliation tests pass | current-browser + current-tests | one worker; no multi-day soak; real credential expiry untested |
| 11 | Approval binds exact payload/artifact; duplicate approval no duplicate transport | accepted atomic binding; controlled outbox once; one-use live grant exhausted 1/1, provider accepted, exactly one Sent Items row, restart terminal/no second effect (`live_qualification_20261101/part-b/`) | current-tests + controlled + live | recipient delivery, second recipient and other payloads unclaimed |
| 12 | Install/start/sign in/use workspace/restart/recover | passed: normal app launch, admin login, post-repair journey on clean source, real backend restart, same run recovered, large-workbook canvas reopened after restart | current-browser | hosted deployment/public release deferred |

## External and controlled boundaries
1. **Live Microsoft read-only ingestion** (goal 4) — **executed on the current
   candidate** for one genuine Outlook workbook attachment
   (`live_qualification_20261101/part-a/`); no write, other connector or
   general Microsoft claim.
2. **Real Outlook send** (goals 8/11) — **executed once** under a one-use grant
   with exact body binding, provider acceptance and exactly one reconciled
   Sent Items row (`live_qualification_20261101/part-b/`). Recipient inbox
   **delivery** remains unclaimed and separate.
3. **Model-dependent substantive judgment** (goal 7) — the local
   `llama3.1:8b` configuration failed. Deterministic taught rules are
   qualified and are the usable configuration for rule-expressible policies;
   model judgment remains unqualified.
4. **Multi-worker/soak, KVM/Firecracker, live-provider breadth, hosted
   deployment** — outside this candidate's tested scope or owner-deferred.

## Unblocked engineering still available

- broader Office/workbook fixtures beyond the executed 24-sheet workbook can be
  added and run locally;
- the merged README claim matrix can be re-run on this exact candidate, but
  that is a separate breadth milestone, not this goal reconciliation.

## Live qualifications

- **Part A — accepted** on `0aa6105e4872` (connector entry point
  `a49b854ce660`): read-only Microsoft account
  `rish@brennan.ca`, genuine Outlook workbook attachment, 8/8 rows, independent
  sum `216700`, product materialization and assignment retrieval; restart
  reopened the result. Evidence: `live_qualification_20261101/part-a/`.
- **Part B — accepted once** on `0aa6105e4872`: one-use grant exhausted 1/1,
  exact body binding, provider accepted, exactly one Sent Items row, restart
  terminal/no second effect. Recipient inbox delivery is **not claimed**.
  Evidence: `live_qualification_20261101/part-b/`.

Independently accepted within the documented scope on 2026-11-01
(`FINAL_ACCEPTANCE_2026-11-01.md`). The default runtime remains
controlled-transport and does not send without an explicit new grant.
