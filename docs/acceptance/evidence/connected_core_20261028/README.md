# Connected-source evidence — 2026-10-28

Status: **connected assessment slice accepted; overall successor release open
on live changed-source refresh.** Not a release package. R3 remains frozen.

## Source

- Microsoft Graph Outlook/OneDrive token active.
- OneDrive workbook `Consolidated Price List 2019.xlsx`
  - item id `01P3INOW7U35MJ76UHXZFLQBL4A2WXP5CG`
  - 11,463,449 bytes
  - 45 sheets
  - content version `2abb1bf40ec31d131e5ae96abb173ac463426ef7`
- Zoho WorkDrive is expired (`invalid_client` on refresh); it was not used or
  bypassed.

## Core evidence

- `onedrive_ingest_start.json` / `onedrive_ingest_job.json` — real product API
  ingestion; 3,222,905 chars; 159 s.
- `employee_bind_connected.json` — server-resolved catalog binding; separate
  canvas snapshot and upstream identity; coverage complete.
- `employee_assessment_v1.json` — 18/18 certified, 16 APPROVE + 2 REVIEW,
  served `deepseek-flash`, 12.81 s.
- `employee_assessment_v2_corrected.json` — 22/22 certified after CNC
  REVIEW→HOLD; 20 APPROVE + 2 HOLD; four unfamiliar subjects.
- `employee_assessment_threshold_pilot.json` — 285 selected / 24 assessed /
  261 unassessed named explicitly; retained as a coverage pilot.
- `employee_teaching_history.json` — policy revisions and restart agreement.
- `employee_calculation.json`, `employee_export.json` — full 11,219-row total
  `9,958,743.62`; XLSX reopen/download agreement.
- `employee_docx.json`, `employee_pptx.json`,
  `artifact_reopen_verification.json` — real Word/PowerPoint artifacts, native
  tables, reopen and download agreement.
- `employee_email_draft.json`, `employee_email_reopen.json` — connected reply
  draft saved/reopened; no send.
- `employee_repeat_sync_job.json` — `unchanged=True` repeat sync.
- `employee_post_restart_retrieval.json`,
  `employee_post_restart_assessment.json` — fresh retrieval and 5/5 certified
  assessment after restart.
- `employee_negative_controls.json` — API-level wrong/stale/forged/revoked
  refusals.
- `employee_revoked_retrieval.json` — named and generic chat retrieval after
  grant revocation; neither returned a cached total.
- `employee_refresh_rebind.json` — explicit rebind, prior provenance retained,
  assessment reuse invalidated.
- `browser/` — Data/Settings screenshots and text for connected, retry,
  disconnected/stale and restored states.
- `formula_same_sheet.txt`, `formula_cross_sheet.txt` — formula evaluation.

## Measured

- Full workbook ingestion: 159 s through the product API.
- Direct dataset materialization: 3.5 s, peak RSS ~898 MB.
- 45 dataset entries; 11,219-row sheet complete, `truncated=false`.
- Formula sidecar: 733 cells on `#40 TOOLING`.
- Deterministic sum/count over full eligible set, not display page.
- Assessment latency: 12.81 s (v1), 12.03 s (corrected), 12 s after restart.
- Natural-language retrieval latency after restart: 43.59 s.

## Not evidenced / limitations

- Live changed-byte refresh: modifying OneDrive would be source writeback,
  which is forbidden. Explicit same-version rebind and a local changed-version
  unit control were used instead.
- Multi-user per-file Office authorization remains unsupported.
- Token cost was not metered; no cost figure is claimed.
- Microsoft Graph access expired at `2026-10-29T00:27:28Z` after the evidence
  run; owner reconnect is required for further live runs.
- Deployment, send and credential rotation did not occur.

## Honest blockers

- Zoho WorkDrive refresh `invalid_client` — owner reconnection required.
- The structured review route supports bounded subject assessment; a broad
  selection that exceeds the cap is returned as `partial` with the unassessed
  subjects named, not silently certified.
- Messy sheet headers still require explicit subject/measure confirmation.
