# Cross-sheet formula required-input validation

Status: **frozen delta candidate for independent review.** No merge or
self-acceptance.

Base: `50a5dffd71bf2cc02198f14965f4f757ac96a095`  
Prior repair source: `db0b52d0fba5dd8b7604930539d021f9c2abf1a8`  
Cross-sheet production source: `7bd2731075c71a65130aea9def8b942982fc6c70`  
Final test source: `4388a60fc7c2e12e2fd93551df24776d05223043`

## Gap

The root cross-sheet probe (`root-cross-sheet.8Ujn0v/test_cross_sheet.py`)
uses a real sibling CellBook (`Inputs!C2/C3`) and a blank required quantity.
The first repair validated only the target sheet's columns/blank set, so the
sibling dependency gap was omitted and a total could still publish.

## Repair

- Formula dependencies are grouped by their resolved sheet.
- Each group is validated against that sheet's own `CellBook` values and
  known-blank set and its own frame columns/role mapping.
- Sibling books resolve through the existing `_FileSheetBooks.provider`,
  preserving the same-workbook-version (`prefer_hash`) isolation.
- Gaps include the sheet, row, identity where available, missing role and
  cell.
- Explicit zeros remain supplied values. The raw CellBook engine keeps
  Excel blank-as-zero arithmetic; the application result is incomplete and
  publishes no value when a blank required input contributes.

No new engine/catalog/store; aggregate dispatch and all prior controls are
unchanged. The prior failure-first campaign was not rerun.

## Verification

| Check | Result |
|---|---|
| Root cross-sheet probe | **1 passed** (`root-cross-sheet-probe.log`) |
| New cross-sheet/populated/version/zero/raw controls | **10 passed** (`new-cross-sheet-controls.log`) |
| Prior 113-test gate expanded with the new controls | **118 passed** (`bounded-gate-4388a60fc.log`) |
| `git diff --check` | clean |

Controls include the exact root cross-sheet negative, a populated twin that
computes, a real `DatasetEntry` catalog test proving `prefer_hash` selects the
same version and does not read another version's parquet, explicit zero as
supplied, and raw blank-as-zero evaluator semantics preserved.

## Boundaries

No live provider/DB/credential/send/spend, no installs/world copies. PR843/844
branches and root integration untouched.
