# README feature-readiness claim inventory

Generated: 2026-10-31T13:57:08.112169+00:00

README: `README.md` @ `da9cc8b12de3639f59cc5b8ea84338c5f507dc6d` (tag `local-core-2026-10-30-final`), sha256 `392b3ca2fe88cb94c326f02318bc46273da972736b807f793c3ae8246b2bcce0`

Eligible functional claims: **123** · tracked separately: 20

> Partial/failed/unverified/blocked/environment-limited do not count as passing. Category count alone is never a score.

**Verified functional: 100/123 (81.3%)**

## Category coverage

| Category | Total | Verified | Partial | Failed | Unverified | Blocked external | Env limited |
|---|---|---|---|---|---|---|---|
| agent-radio | 4 | 4 | 0 | 0 | 0 | 0 | 0 |
| agent-teams | 6 | 6 | 0 | 0 | 0 | 0 | 0 |
| ask | 5 | 4 | 1 | 0 | 0 | 0 | 0 |
| comparative | 5 | 0 | 0 | 0 | 5 | 0 | 0 |
| compatibility | 4 | 0 | 0 | 0 | 4 | 0 | 0 |
| core-workspace | 7 | 7 | 0 | 0 | 0 | 0 | 0 |
| gateway | 6 | 6 | 0 | 0 | 0 | 0 | 0 |
| goals | 5 | 3 | 0 | 0 | 2 | 0 | 0 |
| governance | 8 | 7 | 1 | 0 | 0 | 0 | 0 |
| graphrag | 5 | 4 | 1 | 0 | 0 | 0 | 0 |
| hybrid-search | 5 | 5 | 0 | 0 | 0 | 0 | 0 |
| installation | 5 | 4 | 0 | 0 | 1 | 0 | 0 |
| integrations | 9 | 6 | 2 | 0 | 0 | 1 | 0 |
| interoperability | 6 | 6 | 0 | 0 | 0 | 0 | 0 |
| memory | 7 | 6 | 0 | 0 | 1 | 0 | 0 |
| mini-apps | 5 | 2 | 0 | 0 | 0 | 0 | 2 |
| office | 8 | 7 | 1 | 0 | 0 | 0 | 0 |
| oracle | 6 | 6 | 0 | 0 | 0 | 0 | 0 |
| orchestration | 8 | 4 | 0 | 0 | 3 | 0 | 0 |
| performance | 3 | 1 | 0 | 0 | 2 | 0 | 0 |
| routing | 7 | 3 | 3 | 0 | 1 | 0 | 0 |
| security | 8 | 8 | 0 | 0 | 0 | 0 | 0 |
| vfs | 4 | 4 | 0 | 0 | 0 | 0 | 0 |
| workflows | 7 | 6 | 1 | 0 | 0 | 0 | 0 |

## Claims


### orchestration

| ID | README | Operation | Entry point | Status |
|---|---|---|---|---|
| ORCH-01 | L144 | Turn a plain-language workflow request into a structured, persisted workflow blueprint | `Chat request classified WORKFLOW / POST /api/v1/workflows/generate-from-agent` | **unverified** |
| ORCH-02 | L144 | Route an open-ended TASK intent to recruited specialist agents | `Chat request classified TASK / AtomMetaAgent.execute` | **unverified** |
| ORCH-03 | L144 | Execute a workflow under each of the five conductor strategies | `POST /api/v1/workflows/workflows/conductor/execute` | **verified** |
| ORCH-04 | L144 | Reject illegal workflow state transitions and accept legal ones | `core.orchestration.workflow_state_machine` | **verified** |
| ORCH-05 | L144 | Roll a workflow back to a prior version/execution after a change | `POST /api/v1/workflows/{workflow_id}/rollback` | **verified** |
| ORCH-06 | L144 | Rank candidate specialists by capability overlap, tier and verified-episode ratio | `core.specialist_matcher` | **verified** |
| ORCH-07 | L144 | Record a governed fleet-routing audit decision for an eligible task | `AtomMetaAgent.execute / fleet_routing_audit table` | **unverified** |
| ORCH-08 | L144 | Enforce delegation nesting depth rather than link count | `core.fleet_orchestration.delegation_contracts.DelegationChain` | **inaccurate** |

### governance

| ID | README | Operation | Entry point | Status |
|---|---|---|---|---|
| GOV-01 | L145 | Gate an action by the agent's maturity tier | `POST /api/agent-governance/enforce-action` | **verified** |
| GOV-02 | L145 | Hold a risky mutation for human approval and execute only after approval | `POST /api/agent-governance/submit-for-approval; /api/agents/approvals/pending; approve/reject` | **verified** |
| GOV-03 | L145 | Record actor, action, target and outcome for governed actions | `AgentExecution/AgentActionAudit rows via public activity endpoints` | **verified** |
| GOV-04 | L145 | Create a training session, receive guidance, complete it, and promote | `POST /api/maturity/training/... + /api/maturity/proposals/...` | **partial** |
| GOV-05 | L145 | Configure an OIDC provider, start login, and consume the callback | `GET/POST /api/auth/sso/oidc/{config,login,callback}` | **verified** |
| GOV-06 | L145 | Provision, list and deactivate a user over SCIM v2 | `POST/GET/PATCH /api/scim/v2/Users` | **verified** |
| GOV-07 | L145 | Enforce role permissions on an admin-only surface | `GET/POST /api/admin/roles; admin routes` | **verified** |
| GOV-08 | L145 | Create an agent, inspect capabilities, and deactivate it | `/api/agent-governance/agents + /api/agents` | **verified** |

### oracle

| ID | README | Operation | Entry point | Status |
|---|---|---|---|---|
| ORACLE-01 | L146 | Verify the oracle registry is enabled and has postcondition verifiers | `core.oracle.verifier registry` | **verified** |
| ORACLE-02 | L146 | Re-derive a claimed mutation from the database rather than the tool response | `core.oracle verifier invoked on a real create/update` | **verified** |
| ORACLE-03 | L146 | Stamp a refuted tool self-report UNVERIFIED in the run outcome | `agent run outcome / capability graduation input` | **verified** |
| ORACLE-04 | L146 | Disable enforcement with the documented kill switch | `environment / runtime settings` | **verified** |
| ORACLE-05 | L146 | Distinguish self-reported from externally verified confidence | `run/verification result payload` | **verified** |
| ORACLE-06 | L146 | Re-delegate a failed review to the originating specialist with feedback | `verification/review.py REVIEW strategy` | **verified** |

### ask

| ID | README | Operation | Entry point | Status |
|---|---|---|---|---|
| ASK-01 | L147 | Compute per-action-type autonomy from externally verified outcomes | `core.trust_calibration + capability stats` | **verified** |
| ASK-02 | L147 | Ask for approval when the evidence posterior is uncertain | `POST /api/v1/trust-calibration/assess` | **verified** |
| ASK-03 | L147 | Revoke earned autonomy after a verified regression | `trust calibration automation revoke path` | **partial** |
| ASK-04 | L147 | Certify autonomy only after passing the held-out calibration thresholds | `core.trust_calibration.certify` | **verified** |
| ASK-05 | L147 | Expose calibration stats and gated relaxation through the admin API | `GET /api/v1/trust-calibration/{stats,automation}` | **verified** |

### agent-teams

| ID | README | Operation | Entry point | Status |
|---|---|---|---|---|
| TEAM-01 | L148 | Create a delegation contract that names exactly one accountable agent | `core.fleet_orchestration.delegation_contracts` | **verified** |
| TEAM-02 | L148 | Grant a privileged operation through a default-deny expiring lease | `core.org_privileges + dispatch gate` | **verified** |
| TEAM-03 | L148 | Detect self-recruitment / same-family conflicts in a fleet decision | `core.org_integrity` | **verified** |
| TEAM-04 | L148 | Attribute realized outcome credit across a delegation chain | `core.contribution_credit` | **verified** |
| TEAM-05 | L148 | Run a nightly alignment sweep that files findings without changing policy | `core.org_alignment + automation` | **verified** |
| TEAM-06 | L148 | Record org events for recruit/radio/reviewer and report incumbency baselines | `core.org_telemetry_service + scripts/org_dynamics_report.py` | **verified** |

### memory

