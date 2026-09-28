# Integration handoff into the c16 background lane — 2026-09-27 20:30

From the integration agent. **I have not touched `core/async_turn_continuation.py`,
`controlled_planner_c16.py`, `provider_shim.py` or any C16 evidence** — you own
those and were mid-edit. This note is about shared code I changed that changes
what your two open defects mean, plus one proposal for the attribution join.

## What I changed in shared code (all boot/durability layer, none of it yours)

| File | Change |
|---|---|
| `backend/main_api_app.py` | the boot crash-recovery sweep and the continuation-recovery pass moved OUT of `if ENABLE_SCHEDULER … and not is_test_mode` |
| `backend/core/execution_ownership.py` | **new** — per-process owner stamp + liveness classification |
| `backend/core/models.py` | one mapper `before_insert` listener stamps every `AgentExecution` with its owner |
| `backend/core/execution_recovery.py` | the sweep skips rows a live process owns; it also resolves the keyed `ChatRequestRecord` of a turn it just failed |
| `backend/core/chat_transport.py` | new terminal `crashed` state; `check()` returns a distinct `crashed` action |
| `backend/integrations/chat_routes.py` | a crashed key answers **409 `request_crashed`**, not an endless 202; the keyed id is put into the turn context |
| `backend/integrations/chat_orchestrator.py` | `_start_chat_execution` records `request_id` in the execution metadata |

## Consequence for your defect 2 ("the continuation can be abandoned mid-flight")

You wrote: *"Process death is not yet excluded — rule that out before calling it
a product defect."* It is now ruleable, and the rule is mechanical:

* A continuation's durable `AgentExecution` row is an ordinary insert, so it now
  carries `metadata_json.owner` = `{pid, token, host, process_started_at,
  os_process_start}`.
* On boot, `reconcile_orphaned_executions()` marks a running row failed **only on
  a VERIFIED dead owner** — no such pid, or a confirmed pid reuse. Three verdicts,
  not two: verified-live is untouched; a missing stamp, an owner on another host,
  and a failed liveness inspection are all `unknown`, which is left running AND
  reported (`agent_unknown_detail`) rather than treated as death. An earlier
  version of this reconciled `remote` and `absent`; that was wrong, because an
  unfamiliar host is not proof a worker died.
* So: kill the process (SIGKILL) instead of tearing the world down, restart
  through `preview_stack.py --reuse-run`, and the abandoned row becomes
  `status=failed` with `metadata_json.recovery.crashed = true` and
  `recovery.owner_state` saying which verdict was reached. That is a
  process-death proof you can attach to the checkpoint, and it is the same
  mechanism the crash lane measured end to end
  (`../crash_recovery_run6/crash_recovery.json`, 24/24).

Two things to know so you do not misread it:

1. **An in-process stall is NOT recoverable by this, and should not be.** A
   continuation stuck inside a live process keeps a live owner, so the sweep will
   decline to touch it. That is the intended direction: the sweep's job is to
   reclaim ghosts, not to interrupt running work. If your reproduction leaves the
   row `running` because the *process is still up*, the finding is the in-process
   `finally` gap you described — the sweep is not the fix for it.
2. `_finish_durable_record()` in the `finally` of `_apply_effects()` is still the
   structural hole for the in-process case. I have not changed it.

## Proposal for your defect 1 (the wrong `operation_id` on the landed write)

You have: the surviving `canvas_audit` row carries `operation_id=1e57dfae…`
while the continuation is `3fe40fae…`, and `_operation_status()` looks for
`operation_id == continuation_id`, so it can never see the write that landed.

The structural cause is the same one I hit on the keyed-request side: **the
effect is stamped with whatever identity the writer happened to hold, and the
reader assumes it equals its own.** `ChatRequestRecord.execution_id` was NULL
until finalization, so a crashed turn's key could not be joined to anything; the
fix was to record the owning identity *at claim time* and join on that.

The same shape applies to your case, with one difference: the interactive attempt
genuinely cannot know the continuation id (it is minted after the fork), so no
amount of reading at that layer will line them up. The join has to go the other
way — from the landed effect to the operation that owns it:

* either the effect records `execution_id` (which the continuation *does* know,
  since it created its own row) alongside `operation_id`, and `_operation_status`
  resolves through that,
* or `_classify_preapply`'s revision-attribution fallback is made to fire by
  matching on the *revision* the fork observed rather than on id equality.

Either way the acceptance rule is the one this repo keeps re-learning: match on
identity, never on recency or on "the id I happen to have". I have not
implemented this — it is in your files and you are in them.

## One harness note that will save you a confusing diff

A world's `source_id` (`<commit>-dirty.<digest>`) is **not stable across
launches of the same code**. The digest is taken over `git status
--porcelain --untracked-files=all` inside the world's own checkout, and that
checkout contains the evidence directory — so every new `candidate_*/` or
`*.json` under `docs/architecture/orchestration_migration/acceptance/` changes
the next launch's digest. Two of my runs on byte-identical exported code read
`…dirty.9b2084c16e84` and `…dirty.21ce2b24fd0b`.

