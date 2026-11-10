# Verified manual presence override / clear at `310e72aec`

- Branch: `codex/web-presence-override-20261110`
- Base: `310e72aecd1a4041a35af6ac093379d39b93556b`
- Repair commit: `29dcfaad900d4aa91c84c40996f024f1cf2470e9`
- Scope: ORACLE-01 bounded family — two presence mutations, the essential state
  read, and the existing heartbeat/expiry consumer path. Not whole-app ORACLE.

## Original runtime failure reproduced

A real scratch SQLite + JWT public-API probe (`original-failure/repro-before.py`)
showed:

- `POST /api/users/{self}/activity/override` with a valid future aware expiry:
  `200`, then `GET /state` `500`.
- Same with a naive expiry (`2030-01-01T00:00:00`): `200`, then `GET /state`
  `500`.
- An expired override followed by `GET /state`: `500`.
- A foreign user `GET /state`: `500`.
- Invalid state and invalid expiry were already typed `400`.
- Foreign set/clear were already `403`.

The cause was SQLite returning naive `manual_override_expires_at` values while
the service compared them with an aware UTC `now`; the broad route catch turned
the `TypeError` into `500`.

The root's independent negative is preserved unchanged under
`root-independent/`: 2 actor-race controls passed and the uncertainty control
failed because a `202` unknown was consumed as success by the existing hook.
No file in that packet was rewritten.

## Repair

`backend/core/presence_override_write_service.py` uses the existing
`UserActivity` table, `UserActivityService` and `AuditLog` receipt pattern:

- validated raw actor snapshot is pinned by a guarded no-op `User` UPDATE in
  the same transaction as the target CAS and audit row;
- current member may mutate only their own presence;
- operation id, request/prior/result digests are immutable audit material;
- same operation/material is `already_applied`; changed material or changed
  authority is refused; a stale target CAS is `conflict`;
- same-state request is a truthful `no_change` with `effect: none`;
- after commit, an independent fresh Session verifies both the activity row and
  audit row;
- confirmed pre-commit rollback reports `effect: none`;
- `committed_unverified` reports HTTP `503` with `success:false`,
  `effect:committed`, `replay:do_not_repeat`; `effect_unknown` reports HTTP
  `503` with `success:false`, `effect:unknown`, `replay:do_not_repeat` and
  `COMMIT_OUTCOME_UNKNOWN`; neither is a false `2xx` or false rollback;
- only a confirmed pre-commit rollback reports `effect:none`;
- expiry is parsed/normalized to UTC only at the boundary and responses carry
  `+00:00`;
- expired overrides are cleared on read, transition batch and supervisor read;
- heartbeat state update is CAS-guarded by `manual_override=false`, so a
  concurrent override is not overwritten/resurrected.

`frontend-nextjs/hooks/useUserActivity.ts` now rejects ambiguous `202`/`503`
and malformed/missing state payloads without replacing the prior valid state,
and surfaces the existing API error message. Existing method signatures and
successful legacy `200` state payloads remain compatible.

## Controls

- Backend activity/public-API selection: **62 passed**, exit 0
  (`logs/backend-controls.log`). Includes fresh-process readback, actor claim,
  actor-change replay refusal, stale CAS, no-change, forced after-commit lost
  confirmation, 202→503 contract and existing activity callers.
- Frontend hook: **39 passed**, exit 0
  (`logs/frontend-hook-controls.log`). Includes 202 unknown, 503 unknown,
  malformed state and clear-failure state preservation.
- `tsc --noEmit`: exit 0.
- Root independent exact rerun after the fix: **3 passed in 3.98s**, same
  source `29dcfaad9` (`root-independent/independent-3pass-review.json` and
  `independent-3pass-controls.log`). The earlier `tgw52lci` 2-pass/1-fail
  negative remains preserved separately.

Frontend tests reused an existing local `node_modules` directory through a
temporary symlink; no install or download was performed.

## Limits

- Only this two-mutation/read family is addressed; the 836-route ORACLE claim,
  PostgreSQL and browser claims remain open.
- No live DB, provider/model, browser, credential, spend, install, deployment,
  PR or merge.
- Root independent exact probe and review are still required.
- The historical 143 claims / 18 goals are unchanged.
