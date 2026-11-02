# User-authored canvases — typed three-canvas successor

Status: **submitted for independent verification; not self-accepted.** This is a
successor batch after the connected-workflow submission. Historical 111/123
scope is unchanged. No live provider lookup, refresh, write or send occurred.

## Executed source

| Item | Value |
|---|---|
| Worktree | `/private/tmp/atom-canvas-successor` |
| Branch | `codex/brennan-canvas-successor-20261101` |
| Base | `9b39c35b7` (connected-batch docs head) |
| Executed source head | `fa77cc2abf45ea17d3ab3ee8a07b9496a81c082c` |
| Tree at execution | clean (`dirty=false`) |
| Backend identity | pid `70749`, source `fa77cc2abf45`, instance `fa77cc2abf45.70749.1793591895` |
| World | isolated local world `canvas-successor-20261101-clean` |
| Frontend | production build on `127.0.0.1:3131`, build id `8ekSj7KLz89t9mn-dO1A0` |
| Backend | `127.0.0.1:8091`, real routes/executor/sqlite |

The backend health identity and the frontend health/build identity are captured
in `backend-health.json`, `frontend-health.json`, `world.json` and
`frontend-build-id.txt`.

## Three canvases created through the ordinary UI

The browser journey uses the normal `/canvas` page, blank-canvas control, agent
attach, capability panel, manifest editor, CSV binding and Derive button. It
does not call per-canvas Python.

| Canvas | Shape | Independently expected total |
|---|---|---|
| Industrial quote | table, `quantity × unit_price`, grouped by item | `350.00 USD` |
| Service proposal | form, `hours × rate`, grouped by service | `630.00 CAD` |
| Non-sales exception queue | queue, count + amount by status | `170.00 USD`, 3 exceptions |

The exception queue intentionally binds one blank amount. The first derive
returns a targeted clarification on row 2 / `amount`; answering `100.00`
resumes the same derivation and yields `170.00`. This is canvas state, applied
through the existing edit operation; it is not the assignment-executor task
resume path.

Browser result: **13/13 checks passed**, no page errors.

## Controls proven

- Schema 2 stable field IDs survive relabel/reorder; labels are presentation.
- Explicit units/currencies are required for typed numbers and money.
- Derived expressions are a tiny server-side grammar (`+ - * /` and field
  names); the browser sends only state/manifest/source revisions, never a
  total.
- A client `total` or hidden value is rejected by `extra="forbid"`; an untyped
  `Total` column is ignored by the manifest and cannot change the computed
  total.
- Unknown widget/base component, action, field ID, field type, aggregate and
  unit are refused at manifest save.
- A missing required value produces a targeted row/field question; answering
  resumes the same derivation; duplicate answers are idempotent; conflicting
  answers refuse.
- Stale state revision, manifest revision or source version refuses before
  arithmetic.
- Cross-workspace direct access refuses (403).
- Reload preserves fields, history and revisions.
- Fork keeps typed shape but drops action bindings/authority references.
- Declared custom-code runtime unavailable is an explicit `RuntimeError`, with
  no host-execution fallback.

## Tests

| Scope | Result |
|---|---|
| `tests/test_canvas_typed_fields.py` | **13 passed** |
| Canvas capability/assessment/route/crud/fork focused suite | **105 passed** |
| Frontend `CanvasCapabilityRules`, `CanvasCapabilityAssessment`, `CanvasCapabilityDerive` | **6 passed** |
| Browser typed three-canvas journey | **13/13 checks** |

Commands:

```bash
cd backend
TESTING=1 PYTHONPATH=$PWD /Users/rushiparikh/projects/atom/backend/venv314/bin/python \
  -m pytest tests/test_canvas_typed_fields.py -q

cd frontend-nextjs
npx jest components/canvas/__tests__/CanvasCapabilityRules.test.tsx \
  components/canvas/__tests__/CanvasCapabilityDerive.test.tsx \
  components/canvas/__tests__/CanvasCapabilityAssessment.test.tsx \
  --runInBand
```

## Changed files vs base

```text
backend/api/canvas_capability_routes.py
backend/core/canvas_capability_service.py
backend/tests/test_canvas_typed_fields.py
frontend-nextjs/components/canvas/CanvasCapabilityPanel.tsx
frontend-nextjs/components/canvas/__tests__/CanvasCapabilityDerive.test.tsx
scripts/acceptance/canvas_typed_canvases_local.py
```

## Exclusions and remaining work

- Isolated local world and a production frontend build; hosted deployment and
  public publication are not claimed.
- No live external provider call, refresh, write or send.
- Action declarations are validated against the registered action registry but
  are not executed from the canvas in this batch; connected effects remain
  assignment-executor-owned.
- The derive clarification is canvas-state and reuses the edit operation; it
  does not claim assignment-task resume. Binding a canvas derivation to the
  assignment executor is the next integration step.
- Expressions intentionally support only `+ - * /`, declared scales and
  half-up/half-even/down rounding. They are not a general formula language.
- No independent unfamiliar-user utility study was run; browser/test passes
  are not a usability certification.
- No universal mini-app/runtime claim follows from three supported canvases.
