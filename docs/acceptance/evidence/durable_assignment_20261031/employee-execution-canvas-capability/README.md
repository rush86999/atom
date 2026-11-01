# User-created canvas capability — normal application

A blank canvas was created through the normal canvas UI, an employee was
attached, a table capability manifest was installed, and a CSV was bound
through the capability panel.

## Results

| Step | Result |
|---|---|
| Effective operations | bind/read at install; calculate/edit/export used through the panel |
| Initial sum | **290.00** |
| Edit row 2 Amount 75 → 110 | readback **110**, success |
| Recalculated sum | **325.00** |
| Export | real XLSX, 5,690 bytes |
| Reload | `revision 2 · 4 rows` |
| Page errors | none |

`canvas.json` records the manifest, bound rows, operation receipts and export
hash; `canvas-export.xlsx` is the artifact; `screenshot.png` is the completed
canvas.

## Scope

Supported table adapter only; this is not a claim for arbitrary spreadsheet
controls, future canvas components or model-dependent assessment. The
deterministic assessment path is qualified separately.
