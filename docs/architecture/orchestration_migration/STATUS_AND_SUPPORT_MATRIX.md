# Status and Support Matrix (corrected 2026-09-28)

Source fingerprint: commit `1a953b589`, orchestrator `e14101821aed9248`,
task_lifecycle `a49d529dc69362e9` (2,191 lines), chat_routes `5f5d808d6300db5b`,
answer_presentation `d875f731037a087b`.

Test command: `venv314/bin/python -m pytest tests/test_task_lifecycle.py
tests/test_workbook_structured_delivery.py tests/test_pending_file_task_resume.py
tests/test_acceptance_runner_guards.py tests/test_workbook_read_replay.py -q`
→ 449 passed, 2 xfailed, 0 failed.

## Implemented (in source, suite-tested)

| Capability | Where |
|---|---|
| Task lifecycle: guarded transitions, revision chain, operation records, delivery recording | `core/task_lifecycle.py` (2,191 lines) |
| Keyed request identity: `request_id` on ChatMessageRequest, same-key/payload replay, different-payload 409 conflict | `integrations/chat_routes.py` :490, :1740, :1813 |
| Planner contract enforcement at the schema boundary | commit `6e34725c7` (chat_canvas_editor.py +354/−28) |
| Presentation renderer: pres-v2 typed values, identity status, field-selection status | `core/answer_presentation.py` |
| M1 finalizer: failure correction, no concealment, execution identity preserved | `core/finalization.py` |
| Structured-result persistence: `_set_structured_result` writes to plan meta | `core/chat_tool_planner.py` :5485 |

## Boundary-verified (public endpoint, this session)

| Case | Evidence |
|---|---|
| Eight-machine ask: 8 ordered entries, no clutter | Gate run on gate_world_v2, exact_ordered_identities ✓ |
| Formatting follow-up: zero re-retrieval, presentation served | Gate run, zero_new_persisted_attempts ✓, requested_presentation_served ✓ |
| Re-search: new attempt, outcome recorded, new identity | Gate run, persisted_attempt_executed ✓, new_attempt_identity ✓ |
| Overlapping turns: distinct execution ids, rows distinct | Gate run, 3/3 checks ✓ |
| Corruption: honest empty result, no fabricated prices | Gate run, 4/4 checks ✓ |
| Unknown source: no fabricated evidence | Gate run, 3/3 checks ✓ |
| Finalized binding: execution id preserved, pin matches | Gate run, 4/4 checks ✓ |

## Still unverified (browser evidence required)

| Case | What's needed |
|---|---|
| Browser canvas edit through the real planner | Open a seeded canvas in the real UI, type into the real composer, verify the mutation landed |
| Reload: history shows the same delivered text | Browser reload, compare with the persisted row |
| Token-bearing streaming | A path that actually generates token frames |
| Restart then history/retry | Server restart, then public history and retry |
| Controlled retrieval failure with explicit error | Not "no matching row" — the source could not be read |

## Stale-WAL removal is NOT an isolation capability

Removed from the isolation claims. WAL sidecars are part of the database
state; removing them can discard committed transactions. Fixture freshness
must use the backup API or a fresh directory per run.
