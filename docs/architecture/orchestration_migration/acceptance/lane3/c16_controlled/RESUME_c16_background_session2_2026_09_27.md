# Lane 3 resume — c16 background success (2026-09-27, session 2)

Additive resume note. Does not overwrite any other stream's resume document.
Companion machine-readable state: `CHECKPOINT.json` in this directory.
Governing directive: `docs/architecture/orchestration_migration/FINISH_LANE3_DIRECTIVE_2026_09_27.md`.

## Where this session started

Picked up from a checkpoint whose step 1 ("Background success") was diagnosed but
blocked. That diagnosis was **partly wrong, and correcting it is most of this
session's value**: the background path had never actually been exercised, so the
symptoms it reported as a product defect were largely artifacts of the harness.

## The one-paragraph version

`--interactive-budget` was declared in the harness and then never used, and
`preview_stack.server_env()` builds the server's environment through
`SERVER_ENV_WHITELIST`, which strips `ATOM_CHAT_REQUEST_DEADLINE_SECONDS`
outright. The server therefore ran on the product default
`CHAT_TURN_BUDGET_DEFAULT_SECONDS = 95s` while the shim stalled 40s. The stall
fitted *inside* the budget, so the request completed synchronously, the product
never forked, and every "background" assertion was quietly measuring the
synchronous path. A second, independent bug compounded it: the shim's
`stall_counts` is a global per-key counter, so the single armed stall was always
consumed by case 1. With both fixed, the fork is real and reproducible.

## What is now proven

- The budget knob **reaches the server** — asserted by reading it back from the
  run dir's `server_env.json`, not assumed from the request.
- The product **does fork**: durable `AgentExecution(triggered_by='continuation')`
  row plus the matching `canvas_audit` rows, in the world's own database.
- Case 1's evidence is **preserved and re-verified**: `c16_controlled_planner.json`,
  15/15, all five boundaries green.

## What is still broken (product, not harness)

1. **The landed write is stamped with the wrong `operation_id`.** The surviving
   `canvas_audit` row carries `operation_id=1e57dfae…` while the continuation was
   `3fe40fae…`. `_operation_status()` (`core/async_turn_continuation.py:605`)
   searches for `operation_id == continuation_id`, and the timed-out interactive
   attempt structurally cannot know that id — so the probe can never see the write
   that actually landed, and readback is refused on every attempt.
   `_classify_preapply`'s revision-attribution fallback is meant to catch exactly
   this and did not fire: attempts 2 and 3 re-ran the edit leg instead of
   returning `already_applied`. Net effect: the requested edit **is** durably
   applied and is reported as failed.

2. **The continuation can be abandoned mid-flight.** `3fe40fae` logged through
   `retry 2/3` and then stopped — no attempt 3, no `finished` — leaving its row
   `status='running'` with an empty summary 20 minutes later against a 300s
   budget. `_finish_durable_record()` lives in the `finally` of
   `await _apply_effects()` (`:810-814`), so anything that stops the task between
   the runner returning and that `finally` loses the terminal record entirely.
   **Process death is not yet excluded** — the world is torn down and relaunched
   between runs — so rule that out before calling it a product defect.

## The trap that will waste the next hour if unnoticed

**Editing `backend/` does not change what the acceptance world runs.**
`c16_d0/code/backend` is a read-only, hash-pinned *working-tree snapshot* taken
at 16:36, symlinked into `backend_root/`. The `READBACK-DECISION` log line and the
`_apply_effects` per-stage logs added this session are in the working tree and
**did not execute**. Rebuilding the snapshot changes `code_manifest.json`, so
case 1 must be re-run afterwards against the new fingerprint — the current 15/15
belongs to the 16:36 snapshot.

## Do this next, in order

1. Fix `durable_continuations()` returning `[]` for a row that demonstrably
   exists. Not a missing column (`agent_executions` has no `session_id`; the
   query uses `metadata_json LIKE`) and not a missing value (the row's metadata
   does carry the session id). The `terminal: {}` in the report is the tell.
   **No durable-terminal assertion is trustworthy until this is fixed.**
2. Re-run:
   `backend/venv314/bin/python docs/architecture/orchestration_migration/acceptance/lane3/controlled_planner_c16.py --world c16_d0 --out docs/architecture/orchestration_migration/acceptance/lane3/c16_controlled --port 8074 --relaunch --mode bg-success`
   Re-verify case 1 in the same run — the per-leg stall arming is untested.
3. Rebuild the `c16_d0` code snapshot so the diagnostics actually run, then name
   the failing gate from the log rather than inferring it.
4. Only then fix the `operation_id` mismatch in `_classify_preapply`, and re-run
   to green.

## Rules that held this session, worth keeping

- The `chat_continuation` "zero events" result from the prior session was a
  **harness artifact**: the subscription opened *after* the 420s wait it was
  meant to measure. It is now a collector thread that subscribes before the
  barrier and runs across it. Do not "fix" a product bug that a timing bug in
  the harness reported.
- Never relax readback verification to turn a test green. The product
  verification chain (`updated` → `postcondition_verified` → `_operation_landed`
  → `read_canvas`) is the thing under test; the `READBACK-DECISION` log names
  which link failed without altering any of them.
- The short interactive budget applies to the **whole world launch**, so it also
  applies to case 1. That is why the stall must be armed per-leg rather than at
  script-write time.
