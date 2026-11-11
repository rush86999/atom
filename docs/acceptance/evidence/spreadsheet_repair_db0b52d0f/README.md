# Spreadsheet dispatch + formula required-input repair

Status: **frozen source/test candidate for independent review.** No merge or
self-acceptance.

Base: `50a5dffd71bf2cc02198f14965f4f757ac96a095`  
Executed source: `db0b52d0fba5dd8b7604930539d021f9c2abf1a8`

## Confirmed gaps (failure-first on parent 50a5dffd)

`failure-first-parent-50a.log`: **4 failed, 1 passed**.

1. `answer_from_datasets` ran Stage-0 candidate/item probes before the SQL
   path. A row-predicate aggregate containing an identifier-like token could
   return a probe instead of the existing deterministic selection/aggregate.
2. Formula totals used CellBook's Excel blank-as-zero arithmetic without the
   application completeness check. A blank required quantity/price/currency
   dependency could publish a complete total.
3. `sheet_grid_from_parquet` did not recognize pandas NaN as a known blank,
   surfacing a non-finite operand instead of the required-input gap.

## Repair (existing mechanisms only)

- `answer_from_datasets` now detects an aggregate operation first and
  delegates to the existing `aggregate_named_dataset` (NL-to-SQL selection +
  Decimal aggregation). `render_dataset_answer` passes the deterministic
  aggregate block through. Ordinary item lookup remains unchanged.
- `required_formula_input_gaps` reuses the existing frame role resolver and
  `col_letter` contract to name blank required quantity/price/currency
  dependency cells before a formula total is published.
- `FormulaResult` carries the gaps; `workbook_calculation_result` publishes no
  value and names the gap, never zero/fabricated. The raw formula engine
  arithmetic remains available as evaluation semantics, but the application
  result is incomplete.
- `sheet_grid_from_parquet` treats pandas NaN as a known blank.

No new SQL engine, formula evaluator, catalog, store, router or migration.

## Verification

| Check | Result |
|---|---|
| Failure-first new controls on parent `50a5dffd` | **4 failed** |
| New controls at final source | **5 passed** |
| Bounded regression gate via `run_bounded_test_gate.py` | **113 passed** (`bounded-gate-db0b52d0f.log`) |
| Gate groups | new dispatch/formula controls + dataset aggregation + formula engine + sheet dataset service/formulas |

The controls prove: aggregate asks skip the item probe and reach the existing
aggregate executor; ordinary item lookup remains; blank formula dependencies
produce a named gap and no complete value; and the result exposes the gap.

No live provider, database, credential, send or spend was used. No world was
built or deleted; no installs.

## Boundaries

Scope is the supported synthetic-TXT/XLSX workbook job path and formula
reference path. No deferred global Search, original-binary download, format
breadth, model grounding, PostgreSQL concurrency or Goal 11 claim. PR843/844
branches and their integration remain root-owned and untouched.
