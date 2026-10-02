# CURRENT STATUS — read-only preview (the one document)

Last measured **2026-09-27 18:56 EDT**. This file supersedes the state narratives
in `RESUME.md`, `notes/RESUME_HANDOFF_2026-09-27.md`, `LANE_3_INVENTORY.md` and
`CHAT_ORCHESTRATOR_READINESS_REPORT.md` for the question *"what can I open and
use right now?"*. Those remain as history; if they disagree with this file about
a live port, this file was measured more recently.

Everything below was read from a live `/api/health` identity, a `preview_stack
verify` run, or a result artifact that names the fingerprint it was produced on.

## 1. Open this

| | |
|---|---|
| **URL** | **http://localhost:3102/chat** |
| Login | `admin@example.com` / `preview-only-local-2026` |
| Backend API | `http://127.0.0.1:8071` (pid 50248) |
| Frontend | `http://localhost:3102` (pid 50366) |
| World | `candidate_fix1`, run `run-7325767729a0` — a disposable export; your dev DB is never opened |
| Fingerprint | `a8bc48dc13e5-dirty.e2323daaad44` |
| Freeze record | `candidate_e2323daaad44/candidate_freeze.json` — 6554 exported files, tree sha256 `068171fa…`, rehashed intact at 18:56 |
| User's own stack | `:8001` / `:3000` — untouched, never restarted by any of this |

The backend serves the world's **immutable code export**, so this fingerprint and
run dir are stable for the life of the process. It is not a moving checkout.

## 2. Verified on exactly that fingerprint

| Gate | Command | Result |
|---|---|---|
| Stack identity + containment | `preview_stack.py --world candidate_fix1 verify` | **10/10** — own world, own run DB open, dev DB not held, frontend compiled against `:8071`, lifecycle flag effective, streaming flag effective |
| Task correction over HTTP | `task_correction_acceptance.py --base http://127.0.0.1:8071` | **4/4** — replacement, replacement→formatting, replacement→re-search, reload-after-replacement |
| **Real browser, real UI** | `lane3/browser_correction_chain.py --world candidate_fix1` | **25/26** — `lane3/browser_live_2026_09_27/` (transcripts + screenshots) |

The browser run drove the login form, not a seeded token, and watched every
request: the only origins touched were `:3102` and `:8071`, foreign `[]`.

## 3. Supported now (the frozen scope)

Each row is a check that passed in the browser on this fingerprint.

| Capability | Browser check |
|---|---|
| Sign in through the real form | `B0_login_through_real_form`, `B0_browser_only_talks_to_this_candidate` |
| Real-model chat | `B7_bubble_settled_on_non_empty_text`, `B7_final_bubble_matches_durable_history` |
| Workbook lookup, 8 items in requested order | `B1_lookup_shows_all_eight_in_order` |
| **Item replacement** (`Replace U-22 with U-38`) | `B2_displayed_set_is_the_revised_one`, `B2_outgoing_item_is_gone`, `B2_incoming_item_is_present`, `B2_incoming_item_labelled_absent_no_invented_value` |
| Replacement creates no side-effect task | `B1_lookup_did_not_create_a_task`, `B2_no_task_row_created`, `B6_whole_chain_created_no_task_row` |
| Formatting (re-render, no resurrection, prior answers intact) | `B3_*` (4 checks) |
| Explicit re-search | `B4_*` (2 checks) |
| Reload preserves every answer and its evidence | `B5_*` (4 checks) |

U-38 is **not in the seeded workbook**. Its honest absence is asserted by
`B2_incoming_item_labelled_absent_no_invented_value`; a price next to U-38 would
be a fabrication and fails that check.

## 4. Failed / not supported — do not advertise

1. **`B7_bubble_text_grew_progressively` FAIL** (1 sample, 27 chars, no
   intermediate lengths). Token streaming in the UI is **intermittent**: the same
   check passed at 13:12 EDT on the previous fingerprint of this world (27
   samples, 4 distinct lengths) and failed at 18:56 on this one. The answer
   always arrives whole over HTTP; the bubble shows a "Reasoning Process" line
   while working and then completes. **Delivery is HTTP, not streaming.** Bounded
   diagnosis only — this is an optional capability and does not gate the preview.
