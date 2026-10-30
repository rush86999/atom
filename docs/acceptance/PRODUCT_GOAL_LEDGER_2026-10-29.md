# Product goal ledger — 2026-10-29

This ledger is the durable reference for the bounded single-user AI-employee
pilot. Historical evidence stays bound to the source that produced it. The
previous packaged product identity remains `901e5d77348e0c7b85b1f1291cbeb0fc50eb2ff0`
(tag `assignment-successor-2026-10-29`, product tree
`92d794b20400aa013019a602fc6dccfa2c3b53240ff63905dc40d80340d3937c`). The frozen
successor candidate is `a9648432495f4f75f59bf4667cac3cb997d7f229` (tag
`assignment-successor-2026-10-29-a96484324`, product tree
`937d100838300c8ec703f5c8ee164f029acf4ecbe64d6a823bd994fa9070d8e6`), not deployed.

Statuses: **Demonstrated**, **Partial**, **Deferred**, **Blocked**.

| # | Goal | Status | Implementation entry points | Tested source/config | User-visible evidence | Limitation / next action |
|---|---|---|---|---|---|---|
| 1 | Domain- and business-independent employee work | Demonstrated for tested domains; not universal competence | `core/assignment_planner.py`, `core/assignment_executor.py`, `core/table_selection.py`, `core/dataset_aggregation.py`, `core/review_result.py` | Cross-domain evidence on the review-fixed line (`294fdf0ec` / `40b3367d9`); C10 changes only outbound policy, not domain logic | `docs/acceptance/DURABLE_ASSIGNMENT_2026-10-29.md`; commercial and eligibility evidence under `docs/acceptance/evidence/durable_assignment_20261029/` | Two domains are demonstrated; arbitrary domain competence is not claimed. Keep business labels in task/teaching data. |
| 2 | Teaching context, approach, protocol and formatting | Demonstrated; current successor journey test | `core/artifact_teaching.py`, `core/student_learning_service.py`, `core/office_service.py`, renderers | `1d5e8d780` owner delta plus reviewed C10 package; historical bounded taught job | Bounded taught job evidence: `evidence/durable_assignment_20261029/bounded-taught-job/` | Teaching capture/correction/restart is demonstrated; arbitrary instructions and every renderer field are not. |
| 3 | Extrapolation to unfamiliar sheets and columns | **Demonstrated for tested mapping/confirmation/correction/restart workflows** | Mapping resolver in `core/artifact_teaching.py`; mapping-candidate gaps, unit authority, source-identity correction, scoped invalidation, rejection acknowledgement and replay guards in `core/assignment_executor.py`; gap/correction routes in `backend/api/assignment_routes.py`; candidate/unit picker, rejection and correction form in `frontend-nextjs/components/assignments/AssignmentPanel.tsx` | Final product `a96484324` (waiting-restart/rejection + authority controls) on unit-authority product `ae53e7e41`; B/C/correction/waiting-restart browser campaign | Browser B: gap → `Amount` → `35.00 USD` (`mapping-browser-b/attempts/c78b9a0c-4d4b-4ef6-97e5-4be56fa31449/`). Browser C: no source unit → explicit USD → `75.00` (`mapping-browser-c/attempts/a228e80a-1980-4d9c-8489-6295ca38abce/`). Correction: List Price `100.00` → Contract Price `80.00`, mapping revision 2→3; prior result/artifact preserved; unrelated Tax mapping, formatting/applicability and independent Tax `8.00` work unchanged; stale `409`, wrong workspace `404`, concurrent `200`/`409` (`mapping-browser-correction/attempts/0f8db7bb-f3d2-4d5f-8ec5-768dd677843e/`). Waiting restart: reject through panel keeps the same assignment/request/candidates/source and teaching revisions with no result or teaching write; backend-only restart reopens the same request; `Amount` then completes the same assignment at `35.00 USD`, mapping revision 2, one applied calculation, one superseded wait, artifact/reload durable (`mapping-browser-waiting-restart/attempts/a8b27ce5-ead8-4a9f-8b21-8069e088486e/`). Route controls cover wrong request/assignment, forged column, stale source, stale teaching, wrong workspace, incompatible unit, identical replay (no duplicate work) and conflicting replay; ambiguous concept/source correction is also refused. Affected suites: 98 passed; all four browser flows passed on the same commit. | Tested workflows only. Automatic understanding of arbitrary schemas, every possible authority surface, and arbitrary Excel compatibility are not claimed. |
| 4 | Connected ingestion and agent retrieval | Demonstrated for declared Microsoft scope | `core/assignment_resources.py`, `core/sheet_dataset_service.py`, shared OAuth resolver, typed bindings | Live Outlook attachment and OneDrive changed-byte gates at `001f93472`; C10 resource code unchanged | `live-connected/guided/gate-result.json`, `live-connected/changed-source/gate-result.json` | Zoho is optional/out of scope; arbitrary connector coverage is not claimed. |
| 5 | Large spreadsheets and formula ingestion | Demonstrated within published subset; 24-sheet/cross-sheet current test | Workbook ingestion, `sheet_dataset_service`, formula sidecar/evaluator, `dataset_aggregation` | Historical large-workbook evidence; C10 did not regress it | Historical `connected_core_20261028` evidence and clean-source verification | Large retrieval and same/cross-sheet formula subset are demonstrated; arbitrary Excel compatibility and unsupported formulas as certified recalculation are not. |
| 6 | Excel-like canvas | Demonstrated for supported operations | Capability adapter, authoritative frame, revision-checked edits, office routes | Historical acceptance on the supported table adapter; C10 no change | Office/canvas acceptance evidence under `docs/acceptance/evidence/` | Filtering/edit/recalc/reload/XLSX export are demonstrated for supported sheets; every spreadsheet control and unsupported formula display are not. |
| 7 | Grounded selection, calculations and assessments | Demonstrated for tested contracts | `core/table_selection.py`, `core/dataset_aggregation.py`, `core/review_result.py`, deterministic receipt/evidence binding | Clean-source and bounded tests; C10 unchanged except outbound policy | Assignment tests and cross-domain evidence; fresh C10 assignment produced `216700.00` with row/cell provenance | Structural validity is separate from substantive policy judgment; arbitrary policies and full assessment certification coverage remain bounded. |
| 8 | Email, documents and presentations | Demonstrated for draft/format/reopen; send separate | `core/office_service.py`, email/canvas services, artifact renderers | Historical Office/email evidence; C10 draft smoke completed and survived restart | `deployment-auth-20261029-c10/draft-smoke.json`; historical DOCX/PPTX/email evidence | Image/chart understanding is excluded. Real-provider send is **Blocked** on the separate authorized test (goal 11). |
| 9 | User-created canvases inherit capabilities | Demonstrated for supported table adapter; two canvas shapes current test | Versioned capability manifests, adapter registry, canvas routes | Historical capability evidence; C10 no change | Capability acceptance evidence | Only the supported table adapter is claimed; every future canvas component is not. |
| 10 | Long-running, multi-source employee assignments | Demonstrated for controlled wait/approval/restart; artifact-restart current test | `core/task_lifecycle.py`, GoalRun services, executor checkpoints, HITL routes | Bounded taught job and C10 fresh/persistence restart checks | Bounded job evidence; C10 `deployment-receipt.json` restart agreement | One worker per assignment is the verified topology; multi-worker campaigns and autonomous third-party research are not claimed. |
| 11 | Approval and eventual sending | **Partial / Blocked** — local attachment-byte binding added; real send separate | Approval binding and HITL; `core/assignment_executor.py`; `core/email_send_policy.py`; `integrations/outlook_service.py`; `core/canvas_email_service.py` | C10 config: `ATOM_EMAIL_SEND_DISABLED=1`, `ATOM_ASSIGNMENT_ALLOW_LIVE_SEND=0`; server-side denial tested | C10 `send-denial.json`: HTTP 422 before run creation; draft smoke saved/reopened; no provider/outbox effect | Draft and approval preparation work; production send is refused before transport. **Remaining action:** separately authorized real-provider test with exact payload, provider receipt, reconciliation and restart/no-duplicate checks. |
| 12 | Everyday usability, security and operational readiness | Pilot candidate; successor package prepared; deployment blocked on approval/password/quiescence | Normal auth, Assignments/Activity, durable storage, deployment kit and recovery guards | C10 packaged source plus successor packaged smoke on `a96484324` | C10 auth smoke, fresh assignment, restart agreement, deployment receipt, 19 kit controls, 41 product controls; successor packaged smoke, backup and restart receipts | Normal sign-in/logout/relogin and fresh packaged execution pass in isolation. The successor packaged smoke reopened an existing taught assignment, exercised the mapping flow and survived restart. Deployment authorization is requested but not granted. |

