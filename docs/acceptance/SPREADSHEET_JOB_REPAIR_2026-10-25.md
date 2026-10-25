# Spreadsheet job repair — acceptance record (2026-10-25)

**Candidate:** `fix/spreadsheet-aggregation` on parent `c912375de81b55465e61fe468bf0bc2b405fd206`
**Work order:** `docs/acceptance/SPREADSHEET_JOB_REPAIR_WORK_ORDER_2026-10-25.md`
**Status:** candidate frozen after served scratch acceptance; **no deployment or restart of the live pilot**.
**Live pilot:** still `c912375de` (backend PID 54976, frontend PID 55007).

## Why the original ask failed

The request was routed through item matching before operation selection:
`_datasets_named_file_block` looked for item codes, and
`answer_from_datasets` probed identifiers before its SQL path. “Approved rows”
became item text, “PO Register” became a candidate scope, and no lane reached
a row-selection/aggregation plan. The workbook itself was already materialized
and its inputs were present.

## Repair shape

1. **Operation before item matching.** The existing accepted-operation
   classifier now distinguishes `aggregate`, `formula_reference`, `refresh`,
   `re-run`, and ordinary `read`. Explicit refresh/re-run and comparison keep
   precedence. Aggregate dispatch happens before `_resolve_active_items`.
2. **Controlled execution first.** `core/dataset_aggregation.py` adds a
   deterministic adapter over the existing sheet-dataset planner and DuckDB
   executor: detail-row SELECT only, `__sheet_row` and identity required,
   Decimal aggregation over the full eligible set, no SQL totals/LIMIT.
3. **Completeness separate from summation.** Blank, empty, NaN/Inf sentinel,
   and null-like values are named gaps, never zero. A partial result publishes
   a known subtotal and withholds the complete/grand total. Provenance is the
   original sheet row and cell, not DataFrame position.
4. **Explicit scope.** Workbook filenames are stripped before sheet binding;
   catalog sheet names match as whole tokens with longest/containment
   resolution. A missing or unnamed multi-sheet scope is reported, never
   substituted. Truncated materialization withholds totals.
5. **Neutral formula reference.** `calculate formula for FILE.xlsx SHEET
   [row N] cell D8` (and the cell-first form) parses before the pricing
   grammar, evaluates through the existing `CellBook` /
   `sheet_grid_from_parquet` / `evaluate_reference` path, and records no
   pricing policy, proposed `Money`, or authorization identity. The pricing
   teaching gate is unchanged; neutral asks that carry `currency=`/`item=`
   are refused rather than converted into priced lookups.
6. **Delivery.** Deterministic aggregate blocks carry the result and its
   gaps; the ask lane does not replace them with the empty-item path. The
   formula lane derives completed/identity state from the calculation and
   strips the internal `[calc:result_id=…]` marker from user text.

## Served scratch acceptance (final candidate)

Scratch only: backend `:8121`, database
`atom-named-doc-scratch/data/atom.db`. The original requests were unchanged.

| Case | Session | Delivered result |
|---|---|---|
| PO Register, approved rows, totals by currency | `418e98cd-7bb6-4691-be3e-b791876679bd` | CAD **8050.00** (3 rows, qty 10); USD **3999.96** (1 row, qty 4); cancelled row excluded; rows 2/3/4/6 with C/D provenance |
| Adjustments, approved rows, name missing inputs | `7029bbfa-d5fd-4168-a175-c90b9cff5717` | Known subtotal **−700.00 CAD**; gap **0055**, missing quantity at **C5**; complete/grand total withheld |
| Formula reference, D8 | `ca47f822-0b1e-457b-ade8-66e9e8e0258d` | **8050.00** neutral workbook arithmetic; 7 dependencies; no pricing policy |
| Formula reference, row-qualified D8 | `0fbb11ad-74fe-48d4-942d-d4d5f3b297a3` | **8050.00**; same neutral basis |
| Aggregate with no sheet named | `41464758-3eab-436f-b803-33bdc6251fee` | `SHEET AMBIGUOUS`; no total computed |
| Explicit missing sheet | `58d93f54-6d37-4c92-93f6-7c3a64b4d1ca` | `SHEET NOT FOUND`; no fallback; no total computed |
| Ordinary item lookup | `bb51a247-766f-406b-be97-0e5b38503302` | `0007` remains ambiguous between Adjustments row 2 (D2 = 100) and PO Register row 2 (D2 = 1,250) |

PO response also reports `Sheet rows: 5; selected: 4; not selected: 1` and
`Sheet status counts: Approved=4, Cancelled=1`, making the exclusion auditable.
Adjustments reports `Approved=3, Cancelled=1`.

## Safety and persistence checks

- Source workbook SHA-256 values are unchanged before/after:
  - `spreadsheet_job_20261025.xlsx` = `888ce157…e07a5`
  - `spreadsheet_job_totals_20261025.xlsx` = `4a1ffa4f…3517b1`
- Every acceptance session persisted its assistant message in `chat_messages`;
  the required values, provenance, and gaps are present in persisted history, and
  no internal `[calc:result_id=…]` marker appears in stored user-facing text.
- No canvas or canvas-audit rows were created after 18:57; the only canvas
  pre-dates the acceptance asks.
- Provider POSTs during acceptance were limited to the authorized set
  (`api.deepseek.com`, `openrouter.ai`, `opencode.ai/zen/go`,
  `localhost:11434`).
- The trained-agent evaluation remains paused.

## Tests

Focused suite (aggregation, routing, pending-file, workbook delivery, turn
program, source-ask, pricing):

```
612 passed, 4 skipped, 2 xfailed, 11 failed
```

The same 11 failures reproduce on parent `c912375de` (refresh verdict/fixture
tests unrelated to this job). New controls in `tests/test_dataset_aggregation.py`
cover: operation precedence, whole-token/longest/filename sheet binding
(including space-containing filenames), generic sheet words without a cue,
ambiguous/missing sheet, DISTINCT/UNION/path/missing-`__sheet_row` rejection,
COALESCE/IFNULL/NULL filtering of required inputs, quoted keyword columns,
string NaN/Inf/null gaps, duplicate rows, version ambiguity, truncated
materialization, display cap, formula grammar ordering, neutral priced-scope
refusal, neutral stored-value record shape, and refreshed aggregate receipt
replacement.

## Freeze decision

The candidate is frozen for review. Deployment is intentionally not part of
this record; the live pilot remains `c912375de` until a separate served-update
approval is given.
