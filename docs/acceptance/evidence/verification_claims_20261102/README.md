# Verification claims batch 1 — TEAM-05 and ORACLE-01

Status: **submitted for independent verification; not self-accepted.** This is
the first local batch under `MARKETING_FEATURE_VERIFICATION_PLAN_2026-11-02.md`.
It closes two open original functional claims at service level; it does not
claim the remaining ten or a new whole-product score.

## Executed source

| Item | Value |
|---|---|
| Worktree | `/private/tmp/atom-canvas-successor` |
| Branch | `codex/brennan-canvas-successor-20261101` |
| Executed source | `6d62855d02` |
| Tree at execution | clean (`dirty=false`) |
| Runtime | local service-level tests, Python 3.14 venv |
| Browser | not part of this batch; these are service/registry claims |

## TEAM-05 — opt-in nightly alignment sweep

- `certify(db, chat_fn=...)` runs the full scenario × structure alignment
  battery through a controlled chat seam; the nightly worker and run-now path
  reuse the same certification pass.
- In `approve` mode, green telemetry/sweep **queues** an
  `org_politics_actions` finding and leaves the feature flag off. No policy is
  changed without the configured consent mode.
- The nightly loop calls the automation pass on its interval; a controlled
  cancellation stops it cleanly.
- Existing tests cover revocation, no-sweep fail-safe, low-telemetry block,
  approval/rejection and restart of the action state.

Evidence: `team05-tests.log` (21 passed), `oracle-team-neighborhood.log`
(271 passed including org/covpush/oracle/generic-agent).

## ORACLE-01 — postcondition oracle coverage

- Enumerated every registered action with a mutating effect; six connected
  actions are covered by postcondition verifiers (both `connected.*` and
  `brennan.*` names).
- Each verifier requires `action_result=applied`, a non-empty `remote_id`, a
  matching authoritative `read_receipt.resource_id`, `coverage` of
  single/complete, a payload digest, and a verification status that is not
  uncertain/conflict/incomplete.
- Negative controls: uncertain outcome, readback mismatch, incomplete
  verification and missing digest are all refuted.
- `oracle_registry.json` records the mutation inventory and verifier names.

Evidence: `oracle-team-tests.log` (23 passed), `oracle_registry.json`.

## Tests

| Scope | Result |
|---|---|
| Org-politics automation | **21 passed** |
| Oracle mutation coverage | **2 passed** |
| Org/covpush/oracle/generic-agent neighborhood | **271 passed** |

## Boundaries

- Service-level evidence, not a new full-UI or live-provider campaign.
- ORACLE-01 verifies the action's authoritative readback receipt; it does not
  add a second independent provider call for every mutation.
- No live provider lookup/refresh/write/send.
- Remaining original claims are still open: ORCH-01/02/07, GOAL-02, MEM-07,
  MINI-03/04/05, INT-09, ROUTE-07, plus the remaining ordinary full-app
  journeys. MINI requires a supported Linux/KVM runtime; INT/ROUTE require
  separate live authorization; ORCH/GOAL/MEM require model/planning work.
- Connected acceptance remains `6431bcb78`; historical 111/123 unchanged.
