# Exact external reply identity — root verification

Runtime source: `fa6a047f6`. CI-only follow-through: `fe866bf55`.
Direct-step external replies bind exact run/wait, opaque reply identity and
canonical material. Exact repeats are idempotent; changed material refuses.
CAS retries reload authoritative state; old receipts are not evicted with the
short public conflict history.

## Recorded evidence

- `material-negative`: independent original explicit-ID defect, 1 failed.
- `legacy-negative`: changed unkeyed terminal reply borrowed an earlier receipt,
  1 failed before the root correction.
- `final-focused`: corrected direct identity controls, 17 passed (Python 3.14).
- `fa6-affected`: seven affected modules, 220 passed (Python 3.14).
- `fa6-affected-py311`: same seven modules, 220 passed (Python 3.11).

Counts overlap and must not be added. Each raw log retains its own original
spec, exit, executed source and final observed head; negative sources are not
relabeled as the corrected runtime. Earlier author-test scaffold failures
(empty workspace directories mistaken for artifacts and optional None vs [])
were harness defects and are not represented as product failures.

Python 3.11 explicitly loads the copied existing pytest-freezegun plugin
because that environment lacks automatic plugin installation; the exact helper
is retained. Python 3.14 uses its existing installed plugin. No packages were
installed. Commands use TESTING=1, unique SQLite/database/data/office/output
paths, no real application DB, and no model/provider/live external effect.
The completed 3.14 affected scratch world was archived with exact-byte checks;
its raw log/spec/exit remain unchanged here.

## Limits

This qualifies direct-step reply identity at scratch-DB/public API scope, not
the separate question/gap branch, elapsed days, multi-worker/soak, or general
autonomous coordination. Hosted verification and final independent PR review
remain separate. Runtime mechanism reuses existing task CAS and receipts.
