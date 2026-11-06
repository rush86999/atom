# Agent 3 independent review — merged PR682/683/684 workflow approval scope

Reviewer: Agent 3 (independent verification), 2026-11-06, per
`AGENT3_LEAD_REVIEW_AND_NEXT_20261106.md` and the work-order queue correction.
Recommendation to the lead; the lead owns final acceptance, the owner's
merge authority remains separate (#682/#683/#684 are already merged).

## 1. User contract reviewed

A user must be able to find and decide the work their employee is waiting on:
an authenticated workflow run (direct or scheduled) freezes the caller's
tenant/workspace into the durable execution; a governance pause files an
approval visible in exactly that scope's real queue; deciding the exact
material resumes the run once on a fresh engine to one durable local effect;
rejection or changed material leaves zero effect; duplicates do not
redispatch; foreign scopes can neither see nor decide; resume inputs cannot
rewrite the frozen scope.

## 2. Source and artifact identity (reconciled first)

| Identity | Value | Role |
|---|---|---|
| Runtime source | `068abd57a34c81948d01fd12aa941ca2f4fa55b5` | executed/submitted checkpoint |
| PR682 merge | `49d45c7f3cc3529e15e1cb6d48a81c88fda1a419` | owner-merged |
| PR683 evidence merge | `76cf78ad6` | freezes the evidence bundle |
| PR684 scheduled-join merge | `78d2e0ca8` | adds the scheduler join |
| Current main | `3925cf3592e955bebb8282ec7168e3fdce20ec42` | reviewed here |

- All 5 PR682 runtime/test files hash identically across `068abd57a`,
  `49d45c7f3`, `78d2e0ca8` and main, except
  `tests/test_workflow_public_approval_flow.py`, which PR684 extends
  (expected; main carries the PR684 version `bb4674c9…`).
- Evidence bundle `docs/acceptance/evidence/workflow_public_approval_scope_20261106/`:
  **all 6 declared source hashes (git blob + sha256) verified at the
  checkpoint**, and **all 12 declared artifacts hash-match at both the PR683
  merge and current main**. This bundle is complete and checkout-verifiable —
  no missing-artifact finding here.
- `verification.json` result claims (governance probe 4, flow controls 7,
  CI selections 641+1 on both Pythons, hosted green, identical
  baseline/repair failure identity) remain author-reported; hosted CI/E2E
  and CI-selection logs are committed evidence, not independently rerun by
  Agent 3.

## 3. Independent execution (Python 3.11.16, fresh `TESTING=1` scratch `DATABASE_URL`/data)

One decisive combined gate, once:
`tests/test_workflow_approval_scope.py` +
`tests/test_workflow_public_approval_flow.py` +
`tests/test_agent3_pr682_scope_freeze_probes.py` — **14 passed / 0 failed**
in 31.93s (log: `combined-gate-311.log`). Node identity: 4 governance-scope
controls (same-scope visible/decidable, wrong-workspace, wrong-tenant), 8
public-flow controls (direct visible→decidable→fresh-engine resume→one
effect→no duplicate redispatch; scheduled real-scheduler join; resume
scope-rewrite discarded; schedule freezes caller scope and discards client
key; rejection zero effect; changed material no execution; foreign
workspace/tenant refused ×2), plus Agent 3's 2 probes below.

Honest classification of the road to that run: my first probe draft posted
`{"input_data": …}` to the execute route; FastAPI binds a lone dict body
parameter *without* embedding, so the foreign key sat inert inside a nested
data key and my `x` assertion KeyError'd (1 failed / 13 passed, intermediate
log not retained). A controlled dump showed the durable row already carried
the caller's scope at top level while the smuggled key was inert data the
engine never reads for scope — a probe-authoring error, not a product
defect. Corrected probe included in the final decisive gate.

## 4. Agent 3 probes (genuinely missing cases only)

1. **Execute-route client-scope smuggling (negative twin)**: posting
   `_atom_execution_scope` (foreign) at the input top level — the route's
   real body shape — the durable `WorkflowExecution.input_data` carries the
   authenticated caller's scope, and the governance approval waits in the
   caller's own queue. (The merged suite covered the schedule route only.)
