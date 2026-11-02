# Canvas teaching repair — results

Executed source: `a87882526323` (clean). Branch
`codex/brennan-canvas-successor-20261101`.

## Independent probes

```text
/private/tmp/test_verifier_canvas_assignment_boundaries.py .... 4 passed
/private/tmp/test_verifier_canvas_boundaries.py ........... 3 passed
```

The four teaching probes now pass: stale proposal, foreign employee, CAS
failure journal rollback, and global lesson consumption. Logs:
`verifier-probes.log`.

## Focused tests

| Scope | Result |
|---|---|
| Canvas focused suite | **127 passed** |
| Assignment regression | **167 passed** |
| Teaching neighborhood | **203 passed** |
| Frontend canvas suites | **7 passed** |

Logs: `focused-tests.log`, `assignment-regression.log`,
`teaching-neighborhood.log`, `frontend-tests.log`.

Known pre-existing mock-only failures: 3 in
`tests/test_student_training_service.py` reproduce from the 2026-08-27
duplicate-proposal guard (`1591320ea`) with a generic DB mock; they are not
caused by this repair and are excluded from the 203.

## Browser

`scripts/acceptance/canvas_typed_canvases_local.py` -> **17/17 checks**, no
page errors.

- Three canvases through the normal UI; totals `350.00 USD`, `630.00 CAD`,
  `170.00 USD / 3 exceptions`.
- Typed receipt starts an ordinary assignment from the industrial quote.
- Source replacement old answer `409`; new subject `B` completes only through
  its new question at `2000.00`.

Teaching promotion/consumption is exercised through the public canvas route
and real journal reads in the focused controls; the browser smoke covers the
ordinary canvas/assignment path.

## Repair evidence

- Stale proposal: recomputed receipt digest + state/source/manifest/policy +
  proposal-content digest + target comparison -> 409, no journal entry.
- Foreign/moved target: authoritative workspace/tenant/role check at proposal,
  assignment and promotion -> 403/404; no journal/task/provider mutation.
- Failed promotion: journal append is `commit=False`; canvas CAS commits both
  or rolls both back. Forced CAS race leaves no lesson and proposal `proposed`.
- Global consumption: provenance stored under `entry["provenance"]`; normal
  `get_agent_lessons(task_context={})` returns the global lesson with full
  receipt digest/source versions.

## Runtime identity

- Backend pid `30391`, source `a87882526323`, instance
  `a87882526323.30391.1793628386`, clean.
- Frontend build `X_PhH8Q4l6qVCB2K0XQLf`, `atom-frontend` healthy.
- World `canvas-successor-20261101-assignment`.

## Boundaries

No live provider action; no new send. Explicit promotion only. Connected
acceptance remains `6431bcb78`; historical 111/123 unchanged.