Mapping campaign identities: the canonical B baseline stays bound to harness
`7399fe41e`; new B/C/correction/waiting-restart attempts are written under
unique `attempts/<run_id>/` directories. The final B/C/correction/waiting-restart
evidence is bound to product `a96484324` (tree
`ae8b96bba44df25915be38bce3679eab8901056a`). Prior correction evidence remains
bound to `06e6c2cdc`/`f0d96c5ed`; the original C evidence remains bound to
product `ae53e7e41` (tree `a7f627fdf7705a26b361c0d1b1e7e17abadc13d3`). Frozen
release `901e5d773` is unchanged. The final manifest and file hashes are
`docs/acceptance/evidence/durable_assignment_20261029/mapping-restart-campaign/manifest-a96484324.json`;
the prior manifests and attempt directories are preserved unchanged.

## Core completion successor — fda4f2dc9

Product `fda4f2dc9376f20a6e10de6d7d1e55cf16eeffd4` (tag
`assignment-successor-2026-10-30-fda4f2dc9`, tree
`92924cd8f8f3cffa8e884a9a7fecc5f820f4f5ce8acbba60fdd257975df614fa`)
preserves all prior evidence and adds the bounded external-information
workflow.

- `external.research` dispatches only registered read-only actions through the
  shared action registry, validates required result fields, and records
  retrieved content as evidence with action/arguments/time provenance.
