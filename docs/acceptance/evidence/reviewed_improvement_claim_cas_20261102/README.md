# Reviewed-apply claim/revision CAS — evidence

Status: **submitted for independent verification; not self-accepted.**

Closes the one blocking interleaving from the `52549c51a` recheck: a newer
review committed between validation and claim was overwritten by the older
application. The prior accepted/preserved bundles are unchanged.

## Executed source

| Item | Value |
|---|---|
| Branch | `codex/brennan-full-app-20261102` |
| Executed source | `c1074f0a9ecb057275b6990ef24eef1742c724a1` |
| Worktree | `/private/tmp/atom-consolidated-clean` (isolated) |
| Tree at execution | clean |
| Applied files | `core/reviewed_improvement.py`, `api/autodev_review_routes.py`, `tests/test_reviewed_improvement_boundaries.py` |

## Claim invariant

- The DB claim binds **status=validated**, the exact **review revision**
  (dialect-aware JSON predicate; unsupported dialects fail closed), the
  `validated_at` revision, and an `exists()` predicate requiring the candidate's
  current employee to still be in the reviewed tenant/workspace.
- Review/reject use conditional updates against the current revision and cannot
  overwrite `applying`/`promoted` state. A validated→validated re-review
  increments the revision even when material is identical, invalidating older
  claims.
- Final promotion is conditional on the claimed revision; it merges the applied
  record into the authoritative review JSON rather than committing a dirty ORM
  snapshot.
- A zero-row claim rolls back before package/registry effects, reloads the
  authoritative row, returns the original result only for the exact
  already-applied same review, and otherwise refuses (409/fresh review).

## Controls on this source

| Control | Expected | Result |
|---|---|---|
| Independent CAS probe: new review between validation and claim | old apply refuses, review 2 preserved, zero executions | passed |
| Repo: changed material + new review | conflict, new review preserved | passed |
| Repo: identical material + new revision | older claim invalidated | passed |
| Repo: rejection before claim | rejection wins, no execution | passed |
| Repo: employee move before claim | claim 0 rows, no execution | passed |
| Repo: two applications, same review | one skill/execution, same returned id | passed |
| Repo: failed apply then retry | no Active row on failure; retry reuses package, one execution | passed |
| Original five boundary controls | viewer, move, atomic failure, stale replay, changed material | passed |

Suites: **487 backend passed** (`backend-tests.log`), CAS probe **1 passed**
(`cas-probe.log`), frontend **7 passed** (`frontend-tests.log`).

## Scope

No live provider call, credential, spend, send or reseed. Historical 111/123,
the 123 denominator and prior accepted sources/bundles are unchanged.
