# Budget pause-credit repair — 2026-11-01

Closes the reviewed defect where a persisted wait interval could be credited
twice, making genuinely exhausted active work look unexhausted.

## Source identity

| Item | Value |
|---|---|
| Integrated repair commit | `019aa1eeb` (this branch), based on the earlier `bec60978b` idempotent-credit repair |
| Backend tree | `c2963fbcdc8e` |
| Frontend tree | `c921cb82e784` |
| Development worktree | `/private/…/budget-repair` at `88bf413e8` |

C2 remains pinned to its historical source `414d8add3` (backend
`715969f01d23`) for the elapsed closure; it does not load this repair. The
repaired source is for the verification controls and the integrated submission,
not a relabel of C2's execution.

## Defect (reproduced)

A legacy budget could carry `paused_seconds = 500` for a completed wait **and**
still keep the same timestamp in `waiting_since` because the older credit path
did not clear it. `_effective_wall_elapsed` then subtracted the interval from
both fields:

```
started 2000s ago - paused 500s - waiting_since 1500s -> ~0s working
```

A run with **1500s of real work against a 900s budget** was therefore allowed.
The legacy `_credit_wait_once` branch also returned without clearing the live
`active_wait`/`waiting_since`, so the retry path kept the double subtraction.

## Repair

- `_credit_wait_once` now clears the matching `active_wait`/`waiting_since` on
  **every** outcome: newly credited, already in the ledger, and legacy
  already-credited. Only the interval just closed is cleared.
- `_effective_wall_elapsed` ignores a `waiting_since` already present in the
  credit ledger. For a legacy paused ledger with no live `active_wait`
  identity, it does not subtract the same interval again. A new wait always
  records `active_wait` in `_enter_wait`, so a genuinely open new wait is still
  excluded.
- No statuses rewritten, no history deleted; the assignment step and decision
  log keep the wait record.

## Controls (6 new)

1. `test_legacy_open_wait_is_not_subtracted_twice` — 1500s real work against
   900s refuses; effective elapsed is 1500s, not 0.
2. `test_legacy_credit_clears_matching_active_wait` — paused stays 500s, the
   matching live wait is cleared, the credit is marked `already_credited`.
3. `test_legacy_retry_keeps_genuine_active_exhaustion` — retry preserves
   500s paused, clears the stale wait, still refuses at 1500s working.
4. `test_recorded_credit_with_stale_open_wait_is_not_double_subtracted` — a
   recorded credit plus stale open wait still reports 1500s and refuses.
5. `test_concurrent_external_responses_credit_the_wait_once` — two concurrent
   responses credit one interval, clear the wait, complete once.
6. `test_restart_while_waiting_credits_the_interval_once` — a new executor
   excludes the open 600s wait, credits it once on response, and subsequent
   effective elapsed stays at active work.

Existing controls for retry/repeated/restart legacy credit and the original
durable-wait exclusion remain green.

## Results

| Suite | Result |
|---|---|
| `tests/test_assignment_executor.py` | **61 passed** |
| Routes + executor + goal service/events/routes/watchdog | **140 passed** |

Logs: `executor-61.txt`, `focused-tests.txt`.

## Remaining limitation

C2's historical closure will show the pre-repair budget behavior it actually
ran; the repaired behavior is verified by the controls above and by the
integrated verification run, not by relabelling C2.
