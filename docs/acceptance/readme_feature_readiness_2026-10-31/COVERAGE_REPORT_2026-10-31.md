# README feature-readiness — integrated campaign result

**Date:** 2026-10-31 (final integrated candidate)
**Branch:** `codex/readme-feature-readiness`
**Base checkpoint:** tag `local-core-2026-10-30-final` (`da9cc8b12de3639f59cc5b8ea84338c5f507dc6d`)
**README:** `README.md` sha256 `392b3ca2fe88cb94c326f02318bc46273da972736b807f793c3ae8246b2bcce0`

> **Status: 99/123 = 80.5%, awaiting independent verifier agreement.**
> This is a self-assessed integrated campaign result, not a release
> declaration. No deployment or publication was performed. The denominator is
> unchanged at 123 eligible functional claims.

---

## 1. Final result

| Measure | Value |
|---|---:|
| Eligible functional claims (frozen) | **123** |
| Verified functional claims | **99** |
| Coverage | **80.5%** |
| Not verified (partial / unverified / blocked / env-limited / inaccurate) | **24** |
| Security claims (tracked separately) | 8 / 8 verified |
| Performance claims (tracked separately) | 0 / 3 verified |
| Compatibility claims (tracked separately) | 0 / 4 verified |
| Comparative marketing claims (tracked separately) | 0 / 5 verified |

The integrated run executed all 17 acceptance groups on one marked world:
**130 claims, 110 verified, 0 failed, 0 group errors**, plus the process-level
install/restart evidence and the existing frontend evidence. The explicit
5-claim final audit then downgraded only the claims whose assertions were
weaker than their frozen acceptance (ORACLE-01, GOV-05, TEAM-01, TEAM-05,
CORE-06). The earlier 18-claim audit is retained as history.

### Category breakdown

| Category | Total | Verified | Not verified |
|---|---:|---:|---:|
| agent-radio | 4 | 4 | 0 |
| agent-teams | 6 | 4 | 2 |
| ask | 5 | 4 | 1 |
| core-workspace | 7 | 6 | 1 |
| gateway | 6 | 6 | 0 |
| goals | 5 | 3 | 2 |
| governance | 8 | 6 | 2 |
| graphrag | 5 | 4 | 1 |
| hybrid-search | 5 | 5 | 0 |
| installation | 5 | 4 | 1 |
| integrations | 9 | 8 | 1 |
| interoperability | 6 | 6 | 0 |
| memory | 7 | 6 | 1 |
| mini-apps | 5 | 2 | 3 |
| office | 8 | 8 | 0 |
| oracle | 6 | 5 | 1 |
| orchestration | 8 | 4 | 4 |
| routing | 7 | 4 | 3 |
| vfs | 4 | 4 | 0 |
| workflows | 7 | 6 | 1 |

---

## 2. What the new waves proved

### Approval + audit + goal durability + templates

- **GOV-02** — a goal-run checkpoint held the deliverable, approval resumed
  the same run and created exactly one canvas; rejection created none.
- **GOV-03** — a real `GenericAgent` turn executed `tasks.create`; the audit
  feed carried actor, action, target and outcome, and the execution replay
  had `execution_start → tool:tasks.create → execution_complete`.
- **GOAL-05** — a paused goal run kept identity, status, plan and canvases
  across a real backend process restart; approval resumed it into exactly
  one deliverable.
- **WF-07** — a starter template import + execution completed with two
  per-step results; an unknown template returned 404.

### Memory + lesson application

- **MEM-01** — the real `sync_turn` hook persisted the controlled-model fact
  with the correct category; transient chatter did not persist.
- **MEM-04** — ten session-backed episodes produced readiness, a passing
  graduation exam, a recorded promotion to INTERN, and an empty agent stayed
  unready/unpromoted.
- **CORE-04** — a taught rule reached a later turn and changed its observable
  answer; a different agent did not receive it; a goal-scoped lesson did not
  leak; a corrected lesson replaced the old value.

### Ask/trust

- **ASK-01** — twenty oracle-verified `tasks.create` outcomes graduated the
  action through the capability path; the gate changed from propose to
  execute. A reset `canvas_edit` capability still proposed.
- **ASK-05** — the admin stats surface, cold-start certification refusal,
  gated relaxation queue and enforcement switch were exercised end to end.

### Routing + tracing

