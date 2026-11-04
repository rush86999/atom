# BYOK durable incident identity — 5bbefe4c2

Runtime candidate: `5bbefe4c2d84ba62673bd298a0561d0c3aa434de`
(branch `codex/brennan-full-app-20261102`). This is the incident-identity
repair on top of `73cb1da51`. No provider was called, no credential/policy
changed, and no spend or download occurred.

## Repair

Feedback observation identity is now durable and material-bound:

- `load_feedback_evidence` carries the authoritative feedback row primary key
  (`row.id`) and `routing_result_id` through the production projection.
- Incident identity is `feedback-<row_id>-<material_digest>`. The routing result
  is retained as separate provenance, not used as the sole observation key.
- The material digest covers profile/version, exact scope, route, creation
  time, failure kind, success and quality flags. A row updated from safe to
  unsafe, or otherwise materially changed, receives a new incident ID and
  cannot inherit an old review.
- Legacy rows without a trustworthy row ID use a stable material digest;
  missing creation ordering is marked unreliable and cannot be released by
  automated recovery. Duplicate identical digests are marked ambiguous and
  fail closed.
- Array position, arrival order and current sample count are no longer part of
  the identity. Adding a later success row or reordering rows does not change
  an older incident's ID.
- Recovery still releases only named incidents, honors review time, remains
  idempotent, survives restart, and invalidates the live evidence cache on new
  feedback/recovery.

## Verification

- **1/1 independent production-loader identity probe passed**: a later success
  row inserted ahead of an unchanged unsafe row does not change its incident ID
  or break its existing recovery.
- **5/5 earlier boundary probes passed**; **1/1 recovery-epoch probe passed**.
- **168 focused tests passed** in 17.87 seconds, including production-loader
  controls for unrelated/reordered rows, fresh session/restart, new unsafe
  incidents, duplicate reviews, changed material, legacy ambiguous identity,
  two scopes, strict pins, semantic outcomes, journal scope/path and BPC
  economy selection.
- `routing-probe.json` retains the economy-Flash/quality-preference/semantic/
  unsafe/recovery controls.

## Policy unchanged

Economy remains the default among eligible configured routes: lowest expected
cost of a satisfactory result, including capable Flash. Explicit quality
preference only reorders eligible candidates and never bypasses safety, scope,
protocol, credentials or authority. A failed workload preserves the job and
explains the next useful action rather than silently weakening the task or
switching provider class.

## Boundaries

- Controlled-candidate and production-path evidence, not general model
  qualification; no live/paid inference.
- The separate procurement-wait campaign failure at `9a342109b`
  (`already_applied` versus `terminal`) belongs to Agent 1's durable-wait work
  and is not part of this focused BYOK suite. Full G5 remains open.
- Historical 111/123, previous tags, planner 5/5, goal router 1/2 and alignment
  gap 3.0 are unchanged.
