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

No credentials, tokens, live recipients or production source changes are
present. No live send was performed.