- **ROUTE-04** — 56 feedback rows changed the selected route from
  `minimax-m3` to `gpt-4o`; the readiness surface reported two qualified
  models.
- **IO-06** — a real gateway request emitted `llm.gateway.request` with
  model/provider/status attributes; a local collector received a
  `trace-create` + `span-create` batch with no secret values.

### Office + teams + integrations

- **OFF-07** — the agent write was delivered on **both** live channels:
  the canvas subscriber and the working `user:{uid}` subscriber each received
  the same structured snapshot/revision; the unrelated canvas was not
  targeted. The direct `notify_file_canvases()` call was removed from the
  assertion path.
- **TEAM-06** — the org dynamics report computed the expected incumbency,
  reviewer and radio→recruit COI baselines; an empty window was zero.
- **INT-04** — the registered HubSpot adapter read controlled records with
  the bearer token and path asserted; a missing token was refused.
- **INT-05** — an external send returned `waiting_approval` with no effect;
  approval produced exactly one controlled send; repeating the approved
  operation returned `duplicate` with the effect count still 1; replaying the
  approval endpoint returned 400 and did not send again; rejection kept the
  second pattern blocked. The durable claim now uses the existing
  `task_operation_records` arbiter, bound to the complete payload hash:
  - two simultaneous retries produced one success and one
    `uncertain_effect`/in-progress, with **one** effect;
  - a persisted `dispatching` claim after a simulated restart did not resend;
  - a changed payload on the same approval key returned `conflict` with no
    transport;
  - transport success followed by a failed confirmation write stayed
    `uncertain_effect`, and retry did not send again;
  - a known-before-effect failure was stored as `failed_before_effect` and
    was not auto-resent;
  - approval binding: the complete normalized request is compared with the
    immutable reviewed payload before the claim is created. An approved
    send whose content was changed returned `approval_binding_mismatch`,
    created **no claim row** and made **zero transport calls**. The captured
    approved payload — not the current request — is what gets dispatched.
- **INT-07** — a Slack HMAC signature over the original bytes was accepted
  once, replay was duplicate, and forged/missing signatures were 401.

### Objective integration

- **GOAL-01** — `GenericAgent.execute()` stopped at 2/5 on the satisfying
  predicate and returned `objective_satisfied`; the impossible control burned
  3/3 and returned `max_steps_exceeded`. The satisfied run persisted as a
  successful `AgentExecution` and the audit close-out was `success=true` with
  `objective_satisfied` recorded. It is now counted.

---

## 3. Fixes required to make the claims executable

1. **Workflow template execution** — `create_workflow_from_template` generated
   an id that was never registered in the orchestrator, and `execute_template`
   executed that unknown id. The instance id is now stable, the generated
   definition is registered with the orchestrator, and linear templates chain
   their `next_steps`. Import accepts template parameters.
2. **Canvas WebSocket** — the canvas WS route inherited the HTTP-only pilot
   dependency and could not complete a handshake; it now lives on a
   dependency-free sibling router with its own token/ownership checks.
   Office broadcasts now mirror to the canvas page's connection manager.
3. **GraphRAG mount** — `/api/graphrag` was mounted twice, producing
   `/api/graphrag/api/graphrag`. The public/frontend path is now the single
   correct prefix.
4. **Episode creation** — the route treated the production episode dict as an
   ORM object; explicit `/api/episodes/create` now handles both shapes.
5. **Graduation exam sandbox** — `EpisodeSegment.metadata` is SQLAlchemy's
   declarative MetaData, not a JSON payload; the executor now uses an explicit
   JSON field or empty metadata.
6. **Objective status consumers** — `objective_satisfied` is treated as a
   successful terminal state for plan adherence, BPE close-out, audit
   completeness, experience confidence and persisted execution status.
7. **Provider fallback** — the fallback ladder now includes async-only
   clients (the local Ollama runtime), so cross-provider resilience is not
   silently reduced to one provider.
8. **Process-level install** — the install script now exercises a goal run
   paused on a checkpoint across a real restart, plus the existing task,
   workflow and Office canvas durability checks, and exits nonzero on failure.
9. **Approved outbound effect claim** — the gateway reuses the durable
   `task_operation_records` uniqueness arbiter. The claim is inserted before
   dispatch, bound to a hash of the complete validated payload, and records
   `claimed` / `dispatching` / `succeeded` / `failed_before_effect` /
   `uncertain_effect` distinctly. A competing or restarted caller never
   dispatches; possible-effect states require reconciliation and are never
   auto-resent.

