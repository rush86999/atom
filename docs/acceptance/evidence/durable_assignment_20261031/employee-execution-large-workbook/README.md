# Large workbook (24 sheets) — ingestion, retrieval, recalculation, export, restart

This bundle is the Goal 5 large-workbook exercise on the clean repaired source
`31ba9725e02a`. It is a representative fixture, not a general Excel
compatibility claim.

## Fixture

`workbook/twenty_four_sheet_workbook.xlsx` has **24 sheets**: `Data01`–`Data20`,
`Summary`, `Rates`, `Notes`, `Index`.

- 20 data sheets × 25 rows = **500 data rows** (the catalog also exposes the
  four reference sheets: **547 materialized rows** across 24 sources);
- leading-zero IDs (`0001`…`0025`) preserved as text;
- some Unit Price / Note cells blank;
- each data row computes `Total = Qty * Unit Price` (`=B2*C2`);
- `Summary!B2:B21` sums each data sheet (`=SUM(Data01!D2:D26)`);
- `Summary!B22` is the grand total (`=SUM(B2:B21)`).

## Executed workflow

1. **Ingestion** — the workbook was uploaded through the normal **Data** page.
   The product catalog exposes all **24** sheet sources with a combined
   **547** rows (`catalog/sources.json`). The earlier canvas-catalog copies
   (`office_canvas_*`) are not used here: assignment source access rejects them
   with `409 source_access_unverified`; the upload sources are the authorized
   product path.
2. **Retrieval without supplied rows** — an assignment was created from
   `upload_twenty_four_sheet_workbook__data01` with a sum over `Total`. The
   source receipt loaded **25 rows** (`sheet_rows 2–26`, `selected_count=25`)
   and returned **1725.00**; the completed DOCX says `Total 1725.00` and cites
   the workbook/sheet (`assignment-full-population.json`,
   `assignment-detail.json`, `artifacts/full-population-total.docx`). No row
   values were supplied in the request. The operation record's `claimed_by`
   is `instance_id:31ba9725e02a.64859…`, the clean serving instance.
3. **Recalculation after an edit** — the canvas cell `Data01!B2` was changed
   from `2` to `5` through the ordinary grid (commit on blur). The
   `/api/v1/office/sync-update` response reported `recalc_status=complete`,
   `recalculated=true`, and no formula gaps. `Data01!D2` became `55`, and the
   dependent cross-sheet values became `Summary!B2=1758`, `Summary!B22=34533`
   (`edit-recalc.json`). A revert to `2` was also recalculated cleanly first,
   so the final edit is a real second write, not a stale cached value.
4. **Export** — the visible **Download** action produced a file byte-identical
   to the authoritative workbook (`export-verification.json`,
   `workbook/exported-download.xlsx`). It still has 24 sheets, leading-zero
   IDs, 500 data rows, blanks, live formulas and the recalculated cached
   values.
5. **Restart/reopen** — the backend was stopped and relaunched on the same
   clean source (`31ba9725e02a`, `dirty=false`, new PID). Reopening
   `canvas_5da23f09ef60` shows all **24 sheet tabs**, `Data01!A2=0001`,
   `B2=5`, `D2=55`, and `Summary!B2=1758`, `B22=34533`
   (`reopen-after-restart.json`, screenshots).

## Serving identity

| Phase | Source | Dirty | PID |
|---|---|---|---|
| ingestion + edit | `31ba9725e02a` | false | 64859 |
| restart/reopen | `31ba9725e02a` | false | 67158 |

`health-ingest-edit.json` and `health-reopen.json` are the captured runtime
identities. The ingest/edit process is the same process that completed the
repaired normal-app journey; the workbook was created and edited on that clean
source.

## Boundary

Supported formulas here are the ones exercised: arithmetic cell formulas and
cross-sheet `SUM` ranges. Arbitrary Excel functions, macros, charts, external
links and full Excel compatibility are not claimed.
