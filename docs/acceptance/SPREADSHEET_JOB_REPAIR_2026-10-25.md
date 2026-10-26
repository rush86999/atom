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
   executor: SQL selects ROW IDENTITIES only (`__sheet_row` as a plain
   column); row references must be exact, unique integers present in the
   bound workbook/sheet/version. Quantity, price, currency, status and item
   identity are re-read from the authoritative materialized frame, never
   from SQL projections/aliases/CASE/casts. Decimal aggregation then runs
   over the full eligible set with no SQL totals/LIMIT.

### Evidence-binding correction (successor to `04fd550be`)

The prior candidate still let a generated projection supply calculation
values: a `CASE`/constant/cast could replace a missing quantity or price
before aggregation. The successor closes that trust boundary:

- generated SQL determines MEMBERSHIP only; DuckDB's own
  `json_serialize_sql` AST requires the outer FROM to be the registered
  BASE_TABLE and the outer projection to contain exactly one plain
  `__sheet_row` column reference (no CASE/cast/alias/star). Comments,
  dollar-quoted strings, CTEs, derived tables, joins, outer or nested
  `USING SAMPLE`/`TABLESAMPLE`, and case-variant header collisions cannot
  hide that shape from the parser; the exact `__sheet_row` output name is
  required;
- row references are validated as exact integers (floats/fractional values
  are rejected), unique, and present in the bound workbook/sheet/version;
- CTE, derived-table, comma-join and other-table forms that could fabricate
  real-looking row references are rejected;
- all quantity/price/currency/status/identity values are read back from the
  authoritative materialized frame, so projections are ignored;
- missing/aliased role fields are filled from exact generic FRAME column
  names (`Qty`/`Quantity`, `Unit Price`/`Price`, `Currency`, etc.)
  BEFORE the required-column SQL guard, so omitting a role cannot disable
  gap protection; required-input predicate columns are read from the
  DuckDB AST (WHERE/HAVING/QUALIFY/GROUP across nested selects), so a
  quoted identifier, literal or comment containing `limit`/`order by`
  cannot hide `"Qty" > 0`; projected columns may not be aliased (including
  nested SELECTs); `COLUMNS(...)` expansion and `#n` positional references
  are rejected; struct/array/JSON field extraction, whole-row `->`/`->>`,
  `json_value`/`json_each`/`query()` table functions, random()/uuid()/
  setseed(), and FROM column-alias lists are rejected at any depth;
  predicate COLUMN_REFs must resolve to physical frame columns; extra
  projection items may be plain frame columns/constants only (no
  functions/unnest/CASE/casts/subqueries), so a projection cannot expand
  or drop rows; whole-row/relation refs (e.g. `main.df::JSON`), struct_pack
  and similar row serializers are rejected in predicates; calculation
  required/status roles are deterministically re-bound to the frame's
  single matching column (camelCase-aware; `UnitPrice`/`Amount`/decorated
  Price headers cannot displace Qty); multiple matches are ambiguous and
  fail closed; roles must be distinct; nested SELECTs/subqueries are
  rejected entirely, closing nested FETCH/aggregate evasions; predicate
  checks cover all quantity/price/currency-like columns, not just the
  mapped role; `__sheet_row` is rejected as any calculation role;
- if a planner returns `__sheet_row` as the identity role while projecting
  a real business key, the role is corrected deterministically to that key;
  values still come from the frame.

Local controls include the malicious `CASE` projection (0055 remains a
missing-quantity gap; no invented 75 CAD), a constant price under the
original column name, fabricated/fractional row references, and the
ordinary positive twin (8050.00 CAD / 3999.96 USD). This closes value
substitution; it does NOT prove that the generated selection predicate
matches the user's intent — predicate correctness is tested separately.
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
| PO Register, approved rows, totals by currency | `ab1ae599-87ef-4553-b04d-3f41f6a7b666` | CAD **8050.00** (3 rows, qty 10); USD **3999.96** (1 row, qty 4); cancelled row excluded; rows 2/3/4/6 with C/D provenance |
| Adjustments, approved rows, name missing inputs | `c26f01bd-c618-41c1-89ae-3fb72597ffeb` | Known subtotal **−700.00 CAD**; gap **0055**, missing quantity at **C5**; complete/grand total withheld |
| Formula reference, D8 | `491241f7-c20e-4ea0-a9d7-387193d8a5d4` | **8050.00** neutral workbook arithmetic; 7 dependencies; no pricing policy |
| Formula reference, row-qualified D8 | `5638fcb9-6939-431d-98da-f08290b76b6e` | **8050.00**; same neutral basis |
| Aggregate with no sheet named | `8628ddc5-2d77-4f16-9b31-857649cf2603` | `SHEET AMBIGUOUS`; no total computed |
| Explicit missing sheet | `604f0f86-b860-4c7e-8743-dd64e716d815` | `SHEET NOT FOUND`; no fallback; no total computed |
| Ordinary item lookup | `e00fcfe5-59fc-49cb-8b26-d96a9a711da9` | `0007` remains ambiguous between Adjustments row 2 (D2 = 100) and PO Register row 2 (D2 = 1,250) |

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
627 passed, 4 skipped, 2 xfailed, 11 failed
```

The same 11 failures reproduce on parent `c912375de` (refresh verdict/fixture
tests unrelated to this job). New controls in `tests/test_dataset_aggregation.py`
cover: operation precedence, whole-token/longest/filename sheet binding
(including space-containing filenames), generic sheet words without a cue,
ambiguous/missing sheet, DISTINCT/UNION/path/missing-`__sheet_row` rejection,
CASE/constant projection substitution, fabricated/fractional row references,
CTE/derived-table identity fabrication via comments and dollar-quoted
strings, outer/nested `USING SAMPLE`, case-variant header shadowing,
missing-role inference before the SQL AST predicate guard, predicate
columns after `limit`/`order by` tokens in literals/comments, predicate
aliases/COLUMNS/positional/nested aliases, struct/array/JSON/whole-row
field extraction, query()/json_each table functions, random()/uuid(),
non-frame predicate names, whole-row/relation refs, struct_pack,
projection unnest/CASE expansion, nested SELECT/FETCH/aggregates,
deterministic role rebinding, role substitution/duplicates, decorated/
camelCase price headers, ambiguous role columns, meta-role rejection,
COALESCE/IFNULL/NULL filtering of
required inputs, quoted keyword columns, string NaN/Inf/null gaps, duplicate
rows, version ambiguity, truncated materialization, display cap, formula
grammar ordering, neutral priced-scope refusal, neutral stored-value record
shape, and refreshed aggregate receipt replacement.

## Documented limitation

The selection guard rejects filters on required-input columns (quantity,
price, currency) because filtering a row out is indistinguishable from
erasing a missing-input gap. That also rejects legitimate asks such as
“approved CAD rows.” Separating user-requested selection authority from
missing-input protection is future work; this correction intentionally does
not broaden that behavior.

Role binding is deterministic when a frame header matches a generic role
hint (Qty/Quantity, Unit Price/Price, Currency, Status). If a required
header matches none of those hints, the planner's role field is still
trusted after conflict/ambiguity checks; failing closed on zero hint matches
is future work and is not exercised by this workbook.

## Freeze decision

The candidate is frozen for review. Deployment is intentionally not part of
this record; the live pilot remains `c912375de` until a separate served-update
approval is given.