The earlier fixes are retained: world deletion guard, MCP egress policy,
ORACLE-06 executable re-delegation, SEARCH-02 semantic retrieval and SEARCH-04
citeable-path resolution, workflow versioning/rollback, GraphRAG argument
order and deterministic extraction fallback.

---

## 4. Not verified (24 functional claims)

| Claim | What is missing | Status |
|---|---|---|
| ORCH-01 | Queen blueprint requires a usable authorized reasoning model | unverified |
| ORCH-02 | Fleet open-ended task requires the same model | unverified |
| ORCH-07 | fleet routing audit row requires the same model | unverified |
| ORCH-08 | `DelegationChain.max_depth` is stored, not enforced in `recruit_member` | **inaccurate** |
| GOV-04 | Training session creation needs a blocked model-backed run | partial |
| GOV-05 | OIDC config round-trips, but login returned 503; no IdP callback/session | partial |
| ORACLE-01 | Registry covers only `trigger_workflow` and `tasks.create`, not every mutating action | partial |
| ASK-03 | Automatic revocation is consent-gated; no runtime consumer is wired | partial |
| TEAM-01 | Exactly-one accountability is not validated/enforced | partial |
| TEAM-05 | Manual sweep with controlled chat; nightly automation not exercised | partial |
| MEM-07 | Evolution candidate harness is disabled | unverified |
| MINI-03 | Firecracker/KVM unavailable on this host | environment_limited |
| MINI-04 | Firecracker runtime unavailable | environment_limited |
| MINI-05 | microVM isolation cannot be exercised without KVM | architecture_only |
| GRAPH-05 | D3 explorer browser check; API query already verified | partial |
| INT-09 | Live qualification of 46+ providers needs real accounts/permissions | blocked_external |
| ROUTE-03 | Provider policy admits one gateway route; no cross-provider fallback | partial |
| ROUTE-06 | Local provider serves chat, but user-selected local route is not exercised | partial |
| ROUTE-07 | opencode-go needs a real subscription key | unverified |
| GOAL-02 | Utility-target scoring inside the model-backed ReAct loop | unverified |
| GOAL-04 | Stuck detection inside the model-backed ReAct loop | unverified |
| WF-05 | Workflow pause/resume needs a low-maturity model-backed run | partial |
| CORE-06 | Settings → save key → route without restart is not demonstrated | partial |
| INST-01 | Pristine `make setup` dependency bootstrap not run | unverified |

The 24 are not deleted. Each remains in the frozen inventory with its evidence
or blocker.

---

## 5. Shared/product defects still open

1. **Cached BYOK refresh** — the credential-revision rebuild, dispatch-time
   backstop and negative provider-cache reset are implemented, but the full
   Settings → save key → Chat acceptance still fails in the harness because
   the chat router selects an unsupported catalog model after the rebuild.
   CORE-06 remains **partial** and is not counted; ROUTE-06 also remains
   partial.
2. **Provider policy / fallback** — the async-client fallback fix is in place,
   but this world's saved provider policy admits one gateway route; ROUTE-03
   remains partial until a cross-provider fallback world is configured.
3. **Model-backed gates** — ORCH-01/02/07, GOAL-02/04, GOV-04, WF-05, MEM-07
   and ROUTE-07 require an authorized usable model or external key. No
   deterministic arithmetic or controlled stub is substituted for judgment
   evidence.

---

## 5.1 Practical employee gate — controlled orchestration

The connected-assignment acceptance (`assignment_connected_acceptance.py`)
passed on the integrated candidate:

- real scoped `DatasetEntry` → real materialized Parquet rows;
- delivered teaching standards (document and presentation) applied;
- grounded sum (`85.00`) and count (`3`) over the full eligible sheet;
- generated DOCX/PPTX artifacts with source-bound references and hashes;
- controlled approval/outbox with no provider contact;
- durable reopen/read-back of both completed assignments.

Evidence: `evidence/practical-assignment.json`.

**Browser-level follow-up (separate candidate):** the five remaining boundaries
were exercised through the real Assignments page on
`codex/employee-execution-readiness` (source `b24f67c29`) and passed **5/5**:
process restart while waiting → resume, changed-source revision invalidation
(completed work preserved), ambiguous mapping identity (refused without
sheet/version, resolved with it), cancellation with a late response, and
duplicate concurrent resume (one dispatch, zero outbox effects). Evidence:
`atom-employee-execution/docs/acceptance/evidence/durable_assignment_20261031/assignment-recovery-browser/`.
This is a product gate, not part of the README breadth count.

