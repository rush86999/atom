# Canvas successor — lost-update repair and final rerun

Status: **submitted for independent verification; not self-accepted.** This
closes the remaining lost-update defect in the consolidated canvas repair
batch. Connected acceptance remains bound to `6431bcb78`.

## Executed source

| Item | Value |
|---|---|
| Worktree | `/private/tmp/atom-canvas-successor` |
| Branch | `codex/brennan-canvas-successor-20261101` |
| Product repair source | `4859b0ce2477` |
| Executed clean tip | `4859b0ce2477` |
| Tree at execution | clean (`dirty=false`) |
| Backend identity | pid `13382`, source `4859b0ce2477`, instance `4859b0ce2477.13382.1793620956` |
| World | `canvas-successor-20261101-repair2` (isolated local world) |
| Frontend | production build on `127.0.0.1:3133`, build id `3GFWeWvtCydaBRfYM0_RY` |
| Backend | `127.0.0.1:8092`, real routes/executor/sqlite |

## Lost-update repair

The answer path now:

1. rolls back the caller transaction and reloads the canvas with
   `populate_existing()` — a stale identity-map object is never trusted;
2. validates the captured source/manifest/policy/state/subject/row/field
   binding against that authoritative snapshot;
3. applies the edit and derive without ORM autoflush;
4. commits through a **database compare-and-swap**. The conditional UPDATE
   matches the persisted capability revision, source version, manifest
   revision and clarification ID. SQLite uses `json_extract` predicates;
   PostgreSQL uses JSON `astext` predicates; an unsupported dialect refuses
   rather than writing unchecked. Zero matching rows raises
   `concurrent_edit` and leaves the newer snapshot intact.
5. expunges the dirty ORM object before commit so SQLAlchemy cannot emit an
   unconditional primary-key UPDATE after the CAS.

The same conditional write protects the open-question writer, the
refused-attempt writer, dataset binding, manifest changes and ordinary edits.
A failed derive rolls back the edit and leaves the question open with the
refused attempt.

### Reproductions

- Two sessions: B replaces A with B; A answers its old question -> refusal,
  B and B's revision remain in a new session, no resolved old question.
- Writer injected **after refreshed validation but before the CAS** -> zero
  rows, rollback, B remains; no edit/total.
- The updated verifier boundaries test (third case) passes.

**Probe note:** the older `/private/tmp/test_verifier_canvas_lost_update.py`
calls `answer_derive_clarification` without catching the expected
`CapabilityError`, so it errors before its durability assertion. The updated
boundaries probe expects that exception. Our own two-session and
write-after-validation controls use `pytest.raises` and assert B in a new
session. See `PROBE_NOTES.md`.

## Three canvases through the ordinary UI

| Canvas | Independent total |
|---|---|
| Industrial quote (table, quantity × unit price) | `350.00 USD` |
| Service proposal (form, hours × rate) | `630.00 CAD` |
| Non-sales exception queue (count + amount by status) | `170.00 USD`, 3 exceptions |

Browser: **16/16 checks**, no page errors, including the page-level
source-replacement refusal: old answer `409 stale_clarification`, no edit to
replacement `B`, new question for `B`, completion at `2000.00`.

## Tests

| Scope | Result |
|---|---|
| `tests/test_canvas_typed_fields.py` (incl. lost-update + CAS-race) | **24 passed** |
| Canvas capability/assessment/routes/crud/fork focused suite | **116 passed** |
| Updated verifier boundaries probe | **3 passed** |
| Frontend canvas capability suites | **6 passed** |
| Browser journey | **16/16 checks** |

Logs: `typed-tests.log`, `backend-tests.log`, `verifier-boundaries.log`,
`frontend-tests.log`, `run.log`.

## Changed files vs previous repair

```text
backend/core/canvas_capability_service.py
backend/api/canvas_capability_routes.py
backend/tests/test_canvas_typed_fields.py
```

## Exclusions

- Isolated local world and production frontend build; not hosted deployment.
- No live provider lookup, refresh, write or send.
- Canvas action declarations are validated but not executed from the canvas.
- Derive clarification is canvas-state and reuses edit/derive, not assignment
  task resume.
- Expression grammar is bounded `+ - * /` with the documented rate contract.
- No independent unfamiliar-user utility study.
- No universal mini-app/runtime claim.
