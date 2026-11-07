# Admitted execution outcome + trusted context join — evidence

Bounded repair of the reproduced admitted-run outcome/context defect.
Branch base: `02bf17f98` (contains accepted Generic consumer `039a`).
Authoritative actual Git baseline: root checkout at main `335fd77fa`,
`/private/tmp/atom-agent-job-baseline`; 36 existing failure IDs
(`root-actual-baseline-findings.json`).

## Defect

The real public `POST /api/agents/{id}/run` admitted a durable `AgentJob`,
then the real `_dispatch_admitted_run` treated **any non-`None` result** as
business success and marked the job `success`. A returned
`uncertain`/`failed`/`blocked`/`cancelled`/`waiting`/empty/contradictory
result therefore produced a successful durable job and a nominal success
WebSocket event. The same wrapper passed only raw request parameters, so the
Generic consumer ran with the default workspace, accepted body-forged
workspace/tenant/actor/execution/operation keys as context, and broadcast
private step/outcome frames onto `workspace:default`.

## Repair

No new engine, table, operation store or schema.

- `_execution_outcome` maps explicit success only for supported success
  statuses. Uncertain/failed/blocked/cancelled/contradictory/empty/invalid
  results preserve the exact outcome, reason and next action and never
  complete the job. Result presence is not success.
- The actual HITL producer was fixed at its existing neighborhood:
  `GenericAgent` constructs the governance service with the run
  workspace/tenant and `AgentGovernanceService.request_approval` persists the
  already-trusted job/execution/actor context in the existing
  `context_snapshot` field (business params untouched). Older callers that
  pass no context keep their previous shape; their legacy rows stay readable
  but cannot certify a new scoped task.
- A bare model/body `"waiting"` string is not a durable wait. A returned
  reference becomes a non-terminal `waiting` job only when it resolves to an
  existing **pending** `HITLAction` row bound to this exact agent and the
  frozen workspace/tenant (and actor when the row names one), with
  task/execution material checked when the row carries it. Invented, foreign,
  other-agent and settled references remain explicit non-success. The real
  review row is read back in the positive control. A durable wait preserves
  its receipt and `await_information`, does not set `finished`/`end_time`,
  and does not occupy the active-run slot; the existing continuation owner
  can resume the same task.
- The admission namespace is built from the durable job, the original
  admission `AuditLog` receipt, the frozen `parameters_digest` and the
  authenticated actor. A moved agent, changed parameters, foreign actor,
  missing receipt, terminal job or peer cancellation refuses dispatch.
- The protected namespace (`workspace_id`, `tenant_id`, `actor_id`/`user_id`,
  `job_id`, `run_id`/`execution_id`, `operation_id`, operation/intent/
  authorization slots, session/proposal/goal and trigger provenance) is
  overwritten server-side; business parameters remain available.
- An unscoped global agent with a genuinely scoped actor resolves the
  actor's workspace rather than silently falling back to `default`.
- `_begin_job` is an atomic conditional claim on id + exact agent + active
  status + exact summary; `_finish_job` additionally binds the dispatched
  execution id, exact agent and expected summary, and uses conditional DML.
  A peer job move, peer cancellation or stale dispatcher is preserved, never
  overwritten by a late success.
- WS step/outcome frames now go to the actual workspace channel plus the
  authenticated `user:{actor}` channel (already auto-subscribed by `/ws`).
  No scoped output is sprayed onto `workspace:default`.
- `execute_agent_task` constructs the real Generic consumer with the frozen
  workspace/tenant and no raw-body authority. Sync failure/uncertain returns
  a truthful 409/503 envelope with top-level `data`; a durable wait returns
  202; success returns the whitelisted user-facing result (no
  `audit_report`/internal scores).
- `GenericAgent._execute_impl` reuses the canonical
  `execution_id`/`run_id` for `_run_uuid`, so the audit bracket and the
  persisted `AgentExecution` row share one identity.

## Public capture (controlled transport)

