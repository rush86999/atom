# f815 promotion exact-replay — independent source review

- Reviewed source: `/private/tmp/atom-web-graduation-reviewed-delivery-20261110`
  at `e4ffe720f14d2fdf2b77147c6fc1dfbf1627fcdc` (clean tracked tree)
- Commit under review: `f8155821f` “reconcile manual promotion with its exact
  qualified result”
- File: `backend/core/agent_decision_write_service.py`
- Read-only; no edits to the graduation worktree.

## The defect the repair addresses

The promotion commit material included `last_exam_id` and
`promotion_count`, but the exact-operation replay path recomputed the target
digest from `_state_material()`, which contains neither. A committed promotion
therefore replayed as `503`/refuted instead of `already_applied` (the adapted
legacy positive exposed this). The repair shares one promotion material
snapshot between commit and replay.

## Current implementation

`_promotion_state_material(agent)` (lines 440–445) is exactly
`_state_material(agent)` plus:

```python
material["last_exam_id"] = agent.last_exam_id
material["promotion_count"] = int(getattr(agent, "promotion_count", 0) or 0)
```

`promote_agent` (lines 965–1046) uses it in all three promotion places:

- `prior_material = _promotion_state_material(agent)` — prior digest;
- `result_material` includes the receipt id and `new_promotion_count`;
- `_commit_and_verify(..., target_check=_promotion_state_material(now) == expected["result_digest"])`.

The default replay path in `_replay` (lines 704–714) selects the same helper
when `audit_expected["action"] == _ACTION_PROMOTE`:

```python
target_ok = (
    current is not None
    and _state_digest(
        _promotion_state_material(current)
        if audit_expected["action"] == _ACTION_PROMOTE
        else _state_material(current))
    == audit_expected["result_digest"])
```

`_ACTION_PROMOTE = "agent_promoted"` is the only promotion action
(lines 58–63; the only `action=_ACTION_PROMOTE` use is the promotion writer at
line 976). There is no alternative promotion action that would bypass the
helper. The explicit `target_check` argument some callers pass is separate and
was not changed.

## Evidence

- In the fresh broader run on `e4ffe720f`, all four previously failing
  promotion/replay controls now pass:
  - `test_promote_transitions_replay_and_stale`
  - `test_confirmed_audit_rollback_reports_effect_none[promote]`
  - `test_manual_promotion_success`
  - `test_manual_promotion_creates_history`
- The 121-control root proof (`31ub0c6n`) includes the 8 promotion controls
  and reports `121 passed`, `actual_exit=0`, `same_source=true`; its captured
  source hashes are equal to current `e4ffe720f` (not rerun here).

## Bounded observations (no confirmed defect)

- `promotion_count` is part of the digest and result check but is not one of
  the `_agent_predicates` CAS columns (lines 466–479). A concurrent change to
  `promotion_count` alone is caught by the post-commit target check / replay,
  not by the row-count CAS. No concrete counterexample was observed; this is
  a narrow concurrency observation, not a policy relaxation.
- Replay is conservative for older promotion audits whose result digest
  omitted the receipt/count: they are refuted rather than silently accepted.
  That is the intended safe direction.