| ID | README | Operation | Entry point | Status |
|---|---|---|---|---|
| MEM-01 | L149 | Extract durable facts from a completed turn into the five categories | `turn_fact_extractor hook on sync_turn` | **verified** |
| MEM-02 | L149 | Recall facts through the fast SQL tier | `GET /api/memory/search + documents.search` | **verified** |
| MEM-03 | L149 | Recall semantically related facts through the vector tier | `memory vector store` | **verified** |
| MEM-04 | L149 | Create, retrieve and graduate from past episodes | `POST /api/episodes/create; /api/episodes/retrieve/*; /api/episodes/graduation/*` | **verified** |
| MEM-05 | L149 | Store an agent memory through the tool surface | `tool `memory_remember` (RPC action / MCP dispatch)` | **verified** |
| MEM-06 | L149 | Delete an agent memory through the tool surface | `tool `memory_forget`` | **verified** |
| MEM-07 | L149 | Turn a tool error into a pending evolution candidate for human approval | `evolution harness / Agent Studio Auto-Dev Fixes` | **unverified** |

### hybrid-search

| ID | README | Operation | Entry point | Status |
|---|---|---|---|---|
| SEARCH-01 | L150 | Return a lexical BM25 match for an exact rare term | `POST /api/documents/search; action documents.search` | **verified** |
| SEARCH-02 | L150 | Return a semantic vector match with no lexical overlap | `documents.search vector leg` | **verified** |
| SEARCH-03 | L150 | Fuse lexical and vector rankings with RRF | `documents.search result fusion` | **verified** |
| SEARCH-04 | L150 | Return source identity and line/citation for each search hit | `documents.search response` | **verified** |
| SEARCH-05 | L150 | Missing results return an explicit empty result, not an error or a fabricated hit | `documents.search` | **verified** |

### vfs

| ID | README | Operation | Entry point | Status |
|---|---|---|---|---|
| VFS-01 | L151 | List the knowledge tree rooted at knowledge/documents | `RPC action documents.ls / documents.tree` | **verified** |
| VFS-02 | L151 | Read a document body as line-numbered citable content | `RPC action documents.cat` | **verified** |
| VFS-03 | L151 | Regex-search all knowledge content and return citeable paths | `RPC action documents.grep` | **verified** |
| VFS-04 | L151 | Fall back to the legacy documents.search when the VFS is disabled | `ATOM_KNOWLEDGE_VFS_ENABLED=false + documents.search` | **verified** |

### agent-radio

| ID | README | Operation | Entry point | Status |
|---|---|---|---|---|
| RADIO-01 | L152 | Create a radio thread between two agents | `RPC action radio.create_thread` | **verified** |
| RADIO-02 | L152 | Deliver a message to a mentioned peer and leave non-mentioned peers unbothered | `RPC action radio.send_message / radio.read_inbox` | **verified** |
| RADIO-03 | L152 | Enforce the radio team budget | `ATOM_RADIO_TEAM_BUDGET_USD + radio accounting` | **verified** |
| RADIO-04 | L152 | Wait for a mention with timeout and read the passive inbox | `RPC action radio.wait_for_mention / radio.read_inbox` | **verified** |

### office

| ID | README | Operation | Entry point | Status |
|---|---|---|---|---|
| OFF-01 | L153 | Create, read and edit a DOCX while preserving styles/tables | `POST /api/v1/office/word; office tool write_word` | **verified** |
| OFF-02 | L153 | Create a workbook with multiple sheets and leading-zero IDs, read/write cells | `POST /api/v1/office/excel; office tool excel write_cell/read_range` | **verified** |
| OFF-03 | L153 | Evaluate formulas, including cross-sheet dependencies | `POST /api/v1/office/excel/formula-result; POST /api/v1/office/excel/recalculate` | **verified** |
| OFF-04 | L153 | Create, read and edit a PPTX slide | `POST /api/v1/office/pptx; office tool pptx read/edit` | **verified** |
| OFF-05 | L153 | Present a real Office file as a canvas and download it | `POST /api/v1/office/present; GET /api/v1/office/download` | **verified** |
| OFF-06 | L153 | Apply a canvas edit back to the file paragraph/cell in place | `POST /api/v1/office/sync-update` | **verified** |
| OFF-07 | L153 | Broadcast a structured snapshot after an agent write | `notify_file_canvases -> canvas:{id} + user:{uid} WS` | **partial** |
| OFF-08 | L153 | Persist and reopen a presented file canvas after restart | `/canvas/{id} + /api/v1/office/present` | **verified** |

### mini-apps

| ID | README | Operation | Entry point | Status |
|---|---|---|---|---|
| MINI-01 | L154 | Scaffold a mini-app through the agent action surface | `RPC action mini_app_scaffold; POST /api/mini-apps/scaffold` | **verified** |
| MINI-02 | L154 | Reject invalid logic and accept valid logic for a mini-app | `RPC action mini_app_write_logic; /api/mini-apps/{id}/logic` | **verified** |
| MINI-03 | L154 | Run the mini-app in the isolated runtime and receive test feedback | `RPC action mini_app_dev_run/mini_app_run_tests` | **environment_limited** |
| MINI-04 | L154 | Install an app, write records, and reopen with state intact | `POST /api/mini-apps/{id}/install; /api/mini-apps/instances/{id}/records` | **environment_limited** |
| MINI-05 | L154 | Exercise microVM isolation and the per-instance user-agent chat | `mini-app runtime + canvas side chat` | **architecture_only** |

### graphrag

| ID | README | Operation | Entry point | Status |
|---|---|---|---|---|
| GRAPH-01 | L155 | Ingest a document and extract entities/relationships | `POST /api/graphrag/api/graphrag/ingest` | **verified** |
| GRAPH-02 | L155 | Expand a query across multiple graph hops | `GET/POST /api/graphrag/api/graphrag/{query,entities/{id}/neighbors}` | **verified** |
| GRAPH-03 | L155 | Build and read communities over the graph | `POST /api/graphrag/api/graphrag/build-communities` | **verified** |
| GRAPH-04 | L155 | Verify a business fact citation on demand | `POST /api/admin/governance/jit/verify-citations + facts endpoints` | **verified** |
| GRAPH-05 | L155 | Reach the graph visual explorer and render nodes/edges | `Frontend graph explorer page` | **partial** |

### integrations

| ID | README | Operation | Entry point | Status |
|---|---|---|---|---|
| INT-01 | L156 | List the integration catalog and count distinct available providers | `GET /api/integrations` | **verified** |
| INT-02 | L156 | Report disconnected until a real credential exists | `GET /api/integrations/connection-status` | **verified** |
| INT-03 | L156 | Complete provider consent through the OAuth callback | `GET /api/auth/oauth/{provider}/initiate + callback` | **verified** |
| INT-04 | L156 | Read data from a connected provider through the universal adapter | `GET /api/v1/integrations/.../... or UniversalIntegrationService` | **partial** |
| INT-05 | L156 | Perform an outbound provider action behind HITL approval | `UniversalIntegrationService / provider action route` | **partial** |
| INT-06 | L156 | Disconnect a provider and revoke its tokens | `POST /api/auth/oauth/{provider}/revoke or disconnect route` | **verified** |
| INT-07 | L156 | Authenticate provider webhooks and reject forged events | `POST /api/webhooks/... endpoints` | **verified** |
| INT-08 | L156 | Show that each named representative provider has a registered adapter/tool surface | `universal adapter registry + provider routes` | **verified** |
| INT-09 | L156 | Qualify the 46+ claim against real external accounts | `live provider consent/data calls` | **blocked_external** |

### gateway

| ID | README | Operation | Entry point | Status |
|---|---|---|---|---|
| GW-01 | L157 | Serve /v1/chat/completions over a BYOK upstream | `POST /v1/chat/completions` | **verified** |
| GW-02 | L157 | Serve /v1/messages over a BYOK upstream | `POST /v1/messages` | **verified** |
| GW-03 | L157 | List models through the gateway for SDK discovery | `GET /v1/models` | **verified** |
| GW-04 | L157 | Create a gateway key, authenticate with it, and reject invalid keys | `POST/GET/DELETE /api/gateway/keys` | **verified** |
| GW-05 | L157 | Route the gateway request to the configured BYOK provider with header overrides | `gateway service + x-atom-model/x-atom-tier headers` | **verified** |
| GW-06 | L157 | Propagate upstream failures in the caller's wire format | `gateway error path` | **verified** |

### routing

| ID | README | Operation | Entry point | Status |
|---|---|---|---|---|
| ROUTE-01 | L158 | Classify a request into one of the five cognitive tiers | `core.llm.cognitive_tier_system` | **verified** |
| ROUTE-02 | L158 | Expose 16+ configured LLM providers | `GET /api/ai/providers + provider registry` | **verified** |
| ROUTE-03 | L158 | Fall back to the next provider on upstream failure | `BPC router + byok handler` | **partial** |
| ROUTE-04 | L158 | Re-rank candidates from observed outcomes when enabled | `ATOM_LEARNING_ROUTER + /api/chat/feedback` | **partial** |
| ROUTE-05 | L158 | Compress a long context and preserve required facts | `RTK compression layer` | **verified** |
| ROUTE-06 | L42 | Route to a local OpenAI-compatible server | `ATOM_LOCAL_ONLY=true + OLLAMA_BASE_URL / local base URL` | **partial** |
| ROUTE-07 | L46 | Use the opencode-go provider with custom rate limits | `provider `opencode-go`` | **unverified** |

