# Live-value freshness repair — cross-sheet formula operands

Status: **frozen repair candidate for independent review.** No merge or
self-acceptance.

Base: `50a5dffd71bf2cc02198f14965f4f757ac96a095`  
Prior cross-sheet source: `7bd2731075c71a65130aea9def8b942982fc6c70`  
Prior evidence head: `6fae2697391839650fdf38390d0bfeff06fde8ee`  
Live-value source/head: `a4e4aff6067ad2ff0e1de00ac035a5348c5c1442`

## Gap

The root overlay probe (`/private/tmp/root-overlay.bzZwbF/test_overlay.py`)
found two false incomplete totals. A sibling CellBook's live overlay adds the
current value (`C3 = 0` or `3`) to `values`, but CellBook retains the older
blank marker in `empty`. Validation trusted stale blank membership and
declared `C3` missing even though the effective resolved operand was present.

## Repair

`required_formula_input_gaps` now treats an effective resolved value as
supplied — including an explicit `0` — before considering stale blank
membership. A gap is reported only when the dependency has no resolved value
and remains genuinely blank. Sheet/cell/row/identity attribution is retained.

Raw CellBook Excel blank-as-zero arithmetic is untouched. Neutral evidence
blocks also expose `computed_value` for attribution consumers; the prose
answer still renders the computed value.

No new engine/catalog; aggregate dispatch and all prior controls remain.

## Verification

| Check | Result |
|---|---|
| Root overlay probe (`0` and `3`) | **2 passed** (`root-overlay-probe.log`) |
| New overlay/genuine-blank controls | **12 passed** (`new-overlay-controls.log`) |
| Prior 118-test gate expanded | **120 passed** (`bounded-gate-a4e4aff60.log`) |

Exact totals: live `C3=0` → **150**, live `C3=3` → **450**. The genuine blank
negative still reports the required-input gap. The historic failure campaign
was not rerun.

## Boundaries

No live provider/DB/credential/send/spend, no installs/world copies. Existing
evidence packets remain; PR843/844 branches and root integration untouched.
