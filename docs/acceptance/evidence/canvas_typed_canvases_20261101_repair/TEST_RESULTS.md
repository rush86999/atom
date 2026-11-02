# Canvas repair batch — results

Executed clean tip: `e7c4641701f3` (product repair `1d7f96f1e`; the later tip is
the acceptance runner and docs only). Branch
`codex/brennan-canvas-successor-20261101`. Tree clean at execution.

## Independent verifier probes

The two reproduced failures now pass:

```text
tests/test_verifier_canvas_boundaries.py .. 2 passed
```

- old open clarification + replacement dataset -> `409 stale_clarification`,
  no edit;
- USD + CAD -> `CapabilityError` before any total.

See `verifier-probe.py` and `verifier-probes.log`.

## Focused tests

| Scope | Result |
|---|---|
| `tests/test_canvas_typed_fields.py` | **21 passed** |
| Canvas capability/assessment/routes/crud/fork suite | **113 passed** |
| Frontend canvas capability suites | **6 passed** |

Logs: `typed-tests.log`, `backend-tests.log`, `frontend-tests.log`.

The focused controls now include: mixed USD/CAD, USD output from CAD-only
dependency, currency hidden through a decimal intermediate, currency + hours,
same-currency addition, quantity × currency rate, service hours × CAD rate,
invalid type dependencies, old question against replacement subject, changed
source value, changed manifest, failed-derive rollback, fresh-session answer,
duplicate resolution and stale duplicate refusal.

## Browser

```text
scripts/acceptance/canvas_typed_canvases_local.py ... 16/16 PASS
```

Three ordinary-UI canvases: industrial quote `350.00 USD`, service proposal
`630.00 CAD`, exception queue `170.00 USD` / 3 exceptions. The same run
executes the page-level source-replacement refusal (`409`), confirms no edit to
the replacement subject, receives a new question for `B`, and completes only
through that new question at `2000.00`.

No browser page errors. See `result.json`, `run.log` and the screenshots.

## Runtime identity

- Backend pid `79812`, source `e7c4641701f3`, instance
  `e7c4641701f3.79812.1793595326`, clean, SQLite world
  `canvas-successor-20261101-repair-final`.
- Frontend production build `3GFWeWvtCydaBRfYM0_RY`, service `atom-frontend`,
  healthy on `127.0.0.1:3133`.
- Backend `127.0.0.1:8092`.

## Boundaries

No live provider action; no hosted deployment; canvas action declarations are
validated but not executed; derive clarification is canvas-state, not
assignment-task resume; expression grammar is bounded `+ - * /`; no unfamiliar
user study.