2. **Artifact / canvas editing** — not verified. Do not test. (Being worked
   separately on world `c16_d0`; the production planner measurably declines
   edits, so nothing here may advertise them.)
3. **Background and asynchronous actions** (authorized/denied edit, effect
   counts, duplicate request, notification delivery) — not closed. A real
   background edit has been observed to land its write while never reaching a
   verified terminal state and never notifying the user
   (`c16_controlled/CHECKPOINT.json`, case 2).
4. **Crash recovery — FIXED and proven, 2026-09-27 20:16.** See §4a.
5. **Mutation races / cross-host task-creation lock** — does not coordinate
   independent hosts.
6. **C16 controlled-planner leg** and the **full C00–C26 matrix** — not run on
   this fingerprint. `CASE_ACCOUNTING_C00_C26.md` is the accounting; it is not a
   pass.
7. **Ranking benchmarks, reranker evaluation, mailbox `hybrid_min` gate,
   contextual indexing, live connectors, sandboxed outbound send** — out of
   scope for this preview.

## 4a. Crash recovery (own world, not the preview)

A turn interrupted by `SIGKILL` mid-flight, then a restart through the real
launcher against the same run dir and database. World `crash_recovery`, export
tree `25c8c226…` (6562 files, 0 mismatches on rehash), result
`crash_recovery_run6/crash_recovery.json` — **24/24**. This is a single-process
scenario and is kept separate from background-edit recovery and notification
delivery, which are **open** (item 3 above).

**Three defects found and fixed, in order.**

1. **The sweep never ran.** `reconcile_orphaned_executions` was wired into
   `main_api_app.lifespan` but *inside* `if ENABLE_SCHEDULER … and not
   is_test_mode`. Any process without schedulers reconciled nothing and logged
   nothing, so the omission was invisible. Measured: **14/18**, the interrupted
   execution still `running` after a clean restart — the exact ghost-run problem
   the function exists to solve, reproduced by an unrelated feature flag. Moved
   out of the gate, and before it: reconcile, then start work.
2. **It would have failed a live worker's turn.** Moving the sweep out of the
   gate exposed the next layer: the sweep selected by status alone, so any second
   process on the same database marked the *first* process's in-flight turn
   failed underneath it — the turn keeps running and then tries to finalize into
   a row that now says it failed, with nothing reporting the contradiction.
   Ownership is now stamped on every `AgentExecution` insert (one mapper
   listener, all writers) and classified in **three** verdicts, not two:

   | Verdict | Meaning | Action |
   |---|---|---|
   | `self` / `live` | VERIFIED live owner on this host | untouched |
   | `dead` | VERIFIED gone: no such pid, or **confirmed** pid reuse (OS start time differs) | reconcile |
   | `unknown` | owner on another host, **no owner recorded**, or the liveness inspection itself failed | **untouched and reported** — not declared crashed, key not released |

   `unknown` is the correction that matters: an unfamiliar host is not evidence
   that a worker died, and a missing stamp is not evidence of anything. My first
   version reconciled both, and reconciling on a guess is how a running turn gets
   failed by a process that simply could not see who owned it. A pid that is
   alive but whose recorded OS start time is unavailable is `live`, not
   `unknown`: liveness was established and reuse is neither confirmed nor
   refuted, and the harmful direction is the other one.

   **The deliberate cost:** a genuine ghost whose owner cannot be established now
   stays `running` instead of being reclaimed. That is the right direction to be
   wrong in, and it is not silent — every unknown row is logged and returned in
   `agent_unknown_detail`. Verified with a genuine second process — own pid, own
   token, same database, the world's own code — while a turn was in flight:
   `agent_recovered: 0, agent_untouched_live: 1, agent_unknown_owner: 0`, turn
   still `running`. The probe asserts the live row is counted as untouched-**live**
   specifically, so "unverifiable" can never be quietly relabelled as "verified
   live".
