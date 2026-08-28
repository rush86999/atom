# Atom — AI-Powered Business Automation Platform

> **Last Updated**: Aug 21, 2026. AI agents automate workflows, integrate services, and manage operations.

**Stack**: Python 3.11, FastAPI, SQLAlchemy 2.0, SQLite/PostgreSQL, multi-provider LLM, Playwright, Redis (WS pub-sub only), Alembic, LanceDB (embedded file store), FastEmbed.

**Dirs**: `backend/core/`, `backend/api/`, `backend/tools/`, `backend/tests/`, `frontend-nextjs/`, `mobile/`, `docs/`

---

## ⚠️ NEVER Commit

| File/Directory | Risk |
|---|---|
| `.claude/`, `.env*`, `secrets.json`, `credentials.json`, `*.pem`, `*.key`, `backend/token.json` | Key/credential exposure |

**Before committing**: `git status` and verify none are staged. **If leaked**: rotate keys, `git filter-repo`/BFG (NOT `git rm`), force-push only after history is clean, notify maintainers.

---

## Architecture

**Deployment model: SINGLE-TENANT.** Atom is a single-tenant, locally-owned app. All multi-tenant machinery (tenant_id columns, `get_current_tenant`, `tenant_settings`/tenant-scoped stores, SaaS plan gates) exists **only for feature parity with the SaaS offering — it is NOT the deployment model**. Decision rules that follow:
- File-based stores (`./data/*.json`, LanceDB, SQLite) are FIRST-CLASS for this app, not a legacy gap. Don't propose "move it to the DB" as an improvement on their account.
- Tenant-scoped paths (e.g. BYOK `store_tenant_api_key`/`tenant_settings`, tenant_id filters) are compatibility shims — keep them working, never treat them as load-bearing for local deployments, and don't build new features that require them.
- Precedence for credentials/config: local store (file/env) wins in practice; DB sync targets exist for parity only. **BYOK keys specifically** (`api/byok_routes.py`): `data/byok_keys.json` is the single source of truth; the `tenant_settings` DB mirror is write/read-gated behind `ATOM_BYOK_DB_SYNC` (default OFF). Deleting a key must clean all stores (file rows tenant-scoped + global, DB row) — the DELETE endpoint does this unconditionally as hygiene.
- When a bug involves tenant plumbing, the fix should preserve parity semantics but optimize for the single-operator case.

**Storage**: Personal Edition = embedded LanceDB (`./data/lancedb`, `./data/atom_memory`) + SQLite default; Redis/Valkey optional (WS pub-sub only). SaaS flips `LANCEDB_CLOUD_ENABLED=true` (S3/R2).

**Governance flow**: `User Request → AgentContextResolver → GovernanceCache → AgentGovernanceService → Agent Execution → Response`

**Maturity levels** (confidence-based routing):
| Level | Confidence | Capabilities |
|---|---|---|
| STUDENT | <0.5 | Read-only (BLOCKED → training) |
| INTERN | 0.5–0.7 | Streaming, forms (PROPOSAL → approval) |
| SUPERVISED | 0.7–0.9 | State changes (under supervision) |
| AUTONOMOUS | >0.9 | All actions |

**Action complexity**: 1 LOW (presentations STUDENT+) · 2 MODERATE (streaming INTERN+) · 3 HIGH (state changes SUPERVISED+) · 4 CRITICAL (deletions AUTONOMOUS only)

> ⚠️ **Tier is routing, not security.** Maturity decides what an agent is *normally* allowed to do from past clean runs — it does **not** bound blast radius; a prompt-injected agent at any tier acts at that tier's full scope. Bounding blast radius requires the deterministic sandbox layer (#38): filesystem scope, tool whitelist, egress allowlist, resource caps, tripwires. See `docs/security/TRUST_VS_SANDBOX.md`, `docs/security/PROMPT_INJECTION_DEFENSE_PLAN.md`.

---

## Core Components

*(file-path map; deep detail in `docs/architecture/*.md`)*

