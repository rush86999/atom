# Generic source answer: full wait-record scope CAS

Source under test: merge `9e69b9a9c` (A1 root probe `1ac32d015` normally
merged with source `20946867e`) plus this commit's two files:

- `backend/api/agent_routes.py`
- `backend/tests/test_lead_generic_source_scope_cas.py`

## Finding and repair

Root's four permanent negatives changed `workspace_id`, `tenant_id`,
`user_id` or `params` on the durable `HITLAction` after the authorized source
read but before the pending claim. The old CAS compared only
`id/status/action_type/context_snapshot`, so the stale answer approved,
resumed and created an actual task.

The claim now freezes the complete authoritative wait record before any
await/source read and compares it in one conditional UPDATE: id, pending
status, action type, agent, workspace, tenant, owner, params and the full
context snapshot. Physical SQL NULL vs stored JSON null is selected beside
the ORM row and carried into the CAS (the canonical raw-JSON pattern used by
the goal write service); null/default/empty Personal rows stay claimable.
The admitted actor's current authority is part of the same UPDATE through the
existing `actor_authority_conditions` helper.

A lost CAS reloads the row and rechecks the complete binding before treating
an accepted answer as an idempotent replay. Same-material replay is allowed
only when scope/owner/params/job/execution/correlation still match; a foreign
or retargeted approved review is refused with 409 and zero effects.

## Evidence

| Run | Result | Raw log |
|---|---|---|
| Root four negatives, before | 4 failed / exit 1 | `root-scope-cas4-negative.log`, `before-scope4-fail.log` |
| Existing 22 source-answer controls, before | 22 passed / exit 0 | `before-22-pass.log` |
| Extended scope matrix (7 field classes + lost CAS + 3 physical null kinds) | 11 passed / exit 0 | `after-scope11-pass.log` |
| Combined focused family (22 prior + 11 scope + text-only/personal/readback/exact-event) | 52 passed / exit 0 | `after-final52-pass.log` |

All pytest runs used `/private/tmp/atom-agent-cli/run_bounded_test_gate.py`
(`--profile bounded`), the existing `venv314` interpreter, a fresh unique
`TESTING=1` DB/data/Lance/output/basetemp world and a synthetic `SECRET_KEY`.
No dependency install, live model/provider/account/send/spend/deploy, or
frontend change. Root owns independent review and merge; this packet is not
self-acceptance.
