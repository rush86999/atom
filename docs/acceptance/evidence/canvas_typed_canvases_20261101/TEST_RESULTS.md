# Typed three-canvas successor — results

Executed source: `fa77cc2abf45ea17d3ab3ee8a07b9496a81c082c` (clean).
Branch: `codex/brennan-canvas-successor-20261101`.
This manifest commit is docs-only and was not served.

## Browser journey

Command shape:

```bash
cd /private/tmp/atom-canvas-successor
TESTING=0 PYTHONPATH=$PWD/backend \
  /Users/rushiparikh/projects/atom/backend/venv314/bin/python \
  scripts/acceptance/canvas_typed_canvases_local.py \
  --frontend http://127.0.0.1:3131 \
  --password-file <world>/canvas-password.txt \
  --agent-id <agent> \
  --out-dir <evidence>
```

Result: **13/13 checks passed**, no page errors. See `result.json` and
`run.log`.

| Canvas | Independent total | UI evidence |
|---|---|---|
| Industrial quote | `350.00 USD` | `industrial-quote.png` |
| Service proposal | `630.00 CAD` | `service-proposal.png` |
| Non-sales exception queue | `170.00 USD`, 3 exceptions | `exception-queue.png` |

The queue first binds a blank amount, receives a targeted row 2 clarifi-
cation, answers `100.00`, and resumes the same derivation to `170.00`.

## Focused tests

| Scope | Result |
|---|---|
| `tests/test_canvas_typed_fields.py` | **13 passed** |
| Canvas capability/assessment/routes/crud/fork suite | **105 passed** |
| Frontend canvas capability suites | **6 passed** |

## Runtime identity

- Backend: pid `70749`, source `fa77cc2abf45`, instance
  `fa77cc2abf45.70749.1793591895`, clean, SQLite world
  `canvas-successor-20261101-clean`.
- Frontend: production build `8ekSj7KLz89t9mn-dO1A0`, service `atom-frontend`,
  healthy.
- World and health snapshots: `world.json`, `backend-health.json`,
  `frontend-health.json`.

## Known boundaries

- No live provider call, refresh, write or send.
- Canvas action declarations are validated against the registered actions but
  are not executed here.
- The derive clarification reuses the canvas edit operation; assignment-task
  resume is not claimed in this batch.
- Expression grammar is deliberately limited to `+ - * /` with declared
  scale/rounding.
- No independent unfamiliar-user utility study was run.