1. **Agent Governance** — `agent_governance_service.py`, `agent_context_resolver.py`, `governance_cache.py`: lifecycle/permissions/maturity, <1ms cached checks
2. **Streaming LLM** — `llm/byok_handler.py`, `atom_agent_endpoints.py`: OpenAI/Anthropic/DeepSeek/Gemini/Ollama, token streaming via WebSocket. **OpenCode Go provider** (`opencode-go`, `llm/provider_rate_limits.py`): low-cost subscription gateway at `https://opencode.ai/zen/v1` (key `OPENCODE_API_KEY`); custom RPM/TPM/context limits feed BPC routing — headroom penalty + context clamp + hard-skip at exhaustion (see `docs/architecture/` + `tests/test_opencode_go_provider.py`)
3. **Canvas Presentation** — `tools/canvas_tool.py`, `api/canvas_routes.py`: charts, markdown, forms with governance
4. **Real-Time Agent Guidance** — `tools/agent_guidance_canvas_tool.py`, `core/view_coordinator.py`, `core/error_guidance_engine.py`: live tracking, multi-view orchestration, error resolution
5. **Python Package Support** — `core/package_governance_service.py`, `package_dependency_scanner.py`, `package_installer.py`: per-skill Docker, pip-audit+Safety scanning, maturity gating
6. **Canvas AI Accessibility** — `frontend-nextjs/hooks/useCanvasState.ts`: hidden a11y trees, `window.atom.canvas.getState()`, <10ms overhead
7. **LLM Canvas Summaries** — `core/llm/canvas_summary_service.py`: 50–100 word summaries for episodic memory
8. **Queen Agent** — `core/agents/queen_agent.py`, `intent_classifier.py`: WORKFLOW intents → structured blueprints
9. **Unstructured Tasks** — `atom_meta_agent.py`, `fleet_admiral.py`: TASK intents → Fleet-recruited specialists; `spawn_agent()` for custom domains
10. **BYOK Cognitive Tiers** — `core/llm/cognitive_tier_system.py`, `cache_aware_router.py`, `escalation_manager.py`: 5-tier LLM routing, ~90% cost reduction via caching
10b. **Learning LLM Router** — `core/learning_llm_router.py`, `core/llm/learning_router_registry.py`, `core/llm/routing/per_model_router.py`, `core/llm/response_quality.py`: per-model satisfaction predictors re-rank BPC candidates from observed outcomes (truncation/schema/refusal) + user feedback; 16-feature vector (10 baseline + 6 intent one-hots from the intent detector); EMA telemetry term steers during predictor cold-start (incl. full cold start — no predictor bucket yet); legacy 10-feature `.pkl` predictors keep serving via `n_features_in_` truncation; DB-persisted (`llm_routing_feedback`), live `/api/chat/feedback`, flag-gated (`ATOM_LEARNING_ROUTER`, off). See `docs/architecture/LEARNING_LLM_ROUTER.md`
11. **Browser Automation** — `tools/browser_tool.py`, `api/browser_routes.py`: Playwright CDP, INTERN+ required
12. **Device Capabilities** — `tools/device_tool.py`, `api/device_capabilities.py`: camera INTERN+, screen SUPERVISED+, location/notifications INTERN+, cmd exec AUTONOMOUS only
13. **Atom CLI Skills** — `tools/atom_cli_skill_wrapper.py`, `skills/atom-cli/`: 6 built-in skills, subprocess wrapper with 30s timeout
14. **Deep Linking** — `core/deeplinks.py`, `api/deeplinks.py`: `atom://agent/{id}`, `atom://workflow/{id}`, etc.
15. **Enhanced Feedback** — `api/feedback_enhanced.py`, `feedback_analytics.py`: ratings, corrections, A/B testing
16. **Student Training** — `core/trigger_interceptor.py`, `student_training_service.py`: 4-tier routing, AI duration estimation, supervision, proposals
17. **Database Models** — `core/models.py`: AgentRegistry, AgentExecution, AgentFeedback, CanvasAudit, Episode*, CommunitySkill*, TrainingSession, etc.
18. **Episodic Memory** — `episode_segmentation_service.py`, `episode_retrieval_service.py`, `episode_lifecycle_service.py`, `agent_graduation_service.py`: hybrid PG+LanceDB, 4 retrieval modes, graduation at 10/25/50 episodes
19. **World Model & Business Facts** — `core/agent_world_model.py`, `api/admin/business_facts_routes.py`: verified knowledge with citations, JIT verification, GraphRAG
20. **Monitoring** — `api/health_routes.py`, `core/monitoring.py`: `/health/{live,ready,metrics}` (Prometheus), structlog
21. **CI/CD** — `.github/workflows/ci.yml` (backend tests incl. DeepSeek/OpenCode-Go suites + e2e journeys) and `docker.yml` (image build)
22. **Personal Edition** — `cli/daemon.py`, `docker-compose-personal.yml`: local Docker + SQLite, daemon mode, FastEmbed embeddings
23. **Code Quality** — `mypy.ini`, `backend/docs/CODE_QUALITY_STANDARDS.md`: type hints enforced via CI
24. **E2E Tests** — `backend/tests/e2e_ui/`: 486 test functions, API-first auth, worker isolation, Page Object Model
25. **Advanced Skills** — marketplace, dynamic loading, DAG composition, supply-chain security
26. **GraphRAG & Entity Types** — `core/graphrag_engine.py`, `core/graphrag/multi_hop_expansion.py`, `core/graphrag/community_detection.py`, `entity_type_service.py`: PG recursive CTEs, 6 canonical types, multi-hop scored expansion, Leiden community detection. **Temporal Evolution (P0+W1–W7, Aug 2026)**: bi-temporal time travel across the graph — ingestion date anchors (`core/memory/temporal_normalizer.py`, `ATOM_TEMPORALITY_ENABLED`), `as_of` cutoffs on expansion + `local_search`/`global_search`, rolling-window community detection + hierarchy (`parent_community_id` lineage), generation archival into `graph_community_snapshots` for global-search time travel, dialect-aware SQL expander (SQLite portable). See `docs/architecture/TEMPORAL_EVOLUTION.md`
26c. **Zero-Trust Federation** — `api/routes/federation_routes.py`, `core/identity/did_manager.py`, `core/identity/verifiable_credentials.py`, `core/federation/zero_trust_security.py`: DIDs/VCs at `/api/federation/{dids,credentials,verify,security/health}`; in-memory state (DB persistence pending)
26d. **Enhanced Orchestration** — `core/orchestration/conductor_agent.py`, `core/orchestration/workflow_state_machine.py`, `core/orchestration/event_bus.py`: 5 strategies at `POST /api/v1/workflows/conductor/execute`; EventBus lifecycle events; validated transitions + rollback
27. **Frontend XSS Protection** — `frontend-nextjs/lib/sanitize.ts`: DOMPurify `sanitizeHtml()`/`renderMarkdownSafe()` applied to all `dangerouslySetInnerHTML` sites
28. **Mobile Secure Storage** — `mobile/src/storage/secureTokenStorage.ts`: expo-secure-store (iOS Keychain / Android EncryptedSharedPreferences), transparent AsyncStorage migration
29. **Safe Expression Evaluator** — `core/safe_evaluator.py`: AST-validated `safe_eval()` replacing raw `eval()` in workflow conditions, event bus, conductor
30. **CSV Injection Guard** — `accounting/export_service.py:_sanitize_csv_cell`: prefixes `= + - @` cells with quote in financial exports (CWE-1236)
31. **Workflow Parameter Validation** — `core/advanced_workflow_system.py::ParameterValidator`: per-parameter type checks (string/number/array/select) + custom rules (min/max length, min/max value, regex `pattern`); dead code today (test-only, not wired to routes). See `.archive/dead-core-ai-2026-07/workflow_parameter_validator.py` for the former ReDoS-guard implementation (archived, was never production-wired).
32. **Ollama Local LLM** — `core/llm/byok_handler.py`, `core/byok_endpoints.py`: fully local inference, no API key, budget tier at zero cost
33. **Per-Turn Fact Extraction** — `core/turn_fact_extractor.py` (+ `turn_fact_queue.py`, `turn_fact_vector_store.py`, `turn_fact_categories.py`): Mem0's 5 durable-fact categories; hooks `sync_turn` (fire-and-forget) + `on_pre_compress` (queue worker); Tier-1 SQL recall (sub-ms) + Tier-2 LanceDB semantic (opt-in); SQL row is source of truth; maturity-gated; never raises. See `docs/architecture/CONTEXT_MEMORY.md`
34. **Agent Memory Tools** — `tools/memory_tool.py`: `memory_remember` (INTERN+, c2) / `memory_forget` (SUPERVISED+, c3); circuit breaker (5 fails → 120s cooldown); FTS5 lexical search; session-end extraction hook; truncation boundary protection. See `docs/architecture/HERMES_COMPARISON.md`
35. **Outcome Verification** — `core/tool_outcome_verifier.py`, `core/capability_graduation_service.py`, `core/episode_retrieval_service.py`: tri-state `verified` flag gates graduation (unverified can't inflate); episodic outcome prefilter (`WHERE outcome='failure'` before vector search). See `docs/architecture/CONTEXT_MEMORY.md` § Reddit-Critique Follow-On
36. **Pre-Action Match-Confidence Layer** — `core/selector_confidence_service.py`, `core/llm/match_confidence_tiebreaker.py`, `tools/browser_tool.py`, `core/proposal_service.py`: pre-action tri-state (high/partial/ambiguous) selector certainty before click/fill; deterministic scorer + budget-tier LLM tiebreaker (circuit breaker, 256-entry cache); strict Playwright locators; partial/ambiguous → `ProposalService` for ALL tiers; shadow mode default; per-agent opt-out. See `docs/architecture/MATCH_CONFIDENCE.md`
37. **Self-Consistency Voter + Shadow Audit** — `core/llm/self_consistency_voter.py`, `core/hallucination_config.py`, `core/llm_service.py`: N-sample (Wang et al. 2022) majority vote; `VoteResult` tri-state mirrors #36; audit row per vote; shadow mode; force-proposal gating is the caller's job. Kill switch `ATOM_SELF_CONSISTENCY=false`. See `docs/architecture/SELF_CONSISTENCY_VOTER.md`
38. **Execution Sandbox Layer** — `core/sandbox_policy.py`, `sandbox_config.py`, `sandbox_audit.py`, `sandbox_fs.py`, `sandbox_caps.py`, `sandbox_tripwire.py`, `sandbox_killrun.py`, `sandbox_egress_proxy.py`, `sandbox_runtime/`, `core/provenance.py`, `core/llm/action_judge.py`, `core/sandbox_gate.py`: deterministic blast-radius layer, 5 phases (policy → FS scope → tripwires/caps/KillRun → Firecracker/E2B runtime + egress proxy → provenance tagging + LLM ActionJudge). **P9: default-on for all dispatch paths** via shared `sandbox_gate.evaluate_tool_call` at `integrations/mcp_service.call_tool` (agent loop, workflow, fleet, business agents — not just the meta-agent). Kill switch `ATOM_SANDBOX_FORCE_ENFORCE=false` restores shadow. See `docs/architecture/SANDBOX_LAYER.md`
39. **Office Automation & Canvas Co-Editing** — `core/office_service.py`, `core/workbook_runtime.py`, `core/office_sync_service.py`, `api/office_routes.py`, `tools/office_tool.py`: read/write/render docx/xlsx/pptx; formula-evaluating Excel runtime (LibreOffice → `formulas` → openpyxl); bi-directional canvas/file co-editing + sync. **Co-editing loop live (Aug 2026)**: editable `OfficeFileCanvas` (xlsx grid w/ sheet tabs + formula flags, docx line-per-paragraph editor, pptx slide cards) commits via `/sync-update`; docx sync is paragraph-in-place (styles/tables/images survive), pptx gained `slide`/`add_slide` edit types (`update_slide` action in PowerPointManager); every file change broadcasts a structured snapshot (cells/paragraphs/slides, not just HTML) on BOTH `canvas:{id}` + `user:{uid}` channels (was dead-lettered); `/present` persists/reuses one DB Canvas row per file (`content.office_file`) so canvases reload at `/canvas/{id}`; all 8 agent write tools call `notify_file_canvases()` so agent edits refresh open canvases. Tests: `backend/tests/test_office_canvas_coediting.py` + `frontend-nextjs/components/canvas/__tests__/OfficeFileCanvas.test.tsx`. See `docs/guides/ATOM_OFFICE_AUTOMATION_GUIDE.md`
40. **LLM Gateway (OpenAI/Anthropic-compatible)** — `core/llm/gateway/`, `api/openai_gateway_routes.py`, `api/gateway_key_routes.py`: inbound `/v1/chat/completions` + `/v1/messages` over BYOK routing; `atom_sk_*` keys (SHA-256 only, `GatewayApiKey`); SSE adapters; wire-format translators; header overrides (`x-atom-model`/`x-atom-tier`/`x-atom-intent`); `ATOM_GATEWAY_ENABLED` master switch. See `docs/architecture/LLM_GATEWAY.md`

### Cloudflare OS gap-closure (P0–P9, Aug 2026)

41. **Credential Encryption (P0)** — `core/privsec/token_encryption.py`: `IntegrationToken` access/refresh tokens encrypted at rest (Fernet); `BYOK_ENCRYPTION_KEY` env or persisted key file `./data/byok_encryption_key` (0600); **fail-closed in prod** (raises instead of minting a throwaway key); legacy plaintext decrypts transparently (`allow_plaintext=True`). See `docs/security/DATA_PROTECTION.md`
42. **Unified Action Registry (P1)** — `core/action_registry.py`, `api/rpc_routes.py` (`POST /api/rpc/{action}`), `frontend-nextjs/lib/rpc-client.ts`: single decorator-based registry both the agent MCP dispatch AND the frontend RPC endpoint route through (resolves the former dead-import seam at `mcp_service.py:840,1105`). Foundation enforcement point for P2/P3/P9.
43. **Agent Capability Bindings (P2)** — `core/capability_resolver.py`: per-agent zero-trust tool scoping (intersection of `AgentRegistry.capabilities` with the tier floor) enforced at `integrations/mcp_service.call_tool`, so ALL callers (agent loop, workflow, meta-agent, fleet) are gated — not just the agent loop. `[]`/`["*"]` default = unrestricted.
44. **Outbound Gatekeeper (P3)** — `middleware/governance_middleware.py`, `core/gatekeeper_config.py` (via `api/gatekeeper_routes.py`): per-service policy gate in front of every outbound integration call (OAuth refresh, rate limiting, response field masking, audit, HITL mutation approval). Fills the formerly-swallowed import at `universal_integration_service.py:10`.
45. **Observation-Based Data Taint (P4)** — `core/data_taint_tracker.py`: tracks sensitivity (public|internal|confidential|restricted, incl. PII auto-classification) of data a run observed; blocks external outbound when restricted data is headed out. First real emission of the reserved `VT_PROVENANCE` violation type. Documents carry a nullable `sensitivity` column.
46. **Blueprint Security (P5)** — `core/blueprint_sanitizer.py` (`strip_credentials` denylist regex), `POST /api/canvas/{id}/fork`: sharing/forking never leaks credentials — template export + canvas fork strip credential-shaped keys; fork creates an independent copy (fresh id, `share_token=None`, one audit row, stripped component configs).
47. **Real MCP Client (P6)** — `core/mcp_client.py` (JSON-RPC 2.0 over HTTP+SSE/stdio), revived `core/mcp_service.py` `register_server` (real handshake, replaces the placeholder), `api/mcp_client_routes.py` (`/api/mcp/servers`): Atom connects to arbitrary external MCP servers (Cloudflare "MCP Server Portals"), not just the 3 hardcoded pseudo-servers.
48. **Per-Canvas Server Runtime (P7)** — `core/canvas_logic_service.py`, `CanvasLogic` model, `frontend-nextjs/components/canvas/CanvasLogicPanel.tsx`: a canvas can have server-side Python logic executed in the isolated sandbox runtime with a per-canvas storage namespace (`./data/canvas_runtime/<canvas_id>`); AUTONOMOUS-gated. Also repairs the `CustomComponent` model stub (adds slug/props_schema/default_props/is_public/current_version/min_maturity_level/tenant_id).
49. **Workspace-Scoped Curated Context (P8)** — curated knowledge in `Workspace.metadata_json["curated_context"]` + skill assignment via `workspace_skills` association table, injected into the agent system prompt at `core/generic_agent.py:_workspace_context_block`. `knowledge_documents`/`agent_episodes` gained nullable `workspace_id`. Admin surface: `api/workspace_context_routes.py`.
50. **Mini-Apps (IMPLEMENTED, backend — agent-driven authoring)** — stateful, resumable canvas-UI apps (spreadsheets/docs/decks) on Firecracker microVMs. MVC model: `Canvas`=View, `CanvasLogic` (P7)=Controller, `MiniApp` manifest=Model; instance state in `CanvasState` (versioned, latest-wins); storage host-mediated (`MiniAppStorage` + `MiniAppAsset`); Firecracker is the ONLY mini-app runtime (`get_miniapp_runtime()` fails closed — no Docker fallback); deps baked into per-app ext4 rootfs by `scripts/build_miniapp_rootfs.sh` (fail-closed scan, never auto-build). **All authoring is agent-driven — a user creates a mini-app by chatting with an agent in the main chat UI**, which drives 13 `mini_app_*` actions (`core/action_registry.py` + `tools/mini_app_tool.py`): scaffold → write_logic (syntax-gated, checkpointed) → dev_run (dry) → run_tests (acceptance feedback loop) → revert → publish → install → run. **Dual-face access**: every instance is a rendered canvas for the user AND structured state for the agent (canvas AI-a11y layer + `mini_app_get_state`); co-editing is universal via the app-agnostic WS `canvas:update` broadcast, and agents are autonomous operators — after install they run the app (`mini_app_run` → read back → iterate in a closed a11y-view → decide → run → verify loop), gated by declared scopes ∩ the operating agent's own tier; **every instance also carries a per-instance user↔agent chat** (the `/canvas` side-chat co-editor pattern applied universally) so the user instructs/approves in natural language while the agent acts on the live canvas. The platform is the harness — every side effect flows through P1→P3→P4→P9; viewer/operator rights always cap an app's declared scopes (no privilege escalation). **Data layer (Aug 2026)**: host-mediated per-instance record store `CanvasRecord` (series + monotonic `seq` + JSON `data`, full CRUD via `record_ops` envelope, `mini_app_db_query`/`mini_app_db_write` actions, and `/api/mini-apps/instances/{id}/records/*` routes — one service `core/mini_app_db_service.py`); read bridge injects own-history (`db.record_queries`), `documents.search` (`data_sources`), and integration results (`mcp_servers` pre-fetch via `ExternalIntegrationService` — credentials resolved host-side, never reach the guest). Caps: 200 ops/run, 100 KiB/record, 10k rows/series; kill switch `ATOM_MINIAPP_DB_ENABLED`. See `docs/architecture/MINI_APPS.md`. See `docs/architecture/MINI_APPS.md` + `docs/deployment/FIRECRACKER_HOST_SETUP.md`.
51. **Agent Hybrid Search** — `core/hybrid_search/` (`lexical_ranker.py`, `documents_hybrid.py`, `backfill_matcher.py`), `alembic/versions/20260808_add_documents_fts.py`: `documents.search` is now BM25 (FTS5/tsvector+GIN) + LanceDB vector fused by RRF (k=60); join-key bridge (`pg_document_id` stamped at ingest) closes the PG↔LanceDB silo; `scripts/backfill_lancedb_join_keys.py` backfills pre-bridge rows; ILIKE fallback ladder; extra legs (episodes/turn_facts/reasoning-steps) additive. See `docs/architecture/AGENT_HYBRID_SEARCH.md`
52. **Knowledge VFS** — `core/vfs_base.py`, `core/vfs_registry.py`, `integrations/vfs/knowledge_vfs.py`, `core/knowledge_vfs_config.py`: knowledge stores exposed as an agent-native `knowledge/` tree — 11 `documents.*` actions (`ls/tree/cat/head/tail/grep/scan/search/map/reduce/ask_image`) with line-numbered citable content (`L<n>: <text>`); flag `ATOM_KNOWLEDGE_VFS_ENABLED` (default ON, additive read-only; off = legacy ILIKE `documents.search`). See `docs/architecture/KNOWLEDGE_VFS.md`
53. **Postcondition Oracle + Two-Tier Confidence** — `core/oracle/` (`__init__.py` decorator registry, `postcondition_verifiers.py`): re-derives success against the system of record (DB read-back) independent of the tool's self-report — only `EXTERNAL_VERIFIED` is credible; `verify_before_retry` prevents duplicate side effects on ambiguous timeouts; flag `ATOM_ORACLE_VERIFIER_ENABLED` (default ON, shadow; force-enforce companion off). See `docs/architecture/ORACLE_VERIFICATION.md`
54. **Reviewer Re-delegation Loop** — `verification/review.py`: REVIEW strategy re-delegates the originating specialist with feedback (no candidate swap, deliberately NOT debate — Debate-or-Vote/Cost-of-Consensus literature); pairs with diversity-aware MoA sampling (P4a). See `docs/architecture/REVIEWER_LOOP.md`
55. **Agent Radio (Lateral Coordination)** — `core/agent_radio/` (`radio_service`, `radio_server`, `radio_guard`, `radio_breaker`, `radio_config`), `alembic/versions/20260808_add_lateral_messaging.py`: passive-awareness peer messaging — `radio.create_thread`/`radio.send_message`/`radio.wait_for_mention` via the Unified Action Registry (P2/P9 gates apply); `agent_threads` + `lateral_messages` tables, `agent_executions.thread_id`; mention-first delivery, budget accounting (`ATOM_RADIO_TEAM_BUDGET_USD`), passive inbox drain in both ReAct loops (`generic_agent.py`, `atom_meta_agent.py`), fleet bridge in `_recruit_fleet`; teams opt-in via `config/lateral_teams/*.yaml`; flag `ATOM_RADIO_ENABLED` (default ON). See `docs/architecture/AGENT_RADIO.md`
56. **Fleet Orchestration Wiring (W4)** — `core/fleet_routing_config.py`, `core/specialist_matcher.py`, `core/fleet_orchestration/fleet_scaler_service.py`: dead `route_with_governance` wired into live `AtomMetaAgent.execute()`; real `SpecialistMatcher` (capability overlap + tier + verified-episode ratio); `DelegationChain.max_depth` enforced on nesting DEPTH not link count; fleet budget/memory hooks. **On 2026-08-21 the master switch flipped to ON (shadow)**: fleet-eligible TASK intents get governed recruitment computed + audited on every `execute()` (`fleet_routing_audit` table), responses still come from Queen→ReAct; `ATOM_FLEET_ROUTING_ENABLED=false` is the full kill switch. **Validation pipeline (2026-08-21)**: `fleet_routing_stats.py` (audit + execution-outcome join + `fleet_calibration_status`), `fleet_router_automation.py` (consent-gated `off|notify|approve|auto`, revocation always automatic), `api/fleet_router_routes.py` + public `/health/fleet-router`; enforcement resolved via `resolved_fleet_enforce()` (env kill-switch wins, else latest applied automation action). Single-arm semantics: shadow measures the incumbent baseline (fleet not auto-executed in shadow) — certification = healthy baseline + healthy recruitment → recommend pilot. See `docs/architecture/FLEET_ORCHESTRATION.md`
57. **Agent Environment / Goal-Driven Loop (W5)** — `core/agent_objective.py`, `core/generic_agent.py`: Objective + `definition_of_done` termination predicate (early exit instead of always-`max_steps`), maturity success-ratio as utility target, maturity-gated custom action surface (`register_action`), stuck-detector (P5b/P5c); flag `ATOM_OBJECTIVE_LOOP_ENABLED` (default ON; off restores exact pre-P5 loop). See `docs/architecture/AGENT_ENVIRONMENT.md` + `docs/architecture/STANFORD_VIRTUAL_BIOTECH_PAPERCLIP.md`
58. **Stage Router (Switchyard port)** — `core/llm/stage_router.py`, `core/llm/routing/traffic_split.py`, `alembic/versions/20260811_add_stage_router_audit.py`, `scripts/calibrate_stage_router.py`: proactive turn-level tier routing in both ReAct loops (`generic_agent._react_step`, `atom_meta_agent._react_step`) from tool-result signals — windowed error severity, spinning (churn, no reads/writes), exploring (reads without writes), production intensity; tanh-corroborative scoring (one full signal ≈ 0.46 < default 0.5 threshold; critical error = hard override), pickers (`efficient_first`/`capable_first`), decision-source taxonomy (`override`/`dimensions`/`fall_open`), handoff notes on tier switches. **Harness-first**: `ATOM_TRAFFIC_SPLIT`/`ATOM_STAGE_ROUTING_SPLIT` enable a weighted-random A/B split; every decision is audited (`llm_stage_router_audit`, outcome-joined from `byok_handler._record_outcome_feedback` via a contextvar carrier — cost/quality/latency per decision) so `scripts/calibrate_stage_router.py` can certify per-workload thresholds (RESCUE/LOSS quadrants) before enforcement. **Per-workload control**: readiness is per `agent_id`; enforcement resolves via `resolve_agent_policy` — `configuration["stage_routing"]` (`enforce` bool overrides the global; optional `confidence_threshold`/`picker`/`window` knobs) so certified agents go live while others keep shadowing; audit rows record `policy_source` (global|agent-config). **Consent-gated automation**: `core/llm/stage_router_automation.py` + `api/stage_router_routes.py` (admin-gated `/api/v1/llm/stage-router/{status,automation,config,run-now,approve,reject}`) — a background pass computes per-workload verdicts and either notifies, queues an approval (default), or applies (`ATOM_STAGE_ROUTER_AUTO_ENFORCE=off|notify|approve|auto`); **revocation is always automatic** (fail-safe); actions persisted in `stage_router_automation_actions` + in-app notifications via `NotificationService`. `GET /health/stage-router` reports per-workload phase + minimum detectable gap (two-proportion sample-size math, not a fixed turn count). Shadow by default (`ATOM_STAGE_ROUTING_ENABLED` alone = audit-only; `ATOM_STAGE_ROUTING_FORCE_ENFORCE` = default enforce policy). Never raises. See `docs/architecture/SWITCHYARD_GAP_ANALYSIS.md`
59. **Org Ingestion Sharing (ALL PHASES IMPLEMENTED — 0–2, 2b memory bundle, 3 hub)** — `docs/architecture/ORG_INGESTION_SHARING_PLAN.md`, `core/org_sharing_crypto.py`, `core/ingestion_profile_service.py`, `core/org_data_bundle_service.py`, `core/org_hub_service.py`, `api/data_ingestion_routes.py`, migration `20260816_org_ingestion_sharing`: members of one org running local instances share ingestion config + opt-in data/memory. Phase 0: `HybridDataIngestionService` sync configs/usage stats persist to `ingestion_settings` (were in-memory-only, lost on restart; `ATOM_INGESTION_PERSIST_STATE` default ON). Phase 1: signed Ed25519 ingestion profiles (`GET /api/data-ingestion/profile/export`, `POST .../profile/import` HIGH) — config only, `strip_credentials` fail-closed, key registry `org_public_keys` (`/org-key`, `/org-key/register`); private key in `./data/org_sharing_key` (0600), never DB. Phase 2: org data bundles (`POST .../bundle/export` **CRITICAL — exfiltration surface**, `POST .../bundle/import` HIGH) — normalized records only (never embeddings — importer re-embeds via governed paths), P4 sensitivity gate (confidential/restricted excluded unless ceiling raised for scoped sub-bundles), signature verified BEFORE parse, dedup via `document_ingestions`, tombstones → `freshness_status='removed'`, caps 100k records. **Phase 2b (memory bundle, `bundle_version: 2`, v1 back-compat)**: `graph` section (GraphRAG nodes keyed `(name,type)` — never local UUIDs, never the derived `embedding` column; edges keyed by endpoint pairs, exported only when BOTH endpoints pass the sensitivity filter; import upserts on `(workspace,name,type)` with last-writer-wins merge, sensitivity raised-never-lowered, **no stub nodes** for unresolved edge endpoints, local Leiden recompute via `build_communities`) + `texts` section (`knowledge_documents` SQL upsert + `business_facts` from LanceDB with deterministic `orgbundle:` doc ids); extraction-time taint: `GraphRAGEngine.ingest_document(sensitivity=...)` propagates source-doc classification to extracted nodes (`graph_nodes.sensitivity`); per-section counts in `bundle_exports/imports.section_counts`; sections selectable via `include: [records|graph|texts]`. Episodic memory/chat/turn facts permanently excluded (graduation trust semantics). **Phase 3 (org ingestion hub)**: `core/org_hub_service.py` — one always-on instance owns org sources; members pull signed **delta** bundles on an interval and apply via the Phase 2 import path; hub endpoint `GET /api/data-ingestion/hub/bundles?since=<cursor>` (flag `ATOM_ORG_HUB_ENABLED`, auth = `atom_sk_*` gateway keys via `core/llm/gateway/auth`), member-side `POST /api/data-ingestion/hub/pull` + scheduled loop in `main_api_app` lifespan (env `ATOM_ORG_HUB_URL`, `ATOM_ORG_HUB_API_KEY`, `ATOM_ORG_HUB_PULL_INTERVAL_MIN` default 15, `ATOM_ORG_HUB_SOURCES`, `ATOM_ORG_HUB_SENSITIVITY_CEILING`); monotonic per-source cursor `(max updated_at, external_id)` persisted in `ingestion_settings.usage_stats_json` (integration `org_hub`) — hub is single writer so conflicts impossible by construction; `freshness_status='removed'` rows travel as tombstones; dead hub degrades members to stale-but-functional (loop retries). Kill switch `ATOM_ORG_SHARING_ENABLED` (default OFF).
60. **Trust Calibration Gateway (P0–P3 scaffold IMPLEMENTED — shadow)** — `docs/architecture/TRUST_CALIBRATION_PLAN.md`, `core/trust_calibration/` (`gp.py` product-kernel probit GP k_tool×k_ctx×k_time with half-life decay folded as covariance scale AND label noise → predictive variance floors at base_noise = bounded false-allows; `features.py`; `service.py` adapters over `hitl_actions`+`agent_proposals`; `gateway.py` TTL refit + three-tier allow/ask/block fail-safe ask; `certify.py` temporal-holdout gate: Brier ≤0.25 + denial-coverage ≥0.7 + n≥30; `automation.py` consent-gated off|notify|approve|auto with always-automatic revocation), `api/trust_calibration_routes.py` (admin-gated /assess,/stats,/automation,/run-now,/approve,/reject), migrations `20260822_add_trust_calibration_assessments` + `20260822b_..._actions`. P1 records shadow assessments at BOTH ask-paths (`generic_agent._step_act` HITL pauses, `mcp_service._check_hitl_policy` interventions) keyed decision_ref→HITLAction.id; /stats joins outcomes live (Brier/ECE/rec×outcome matrix). Self-provisioning table on first record. Frontend client `lib/trust-api.ts`. Flags: `ATOM_TRUST_CALIBRATION_ENABLED` (default false→503), `ATOM_TRUST_CALIBRATION_AUTO_ENFORCE` (off|notify|approve|auto default off) + `_AUTO_INTERVAL_MIN` + `_FORCE_ENFORCE`, kernel/threshold knobs `_HALF_LIFE_DAYS/_MAX_OBS/_REFIT_TTL/_TAU_LOW/_TAU_UNCERTAIN`. No decision path reads the posterior until a production certification run passes.

61. **Agent Org Politics & Hierarchy (ALL PHASES P0–P6 IMPLEMENTED, Aug 2026)** — `docs/architecture/AGENT_ORG_POLITICS_PLAN.md`: applies 2025–26 research on agent organizations/hierarchy/emergent "office politics" to the fleet stack. **P0 telemetry** (`agent_org_events` append-only + `core/org_telemetry_service.py`, wire-ins at fleet recruit / radio attach+send / reviewer verdicts, `scripts/org_dynamics_report.py` incumbency+favoritism+COI baselines; `ATOM_ORG_TELEMETRY_ENABLED` default ON). **P1 delegation contracts** (`core/fleet_orchestration/delegation_contracts.py` — typed objective/format/guidance/boundaries/effort handoffs wired into `_recruit_fleet` ChainLinks + conductor AGENT steps; RACI `accountable_agent_id`; `ATOM_DELEGATION_CONTRACTS_ENABLED` default ON). **P2 privilege axis** (`core/org_privileges.py` — Permission≠Privilege: default-DENY expiring leases in `AgentRegistry.configuration["org_privileges"]` for approve/promote/publish/spawn/grant/halt; dispatch gate in `mcp_service.call_tool` after the capability gate, fail-CLOSED; mini_app_publish/install → publish_skill). **P3 skill-scoped trust** (`core/skill_scoped_trust.py` — per-domain shrunk posterior over verified `capability_stats`, β=0.1 pooling via DOMAIN_ALIASES with 0.6 laundering floor, fast-fail penalty, cold-start boost; replaces the matcher's global-confidence term when enabled; `record_usage` stamps failures_verified/last_outcome_at). **P4 contribution credit** (`core/contribution_credit.py` — deterministic bucket-brigade over ChainLink statuses γ=0.7, Σweights=realized outcome, late failure dampens not zeros; feeds graduation from `record_fleet_execution_outcome`; zero-weight skipped = no double-counted failures). **P5 allocator integrity** (`core/org_integrity.py` — self-recruitment block, coordinator rotation fixed|task|daily, model-family diversity floor (shadow), radio→recruit COI signal on link context). **P6 alignment sweep** (`core/org_alignment.py` + `tests/e2e/multi_agent_alignment/` — 3 adversarial scenarios × single/flat/hierarchical structures, judge rubric with aligned_utility; double-gated nightly-only, ≤400 tok/call). **Full lifecycle automation** (`core/org_politics_automation.py` + admin-gated `/api/v1/org-politics/*`): modes off|notify|approve|auto(**default**); escalation needs consent only in approve mode (telemetry ≥10 recruits AND green sweep); revocation ALWAYS automatic (red sweep gap>2.0 or ≥20 COI pairs); flag resolution env kill-switch > latest `org_politics_actions` row > default off (60s TTL cache) so flips need no restart. Rollout posture: P0/P1 ON by default; P2/P3/P5 flip themselves when healthy under `auto`.

---

## Bug-Fix History (TDD — Red-Green-Refactor)

Every fix = failing test first. Full narrative in git history; this is the searchable index. Test files: `backend/tests/test_round{N}_*.py`, `tests/test_auth_fixes.py`, `tests/test_rounds27_30_consolidated.py`, `tests/unit/core/test_sandbox_*.py`, `frontend-nextjs/lib/__tests__/*`.

| Round | Scope | Key fixes | Tests |
|---|---|---|---|
| 5–6 | BYOK/router audit | `require_admin`→None; manager race; 8 str(e) leaks; 15 zero-auth `workflow_debugging` endpoints; `shell_routes /sessions` no auth | 12 |
| 7–8 | Injection/IDOR | business_facts path traversal; SQL interpolation ×3; `get_recording` IDOR; missing `os` import / `await`; wrong params | 11 |
| 9–10 | Deserialization/secrets/eval | hardcoded admin password; webhook fallback secret; raw `eval()` in event_bus/conductor → `safe_eval` (CWE-94) | 7 |
| 11 | Auth/races | refresh-token reuse; print() leaks; hitl double-spend (`with_for_update`); register/run TOCTOU; header logging | 4 |
| 12 | Test infra/headers | timeout marker unregistered; langchain collection break; headers skipped on `/api/`; `SecurityHeadersMiddleware` never registered; `/docs` in prod | 5 |
| 13 | Timezone | `utcnow()` vs aware datetimes (PG TypeError); 5 naive `models.py` defaults | 3 |
| 14 | Auth limits/Pydantic v2 | login/register/refresh unlimited → `AuthRateLimiter` (10/min, 3/5min, 30/min); `@validator` → `@field_validator` | 5 |
| 15–16 | Email verify/2FA | enumeration; missing rate limits; weak entropy; hardcoded backup codes; TOTP brute-force; str(e) leak | 7 |
| 18–31 | Full security sweep | ~1,100 bugs / 150+ files: 992 str(e) leaks → generic; ~250 unauth routes auth'd; 12 naive datetimes; webhooks fail-open + hardcoded secrets; workflow RCE (eval) + ReDoS; fleet/maturity privilege escalation; CSV injection; marketplace zip-slip; messaging/canvas/LLM/memory route auth; finance/tools/monitoring handlers; DB integrity | 199 |
| 38–40 | Final auth sweeps | governance silently disabled (`request`/`http_request`); impersonation via client `user_id`; 17 str(e) leaks; route shadowing (`/search`); ~90 anon endpoints auth'd (business-health, analytics, skill reads, byok pricing…) | 105 |
| 41 | str(e) sweep + social pipeline | 11 leak sites; `uuid4` NameError → duplicate posts; phantom `OAuthToken` schema → real `IntegrationToken` | 11 |
| 42 | Identity sweep | user_templates IDOR ×8 + phantom-schema repair; dashboard/queue clamps; messaging approver spoof; anon reject/cancel auth'd | 16 |
| 43 | Deactivated-user tokens | `get_current_user`/`_ws` reject non-ACTIVE → deactivation immediate for existing JWTs | 6 |
| 44 | Rate-limit bypasses | `X-Scheduler-Secret` presence check removed; XFF spoof → TCP peer unless `TRUST_X_FORWARDED_FOR=1` | 5 |
| 45 | Webhook fail-open | HubSpot/Salesforce/Notion processed unverified when unconfigured → fail closed (503/401) | 6 |
| 46 | Outlook clientState | verification ignored → forged events + entity deletion; fail closed | 4 |
| 47 | BYOK tenant dep | missing `get_current_tenant` → `Depends(None)` → 422 everywhere; implemented in `core/auth.py` | 3 |
| 48 | Test-infra | stale `test_byok_routes.py` (phantom routes) rewritten; session env pollution fixed | 13 |
| 49 | Financial validation | negative amounts → auto-approved invoices, inverted guardrails; `Field(gt=0)` + engine `ValueError` | 11 |
| 50 | Upload size cap | business-facts upload unbounded → `MAX_UPLOAD_BYTES` (50 MiB) | 4 |
| 51 | CSV injection (CWE-1236) | feedback + GL exports unsanitized → `_sanitize_csv_cell` everywhere | 5 |
| 52 | Office leaks + dead router | 9 str(e) sites; `List`/`uuid` NameError → router never mounted (404s / prod crash) | 6 |
| 53 | Office sync containment | unvalidated `file_path` → arbitrary read/overwrite; `_validate_office_path()` at both entry points | 5 |
| 54 | Workspace identity/ownership | spoofed `user_id`; cross-user read/write + external platform side effects; ownership gate; 5 leaks | 7 |
| 55 | Body size limit | unbounded JSON → OOM; streamed 64 MiB cap → 413 | 4 |
| 56 | Password-recovery limits | forgot/reset/verify unthrottled → limiters (5/5min, 10/5min) | 5 |
| 57 | Test-infra | `from main import app` (no `main.py`!) broke 28 files' collection → `main_api_app` | 3 |
| 58 | Office /present + /sync-update | client-supplied `user_id` → audit/memory forgery; R53 dead-code regression (broadcast body swallowed) | 3 |
| 59 | BYOK encryption key | fresh Fernet per start → stored keys bricked on restart; persisted key file (0600) | 5 |
| 60 | Mobile auth user status | mobile login/refresh/biometric accepted deactivated users → non-ACTIVE rejected | 3 |
| 61 | Runtime BYOK manager | unpersisted key + two managers on different keys for same store; `_get_fernet` fail-loud | 5 |
| 62 | BYOK config forward-compat | unknown fields bricked whole store → filter to dataclass fields | 3 |
| 63 | Protection API leaks | str(e) on all 4 endpoints → generic + logger | 4 |
| 64 | Health/federation/workflow leaks | 8 sites incl. public `/health/db` + stdout traceback | 6 |
| 65 | Supervision role gate | intervene/complete/autonomous-approve any-user → `_require_supervisor` (TEAM_LEAD+) | 5 |
| 66 | Canvas family | anon comment endpoints; spoofed `user_id`; IDOR on docs/terminal/email | 7 |
| 67 | Workflow-executed MCP bypass | `WORKFLOW_RUN` granted to all → ungoverned local tool execution; critical MCP tools need `WORKFLOW_MANAGE`; bonus: conductor route shadowing + 422 strategy parse | 10 |
| 68 | Workflow trigger-path sweep | extended the R67 critical-step gate (`core/workflow_security.py`) to every trigger path (advanced_workflow_api + demos, workflow-ui, intelligence `/execute`, atom-agent chat handlers + `/execute-generated`, template `/execute`, mobile `/trigger`) and added auth to anonymous analytics/automation triggers; mobile trigger + intelligence no longer trust spoofable `user_id` | 62 |
| 69 | Async/unguarded execution + unauth sweep | MCP `/execute` critical-tool + `trigger_workflow` gate (`WORKFLOW_MANAGE`, service-level fail-closed for critical-step targets); `trigger_event` skips critical workflows unless `allow_event_critical`; Shopify webhooks fail-closed HMAC (`SHOPIFY_WEBHOOK_SECRET`); `/generate-from-agent` auth + token identity; scheduler critical `nodes[].config.actionType` sink (`has_critical_automation_nodes`) + `authorized` threading; Teams/Gmail webhook shared-secret auth + Gmail resume gate; sales/messaging/workflow-ui/canvas-docs/marketing/oauth-config-status route auth | 60 |
| 70 | Data/predictive/OAuth bug hunt | data tools RCE killed (in-process `exec` fallback removed → fail-closed; `__inputs__['df']` channel; AST policy before `eval`; path allowlist; DuckDB file/URL read + httpfs SSRF blocked); OAuth `/api/auth/*` all auth'd (B7) + provider allowlist (B8); zero `str(e)` leaks; `analyze_data`→SUPERVISED/3 + `forecast`/`run_model` wired (B10); exponential forecast fallback (B11); boot router-mount coverage via HTTP (B12); SUPERVISED gate + HITL `governance` surface (B13); Outlook connect forwards Bearer token | 91 |
| 71 | Stale-suite + service bug hunt | `IntegrationDataMapper.validate_data` type-validation stub → real `_value_matches_type` check (type mismatches previously passed); stale-suite alignment: financial-audit service (29), data-mapper coverage (46), workflow-debugger trace-stream assert (17), browser-agent AI (17), ab-testing env (21); `test_audit_api_endpoints.py` git-rm'd (phantom `/api/v1/financial-audit` router dead since `8bf4e3237`); dev-DB reconciliation — applied guarded DDL for `agent_divisions`/`agent_threads`/`lateral_messages` + 9 drifted columns (a batch-mode alembic FK crash + broken revision chain block the CLI) | 236 + 21 + 4 |
| 72 | Coverage waves 20–26 + e2e repair sweep | `agent_world_model` 60→92%, `entity_type_service` 78→99%, `learning_llm_router` 94%, `turn_fact_extractor` 89%, taint-tracker 100% (315 new tests); phantom `core.acu_billing_service` import (no such module) at 2 archival call sites → real `UsageTrackingService` shim; e2e suite unblocked: fixture `pytest_plugins` wiring, metrics-hook config/session mismatch, phantom `WebSocketManager` patch, Shopify mock `.json`/wrapper bugs, LLM placeholder-key gates (`sk-test-`/`sk-ant-test-`) + OpenCode-Go canary probe, dev-DB reconciliation #2 (atom_dev.db missing `users`/`turn_facts`/`agent_episodes` + ~280 tables → `create_all`; pytest-visible DB is env-dependent via `load_dotenv`); 11 stale e2e/unit suites repaired to current schemas (AgentExecution/CanvasAudit/AgentFeedback/AgentEpisode/AgentProposal drift) | 315 + 243 + 73 e2e |
| 81a–h | Agent journey verification + gap closure (memory & learning included) | `/api/maturity/*` restored (archived July 2026 w/ zero replacements — training approve/complete + INTERN proposal review/execute were unreachable; STUDENT→INTERN promotion severed); `/api/agent-governance/*` MOCK_AGENTS → real AgentRegistry reads, /feedback → submit_feedback, submit-for-approval → real HITLAction; `memory_forget` pinned to complexity 3 (was defaulting to 2 = INTERN could erase facts); session-linked GenericAgent runs create episodes; turn-fact sync_turn parity for GenericAgent; `_check_hitl_policy` fail-CLOSED (catch-all swallowed its own security raises → risky sends silently allowed) + auto-approve compared status STRING to int 5 (TypeError since day one: auto-approve never fired, then would have hard-blocked) → tier-name compare; atom_main registry row get-or-create (record_outcome was a permanent no-op — meta-agent never learned); GenericAgent stamps run_id/tier_at_issuance so P2/P9 gates engage on specialty runs; step-feedback fixed signature (`is_positive` kwarg never existed → TypeError swallowed → APPROVE/REJECT never moved confidence); proposal executions persist as episodes (create_episode_from_execution had zero prod callers); scheduler/direct runs persist execution+episode (exactly-once across all surfaces); tenant_id stamped on AgentExecution rows (AgentEpisode.tenant_id NOT NULL would reject inserts); operator smoke script `backend/scripts/smoke_test_agent_journey.py` (12 checks, isolated SQLite, exit≠0 on any severed link) | 22 + stale-suite re-contracts |
| 81i–j | Journey surfacing + research-informed learning knobs | `lib/maturity-api.ts` typed client (boards-api conventions, 6 contract tests) + `MaturityApprovalPanel.tsx` supervisor UI (training approve→inline complete→promotion notice; reject-reason; INTERN approve&execute — 5 RTL tests; page wiring pending in-flight index.tsx work, snippet in tracker); G14: trusted-user ratings ≥4 nudge confidence +0.005 capped 3/day/(agent,user), ledger in ai_reasoning — research-grounded (explicit ratings high-precision/noisy; promotions stay outcome-gated), flag `ATOM_POSITIVE_RATING_BOOST_*`; G15: `EpisodeLifecycleService.run_daily_maintenance()` decay(90d)+consolidation wired as opt-in daily worker `ATOM_EPISODE_LIFECYCLE_MAINTENANCE_ENABLED`; env docs updated | 13 + panel/client suites |
| 81k–n | Ou-style GP trust calibration gateway (P0–P2) | Plan verified vs repo+research then implemented shadow-first: `core/trust_calibration/` product-kernel probit GP (k_tool×k_ctx×k_time; half-life decay folded as covariance scale AND label noise → predictive variance floors at base_noise = bounded false-allows), three-tier allow/ask/block with fail-safe ask; P1 records assessments at BOTH ask-paths (`_step_act` HITL pauses + `_check_hitl_policy` interventions) keyed decision_ref→HITLAction.id; /stats joins outcomes live → Brier/10-bin ECE/rec×outcome matrix; P2 `certify()` temporal-holdout gate (Brier ≤0.25, denial-coverage ≥0.7, n≥30) + `scripts/calibrate_trust_gateway.py` exit-code verdicts. Flag `ATOM_TRUST_CALIBRATION_ENABLED` default false → 503. No decision path reads the posterior; P3 relaxation gated on passing production certification. Tests caught: 0/1 labels in ±1 GP muted rejection evidence; StaticPool needed for TestClient+in-memory sqlite | 27 trust + 86 full R81 cluster |
| 81o–p | Trust gateway automation + frontend surface | `core/trust_calibration/automation.py`: run_automation_pass dispatches certify verdicts through off\|notify\|approve\|auto — auto applies enable verdicts and ALWAYS auto-revokes on regression; `TrustCalibrationAction` ledger (monotonic int PK — created_at second-granularity made applied/revoked order ambiguous) drives resolved_trust_enforce() env-FORCE-wins boolean; admin endpoints GET/POST /automation, /run-now, /approve/{id}, /reject/{id}; opt-in lifespan worker; gateway._ensure_table self-provisions assessments table per-engine (removes manual alembic for dev/hybrid); `lib/trust-api.ts` typed FE client (assess/stats/automation/run-now). Tests lock: off-noop, auto-apply, auto-revoke-on-regression, notify cooldown, latest-ledger-wins consent, self-provisioning | 7 automation + 5 FE contract |

62. **Admin Runtime Settings (env vars as UI settings, Aug 2026)** — `core/settings_catalog.py` (~165 typed SettingSpecs covering every CLAUDE.md var; secrets locked server-side), `core/runtime_settings.py` (resolver: explicit env var WINS > `runtime_settings` DB row > default — kill-switch semantics preserved; 60s TTL cache; never raises), `api/admin_runtime_settings_routes.py` (admin-gated GET catalog/categories/audit + PUT/DELETE at `/api/v1/admin/settings`), models `RuntimeSetting`+`SettingChangeAudit`, migration `20260824_add_runtime_settings`; UI: `pages/admin/settings.tsx` (category tabs, source badges env/UI/default, reset) + `lib/runtime-settings-api.ts`. **Wired subsystems** (resolvers read through the layer — UI edits live within TTL): hallucination_config (SC/MoA/cascade/thresholds), sandbox_config, stage_router (+automation), fleet_routing, radio, knowledge VFS, trust calibration knobs, org politics automation, LLM gateway (+request logger), turn facts, doc freshness, memory consolidation, reviewer loop, contribution credit. Guide: `docs/guides/RUNTIME_SETTINGS_GUIDE.md`.

63. **Ontology Draft Promotion Automation (Aug 2026)** — `core/ontology/ontology_draft_automation.py` + admin-gated `/api/v1/ontology-drafts/{status,automation,run-now,pending,approve/{id},reject/{id}}` (`api/ontology_draft_routes.py`): closes the O1 journey gap — auto-discovered `EntityTypeDefinition` drafts (`is_active=False`, from integration-sync `resolve_or_create_draft`, OpenIE discovery, single-entity linking) rot invisibly until a manual PATCH; the pass promotes them following the repo's consent-gated pattern (off|notify|approve|auto, default **auto**), evidence-thresholded (graph-usage node-label match incl. the `{workspace}_{integration}_{type}` slug-suffix heuristic; re-discovery = `version` raised since the type's last automation action; optional `sample_count`; age floor), **always-automatic revocation** (zero usage + no new evolution + stale), and **never overrides manual decisions** (PATCH stamps `metadata_json["manual_decisions"]`; a newer manual decision wins outright; system types out of scope). Ledger `OntologyDraftAction` (`ontology_draft_actions`, monotonic int PK, evidence_json) + migration `20260826_...`; en-vars in the settings catalog under *Ontology Drafts*. See `docs/architecture/ONTOLOGY_DRAFT_AUTOMATION.md`.

**Feature rounds**: 41 (match-confidence, see #36), 42 (self-consistency shadow, see #37), 43–47 (sandbox layer, see #38 — 166 tests) — landed in shadow mode (compute + audit on, enforcement off), then **flipped to default-on by P9 (Aug 2026)** for all dispatch paths via `core/sandbox_gate.py`; kill switch `ATOM_SANDBOX_FORCE_ENFORCE=false`. **W1–W5 (Aug 2026)**: knowledge VFS (#52) → hybrid search (#51) → oracle verification (#53) → reviewer loop (#54) → agent environment (#57) + fleet wiring (#56) + Agent Radio (#55); additive layers default ON (VFS/oracle/objective), fleet routing ON-shadow with validation automation built (2026-08-21, see #56). **W20–W26 (Aug 2026)**: coverage waves on `agent_world_model`/`entity_type_service`/`learning_llm_router`/`turn_fact_*`/supervision stack + full `tests/e2e/` repair (fixture `pytest_plugins` wiring, metrics-hook session mismatch, phantom `WebSocketManager`/`ACUBillingService` patches, LLM placeholder-key gates, 11 stale suites re-synced to current schemas); e2e now 73 passed / 165 clean skips (Postgres/Docker/real-LLM-key dependent) with 0 errors.

**Rounds 38–69 policy**: zero-regression verified via `comm -13` on failure lists; mypy baseline unchanged; `main_api_app` imports clean. Audit docs: `docs/FRONTEND_SECURITY_AUDIT.md`, `docs/MOBILE_SECURITY_AUDIT.md`.

---

## Development Guidelines

### Patterns
```python
FEATURE_FLAG = os.getenv("MY_FEATURE_ENABLED", "true").lower() == "true"

# Service layer: ALWAYS context manager (avoids leaks)
with get_db_session() as db:
    agent = db.query(Agent).filter(Agent.id == agent_id).first()

# API routes: dependency injection
@app.get("/agents/{agent_id}")
def get_agent(agent_id: str, db: Session = Depends(get_db)):
    return db.query(Agent).filter(Agent.id == agent_id).first()
```

### Error Handling — NEVER leak `str(e)` to clients
```python
except Exception as e:
    logger.error(f"Operation failed: {e}")   # keep detail server-side
    raise api_error(ErrorCode.DATABASE_ERROR, "Database operation failed")
```

### API Response Standards
```python
{"success": True, "data": {...}, "message": "...", "timestamp": "..."}
{"success": False, "error_code": "AGENT_NOT_FOUND", "message": "...", "details": {...}}
```

### Coding Standards
Python 3.11+, PEP 8, type hints required (mypy in CI), Google-style docstrings — see `backend/docs/CODE_QUALITY_STANDARDS.md`. Import order: stdlib → third-party → local. Performance: `GovernanceCache` for hot data (<1ms), async/await for I/O, connection pooling.

---

## Testing

**TDD mandatory for bug fixes** — see `docs/testing/BUG_FIX_PROCESS.md`. **Never fix a bug without a failing test first.** Red → Green (minimal fix) → Refactor. Frontend (Jest/RTL): same pattern (`waitFor`, fake timers).

> **Before touching any file, check `docs/testing/TESTED_FILES_TRACKER.md`** — date-stamped log of every file tested/fixed (R79+), measured coverage, and known-remaining failures. Grep it to skip already-verified work; append a row after every fix.

```bash
PYTHONPATH=/Users/rushiparikh/projects/atom/backend pytest tests/ -v
pytest tests/test_governance_streaming.py -v
pytest tests/ --cov=core --cov-report=html

# E2E UI (Phase 234, 486 tests): API-first auth, worker isolation, POM
cd backend/tests/e2e_ui && ./scripts/start-e2e-env.sh
pytest backend/tests/e2e_ui/ -v -n 4
pytest backend/tests/e2e_ui/ -v --alluredir=allure-results && allure serve allure-results
```

Key e2e files: `backend/tests/e2e_ui/conftest.py`, `fixtures/auth_fixtures.py` (API-first, 10–100× faster), `pages/page_objects.py`. Coverage IDs: AUTH-01..07, AGNT-01..08.

---

## Environment Variables

```bash
# Database / Personal Edition
DATABASE_URL=sqlite:///./atom_dev.db     # Personal default (Postgres for prod)
EMBEDDING_PROVIDER=fastembed
FASTEMBED_MODEL=BAAI/bge-small-en-v1.5
LANCEDB_PATH=./data/lancedb
LANCEDB_CLOUD_ENABLED=false              # true = SaaS S3/R2 remote storage
ATOM_HOST_MOUNT_ENABLED=false            # AUTONOMOUS gate
PORT=8000   LOG_LEVEL=INFO   BROWSER_HEADLESS=true

# LLM keys: OPENAI_API_KEY, ANTHROPIC_API_KEY, MINIMAX_API_KEY (optional 204K ctx)
# OpenCode Go (low-cost subscription gateway, opencode.ai/zen): 
OPENCODE_API_KEY=                # OPENCODE-GO_API_KEY does NOT work (hyphen); this is the canonical env name
OPENCODE_BASE_URL=https://opencode.ai/zen/v1
# Cost-effective LLM testing (e2e fixtures/tests/e2e/fixtures/llm_fixtures.py):
# with OPENCODE_API_KEY set, e2e LLM tests pin routing to opencode-go's
# CHEAPEST model (deepseek-v4-flash) for ALL query complexities (BPC would
# otherwise bill deepseek-v4-pro/kimi-k2.7-code for COMPLEX/ADVANCED) and run
# a single 1-token canary probe per session — an unfunded subscription skips
# the suite with a clear reason instead of burning retries.
# Custom rates/limits feed BPC routing (headroom penalty + context clamp):
OPENCODE_RPM=60                  # requests/min ceiling for routing headroom
OPENCODE_TPM=2000000             # tokens/min ceiling for routing headroom
OPENCODE_MAX_CONTEXT=200000      # gateway context cap (clamps candidate models)
# Free-usage models (gateway IDs ending in "-free": deepseek-v4-flash-free,
# mimo-v2.5-free, ...) can exhaust their free allowance even with an active
# subscription — byok_handler retries the SAME request on a paid model
# (deepseek-v4-flash cheapest; documented siblings deepseek-v4-flash-free→
# deepseek-v4-flash, mimo-v2.5-free→minimax-m2.7) when they fail with
# CreditsError/"Insufficient balance". Override per-model:
# OPENCODE_FREE_PAID_FALLBACK='{"deepseek-v4-flash-free": "deepseek-v4-flash"}'
# Local LLM (Ollama, free, keyless): OLLAMA_BASE_URL=http://localhost:11434/v1  OLLAMA_MODEL=llama3:8b

# Governance
STREAMING_GOVERNANCE_ENABLED=true   CANVAS_GOVERNANCE_ENABLED=true
FORM_GOVERNANCE_ENABLED=true        BROWSER_GOVERNANCE_ENABLED=true
EMERGENCY_GOVERNANCE_BYPASS=false

# Monitoring
PROMETHEUS_ENABLED=true   STRUCTLOG_LEVEL=INFO   HEALTH_CHECK_DISK_THRESHOLD_GB=1

ATOM_MEMORY_POISON_TRIPWIRE=true         # quarantines sources that supersede >=5 facts/10min (memory-injection defense)

# Model provenance & harness-patch scoping (R82, docs/architecture/HARNESS_EVOLUTION.md)
ATOM_MODEL_DRIFT_DETECTION_ENABLED=true  # detect silent provider checkpoint bumps (resolved-ID change under stable alias)

# Temporal Evolution (docs/architecture/TEMPORAL_EVOLUTION.md)
ATOM_TEMPORALITY_ENABLED=true            # ingestion date anchors + bi-temporal graph reads (default ON)

# Per-turn fact extraction (docs/architecture/CONTEXT_MEMORY.md)
TURN_FACT_EXTRACTION_ENABLED=true        # 1 fast-model call/turn (R72 D: default ON)
TURN_FACT_PRE_COMPRESS_ENABLED=true      # pre-truncation queue, free — default ON
TURN_FACT_VECTOR_RECALL_ENABLED=true     # LanceDB semantic recall (R72 D: default ON)
TURN_FACT_MAX_PER_TURN=5   TURN_FACT_EXTRACTION_SAMPLE_RATE=1.0   TURN_FACT_QUEUE_MAXSIZE=100

# Hallucination mitigation (PR #548 + Round 42)
ATOM_CASCADE_ROUTING=false               # retry structured-gen on same family
ATOM_SELF_CONSISTENCY=false              # master switch
ATOM_SELF_CONSISTENCY_SAMPLES=3   ATOM_SELF_CONSISTENCY_FORCE_PROPOSAL=false
ATOM_SELF_CONSISTENCY_HIGH_THRESHOLD=0.85   ATOM_SELF_CONSISTENCY_PARTIAL_THRESHOLD=0.50

# R72 reasoning-loop upgrades (all deterministic gains default ON; LLM judge stays opt-in)
ATOM_MOA_ENABLED=true                    # Mixture-of-Agents on hard structured tasks (F)
ATOM_MOA_SAMPLES=3                       # samples drawn per MoA vote (min 2)
ATOM_PARALLEL_TOOLS=true                 # in-loop parallel tool execution (G)
ATOM_MAX_PARALLEL_TOOLS=4                # max tools per parallel batch (G)
ATOM_SKILL_INJECTION_ENABLED=true        # prompt-time skill auto-injection (C)
ATOM_TOOL_CACHE_ENABLED=true             # read-only tool-result memoization (H)
ATOM_TOOL_CACHE_TTL=30                   # cache TTL seconds (H)

# Execution Sandbox Layer (Rounds 43-47 + P9 Cloudflare OS G5: DEFAULT-ON)
# P9 flipped the deterministic blast-radius controls ON by default for ALL
# dispatch paths (agent loop, workflow, fleet, business — via the shared
# sandbox_gate at integrations/mcp_service.call_tool). Each flag remains a kill
# switch: set any to `false` to restore the prior shadow/off behavior instantly.
ATOM_SANDBOX_ENABLED=true                # master (Phase A+) — ON (P9)
ATOM_SANDBOX_FORCE_ENFORCE=true          # enforce, not just audit — ON (P9)
ATOM_SANDBOX_POLICY_TENANT_OVERRIDE=false
ATOM_SANDBOX_FS_ENABLED=true             # Phase B — fs scope — ON (P9)
ATOM_SANDBOX_WHITELIST_ENABLED=true   ATOM_SANDBOX_TRIPWIRES_ENABLED=true   ATOM_SANDBOX_CAPS_ENABLED=true   # Phase C — ON (P9)
ATOM_SANDBOX_MAX_TOOL_CALLS=200   ATOM_SANDBOX_MAX_EXEC_SECONDS=600
ATOM_SANDBOX_MAX_BYTES_WRITTEN=104857600   ATOM_SANDBOX_MAX_COST_USD=5.0
ATOM_SANDBOX_RUNTIME=docker               # docker|firecracker|e2b (E2B_API_KEY for e2b)
ATOM_SANDBOX_EGRESS_ENABLED=false         # Phase D — stays OFF (opt-in; network egress isolation)
ATOM_SANDBOX_VM_MEM_MB=256   ATOM_SANDBOX_VM_VCPUS=1   ATOM_SANDBOX_VM_BOOT_TIMEOUT_SECONDS=5
ATOM_SANDBOX_PROVENANCE_ENABLED=true      # Phase E — ON (P9); ATOM_SANDBOX_JUDGE_ENABLED=false (LLM judge opt-in per R72)
ATOM_SANDBOX_JUDGE_TIMEOUT_SECONDS=2.0   ATOM_SANDBOX_JUDGE_CIRCUIT_THRESHOLD=5   ATOM_SANDBOX_JUDGE_CIRCUIT_COOLDOWN_SECONDS=120

# W1–W5 agent intelligence (Aug 2026) — docs/architecture/{KNOWLEDGE_VFS,AGENT_HYBRID_SEARCH,ORACLE_VERIFICATION,REVIEWER_LOOP,AGENT_RADIO,FLEET_ORCHESTRATION,AGENT_ENVIRONMENT}.md
ATOM_KNOWLEDGE_VFS_ENABLED=true            # knowledge/ VFS (11 documents.* actions) — default ON, additive
ATOM_HYBRID_VECTOR_LEG_ENABLED=true        # BM25+vector RRF for documents.search; false = lexical-only
ATOM_ORACLE_VERIFIER_ENABLED=true          # postcondition oracle (shadow; force-enforce companion off)
ATOM_OBJECTIVE_LOOP_ENABLED=true           # goal-driven loop — definition_of_done early exit + stuck-detector
ATOM_FLEET_ROUTING_ENABLED=true            # governed fleet dispatch — default ON (shadow: recruitment+audit run; FORCE_ENFORCE=true to return fleet results)
ATOM_FLEET_ROUTING_FORCE_ENFORCE=false
# Fleet router validation automation (#56, consent-gated shadow→pilot)
# resolved_fleet_enforce(): env FORCE_ENFORCE wins, else latest applied automation action
ATOM_FLEET_ROUTER_AUTO_ENFORCE=approve     # off | notify | approve | auto (revoke is always automatic)
ATOM_FLEET_ROUTER_AUTO_INTERVAL_MIN=60     # certification cadence
ATOM_FLEET_ROUTER_AUTO_SUCCESS_GAP=0.70    # incumbent baseline floor to recommend pilot (≥30 joined rows)
ATOM_FLEET_ROUTER_AUTO_MIN_ROWS=30         # outcome-joined rows floor per verdict
ATOM_FLEET_ROUTER_AUTO_NOTIFY_COOLDOWN_HOURS=24  # notify-mode dedupe
ATOM_RADIO_ENABLED=true                    # lateral peer messaging (3 radio.* actions) — default ON
ATOM_RADIO_TEAM_BUDGET_USD=0.20   ATOM_RADIO_INBOX_CAP=10   ATOM_RADIO_BACKLOG_TTL_MIN=30
ATOM_RADIO_WAIT_TIMEOUT_SECONDS=30   ATOM_RADIO_BREAKPOINT_GATE=true

# Stage Router (Switchyard port, #58) — docs/architecture/SWITCHYARD_GAP_ANALYSIS.md
ATOM_STAGE_ROUTING_ENABLED=true               # master switch; on alone = shadow (audit-only, default ON)
ATOM_STAGE_ROUTING_FORCE_ENFORCE=false        # live override of loop model type (fast/quality)
ATOM_STAGE_ROUTING_PICKER=efficient_first     # efficient_first | capable_first (default tier)
ATOM_STAGE_ROUTING_CONFIDENCE_THRESHOLD=0.5   # corroborative signals must clear this
ATOM_STAGE_ROUTING_WINDOW=3                   # recent turns scored per decision
ATOM_TRAFFIC_SPLIT=false                      # A/B harness master switch (calibration)
ATOM_STAGE_ROUTING_SPLIT=                     # JSON weights, e.g. '{"efficient": 0.7, "capable": 0.3}'
ATOM_STAGE_ROUTING_SPLIT_SEED=                # optional int for reproducible splits

# Stage Router Automation (#58) — consent-gated per-workload certification
ATOM_STAGE_ROUTER_AUTO_ENFORCE=approve        # off | notify | approve | auto (revoke is always automatic)
ATOM_STAGE_ROUTER_AUTO_INTERVAL_MIN=60        # certification cadence
ATOM_STAGE_ROUTER_AUTO_SUCCESS_GAP=0.03       # capable-arm success advantage to certify
ATOM_STAGE_ROUTER_AUTO_MAX_COST_RATIO=8.0     # max capable/efficient cost ratio
ATOM_STAGE_ROUTER_AUTO_REVOKE_GAP=0.02        # capable-arm deficit that auto-revokes
ATOM_STAGE_ROUTER_AUTO_NOTIFY_COOLDOWN_HOURS=24  # min hours between notifications per agent (dedupe)

# Security (Rounds 18-69)
MAX_UPLOAD_BYTES=52428800                # 50 MiB upload cap
MAX_BODY_BYTES=67108864                 # 64 MiB POST/PUT/PATCH body cap (R55)
ATOM_BOOTSTRAP_PASSWORD_FILE=            # generated admin password, written 0600
SHOPIFY_WEBHOOK_SECRET=   ATOM_WHATSAPP_WEBHOOK_SECRET=   ATOM_SLACK_WEBHOOK_SECRET=
ATOM_DISCORD_WEBHOOK_SECRET=   ATOM_TELEGRAM_WEBHOOK_SECRET=    # fail-closed if missing
ATOM_TEAMS_WEBHOOK_SECRET=   ATOM_GMAIL_WEBHOOK_SECRET=   ATOM_SCHEDULER_SECRET=   ZENDESK_WEBHOOK_SECRET=   # R69 webhook/scheduler shared secrets — fail-closed if missing

# Trust Calibration Gateway (R81l-p) — docs/architecture/TRUST_CALIBRATION_PLAN.md
ATOM_TRUST_CALIBRATION_ENABLED=false            # master switch; true = SHADOW recording at ask-paths
ATOM_TRUST_CALIBRATION_AUTO_ENFORCE=off         # off|notify|approve|auto (consent-gated relaxation loop)
ATOM_TRUST_CALIBRATION_AUTO_INTERVAL_MIN=60     # automation worker cadence
ATOM_TRUST_CALIBRATION_FORCE_ENFORCE=false      # env hard-switch overrides the action ledger
ATOM_TRUST_CALIBRATION_HALF_LIFE_DAYS=30        # k_time decay half-life
ATOM_TRUST_CALIBRATION_MAX_OBS=400              # most-recent decisions per refit
ATOM_TRUST_CALIBRATION_REFIT_TTL=300            # posterior cache seconds
ATOM_TRUST_CALIBRATION_TAU_LOW=0.35             # p below -> block (confident denial)
ATOM_TRUST_CALIBRATION_TAU_UNCERTAIN=0.15       # sigma^2 above -> ask (ASK band)

# Ontology Draft Promotion Automation (#63) — docs/architecture/ONTOLOGY_DRAFT_AUTOMATION.md
ATOM_ONTOLOGY_DRAFT_AUTO_ENFORCE=auto           # off|notify|approve|auto (consent-gated promotion; default auto; off = no pass, no loop)
ATOM_ONTOLOGY_DRAFT_AUTO_INTERVAL_MIN=60        # pass cadence
ATOM_ONTOLOGY_DRAFT_AUTO_MIN_NODES=3            # graph-usage evidence floor
ATOM_ONTOLOGY_DRAFT_AUTO_MIN_AGE_DAYS=2         # min draft age to promote (one burst is not recurrence)
ATOM_ONTOLOGY_DRAFT_AUTO_MIN_SAMPLES=3          # sample_count floor (applied only when discovery metadata sets it)
ATOM_ONTOLOGY_DRAFT_AUTO_REVOKE_STALE_DAYS=14   # unused + undiscovered -> automatic revoke
ATOM_ONTOLOGY_DRAFT_AUTO_NOTIFY_COOLDOWN_HOURS=24  # notify-mode dedupe

# Agent Org Politics & Hierarchy (#61) — docs/architecture/AGENT_ORG_POLITICS_PLAN.md
ATOM_ORG_TELEMETRY_ENABLED=true                 # P0 org-dynamics events (default ON)
ATOM_DELEGATION_CONTRACTS_ENABLED=true          # P1 typed delegation handoffs (default ON)
ATOM_ORG_PRIVILEGES_ENABLED=                    # P2 privilege gates — unset = automation state; true/false = hard override
ATOM_SKILL_SCOPED_TRUST_ENABLED=                # P3 matcher trust term — same resolution
ATOM_CONTRIBUTION_CREDIT_ENABLED=false          # P4 bucket-brigade graduation credit (env-only by design)
ATOM_ALLOCATOR_INTEGRITY_ENABLED=               # P5 self-dealing/diversity/COI — same resolution
ATOM_ALIGNMENT_SWEEP_ENABLED=false              # P6 nightly LLM sweep (cost-gated; escalation blocked while unrun)
ATOM_ORG_AUTO_ENFORCE=auto                      # lifecycle automation: off|notify|approve|auto
ATOM_ORG_AUTO_INTERVAL_MIN=1440                 # certification cadence (daily)
ATOM_ORG_AUTO_NOTIFY_COOLDOWN_HOURS=24

# LLM Gateway (Phase A, R70) — docs/architecture/LLM_GATEWAY.md
ATOM_GATEWAY_ENABLED=true                # master switch for /v1/* inbound surface
ATOM_GATEWAY_PREFER_COST=true            # cost-aware routing default
ATOM_GATEWAY_LOG_BODIES=false            # Phase B: persist full bodies (redacted)
ATOM_GATEWAY_DEFAULT_MAX_TOKENS=1000
ATOM_GATEWAY_BUDGET_ALERTS=false         # Phase B: threshold spend alerts
ATOM_GATEWAY_LOG_RETENTION_DAYS=30       # Phase B: log sweep retention
# Phase C providers: XAI_API_KEY, CEREBRAS_API_KEY, FIREWORKS_API_KEY,
# HUGGINGFACE_API_KEY, NVIDIA_NIM_API_KEY, ZAI_API_KEY
# Phase D: subscription-credential reuse (ChatGPT Plus / Claude Pro) at
# /api/v1/llm-oauth/* — OAuth-granted only; reuses BYOK_ENCRYPTION_KEY for
# token encryption. See docs/security/LLM_GATEWAY_SUBSCRIPTION_REUSE.md
```

---

## Database Migrations

```bash
alembic revision -m "description" | upgrade head | downgrade -1 | current | history
```

**SQLite (Personal Edition)**: column type/`add` changes must use `op.batch_alter_table()` and guard with `_table_exists()`/`_column_exists()` (SQLite has no native `ALTER COLUMN`; dev DB is hybrid — schema via `create_all`, alembic bookkeeping lags, unguarded migrations fail). Canonical pattern: `alembic/versions/20260624_add_turn_facts.py`.

**Reconciling a hybrid DB**: divergent heads + complete schema → `alembic stamp <merge_rev> --purge`, then `upgrade head` runs only genuinely-pending migrations.

---

## Performance Targets

| Metric | Target | Current |
|---|---|---|
| Cached governance check | <10ms | 0.027ms P99 |
| Agent resolution | <50ms | 0.084ms avg |
| Streaming overhead | <50ms | 1.06ms avg |
| Cache hit rate | >90% | 95% |
| Cache throughput | >5k ops/s | 616k ops/s |
| Browser session creation | <5s | ~1–2s avg |
| Health liveness / readiness | <10 / <100ms | 2ms / 15ms P50 |
| Metrics scrape | <50ms | 8ms P50 |
| Vector embedding | <20ms | 10–20ms (FastEmbed) |

---

## Key Concepts

1. Multi-agent architecture with maturity levels · 2. Governance first — every AI action attributable/auditable · 3. Single-tenant (no workspace isolation) · 4. Graceful degradation (log, allow) · 5. Sub-ms cache · 6. Observability (health, metrics, structured logs) · 7. E2E excellence (486 tests, API-first, parallel) · 8. Personal Edition (Docker Compose local) · 9. Type safety (mypy in CI) · **Always consider agent attribution and governance for any AI feature.**

---

## Quick Reference Commands

```bash
# Dev (run from repo root — entry is backend/main_api_app.py, NOT main.py)
PYTHONPATH=$PWD:$PWD/backend ./backend/venv/bin/python -m uvicorn main_api_app:app --reload --port 8000

# Auth (admin password auto-generated on first launch → backend/logs/bootstrap_admin_password.txt, 0600)
curl -X POST http://localhost:8000/api/auth/login -H "Content-Type: application/json" \
  -d '{"username":"admin@example.com","password":"<from-file>"}'

# Daemon / Health
atom-os daemon | status | stop | execute <command>
curl http://localhost:8000/health/live    # /health/ready, /health/metrics

# Canvas state (browser console)
window.atom.canvas.getState('canvas-id') / window.atom.canvas.getAllStates()

# Cognitive tiers / GraphRAG / Intent + Fleet
python -c "from core.llm.cognitive_tier_system import CognitiveClassifier; print(CognitiveClassifier().classify('hello'))"
curl -X POST "/api/v1/graph/search/local" -d '{"query": "Project Alpha", "depth": 2}'
curl -X POST "/api/v1/agent/route" -d '{"request": "Analyze sales data"}'

# Playwright / DB / Git / Logs
playwright install chromium
alembic upgrade head
git status | add . | commit -m "feat: ..." | push origin main
tail -f logs/atom.log

# E2E / Personal Edition
cd backend/tests/e2e_ui && ./scripts/start-e2e-env.sh && pytest backend/tests/e2e_ui/ -v -n 4
docker-compose -f docker-compose-personal.yml up -d | logs -f | down
```

---

*Full docs in `docs/`, `backend/docs/`, and test files. Component deep-dives in `docs/architecture/*.md`. Bug-hunt narratives in git history (see table above).*
