# Connected-data core status — 2026-10-28

Status: **connected assessment slice accepted; overall successor release remains
open on one live-source refresh boundary.** R3 remains the frozen functional
release. Nothing here is a deployment or a successor tag.

## What now passes

| Boundary | Result |
|---|---|
| Real connected source | Microsoft Graph Outlook/OneDrive grant active; Zoho WorkDrive remains expired and unused |
| Connected file ingestion | `Consolidated Price List 2019.xlsx`; 11,463,449 bytes; 45 sheets; 3,222,905 chars; 159 s |
| Workbook materialization | 45 dataset entries; `US$ SCOTCH PARTS` complete at 11,219 rows; `truncated=false` |
| Formula ingestion/evaluation | 733 formula cells; same-sheet `#40 TOOLING!M5 = 0.4`; cross-sheet `N5` resolves two dependencies |
| Server-resolved connected binding | Catalog reference + active version resolved in the canvas workspace; authoritative Parquet read; no rows/paths/hashes accepted from the client |
| Two identities | Canvas snapshot `b92aaf07eb1d219b` and OneDrive content hash `2abb1bf40ec31d131e5ae96abb173ac463426ef7` retained separately; snapshot labelled local; no writeback |
| Taught assessment v1 | 18/18 rows assessed, completed/certified, 16 APPROVE + 2 REVIEW, served `deepseek-flash`, 12.81 s |
| Correction + unfamiliar records | CNC changed REVIEW→HOLD; 22/22 rows assessed, completed/certified, 20 APPROVE + 2 HOLD, four unfamiliar subjects included, 12.03 s |
| Full-set calculation | 11,219 rows, total `9,958,743.62`, not the displayed page |
| XLSX export | 11,219 rows; reopened total matches; download bytes match |
| DOCX | Real 38,200-byte document with two tables (19 and 23 rows), correction section, sources; reopened and downloaded |
| PPTX | Real 36,017-byte deck with 3 slides and native tables; reopened and downloaded |
| Connected email | Outlook MIME with one workbook attachment; editable reply draft saved and reopened; no send |
| Repeat sync | Completed `unchanged=True skipped`; no duplicate logical records observed |
| Restart | Same retrieval total/version; fresh 5/5 certified assessment; drafts and artifacts reopened |
| Data/Settings browser | Connected state, scope, last success, coverage, failure, retry, disconnected/stale and restored states all exercised at `localhost:3003/settings` |
| Negative controls | Wrong workspace, guessed id, stale version, inactive source, revoked grant, disconnected source, revoked-grant chat retrieval (no cached total), client path/hash/rows, incomplete materialization, blank/duplicate subject, snapshot-writeback claim |

Evidence: `docs/acceptance/evidence/connected_core_20261028/`
Detailed run: `docs/acceptance/EMPLOYEE_JOB_2026-10-28.md`
Ledger: `docs/acceptance/CONNECTED_CORE_LEDGER_2026-10-28.json`

## Real defects found and fixed

1. **Natural-language ordering predicate.** “Unit Price is greater than 10000.”
   was parsed as equality against the word “greater”, and a sentence-final
   period made the numeric literal a string. Fixed in
   `core/table_selection.py`; controls added.
2. **Assessment projection.** A predicated assessment selected only the
   predicate column, so the subject column never reached the evidence index.
   Assessment now requires all physical columns while other select operations
   keep their existing projection.
3. **DOCX core-property limit.** Multi-source provenance exceeded Word’s
   255-character core-property cap and aborted document creation. Truncated in
   `core/office_service.py`; regression test added.
4. **Browser ingest retry.** The shared `startIngestJob` helper omitted
   `Content-Type: application/json`, causing a 422 before job creation. Fixed
   in `frontend-nextjs/lib/ingest-jobs.ts`; the browser retry now creates and
   completes a job.

## Still open

- **Live changed-byte refresh.** The only remaining job-protocol step is
  modifying the OneDrive source, syncing, and verifying updated retrieval.
  That requires source writeback, which the work order forbids. Verified
  instead: real unchanged repeat sync, explicit rebind with assessment-reuse
  invalidation and retained prior provenance, plus a changed-version control
  at the catalog/materialization boundary in unit tests.
- **Multi-user Office authorization.** Per-file Office path authorization is
  still unsupported; single-user restrictions remain.
- **Cost.** The structured review route does not persist token usage; latency
  and memory are recorded, but no cost figure is claimed.
- **Zoho WorkDrive.** Refresh still returns `invalid_client`; owner
  reauthorization is required and was not bypassed.
- **Microsoft token expiry.** The Graph access token expired at
  `2026-10-29T00:27:28Z`, after the evidence run. No refresh, rotation or
  reconnect was performed; further live runs require the owner to reconnect.

## Release position

- R3 tag unchanged: `expanded-core-2026-10-28-r3` → `68b949409`.
- No successor tag, release package, deployment, email send, source writeback
  or credential rotation was performed.
- The connected assessment slice is accepted for its demonstrated scope; the
  overall exit condition for a successor release is not claimed because the
  live changed-byte refresh was not executed.
