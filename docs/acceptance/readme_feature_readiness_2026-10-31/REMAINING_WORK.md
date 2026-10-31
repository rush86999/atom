# Remaining work — 2026-10-31

**Current:** 99/123 README functional claims (80.5%). Coverage target reached;
the items below are the remaining engineering, product decisions and external
dependencies. This is not a release declaration.

| Item | Owner | Next executable action | Blocker |
|---|---|---|---|
| CORE-06 / ROUTE-06 cached BYOK | Agent 1 | Make Settings → save key → Chat pass after the credential-revision rebuild; the current chat route selects an unsupported catalog model (`gpt-5.6-luna-pro`) in the harness | None; engineering/catalog-selection correction |
| ROUTE-03 cross-provider fallback | Agent 2 | Configure a two-provider policy/world and assert a failed primary produces a secondary response | Product decision on the provider policy used by the acceptance world |
| ASK-03 automatic revocation | Agent 1 / 2 | Wire the trust-calibration revoke ledger to a runtime action decision, or mark the claim inaccurate | Product decision on runtime consumer |
| GRAPH-05 browser explorer | Agent 2 | Fix the frontend graph route/profile/proxy and run the Chrome check with seeded nodes/edges | No external access; local frontend/browser work |
| Practical gate: restart while waiting / after approval preparation | Agent 1 | Extend the connected-assignment gate with a process restart and same-assignment resume | None |
| Practical gate: changed source/lesson revision invalidation | Agent 1 | Change a source or teaching revision and assert stale work/calc is rejected while completed work survives | None |
| Practical gate: ambiguity, cancellation, duplicate resume | Agent 1 | Add clarification, cancel, and idempotent/duplicate-resume controls to the assignment gate | None |
| Substantive model-quality assessment | Agent 1 | Run the frozen corpus/expectations against the locally available model, with provider/model provenance; the failure mode to fix is unsupported approvals not failing qualification and human review not being enforced before downstream action | None; safety/qualification repair |
| Assessment safety repairs | Agent 1 | Unsupported approvals must fail qualification; human review must be enforced before any downstream action | None; product-safety repair |
| ORCH-01/02/07, GOAL-02/04, GOV-04, WF-05, MEM-07 | Agent 1 | Run the model-backed scenarios against the locally available model; keep controlled-provider evidence separate | None; engineering work |
| GOV-05 OIDC SSO | Agent 1 | Stand up a bounded local IdP, complete login/callback/session | None; local IdP work |
| TEAM-01 / TEAM-05 | Agent 1 / 2 | Enforce exactly-one accountability; exercise the opt-in nightly alignment automation | Product decision/enforcement |
| MEM-07 evolution candidate | Agent 2 | Enable the controlled evolution harness and verify a pending candidate for approval | None; controlled harness work |
| MINI-03/04/05 | Agent 1 | Run the Firecracker/KVM scenarios on a KVM-capable host | **External: KVM/Firecracker host** |
| INT-09 46+ live qualification | Agent 1 | Qualify real accounts/permissions for the named providers | **External: provider accounts** |
| INST-01 pristine `make setup` | Agent 2 | Run the full dependency bootstrap on a clean checkout | None; installation campaign |
| ORACLE-01 every mutating action | Agent 1 | Expand postcondition verifiers or mark the README wording inaccurate | Product decision |
| ORCH-08 delegation depth | Agent 1 | Enforce `max_depth` in `AgentFleetService.recruit_member` or mark the claim inaccurate | Product decision |

The 24 non-verified functional claims are enumerated in
`COVERAGE_REPORT_2026-10-31.md` §4. Historical and failed-attempt evidence is
preserved; no deployment, send, credential change or connected-system write was
performed.
