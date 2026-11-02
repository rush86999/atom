# Verification claims batch 1b — oracle/readback repair

Status: **submitted for independent verification; not self-accepted.** This
repairs the withheld ORACLE-01 boundary and completes the runtime trigger for
MEM-07. TEAM-05 is carried forward from the accepted controlled service scope.

## Executed source

| Item | Value |
|---|---|
| Worktree | `/private/tmp/atom-canvas-successor` |
| Branch | `codex/brennan-canvas-successor-20261101` |
| Executed source | `6f0acd0bd` |
| Tree at execution | clean (`dirty=false`) |
| Runtime | local service/API tests; no browser claim in this bundle |

## ORACLE-01 repair

- A connected mutation is verified only with an explicit `verification` object
  whose `status` is exactly `verified`, no `missing_fields`, and no
  `mismatches`.
- The top-level `payload_sha256` and `provider_receipt.payload_sha256` must both
  exist and agree; a verification digest, when present, must agree too.
- Missing verification, empty verification, incomplete/mismatch status and
  digest disagreement all refute. The three independent false-pass probes now
  pass.
- The registered-action consumer (`core.assignment_executor._action_registry_adapter`)
  calls the oracle and downgrades an `applied` result to `uncertain` when the
  postcondition is refuted.
- Outlook draft creation now independently reads the created draft through
  `OutlookService.get_email_by_id` and compares to/cc/bcc, subject and body
  against the authorized request. Missing readback is `uncertain`; mismatched
  readback is `conflict`; neither creates a second draft.
- The mutation inventory in `oracle_registry.json` records six connected
  mutating actions plus the existing task/workflow verifiers.

## MEM-07 runtime trigger

A real controlled tool-failure event is processed by `ReflectionEngine` with a
real episode/segment and the existing Memento candidate pipeline. The runtime
trigger files a pending `SkillCandidate` for the original episode/agent, the
authenticated review API lists it, and the agent configuration is unchanged.
This closes the pending-candidate boundary; safe application/rollback/measured
improvement remains a broader milestone.

## TEAM-05

The controlled alignment sweep, approve-mode queued finding, nightly loop and
consent/revocation controls remain as accepted. No model-quality or 24-hour
deployment claim is added.

## Tests

| Scope | Result |
|---|---|
| Oracle/team/MEM + independent oracle probes | **29 passed** |
| Connected action/readback neighborhood | **59 passed** |
| Canvas/assignment probes | **42 passed** |
| Canvas focused suite | **127 passed** |
| Assignment regression | **167 passed** |
| Teaching neighborhood | **203 passed** |
| Frontend canvas suites | **7 passed** |

Logs are tracked in this directory. `oracle_registry.json` records the
mutation inventory.

## Changed files

```text
backend/core/assignment_executor.py
backend/core/connected_actions.py
backend/core/oracle/postcondition_verifiers.py
backend/tests/integration/test_brennan_joint_document_flow.py
backend/tests/integration/test_brennan_joint_quote_campaign.py
backend/tests/test_canvas_assignment_integration.py
backend/tests/test_memento_candidate_review.py
backend/tests/test_oracle_connected_mutations.py
backend/tests/unit/test_brennan_agent2_connected_operations.py
```

## Remaining open

ORCH-01/02/07, GOAL-02, MINI-03/04/05, INT-09, ROUTE-07 and the remaining
ordinary full-app journeys. MINI needs Linux/KVM; INT/ROUTE need separate live
authorization; ORCH/GOAL need model-backed planning/utility work. No live
provider action, send or hosted claim. Connected acceptance remains
`6431bcb78`; historical 111/123 unchanged.
