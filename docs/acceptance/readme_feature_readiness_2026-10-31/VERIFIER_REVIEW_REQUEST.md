# Independent verifier review request — integrated 99/123 candidate

**Date:** 2026-10-31 (integrated campaign)
**Prepared by:** Agent 2 (README breadth + acceptance)
**Status requested:** review of the frozen claim matrix and evidence, not a
release approval.

## 1. Result

| Question | Answer |
|---|---|
| Denominator | **123 eligible functional claims** (unchanged; README hash/commit pinned) |
| Verified | **99 / 123 = 80.5%** |
| Not verified | 24 functional claims |
| Security | 8 / 8 separately |
| Performance | 0 / 3 separately (test count reported; latency/throughput unmeasured) |
| Compatibility | 0 / 4 separately |
| Comparative marketing | 0 / 5 separately |
| Broad run | 130 claims, 110 verified, **0 failed, 0 group errors** |
| Install/restart | process-level task/workflow/Office canvas/goal-run checks pass |
| Scripts | harness and install exit nonzero on a failed assertion |

The 99 includes GOAL-01 after its objective status was integrated and its
downstream success semantics were verified. It excludes ASK-03, ROUTE-03 and
GRAPH-05, which are deliberately left partial rather than counted on weaker
evidence. The final audit downgraded only five claims whose assertions were
weaker than their frozen acceptance: ORACLE-01, GOV-05, TEAM-01, TEAM-05,
CORE-06.

## 2. New executable evidence

| Claim | Evidence |
|---|---|
| GOV-02 | goal checkpoint held before approval; approval resumed into one canvas; rejection created none |
| GOV-03 | real `tasks.create` execution feed with actor/action/target/outcome and replay |
| GOAL-01 | 2/5 `objective_satisfied`, 3/3 `max_steps_exceeded`; persisted execution completed; audit success |
| GOAL-05 | same paused run identity/status/canvases after real backend restart; one resumed deliverable |
| WF-07 | template import + execution completed with per-step results; unknown id 404 |
| MEM-01 | real `sync_turn` hook persisted the controlled fact; transient chatter absent |
| MEM-04 | 10 episodes → readiness → exam → recorded INTERN promotion; empty agent not promoted |
| CORE-04 | taught rule changed a later answer; wrong-agent and wrong-goal controls; corrected lesson applied |
| ASK-01 | 20 oracle-verified outcomes → capability supervised → gate propose→execute; reset control proposed |
| ASK-05 | stats, cold-start refusal, gated certification queue, approval flips enforcement |
| ROUTE-04 | 56 feedback rows changed selection `minimax-m3`→`gpt-4o`; readiness true |
| IO-06 | gateway request span + local Langfuse collector batch, no secrets |
| OFF-07 | agent write delivered to both the canvas subscriber and the `user:{uid}` subscriber with the same structured revision; unrelated canvas excluded |
| TEAM-06 | incumbency/reviewer/COI report baselines; empty-window zero control |
| INT-04 | registered HubSpot adapter read with bearer token/path assertions; missing token refused |
| INT-05 | external send held at HITL; one effect after approval; sequential retry duplicate; approval replay 400; two simultaneous retries → one effect; restart-after-claim, changed-payload conflict, persistence-failure uncertainty and before-effect failure all leave the effect count at one/zero; a parameter changed after approval is refused before claim creation with zero transport; rejection still blocked |
| INT-07 | original-bytes HMAC accepted once, replay duplicate, forged/missing 401 |

## 3. Product fixes in the integrated candidate

- stable/registered workflow-template instances and linear step chaining;
- canvas WebSocket on a dependency-free router with its own token/ownership
  check; Office broadcast mirrors to the canvas page manager;
- single `/api/graphrag` mount (the double prefix is gone);
- episode-create route handles the production dict record;
- graduation-exam sandbox no longer treats SQLAlchemy `MetaData` as JSON;
- `objective_satisfied` is success for audit, experience confidence, plan
  adherence and persisted execution status;
