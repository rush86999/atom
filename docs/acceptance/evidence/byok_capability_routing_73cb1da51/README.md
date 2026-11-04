# BYOK incident-bound recovery — 73cb1da51

Runtime candidate: `73cb1da513b2ecf6134b900ca3224750b48109a2`
(branch `codex/brennan-full-app-20261102`). This is the final recovery-epoch
repair on top of `757176e22` and `77d13377e`. No provider was called, no
credential/policy changed, and no spend or download occurred.

## Repair

Recovery is now bound to the exact feedback incidents reviewed, not just to a
scope/profile/route bucket:

- `parse_evidence_rows` preserves a stable incident id, kind and timestamp for
  every unsafe/semantic failure.
- `recover_capability_quarantine(..., incident_ids=[...])` records the exact
  reviewed observations, a meaningful `reviewed_by` and reason, and a review
  timestamp.
- `apply_capability_recoveries` releases only incidents named by the review.
  It never releases a later incident, an incident with missing/ambiguous
  timestamp, or a different route/profile/version/scope.
- A recovery with no incident binding is audit-only and releases nothing.
- Duplicate recovery is idempotent; a second reviewed recovery can release a
  second incident.
- New feedback and recovery invalidate the live evidence cache so restart and
  live selection use the same persisted feedback/journal.
- Historical failure rows/incidents remain auditable after recovery.

The five earlier boundary repairs remain in place: strict pins cannot escape,
semantic transport success is not satisfactory, one unsafe event quarantines,
evidence requires exact scope/binding, and decision history is workspace/tenant
scoped with a world-owned journal.

## Verification

- **5/5 independent boundary probes passed**.
- **1/1 independent recovery-epoch probe passed**: an old recovery does not
  clear a new unsafe incident observed after the review.
- **162 focused tests passed** in 17.90 seconds, covering both verifier probes,
  quarantine/recovery/restart, duplicate recovery, malformed/missing binding,
  two scopes, unrelated workloads, semantic outcomes, strict pins, journal
  scope/path, BPC production selection, employee regressions and learning
  feedback persistence.
- `routing-probe.json` records economy Flash selection, explicit quality
  preference, semantic no-suitable, missing-scope evidence, one-event unsafe
  quarantine and incident-bound reviewed recovery.

## Policy unchanged

Economy remains the default among eligible candidates: lowest expected cost of
a satisfactory result, Flash first-class. Explicit quality preference only
reorders eligible candidates and never bypasses safety, scope, protocol,
credentials or authority. No suitable route remains an explicit actionable
outcome.

## Boundaries

- Controlled-candidate and production-path evidence, not general model
  qualification; no live/paid inference.
- The separate procurement-wait campaign failure at `9a342109b`
  (`already_applied` versus `terminal`) reproduces before the BYOK repair; it
  belongs to Agent 1's durable-wait work and is not included in this focused
  BYOK suite. Full G5 remains open.
- Historical 111/123, previous tags, planner 5/5, goal router 1/2 and alignment
  gap 3.0 are unchanged.
