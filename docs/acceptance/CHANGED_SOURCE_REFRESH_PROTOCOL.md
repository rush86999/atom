# Disposable changed-source refresh — prepared protocol

Status: **prepared; awaiting the one combined authorization.** The historical
production price list will not be modified.

## Exact configuration restoration

- Existing approved private source:
  `/Users/rushiparikh/projects/atom/backend/.env` (same Microsoft app id as the
  stored grant; values verified by presence/length only).
- Runtime destination:
  `/private/var/folders/sq/kf_272b520nc5wnsp27hq1h00000gn/T/opencode/atom-whole-app/backend/.env`
- Keys restored: `MICROSOFT_CLIENT_ID`, `MICROSOFT_CLIENT_SECRET`,
  `MICROSOFT_TENANT_ID`.
- Prepared command:
  `python scripts/acceptance/restore_private_microsoft_config.py --source /Users/rushiparikh/projects/atom/backend/.env --destination /private/var/folders/sq/kf_272b520nc5wnsp27hq1h00000gn/T/opencode/atom-whole-app/backend/.env`
- The script backs up the destination, writes only those keys, prints presence
  only, and never creates/rotates credentials or starts a user reconnect.
- Process precedence: `main_api_app.py` loads `backend/.env`, then root
  `.env`, then `.env.local` (override). The worktree has no root `.env` or
  `.env.local`; `backend/.env` is the effective private destination.

## Exact test-only OneDrive location

- Folder: `AtomAcceptance/connected-refresh-20261029-0120Z`
- File: `refresh_probe_f5f_20261029.xlsx`
- The folder/file are new, uniquely named, test-only, and safe to delete.
- No other OneDrive item is created or modified.

## Prepared workbook

Two sheets:

- `Inputs`: `Item`, `Qty`, `Unit Price`
  - `PROBE-001`, 2, 10.00
  - `PROBE-002`, 3, 10.00
- `Calc`: `Item`, `Qty`, `Unit Price`, `Line Total`
  - `Calc!D2 = Inputs!B2*Inputs!C2` → 20
  - `Calc!D3 = Inputs!B3*Inputs!C3` → 30

Local files:

- `docs/acceptance/evidence/connected_core_20261028/disposable_source/refresh_probe_f5f_baseline.xlsx`
- `.../refresh_probe_f5f_changed_expected.xlsx`
- `.../refresh_probe_f5f_manifest.json`

## Predeclared baseline

- Source version/hash: to be captured by the first product sync.
- Calc total: **50.00**
- Assessment policy: REVIEW when `Line Total >= 25`; APPROVE otherwise.
- Decisions: `PROBE-001` APPROVE (20), `PROBE-002` REVIEW (30).
- Coverage: 2/2 rows on `Calc`; no truncation.

## One changed input

- `Inputs!B2`: **2 → 3**
- Only input changed. The workbook is re-saved so Excel/OneDrive recalculates
  the cross-sheet formulas.

## Predeclared changed expected

- Calc formula values: `D2=30`, `D3=30`.
- Calc total: **60.00**
- Decisions: `PROBE-001` REVIEW (30), `PROBE-002` REVIEW (30).
- Baseline calculation/assessment/export receipts for the old version become
  stale and must not be reused.
- Prior version/provenance must remain attributable in the catalog and canvas
  `previous_bindings`.

## Checks after authorization

1. Restore the existing private Microsoft keys using the prepared command.
2. Restart the isolated backend; verify startup preflight reports configured.
3. Verify live refresh (`token_state=refreshed`, no reconnect).
4. Create the exact test folder/file and upload the baseline workbook.
5. Product-sync the file; record item id, version/hash, coverage, formula
   sidecar and baseline calculation/assessment/export.
6. Replace only the same test file with the changed workbook (one bounded
   source edit).
7. Product-sync again; verify changed hash, new materialization, old version
   superseded, stale assessment reuse invalidated and prior provenance kept.
8. Re-bind; calculate 60.00; assess REVIEW/REVIEW; export and reopen.
9. Restart and verify the new binding, calculation, assessment and download.
10. Preserve both versions and evidence; delete nothing until evidence is
    captured.

## Authorization requested

One combined authorization covering only:

- restoration of the existing approved Microsoft client settings to the
  destination above;
- creation and one modification of the exact disposable workbook above;
- product sync, calculation, assessment, restart and download verification.

Excluded: production price-list changes, general writeback, email send,
credential rotation/creation, deployment, model changes, Zoho repair and
multi-user ACL work.
