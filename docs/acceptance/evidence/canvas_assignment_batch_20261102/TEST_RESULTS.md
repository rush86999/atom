# Canvas assignment batch — results

Executed source: `acc22b9283bc` (clean). Branch
`codex/brennan-canvas-successor-20261101`.

## Focused tests

| Scope | Result |
|---|---|
| Canvas focused suite (12 files, including assignment integration) | **122 passed** |
| `tests/test_canvas_typed_fields.py` | **25 passed** |
| `tests/test_canvas_assignment_integration.py` | **5 passed** |
| `tests/test_assignment_routes.py tests/test_assignment_executor.py tests/test_assignment_quote.py` | **167 passed** |
| Verifier canvas boundaries probe | **3 passed** |
| Frontend canvas capability suites | **7 passed** |

Logs: `focused-tests.log`, `typed-tests.log`, `assignment-tests.log`,
`assignment-regression.log`, `verifier-boundaries.log`, `frontend-tests.log`.

## Browser journey

`scripts/acceptance/canvas_typed_canvases_local.py` -> **17/17 checks**, no
page errors.

- Three canvases created/configured/bound through the normal `/canvas` UI.
- Typed receipt starts an ordinary assignment from the industrial quote
  canvas: `run_id` returned, receipt-only assignment completed.
- Industrial quote `350.00 USD`, service proposal `630.00 CAD`, queue
  `170.00 USD / 3 exceptions`.
- Source replacement old answer `409`; no edit to replacement `B`; new
  question for `B`; completion `2000.00`.

## Action controls (scratch backend)

- Registered `connected.outlook.create_draft` behind the production action
  registry; controlled service only. One approved draft, body `350.00 USD`.
- Duplicate execute/approval and a fresh executor: no second draft.
- Canvas edit during approval: `canvas.action` final recheck fails, zero
  drafts.
- Manifest/action revocation during approval: manifest recheck fails, zero
  drafts.
- Teaching proposal is shadow; agent journal unchanged. Explicit promotion
  writes one lesson; duplicate promotion returns `already_promoted`; missing
  approval `403`; stale receipt/revision `409`.

## Runtime identity

- Backend pid `22696`, source `acc22b9283bc`, instance
  `acc22b9283bc.22696.1793625234`, clean.
- World `canvas-successor-20261101-assignment`.
- Frontend build `X_PhH8Q4l6qVCB2K0XQLf`, `atom-frontend` healthy on
  `127.0.0.1:3133`.
- Backend `127.0.0.1:8092`.

## Boundaries

No live provider action; controlled Outlook only. No assignment-owned
missing-value resume; canvas clarification remains the path for incomplete
receipts. Teaching promotion is explicit human approval. Connected acceptance
remains `6431bcb78`; historical 111/123 unchanged.
