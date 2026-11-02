# Canvas lost-update repair — results

Executed clean tip: `4859b0ce2477`. Branch
`codex/brennan-canvas-successor-20261101`. Tree clean at execution.

## Lost-update invariant

| Control | Result |
|---|---|
| Two-session B replacement, stale A answer | Refused; B and its revision remain; old question not resolved |
| Writer between refreshed validation and CAS | CAS zero rows; rollback; B remains; no edit/total |
| Updated verifier boundaries third case | **pass** |
| Invalid derive after answer edit | Edit rolled back; question open with refused attempt |

The answer, open-question, refused-attempt, dataset bind, manifest and edit
writers all use the same database conditional write (`_commit_canvas_content_cas`).
SQLite uses JSON-extract predicates; PostgreSQL uses JSON text predicates;
unsupported dialects refuse.

## Focused tests

| Scope | Result |
|---|---|
| `tests/test_canvas_typed_fields.py` | **24 passed** |
| Canvas capability/assessment/routes/crud/fork focused suite | **116 passed** |
| Updated verifier boundaries probe | **3 passed** |
| Frontend canvas capability suites | **6 passed** |

The direct `/private/tmp/test_verifier_canvas_lost_update.py` file does not
catch the expected `CapabilityError`; see `PROBE_NOTES.md`. No probe file was
edited.

## Browser

`scripts/acceptance/canvas_typed_canvases_local.py` -> **16/16 checks**, no
page errors. Three ordinary-UI canvases:

- industrial quote `350.00 USD`
- service proposal `630.00 CAD`
- exception queue `170.00 USD`, 3 exceptions

Source-replacement control: old answer `409 stale_clarification`, no edit to
replacement `B`, new question for `B`, completion only through the new answer
at `2000.00`.

## Runtime identity

- Backend pid `13382`, source `4859b0ce2477`, instance
  `4859b0ce2477.13382.1793620956`, clean.
- World `canvas-successor-20261101-repair2`.
- Frontend build `3GFWeWvtCydaBRfYM0_RY`, service `atom-frontend`, healthy on
  `127.0.0.1:3133`.
- Backend `127.0.0.1:8092`.

## Boundaries

No live provider action; no hosted deployment; canvas actions are validated but
not executed; derive clarification is canvas-state, not assignment-task resume;
expression grammar is bounded; no unfamiliar-user study.