- fallback ladder includes async-only local providers;
- install/restart evidence includes a paused goal checkpoint;
- approved outbound effects atomically claim the existing
  `task_operation_records` row before dispatch, bind it to the complete
  payload hash, and persist success/failed-before-effect/uncertain-effect
  distinctly; competing/restarted callers never resend. The complete
  normalized request is compared with the immutable reviewed payload before
  claiming; a changed parameter is refused before any claim or transport, and
  the captured approved payload is dispatched.

## 3.1 Practical employee gate

The controlled connected-assignment gate passed: real catalog/Parquet retrieval,
teaching standards, grounded calculation (`85.00` sum / `3` count), DOCX/PPTX
artifacts, approval/outbox, and durable reopen. Evidence:
`evidence/practical-assignment.json`.

The five remaining boundaries were then exercised through the real Assignments
page on the sibling `codex/employee-execution-readiness` candidate (source
`b24f67c29`): **5/5 checks passed** — wait→backend restart→resume, changed
source revision invalidates stale mapping work while completed work survives,
ambiguous mapping identity is refused without sheet/version and resolved with
it, cancellation survives reload and refuses a late response, and duplicate
concurrent resume dispatches once with no outbox effect. Evidence:
`atom-employee-execution/docs/acceptance/evidence/durable_assignment_20261031/assignment-recovery-browser/`.
This is a product gate, not an addition to the README breadth denominator.

---

## 4. Specific remaining work

- **CORE-06 / ROUTE-06**: the credential-revision rebuild, dispatch-time
  backstop and negative provider-cache reset are implemented, but the full
  Settings → save key → Chat acceptance still selects an unsupported catalog
  model. This is an engineering/catalog-selection issue, not a missing owner
  decision. CORE-06 and ROUTE-06 remain partial and are not counted.
- **ROUTE-03**: this world's provider policy admits one gateway route; a
  failed upstream returns `all_providers_failed`. The async-provider fallback
  fix is in place, but no cross-provider fallback world is configured yet.
- **ORACLE-01**: only two postcondition verifiers; "every mutating action" is
  not established.
- **GOV-05**: OIDC config only; login 503 and no IdP callback.
- **TEAM-01/05**: exactly-one accountability and nightly automation are not
  enforced/exercised.
- **Model-backed**: model access is now available locally. ORCH-01/02/07,
  GOAL-02/04, GOV-04, WF-05, MEM-07 and ROUTE-07 remain engineering work.
  The substantive assessment was executed on local `ollama`/`llama3.1:8b`;
  it scored 17/18 determinate in every phase and produced a false APPROVE on
  `Q-012`, so the qualification verdict is **failed**, not pending
  infrastructure.
- **Assessment safety repairs**: done on `codex/employee-execution-readiness`
  (source `6363e3794`; typed outcomes `f8198c60e`). Unsupported approvals fail qualification; the default
  review policy requires human approval before downstream action; approval is
  bound to a canonical artifact digest recomputed from persisted content plus
  execution/source/policy/canvas revisions and an atomic assessment revision.
  A route-level test confirms unreviewed refusal, exact-execution approval,
  and `content_drift` refusal when one reviewed field changes with the stored
  hash untouched. **106 focused tests pass**. Evidence:
  `atom-employee-execution/docs/acceptance/evidence/durable_assignment_20261031/employee-execution-assessment-approval/`.
- **Environment/external**: MINI-03/04/05 need KVM; INT-09 needs real provider
  accounts; INST-01 needs a pristine `make setup`.
- **GRAPH-05**: API query verified; the browser explorer check is not yet
  counted (the standalone browser harness is not part of the authoritative
  result).
- **ASK-03**: automation ledger revocation is consent-gated and has no
  runtime action consumer; left partial.

## 5. Decision requested

- **Agree** — denominator and 99/123 integrated set accepted as reviewed.
- **Disagree** — name the claim and the boundary/evidence problem; it will be
  rerun or downgraded, not argued.
- **Conditional** — specify the additional worlds required (local IdP, live
  provider, KVM/Firecracker, authorized model, cross-provider policy).

No deployment, real send, credential change or connected-system write was
performed. Controlled-provider evidence is separated from model-quality and
live-delivery evidence.
