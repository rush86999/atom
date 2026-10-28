# Connected-data core status — 2026-10-28

Status: **partial connected acceptance.** R3 remains the frozen functional
release; nothing here is a successor release or a deployment.

## What passed

| Boundary | Result |
|---|---|
| Real connected source | Microsoft Graph Outlook/OneDrive token is active; OneDrive workbook downloaded from source version |
| Connected file ingestion | `Consolidated Price List 2019.xlsx` ingested through `/api/onedrive/ingest-document`; 11,463,449 bytes, 45 sheets, 3,222,905 chars, 159 s end-to-end |
| Workbook materialization | 45 dataset entries; 11,219-row `US$ SCOTCH PARTS` sheet; complete coverage (`truncated=false`) |
| Formula ingestion | 733 formula cells on `#40 TOOLING`; same-sheet `M5 = SUM(1-K5/L5)` evaluates to `0.4`; cross-sheet `N5` resolves `MULT SCOTCH TOOLING` and `Exchange-Index` dependencies |
| Agent retrieval without supplied rows | Chat retrieved the workbook and sheet from natural language and returned `9,958,743.62` over 11,219 rows with source/sheet/version citations |
| Connected email | Outlook MIME message imported through the email canvas; `consolidated price lists` + one workbook attachment; editable reply draft saved |
| Deliverables | Real DOCX with table and source references; real PPTX with 2 slides, table and notes; both reopen/download |
| Repeat sync | Second OneDrive ingest completed `unchanged=True` / `skipped` |
| Restart | Same workbook total `9,958,743.62`, version and sheet after backend restart |
| Direct materialization performance | 3.5 s, peak RSS ~898 MB on this machine for the 11.4 MB workbook |

## What is still missing

- Taught assessment over connected workbook rows, with decision vocabulary,
  correction, and an unfamiliar variation.
- The full connected employee job (email + workbook + document/deck,
  correction, refresh, restart, artifact reopen) as one accepted run.
- Data/Settings UI evidence for connection state, last sync, coverage,
  failures, unsupported files and retry.
- Zoho WorkDrive refresh is currently `invalid_client`; that connection needs
  owner reauthorization. OneDrive is the working file source for this run.
- Connected-source permission-loss and wrong-workspace negative controls on
  retrieval, beyond the existing R3 canvas/office controls.
- The connected run used API/public boundaries for source ingestion/chat and
  deliverable generation; browser-level Data status was not exercised.

## First broken transitions observed

1. Zoho WorkDrive access token expired and refresh failed with
   `invalid_client` — owner reconnection required; not bypassed.
2. The existing chat path initially treated “document(s) and workbook(s)” as
   ambiguous. A workbook-only ask resolved correctly. This is a clarification
   behavior, not a fabricated answer.
3. `US$ SCOTCH PARTS` headers are messy; deterministic sum/count worked only
   after the sheet was named. Ambiguous price columns correctly returned a
   clarification rather than guessing.

## Source identity

- OneDrive item: `01P3INOW7U35MJ76UHXZFLQBL4A2WXP5CG`
- Content version: `2abb1bf40ec3`
- Outlook message: `AAMkADdlNTY5N2I1LTQwNTMtNDQ2OC04MzBlLTU5OGFmZGQ2MzRmYQBGAAAAAADWztKWmJlHSYU0pqyNk-0MBwDEtbYrrPLwTae3iXb78LoOAAAAAAEJAADEtbYrrPLwTae3iXb78LoOAAAAAFX1AAA=`
- Email canvas: `9c44465a-232d-440b-b66e-63d255c5ac76`
- Generated document canvas: `2eac4ef5-883c-421a-951a-767971d64b34`
- Generated deck canvas: see connected ledger/evidence

## Release position

- R3 tag unchanged: `expanded-core-2026-10-28-r3` → `68b949409`.
- No successor package is claimed.
- No deployment, email send, external write, or credential rotation was
  performed.
- Multi-user source use remains unauthorized until direct Office file-path
  authorization and source-permission negative controls are closed.
