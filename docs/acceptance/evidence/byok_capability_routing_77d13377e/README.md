# BYOK capability routing boundary repair — 77d13377e

Runtime candidate: `77d13377eab576d3356007c0e628cbf072b5f9d5`
(branch `codex/brennan-full-app-20261102`). Product routing repair is at
`757176e22`; this commit adds the extended controlled probe. No provider was
called, no credential/policy changed, and no spend or download occurred.

## Five boundary repairs

1. **Strict pins cannot escape.** An explicit capability-profile pin is
   exact-route-or-failure at the real consumer boundary
   (`pinned_structured_call`). Exceptions, `None`, timeout and malformed output
   return no result, with no unpinned retry. The separate auto-derived employee
   profile keeps its historical fallback behavior; the distinction is explicit.
2. **Satisfactory business outcomes, not transport success.** Profile evidence
   counts a row as successful only with `success=true` AND
   `quality_satisfied=true` AND no semantic/unsafe failure kind. Six
   transport-successful but quality-failed rows produce `no_suitable`. A
   semantic failure also overrides transport/quality flags.
3. **Verified unsafe outcomes quarantine immediately.** One
   `unsafe_action` row quarantines the exact profile/version/route even below
   the ordinary sample floor. Recovery requires an explicit reviewed recovery
   record (`reviewed_by` + reason) bound to scope/profile/version/route;
   recovery survives restart. Historical feedback rows are retained. An
   unrelated workload/profile is not quarantined.
4. **Exact evidence scope.** Evidence requires matching tenant, workspace,
   provider, model, profile and profile version. Missing/null workspace or
   provider is unknown/ineligible, never stamped with the reader's scope.
   Profile metadata is written to feedback rows even when the generic learning
   router is not re-ranking.
5. **Scoped decision history and world-owned journal.** The provider-policy
   settings route filters decisions against the authenticated workspace and
   tenant (and re-filters even a compatibility test double). The journal path
   follows `ATOM_CAPABILITY_ROUTING_JOURNAL`, then `ATOM_DATA_DIR`, then the
   SQLite world directory, then the office directory; no repository-shared
   history is created. Test runs without an owned journal path stay in memory.

Additional hardening: forced/sweep candidates are profile-gated, capability
calls keep at most one eligible escalation candidate, and recovery/scope
errors never grant authority.

## Verification

- **5/5 independent verifier boundary probes passed** on the clean successor:
  strict-pin consumer, semantic transport success, one-event unsafe,
  missing-workspace evidence, and route decision scoping.
- **160 focused tests passed** in 16.77 seconds, including the verifier probes,
  workload selector, BPC production path, recovery/restart, journal path,
  route scope, pinned planning, LLMService forwarding and employee regressions.
- `routing-probe.json` records the economy/quality ordering, semantic
  no-suitable, missing-scope empty evidence, one-event unsafe quarantine and
  reviewed recovery.

## Product behavior

- Economy remains the default among eligible candidates: lowest expected cost
  of a satisfactory result, latency tiebreak. Flash remains first-class.
- Explicit quality preference reorders eligible candidates only; it never
  bypasses safety, scope, protocol, credentials or authority.
- No eligible configured route produces an explicit, actionable
  `no_suitable_configured_model` outcome, not a silent weaker/local/cloud
  substitution.

## Boundaries

- This is controlled-candidate and production-path selection evidence, not a
  general model qualification campaign. No live or paid inference is claimed.
- The two-domain wait campaign test has a pre-existing failure at `9a342109b`
  (`already_applied` vs `terminal`), verified in a clean worktree without these
  BYOK changes. It belongs to Agent 1's durable-wait work and is excluded from
  this focused BYOK neighborhood; full G5 remains open.
- Historical 111/123, previous tags, planner 5/5, goal router 1/2 and alignment
  gap 3.0 are unchanged.
