# Durable assignment evidence — 2026-10-29

Created by `backend/tests/test_assignment_executor.py` with
`ATOM_ASSIGNMENT_EVIDENCE_DIR` pointed at this directory. The external
transport is a controlled outbox file, never a live provider.

- `commercial_evidence.json` — task revision, operations, operation
  bindings, approvals, receipts, decisions and final status for the
  commercial response.
- `eligibility_evidence.json` — the same record for the eligibility package.
- `commercial.docx`, `eligibility/eligibility.docx` — saved artifacts.
- `outbox.jsonl`, `eligibility/outbox-eligibility.jsonl` — one controlled
  transport record per approved effect.
- `records.xlsx`, `eligibility/qualification.txt` — source fixtures.
- `browser/` — Playwright run against the real assignment routes and executor
  with the environment-gated controlled outbox: both domains completed
  through the UI, approval was bound to the concrete payload, and the
  completed state survived a page reload. `browser/outbox.jsonl` has one
  record per approved effect; screenshots are `browser-A-completed.png` and
  `browser-B-completed.png`.
- `browser-start/` — the starting-boundary run: both objectives were entered
  through the product form, the correlated reply and approval were completed,
  and the assignments remained completed after a backend restart.
- `connected-guided/` — the real connected guided-start acceptance: a real
  scoped `DatasetEntry` and real Parquet rows, no mocked reader/catalog and no
  internal fixture paths. `connected_acceptance.json` records the typed
  binding, rows 2/3/4, `85.00` sum, `3` count, grounded artifacts, controlled
  approval/outbox and a durable reopen. `sum-artifact.docx` and
  `count-artifact.pptx` are the saved outputs.
- `browser-guided/` — the same two objectives started through the normal
  Assignments UI with scope-only discovery: approval, completion, reload, and
  completion again after a backend restart. The outbox body carries the
  result and source, not a placeholder.
- `browser-explicit/` — the advanced explicit-form run, kept separate from
  guided discovery.

No credentials, tokens, live recipients or production source changes are
present. No live send was performed.