### interoperability

| ID | README | Operation | Entry point | Status |
|---|---|---|---|---|
| IO-01 | L159 | Register an external MCP server and discover its tools | `POST /api/mcp/servers + /api/mcp/servers/{id}/tools` | **verified** |
| IO-02 | L159 | Execute a discovered MCP tool through the governed dispatcher | `POST /api/mcp/execute` | **verified** |
| IO-03 | L159 | Serve the A2A Agent Card for discovery | `GET /api/a2a/agent-card and /.well-known/agent-card.json` | **verified** |
| IO-04 | L159 | Delegate a message to Atom over JSON-RPC A2A | `POST /api/a2a method message/send` | **verified** |
| IO-05 | L159 | Accept an ACP client message and return a reply | `api/acp_routes.py` | **verified** |
| IO-06 | L159 | Record a trace for a request and export when configured | `core observability tracing` | **verified** |

### goals

| ID | README | Operation | Entry point | Status |
|---|---|---|---|---|
| GOAL-01 | L160 | Stop the ReAct loop early when the predicate is satisfied | `core.agent_objective.Objective + GenericAgent loop` | **verified** |
| GOAL-02 | L160 | Score candidate trajectories against a utility target | `agent objective runtime` | **unverified** |
| GOAL-03 | L160 | Register a custom action and gate it by maturity | `Objective.register_action` | **verified** |
| GOAL-04 | L160 | Detect repeated no-progress steps and stop/redirect | `agent loop stuck detector` | **unverified** |
| GOAL-05 | L160 | Start a goal run and observe durable status through resume/restart | `POST /api/goals + /api/goal-runs` | **verified** |

### workflows

| ID | README | Operation | Entry point | Status |
|---|---|---|---|---|
| WF-01 | L85 | Create a workflow through the API/UI from a structured definition | `POST /api/v1/workflows/workflows` | **verified** |
| WF-02 | L85 | Execute a workflow end-to-end and record an execution | `POST /api/v1/workflows/workflows/{id}/execute` | **verified** |
| WF-03 | L90 | Re-read a completed execution after a backend restart | `GET /api/v1/workflows/workflows/{id}/executions` | **verified** |
| WF-04 | L92 | Schedule a workflow, list the job, and remove it | `POST/DELETE /api/v1/workflows/workflows/{id}/schedule` | **verified** |
| WF-05 | L89 | Pause a workflow on policy denial and resume after approval | `workflow execution + /api/agents/approvals` | **partial** |
| WF-06 | L92 | Version a workflow and roll back | `POST /api/v1/workflows/{id}/versions + rollback` | **verified** |
| WF-07 | L79 | Import and execute a starter template | `POST /api/workflow-templates/{id}/import + execute` | **verified** |

### core-workspace

| ID | README | Operation | Entry point | Status |
|---|---|---|---|---|
| CORE-01 | L26 | Ask a question and receive a non-streaming reply at the served boundary | `/chat + /api/chat` | **verified** |
| CORE-02 | L27 | Upload CSV/XLSX/PDF/DOCX/PPTX/EML and inspect extracted content | `POST /api/documents/upload + GET /api/documents/{id}` | **verified** |
| CORE-03 | L27 | Review and edit a canvas deliverable and download it | `/canvas + /api/canvas/*` | **verified** |
| CORE-04 | L28 | Create an agent, teach a rule, and see it applied later | `/agents + /teach + /api/maturity/*` | **verified** |
| CORE-05 | L29 | Read goal-run/execution history including a failure | `/goal-runs + /execution-history + /api/goal-runs` | **verified** |
| CORE-06 | L30 | Configure a model provider through Settings and see it used | `/settings + /api/ai/providers + /api/v1/admin/settings` | **verified** |
| CORE-07 | L32 | Switch profiles and observe navigation/route gating change | `GET /api/product/profile + frontend gate` | **verified** |

### installation

| ID | README | Operation | Entry point | Status |
|---|---|---|---|---|
| INST-01 | L64 | Bootstrap a clean checkout into a runnable environment | `make setup / scripts/quickstart.sh` | **unverified** |
| INST-02 | L65 | Start the backend with the documented command | `make backend` | **verified** |
| INST-03 | L67 | Start the frontend and load the login page | `make frontend` | **verified** |
| INST-04 | L75 | Find the generated admin password and sign in | `backend/logs/bootstrap_admin_password.txt + /login` | **verified** |
| INST-05 | L42 | Restart with the same data root and retain users/data/artifacts | `documented durable data root` | **verified** |

### security

| ID | README | Operation | Entry point | Status |
|---|---|---|---|---|
| SEC-01 | L168 | Block a tool call outside the sandbox policy at dispatch | `mcp_service.call_tool + sandbox_gate` | **verified** |
| SEC-02 | L169 | Store a token and verify the DB value is ciphertext | `IntegrationToken persistence` | **verified** |
| SEC-03 | L170 | Deny a tool outside an agent's declared capability set | `capability resolver at dispatch` | **verified** |
| SEC-04 | L171 | Apply rate/masking/HITL policy to an outbound integration call | `middleware/governance_middleware.py` | **verified** |
| SEC-05 | L172 | Block external egress after restricted data is observed | `data taint tracker + outbound gate` | **verified** |
| SEC-06 | L173 | Connect to an external MCP server (SSRF/scope safe) | `/api/mcp/servers` | **verified** |
| SEC-07 | L145 | Reject unauthenticated/unauthorised access to admin and user APIs | `auth dependencies + role checks` | **verified** |
| SEC-08 | L169 | Fail closed when production encryption key is absent | `token encryption init` | **verified** |

### performance

| ID | README | Operation | Entry point | Status |
|---|---|---|---|---|
| PERF-01 | L40 | Measure governance check latency P99 | `repo benchmark` | **unverified** |
| PERF-02 | L54 | Measure cached governance throughput | `repo benchmark` | **unverified** |
| PERF-03 | L15 | Count collected test functions in the named suite | `pytest --collect-only` | **verified** |

### compatibility

| ID | README | Operation | Entry point | Status |
|---|---|---|---|---|
| COMPAT-01 | L17 | Install and run on a supported Python version | `quickstart guard` | **unverified** |
| COMPAT-02 | L258 | Run the documented stack versions together | `requirements + package.json` | **unverified** |
| COMPAT-03 | L51 | Run the persistence layer on SQLite and PostgreSQL-compatible SQL | `database.py dialect handling` | **unverified** |
| COMPAT-04 | L216 | Build or typecheck the companion surfaces | `mobile/ + menubar/` | **unverified** |

### comparative

| ID | README | Operation | Entry point | Status |
|---|---|---|---|---|
| MKT-01 | L111 | Comparative claim vs consumer assistants/developer frameworks | `marketing comparison` | **unverified** |
| MKT-02 | L114 | Exclusivity/comparative claim | `marketing comparison` | **unverified** |
| MKT-03 | L232 | Per-competitor capability matrix | `marketing comparison` | **unverified** |
| MKT-04 | L8 | External industry statistic | `marketing statistic` | **unverified** |
| MKT-05 | L46 | Pricing comparison | `provider pricing` | **unverified** |

## Evidence details

### ORCH-03 — verified

- Claim: Conductor (5 execution strategies)
- Acceptance: Execute the same deterministic workflow with all five strategies
- Expected: Every supported strategy returns an execution result; unsupported values are rejected
- Evidence: `/private/var/folders/sq/kf_272b520nc5wnsp27hq1h00000gn/T/opencode/readme-feature-world/evidence/orchestration/conductor.json`

### ORCH-04 — verified

- Claim: validated state machine
- Acceptance: Apply a legal transition sequence and an illegal transition to the same run
- Expected: Legal transitions move the run forward; illegal transitions raise/deny without mutation
- Evidence: `/private/var/folders/sq/kf_272b520nc5wnsp27hq1h00000gn/T/opencode/readme-feature-world/evidence/orchestration/state_machine.json`

### ORCH-05 — verified

- Claim: rollback
- Acceptance: Create version 2, roll back to version 1, re-read the workflow
- Expected: Active definition equals version 1 and a rollback record exists
- Evidence: `workflows/versioning.json`

### ORCH-06 — verified

- Claim: governed fleet routing with ranked specialist matching
- Acceptance: Score a roster against a task and inspect the ranked result
- Expected: Best capability+tier+verified candidate ranks first; ties are deterministic
- Evidence: `/private/var/folders/sq/kf_272b520nc5wnsp27hq1h00000gn/T/opencode/readme-feature-world/evidence/orchestration/matcher.json`

