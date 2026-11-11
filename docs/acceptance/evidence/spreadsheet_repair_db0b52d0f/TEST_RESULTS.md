# Spreadsheet dispatch + formula required-input repair — test results

Executed source: `db0b52d0fba5dd8b7604930539d021f9c2abf1a8`  
Base/parent: `50a5dffd71bf2cc02198f14965f4f757ac96a095`

Python 3.14 existing venv; scratch SQLite/LanceDB and temporary parquet only.
No live provider/DB/credential/send/spend, no installs, no world build/delete.

## Failure-first on parent 50a5dffd

```
TESTING=1 DATABASE_URL=sqlite:///... ATOM_DATA_DIR=... ATOM_OFFICE_DIR=... \
python -m pytest backend/tests/test_spreadsheet_dispatch_formula_repair.py -q
```

Result: **4 failed, 1 passed** (`failure-first-parent-50a.log`).

- missing `required_formula_input_gaps` helper;
- aggregate request still hit item probe (no aggregate block);
- FormulaResult did not carry required-input gaps;
- blank formula dependency produced a non-finite/incomplete evaluation without
  the required-input gap refusal.

## Final controls

```
TESTING=1 ... python -m pytest backend/tests/test_spreadsheet_dispatch_formula_repair.py -q
```

Result: **5 passed** (`new-controls-db0.log`).

## Bounded regression gate

```
TESTING=1 ... python3.11 /private/tmp/atom-agent-cli/run_bounded_test_gate.py \
  --cwd .../backend --profile bounded -- \
  python -m pytest \
    tests/test_spreadsheet_dispatch_formula_repair.py \
    tests/test_dataset_aggregation.py \
    tests/test_formula_engine.py \
    tests/unit/test_sheet_dataset_service.py \
    tests/unit/test_sheet_dataset_formulas.py \
    -q --tb=short
```

Result: **113 passed** (`bounded-gate-db0b52d0f.log`).

Covered: aggregate-before-probe dispatch, ordinary item lookup unchanged,
deterministic aggregate block pass-through, formula dependency gap naming,
formula result exposing no computed value when a required input is blank,
existing dataset aggregation/formula/sheet behavior.

## Boundaries

No new engine/catalog; no deferred Search/format/concurrency claim; PR843/844
branches and root integration untouched.
