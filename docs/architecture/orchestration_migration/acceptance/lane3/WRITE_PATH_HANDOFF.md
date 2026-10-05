# Write-path acceptance package — and its explicit supported scope

**Date:** 2026-09-27, updated after D5 and again on 2026-09-28 (interruption
window + zero-effect claims). Current candidate: code identity
`90f0354c97a9…` (`identity.code.export_tree_sha256`, 6563 exported files,
rehashed with 0 mismatches), freeze record `candidate_write_d5/`. The previous
candidate `dfd0cdacd214…` is superseded; its record is `candidate_write_combined/`.

**Changes since the first package, and what they moved:**
- **D5 presentation is FIXED** (was "not supported"). A background outcome is now
  a sentence a user can read, identical live and after reload, with the
  machine-readable binding in the row's metadata. Verified on `90f0354c…`:
  `has_raw_bracket_diagnostic: false`, live delivery `ws_events_seen: 6`, reload
  recovery `history_recovery_reachable: true`, and the terminal summary reads
  *"Background update failed. The background edit did not apply after 3 attempts.
  Nothing was changed on the canvas."* — that sentence is **emitted only when
  verified** (`async_turn_continuation._verified_zero_effect`: the canvas's audit
  trail has not advanced past the fork snapshot AND no audit row carries an
  operation id this continuation owns, with a content-hash cross-check); when it
  cannot be established the wording keeps the uncertainty instead of denying it.
- **The synchronous edit path got the same treatment (2026-09-28).**
  `update_canvas_content` / `restore_canvas_version` now state, on every return,
  whether their append was attempted (`write_outcome`: `not_attempted` /
  `committed` / `unknown`), because a `success: False` from those functions is
  NOT evidence that the canvas is untouched — a failure after their own commit
  is reported as a refusal. `apply_canvas_edit` maps anything but
  `not_attempted` onto a `write_uncertain` reason, and `describe_apply_failure`
  only says "nothing was changed" for refusals that were decided before the store
  was called; the default direction is now uncertain, so a future refusal path
  cannot inherit a confident zero-effect claim by omission. A revision conflict
  also stopped denying a change — the canvas really did move, by someone else.
  Covered by `tests/test_write_zero_effect_claims.py` (39 cases), including the
  source case: a post-commit failure returns `success: False` with
  `write_outcome: "committed"` and the row really is in the audit trail.
- **The C16 lane fixed the two success-only assertions** I reported — the
  background-failure case now publishes 24/24 with **zero** not-applicable
  (their check is now `no_mutation_landed_on_a_failed_turn`). Published by
  `publish_case.py`, which prints every assertion with PASS / FAIL / NOT
  APPLICABLE and never folds an inapplicable one into a ratio.
- **Editing is still NOT promoted.** The remaining promotion gate is item 3 below
  and it has not been run.

## The supported scope, stated plainly

### Supported, on this candidate

| Capability | Evidence |
|---|---|
| A real background canvas mutation, applied once, correctly attributed, reported truthfully | C16 background success 26/26 (`write_combined_c16/c16_controlled_bg-success.json`) |
| A synchronous authorized mutation with verification, five boundaries green | C16 sync 15/15 (`c16_controlled_sync.json`) |
| A background mutation that fails, with zero effects and no false success | C16 background failure 24/24 applicable (`c16_controlled_bg-failure.json`) |
| The terminal notification is about *this* conversation, canvas and execution | `delivery_binding.json` 8/8 |
| Two independent processes, same intended operation → one winner, one effect, correct loser behaviour, conflicting payloads refused | `combined_concurrency/concurrent_claim.json` 11/11 |
| Chat-turn crash: ownership respected, ghost reconciled, no duplicate, no false success | `combined_crash/crash_recovery.json` 24/24, and `crash_barrier_run2/crash_recovery.json` 29/29 in barrier mode |
| Interrupted **background** work — killed after its effect had committed but before its terminal record — reconciled on a verified dead owner, effect not repeated, terminal report truthful | `bg_barrier_run2/background_interrupt.json` 21/21 |
| The same, for a **chat turn** interrupted after its AgentExecution row was claimed | `crash_barrier_run2/crash_recovery.json` 29/29 |
| The read path through the real browser, on this same code | `combined_browser/` 25/26 (the one failure is token streaming — see below) |

### NOT supported — do not use, do not advertise