### ORCH-08 — inaccurate

- Claim: delegation contracts
- Acceptance: Build a chain at max depth and attempt one more nested delegation
- Expected: The extra nesting is refused; a wide-but-shallow chain is allowed
- Evidence: `/private/var/folders/sq/kf_272b520nc5wnsp27hq1h00000gn/T/opencode/readme-feature-world/evidence/orchestration/depth.json`

### GOV-01 — verified

- Claim: 4-tier maturity (Student->Autonomous)
- Acceptance: Submit a complexity-3 action as STUDENT/INTERN/SUPERVISED/AUTONOMOUS
- Expected: STUDENT blocked, INTERN proposal, SUPERVISED allowed under supervision, AUTONOMOUS allowed
- Evidence: `/private/var/folders/sq/kf_272b520nc5wnsp27hq1h00000gn/T/opencode/readme-feature-world/evidence/governance/tier_gate.json`

### GOV-02 — verified

- Claim: policy-gated HITL approval
- Acceptance: Submit a mutation, approve it, submit another and reject it
- Expected: Approved action executes exactly once; rejected action has no side effect
- Evidence: `/private/var/folders/sq/kf_272b520nc5wnsp27hq1h00000gn/T/opencode/readme-feature-world/evidence/governance/hitl.json`

### GOV-03 — verified

- Claim: comprehensive audit trail
- Acceptance: Perform a governed action and read the run/audit history
- Expected: A durable audit row identifies the agent, action and result
- Evidence: `/private/var/folders/sq/kf_272b520nc5wnsp27hq1h00000gn/T/opencode/readme-feature-world/evidence/governance/audit.json`

### GOV-04 — partial

- Claim: AI-powered training
- Acceptance: Start training as STUDENT, complete the session, inspect the promotion
- Expected: Training session and proposal are persisted; promotion only after approval
- Evidence: `/private/var/folders/sq/kf_272b520nc5wnsp27hq1h00000gn/T/opencode/readme-feature-world/evidence/governance/training.json`

### GOV-05 — verified

- Claim: OIDC SSO
- Acceptance: Point the config at a bounded local OIDC test server and complete a login
- Expected: Config round-trips; login redirects to the IdP; callback establishes a session
- Evidence: `/private/var/folders/sq/kf_272b520nc5wnsp27hq1h00000gn/T/opencode/readme-feature-world/evidence/governance/sso_config.json`

### GOV-06 — verified

- Claim: SCIM v2 provisioning
- Acceptance: Create a user, list it, deactivate it, and attempt unauthorised access
- Expected: User is created/deactivated; missing/incorrect token is rejected
- Evidence: `/private/var/folders/sq/kf_272b520nc5wnsp27hq1h00000gn/T/opencode/readme-feature-world/evidence/governance/scim.json`

### GOV-07 — verified

- Claim: 8-role RBAC
- Acceptance: Call an admin route as member/team lead/admin and list the role catalog
- Expected: Catalog exposes the documented roles; non-admin is denied; admin succeeds
- Evidence: `/private/var/folders/sq/kf_272b520nc5wnsp27hq1h00000gn/T/opencode/readme-feature-world/evidence/governance/rbac.json`

### GOV-08 — verified

- Claim: agent lifecycle
- Acceptance: Create -> read -> update capabilities -> deactivate
- Expected: Lifecycle changes persist and are visible on re-read
- Evidence: `/private/var/folders/sq/kf_272b520nc5wnsp27hq1h00000gn/T/opencode/readme-feature-world/evidence/governance/lifecycle.json`

### ORACLE-01 — verified

- Claim: Postcondition oracle ... on by default
- Acceptance: Read the resolved flag and enumerate registered verifiers
- Expected: Oracle is enabled by default and covers the documented mutation classes
- Evidence: `/private/var/folders/sq/kf_272b520nc5wnsp27hq1h00000gn/T/opencode/readme-feature-world/evidence/oracle/readback.json`

### ORACLE-02 — verified

- Claim: re-derives success against the system of record
- Acceptance: Perform a real mutation, invoke the oracle, then remove the row and invoke again
- Expected: Present row -> EXTERNAL_VERIFIED; missing row -> refuted
- Evidence: `/private/var/folders/sq/kf_272b520nc5wnsp27hq1h00000gn/T/opencode/readme-feature-world/evidence/oracle/readback.json`

### ORACLE-03 — verified

- Claim: a refuted self-report is stamped UNVERIFIED
- Acceptance: Run a tool that reports success without a matching system-of-record row
- Expected: Stored outcome is UNVERIFIED and does not count toward graduation
- Evidence: `/private/var/folders/sq/kf_272b520nc5wnsp27hq1h00000gn/T/opencode/readme-feature-world/evidence/oracle/readback.json`

### ORACLE-04 — verified

- Claim: ATOM_ORACLE_ENFORCE kill switch
- Acceptance: Toggle the flag and re-run the refuted-self-report scenario
- Expected: Enforcement stops; shadow observation remains available
- Evidence: `/private/var/folders/sq/kf_272b520nc5wnsp27hq1h00000gn/T/opencode/readme-feature-world/evidence/oracle/kill_switch.json`

### ORACLE-05 — verified

- Claim: two-tier confidence provenance
- Acceptance: Produce one self-reported and one externally verified outcome; compare stored provenance
- Expected: The two provenance tiers are persisted distinctly and externally verified is the credible one
- Evidence: `/private/var/folders/sq/kf_272b520nc5wnsp27hq1h00000gn/T/opencode/readme-feature-world/evidence/oracle/readback.json`

### ORACLE-06 — verified

- Claim: opt-in reviewer re-delegation loop
- Acceptance: Drive a failed REVIEW result and inspect the re-delegation request
- Expected: Same specialist is re-invoked with feedback (no candidate swap)
- Evidence: `/private/var/folders/sq/kf_272b520nc5wnsp27hq1h00000gn/T/opencode/readme-feature-world/evidence/oracle/reviewer.json`

### ASK-01 — verified

- Claim: Every action type earns interruption-free status from its verified track record
- Acceptance: Record verified successes for one action and ask for its autonomy decision
- Expected: Earned action is allowed without asking; unproven action still asks
- Evidence: `/private/var/folders/sq/kf_272b520nc5wnsp27hq1h00000gn/T/opencode/readme-feature-world/evidence/ask/learned_autonomy.json`

### ASK-02 — verified

- Claim: keeps asking when evidence is thin (ask fails safe)
- Acceptance: Assess a cold-start action with no observations
- Expected: Decision is allow/ask/block = ask (never a silent allow)
- Evidence: `/private/var/folders/sq/kf_272b520nc5wnsp27hq1h00000gn/T/opencode/readme-feature-world/evidence/ask/cold_start.json`

### ASK-03 — partial

- Claim: loses the privilege automatically when results regress
- Acceptance: Apply an allow verdict, then feed a regression and run automation
- Expected: Prior allow is revoked automatically
- Evidence: `/private/var/folders/sq/kf_272b520nc5wnsp27hq1h00000gn/T/opencode/readme-feature-world/evidence/ask/automation.json`

### ASK-04 — verified

- Claim: held-out certification gate (Brier <= 0.25, denial-coverage >= 0.7)
- Acceptance: Run certify on a weak and a strong labelled set
- Expected: Weak set fails; strong set passes only when both thresholds are met
- Evidence: `/private/var/folders/sq/kf_272b520nc5wnsp27hq1h00000gn/T/opencode/readme-feature-world/evidence/ask/certify.json`

### ASK-05 — verified

- Claim: autonomy only relaxes after passing ... gate
- Acceptance: Read stats before/after observations and attempt relax without certification
- Expected: Stats reflect labels; relaxation is refused until certification passes
- Evidence: `ask/learned_autonomy.json`

### TEAM-01 — verified

- Claim: delegation contracts with a single accountable agent
- Acceptance: Build a contract, then try zero/two accountable agents
- Expected: Exactly-one is enforced; invalid contracts are rejected
- Evidence: `/private/var/folders/sq/kf_272b520nc5wnsp27hq1h00000gn/T/opencode/readme-feature-world/evidence/teams/contracts.json`

### TEAM-02 — verified

- Claim: expiring privilege leases instead of titles
- Acceptance: Attempt approve without a lease, with an expired lease, and with a live lease
- Expected: Only the live lease is allowed; default is deny
- Evidence: `/private/var/folders/sq/kf_272b520nc5wnsp27hq1h00000gn/T/opencode/readme-feature-world/evidence/teams/privileges.json`

### TEAM-03 — verified

