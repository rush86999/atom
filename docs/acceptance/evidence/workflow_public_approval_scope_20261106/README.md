# Public workflow approval scope — evidence

Bounded repair of the reproduced public workflow approval-scope defect.
Base main: `33b8d6472`. Source checkpoint: `068abd57a` (PR #682).

## Defect

At source `e205b6fb8` the supplied probe failed 2/4:

- a real scoped `AgentGovernanceService` created a pending `HITLAction` with
  `workspace_id` but **no `tenant_id`**;
- the real `WorkflowEngine` governance factory call passed `tenant_id` but
  **dropped the workflow workspace**;
- the correct tenant/workspace reviewer's
  `GET /api/agents/approvals/pending` returned `[]`;
- the exact `POST /api/agents/approvals/{id}` returned
  `404 {"detail":"Approval not found"}`;
- foreign workspace/tenant reviewers were already correctly refused.

## Repair

Existing mechanisms only; no new router, scheduler or operation engine.

- `AgentGovernanceService.request_approval` persists the scoped service's
  authoritative `tenant_id` on the existing `HITLAction`.
- The `WorkflowEngine` passes `workspace_id` **and** `tenant_id` into the
  existing `ServiceFactory.get_governance_service` call.
- `POST /workflows/{id}/execute` freezes the authenticated caller's
  tenant/workspace into the durable execution inputs.
- `POST /workflows/{id}/schedule` freezes the scheduling user's scope into
  the persisted APScheduler job args.
- Linear and graph execution resolve the frozen scope first, then the
  definition's own scope for seeded/scheduled runs, then the legacy
  `"default"` behavior.
- `WorkflowEngine.resume_workflow` strips the reserved scope key from
  untrusted resume inputs, so a resume cannot move a run into another
  tenant/workspace.
- Queue/decision filters and role checks are unchanged.

## Public capture (exact)

`public-flow-capture.json` records one real run through the authenticated
workflow router and the real approvals router:

| Step | Observed |
|---|---|
| `POST /workflows/{id}/execute` | `200`, execution `ed8635d4…`, status `running` |
| durable pause | execution `PAUSED`, step `s1 PAUSED`, dispatch count **0** |
| `GET /api/agents/approvals/pending` | `200`, one row with action `create`, agent, real reason `Maturity check failed. Required: supervised`, and the exact execution/step parameters |
| `POST /api/agents/approvals/{id}` `{"decision":"approved"}` | `200`, `success:true`, `resume:{handled:true,resumed:true,kind:"workflow",status:"RUNNING"}` |
| durable completion | execution `COMPLETED`, step `s1 COMPLETED`, one output under `s1`, dispatch count **1** |
| approval receipt | `status:"approved"`, `tenant_id:"tenant-local-…"`, `workspace_id:"workspace-local-…"`, `reviewed_by:"reviewer-local-…"`, id in `consumed_hitl_action_ids` |

## Verification

| Gate | Result |
|---|---|
| Supplied governance scope probe (same-scope queue/decision + foreign workspace/tenant) | **4 passed** |
| Real public flow controls | **7 passed** |
| Combined new controls, Python 3.11 | **11 passed** |
| Updated CI selection, Python 3.11 | **641 passed, 1 skipped** |
| Updated CI selection, Python 3.14 | **641 passed, 1 skipped** |
| Affected governance/factory/approval/workflow batch, baseline | **57 failed, 777 passed, 1 skipped, 2 errors** |
| Same batch on the repair | **57 failed, 788 passed, 1 skipped, 2 errors** |
| Failure/error identity | **identical 59 IDs** (`baseline-failures.txt` vs `branch-failures.txt`) |
| Hosted backend job 128003564341 | **641 passed, 1 skipped**; memory recall **1.0** |
| Hosted e2e job 128003564095 | API **211 passed, 1 skipped, 1 xfailed**; UI **29 passed**; role UI **40 passed**; zero failures |
| syntax, frontend typecheck, app boot, quickstart, Docker, GitGuardian | pass |

The baseline batch failures are pre-existing maturity/confidence and
singleton-state tests; the repair changes no failure identity and adds only
the 11 new passes. Logs: `public-flow-controls-311.log`,
`ci-selection-311.log`, `ci-selection-314.log`,
`affected-callers-baseline-311.log`, `affected-callers-branch-311.log`,
`hosted-backend.log`, `hosted-e2e.log`.

## Source hashes

| File | Git blob | SHA-256 |
|---|---|---|
| `backend/core/agent_governance_service.py` | `c063f55efb3f7370796954b11250dd7029348b0e` | `9d369a381122c311869dfe888ee0f4a1ddb585f90611f0981f67e4fb4323db45` |
| `backend/core/workflow_engine.py` | `bce106f208c78adfad387b8b7aa5e23b08222aa7` | `510242d909525c38bf0e6a8710898c28cf7c98ad26928f8ea1b43774886f7d11` |
| `backend/core/workflow_endpoints.py` | `0e4953c144fd19e34fab794baf9d7e21bcd0b066` | `f570ead8b9163a9a86ae1109113ecf45e6d06be4849f837159eedbaa44079d17` |
| `backend/tests/test_workflow_approval_scope.py` | `5656db4597843b95dcd4f70e8d7be2e7ac1b0f93` | `29d64005d638fa1b4998f444ff44235f27f9ba6b0c0b9348cc514565c3a4057b` |
| `backend/tests/test_workflow_public_approval_flow.py` | `5b76dbe7a2a84d0f278f77f0b591e76090c77fab` | `eff474388a7be7b51b90f6045e4daeb83eb9cba769bbf1370eadb5bc98a6c7da` |
| `.github/workflows/ci.yml` | `a9faaee2fdd1955daed7066780d8ea66d3e47a00` | `dfdf7bd26a5aba4c3eafcfa54120e3e6f859d57b2ce0f6d84ca2c8ef5007e9d2` |

Artifact hashes are in `verification.json`.

## Boundaries

- Proven on a SQLite scratch database in one process/event loop with the
  real routers, governance service, durable state manager, `_execute_step`
  and the harmless registered `database.create` action. PostgreSQL,
  multi-worker and soak behavior remain separate.
- The authenticated principal and the workflow-definition source are
  supplied by the test fixture; the real public HTTP handlers, approval
  service and durable engine are not doubled.
- The scheduler entry remains the one accepted by PR676; this repair only
  freezes the scheduling user's scope into its persisted job args.
- No live model/provider/account, credential, spend, send, download,
  deployment, merge or approval was performed by the agent.
