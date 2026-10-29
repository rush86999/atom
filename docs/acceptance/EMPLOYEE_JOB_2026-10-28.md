# Connected employee job — 2026-10-28

Status: **connected assessment slice accepted; one live-source refresh boundary
remains unexercised.** R3 is unchanged. No successor release tag or deployment
is claimed.

## Candidate and configuration

- Branch: `whole-app/successor-f5f`
- R3 tag: `expanded-core-2026-10-28-r3` → `68b949409`
- R3 tested app code: `c04591909`
- Connected world: `/private/var/folders/.../opencode/connected_world`
- Backend: `127.0.0.1:8084`
- Isolated frontend: `127.0.0.1:3003` (`NEXT_DIST_DIR=.next-connected`)
- Review model: `deepseek/deepseek-flash`, structured transport, streaming off,
  180 s deadline. Actual served route in every assessment receipt:
  `served_provider=deepseek`, `served_model=deepseek-flash`.

## Source and binding

- OneDrive item: `01P3INOW7U35MJ76UHXZFLQBL4A2WXP5CG`
- File: `Consolidated Price List 2019.xlsx`
- Sheet: `US$ SCOTCH PARTS `
- Upstream content version: `2abb1bf40ec31d131e5ae96abb173ac463426ef7`
- Dataset: `onedrive_consolidated_price_list_2019__us_scotch_parts`
- Subject field: `No.`; measure: `Unit Price`
- Canvas: `96b165e2-750b-45b5-ae00-b90968af9d97`
- Canvas snapshot version: `b92aaf07eb1d219b`
- Snapshot rows: 11,219; columns: 3; coverage `known=true`,
  `truncated=false`.
- The snapshot is explicitly labelled local. No OneDrive writeback occurred.

## Assessment 1 — certified, fully covered

- Teaching policy revision: `2fb749d9c7309426`
- Policy: REVIEW when Description contains CNC; APPROVE otherwise; HOLD when
  Description contains SEE or is blank.
- Ask: “Assess rows where Unit Price is greater than 50000.”
- Selection: 18 rows; assessed 18; unassessed 0; `status=completed`.
- Decisions: 16 APPROVE, 2 REVIEW.
- Expected before the call: 16 APPROVE, 2 REVIEW. Matched exactly.
- Latency: 12.81 s.
- Evidence: `employee_assessment_v1.json`.

## Correction and unfamiliar records

- Corrected policy revision: `a54191685f9813e6`
- Change: CNC rows move from REVIEW to HOLD.
- Ask: “Assess rows where Unit Price is greater than 40000.”
- Selection: 22 rows; assessed 22; unassessed 0; `status=completed`.
- Decisions: 20 APPROVE, 2 HOLD.
- Expected before the call: 20 APPROVE, 2 HOLD. Matched exactly.
- The two CNC rows were previously assessed; four records
  (`089126`, `089130`, `1103`, `1104`) were unfamiliar.
- Latency: 12.03 s.
- Evidence: `employee_assessment_v2_corrected.json`.

A broader 285-row selection capped at 24 subjects was also run as a coverage
pilot. It returned 24/24 decisions with 261 unassessed subjects named
explicitly, `status=partial`. It is retained as
`employee_assessment_threshold_pilot.json`; it is not the accepted task.

## Calculation and export

- Deterministic sum over the complete 11,219-row sheet:
  `9,958,743.62`.
- Calculation receipt includes both the canvas snapshot version and the
  upstream content hash, and states that edits are local.
- XLSX export: 11,219 data rows, 3 columns, total `9,958,743.62`.
- Reopened XLSX total agrees; download bytes match the saved file.
- Evidence: `employee_calculation.json`, `employee_export.json`.

## Artifacts

- DOCX canvas: `e7e878cb-db5c-4aab-bff8-6640b8fe2a82`
  - 38,200 bytes, 2 tables (19 and 23 rows), headings including
    “Correction and unfamiliar records”.
  - Reopened through python-docx and `/api/v1/office/word`; download hash
    matches the saved file.
- PPTX canvas: `10ac491a-7bc7-4c86-824b-7fc2805e0a34`
  - 36,017 bytes, 3 slides, native tables on slides 2 and 3.
  - Reopened through python-pptx and `/api/v1/office/pptx`; download hash
    matches.
- Connected email canvas `9c44465a-232d-440b-b66e-63d255c5ac76` retains the
  imported thread and one workbook attachment. A reply draft with both
  certified results was saved and reopened. No send occurred.
