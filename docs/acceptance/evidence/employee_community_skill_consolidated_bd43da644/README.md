# Community-skill review — single-engine consolidation and current-authority binding

Status: **submitted for independent verification.** PR
[#666](https://github.com/rush86999/atom/pull/666). No merge or deployment was
performed.

## Executed source

| Item | Value |
|---|---|
| Branch | `codex/oracle01-skill-consolidation-20261106` |
| Base main | `d860072a787e6460d83260e9cb629cfa5d5ea14b` (includes PR #664) |
| Executed source | `bd43da6446f71fb0237c64c189f9e25f0b028d95` (single commit on base main) |
| Prepared branch tip (provenance) | `4e25a2836820eb4ae17286876c1788a0ade5791f` |
| Removed parallel engine | `backend/core/skill_review_write_service.py` (blob `bc9d3f905`) |
| Removed parallel test | `backend/tests/test_skill_review_write_contract.py` (blob `08b969c0d`) |
| Runtime | real scratch SQLite with fresh sessions and committed two-session authority interleaving; no live model/provider/code-sandbox |

The route file is byte-identical to base main's
`backend/api/skill_routes.py`; the route is not changed by this candidate.

## Branch hygiene

The consolidation was first pushed on the prepared branch, whose stale
pre-squash history still contained old ORCH01 evidence files. GitGuardian
flagged eight pre-existing high-entropy strings in those files even though the
files are byte-identical to base main. The candidate was therefore rebuilt as
a single commit directly on current main; no force-push was performed. The
stale commits, and the two historical community-skill bundles they carried,
are not part of this PR.

## Consolidation decision

Main already carries the verified community-skill write family from merged
PR #652: `core/community_skill_write_service.py` plus main's DB-backed
`_require_community_skill_reviewer` route helper. The prepared branch carried a
second implementation, `core/skill_review_write_service.py`, with the missing
current-authority claim.

This candidate keeps **one** engine:

- main's `community_skill_write_service` and `skill_routes` remain the engine
  and route surface;
- the branch's duplicate service and its parallel contract test are removed;
- the current-authority resolution/claim is ported into main's service.

The old bundles `employee_community_skill_review_5eb3cf626/` and
`employee_community_skill_authority_5ab9c0a37/` remain historical records of
the removed parallel engine. This bundle is the merged-source evidence.

## Scope

| Method | Path | Handler | Service |
|---|---|---|---|
| POST | `/api/skills/promote` | `promote_skill` | `core.community_skill_write_service.promote_skill` |
| DELETE | `/api/skills/{skill_id}` | `delete_skill` | `core.community_skill_write_service.delete_skill` |

Import, execute, package installation, sandbox execution, marketplace and the
remaining skill surfaces remain out of scope.

## Authority contract

- `_resolve_actor` reads the authoritative `User` row in a fresh session before
  any decision: the account must be active and the current role must satisfy
  `role_level(role) >= role_level(UserRole.TEAM_LEAD)`.
- The resolved principal freezes id, email, current role, status, active flag,
  resolved tenant and raw tenant.
- `_claim_actor` executes a guarded no-op `UPDATE User` inside the decision
  transaction, matching the frozen id, active flag, status, role and raw
  tenant. A zero-match means the principal changed after resolution; the
  service rolls back and returns typed `AUTHORITY_CHANGED` with
  `verification.effect="none"`.
- The claim runs in the same transaction as the exact-material target CAS, the
  tombstone delete and the `AuditLog` receipt. A changed principal leaves the
  peer skill row intact and writes zero audit rows.
- The route-level DB-backed TEAM_LEAD+ guard remains in place; the service
  claim is the race-safe authority boundary, not a replacement.

## Tests added

`backend/tests/test_community_skill_write_contract.py`:

- promote/delete × deactivate/demote/tenant-move authority-change twins, each
  asserting `AUTHORITY_CHANGED`, `effect=none`, peer row preserved and zero
  audits;
- stale-entry resolution controls for a deactivated or demoted current user.

`backend/tests/test_covpush_w104_gaps_b.py` route-unit fixture:

- the mocked reviewer DB now returns the authorized `team_lead` row the
  DB-backed guard reads, and the route tests exercise the routed
  `_promote_community_skill` / `_delete_community_skill` wrapper. The guard is
  not bypassed, disabled or weakened.

## Verification

| Gate | Result |
|---|---|
| Focused community-skill gate, Python 3.14 | **38 passed** |
| Focused community-skill gate, Python 3.11 | **38 passed** |
| Affected skill/registry/review/audit selection, 3.14 | **264 passed, 4 failed** |
| Affected skill/registry/review/audit selection, 3.11 | **264 passed, 4 failed** |
| Same selection on main `d860072a7`, 3.14 | 254 passed, 6 failed |
| Same selection on main `d860072a7`, 3.11 | 254 passed, 6 failed |

The 4 affected failures on both versions are the exact pre-existing
`test_round22_marketplace_security` missing-module failures, identical to the
baseline failure list. Main additionally fails the 2 route-unit fixture tests
that this candidate aligns. The candidate therefore adds **10 passing
controls** and closes 2 baseline failures while preserving all 4 baseline
failure identities.

## Boundaries

- No live model, provider, code sandbox, credential, spend, send, download,
  deployment or multi-worker operation.
- No production role, tenant, provider-eligibility, oracle, capability or
  audit gate weakened.
- No test deleted, skipped or xfailed.
- PostgreSQL runtime/soak and whole-app ORACLE remain open.
