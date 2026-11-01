# 12-goal reconciliation — merged candidate 2026-10-31

**Candidate:** merged README + employee-execution fixes, current product source
`bc164fb96632` (product code `589389218`; guided rule authoring added in
`bc164fb96632`; accepted product source `b7ee7ee22`). The post-repair journey
and 24-sheet evidence executed on `31ba9725e02a`; the unforced teaching and
guided-rule smokes executed on `bc164fb96632`. Configuration: isolated local
world, `core` profile, single worker, controlled outbox, no live
provider/send.

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
| 4 | Upload/connect authorized data and retrieve | local path passed: CSV upload via Data and source picker in the post-repair journey; 24-sheet workbook uploaded through Data and exposed as 24 assignment sources (547 rows); live Microsoft reads are historical only | current-browser (local); **historical** (live Microsoft) | **External Part A**: read-only Microsoft account/workbook/attachment |
| 5 | Large/multi-sheet workbooks and formulas | passed: 24-sheet workbook (500 data rows, 547 catalog rows, leading-zero IDs, blanks); 25-row assignment retrieval 1725.00 without supplied rows; `B2 2→5` recalculated `D2=55`, `Summary!B2=1758`, `B22=34533`; export byte-identical; restart/reopen shows 24 sheets and persisted values (`employee-execution-large-workbook/`) | current-browser | arbitrary Excel functions/macros/charts not claimed |
| 6 | Create canvas, bind data, calculate, edit, export, reload | passed: normal-app canvas 290 → edit 110 → 325, XLSX export, `revision 2 · 4 rows` | current-browser | arbitrary controls/formulas not claimed |
| 7 | Grounded selection/calculation and substantive assessment | calculations current; **deterministic rules qualified** (18/18 V1, 19/19 V3, safe abstention); deterministic rule authoring exercised through the normal canvas capability panel (`employee-execution-deterministic-rule-authoring/`) and the **guided editor** (selects/inputs, no JSON, server-validated, 13/13; `employee-execution-guided-rule-authoring/`); model-dependent judgment **failed** | current-tests + current-browser | model judgment unqualified; deterministic only for rule-expressible policies |
| 8 | Editable DOCX/PPTX and email draft | DOCX passed (Arial 11 active, Calibri 14 revised); controlled outbox one line with greeting/signature/prefix; PPTX evidence from prior candidate remains current-tests for renderer | current-browser + controlled | real delivery not performed; PPTX visual/chart not claimed |
| 9 | User-created canvases inherit supported capabilities | passed: guided manifest authoring in the normal panel (field mapping, editable fields, ordered rules), CSV bind, deterministic assess, exact-content approval, decisions/export; plus the earlier manifest install/edit/reload run | current-browser | table adapter only |
| 10 | Long-running multi-source, missing info, browser close, restart, delayed response, changed teaching, cancellation, uncertainty | passed: wait → close → backend PID change → same run resumed → correlated response; teaching revision stayed pinned; revised lesson applied to new work; prior boundaries/reconciliation tests pass | current-browser + current-tests | one worker; no multi-day soak; real credential expiry untested |
| 11 | Approval binds exact payload/artifact; duplicate approval no duplicate transport | accepted atomic-binding evidence; controlled outbox once; duplicate/drift controls | current-tests + controlled | real send not performed (Part B) |
| 12 | Install/start/sign in/use workspace/restart/recover | passed: normal app launch, admin login, post-repair journey on clean source, real backend restart, same run recovered, large-workbook canvas reopened after restart | current-browser | hosted deployment/public release deferred |

## Essential capabilities supported only by historical or controlled evidence

1. **Live Microsoft read-only ingestion** (goal 4) — current candidate uses
   local uploads and Office workbook presentation. Historical Microsoft
   evidence is bound to `001f93472`. External request: Part A.
2. **Real Outlook send / recipient delivery** (goals 8/11) — only the
   controlled outbox is current. The real adapter is implemented behind two
   explicit flags and a one-use grant, but no send has run. External request:
   Part B.
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

## External gates

- **Part A**: read-only Microsoft account + workbook + attachment authorization.
- **Part B**: one owner-controlled live Outlook recipient and a one-use send
  statement.

See `EXTERNAL_QUALIFICATION_REQUEST_2026-10-31.md` and
`REAL_TRANSPORT_QUALIFICATION_REQUEST_2026-10-31.md`. No live action was taken.