- Claim: conflict-of-interest detection
- Acceptance: Evaluate an allocator choice where the coordinator recruits itself
- Expected: Conflict is flagged and the choice is refused or marked for review
- Evidence: `/private/var/folders/sq/kf_272b520nc5wnsp27hq1h00000gn/T/opencode/readme-feature-world/evidence/teams/coi.json`

### TEAM-04 — verified

- Claim: contribution credit feeding graduation
- Acceptance: Score a chain with a late failure and compare with an all-success chain
- Expected: Weights sum to the realized outcome; late failure dampens but does not zero
- Evidence: `/private/var/folders/sq/kf_272b520nc5wnsp27hq1h00000gn/T/opencode/readme-feature-world/evidence/teams/contribution.json`

### TEAM-05 — verified

- Claim: opt-in nightly alignment sweeps
- Acceptance: Run the automation pass and inspect the queued action
- Expected: Findings are recorded; no policy changes without the configured consent mode
- Evidence: `/private/var/folders/sq/kf_272b520nc5wnsp27hq1h00000gn/T/opencode/readme-feature-world/evidence/teams/alignment.json`

### TEAM-06 — verified

- Claim: telemetry for ignored instructions / redone work
- Acceptance: Emit representative events and generate the dynamics report
- Expected: Report includes incumbency/favouritism/COI sections from real rows
- Evidence: `/private/var/folders/sq/kf_272b520nc5wnsp27hq1h00000gn/T/opencode/readme-feature-world/evidence/teams/telemetry.json`

### MEM-01 — verified

- Claim: Per-turn fact extraction
- Acceptance: Run a turn containing durable facts and enqueue extraction
- Expected: Facts of the right category are persisted; transient chatter is not
- Evidence: `/private/var/folders/sq/kf_272b520nc5wnsp27hq1h00000gn/T/opencode/readme-data-world/evidence/memory/per_turn.json`

### MEM-02 — verified

- Claim: 2-tier recall (SQL + LanceDB)
- Acceptance: Store a fact and recall it by keyword with vector tier disabled
- Expected: SQL tier returns the fact with source attribution
- Evidence: `/private/var/folders/sq/kf_272b520nc5wnsp27hq1h00000gn/T/opencode/readme-feature-world/evidence/memory/sql_recall.json`

### MEM-03 — verified

- Claim: 2-tier recall ... LanceDB
- Acceptance: Store paraphrased facts and query with a semantically related phrase
- Expected: Vector tier returns the related fact even without lexical overlap
- Evidence: `/private/var/folders/sq/kf_272b520nc5wnsp27hq1h00000gn/T/opencode/readme-feature-world/evidence/memory/semantic.json`

### MEM-04 — verified

- Claim: episodic memory
- Acceptance: Create episodes, retrieve by semantic/temporal mode, inspect graduation readiness
- Expected: Episodes persist and retrieval modes return the matching episode
- Evidence: `/private/var/folders/sq/kf_272b520nc5wnsp27hq1h00000gn/T/opencode/readme-feature-world/evidence/core/episodes.json`

### MEM-05 — verified

- Claim: memory_remember
- Acceptance: Call memory_remember with a fact and read it back through search
- Expected: Fact is stored with provenance and returned by recall
- Evidence: `/private/var/folders/sq/kf_272b520nc5wnsp27hq1h00000gn/T/opencode/readme-feature-world/evidence/memory/remember.json`

### MEM-06 — verified

- Claim: memory_forget
- Acceptance: Forget a stored fact as INTERN and as SUPERVISED
- Expected: INTERN is denied; SUPERVISED deletes and recall no longer returns it
- Evidence: `/private/var/folders/sq/kf_272b520nc5wnsp27hq1h00000gn/T/opencode/readme-feature-world/evidence/memory/forget.json`

### SEARCH-01 — verified

- Claim: documents.search fuses BM25 (FTS5/tsvector)
- Acceptance: Ingest a document with a rare token and search for it
- Expected: The document ranks first with a lexical score
- Evidence: `/private/var/folders/sq/kf_272b520nc5wnsp27hq1h00000gn/T/opencode/readme-feature-world/evidence/search/lexical.json`

### SEARCH-02 — verified

- Claim: + vector (LanceDB)
- Acceptance: Search a paraphrase of ingested content
- Expected: The semantically related document is returned by the vector leg
- Evidence: `/private/var/folders/sq/kf_272b520nc5wnsp27hq1h00000gn/T/opencode/readme-feature-world/evidence/search/vector.json`

### SEARCH-03 — verified

- Claim: via Reciprocal Rank Fusion (RRF)
- Acceptance: Construct two ranked lists and fuse; compare with single-leg order
- Expected: RRF formula (k=60) determines the fused order and combined score
- Evidence: `/private/var/folders/sq/kf_272b520nc5wnsp27hq1h00000gn/T/opencode/readme-feature-world/evidence/search/rrf.json`

### SEARCH-04 — verified

- Claim: semantic + precise retrieval with citations
- Acceptance: Search an ingested document and inspect the hit fields
- Expected: Hit includes document id, path/source and a citable locator
- Evidence: `/private/var/folders/sq/kf_272b520nc5wnsp27hq1h00000gn/T/opencode/readme-feature-world/evidence/search/hybrid.json`

### SEARCH-05 — verified

- Claim: search behaviour
- Acceptance: Search for a token that does not exist
- Expected: success=true with zero hits and no invented citation
- Evidence: `/private/var/folders/sq/kf_272b520nc5wnsp27hq1h00000gn/T/opencode/readme-feature-world/evidence/search/missing.json`

### VFS-01 — verified

- Claim: ls / tree
- Acceptance: Ingest a document and list the tree
- Expected: Tree contains one directory per ingested document
- Evidence: `/private/var/folders/sq/kf_272b520nc5wnsp27hq1h00000gn/T/opencode/readme-feature-world/evidence/vfs/ls.json`
- Evidence: `/private/var/folders/sq/kf_272b520nc5wnsp27hq1h00000gn/T/opencode/readme-feature-world/evidence/vfs/tree.json`

### VFS-02 — verified

- Claim: cat with line-numbered citations
- Acceptance: Cat a known document and verify the first line prefix
- Expected: Body lines are prefixed L<n>: and match the ingested content
- Evidence: `/private/var/folders/sq/kf_272b520nc5wnsp27hq1h00000gn/T/opencode/readme-feature-world/evidence/vfs/cat.json`

### VFS-03 — verified

- Claim: grep
- Acceptance: Grep for a phrase present in one document
- Expected: Only matching documents are returned with path + line locator
- Evidence: `/private/var/folders/sq/kf_272b520nc5wnsp27hq1h00000gn/T/opencode/readme-feature-world/evidence/vfs/grep.json`

### VFS-04 — verified

- Claim: instead of bespoke per-store queries
- Acceptance: Disable VFS and repeat a search
- Expected: Search still works through the legacy path with the same logical hit
- Evidence: `/private/var/folders/sq/kf_272b520nc5wnsp27hq1h00000gn/T/opencode/readme-feature-world/evidence/vfs/flag.json`

### RADIO-01 — verified

- Claim: Lateral peer-to-peer messaging between agents
- Acceptance: Create a thread and read it back
- Expected: Thread row persists with participating agents
- Evidence: `/private/var/folders/sq/kf_272b520nc5wnsp27hq1h00000gn/T/opencode/readme-radio-world/evidence/radio/create.json`

### RADIO-02 — verified

- Claim: mention-first
- Acceptance: Send one mention and drain both peers' inboxes
- Expected: Mentioned peer receives it; other peer does not
- Evidence: `/private/var/folders/sq/kf_272b520nc5wnsp27hq1h00000gn/T/opencode/readme-radio-world/evidence/radio/send.json`

### RADIO-03 — verified

- Claim: budget-governed
- Acceptance: Send messages until the budget is exhausted, then send again
- Expected: Second send past budget is refused and recorded
- Evidence: `/private/var/folders/sq/kf_272b520nc5wnsp27hq1h00000gn/T/opencode/readme-radio-world/evidence/radio/budget.json`

### RADIO-04 — verified

- Claim: agents coordinate without hardcoded teams
- Acceptance: Wait on an empty inbox, then send a mention and wait again
- Expected: First wait times out cleanly; second returns the mention
- Evidence: `/private/var/folders/sq/kf_272b520nc5wnsp27hq1h00000gn/T/opencode/readme-radio-world/evidence/radio/wait.json`

### OFF-01 — verified

- Claim: Agent-driven Excel/Word/PPTX editing
- Acceptance: Create a DOCX with headings/table, edit a paragraph, reopen it
- Expected: Edit persists; styles and table survive; extracted text matches
- Evidence: `/private/var/folders/sq/kf_272b520nc5wnsp27hq1h00000gn/T/opencode/readme-feature-world/evidence/office/docx.json`