2. **Helper contract**: `freeze_execution_scope` discards a client-supplied
   reserved key before setting the authoritative scope, omits empty or
   whitespace-only values (no invented `"default"`), and
   `strip_execution_scope` removes the key from untrusted resume inputs.

## 5. Coverage map against the lead's required items

| Required item | Independently covered by |
|---|---|
| Authenticated execution scope freezing | flow test 1 + Agent 3 probe 1 (durable row readback) |
| Schedule scope freezing | flow test 4 (caller frozen, client key discarded) |
| Persisted scheduler → engine → pause → queue → decision → resume → durable result | PR684 scheduled join (real `WorkflowScheduler._execute_job`, real engine, real approvals router, real `_execute_step` database leaf, dispatch count 0→1) |
| Real durable queue and exact decision | flow tests 1–2, governance probe |
| Fresh-engine resume | flow test 1 (`get_workflow_engine` → new `WorkflowEngine()` reads the durable row) |
| Rejection zero effect | flow test 5 |
| Material change zero effect | flow test 6 (approval consumed, new pending filed, zero dispatch) |
| Duplicate no redispatch | flow test 1 tail (`_run_execution` again → still 1 dispatch) |
| Foreign tenant/workspace refusal | flow test 7 ×2 + governance probe (list empty, decide 404, row stays pending) |
| Resume scope-change protection | flow test 3 + Agent 3 probe 2 |

Code trace confirms the mechanism at source: `execute_workflow` freezes the
caller scope (`workflow_endpoints.py:729`), `schedule_workflow` freezes into
persisted job args (`:972`), the scheduler fire passes args through
unmodified (`workflow_scheduler._execute_job` → `start_workflow(def,
input_data)`), both graph (`workflow_engine.py:476`) and linear (`:831`)
paths resolve the frozen scope first, governance is created with that scope
(`:941`), the HITL row persists the service's authoritative tenant
(`agent_governance_service.py:1055`), and resume strips untrusted scope
(`:784`).

## 6. Shared-caller observation (out of this slice; for lead ranking)

The repair scopes the **workflow** family. Other approval families still
construct governance **without** tenant/workspace — bare
`AgentGovernanceService(db)` at `atom_meta_agent.py:2314,2462,3012,3041,
3106,3389`, and `ServiceFactory.get_governance_service(self.db)` at
`recording_review_service.py:49` and `canvas_recording_service.py:53,62`.
The service now persists whatever scope its constructor carries, so rows
created by those unscoped services still lack a real tenant and would be
invisible to a real tenant's queue — the same defect class #682 fixed for
workflows. Not reproduced here as a failing user transition (that is a
separate finite review if the lead ranks it); recorded as an integration
observation, no repair attempted.

## 7. Exact seam and exclusions (recorded, not certified)

- Controlled leaf: the registered local `database` action (`create` with a
  harmless record) — real `_execute_step`, no transport stub; effect counted
  by `WorkflowExecutionLog` rows. No live model/provider/account/spend/send.
- SQLite scratch, one process/event loop; PostgreSQL, multi-worker and soak
  remain unqualified. My probes are controlled public-boundary cases, not
  simultaneous multi-worker proofs.
- The scheduler entry is the PR676-accepted mechanism; this slice only
  freezes scope into its persisted args. Scheduler restart with an approval
  in flight was not re-run here (PR676's restart-recovery qualification used
  counter callbacks; joining restart+approval is untested and unclaimed).
- #681 review remains root-owned; Agent 4's browser journeys untouched.

## 8. Recommendation to the lead

**Accept the merged #682/#683/#684 public workflow approval-scope repair at
its tested scope**: the contract reproduced end-to-end at the public
boundary on this runtime with zero failing or missing in-scope transitions,
the evidence bundle is complete and hash-verified in Git, and the declared
exclusions are intact. Non-blocking items: the shared-caller observation
(§6) for separate finite ranking, and the scheduler-restart-plus-approval
join as an untested boundary if the lead wants it qualified.
