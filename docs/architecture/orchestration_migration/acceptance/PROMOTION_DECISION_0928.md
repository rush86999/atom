# Promotion decision — 2026-09-28 (final closeout)

## Decision

**PROMOTE the `final_promotion` candidate for the orchestration recovery and
delivery scope, with the exclusions listed below.** Every required scenario
in this closeout actually ran and passed on the frozen candidate; the
pending item from the prior round (F09 consolidation) is closed by the runs
recorded here.

## Frozen candidate

| Binding | Value |
|---|---|
| World | `backend/data/acceptance_worlds/final_promotion` (preserved; API-seeded fixture, 367 tables, 0 dev rows, workbook + sheet index present — 46 dataset files) |
| Export | working-tree snapshot sha256 `56801e7be6731be845490e6cfb5117c4cda2efd9d35b04e89e7891aaf3abaa4b` |
| Loaded-module hashes | verified byte-identical across every relaunch (`core/async_turn_continuation.py`, `core/models.py`, `core/llm/byok_handler.py`, `core/acceptance_barrier.py`, `core/chat_canvas_editor.py`, `integrations/chat_orchestrator.py`); serving runtime identity `79b2a41032c3-dirty.e7f6f88df630` |
| Effective flags | `CHAT_FINALIZATION_M1=1`, `CHAT_FINALIZATION_M2=1`, `ATOM_TASK_LIFECYCLE_ENABLED=1`, `ENABLE_SCHEDULER=false`, barriers armed per case |
| Run database | per-run seeded copies under `final_promotion/runs/` (live dev DB never read) |
| Provider | local shim, per-run unguessable port, neutral program name (provider responses only; execution/persistence/verification/delivery are production code) |
| Results | `acceptance/final_closeout_0928.json` — **9 PASS / 0 FAIL** |

## Case results (all on the candidate above)

| Case | Verdict | Evidence |
|---|---|---|
| F11 effect-before-completion crash (barrier `continuation_after_effect`) | **PASS** | `F11_committed_but_unrecorded` + `F11_crash_recovery_one_effect_one_outcome` + `F11_keyed_retry_truthful`: at the hold — mutation committed (operation-linked audit id, outcome `applied`), terminal completion unrecorded, record `running`; killed inside the window; disarmed recovery → mutation present exactly once, no second write, record reconciled, pending ack preserved, keyed retry truthful with zero new writes. |
| Delivery-claim recovery (barrier `recovery_delivery_held`) | **PASS** | `DLC_claim_exists_message_does_not`: claim stamped on the record, terminal message absent, mutation already landed. `DLC_restart_before_expiry_defers`: killed and restarted at claim-age 10.6s (< 90s lease), scheduling disabled — boot pass DEFERRED. `DLC_automatic_delivery_after_expiry`: left running, delivered automatically after expiry — exactly one terminal row, zero additional canvas mutations. |
| F09 overlap (public endpoint) | **PASS** | `F09_overlap_own_truthful_outcomes`: concurrent pair → distinct execution ids, every fork terminal, live `chat_continuation` per fork, terminal outcomes in history after reload, canvas coherent. `F09_duplicate_terminal_events_no_duplicate`: a further restart re-ran the recovery pass — visible completions and canvas byte-stable. |
| F12 read workflows (isolated app) | **PASS** | `F12_read_workflows`: chat read previews the delivery line; lookup returns the warranty value; replacement reply quotes the change and lands exactly once; formatting readback agrees; re-search finds the line; fresh canonical reload agrees. |

Earlier evidence retained under its own fingerprint: F03/F04/F05/F07/F08/F10
and the first F09/F11 rounds on export `451468608d39…` /
`b5f6d404fadf6ded…` / `0d3bd68378fa…` (`finish_line_cases_0928.json`,
`f09_targeted_0928.json`, `f11_crash_window_0928.json` + evidence dir).

## Working preview

- **URL:** `http://127.0.0.1:8092` — persistent isolated backend serving the
  `final_promotion` world (launched via `preview_server.py`, health-checked,
  identity verified: pid in `final_promotion/backend_root`).
- Relaunch command if stopped: `venv314/bin/python
  scripts/orchestration_acceptance/preview_server.py --port 8092 --name
  final_promotion --frontend-origin http://127.0.0.1:3090`
- The frontend-origin (3090) is the cross-origin allowance for the repo's
  standard preview frontend; the browser UI on that origin was not
  re-verified this round (see exclusions).

## Supported workflows (verified on this candidate)

- Background canvas edits via chat with forked continuation, honest
  terminal outcomes in history + notification, reload-stable.
- Crash recovery: effect-before-completion kill → automatic reconciliation
  and one-time delivery; delivery-claim expiry → automatic takeover by the
  running server's recurring pass (scheduler-independent).
- Keyed transport idempotency: replay / 409 conflict / crashed-key 409 with
  the designed flat error; restart pin survival.
- Concurrent overlapping edits: distinct identities, no duplicated or mixed
  effects, truthful per-execution outcomes.
- Canvas read workflows over chat: read, lookup, replacement, formatting,
  re-search, reload.

## Explicit exclusions

- **F06/F07 (real-planner real-browser)**: stand on the PINNED
  `write_verify_0928` candidate (base `1a953b58934d`, export
  `f530c509948d947d`, planner pin `deepseek/deepseek-v4-pro`). NOT re-run
  on this export and NOT implied to have run here; the shim world's
  planner-substituted equivalents are supplementary only.
- **Browser UI end-to-end**: not exercised this round (backend preview
  verified; frontend origin allowed but unverified).
- **F02a**: the historical wrong-field mismatch incident remains
  UNEXPLAINED.
- **Simultaneous `_apply_effects` / duplicate live WS events for ONE
  continuation under concurrency**: unclaimed (no test).
- **Real external providers**: credentials unavailable (verified live
  2026-09-28: OpenCode Go 403/402; empty `.env` LLM keys).
- **Workbook searchLane metrics**: the workbook + index are seeded in the
  fixture; priced-search scorecard cases belong to the search stream's own
  ledger, not re-run here.
