# 918 SAVEPOINT ownership and the 121 proof — independent review

- Reviewed source: `e4ffe720f` / `backend/core/database.py`
  (sha256 `f82db493c165be5f89e59e79912f78bc8e94541ba6a47f8319eedf0d95e80424`)
- Repair: `918e7a17c` “preserve flushed caller ownership across savepoint
  boundaries”
- Read-only; no edits to the graduation worktree.

## Semantics at the current source

`backend/core/database.py:300–340`:

- `before_flush` records the current transaction:
  `session.get_nested_transaction() or session.get_transaction()`, and sets
  `atom_uncommitted_writes`.
- `after_commit` transfers a released SAVEPOINT's marker to `nested.parent`
  before `after_transaction_end` runs.
- `after_transaction_end` clears everything only at the root
  (`transaction.parent is None`); for a nested end it discards that
  transaction and recomputes the flag.

This matches SQLAlchemy 2.0.45 ordering: `after_commit` is dispatched before
`_remove_snapshot()` / `close()` restores `session._nested_transaction`, so
`nested.parent` is the correct transfer target. Flush subtransactions do not
dispatch `after_commit` (they take the `close()` path), so the parent/root
marker survives. `begin_nested()`'s implicit flush runs before the new nested
transaction is assigned, so pre-existing work is marked on the parent.

## Lifecycle controls

`backend/tests/test_caller_transaction_ownership.py` (13 controls at current
source) includes the three added after the independent review:

- `test_begin_nested_implicit_flush_keeps_outer_caller_ownership`
- `test_session_commit_with_open_savepoint_clears_finished_outer_work`
- `test_session_close_with_open_savepoint_rolls_back_caller_work`

The 121-control proof log shows all three `PASSED` (tail at 98–100%); the
fresh broader consumer run also includes this file and it is not among the
7 failures.

## Bounded observation preserved from the earlier review

`caller_work_pending(db, owned=(...))` still checks the flush marker before
consulting `owned` (`agent_decision_write_service.py:388–410`). An owned-only
flushed/savepoint-released object is therefore conservatively classified as
unrelated. This is the documented safe direction (the shared writer must not
commit or roll back another caller's work); the only production `owned` caller
is `agent_governance_service._update_confidence_score`. No ordinary
false-negative was found, and this slice did not change that policy.

## 121 proof status (not rerun)

`/private/tmp/root-graduation-final-permanent-gate-20261110-31ub0c6n/review.json`:

- `capture_head = f8155821f…`
- `actual_exit = 0`, `same_source = true`
- `121 passed` in 87.86s (73 qualification/assessment/notification +
  13 lifecycle + 8 promotion + 27 CI controls)

Current `e4ffe720f` hashes for all ten files captured by that proof are
byte-identical (`source/source-hashes.json` → `current_vs_121_source_after.all_same=true`).
Per authorization the 121 gate was **not** rerun; the proof is cited as
source-equal, not re-executed here.
