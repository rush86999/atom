# Calculation control — exact captured ask — 2026-10-28

Runs the exact captured ask against the preserved `vendor_loop.csv`
materialized frame from the failed UI world:

> What is the total Invoice Amount for Open invoices in vendor_loop.csv?
> Use a sum and cite the rows.

The model planner is **unavailable** (`llm_service=None`). The deterministic
lane binds the sheet/version, resolves `Invoice Amount` as the named measure
and `State = Open` as the predicate from the frame, and executes through the
validated aggregate path.

Result (`result.json`):

- status `complete`; operation `sum`; measure `Invoice Amount`;
- selected **3** open rows; 1 closed row not selected;
- total **22200.00** (`3200 + 7000 + 12000`);
- source version `0a84a5f50661bc8a7917d158bcd36cad5b3f0262`;
- row citations `IN-7301` (row 2, cell B2), `IN-7302` (row 3, B3),
  `IN-7303` (row 4, B4);
- no gaps.

The preserved world is read-only here; no database or product table was
written.

## Note on the old UI script's expected number

The temporary failed-loop driver checked for `23800`; the authoritative
fixture sums to `22200`. The failed evidence itself contains no total, so this
does not change that evidence. The final UI loop, if run, must use the
fixture-derived `22200`, not the stale check value.
