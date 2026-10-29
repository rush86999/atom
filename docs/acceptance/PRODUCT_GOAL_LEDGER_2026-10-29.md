# Product goal ledger — 2026-10-29

This ledger is the durable reference for the bounded single-user AI-employee
pilot. Historical evidence stays bound to the source that produced it. The
current packaged product identity is `901e5d77348e0c7b85b1f1291cbeb0fc50eb2ff0`
(tag `assignment-successor-2026-10-29`, product tree
`92d794b20400aa013019a602fc6dccfa2c3b53240ff63905dc40d80340d3937c`).

Statuses: **Demonstrated**, **Partial**, **Deferred**, **Blocked**.

| # | Goal | Status | Implementation entry points | Tested source/config | User-visible evidence | Limitation / next action |
|---|---|---|---|---|---|---|
| 1 | Domain- and business-independent employee work | Demonstrated for tested domains; not universal competence | `core/assignment_planner.py`, `core/assignment_executor.py`, `core/table_selection.py`, `core/dataset_aggregation.py`, `core/review_result.py` | Cross-domain evidence on the review-fixed line (`294fdf0ec` / `40b3367d9`); C10 changes only outbound policy, not domain logic | `docs/acceptance/DURABLE_ASSIGNMENT_2026-10-29.md`; commercial and eligibility evidence under `docs/acceptance/evidence/durable_assignment_20261029/` | Two domains are demonstrated; arbitrary domain competence is not claimed. Keep business labels in task/teaching data. |
| 2 | Teaching context, approach, protocol and formatting | Demonstrated | `core/artifact_teaching.py`, `core/student_learning_service.py`, `core/office_service.py`, renderers | `1d5e8d780` owner delta plus reviewed C10 package; historical bounded taught job | Bounded taught job evidence: `evidence/durable_assignment_20261029/bounded-taught-job/` | Teaching capture/correction/restart is demonstrated; arbitrary instructions and every renderer field are not. |
| 3 | Extrapolation to unfamiliar sheets and columns | **Partial** | Mapping resolver in `core/artifact_teaching.py`; mapping-candidate gaps and resume in `core/assignment_executor.py`; structured gap route in `backend/api/assignment_routes.py`; candidate picker in `frontend-nextjs/components/assignments/AssignmentPanel.tsx` | Mapping resolver/executor/panel controls on the mapping successor; browser campaign not yet run | Unit/executor evidence: gap lists real candidates with samples, forged/stale/unit checks reject, confirmation replaces the missing column, recalculates `85.00`, and updates the teaching snapshot | **Missing:** taught-workbook → differently-shaped-workbook browser campaign, correction/restart/third-workbook/stale-confirmation UI run. Next action: run the bounded browser campaign, then freeze the successor. |
| 4 | Connected ingestion and agent retrieval | Demonstrated for declared Microsoft scope | `core/assignment_resources.py`, `core/sheet_dataset_service.py`, shared OAuth resolver, typed bindings | Live Outlook attachment and OneDrive changed-byte gates at `001f93472`; C10 resource code unchanged | `live-connected/guided/gate-result.json`, `live-connected/changed-source/gate-result.json` | Zoho is optional/out of scope; arbitrary connector coverage is not claimed. |
| 5 | Large spreadsheets and formula ingestion | Partial — demonstrated subset | Workbook ingestion, `sheet_dataset_service`, formula sidecar/evaluator, `dataset_aggregation` | Historical large-workbook evidence; C10 did not regress it | Historical `connected_core_20261028` evidence and clean-source verification | Large retrieval and same/cross-sheet formula subset are demonstrated; arbitrary Excel compatibility and unsupported formulas as certified recalculation are not. |
| 6 | Excel-like canvas | Demonstrated for supported operations | Capability adapter, authoritative frame, revision-checked edits, office routes | Historical acceptance on the supported table adapter; C10 no change | Office/canvas acceptance evidence under `docs/acceptance/evidence/` | Filtering/edit/recalc/reload/XLSX export are demonstrated for supported sheets; every spreadsheet control and unsupported formula display are not. |
| 7 | Grounded selection, calculations and assessments | Demonstrated for tested contracts | `core/table_selection.py`, `core/dataset_aggregation.py`, `core/review_result.py`, deterministic receipt/evidence binding | Clean-source and bounded tests; C10 unchanged except outbound policy | Assignment tests and cross-domain evidence; fresh C10 assignment produced `216700.00` with row/cell provenance | Structural validity is separate from substantive policy judgment; arbitrary policies and full assessment certification coverage remain bounded. |
| 8 | Email, documents and presentations | Demonstrated for draft/format/reopen; send separate | `core/office_service.py`, email/canvas services, artifact renderers | Historical Office/email evidence; C10 draft smoke completed and survived restart | `deployment-auth-20261029-c10/draft-smoke.json`; historical DOCX/PPTX/email evidence | Image/chart understanding is excluded. Real-provider send is **Blocked** on the separate authorized test (goal 11). |
| 9 | User-created canvases inherit capabilities | Partial — supported table adapter | Versioned capability manifests, adapter registry, canvas routes | Historical capability evidence; C10 no change | Capability acceptance evidence | Only the supported table adapter is claimed; every future canvas component is not. |
| 10 | Long-running, multi-source employee assignments | Demonstrated for controlled wait/approval/restart | `core/task_lifecycle.py`, GoalRun services, executor checkpoints, HITL routes | Bounded taught job and C10 fresh/persistence restart checks | Bounded job evidence; C10 `deployment-receipt.json` restart agreement | One worker per assignment is the verified topology; multi-worker campaigns and autonomous third-party research are not claimed. |
| 11 | Approval and eventual sending | **Partial / Blocked** | Approval binding and HITL; `core/assignment_executor.py`; `core/email_send_policy.py`; `integrations/outlook_service.py`; `core/canvas_email_service.py` | C10 config: `ATOM_EMAIL_SEND_DISABLED=1`, `ATOM_ASSIGNMENT_ALLOW_LIVE_SEND=0`; server-side denial tested | C10 `send-denial.json`: HTTP 422 before run creation; draft smoke saved/reopened; no provider/outbox effect | Draft and approval preparation work; production send is refused before transport. **Remaining action:** separately authorized real-provider test with exact payload, provider receipt, reconciliation and restart/no-duplicate checks. |
| 12 | Everyday usability, security and operational readiness | Pilot candidate; deployment unverified | Normal auth, Assignments/Activity, durable storage, deployment kit and recovery guards | C10 packaged source, isolated single-user rehearsal | C10 auth smoke, fresh assignment, restart agreement, deployment receipt, 19 kit controls, 41 product controls | Normal sign-in/logout/relogin and fresh packaged execution pass in isolation. Deployment authorization is still required; mapping UI remains partial. |

## Explicit exclusions

- Multi-user deployment and per-file multi-user Office authorization.
- Real email sending/provider delivery; current release is draft-and-approval only.
- Arbitrary third-party research or autonomous external investigation.
- Arbitrary Excel formula compatibility; unsupported formulas must stay gaps.
- Embedded image/chart interpretation.
- Complete mapping-confirmation UI on every canvas surface.

## Evidence policy

- Historical large-workbook/Office evidence is not a C10 regression pass; it is
  identified with its tested commit/configuration.
- C10-specific controls: fresh assignment, persistence/restart, draft save and
  server-side send denial, deployment recovery, and identity checks.
- No goal is marked complete merely because a deployment or a schema validation
  passes.
