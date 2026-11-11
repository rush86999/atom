# Live-value freshness repair — test results

Prior cross-sheet source: `7bd2731075c71a65130aea9def8b942982fc6c70`  
Live-value source/head: `a4e4aff6067ad2ff0e1de00ac035a5348c5c1442`

Scratch SQLite/Parquet only; Python 3.14 existing venv; no live
provider/DB/credential/send/spend, no installs.

## Root overlay probe

```
python -m pytest /private/tmp/root-overlay.bzZwbF/test_overlay.py -q
```

Result: **2 passed** (`root-overlay-probe.log`) for live overlay values `0`
and `3`.

## New overlay controls

```
pytest backend/tests/test_spreadsheet_dispatch_formula_repair.py -q
```

Result: **12 passed** (`new-overlay-controls.log`).

Exact totals:
- live `C3=0` → **150**;
- live `C3=3` → **450**;
- genuine blank `C3` still names the required-input gap and publishes no
  complete total.

Explicit zero is supplied; raw CellBook Excel blank-as-zero arithmetic is
unchanged; stale blank membership no longer overrides a live resolved operand.

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

Result: **120 passed** (`bounded-gate-a4e4aff60.log`). The prior 118-test gate
is preserved and expanded. The historic failure campaign was not rerun.

## Boundaries

No new engine/catalog; no deferred Search/format/concurrency claim; PR843/844
branches and root integration untouched.
