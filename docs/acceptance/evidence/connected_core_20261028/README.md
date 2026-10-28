# Connected-source evidence — 2026-10-28

Status: **partial connected acceptance**. Not a release package. R3 remains
the frozen functional release.

## Source

- Microsoft Graph Outlook/OneDrive token active.
- OneDrive workbook `Consolidated Price List 2019.xlsx`
  - item id `01P3INOW7U35MJ76UHXZFLQBL4A2WXP5CG`
  - 11,463,449 bytes
  - 45 sheets
  - content version `2abb1bf40ec3`
- Zoho WorkDrive is expired (`invalid_client` on refresh); it was not used or
  bypassed.

## Evidence files

- `onedrive_ingest_start.json` / `onedrive_ingest_job.json` — real product API
  ingestion; 3,222,905 chars; 159 s.
- `agent_retrieval.json` — natural-language workbook-only ask; 11,219 rows;
  total `9,958,743.62`; source/sheet/version cited.
- `restart_retrieval.json` — same total/version after backend restart.
- `repeat_sync.txt` — second sync completed `unchanged=True skipped`.
- `email_import.json` — Graph MIME import; one attachment; reply draft.
- `docx_deliverable.json`, `pptx_deliverable.json` — real artifact canvases.
- `formula_same_sheet.txt` — `#40 TOOLING!M5 = SUM(1-K5/L5) = 0.4`.
- `formula_cross_sheet.txt` — `#40 TOOLING!N5` resolves
  `MULT SCOTCH TOOLING` and `Exchange-Index` dependencies.

## Measured

- Full workbook ingestion: 159 s through the product API.
- Direct dataset materialization: 3.5 s, peak RSS ~898 MB.
- 45 dataset entries; 11,219-row sheet complete, `truncated=false`.
- Formula sidecar: 733 cells on `#40 TOOLING`.
- Deterministic sum/count over full eligible set, not display page.

## Not evidenced

- Taught assessment over connected rows; correction; unfamiliar variation.
- Full connected employee job.
- Data/Settings UI connection/ingestion status, retry and coverage.
- Connected-source wrong-workspace/permission-loss negative controls.
- Multi-user office file-path authorization.
- Deployment, send, credential rotation.

## Honest blockers

- Zoho WorkDrive refresh invalid_client — reconnect by owner required.
- Connected rows are not yet bindable to the capability assessment adapter
  without manual row injection; that adapter work is the next implementation
  boundary.
- Multi-source asks correctly clarify rather than guess; a workbook-only ask
  resolves.
- Messy sheet headers require explicit sheet/column confirmation for
  ambiguous measures; no column is guessed.
