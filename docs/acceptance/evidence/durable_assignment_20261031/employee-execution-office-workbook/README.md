# Office workbook regression — normal application

A multi-sheet `.xlsx` with formulas was presented through the normal Office
surface (`POST /api/v1/office/present`) and opened at `/canvas/<id>` in the
product UI.

## What was verified

- Sheet **Orders** and **Rates** both opened; sheet tabs switched correctly.
- Formula cells were live: `D2=B2*C2`, `F2=SUM(D2:D4)`.
- Editing `B2` 4 → 6 triggered the normal `/api/v1/office/sync-update`
  endpoint; `D2` recalculated 40 → 60 and `F2` 105 → 125.
- **Download** produced a real `.xlsx`; reloading it with `openpyxl` preserved
  the edited value **and the formulas** (`=B2*C2`, `=SUM(D2:D4)`).
- Reloading the canvas preserved `B2=6`, `D2=60`, `F2=125`.
- No page errors.

`result.json`: **6/6 checks passed**. `downloaded.xlsx` is the artifact;
`screenshot.png` is the completed canvas; `canvas.json` records the world file
and canvas id.

The `/sync-update` route now contains the supplied `file_path` **before** any
canvas lookup, so an out-of-scope path is a 400 without touching the filesystem
(`test_round53_office_sync_path_containment.py`).

## Scope

Local workbook only; no live OneDrive/SharePoint write, no collaborator
co-editing claim beyond the accepted canvas WebSocket evidence.