3. **A crashed turn's key could not be attributed to it.** `ChatRequestRecord.
   execution_id` is only written at finalization, so a turn that died in flight
   left a key pointing at nothing, and the key stayed `in_progress` forever — the
   documented "mint a fresh id" policy, which is the *absence* of a policy once
   the sweep knows the turn failed. The turn now records its `request_id` at
   claim time, the sweep joins on that exact identity, and the key moves to a
   terminal `crashed` state answered as **409 `request_crashed`**. Deliberately
   not a replay (nothing completed) and not a re-execution (a side effect may
   have landed before the crash).

**Insert paths that bypass the mapper event.** The stamp only works if every
insert builds an ORM instance. Audited for `__table__.insert()`,
`execute(insert(...))`, `bulk_insert_mappings`, `bulk_save_objects`, `copy_from`
and raw `INSERT INTO agent_executions`: **no production path uses any of them**
— the only hits are test fixtures and an unrelated alembic revision. Pinned by
`backend/tests/test_execution_insert_path_audit.py`, which also asserts the
listener is registered *and* fires on a real insert, because a scan that passes
because the listener is gone would be worthless. Not covered by scanning, and
therefore stated rather than assumed: rows written by an older build or copied
in from a snapshot carry no owner, and no scan finds that. Those are exactly the
`unknown` / missing-stamp case.

**The retry assertion is per durable state, not a set of acceptable statuses.**
A retry *while the turn is unfinished* must be 202 with `request_in_progress`
and those words; a retry *after recovery* must be 409 `request_crashed` — 202 is
now wrong (the turn is not in progress) and 200 is wrong (nothing completed, so
replaying would be a lie). A fresh request id in the same session runs a real
turn. My first version graded this `{200, 202, 409}` + non-empty body, which
accepts 202 and a completed replay as equally correct about the same turn; that
was wrong and is recorded as such.

Scope: reconcile-only, by design — a crashed turn is marked failed, never
resumed. Tests: `backend/tests/test_execution_ownership_and_crashed_keys.py`
(29, including nine negative tests proving unknown ownership cannot terminate an
execution, cannot release its request key, and cannot permit duplicate work),
`test_execution_insert_path_audit.py` (2) and
`test_boot_recovery_not_gated_by_scheduler.py` (5). Affected suites: 166 + 476
passed, 2 xfailed.

**Identity, in three separate boxes** (`candidate_crash_d5adefe7/candidate_freeze.json`,
schema v2). `identity.code.export_tree_sha256` is the code identity and the only
thing to cite: `dfd0cdacd214…`, 6563 files, rehashed intact. `identity.config`
holds the resolved launch environment (`server_env` hash, effective flags,
network boundary) and `identity.fixture` the fixture database, parquet count and
credential scrub — because a flag or a dataset changes results without changing a
line of code, and citing the code hash alone would hide that. `identity.launch`
keeps `source_id` / `instance_id` / pid / ports and says in the record that it is
process identity, not code identity. A world's `source_id` is not stable across
launches of identical code (see the environment notes), which is why the
launcher's per-module fingerprint list now also covers `core.execution_recovery`
and `core.execution_ownership`.



## 4b. Write-path gates (in progress; nothing advertised yet)

Artifact editing is still **excluded** from the preview. These gates are the
evidence that has to exist before that changes.

### C16 reconciliation — the "outstanding patch" was my reporting error, not the product

I reported C16 background success/failure as passing *and* the operation
-attribution patch as outstanding. Those cannot both have been true, so it was
checked against the artifacts rather than against a note:

* The export that served the passing runs is world `c16_d1`, `code_snapshot
  9cdf562d10aa5989c6f4fe663fd52709`, 6560 files.
* `core/async_turn_continuation.py` in that export is sha256_16
  `822b0ee42f4c3f78` — **byte-identical to the working tree**.
* That file **contains the patch**: `_operation_identity()` returns
  `[continuation_id, origin_operation_id]` and `_matched_operation_row()` locates
  the audit row through either id plus the canvas. `origin_operation_id` is
  carried on the continuation and set at both fork call sites.

So the patch is present. What the green background run actually exercised is
narrower, and the artifact says so: `landed_operation_id bebcda64…` equals
`continuation_id bebcda64…`, with `landed_by_interactive_attempt: false` and
`update_count: 1` — the **continuation's-own-write** branch. The
**origin-operation** branch (the interactive attempt's write landing, stamped
`1754d62a…`) was not exercised in that run. That matches the C16 lane's own
`not_done` entry, and is now confirmed from the run rather than accepted from the
note.

My error: I reported "the operation-attribution join is still theirs to make"
from their 19:00 checkpoint, which described the defect *before* the fix, and did
not re-read before reporting at 21:30. The lane had landed it by 22:55.

### Gate 1 — concurrent mutation claims: 11/11

`concurrent_claim_probe.py`, world `crash_recovery`, evidence
`concurrent_claim_run3/concurrent_claim.json`. Two REAL operating-system
processes per phase, not two threads — a same-process race is settled by a lock
the product does not have.

| Phase | Race | Result |
|---|---|---|
| A | same `(workspace, run, idempotency_key)`, same payload | exactly one winner; **one** `task_operation_records` row; the loser is handed the winner's `operation_id`, so it replays rather than minting a second effect |
| B | same key, **different** payload | still one row; the loser is given a payload hash it did not ask for — a conflict, not a replay; no second operation materialised |
| C | two independent HTTP clients, one `request_id` | one execution, one delivered answer, statuses `{200, 202}` — the loser waits; a different payload under the same id is **409** with no second execution or answer |

**What this does not measure, stated rather than implied:** the canvas-audit row
itself. Phases A and B sit at the durable operation claim, which is the layer
that gates a mutation; a real canvas edit needs an accepting planner, which is
the C16 lane's provider shim. Claiming "one audit attribution" from this probe
would assert a fact it did not measure. That seam closes in gate 4.

### Gates 2–4 — closed on one combined candidate

All of the following ran against **one** world, `write_combined`, code identity
`dfd0cdacd214…` (6563 exported files, rehashed with 0 mismatches), with
configuration and fixture hashed separately and all eight result artifacts
hash-bound in `candidate_write_combined/candidate_freeze.json`. The handoff, with
the explicit supported scope, is **`WRITE_PATH_HANDOFF.md`**.

| Gate | Result | Artifact |
|---|---|---|
| Completion delivery | **8/8** binding + C16's live-notification, empty-channel and reconnect/reload checks | `write_combined_c16/delivery_binding.json`, `c16_controlled_bg-{success,failure}.json` |
| Interrupted background work | **12/12** | `bg_interrupt_run1/background_interrupt.json` |
| Concurrency, on the combined candidate | **11/11** | `combined_concurrency/concurrent_claim.json` |
| Chat-turn crash, on the combined candidate | **24/24** | `combined_crash/crash_recovery.json` |
| C16 sync / background success / background failure | **15/15 · 26/26 · 24/24 applicable** | `write_combined_c16/` |
| Browser, read path, same code | **25/26** (the streaming check) | `combined_browser/` |

**Canvas editing through the browser is still NOT done, so editing is not
advertised.** Two things are named in the handoff rather than glossed:

* the production planner measurably **declines** canvas edits, so every mutation
  above used one injected accepting plan; and
* a browser pass needs a shim-backed harness that opens a seeded canvas in the
  real UI, which does not exist yet.

**One harness defect found by rerunning the C16 lane's own green case on the
combined code:** `controlled_planner_c16.py:1278` asserts two
*landed-mutation* checks unconditionally, so `--mode bg-failure` — where no
mutation lands by design — reports 24/26. Not a product failure; the assertions
are success-path-only. Not fixed by me: it is their file and they are in it.

**One sub-case not yet exercised:** in the interrupted-background run the kill
landed while `effect_landed: false`, so "already applied, must not repeat" had
nothing to repeat. Timing the kill after the audit row appears is the remaining
work on that gate.

## 5. Stale artifacts — do not read these as current

| Artifact | Reality |
|---|---|
| `acceptance/preview/preview_state.json` | describes `consolidated_preview` `:8092/:3092` — **both dead** |
| `acceptance/preview/preview_verification.json` | describes `search_preview` `:8091/:3091` — **both dead**; carries the now-superseded `PREVIEW-01` |
| `MANUAL_TEST_QUICKSTART.md` | the old `:3091` preview; says the lookup is broken. Superseded — the lookup and replacement now pass on `:3102` |
| `RESUME.md`, `notes/RESUME_HANDOFF_2026-09-27.md` | written when `:8091`/`:3092` were live. History |
| `acceptance/task_correction_results.json` | 4/4, but on `…dirty.58293b7b2484` and a 10:10 run. Current equivalent: `lane3/task_correction_live_2026_09_27.json` |
| `lane3/browser_final/` | 26/26 but on `…dirty.90f75e4ad858`. Current: `lane3/browser_live_2026_09_27/` (25/26) |
| `live_integration_results/*.json` (31 files) | all `all_pass: false`, only 3 carry a descriptor. Historical |

`PREVIEW-01` (pending-file result outranking the turn's own scan) is **closed as
observed**: the browser run's `B1` lookup returns all eight items after the real
login form, in a session that continues through replacement, formatting,
re-search and reload.

## 6. Operating rules for anyone touching this

* One integration agent owns the candidate and the launch. Other agents supply
  scoped patches; they do not relaunch.
* Restart **without** rebuilding: a rebuild re-exports the working tree and
  silently produces a different candidate under the same name.
  ```bash
  backend/venv314/bin/python backend/scripts/orchestration_acceptance/preview_stack.py \
    --world candidate_fix1 down
  backend/venv314/bin/python backend/scripts/orchestration_acceptance/preview_stack.py \
    --world candidate_fix1 up --reuse-run \
    backend/data/acceptance_worlds/candidate_fix1/runs/run-7325767729a0
  ```
  Frontend only: `… preview_stack.py --world candidate_fix1 frontend-up`.
* After any production change: re-freeze
  (`lane3/freeze_candidate.py freeze --world candidate_fix1 --out <dir>`) and
  re-run the three gates in §2. A result from a different `source_id` is not a
  result about this candidate.
* Never `git add -A`. Other lanes have in-flight work in the same files.
* Never restart `:8001` / `:3000`.

## 7. Next milestone (does not block §1–§3)

1. **Background edits + notifications** — owned by the lane working `c16_d0`
   (checkpoint in `c16_controlled/`). Do not duplicate; supply scoped patches.
   My contribution to their two open defects, including the mechanism that now
   makes "was it process death?" answerable, is in
   `c16_controlled/INTEGRATION_HANDOFF_2026_09_27_2030.md`.
2. **Same-host concurrent mutation claims, counting actual effects** — next
   unowned item. Cross-host locking is explicitly OUT of scope: the primary
   deployment is local, and it would expand scope while the background-edit
   defect is still open.
3. **Durable completion + live and reloaded notification behaviour** for a
   verified background mutation.
4. **Then the wider acceptance matrix** — on the same frozen candidate, or on a
   new one that is re-frozen and re-verified through §2 before any claim is
   made about it.

### Environment notes (2026-09-27)

* Disk was at **3.6 GiB free / 100%** — a host-level write-failure condition, not
  untidiness. Two maintenance windows by another session reclaimed the bulk of
  it; 46 GiB free at 20:30. **Correction to my own earlier entry in this file:**
  I removed 12 stale `runs/` directories on a "no live process" rule before the
  agreed storage procedure was applied. That was not sufficient grounds, and I
  should not have treated it as such. The manifest is in
  `stale_run_reclaim_2026_09_27.json`; each removed directory was a per-launch
  run dir in a world with no live process, and each world's newest run, every
  fixture, code export and result file was kept, so all of it is re-derivable
  from the fixture. No further reclamation without the storage procedure.
* A world's `source_id` is **not stable across launches of the same code** — the
  dirty digest is taken over the world's own `git status --untracked-files=all`,
  which includes the evidence directory, so writing a new `*.json` under
  `docs/architecture/orchestration_migration/acceptance/` changes the next
  launch's digest. Cite the **export tree hash** from `freeze_candidate.py` as
  the stable identity. Two runs on byte-identical exported code read
  `…dirty.9b2084c16e84` and `…dirty.21ce2b24fd0b`.
* The maintenance interlock (`core.world_storage_guard`) makes **every** launcher
  refuse to start while a window is open. That is correct — wait for the window;
  do not release another session's lock.
* `backend/tests/test_debug_aggregator_startup.py` fails on `main` **before** any
  of this work: `module 'main_api_app' has no attribute 'lifespan'` under pytest,
  while a direct import has it. Pre-existing, unrelated, not fixed here.
* One throwaway conversation (`probe-409-shape`) was created in the **preview**
  world while measuring the 409 response shape. Disposable world, no effect on
  any evidence; noted rather than left unexplained.