- A missing result becomes a typed `external_research` obligation. Resolving it
  resumes the same assignment; the raw answer is preserved separately from the
  audit annotation, and it never changes teaching or authority.
- Current tests cover successful retrieval, typed obligation/resume with the
  same assignment identity, write-action refusal, and teaching preservation.
- Release-affected suite: **581 passed, 2 skipped**; kit controls: **25
  passed**; four mapping browser flows passed on this product.

Remaining required external gates: deployment authorization/password/source
quiescence, and one real-provider send qualification. Broader compatibility
limits remain explicit and do not exclude the required employee workflows.

## Core completion successor — 242c9a01f

The successor product is frozen at
`242c9a01ff9aebb0467ad7a619ea7e4e468f454d` (tag
`assignment-successor-2026-10-30-242c9a01f`, tree
`c20bb599ff7ab65913f42cd14a5a93012b6817c93b6b0b5eddfb7c056e24c9b7`).
It preserves `a96484324` and `901e5d773` unchanged.

Current package:
`docs/acceptance/assignment-successor-package-2026-10-30-242c9a01f/assignment_successor_manifest.json`.
Prepared root:
`/Users/rushiparikh/projects/atom-deployments/assignment-successor-2026-10-30-242c9a01f`.

Current acceptance:
- 578 release-affected tests passed, 2 skipped; 127 targeted tests passed;
  22 deployment-kit controls passed.
- Four current mapping browser flows passed on this product: B `35.00`, C
  `75.00`, correction `100.00 -> 80.00`, waiting restart `35.00`.
