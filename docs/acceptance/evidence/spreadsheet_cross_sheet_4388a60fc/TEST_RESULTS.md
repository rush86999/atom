# Cross-sheet formula required-input validation — test results

Prior repair source: `db0b52d0fba5dd8b7604930539d021f9c2abf1a8`  
Cross-sheet source: `7bd2731075c71a65130aea9def8b942982fc6c70`  
Final test source: `4388a60fc7c2e12e2fd93551df24776d05223043`

Scratch SQLite/Parquet only; Python 3.14 existing venv; no live
provider/DB/credential/send/spend, no installs.

## Root probe

```
python -m pytest /private/tmp/root-cross-sheet.8Ujn0v/test_cross_sheet.py -q
```

Result: **1 passed** (`root-cross-sheet-probe.log`). Before the repair this
omitted the sibling-sheet required-input gap.

## New controls

```
pytest backend/tests/test_spreadsheet_dispatch_formula_repair.py -q
```

Result: **10 passed** (`new-cross-sheet-controls.log`).

New coverage:
- exact root cross-sheet negative (`Inputs!C3` blank -> required gap);
- populated cross-sheet twin computes;
- real `DatasetEntry` catalog resolution with `prefer_hash` selects the same
  workbook version and does not read another version's parquet;
- explicit zero is supplied, not a gap;
- raw CellBook blank-as-zero arithmetic still computes while the application
  result remains incomplete.

## Bounded gate

```
TESTING=1 DATABASE_URL=sqlite:///... ATOM_DATA_DIR=... ATOM_OFFICE_DIR=... \
python3.11 /private/tmp/atom-agent-cli/run_bounded_test_gate.py \
  --cwd .../backend --profile bounded -- \
  python -m pytest \
    tests/test_spreadsheet_dispatch_formula_repair.py \
    tests/test_dataset_aggregation.py \
    tests/test_formula_engine.py \
    tests/unit/test_sheet_dataset_service.py \
    tests/unit/test_sheet_dataset_formulas.py -q --tb=short
```

Result: **118 passed** (`bounded-gate-4388a60fc.log`).

The prior 113-test gate is preserved and expanded; the unchanged failure-first
campaign was not rerun.

## Boundaries

No new engine/catalog; no deferred Search/format/concurrency claim; PR843/844
branches and root integration untouched.
