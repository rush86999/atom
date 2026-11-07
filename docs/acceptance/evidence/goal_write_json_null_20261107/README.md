# Goal-write JSON-null CAS repair — successor evidence

Source under test: `9205b222a` (merge of the repaired branch with main
`8a577f14a`). Predecessor source: `48889fd99`; this bundle does not modify or
regenerate the predecessor's captured evidence.

## Confirmed defect

A valid unchanged physical JSON null (`metadata_json` stored as the JSON text
`'null'`) was rejected as `409 STALE_TARGET` by
`PUT /api/goals/{goal_id}/utility`, while physical SQL NULL and `{}` succeeded.
The supplied root probe reproduced `1 failed / 2 passed` at `48889fd99`
(`test_unchanged_nullable_metadata_can_accept_target[null]`).

Root cause: `_load_goal` returned only the deserialized Python value. ORM
deserialization maps both a physical SQL NULL and a stored JSON null to
`None`, so `_metadata_cas_condition` built `metadata_json IS NULL` for both.
That predicate matches zero rows for a JSON-null row, producing a false stale
conflict. A second read after the load could not repair this without leaving
the goal value and its physical kind in different snapshots.

## Repair

`backend/core/goals/goal_write_service.py` now selects the goal row and
`GoalObjective.metadata_json IS NULL` in the **same SELECT**
(`_load_goal_snapshot`). The snapshot carries `(goal, physical_sql_null)` to:

- the prior value (`_read_prior_metadata`), which never normalizes one null
  kind into the other;
- the comparison material/digest (`_metadata_material` /
  `_metadata_digest`): SQL NULL, JSON null and `{}` have distinct prior and
  result/replay representations;
- the conditional CAS predicate (`_metadata_cas_condition`): SQL NULL uses
  `IS NULL`, JSON null uses SQLAlchemy `JSON.NULL`, `{}` uses equality;
- the post-commit target readback and replay path, which use the same
  representation as the write.

Object material keeps its original digest shape, so receipts written before
this distinction still replay. The write remains conditional DML
(`synchronize_session` is not left as a stale ORM flush). A peer transition
between any two kinds refuses with effect none, keeps the peer's exact stored
kind and writes no audit receipt. Clearing a null kind with no target remains
a verified `no_change` and does not coerce it to `{}`.

## Permanent controls

`backend/tests/test_goal_write_authority_contract.py` adds:

- positive acceptance for SQL NULL, JSON null and `{}` (including replay of
  the same operation id);
- distinct prior digests across the three physical kinds;
- the full 3x3 peer-transition matrix (same-kind cases skipped) with
  peer-kind preservation, zero audit and a fresh success twin;
- clear-on-null no-change controls that preserve the physical null kind.

## Qualification (fresh owned basetemp children, `TESTING=1`)

| Control | Result | Log |
| --- | --- | --- |
| Supplied JSON-null probe (3) + original actor-race probe (2) | 5 passed | `logs/supplied-probes.log` |
| Focused goal set, 109 collected (was 94 at predecessor) | 106 passed, 3 skipped | `logs/focused-109.log` |
| Affected goal selection, 185 collected (was 170) | 182 passed, 3 skipped | `logs/affected-185.log` |

The 3 skips in the focused/affected runs are the same-kind cells of the
transition matrix, covered by the positive matrix instead.

## Limits and preserves

- Runtime qualification is SQLite only. PostgreSQL is used through the
  existing dialect-aware `JSONBColumn`; the predicate was designed to compile
  for PostgreSQL (`IS NULL` / `JSON.NULL`) but was **not** runtime-qualified in
  this bundle.
- Preserved from the predecessor: actor/role/workspace/request-entry scope
  binding, receipt/no-resend contracts, utility ranking and the existing
  role/read twins. No new table, migration, review engine, router or
  feedback store.
- No live DB, canonical world, app model/provider, install, credentials or
  deployment were used. All tests ran on scratch SQLite files.
