# Historical OneDrive provenance reconciliation — 2026-10-29

No raw evidence was modified.

## Earlier claim

The connected-core acceptance claimed:

- provider: `onedrive`;
- file: `Consolidated Price List 2019.xlsx`;
- OneDrive file id: `01P3INOW7U35MJ76UHXZFLQBL4A2WXP5CG`;
- content hash/version: `2abb1bf40ec31d131e5ae96abb173ac463426ef7`;
- sheet: `US$ SCOTCH PARTS `;
- materialized rows: `11,219`;
- complete coverage, sum of `Unit Price`: `9,958,743.62`.

## Preserved provider/item/version records

`docs/acceptance/evidence/connected_core_20261028/onedrive_ingest_job.json`
records a completed OneDrive ingestion job for that file id, with
`source=onedrive`, 45 sheets, and a `US$ SCOTCH PARTS` preview of 11,221 rows.
The preview count is the sheet inventory count; the materialized/calculation
record is 11,219.

`docs/acceptance/evidence/connected_core_20261028/employee_calculation.json`
records the upstream binding:

- `provider=onedrive`
- `external_id=01P3INOW7U35MJ76UHXZFLQBL4A2WXP5CG`
- `content_hash=2abb1bf40ec31d131e5ae96abb173ac463426ef7`
- `source_row_count=11219`, `materialized_row_count=11219`, `truncated=false`
- total `9958743.62` across 11,219 rows.

Assessment and export evidence independently carry the same upstream provider,
file id and version.

## Current catalog state

The current live catalog at
`/Users/rushiparikh/projects/atom/backend/data/atom.db` contains no
`onedrive`-sourced entry for that workbook. Its `Consolidated Price List 2019`
rows are `zoho_workdrive` with different versions and row counts (11,231 and
11,128 for the relevant sheets), and the Zoho WorkDrive access token expired on
2026-10-24.

## Reconciliation

The earlier OneDrive claim is **historically supported** by the preserved
ingestion and calculation receipts. It is **not currently reproducible** from
the live catalog: the current database does not contain that OneDrive item, and
the named rows are Zoho WorkDrive with different versions.

Therefore the claim is qualified as:

> A genuine OneDrive ingestion of `Consolidated Price List 2019.xlsx` was
> recorded on 2026-10-28 with file id
> `01P3INOW7U35MJ76UHXZFLQBL4A2WXP5CG`, version
> `2abb1bf40ec31d131e5ae96abb173ac463426ef7`, 11,219 materialized rows and a
> certified sum of `9,958,743.62`. The current live catalog no longer contains
> that OneDrive entry; current price-list rows are Zoho WorkDrive versions.

This does not retroactively turn the historical receipt into a current live
read. The raw files remain unchanged. The failed current Zoho gate is preserved
at `docs/acceptance/evidence/durable_assignment_20261029/live-connected/gate-result.json`.

## Replacement live retrieval gate

The accessible Microsoft workbook used for the current live retrieval gate is
an **Outlook attachment**, not a OneDrive file:

- catalog entry `00399616-42f7-4f7d-8867-822752b15a46`
- source `outlook`
- file `HARSLE press brake stock price list.xlsx`
- sheet `库存产品`
- column `Price`
- 8 rows; exact sum `216,700`
- content hash `e0a7fb8a1b4757b7f6bef882b19cc4588d66246e`

Its predeclaration and passing gate are under
`docs/acceptance/evidence/durable_assignment_20261029/live-connected/guided/`.
