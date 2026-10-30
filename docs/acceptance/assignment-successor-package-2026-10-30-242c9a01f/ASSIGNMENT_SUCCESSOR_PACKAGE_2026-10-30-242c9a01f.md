# Assignment successor package — 2026-10-30-242c9a01f

Status: **successor candidate packaged; current acceptance passed; deployment
requested but not authorized; real-provider sending remains separately
unauthorized.**

This package preserves the frozen prior product `a96484324` and rollback
`901e5d773`. It adds exact attachment-byte approval binding and current
acceptance coverage for the remaining core-goal boundaries. It does not deploy,
create `config/APPROVED`, change credentials, send a real message or write to a
connected source.

## Identity

| Item | Value |
|---|---|
| Product commit | `242c9a01ff9aebb0467ad7a619ea7e4e468f454d` |
| Release tag | `assignment-successor-2026-10-30-242c9a01f` |
| Product tree | `c20bb599ff7ab65913f42cd14a5a93012b6817c93b6b0b5eddfb7c056e24c9b7` |
| Rollback | `901e5d77348e0c7b85b1f1291cbeb0fc50eb2ff0` |
| Frontend build | `K3N6o-mTkpSVJ7sj00FLu` |
| Deployment kit | `scripts/deployment/assignment_successor_2026-10-30_242c9a01f/` |
| Kit tree SHA-256 | `629f369dfc98472e786b0e9ba2499f95958ffdf6abfbd349401e1d220f061de5` |
| Prepared root | `/Users/rushiparikh/projects/atom-deployments/assignment-successor-2026-10-30-242c9a01f` |

## What this successor changes

- Staged email attachments carry SHA-256; assignment send planning requires a
  hash for every attachment id and rejects ids without one.
- The approval payload includes the attachment hash map. Changing attachment
  bytes invalidates approval.
- `EmailCanvasService.send_email` re-hashes the bytes actually resolved and
  refuses a mismatch before any provider transport.
- Current acceptance tests add: 24-sheet workbook (all sheets, leading-zero
  ids, blanks), cross-sheet formula text, teach → correct → wrong-context →
  restart journey, two differently shaped canvases using the same operations,
  and restart after artifact creation without recreating work.

## Current acceptance

- Release-affected suite: **578 passed, 2 skipped**.
- Targeted core suite: **127 passed**.
- Deployment-kit controls: **22 passed**.
- Mapping browser flows on this product:
  - B: gap → `Amount` → `35.00 USD`, mapping revision 2.
  - C: no source unit → explicit USD → `75.00`.
  - Correction: List Price `100.00` → Contract Price `80.00`, revision 2 → 3,
    scoped restart, unrelated Tax mapping preserved.
  - Waiting restart: reject → backend restart → confirm `35.00`, one applied
    calculation, durable artifact/reload.
- Data handoff: 50 users / 481 dataset entries / 557 goal runs; 1,205
  artifact/dataset files; 16,305 operations with 0 binding mismatches; 4
  current deliverable hashes verified; 21 pre-existing missing historical
  dataset paths recorded, none referenced by a current assignment.
- Memory: 44,908 documents; 31,415 business facts; 289 experiences; 1,726 chat
  messages; 2,331 Zoho rows; small root tables. The 7.23 GiB communications
  archive and 29.5 GiB `default_shared` workspace remain at source and are not
  searchable in the production copy.
- Rollback re-verified against the refreshed data: `901e5d773` starts healthy,
  same data/artifact world, 0 binding mismatches, no database restore and no
  new interactive approval. Memory retrieval identical before/after restart.

## Cutover freshness boundary

The data snapshot is logically current (0 table changes, memory unchanged, 461
referenced files checked). Production cutover is deliberately refused while the
live source writer is active: pid `19046` (`python3.14`) still holds the source
database/WAL. The deployment transaction now requires quiescence and re-runs
the logical check after backup and immediately before activation.

Before deployment the owner must either stop that writer with operational
authorization and refresh if the source advanced, or authorize an equivalent
quiescence window. The runbook's “Cutover freshness and refresh” section has the
exact commands.

## Supported envelope and explicit limits

- Two unrelated domains are demonstrated; arbitrary domain competence is not
  claimed.
- The mapping workflows above are demonstrated; arbitrary schema
  understanding is not claimed.
- The large-workbook subset covers all sheets, leading-zero identifiers,
  blanks, same/cross-sheet formula text and full-frame aggregation; arbitrary
  Excel compatibility and unsupported formulas as certified recalculation are
  not claimed.
- The canvas adapter is the supported table adapter; every future canvas
  component is not claimed.
- Microsoft-connected ingestion is the declared scope; other connectors are
  optional and not repaired merely to enlarge coverage.
- Embedded image/chart interpretation is excluded.
- One worker per assignment is the verified topology; autonomous third-party
  research is not claimed.
- Real-provider sending is not authorized by this package.

## Evidence

- Production package evidence:
  `docs/acceptance/evidence/durable_assignment_20261030/successor-package-242c9a01f/`
- Package manifest:
  `docs/acceptance/assignment-successor-package-2026-10-30-242c9a01f/assignment_successor_manifest.json`
- Preparation report:
  `docs/acceptance/PRODUCTION_PACKAGE_PREPARATION_2026-10-30-242c9a01f.md`
- Deployment decision:
  `docs/acceptance/DEPLOYMENT_DECISION_242c9a01f_2026-10-30.md`
- Real-send request:
  `docs/acceptance/REAL_PROVIDER_SEND_QUALIFICATION_2026-10-29.md`
- Goal ledger: `docs/acceptance/PRODUCT_GOAL_LEDGER_2026-10-29.md`