`public-capture.json` records the actual constructor/call context through the
public route + real admission + real `_dispatch_admitted_run` +
`execute_agent_task`, with only the Generic transport doubled:

| Field | Observed |
|---|---|
| public response | job `c552f5d4…`, execution `067e83b5…`, `job_status=success`, `outcome=success` |
| Generic constructor | `workspace_id=ws1`, `tenant_id=t1` |
| Generic context | `actor_id/user_id=member-1`, `workspace_id=ws1`, `tenant_id=t1`, real job/execution ids, business note retained |
| body-forged keys | `ws2`, `t2`, `admin-2`, forged job/execution/operation/session/goal values were replaced by server values |
| WS channels | `workspace:ws1` + `user:member-1`; no `workspace:default` |
| durable job | `status=success`, `outcome=success`, `execution_id` matches response, no forged values |

`real-consumer-capture.json` records one public route -> real wrapper -> **real
GenericAgent** run. Only `_react_step` (model/MCP transport), the budget
preflight and the unrelated episodic-memory/episode-summary leaves are
doubled. Readback:

- `AgentExecution.id == public execution_id`, workspace `ws1`, tenant `t1`,
  status `success`;
- 2 audit rows carry the **same** `agent_execution_id` (no fresh audit id);
- durable `AgentJob` links the same execution id with `outcome=success`.

## Verification

Commands used a project `venv314`, `TESTING=1`, explicit scratch
`DATABASE_URL`/`LANCEDB_PATH`, and a fresh uniquely owned `--basetemp`
child under `/private/tmp/atom-job-join-gate-20261107-agent2/`.

| Gate | Command / scope | Result |
|---|---|---|
| Supplied five-cell probe | `/private/tmp/test_lead_agent_job_outcome_join.py` (in `final-focused.log`) | **5 passed, exit 0** |
| New candidate contracts | `test_agent_run_outcome_join_contract.py` + `test_agent_run_admission_contract.py` | **42 passed, exit 0** |
| Supplied lead probes | claim race + draft bindings + all three wait files in `LEAD_PROBES/` | **17 passed, exit 0** |
| Combined focused gate | 64 tests, `final-focused.log` | **exit 0** |
| Actual affected gate | 13 files, `final-affected.log` | **exit 1; 36 failure IDs** |
| Failure identity | `final-failure-identity.json` | **36/36 exactly the root actual baseline; zero new IDs** |
| Generic consumer follow-through | `test_generic_agent.py`, `test_agent_action_audit.py`, `test_generic_oracle_mutation_contract.py`, `test_objective_loop_termination.py` | **passed** |
| Syntax | `py_compile` on changed Python sources | **pass** |

The 36 affected-gate failures are exactly root's authoritative baseline IDs.
The two changed fixture files and the new contract file align stub results
with the new optional server-context contract and explicit success statuses;
they add no production behavior. In particular, the changed fixtures do not
make source `result is not None` success again.

The earlier `PYTHONPATH=.baseline_api` capture is preserved under
`superseded-invalid-baseline/` with a note: it did not load the shim and is
**not** used for classification.

## Source hashes

Per-file Git blob / SHA-256 are in `source-hashes.json`. The evidence commit
also records the code commit that produced these bytes.

## Boundaries

- SQLite scratch database in one process/event loop; PostgreSQL, multi-worker
  and soak behavior remain separate.
- The authenticated principal, agent rows and controlled Generic result are
  supplied by the test fixture; public handlers, admission service, durable
  job/receipt, wrapper, real GenericAgent execution/audit producers and WS
  routing are real.
- `real-consumer` doubles only model/MCP transport and unrelated
  episodic-memory/episode-summary leaves (documented in the test fixture).
- Waiting is preserved as a non-terminal job with its durable receipt; the
  existing continuation owner is responsible for the same-task auto-resume.
  This evidence does not claim a browser/UI campaign or team realtime
  authorization beyond the authenticated user/workspace channels.
- No live model/provider/account/credential/send/spend/download/deployment or
  merge action was performed by the agent. Root owns PR/merge and PR716.
