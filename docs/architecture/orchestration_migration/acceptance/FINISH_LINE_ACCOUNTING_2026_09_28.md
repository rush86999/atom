# Finish-line F01–F12 accounting — 2026-09-28 (REV 3, post-correction)

**REV 1's "suite green ⇒ checklist complete" claim was withdrawn** (REV 2) after
review correctly identified checks that passed without exercising their
required scenario. REV 3 records the state after the bounded corrections:
missing-branch assertions were repaired, the cases were run, and the results
below are the verified state. Nothing was redefined to pass; one sub-assertion
is recorded as NOT REACHED with its structural reason.

## Two evidence sets, never conflated

| Evidence set | Configuration | Covers |
|---|---|---|
| **Pinned browser candidate** (prior stream) | base `1a953b58934d`, export `f530c509948d947d`, world `write_verify_0928` / `run-7240b4691cc1`, planner pin `deepseek/deepseek-v4-pro` (seeded BYOK store, no shim on the F06 path) | F06, F07 real-planner real-browser |
| **Shim world** (this stream) | working-tree snapshot export sha256 `451468608d397dcb76367bd34e03ba9febb093fcd85b6b4f9f5cce38be003320`, world `write_combined`, gate flags M1+M2+`ATOM_TASK_LIFECYCLE_ENABLED`, provider = local shim (provider responses only; execution/persistence/verification/delivery are production) | F03–F05, F08–F12 branch evidence |

The shim world is **not** the frozen `write_verify_0928` candidate; its results
apply only to the configuration above. Final runner output (run 15):
`acceptance/finish_line_cases_0928.json` — **19 PASS / 1 FAIL**; shim request
capture `backend/data/acceptance_worlds/shim_capture_finish_line.jsonl`;
per-launch identity lines in `write_combined/server.log`.

| ID | Required result | Verdict | Evidence and notes |
|----|-----------------|---------|--------------------|
| F01 | Provenance + safe isolated launch | **PASS** | World identity, seatbelt, credential-free env, port preflight, per-run data dir verified every launch. Port-hygiene and shim-freshness checks added after a stale-process contamination (run 9) was diagnosed. |
| F02 | Wrong-field mismatch explained; missing target cannot mutate subject | **PARTIAL** | F02b PASS: controlled decline (`explicit_no_apply`, 6/6) on the pinned candidate + zero-write no-apply in the shim world. **F02a (historical wrong-field incident) remains UNEXPLAINED** — no mismatched-target case was run here. NOT EXERCISED. |
| F03 | Controlled synchronous correct edit, one durable mutation | **PASS** | `F03_controlled_edit`: exactly one write, body 15→30, subject/to unchanged, reload agrees. |
| F04 | Controlled background success, actual fork, truthful terminal completion | **PASS** | `F04_background_fork_success`: armed-stall overrun → fork observed as a durable record (`agent_executions`, `triggered_by='continuation'`, bound to the originating execution id) → mutation landed → WS `chat_continuation` event → truthful terminal outcome in history → exactly one write. |
| F05 | Controlled background failure, execution-time, honest terminal outcome | **PASS** | `F05_background_execution_failure`: plan accepted (planner succeeded), operation cannot apply (find text absent) → fork reached terminal state, zero writes, truthful failure wording in history, no false success claim. |
| F06 | Real-planner browser body edit, one write, reload | **PASS — pinned config only** (prior stream) | Real browser, real planner (`deepseek/deepseek-v4-pro`), fresh canvas, body 15→30, subject unchanged, exactly 1 update row, reload-verified, `verified_mutation` 4/4. Evidence: `acceptance/lane3/FINISH_LINE_CURRENT_STATUS.md` §F06. Retained; not re-run. |
| F07 | Second real-planner edit + legitimate no-apply | **PASS — pinned config only** (prior stream) | Second distinct real-planner edit (payment terms `Net 30`→`Net 45`, 11/11, audit `e8f4e709…`, reload-verified) + separate decline control. The shim world's `F07_no_apply_clarification` (wants_edit=false → zero writes) and `F07_second_edit` are supplementary. |
| F08 | Connected / disconnected / empty-channel completion recovery | **PASS** | `F08_connected_completion`: `chat_continuation` completion event observed on the websocket with outcome status (the run 7 gap — events contained no `chat_continuation` — is closed). `F08_disconnected_recovery`: arm-stalled turn forked (record observed), raw socket abandoned mid-turn (response never read), mutation + terminal outcome persisted, and the **empty-channel broadcast attempt evidenced in the server log** (`Attempted broadcast to EMPTY channel: 'user:…' type='chat_continuation'`). `abandoned: false` from the earlier JSON is superseded — the socket is now provably never read. |
| F09 | Overlap/duplicate terminal events cannot mix identities or repeat effects | **PASS — targeted checks verified** | `F09_overlap_distinct_identities`: concurrent pair → 200/200, distinct execution ids, ≤1 write each, coherent final canvas. `F09_sibling_terminal_outcome` + `F09_reload_preserves_outcomes`: every forked turn delivers a terminal outcome, live and on reload (production fix). **Targeted F09 checks — RECONCILED delivery contract (single fenced path).**
The second review identified that the first targeted round tested fork
arbitration and restart-notification recovery — different contracts. The
delivery-lease mechanisms were then RECONCILED: `AsyncDeliveryLease` (a
second, overlapping claim introduced mid-round) was REMOVED; the one
authoritative path is the fenced conditional-UPDATE claim inside
`_apply_effects` (token + lease on the durable record), which now governs
normal completion AND recovery — recovery delegates to
`recover_missing_terminal_deliveries`, the recurring scan (independent of
ENABLE_SCHEDULER) that owns candidate selection, effect attribution, and
delivery. Fence-contract unit tests (6, real ORM): atomic claim, in-flight
refusal, stale-claim release + re-claim, `_still_holds_claim` fencing a
resumed holder, disabled-lease window. Live evidence, per contract:

- **Running-server expiry recovery (no second restart): PASS** — seeded an
  in-flight claim by a dead holder, restarted once BEFORE expiry, left the
  server running (scheduler off): the boot pass deferred, and the recurring
  pass delivered after expiry with the terminal outcome in chat history
  (f09t6 evidence, shared world; the message is durable in that run DB).
- **Stale-holder two-process: PASS (live, f09t9 log)** — A claimed
  terminal delivery and parked at the confined barrier mid-delivery
  (HOLDING 27.7s); the lease expired; B took over; A was released and the
  fence REFUSED its write: "terminal message NOT written: the delivery
  claim was taken over before this transaction committed" → `fenced-out`
  stage; exactly one durable message.
- **Unrelated-edit control: PASS** (dedicated `f09_delivery` world,
  f09t10): a continuation whose edit failed while an UNRELATED turn changed
  the canvas recovers with UNCERTAINTY wording ("the record cannot
  attribute the change to this edit — check the canvas"), never
  "your update applied". Attribution is operation-linked
  (`canvas_audit.details_json.operation_id` vs the record's
  `origin_operation_id` and the continuation's own id); hash inequality
  alone is never success evidence.
- **Updated public overlap run: PASS** (reconciled export): distinct
  identities, both forks' outcomes live and after reload.

**NOT yet consolidated: one clean single-run sweep of all targeted cases on
one export.** Repeated attempts were invalidated by ACTIVE cross-stream
interference, each instance evidenced: a foreign session (`trl-…`) writing
to the shared world mid-run; foreign boots into the dedicated
`f09_delivery` world after this stream's run completed; and this stream's
shim on its dedicated port killed externally between phases. The runner now
records a foreign-interference audit and a pid journal; the remaining work
is a quiet-window rerun of `f09_targeted_cases.py`, not further product
change.
**Claims kept separate:** simultaneous `_apply_effects` invocations and duplicate live WS events for ONE continuation under concurrency remain NOT claimed (no test, no probe) — open on the ledger. |
| F10 | Keyed retry, payload conflict, restart pin survival | **PASS** | Replay (same ID+payload → identical response, zero writes); conflict (409); kill mid-flight → boot sweep releases key → designed flat `409 {"error":"request_crashed"}`; completed pin survives restart as identical replay (run 6). |
| F11 | Effect-before-kill reconciliation without another write | **PASS — crash-window exercised** | **Crash-window proof by construction (dedicated run, `--crash-window`):** the confined acceptance barrier (`core/acceptance_barrier.py`, stage `continuation_after_effect` — placed after the mutation commits and is verified, before the terminal effects/record; inert by default, refused outside an acceptance world, session-narrowed, bounded) parked the forked worker exactly inside the ~20 ms window polling could never reach. AT THE HOLD, observed: one operation-linked mutation committed (`canvas_audit` id `85cf669e…`, barrier context `outcome=applied`), terminal completion unrecorded (session history held only the pending acknowledgement), durable continuation record still `running`, worker alive and health-checkable. The serving process was SIGKILLed while parked (no release file ever created), and the SAME run was restarted with the barrier disarmed: exactly one effect (mutation present once, no re-application), the durable record reconciled to a terminal state exactly once, no fabricated history outcome, the pre-kill acknowledgement preserved on reload, the keyed retry replayed its acknowledgement truthfully with zero new writes, and a new-id repeat of the same change produced no repeat effect. Results: `/tmp/fl_crashwin4.json` (F11CW_worker_parked, F11CW_committed_but_unrecorded, F11CW_crash_window_recovery, F11CW_retry_truthful_after_crash, F11CW_new_id_no_repeat_effect — 5/5 PASS). Supporting invariants from the full suite (run 15): no second write on recovery, no duplicate terminal outcomes across a second restart, keyed honesty, new-id dedup. |
| F12 | Read preview regressions: chat, lookup, replacement, formatting, re-search, reload | **PASS** | `F12_read_workflows` runs all six as real chat turns / editor operations: chat read previews the delivery line; lookup returns the warranty value; replacement reply quotes the change; formatting edit lands exactly once with readback agreement; re-search finds the line; reload (fresh canonical read) agrees. Baseline field/audit consistency: `F12_read_preview_baseline`. |

## Production changes made (all unit-tested)

1. **`core/llm/byok_handler.py` — false `invalid_credential` provider bench.**
   The structured auth memo bare-scanned `"401"` inside `err_str`, which embeds
   the full completion repr (ids, ms timestamps) → a numeric echo benched a
   healthy provider 600 s and dead-ended every forked leg. Now classifies from
   **structured status** (`model_route_registry._status_of`: status_code attr →
   response status → status-bearing wording only); a standalone "401" inside
   arbitrary completion text is NOT an authentication failure.
   Negative tests: `backend/tests/llm/test_auth_memo_classification.py`
   (4 tests, green) — including the standalone-401-in-text negative, a
   structured 401 positive, status-bearing-text positive, and the exact memo
   predicate composition.
2. **`core/async_turn_continuation.py` — superseded sibling missing terminal
   outcome (the F09 defect).** The cancellation branch finished the durable
   record as cancelled but skipped the effects (durable chatmessage + WS
   `chat_continuation` + notification), leaving the user's last message as
   "still running in the background" forever. Now applies the same effects as
   the sibling branches, with truthful wording ("superseded by a newer canvas
   instruction; that update's result is reported separately").
   `tests/test_async_turn_continuation.py`: 50 green.
3. **`core/async_turn_continuation.py` — terminal-delivery lease, chat-reload
   outcome, and effect-aware recovery wording.** (a) `AsyncDeliveryLease`
   (new table): atomic terminal-delivery claim per continuation — unexpired
   foreign lease blocks delivery, EXPIRED lease is taken over (automatic
   retry even when an earlier recovery pass ran before expiry), completion
   makes a resuming holder unable to duplicate; `ATOM_DELIVERY_LEASE_DISABLED`
   exists as the negative-control switch. (b) Recovery now writes a durable
   chat message into the session — chat reload shows the terminal outcome
   instead of staying stuck on the pre-crash acknowledgement. (c) Recovery
   wording is EFFECT-AWARE: the fork-time snapshot hash vs the current canvas
   determines "applied before the interruption — the change is on the canvas"
   vs "could not finish", so an interrupted completion never implies the
   mutation did not land. `effect_on_canvas` recorded in message metadata and
   the durable record.
4. **`core/async_turn_continuation.py` — continuation durable records had
   NO OS-ownership evidence, so the crash sweep could not reconcile them.**
   `_create_durable_record` now stamps the owner block (`record_os_start`):
   without it the sweep cannot verify the holder's death, leaves the record
   `running` forever, and terminal recovery never sees the continuation —
   the user's chat stays stuck on the pre-crash acknowledgement
   indefinitely. Found by the running-server expiry case.
5. **`core/async_turn_continuation.py` — notified-once flag never persisted
   (found by the F11 crash-window evidence).** `notify_recovered_continuations`
   mutated the record's JSON dict and assigned it back without
   `flag_modified`, so the flag was invisible to SQLAlchemy's change tracker
   and never written — every later boot pass re-notified the same crash.
   Fixed with `flag_modified`; new test
   `test_notified_flag_persists_through_real_orm` exercises a real ORM
   round-trip (the previous SimpleNamespace test hand-set the flag and could
   not catch this); verified live by the F09 delivery-claim crash case
   (restart 1 delivers once, restart 2 delivers nothing).

## Harness repairs (isolation model unchanged)

- Port hygiene + shim-freshness proof in the runner (a stale shim/server from a
  previous run silently served the wrong script — diagnosed via run 9/10).
- Shim: `/api/tags` for the ollama runtime probe; non-empty default completion;
  tool_call entries restricted to tool-advertising requests (a tool_call served
  to a reply leg yields an empty completion → model bench → forked legs die).
- Script converted to the tool-scoped entry format the current loader expects
  (tuple-match keys were silently stringified into unmatchable keys by the
  loader rewrite — every marker entry fell through to the generic plan whose
  find text no longer existed, which read as an effect-layer failure).

## Denominator statement

F01–F12: verified as scoped above — F02a (historical wrong-field incident)
remains UNEXPLAINED and stays open on the ledger; F06/F07 stand on the pinned
candidate's recorded evidence. Evidence binding: the main suite and F11
crash-window ran on export `451468608d39…` (runtime `1a953b58934d-dirty.8cfb7`
family; crash-window evidence persisted and bound in
`acceptance/f11_crash_window_0928.json` + `f11_crash_window_evidence/`, with
the exact recovered terminal status — durable record `failed`,
`recovery.owner_state=dead` — and the user-visible outcome — exactly one
notification, "Background update could not finish / interrupted by a server
restart", history preserving the pending acknowledgements un-rewritten). The targeted F09 lease-contract checks ran on export `b5f6d404fadf6ded…` (includes the notified-flag fix and the delivery-lease/recovery changes). The F09 concurrent-duplicate-live-events gap (simultaneous
`_apply_effects` / duplicate WS frames for ONE continuation) is recorded, not
claimed. The crash-window case and the F09 delivery-claim case test DIFFERENT
interruption points and are kept separate in the ledger. No case was removed
from the denominator; no INCONCLUSIVE branch was reclassified as PASS.

**Port-collision rule (firm):** cleanup may terminate only a process owned by
that run. The runner's port cleanup now verifies listener ownership (cwd
inside this world / this backend's shim cmdline) and REFUSES to touch a
foreign listener, failing loudly instead. Dedicated ports and canaries detect
collisions; they do not authorize killing an unfamiliar listener.

**Closeout: F11 effect-before-completion verified (barrier; evidence bound,
with the semantic qualification that the mutation had already landed). F09's
terminal-delivery lease/recovery contract is IMPLEMENTED, unit-verified, and
has live passing evidence for every required case (running-server expiry
recovery, two-process stale-holder fence-out, unrelated-edit uncertainty
control, public overlap) — but the single clean consolidated run is PENDING
a quiet window: repeated attempts were invalidated by documented cross-stream
interference (foreign sessions, foreign boots into the dedicated world,
external shim kills). F02a remains unexplained. The harness hardening (pid
journal, interference audit, dedicated world, shim self-heal) is in place
for that rerun.****