---

## 5.2 Assessment exact-content approval — separate product gate

The canvas assessment safety repairs are verified on
`codex/employee-execution-readiness` (source `6363e3794`; typed outcomes `f8198c60e`):

- the default review policy requires human approval for every assessment,
  whatever the model reports;
- approval is an atomic compare-and-swap bound to a canonical artifact digest
  recomputed from persisted content plus execution/source/policy/canvas
  revisions and a monotonic assessment revision;
- a route-level test confirms unreviewed refusal, exact-execution approval,
  and `content_drift` refusal when one reviewed decision changes with the
  stored hash untouched;
- unsupported approvals fail the qualification gate (`safe_abstention`).

The substantive assessment on local `ollama`/`llama3.1:8b` remains **failed**
(17/18 on V1 and 18/19 on V3/post-restart; a false APPROVE on `Q-012`). Autonomous
substantive decisions stay outside the supported configuration. Evidence:
`atom-employee-execution/docs/acceptance/evidence/durable_assignment_20261031/employee-execution-assessment-approval/`
and `.../employee-execution-assessment-qualification/`. The clarification follow-up (`099c15e02`, evidence `2108a2839`) adds stable requirement ids, ambiguous-answer refusal and stale-revision history. 106 focused tests pass before that follow-up; the clarification bundle records 15 dedicated controls.


---

## 5.3 Bounded autonomy and the two-domain autonomous journey — separate product gate

On `codex/employee-execution-readiness` (code `814962078`):

- **standing authority** is an explicit user grant — named recipients, a hard
  1–20 effect bound, optional expiry — consumed under the assignment CAS
  before dispatch. Exhausted, expired, out-of-scope or wrong-recipient steps
  fall back to approval; only the controlled outbox opts in, and live email
  send remains approval-required;
- **budgets** enforce steps, attempts, wall time and `max_cost_usd`, with step
  cost accumulated;
- **uncertain effects** reconcile through a TEAM_LEAD route with mandatory
  evidence (`applied` never resends, `not_applied` creates a new operation,
  `insufficient` preserves uncertainty);
- the canvas capability panel labels unapproved assessments as drafts, approves
  the exact execution, answers durable clarifications, and exposes decisions
  only when authorized;
- the **integrated two-domain journey** — sales `85` and grants `4250` from
  unfamiliar datasets, one bounded grant per send, backend restart while both
  wait, both complete on return — passed **5/5** with **2 effects and 0
  assignment approvals**.

This is a product gate, not part of the 123-claim breadth denominator.
Evidence: `atom-employee-execution/docs/acceptance/evidence/durable_assignment_20261031/employee-execution-autonomy-boundaries/`
(185 backend + 6 frontend tests) and `.../two-domain-autonomous-journey/`.

---

## 6. Evidence and reproduction

Authoritative result: `evidence/corrected-results.json` (99/123).
Final audit: `evidence/CLAIM_AUDIT_2026-10-31_final.json`.
Earlier audit: `evidence/CLAIM_AUDIT_2026-10-31.json` (historical).
Integrated run: `evidence/final-all-groups.json`.
Merged pre-audit result: `evidence/merged-integrated.json`.
Install/restart: `evidence/install-final.json`.
Manifest: `evidence/MANIFEST.json` / `evidence/MANIFEST.md`.

Commands:

```bash
# all acceptance groups on one marked world
python -m scripts.readme_acceptance.run --groups all

# process-level install / restart / goal checkpoint
python scripts/acceptance/readme_local_install.py

# merge, explicit final audit, frozen inventory
python scripts/acceptance/merge_readme_results.py --results ... --install ... --out ...
python scripts/acceptance/apply_readme_audit.py \
  --results ... --audit .../CLAIM_AUDIT_2026-10-31_final.json --out ...
python scripts/acceptance/readme_claim_inventory.py --merge ...
```

The acceptance harness exits nonzero on any failed claim or group error. The
install script exits nonzero unless `status=verified`.

No deployment, real send, credential change or connected-system write was
performed. Controlled-provider evidence is labelled; it is not model-quality
or live-delivery evidence.