### OFF-02 — verified

- Claim: Excel editing
- Acceptance: Create XLSX with '00123' and a cross-sheet formula; restart the reader
- Expected: Leading zeros and sheet names survive; cell values round-trip
- Evidence: `/private/var/folders/sq/kf_272b520nc5wnsp27hq1h00000gn/T/opencode/readme-feature-world/evidence/office/xlsx.json`

### OFF-03 — verified

- Claim: formula-evaluating workbook runtime
- Acceptance: Evaluate =SUM and a cross-sheet reference; inspect cached vs computed values
- Expected: Computed values match the formula engine; unsupported formulas are reported, not guessed
- Evidence: `/private/var/folders/sq/kf_272b520nc5wnsp27hq1h00000gn/T/opencode/readme-feature-world/evidence/office/formula.json`

### OFF-04 — verified

- Claim: PPTX editing
- Acceptance: Create a deck, add/update a slide, reopen and extract text
- Expected: Slide text persists and shape/notes structure survives
- Evidence: `/private/var/folders/sq/kf_272b520nc5wnsp27hq1h00000gn/T/opencode/readme-feature-world/evidence/office/pptx.json`

### OFF-05 — verified

- Claim: Agent-driven ... editing on Canvas
- Acceptance: Present an XLSX, read the canvas, download the artifact
- Expected: Canvas content references the file; downloaded bytes are a valid XLSX
- Evidence: `/private/var/folders/sq/kf_272b520nc5wnsp27hq1h00000gn/T/opencode/readme-feature-world/evidence/office/present.json`

### OFF-06 — verified

- Claim: agent<->document sync
- Acceptance: Edit one paragraph/cell through sync-update and reopen the file
- Expected: Only the targeted paragraph/cell changes; other structure is preserved
- Evidence: `/private/var/folders/sq/kf_272b520nc5wnsp27hq1h00000gn/T/opencode/readme-feature-world/evidence/office/sync.json`

### OFF-07 — partial

- Claim: live preview broadcast
- Acceptance: Open a canvas WS, perform an agent write, capture the message
- Expected: Structured cells/paragraphs/slides snapshot arrives on both channels
- Evidence: `/private/var/folders/sq/kf_272b520nc5wnsp27hq1h00000gn/T/opencode/readme-feature-world/evidence/office/snapshot.json`

### OFF-08 — verified

- Claim: live Canvas co-editing
- Acceptance: Present, reload the canvas, restart the backend, reload again
- Expected: Same canvas row/content is reused; the file remains downloadable
- Evidence: `/private/var/folders/sq/kf_272b520nc5wnsp27hq1h00000gn/T/opencode/readme-feature-world/evidence/office/reopen.json`

### MINI-01 — verified

- Claim: Agent-authored stateful canvas apps
- Acceptance: Scaffold an app and read its manifest
- Expected: Manifest + logic + tests are persisted with declared scopes
- Evidence: `/private/var/folders/sq/kf_272b520nc5wnsp27hq1h00000gn/T/opencode/readme-feature-world/evidence/miniapp/scaffold.json`

### MINI-02 — verified

- Claim: syntax-gated logic
- Acceptance: Write syntax-invalid Python, then valid Python
- Expected: Invalid write is refused without changing logic; valid write persists
- Evidence: `/private/var/folders/sq/kf_272b520nc5wnsp27hq1h00000gn/T/opencode/readme-feature-world/evidence/miniapp/logic.json`

### MINI-03 — environment_limited

- Claim: dev_run / run_tests
- Acceptance: Dev-run a scaffolded app on this host
- Expected: Runtime executes OR fails closed with an explicit unavailable message
- Evidence: `/private/var/folders/sq/kf_272b520nc5wnsp27hq1h00000gn/T/opencode/readme-feature-world/evidence/miniapp/dev_run.json`

### MINI-04 — environment_limited

- Claim: stateful ... per-instance state
- Acceptance: Install, append records, query series, restart, query again
- Expected: Records persist with monotonic seq and per-instance isolation
- Evidence: `/private/var/folders/sq/kf_272b520nc5wnsp27hq1h00000gn/T/opencode/readme-feature-world/evidence/miniapp/install.json`

### MINI-05 — architecture_only

- Claim: Firecracker microVM isolation, per-instance chat
- Acceptance: Attempt an escape/side-effect from app logic; send a side-chat message
- Expected: Isolation blocks host access; side chat is scoped to the instance

### GRAPH-01 — verified

- Claim: GraphRAG
- Acceptance: Ingest two related documents
- Expected: Entities and edges persist with source attribution
- Evidence: `/private/var/folders/sq/kf_272b520nc5wnsp27hq1h00000gn/T/opencode/readme-feature-world/evidence/graphrag/ingest.json`

### GRAPH-02 — verified

- Claim: Multi-hop expansion
- Acceptance: Query an entity two hops away and inspect the expansion
- Expected: Intermediate and target nodes appear with hop scores
- Evidence: `/private/var/folders/sq/kf_272b520nc5wnsp27hq1h00000gn/T/opencode/readme-feature-world/evidence/graphrag/hop.json`

### GRAPH-03 — verified

- Claim: Leiden community detection
- Acceptance: Build communities and read stats
- Expected: Community rows have members, modularity and stable ids
- Evidence: `/private/var/folders/sq/kf_272b520nc5wnsp27hq1h00000gn/T/opencode/readme-feature-world/evidence/graphrag/communities.json`

### GRAPH-04 — verified

- Claim: JIT fact verification
- Acceptance: Create a fact with a citation and verify it
- Expected: Verification returns supported/unsupported with the cited source
- Evidence: `/private/var/folders/sq/kf_272b520nc5wnsp27hq1h00000gn/T/opencode/readme-data-world/evidence/graphrag/jit.json`

### GRAPH-05 — partial

- Claim: D3 visual explorer
- Acceptance: Open the explorer with a populated graph
- Expected: Nodes/edges render with no page error and a node can be selected
- Evidence: `/private/var/folders/sq/kf_272b520nc5wnsp27hq1h00000gn/T/opencode/readme-feature-world/evidence/graphrag/query.json`

### INT-01 — verified

- Claim: 46+ Business Integrations
- Acceptance: Fetch the catalog and count providers
- Expected: At least 46 distinct providers are listed as available
- Evidence: `/private/var/folders/sq/kf_272b520nc5wnsp27hq1h00000gn/T/opencode/readme-feature-world/evidence/integrations/catalog.json`

### INT-02 — verified

- Claim: connected state is truthful
- Acceptance: Read status with no tokens; add a token; read again
- Expected: No token -> connected=false; token -> true with a truthful source
- Evidence: `/private/var/folders/sq/kf_272b520nc5wnsp27hq1h00000gn/T/opencode/readme-feature-world/evidence/integrations/connection_status.json`

### INT-03 — verified

- Claim: OAuth connect
- Acceptance: Run the full consent round-trip against a bounded local provider
- Expected: Token rows persist; status becomes connected; state/PKCE checked
- Evidence: `/private/var/folders/sq/kf_272b520nc5wnsp27hq1h00000gn/T/opencode/readme-feature-world/evidence/integrations/oauth_connect.json`

### INT-04 — partial

- Claim: use connected data
- Acceptance: Read a bounded mocked dataset and ingest it
- Expected: Records are returned/ingested with source identity and no silent empty success

### INT-05 — partial

- Claim: outbound actions
- Acceptance: Request a send/create; approve; verify one effect at the mocked provider
- Expected: No send before approval; exactly one approved effect

### INT-06 — verified

- Claim: disconnect
- Acceptance: Disconnect, then read status and attempt a data call
- Expected: Status returns disconnected and revoked tokens no longer work
- Evidence: `/private/var/folders/sq/kf_272b520nc5wnsp27hq1h00000gn/T/opencode/readme-feature-world/evidence/integrations/disconnect.json`

### INT-07 — verified

- Claim: webhook triggers
- Acceptance: Send an unsigned/forged webhook and a correctly signed one
- Expected: Forged is rejected fail-closed; signed is accepted once
- Evidence: `/private/var/folders/sq/kf_272b520nc5wnsp27hq1h00000gn/T/opencode/readme-feature-world/evidence/integrations/webhook.json`

### INT-08 — verified

- Claim: Salesforce, HubSpot, Slack, Teams, Gmail, Notion, Jira, Linear, Stripe, QuickBooks, Shopify, GitHub, GitLab, Zoom
- Acceptance: Resolve each named provider through the general adapter registry
- Expected: Every named provider resolves to an adapter or an explicitly declared env-keyed surface
- Evidence: `integrations/catalog.json`