1. **Canvas editing through the browser.** Every mutation above was driven at
   the API boundary with an accepting planner injected. There is no browser
   evidence for editing, so editing is not advertised. Producing it needs a
   shim-backed harness that opens a seeded canvas in the real UI and types into
   the real composer; that harness does not exist.
2. **Editing with the production planner.** Measured, repeatedly: the
   production planner **declines** canvas edits (`wants_edit=False`). Everything
   green above injects one consistent accepting plan, and that injection is the
   *only* thing injected — fork, reservation, store, audit rows, verification
   and delivery are all the product's. A user on the real configuration will be
   told the canvas was not changed, which is the correct behaviour and not a
   capability.
3. **Token streaming in the UI.** Intermittent: this check passed earlier today
   on a previous fingerprint and fails here (1 sample, no intermediate
   lengths). Delivery is HTTP, whole answer, with a "Reasoning Process" line
   while working. It is not in the supported list and is not a gate.
4. **The D5 completion UX** — **now fixed and verified**; see the header. Removed
   from this list.
5. **Cross-host anything.** Cross-host execution is unsupported by design and
   an unfamiliar host is classified *unknown* — never treated as dead.
6. **The full C00–C26 matrix** on this candidate. `CASE_ACCOUNTING_C00_C26.md`
   is an accounting, not a pass.

## Two findings that are the package's most useful output

1. **A harness defect, found by rerunning someone else's green case on the
   combined code.** `controlled_planner_c16.py:1278` asserts
   `landed_mutation_attributable_to_this_request` and
   `landed_mutation_is_the_current_revision` **unconditionally**. On
   `--mode bg-failure` there is no landed mutation by design (`zero_update_audits`
   and `old_text_intact` both pass), so both checks read False and the case
   reports 24/26. They are not product failures; the assertions are
   success-path-only. Fix shape: gate them on a mutation having landed, or invert
   them for the failure mode ("no mutation landed, and none is attributed").
   **Not fixed by me — it is the C16 lane's file and they are in it.**
2. **The after-the-effect interruption window is ~20 ms, and it is now closed
   by construction rather than by luck.**
   The sub-case that used to be OPEN — "the effect landed and its completion
   was not recorded" — could not be reached by any harness technique, because
   the window between them is ~20 ms: from the resulting database of the old
   attempt, the audit row commits at `10:12:53.334944` and the continuation's
   `completed_at` is `10:12:53.354743`. A 20 ms poll loop only ever observes
   them together, and seizing the SQLite write lock after the effect is
   *visible* is too late, because by the time a reader can see the audit row
   both commits have already happened. `bg_interrupt_after_effect/` (11/14,
   with the three window checks correctly red) is the HISTORICAL record of
   that, and it is kept for exactly that reason: it is why the window was hard
   to reach, and a reader deciding whether the current evidence is credible
   needs to see what it replaced.

   The window is now made deterministic by a **test-only barrier confined to
   the isolated acceptance harness** (`core/acceptance_barrier`): the worker
   signals arrival at a named stage and parks there, and the harness places
   the kill inside the window by construction. It is a pause and nothing else
   — it does not authorize, apply, verify, persist or decide anything, and it
   refuses to arm at all unless every database URL the process can be seen to
   have opened resolves inside `acceptance_worlds` (a production database, a
   Postgres URL, or a `DATABASE_URL` the engine disagrees with is refused
   loudly and the work continues without it).

   Both legs now pass with the window's real state observed from inside it
   (`bg_barrier_run2/background_interrupt.json` 21/21,
   `crash_barrier_run2/crash_recovery.json` 29/29):

   | what the kill must catch | background continuation | chat turn |
   |---|---|---|
   | the operation-LINKED audit row is committed | `de62f442…` at `11:20:49.302985` | n/a (the claim is the row itself) |
   | the terminal record is NOT written | `status: running`, `completed_at: null` | `status: running` |
   | the worker is provably parked, not slow | arrival marker pid 37175, stage `continuation_after_effect`, `arrived_at 2026-09-28T11:20:49.315588Z` | arrival marker on stage `chat_turn_after_claim` |
   | the process is really gone | SIGKILL of the recorded serving pid | SIGKILL |
   | one total effect | 1 `update` audit row at kill, 1 after recovery, 1 after a follow-up turn | n/a |
   | reconciled from a VERIFIED dead owner | `recovery.crashed: true`, `owner_state: "dead"` | same, and the run2 case additionally proves an `unknown` owner is left alone |
   | the terminal report is truthful | "A background canvas update was interrupted by a server restart", no `raw_bracket_diagnostic` | 202 in-progress while running, then terminal `crashed` on retry |

   Both probes record the disarm on the restart leg
   (`ATOM_ACCEPTANCE_BARRIER: "(disarmed)"`), so recovery is decided by the
   product's own boot sweep and not by this probe's test seam.

   **The re-run from the current working tree did NOT happen.** On 2026-09-28
   ~09:31, mid-launch, the whole worlds tree was deleted underneath the probe
   (19 worlds / 80 GB → 2), which is the `AGENTS.md` "silent empty acceptance
   world" hazard in its worst form — the launcher was already `mkdir`-ing a
   fresh run inside a tree being erased. `bg_barrier_run3/ABORTED.md` records
   it. The evidence above is the recorded run2 result; re-running both probes
   is still outstanding, and it is the first thing to do once the worlds tree
   is stable.

