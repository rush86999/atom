# 12-goal reconciliation — merged candidate 2026-10-31

**Candidate:** merged README + employee-execution fixes, source `589389218`
(accepted product source `b7ee7ee22`). Configuration: isolated local world,
`core` profile, single worker, controlled outbox, no live provider/send.

Evidence classes:

- **current-browser** — exercised through the normal product UI in this round;
- **current-tests** — focused tests on this candidate;
- **controlled** — controlled outbox / bounded local provider;
- **historical** — preserved but source-bound to an earlier candidate;
- **external** — requires owner credentials/authorization or a different host.

| # | Goal | Status on this candidate | Evidence class | Remaining gap |
|---|---|---|---|---|
| 1 | Create/select employee, teach, work in a different domain | passed: normal-app sales journey (teach, conflict, qualification, upload, mapping, wait, restart, resume, DOCX; revised dataset) | current-browser | arbitrary domains/schemas not claimed |
| 2 | Teach method/context/qualification/effective period/conflict/format/protocol/correction | passed: all taught through Training; conflict and missing qualification refused, expired lesson excluded, revised lesson applied only to new work | current-browser + current-tests | arbitrary prose not deterministic |
| 3 | Resolve unfamiliar columns/units; correct mapping; resume | passed: `Price → Gross Amount`, `Price → Net Amount`; mapping gap resolved; same run resumed after restart | current-browser + current-tests | arbitrary schemas not claimed |
| 4 | Upload/connect authorized data and retrieve | local path passed: CSV upload via Data, source picker, multi-sheet Office workbook sheets in catalog; live Microsoft reads are historical only | current-browser (local); **historical** (live Microsoft) | **External Part A**: read-only Microsoft account/workbook/attachment |
| 5 | Large/multi-sheet workbooks and formulas | passed: two-sheet XLSX with `=B2*C2` and `=SUM` read, edited, synced, downloaded with formulas, reloaded | current-browser | 24-sheet/large-workbook recalculation not rerun; arbitrary Excel compatibility not claimed |
| 6 | Create canvas, bind data, calculate, edit, export, reload | passed: normal-app canvas 290 → edit 110 → 325, XLSX export, `revision 2 · 4 rows` | current-browser | arbitrary controls/formulas not claimed |
| 7 | Grounded selection/calculation and substantive assessment | calculations current; **deterministic rules qualified** (18/18 V1, 19/19 V3, safe abstention); model-dependent judgment **failed** | current-tests + current-browser (canvas binding) | model judgment unqualified; deterministic only for rule-expressible policies |
| 8 | Editable DOCX/PPTX and email draft | DOCX passed (Arial 11 active, Calibri 14 revised); controlled outbox one line with greeting/signature/prefix; PPTX evidence from prior candidate remains current-tests for renderer | current-browser + controlled | real delivery not performed; PPTX visual/chart not claimed |
| 9 | User-created canvases inherit supported capabilities | passed: manifest install, CSV bind, calculate/edit/export/reload | current-browser | table adapter only |
| 10 | Long-running multi-source, missing info, browser close, restart, delayed response, changed teaching, cancellation, uncertainty | passed: wait → close → backend PID change → same run resumed → correlated response; teaching revision stayed pinned; revised lesson applied to new work; prior boundaries/reconciliation tests pass | current-browser + current-tests | one worker; no multi-day soak; real credential expiry untested |
| 11 | Approval binds exact payload/artifact; duplicate approval no duplicate transport | accepted atomic-binding evidence; controlled outbox once; duplicate/drift controls | current-tests + controlled | real send not performed (Part B) |
| 12 | Install/start/sign in/use workspace/restart/recover | passed: normal app launch, admin login, full journey, real backend restart, same run recovered | current-browser | hosted deployment/public release deferred |

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

- broader Office/workbook fixtures (large/multi-sheet) can be added and run
  locally;
- the canvas deterministic-rule authoring surface can be exercised through the
  normal UI;
- the merged README claim matrix can be re-run on this exact candidate, but
  that is a separate breadth milestone, not this goal reconciliation.

## External gates

- **Part A**: read-only Microsoft account + workbook + attachment authorization.
- **Part B**: one owner-controlled live Outlook recipient and a one-use send
  statement.

See `EXTERNAL_QUALIFICATION_REQUEST_2026-10-31.md` and
`REAL_TRANSPORT_QUALIFICATION_REQUEST_2026-10-31.md`. No live action was taken.
