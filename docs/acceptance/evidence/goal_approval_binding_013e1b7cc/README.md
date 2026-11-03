# Public goal approval binding — exact reviewed decision

Status: **submitted for independent verification; not self-accepted.**

This slice closes the public approval replay: approving decision A could open
pending decision B, and repeating A's identical HTTP request then approved B
without a fresh review. Approval is now bound to the exact reviewed pending
decision, not to whichever decision is current.

## Executed source

| Item | Value |
|---|---|
| Branch | `codex/brennan-full-app-20261102` |
| Worktree | `/private/tmp/atom-full-app` (clean) |
| Goal-binding slice | `013e1b7cc` |
| Integrated source | `4968a92aa` (includes Agent 1's structured consumer slice `bf9de381b`) |
| Tree at integrated run | clean |
| Transport | controlled local service/DB; no live provider |

The integrated source adds Agent 1's typed no-tool/REPLAN-repair consumer
slice on top of the goal-binding source. Both slices are covered by this
bundle's source hashes and combined test run.

## Contract

Each held decision exposes three fields on `run.pending_decision`:

- `decision_id` — stable identity for this one reviewed decision;
- `decision_generation` — the persisted `human_interventions` generation;
- `decision_binding` — SHA-256 over canonical reviewed material.

The binding material includes the run id/tenant/workspace/goal/agent/role/
supervision/created-by, the held status, plan, cursor, evolving parameters,
waiting spec, replan/progress counters, and the complete decision payload
(excluding the binding envelope itself).

`POST /api/goal-runs/{id}/resume` now requires `decision_id` and
`decision_binding`. The service:

1. validates the supplied id and binding against authoritative persisted
   run/pending material (recomputed, never trusted from the payload alone);
2. performs one conditional UPDATE bound to the same run/workspace/status/
   non-null pending/generation;
3. only then records learning/approval and executes the reviewed decision.

Missing/stale bindings return a targeted `409 decision_review_required` or
`409 stale_decision_review`; no HITL, run, learning or executor state is
changed first. The run route snapshots only HITL rows whose stored decision id
matches the reviewed id and closes only those after a successful claim, so a
newer decision/checkpoint stays pending with its own reviewer/history.

Both the run page and the approvals queue are bound:

- the goal-run page sends `decision_id`/`decision_binding` from the run's
  current pending decision and surfaces refresh-required conflicts;
- the approvals queue posts the exact HITL action id; both approval routes
  preflight the action's stored binding against the authoritative run before
  marking the HITL row, then the bridge passes the same binding to the
  service. Legacy unbound rows are refused, not silently applied.

## Controls

`backend/tests/test_goal_effect_family_controls.py` (15 tests) includes:

- bound A approval; A opens B; replay of A's exact body → `409
  stale_decision_review`, exactly one executed decision, B still pending;
- unbound approval → `409 decision_review_required`, HITL row still pending;
- changed decision rationale after review → stale, no executor;
- changed plan after review → stale, no executor;
- duplicate rejection → one override;
- new checkpoint created during execution remains pending while A's row closes;
- the earlier simultaneous/stale/fresh-session service controls and
  wrong-scope/action-registry controls.

`test_hitl_resume.py` adds preflight tests for stale goal decisions, legacy
unbound actions and non-goal actions; `test_hitl_approvals_journey.py` adds a
stale goal action through the public approvals alias, proving the HITL row is
not changed before the refusal.

## Results

| Scope | Result |
|---|---|
| Integrated backend goal/approval + structured consumer suite | **209 passed** |
| Clean goal/approval slice (without Agent 1 slice) | **204 passed** |
| Clean frontend goal-run + approvals suites | **46 passed** |
| Adapted verifier HTTP probe (legitimately bound A, replay A) | **passed** |
| Service resume claim probe | **2/2 scenarios passed** |
| Original unbound verifier probe | first request **409 decision_review_required** (expected refusal) |

The adapted verifier probe is the same probe with the first request carrying
`first_hold["decision_id"]` and `first_hold["decision_binding"]`; its replay
assertion (A cannot execute B) remains unchanged.

## Boundaries

Interrupted-claim reconciliation and provider-accepted/lost-confirmation
replay are **not** claimed here; the binding prevents a stale approval from
executing a different decision, but a crash between claim and execution is a
separately mapped durability item. No live provider action, send, credential,
consent or spend. Historical `111/123`, the 123 denominator and prior accepted
sources/tags are unchanged. Whole-app ORACLE remains open.