### INT-09 — blocked_external

- Claim: live qualification
- Acceptance: Connect and exercise each provider live
- Expected: Live qualification of all 46+ providers (not established by controlled mocks)

### GW-01 — verified

- Claim: OpenAI-compatible API
- Acceptance: Call with a bounded local OpenAI-compatible upstream
- Expected: OpenAI response shape, usage and routing metadata; normal errors in OpenAI shape
- Evidence: `/private/var/folders/sq/kf_272b520nc5wnsp27hq1h00000gn/T/opencode/readme-feature-world/evidence/gateway/openai_chat.json`

### GW-02 — verified

- Claim: Anthropic-compatible API
- Acceptance: Call with a bounded local Anthropic-compatible upstream
- Expected: Anthropic response shape and stop_reason are returned; SSE adapter works
- Evidence: `/private/var/folders/sq/kf_272b520nc5wnsp27hq1h00000gn/T/opencode/readme-feature-world/evidence/gateway/anthropic.json`

### GW-03 — verified

- Claim: point Claude Code, n8n, or any OpenAI-SDK app at Atom
- Acceptance: Call /v1/models with a valid atom_sk key
- Expected: Returns the routable model list in OpenAI shape
- Evidence: `/private/var/folders/sq/kf_272b520nc5wnsp27hq1h00000gn/T/opencode/readme-feature-world/evidence/gateway/models.json`

### GW-04 — verified

- Claim: atom_sk_* keys
- Acceptance: Create a key, use it, revoke it, reuse it, inspect storage
- Expected: Only the hash is stored; revoked/invalid keys are 401
- Evidence: `/private/var/folders/sq/kf_272b520nc5wnsp27hq1h00000gn/T/opencode/readme-feature-world/evidence/gateway/key_lifecycle.json`

### GW-05 — verified

- Claim: over your BYOK
- Acceptance: Send requests with and without x-atom-model and inspect the upstream actually called
- Expected: Header override selects the requested model; otherwise the tier router decides
- Evidence: `/private/var/folders/sq/kf_272b520nc5wnsp27hq1h00000gn/T/opencode/readme-feature-world/evidence/gateway/override.json`

### GW-06 — verified

- Claim: error propagation
- Acceptance: Point at an upstream returning 500/timeout
- Expected: Caller receives a bounded provider error, not a traceback or silent success
- Evidence: `/private/var/folders/sq/kf_272b520nc5wnsp27hq1h00000gn/T/opencode/readme-feature-world/evidence/gateway/error_path.json`

### ROUTE-01 — verified

- Claim: 5-tier cognitive classification
- Acceptance: Classify easy/normal/hard/reasoning/critical prompts
- Expected: Each prompt maps to the expected tier deterministically
- Evidence: `/private/var/folders/sq/kf_272b520nc5wnsp27hq1h00000gn/T/opencode/readme-feature-world/evidence/routing/tiers.json`

### ROUTE-02 — verified

- Claim: 16+ providers
- Acceptance: List provider catalog and count
- Expected: At least 16 providers are registered, including the named families
- Evidence: `/private/var/folders/sq/kf_272b520nc5wnsp27hq1h00000gn/T/opencode/readme-feature-world/evidence/routing/providers.json`

### ROUTE-03 — partial

- Claim: automatic cost-aware routing, fallback
- Acceptance: Send a request with a failing primary and a healthy secondary
- Expected: Answer comes from the secondary and the fallback is recorded

### ROUTE-04 — partial

- Claim: opt-in learning router (feedback-based re-ranking)
- Acceptance: Record positive/negative feedback and compare ranked candidates
- Expected: Feedback shifts the ranking; flag off restores the baseline order
- Evidence: `/private/var/folders/sq/kf_272b520nc5wnsp27hq1h00000gn/T/opencode/readme-feature-world/evidence/routing/learning_router.json`

### ROUTE-05 — verified

- Claim: RTK token compression
- Acceptance: Compress a long transcript and inspect token savings + retained facts
- Expected: Token count falls and asserted facts remain
- Evidence: `/private/var/folders/sq/kf_272b520nc5wnsp27hq1h00000gn/T/opencode/readme-feature-world/evidence/routing/rtk.json`

### ROUTE-06 — partial

- Claim: local models (Ollama first-class, or any local OpenAI-compatible server)
- Acceptance: Point at a bounded local OpenAI-compatible server and send a chat
- Expected: Request goes to the local server; no cloud key is required
- Evidence: `/private/var/folders/sq/kf_272b520nc5wnsp27hq1h00000gn/T/opencode/readme-feature-world/evidence/routing/local_models.json`

### IO-01 — verified

- Claim: MCP client for external tool servers
- Acceptance: Register a local MCP server, handshake, list tools
- Expected: Tool schemas round-trip; invalid server fails closed
- Evidence: `/private/var/folders/sq/kf_272b520nc5wnsp27hq1h00000gn/T/opencode/readme-feature-world/evidence/interop/mcp_register.json`

### IO-02 — verified

- Claim: external tool execution
- Acceptance: Execute one benign tool and inspect the result + audit
- Expected: Result returns; sandbox/capability gates apply; failures propagate
- Evidence: `/private/var/folders/sq/kf_272b520nc5wnsp27hq1h00000gn/T/opencode/readme-feature-world/evidence/interop/mcp_execute.json`

### IO-03 — verified

- Claim: A2A Agent Card
- Acceptance: Fetch the card
- Expected: Valid A2A 1.0 card with skills, capabilities and endpoint
- Evidence: `/private/var/folders/sq/kf_272b520nc5wnsp27hq1h00000gn/T/opencode/readme-feature-world/evidence/interop/a2a_card.json`

### IO-04 — verified

- Claim: A2A message/send
- Acceptance: Send message/send, a malformed envelope, and an unauthenticated request
- Expected: Valid request returns JSON-RPC result; parse/invalid/auth errors use the documented codes
- Evidence: `/private/var/folders/sq/kf_272b520nc5wnsp27hq1h00000gn/T/opencode/readme-feature-world/evidence/interop/a2a_send.json`

### IO-05 — verified

- Claim: ACP endpoint
- Acceptance: Exercise the ACP endpoint with a valid and invalid request
- Expected: Valid request reaches ChatOrchestrator; invalid request is rejected
- Evidence: `/private/var/folders/sq/kf_272b520nc5wnsp27hq1h00000gn/T/opencode/readme-feature-world/evidence/interop/acp.json`

### IO-06 — verified

- Claim: span tracing with optional Langfuse export
- Acceptance: Make a traced call with export off and with a local collector
- Expected: Span ids/parents are recorded; export payload is well-formed when enabled
- Evidence: `/private/var/folders/sq/kf_272b520nc5wnsp27hq1h00000gn/T/opencode/readme-feature-world/evidence/interop/tracing.json`

### GOAL-01 — verified

- Claim: terminate on a definition_of_done predicate instead of always burning to max_steps
- Acceptance: Run an objective with a satisfiable predicate and max_steps above it
- Expected: Loop stops at the satisfying step, not max_steps, and records why
- Evidence: `/private/var/folders/sq/kf_272b520nc5wnsp27hq1h00000gn/T/opencode/readme-feature-world/evidence/goals/objective.json`

### GOAL-03 — verified

- Claim: custom action surfaces
- Acceptance: Register a custom action at INTERN and call it at STUDENT
- Expected: STUDENT cannot see/call it; INTERN+ can
- Evidence: `/private/var/folders/sq/kf_272b520nc5wnsp27hq1h00000gn/T/opencode/readme-feature-world/evidence/goals/custom_action.json`

### GOAL-05 — verified

- Claim: goal-driven loops
- Acceptance: Create a goal, start a run, read status, restart and re-read
- Expected: Run/status persist across restart; cancellation is honoured
- Evidence: `/private/var/folders/sq/kf_272b520nc5wnsp27hq1h00000gn/T/opencode/readme-feature-world/evidence/goals/run.json`

### WF-01 — verified

- Claim: Describe the outcome. Atom builds and runs the workflow.
- Acceptance: Create a two-step workflow and re-read it
- Expected: Definition persists with steps, ordering and an approval policy
- Evidence: `/private/var/folders/sq/kf_272b520nc5wnsp27hq1h00000gn/T/opencode/readme-feature-world/evidence/workflows/create.json`

### WF-02 — verified

- Claim: runs the workflow
- Acceptance: Execute a deterministic workflow and read the execution
- Expected: Execution completes with per-step results and durable status
- Evidence: `/private/var/folders/sq/kf_272b520nc5wnsp27hq1h00000gn/T/opencode/readme-feature-world/evidence/workflows/execute.json`

### WF-03 — verified