- Evidence: `employee_docx.json`, `employee_pptx.json`,
  `employee_email_draft.json`, `artifact_reopen_verification.json`.

## Data/Settings browser evidence

Real browser run at `http://localhost:3003/settings` → Data Pipelines:

- Connected state, account email, granted OAuth scope and token family.
- Last successful sync receipt and per-sheet coverage details.
- Recent jobs, running/failed states and errors.
- Honest failure from an invalid source id (`Failed to download file`).
- UI retry/rerun created a new job; the real unchanged source returned
  `unchanged=True`.
- Token revocation produced “Disconnected / stale”; restoring the grant
  returned “Connected”.
- Screenshots: `browser/data_settings_connected.png`,
  `browser/data_settings_retry.png`, `browser/data_settings_disconnected.png`,
  `browser/data_settings_restored.png`.

A browser retry initially exposed a real defect: the shared
`startIngestJob` helper did not set `Content-Type: application/json`, so the
product returned 422 before creating a job. Fixed in
`frontend-nextjs/lib/ingest-jobs.ts`; the rerun created the job and completed.

## Restart

- Backend restarted; canvas dataset, manifest, policy revision, source
  identities and artifacts survived.
- Fresh natural-language retrieval returned the same total and upstream
  version (`employee_post_restart_retrieval.json`).
- Fresh assessment after restart: 5 rows above 55000, 5/5 assessed, all
  APPROVE under the corrected policy, `status=completed`, served
  `deepseek-flash`.
- Email draft and both artifacts reopened after restart.

## Explicit rebind / invalidation

- Re-binding the same active upstream version returned
  `refresh.replaced=true`, prior snapshot/upstream versions, the new upstream
  version, and `assessment_reuse_invalidated=true`.
- The prior snapshot/upstream pair is retained in `previous_bindings`.
- Revision advanced; no assessment cache was reused.
- Evidence: `employee_refresh_rebind.json`.

## Negative controls

| Control | Result |
|---|---|
| Missing workspace in scoped lookup | `DatasetScopeError`; unit control |
| Wrong workspace | `workspace_mismatch` (403); unit control |
| Guessed dataset name | `source_not_found` (404) |
| Stale version | `stale_source_version` (409), active version named |
| Inactive/superseded source | `source_inactive` (409); unit control |
| Revoked grant | `source_permission_revoked` (403) |
| Revoked-grant chat retrieval | named and generic catalog asks returned no cached total; the answer named the inactive/revoked grant |
| Disconnected source | `source_disconnected` (409); unit control |
| Client-supplied `file_path` | 422 `extra_forbidden` |
| Client-supplied `sha256` | 422 `extra_forbidden` |
| Client-supplied rows | 422 `extra_forbidden` |
| Incomplete/truncated materialization | `materialization_incomplete`; unit control |
| Blank subject | `subject_field_required` / `ambiguous_subject_mapping` |
| Duplicate subject | `duplicate_subject_mapping` |
| Snapshot edit claims writeback | `writeback.upstream_mutated=false`, upstream version unchanged |

Evidence: `employee_negative_controls.json` plus
`backend/tests/test_canvas_connected_binding.py`.

## Remaining gap

The live changed-source refresh was **not** performed. Modifying the OneDrive
item would be source writeback, which this work order forbids. What was
verified instead:

- real repeat sync of the unchanged item (`unchanged=True`);
- explicit same-version rebind with reuse invalidation and retained history;
- a unit control that materializes changed bytes under the same source
  identity, supersedes the old version, rebinds the new version, and records
  the prior version.

A live changed-byte refresh needs an owner-authorised source change (or a
separate sandbox drive where the operator permits a write), then a re-run of
the refresh boundary. Until then the connected employee job is accepted for
its demonstrated scope, but the overall exit condition for a successor release
remains open.

The Microsoft Graph access token expired at `2026-10-29T00:27:28Z`, after the
evidence run. No refresh, rotation or reconnect was performed; further live
runs require the owner to reconnect.

## Release position

- R3 untouched: `expanded-core-2026-10-28-r3` → `68b949409`.
- No successor tag, deployment, email send, source writeback or credential
  rotation was performed.
- Single-user restrictions remain. Per-file multi-user Office authorization is
  still unsupported.
- Cost was not separately metered by the structured review route; latency and
  memory are recorded, but no token-cost figure is claimed.