- New current boundaries: exact attachment-byte approval binding; 24-sheet
  workbook with leading-zero ids and blanks; cross-sheet formula text; teach →
  correct → wrong-context → restart; two differently shaped canvases using the
  same operations; restart after artifact creation without duplicate work.
- Data: 50/481/557 rows; 1,205 files; 16,305 operations, 0 binding mismatches;
  21 missing historical paths visible, none referenced.
- Rollback to `901e5d773` verified against refreshed data with the same
  data/artifact world, 0 binding mismatches, no database restore and no new
  interactive approval.

Remaining boundaries:
- `config/APPROVED` and `config/pilot_password` are absent.
- The live source writer pid `19046` holds the source database/WAL; cutover
  requires an authorized quiescence window or a final refresh. The gate now
  checks before backup, after backup and immediately before activation.
- Real-provider sending remains a separate authorization; local payload,
  approval, attachment-byte, reconciliation and no-duplicate controls are
  implemented and tested.
- Supported-envelope limits remain: arbitrary Excel compatibility, arbitrary
  schema understanding, embedded image/chart interpretation, every future
  canvas component, other connectors, multi-worker campaigns and autonomous
  third-party research are not claimed.

## Release integration — a96484324

The successor candidate is frozen at `a96484324` under tag
`assignment-successor-2026-10-29-a96484324`; the previous release tag and all
prior evidence are unchanged. Package manifest:
`docs/acceptance/assignment-successor-package-2026-10-29-a96484324/assignment_successor_manifest.json`.

The four browser flows pass on that product: workbook B `35.00`, workbook C
`75.00` with an explicit unit, correction `100.00 -> 80.00` at mapping revision
3, and reject -> backend restart -> confirm `35.00` at mapping revision 2.
Authority controls: 5 focused route tests; mapping regressions: 98 passed;
release-affected regressions: 508 passed, 2 skipped.

The full isolated deployment transaction reopened an existing taught assignment
and artifact, created and completed a new mapping assignment at `35.00 USD`,
created a second fresh read-only assignment with calculation and grounded
artifact, confirmed the selected DeepSeek policy (`deepseek` / `deepseek-flash`),
proved an outbound assignment is refused with HTTP 422 before run creation, and
reopened both results after a packaged backend restart with no disagreement.
The first transaction attempt failed at the onboarding modal and is preserved;
the repaired harness passed. Receipts:
`docs/acceptance/evidence/durable_assignment_20261029/release-integration-a96484324-transaction/`.

Deployment kit:
`scripts/deployment/assignment_successor_2026-10-29_a96484324/`; runbook:
`docs/deployment/assignment_successor_2026-10-29_a96484324/DEPLOYMENT_RUNBOOK.md`;
approval request:
`docs/deployment/assignment_successor_2026-10-29_a96484324/APPROVAL_REQUEST.md`.
The production root now exists at
`/Users/rushiparikh/projects/atom-deployments/assignment-successor-2026-10-29-a96484324`
with the authoritative data/artifact handoff, required memory export and a real
`901e5d773` previous link. A logical freshness baseline (389 SQLite tables,
memory versions, referenced files) guards cutover and refused a stale snapshot
during preparation; the current v4 handoff checks fresh. Actual
candidate-failure → rollback-start was re-verified against the refreshed data
in an isolated copy; production authentication smoke awaits the owner pilot
password. Deployment is **not authorized**. The one reviewable deployment decision is
`docs/acceptance/DEPLOYMENT_DECISION_a96484324_2026-10-29.md`; the goal-by-goal
audit is `docs/acceptance/GOAL_COMPLETION_AUDIT_2026-10-29.md`. Real-provider
sending remains explicitly open, is refused before transport by this release,
and has a separate prepared qualification in
`docs/acceptance/REAL_PROVIDER_SEND_QUALIFICATION_2026-10-29.md`.

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