## How to re-verify, in order

```bash
D=docs/architecture/orchestration_migration/acceptance/lane3
# 1. is the world still the frozen candidate?
backend/venv314/bin/python $D/freeze_candidate.py verify \
    --world write_combined --record $D/candidate_write_combined/candidate_freeze.json
# 2. recovery, concurrency, background interrupt
backend/venv314/bin/python $D/crash_recovery_probe.py      --world write_combined --port 8076 --out <dir>
backend/venv314/bin/python $D/concurrent_claim_probe.py    --world write_combined --port 8077 --out <dir>
backend/venv314/bin/python $D/background_interrupt_probe.py --world write_combined --port 8079 --out <dir>
# 2b. the DETERMINISTIC interruption window (the two cases that were ~20 ms wide).
#     --barrier-after-* needs a world whose runs/ tree is stable: it launches a
#     fresh run and the barrier parks a real worker, so run it against a world
#     nobody else is rebuilding. Use a free port; 8071-8080 are previews.
backend/venv314/bin/python $D/background_interrupt_probe.py --world <w> --port 8085 \
    --out <new dir> --barrier-after-effect
backend/venv314/bin/python $D/crash_recovery_probe.py --world <w> --port 8085 \
    --out <new dir> --barrier-after-claim
# 3. C16 (the C16 lane's harness, unchanged, against this world)
backend/venv314/bin/python $D/controlled_planner_c16.py --world write_combined \
    --out <dir> --port 8078 --relaunch --mode sync --only sync
backend/venv314/bin/python $D/controlled_planner_c16.py --world write_combined \
    --out <dir> --port 8078 --relaunch --mode bg-success --only bg
# 4. delivery binding over the fresh C16 artifact
backend/venv314/bin/python $D/delivery_binding.py <dir>/c16_controlled_bg-success.json
```

Rebuild the world **only** when the tested source changes, and re-freeze after
every rebuild: `source_id` is not stable across launches of identical code (the
dirty digest covers the world's own `git status`, which includes this evidence
directory), which is why the export-tree hash is the identity to cite.

## The read-only preview is a separate deliverable and is untouched

**http://localhost:3102/chat** — world `candidate_fix1`, code identity
`e2323daaad44…`. It was not rebuilt, relaunched or re-pointed at any point in
this work. Its status document is `PREVIEW_STATUS.md`; its supported list is
chat, workbook lookup, item replacement, formatting, re-search and reload.

**But its world directory no longer exists on disk.** On 2026-09-28 ~09:31 an
external process deleted `backend/data/acceptance_worlds/` down to two worlds
(`write_combined`, `write_verify_0928`); the previews on `:3102`/`:8071`
(`candidate_fix1`) and `:3101`/`:8051` (`preview_v1`) were still running with
their working directory inside world directories that had been removed, and
nothing in this session restarted, killed or re-pointed them. Their processes
are alive and their open handles are intact, but any restart, any write to
their database path, and any claim that their world is reproducible are now
false until the tree is restored. `bg_barrier_run3/ABORTED.md` has the timeline
and the exact failure.

The combined candidate is a **different world** (`write_combined`, backend
`:8078`, frontend `:3103`) and exists to carry write-path evidence. It is not
the preview and does not replace it.