Use the **export tree hash** from `freeze_candidate.py` as the stable identity
(`candidate_crash_9b2084c1/candidate_freeze.json`: 6562 files, tree
`25c8c226…`, 0 mismatches). If your C16 results are cited by `source_id`, they are
citing a string that moved for reasons unrelated to the code.

## Status of my slice, for your records

Crash recovery, own world (`crash_recovery`), **24/24** on code identity
`dfd0cdacd214…` (6563 exported files, rehashed intact; launch `source_id` for that
run was `a8bc48dc13e5-dirty.1de24506f541`): ownership respected (a second
process's sweep leaves a live turn running and counts it as live, not unknown),
crashed keys resolve to 409 rather than an endless 202, no duplicate execution, no
false success, pre-crash answers intact. Narrative in `../PREVIEW_STATUS.md` §4a;
evidence in `../crash_recovery_run7/`, freeze record in
`../candidate_crash_d5adefe7/`.

**One thing to copy if your case-2 harness asserts on the sweep's return value:**
the keys are `agent_recovered`, `agent_untouched_live`, `agent_unknown_owner`,
`agent_unknown_detail`, `chat_requests_released`. An assertion of the form
`result == {...}` will break when the contract grows, and the useful thing it
loses is the "what did you deliberately NOT touch" half.

---

# Update 21:35 — ownership policy corrected, and two things that affect your next steps

## 1. The sweep now has THREE verdicts, and "unknown" is inert

| Verdict | When | Action |
|---|---|---|
| `self` / `live` | verified live owner on this host | untouched |
| `dead` | verified gone: no such pid, or **confirmed** pid reuse | reconcile |
| `unknown` | owner on another host, **no owner recorded**, or the liveness inspection raised | **untouched and reported** (`agent_unknown_detail`); not declared crashed, request key not released |

If your harness asserts on the sweep's return value, the keys are now
`agent_recovered`, `agent_untouched_live`, `agent_unknown_owner`,
`agent_unknown_detail`, `chat_requests_released`. `agent_skipped_live` is gone.

## 2. Your "timed worker kill" item: kill the SERVING PROCESS, do not stall it

This is the trap I would have walked into, so: a continuation row is an ordinary
`AgentExecution` insert, so it carries `metadata_json.owner` with the pid and
token of the process that forked it.

* **SIGKILL the server** (not a stall, not a teardown-and-relaunch) and restart
  through `preview_stack.py … --reuse-run`. The boot sweep sees a **verified dead
  owner** and reconciles the row to `failed` with
  `metadata_json.recovery.crashed = true` and `recovery.owner_state = "dead"`.
* **A stall in a live process is NOT reconciled, and that is correct.** The owner
  is alive, so the sweep declines. If a recovery test leaves the row `running`
  because the process never died, the recovery code is not broken — the premise
  was. Your `_finish_durable_record()` `finally` gap remains the real hole for
  the in-process case and I have not touched it.

A worked implementation of the kill-and-restart sequence, including a *second
process* running the sweep mid-turn, is in
`../crash_recovery_probe.py` (`second_process_sweep`, the `os.kill` /
`--reuse-run` block). Copy the shape; the chat turn it interrupts is not the
point.

## 3. Your step-4 freeze can use the v2 record instead of hand-rolling it

`../freeze_candidate.py` is now schema **v2** and puts identity in three
separate boxes, which is what "full source + base HEAD + fixture/schema/config
hashes + effective flags" asks for:

```
identity.code    export_tree_sha256 (6563 files, rehashed), file count, mismatches
identity.config  resolved server_env hash, effective_flags, network boundary
identity.fixture atom_db_sha256, parquet count, credential scrub, venv freeze
identity.launch  source_id / instance_id / pid / ports — labelled "process
                 identity, NOT code identity"
```

Two reasons it matters for you specifically:

* A world's `source_id` is **not stable across launches of identical code** (the
  dirty digest covers the world's own `git status --untracked-files=all`, which
  includes this evidence directory). Your `candidate.identity` is
  `…dirty.32f44` for a specific launch; the export tree hash is what identifies
  the code all three cases ran against.
* `preview_stack.FINGERPRINT_MODULES` now also covers `core.execution_recovery`
  and `core.execution_ownership`, so the per-module hashes in your launch
  descriptor include the crash-recovery path your background case depends on.

## 4. Operation attribution (your `not_done` #1) — the join, stated once more

Unchanged from earlier and still not implemented by me, because it is in a file
you are actively editing: the landed effect carries the *timed-out interactive
attempt's* `operation_id`, `_operation_status()` looks for
`operation_id == continuation_id`, and the interactive attempt structurally
cannot know that id. The fix direction is to join from the effect to the
operation through an identity the writer actually had (the continuation's own
`execution_id`), or to make `_classify_preapply` match on the observed revision.
Not on recency, and not on "the id I happen to hold" — the repo has now paid for
that lesson twice on this slice (`ChatRequestRecord.execution_id` was NULL until
finalization; the keyed-request join now records `request_id` at claim time
instead).
