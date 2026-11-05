# ORACLE-01 direct canvas atomic-scope repair

Status: **atomic-scope repair submitted for independent verification.** The
original six findings are closed at source `18e8af4a6` / evidence
`48ee4cee9`. This bundle closes the remaining authorization race in the two
direct HTTP canvas routes. Whole-app ORACLE-01 remains open.

## Executed source

| Item | Value |
|---|---|
| Branch | `codex/oracle01-http-canvas-20261105` |
| Base | `81c5962bd17b3ffa90cd5107d5b3134821c0ffa1` |
| Previous accepted-repair source | `18e8af4a63a5f952e14a9c5f27dc81d6d313b918` |
| Previous evidence commit | `48ee4cee9778c1ddb27255eadf7561ecf4278de9` |
| Atomic repair source | `82ac9681ad66b276a135ce06e1d2b7f03cbb30d9` |
| Tree at execution | clean (`0 modified, 0 untracked`) |
| Runtime | real scratch SQLite, fresh sessions; controlled fault seams |
| Model/provider/browser calls | none |

## The race

The writer authorized scope, then appended the audit and refreshed the Canvas
mirror through an unconditional ORM primary-key update. `with_for_update` has
no locking effect on SQLite, so a second session could commit a tenant or
workspace move after the final check and before the writer continued. The old
principal's PUT/restore effect then committed inside the new foreign scope; the
post-effect oracle could only report `committed_unverified` after the
unauthorized effect.

## Repair

- The writer captures the authoritative tenant/workspace snapshot **before**
  the final scope check.
- The accepted-mirror write is now a guarded
  `UPDATE canvases ... WHERE id = :id AND tenant_id = :snapshot_tenant AND
  workspace_id = :snapshot_workspace`. The conditional DML is the transaction
  linearization point and acquires SQLite's write reservation.
- Zero matched rows rolls back the pending audit/mirror work and returns a
  `409` conflict before effect. The other writer's scope move, content and
  history survive; there is no broadcast or learning capture.
- The same guard covers restore, pending-review claims and the idempotent
  duplicate-operation mirror refresh.
- Null/empty/default scope values are bound exactly. Authorization still
  treats null/empty as legacy/default, but a concurrent move between null,
  empty and `default` is still a scope move and matches zero rows.
- The existing post-commit defense is preserved: a move that commits **after**
  an authorized commit legitimately yields `committed_unverified` on readback.
  The new refusal covers a move that commits **before** the old principal's
  effect.

## Controls

The focused gate is **55 passed on Python 3.14 and 3.11**:

- the original 45 controls (39 direct + 6 scope/no-change/stale-audit probes);
- 6 new direct controls: PUT/restore workspace/tenant scope moves after the
  final check, null-to-default move, duplicate-operation refresh, and
  workspace-scoped unchanged PUT/restore twins;
- the independent verifier's 4 atomic interleavings (PUT/restore ×
  workspace/tenant), retained as `test_verifier_canvas_scope_commit_18e8.py`.

The conflict controls assert fresh-session state, unchanged audit count and
content, the winning scope move, zero broadcasts and zero correction capture.
The unchanged-scope twins assert `verified` with the expected audit/mirror.

## Affected / adjacent

- Affected selection: **187 passed, 8 deselected** on Python 3.14 and 3.11.
- Adjacent canvas projection/feedback/connected: **34 passed** on both.
- Total affected + adjacent: **221 passed** (the previous 211 plus the 10 new
  atomic controls; selections overlap and are not added to the focused total).
- Independent verifier before: 4 atomic cases failed on `18e8af4a6`
  (`verifier-atomic-before.log`); the prior 45 focused and 211 affected/adjacent
  controls passed (`verifier-focused-before.log`,
  `verifier-affected-before.log`).
- External probe rerun on the frozen repair source: **4 passed**
  (`external-probe-314.log`).

## Boundaries

- No second store, router, process-local lock or new oracle.
- PostgreSQL concurrency/soak is not claimed; the SQLite guarded DML and the
  same predicates are the tested boundary. PostgreSQL keeps the existing row
  lock plus the same predicates but was not run here.
- Other canvas routes, the unrelated route/editor/WebSocket suites, goals,
  provider writes and the whole-app ORACLE-01 inventory remain outside this
  slice.
- The auth/2FA note remains read-only next-family preparation and is not part
  of this repair.
- Feedback/shared CAS/wait/employee acceptance remains closed; historical
  `111/123`, tags and model scores are unchanged.
- No new provider, credential, consent, spend, send, download or deployment
  authority.

## Artifacts

`focused-*.log`, `affected-*.log`, `adjacent-*.log`,
`external-probe-314.log`, `verifier-atomic-before.log`,
`verifier-focused-before.log`, `verifier-affected-before.log`, `README.md`,
`TEST_RESULTS.md`, `verification.json`, `routes.json`. `MANIFEST.json` records
the SHA-256 of every artifact and changed source file.