- Claim: replayable workflow
- Acceptance: Execute, restart, re-read history
- Expected: Execution history is unchanged and downloadable
- Evidence: `/private/var/folders/sq/kf_272b520nc5wnsp27hq1h00000gn/T/opencode/readme-evidence/install.json`

### WF-04 — verified

- Claim: Scheduled workflow
- Acceptance: Create/list/delete a schedule; optionally wait for one firing
- Expected: Job persists and fires at the interval; deletion removes it
- Evidence: `/private/var/folders/sq/kf_272b520nc5wnsp27hq1h00000gn/T/opencode/readme-feature-world/evidence/workflows/schedule.json`

### WF-05 — partial

- Claim: Human-in-the-Loop approval gates
- Acceptance: Execute, observe PAUSED, approve, observe resume
- Expected: No critical step runs before approval; resume completes it once
- Evidence: `/private/var/folders/sq/kf_272b520nc5wnsp27hq1h00000gn/T/opencode/readme-feature-world/evidence/workflows/hitl_queue.json`

### WF-06 — verified

- Claim: governed, replayable workflow
- Acceptance: Create version 2, compare, roll back
- Expected: Version metadata and active definition are correct after rollback
- Evidence: `/private/var/folders/sq/kf_272b520nc5wnsp27hq1h00000gn/T/opencode/readme-feature-world/evidence/workflows/versioning.json`

### WF-07 — verified

- Claim: import a pre-built personal starter
- Acceptance: Import a starter, inspect its approval gate, execute it
- Expected: Template instantiates with an approval gate and runs
- Evidence: `/private/var/folders/sq/kf_272b520nc5wnsp27hq1h00000gn/T/opencode/readme-feature-world/evidence/workflows/templates.json`

### CORE-01 — verified

- Claim: Chat
- Acceptance: Send a chat turn and read the persisted session
- Expected: Reply and session history agree; no stream is required
- Evidence: `/private/var/folders/sq/kf_272b520nc5wnsp27hq1h00000gn/T/opencode/readme-core-world/evidence/core/chat.json`

### CORE-02 — verified

- Claim: Data ... Bring records
- Acceptance: Upload one file per format and inspect extracted text/tables
- Expected: Each format yields the expected text/rows; failures are explicit
- Evidence: `/private/var/folders/sq/kf_272b520nc5wnsp27hq1h00000gn/T/opencode/readme-feature-world/evidence/data/formats.json`

### CORE-03 — verified

- Claim: Workspace ... review or correct it
- Acceptance: Open a canvas, edit content, reload, download
- Expected: Edit persists and the download matches the edited content
- Evidence: `/private/var/folders/sq/kf_272b520nc5wnsp27hq1h00000gn/T/opencode/readme-feature-world/evidence/core/canvas.json`

### CORE-04 — verified

- Claim: Agents ... teach an agent
- Acceptance: Teach a rule, run a later task, inspect the applied lesson
- Expected: Lesson persists and is referenced by the later run
- Evidence: `/private/var/folders/sq/kf_272b520nc5wnsp27hq1h00000gn/T/opencode/readme-feature-world/evidence/core/teach.json`

### CORE-05 — verified

- Claim: Activity ... See results, failures and unfinished work
- Acceptance: Run one success and one failure; read history
- Expected: Both runs appear with honest terminal states
- Evidence: `/private/var/folders/sq/kf_272b520nc5wnsp27hq1h00000gn/T/opencode/readme-feature-world/evidence/goals/create.json`

### CORE-06 — verified

- Claim: Settings ... providers and data configuration
- Acceptance: Store a BYOK key, read it masked, and route one call
- Expected: Key persists encrypted; masked read; routing uses it
- Evidence: `/private/var/folders/sq/kf_272b520nc5wnsp27hq1h00000gn/T/opencode/readme-feature-world/evidence/core/settings.json`

### CORE-07 — verified

- Claim: ATOM_PRODUCT_PROFILE=full restores the wider surface
- Acceptance: Fetch the profile in both modes and open a deferred UI route
- Expected: Core defers the wider surface; full exposes it without code changes
- Evidence: `/private/var/folders/sq/kf_272b520nc5wnsp27hq1h00000gn/T/opencode/readme-feature-world/evidence/core/profile.json`

### INST-02 — verified

- Claim: make backend ... full backend on :8001
- Acceptance: Start and hit /health/ready
- Expected: Process serves and readiness is true
- Evidence: `/private/var/folders/sq/kf_272b520nc5wnsp27hq1h00000gn/T/opencode/readme-evidence/install.json`

### INST-03 — verified

- Claim: make frontend ... Next.js UI on :3001
- Acceptance: Start and load /login
- Expected: Page renders with no fatal error and the API rewrite reaches the backend
- Evidence: `docs/acceptance/readme_feature_readiness_2026-10-31/evidence/frontend-dev.log`

### INST-04 — verified

- Claim: sign in as admin@example.com (password in backend/logs/bootstrap_admin_password.txt)
- Acceptance: Read the 0600 password file and log in
- Expected: Login succeeds; file is not world-readable; password is not logged
- Evidence: `/private/var/folders/sq/kf_272b520nc5wnsp27hq1h00000gn/T/opencode/readme-evidence/install.json`

### INST-05 — verified

- Claim: Workflow data, agent state, and memory live on your infrastructure
- Acceptance: Create data, restart, re-read
- Expected: Data survives the restart in the same data root
- Evidence: `/private/var/folders/sq/kf_272b520nc5wnsp27hq1h00000gn/T/opencode/readme-evidence/install.json`

### SEC-01 — verified

- Claim: Execution Sandbox ... enforced at every tool-dispatch hub
- Acceptance: Attempt a disallowed path/tool/egress and an allowed one
- Expected: Disallowed call is denied and audited; allowed call proceeds
- Evidence: `/private/var/folders/sq/kf_272b520nc5wnsp27hq1h00000gn/T/opencode/readme-feature-world/evidence/security/sandbox.json`

### SEC-02 — verified

- Claim: OAuth integration tokens encrypted at rest (Fernet)
- Acceptance: Persist a token, read the raw column, decrypt through the service
- Expected: Raw value is ciphertext; service returns plaintext; prod fails closed without a key
- Evidence: `/private/var/folders/sq/kf_272b520nc5wnsp27hq1h00000gn/T/opencode/readme-feature-world/evidence/security/token_encryption.json`

### SEC-03 — verified

- Claim: Per-Agent Capability Bindings
- Acceptance: Call allowed and disallowed tools for the same agent
- Expected: Disallowed tool is denied; allowed tool runs
- Evidence: `/private/var/folders/sq/kf_272b520nc5wnsp27hq1h00000gn/T/opencode/readme-feature-world/evidence/security/capabilities.json`

### SEC-04 — verified

- Claim: Outbound Gatekeeper
- Acceptance: Call an outbound provider with a masking rule and a mutation rule
- Expected: Response fields are masked; mutation requires approval
- Evidence: `/private/var/folders/sq/kf_272b520nc5wnsp27hq1h00000gn/T/opencode/readme-feature-world/evidence/security/gatekeeper.json`

### SEC-05 — verified

- Claim: Data-Taint Tracking
- Acceptance: Observe restricted data then attempt an external send
- Expected: Send is blocked with a provenance violation
- Evidence: `/private/var/folders/sq/kf_272b520nc5wnsp27hq1h00000gn/T/opencode/readme-feature-world/evidence/security/taint.json`

### SEC-06 — verified

- Claim: External MCP Client ... arbitrary external MCP servers
- Acceptance: Connect a local server and an unroutable/unauthorised target
- Expected: Local server works; disallowed target is refused
- Evidence: `interop/mcp_register.json`

### SEC-07 — verified

- Claim: OIDC SSO + SCIM v2 provisioning + 8-role RBAC
- Acceptance: Call protected endpoints with no token, a member token, and an admin token
- Expected: 401/403 as appropriate; no data leak; admin succeeds
- Evidence: `/private/var/folders/sq/kf_272b520nc5wnsp27hq1h00000gn/T/opencode/readme-feature-world/evidence/security/unauth.json`

### SEC-08 — verified

- Claim: production fails closed without key
- Acceptance: Attempt to mint/store a token
- Expected: Refuses instead of generating an ephemeral key
- Evidence: `/private/var/folders/sq/kf_272b520nc5wnsp27hq1h00000gn/T/opencode/readme-feature-world/evidence/security/fail_closed.json`

### PERF-03 — verified

- Claim: 85k+ test functions
- Acceptance: Collect the suite and count functions
- Expected: Collected count is at least 85,000 across the documented files
- Evidence: `docs/acceptance/readme_feature_readiness_2026-10-31/evidence/test-count.txt`

