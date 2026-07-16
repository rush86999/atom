# Atom - AI-Powered Business Automation Platform

> **Project Context**: Intelligent business automation/integration platform using AI agents to automate workflows, integrate services, and manage operations.

**Last Updated**: July 12, 2026

---

## Quick Overview

**What**: AI-powered workflow automation with multi-agent governance, real-time streaming LLM, canvas presentations, browser/device automation, episodic memory, auto-dev, federation, personal edition, production CI/CD.

**Tech Stack**: Python 3.11, FastAPI, SQLAlchemy 2.0, SQLite/PostgreSQL, Multi-provider LLM, Playwright, Redis (WebSocket), Alembic

**Key Dirs**: `backend/core/`, `backend/api/`, `backend/tools/`, `backend/tests/`, `frontend-nextjs/`, `mobile/`, `docs/`

**Key Services**: `agent_governance_service.py`, `trigger_interceptor.py`, `student_training_service.py`, `supervision_service.py`, `governance_cache.py`, `intent_classifier.py`, `queen_agent.py`, `fleet_admiral.py`, `atom_meta_agent.py`, `auto_dev/`, `atom_saas_client.py`, `health_routes.py`, `monitoring.py`, `cli/daemon.py`, `useCanvasState.ts`, `core/llm/canvas_summary_service.py`

---

## ⚠️ Security: NEVER Commit These Files

| File/Directory | Risk |
|----------------|------|
| **`.claude/`** | API key exposure |
| **`.env*`** | Credential leakage |
| **`secrets.json`** | Full system compromise |
| **`*.pem`, `*.key`** | MITM attacks |
| **`credentials.json`** | Unauthorized access |
| **`backend/token.json`** | Session hijacking |

**Before committing**: `git status` and verify none of the above are staged.

**If secrets accidentally committed**: (1) Rotate all keys immediately (2) Use `git filter-repo` or BFG (NOT `git rm`) (3) Force push only after history is clean (4) Notify maintainers. See CONTRIBUTING.md.

---

## Architecture Overview

**Storage topology (Personal Edition):** LanceDB is **embedded** (file-based `./data/lancedb` / `./data/atom_memory`) — no separate vector server container. SQLite is the default relational store. Redis/Valkey is only used for WebSocket pub-sub and can be omitted for single-process Personal deployments. SaaS edition flips `LANCEDB_CLOUD_ENABLED=true` for S3/R2 remote storage.

### Multi-Agent Governance Flow
```
User Request → AgentContextResolver → GovernanceCache → AgentGovernanceService → Agent Execution → Response
```

### Maturity Levels

| Level | Confidence | Triggers | Capabilities |
|-------|-----------|----------|--------------|
| STUDENT | <0.5 | BLOCKED → Training | Read-only |
| INTERN | 0.5-0.7 | PROPOSAL → Approval required | Streaming, forms |
| SUPERVISED | 0.7-0.9 | Under supervision | State changes |
| AUTONOMOUS | >0.9 | Full execution | All actions |

**Action Complexity**: 1 LOW (presentations STUDENT+) | 2 MODERATE (streaming INTERN+) | 3 HIGH (state changes SUPERVISED+) | 4 CRITICAL (deletions AUTONOMOUS only)

> ⚠️ **Tier is routing, not security.** The maturity system uses past clean
> executions to decide what an agent is *normally* allowed to do. It does
> **not** bound blast radius — a prompt-injected agent at any tier uses the
> full scope that tier permits on the next call. Bounding blast radius
> requires a deterministic sandbox layer (filesystem scope, tool whitelist,
> egress allowlist, resource caps, tripwires) that runs alongside the tier.
> See `docs/security/TRUST_VS_SANDBOX.md` and
> `docs/security/PROMPT_INJECTION_DEFENSE_PLAN.md`.

---

## Core Components

1. **Agent Governance** (`agent_governance_service.py`, `agent_context_resolver.py`, `governance_cache.py`): Lifecycle/permissions/maturity, <1ms cached checks
2. **Streaming LLM** (`llm/byok_handler.py`, `atom_agent_endpoints.py`): Multi-provider (OpenAI, Anthropic, DeepSeek, Gemini), token streaming via WebSocket
3. **Canvas Presentation** (`tools/canvas_tool.py`, `api/canvas_routes.py`): Charts, markdown, forms with governance
4. **Real-Time Agent Guidance** (`tools/agent_guidance_canvas_tool.py`, `core/view_coordinator.py`, `core/error_guidance_engine.py`): Live tracking, multi-view orchestration, error resolution
5. **Python Package Support** (`core/package_governance_service.py`, `package_dependency_scanner.py`, `package_installer.py`): Per-skill Docker, pip-audit+Safety scanning, maturity gating
6. **Canvas AI Accessibility** (`frontend-nextjs/hooks/useCanvasState.ts`): Hidden a11y trees, `window.atom.canvas.getState()`, <10ms overhead
7. **LLM Canvas Summaries** (`core/llm/canvas_summary_service.py`): 50-100 word summaries for episodic memory
8. **Queen Agent** (`core/agents/queen_agent.py`, `intent_classifier.py`): Structured workflow automation with blueprints. WORKFLOW intents → Queen
9. **Unstructured Tasks** (`atom_meta_agent.py`, `fleet_admiral.py`): FleetAdmiral recruits specialists; TASK intents → Fleet. `spawn_agent()` for custom domains
10. **BYOK Cognitive Tiers** (`core/llm/cognitive_tier_system.py`, `cache_aware_router.py`, `escalation_manager.py`): 5-tier LLM routing, 90% cost reduction via caching
10b. **Learning LLM Router** (`core/learning_llm_router.py`, `core/llm/learning_router_registry.py`, `core/llm/routing/per_model_router.py`, `core/llm/response_quality.py`): per-model satisfaction predictors that re-rank BPC candidates from observed outcomes (truncation/schema/refusal) + user feedback. Process-wide singleton, DB-persisted feedback (`llm_routing_feedback`), live `/api/chat/feedback`, flag-gated (`ATOM_LEARNING_ROUTER`, default off). See `docs/architecture/LEARNING_LLM_ROUTER.md`
11. **Browser Automation** (`tools/browser_tool.py`, `api/browser_routes.py`): Playwright CDP, INTERN+ required
12. **Device Capabilities** (`tools/device_tool.py`, `api/device_capabilities.py`): Camera (INTERN+), Screen (SUPERVISED+), Location/Notifications (INTERN+), Cmd Exec (AUTONOMOUS only)
13. **Atom CLI Skills** (`tools/atom_cli_skill_wrapper.py`, `skills/atom-cli/`): 6 built-in skills, subprocess wrapper with 30s timeout
14. **Deep Linking** (`core/deeplinks.py`, `api/deeplinks.py`): `atom://agent/{id}`, `atom://workflow/{id}`, etc.
15. **Enhanced Feedback** (`api/feedback_enhanced.py`, `feedback_analytics.py`): Ratings, corrections, A/B testing
16. **Student Training** (`core/trigger_interceptor.py`, `student_training_service.py`): 4-tier routing, AI duration estimation, supervision, proposals
17. **Database Models** (`core/models.py`): AgentRegistry, AgentExecution, AgentFeedback, CanvasAudit, Episode* (episodic memory), CommunitySkill*, TrainingSession, etc.
18. **Episodic Memory** (`episode_segmentation_service.py`, `episode_retrieval_service.py`, `episode_lifecycle_service.py`, `agent_graduation_service.py`): Hybrid PG+LanceDB, 4 retrieval modes, graduation criteria (10/25/50 episodes)
19. **World Model & Business Facts** (`core/agent_world_model.py`, `api/admin/business_facts_routes.py`): Verified knowledge with citations, JIT verification, GraphRAG integration
20. **Monitoring** (`api/health_routes.py`, `core/monitoring.py`): `/health/live`, `/health/ready`, `/health/metrics` (Prometheus), structlog
21. **CI/CD** (`.github/workflows/deploy.yml`): test → build → staging → production (manual) → verify, auto-rollback
22. **Personal Edition** (`cli/daemon.py`, `docker-compose-personal.yml`): Local Docker + SQLite, daemon mode, FastEmbed embeddings
23. **Code Quality** (`mypy.ini`, `backend/docs/CODE_QUALITY_STANDARDS.md`): Type hints enforced via CI
24. **E2E Tests** (`backend/tests/e2e_ui/`): 486 test functions, API-first auth, worker isolation, Page Object Model
25. **Advanced Skills** (Phase 60): Marketplace, dynamic loading, DAG composition, supply-chain security
26. **GraphRAG & Entity Types** (`core/graphrag_engine.py`, `core/graphrag/multi_hop_expansion.py`, `core/graphrag/community_detection.py`, `entity_type_service.py`): PostgreSQL recursive CTEs, 6 canonical types, dynamic custom types; multi-hop scored expansion wired into `local_search` (SQLMultiHopExpander); Leiden community detection via `build_communities` (with Louvain fallback)
26c. **Zero-Trust Federation** (`api/routes/federation_routes.py`, `core/identity/did_manager.py`, `core/identity/verifiable_credentials.py`, `core/federation/zero_trust_security.py`): DIDs, verifiable credentials, zero-trust verification reachable at `/api/federation/{dids,credentials,verify,security/health}`. In-memory state (resets on restart); DB persistence is a follow-up
26d. **Enhanced Orchestration** (`core/orchestration/conductor_agent.py`, `core/orchestration/workflow_state_machine.py`, `core/orchestration/event_bus.py`): Conductor Agent (5 strategies: sequential/parallel/hybrid/adaptive/rollback_safe) at `POST /api/v1/workflows/conductor/execute`; EventBus lifecycle events (WORKFLOW_STARTED/STEP_STARTED/STEP_COMPLETED/STEP_FAILED/WORKFLOW_COMPLETED) published by every live workflow; state machine with validated transitions + rollback
27. **Frontend XSS Protection** (`frontend-nextjs/lib/sanitize.ts`): DOMPurify-based `sanitizeHtml()` + `renderMarkdownSafe()`, applied to all `dangerouslySetInnerHTML` sites
28. **Mobile Secure Storage** (`mobile/src/storage/secureTokenStorage.ts`): expo-secure-store wrapper for auth tokens (iOS Keychain / Android EncryptedSharedPreferences), transparent AsyncStorage migration
29. **Safe Expression Evaluator** (`core/safe_evaluator.py`): AST-validated `safe_eval()` replacing raw `eval()` in workflow conditions, event bus, and conductor
30. **CSV Injection Guard** (`accounting/export_service.py:_sanitize_csv_cell`): Prefixes `= + - @` cells with single quote in financial exports (CWE-1236)
31. **Workflow ReDoS Guard** (`core/workflow_parameter_validator.py`): `MAX_REGEX_LENGTH=200` + `_has_redos_risk()` heuristic on user-supplied regex patterns
32. **Ollama Local LLM** (`core/llm/byok_handler.py`, `core/byok_endpoints.py`): First-class provider for fully local inference via Ollama's OpenAI-compatible API (`OLLAMA_BASE_URL`); no API key required, registered in `PROVIDER_TIERS["budget"]` with zero cost
33. **Per-Turn Fact Extraction** (`core/turn_fact_extractor.py`, `core/turn_fact_queue.py`, `core/turn_fact_vector_store.py`, `core/turn_fact_categories.py`): Hermes-style memory-provider layer. Two entrypoints — `extract_from_turn()` (`sync_turn` hook, fires fire-and-forget after each ReAct step) and `extract_from_prompt_before_truncation()` (`on_pre_compress` hook, drained by `ExtractionQueue` worker). Extracts Mem0's 5 durable-fact categories (exact_value, hard_constraint, decision_reason, cross_task_dep, implicit_pref) using `model="fast"` + 2s timeout. Two-tier recall: Tier-1 pure-SQL `DURABLE FACTS` prompt block (sub-ms), Tier-2 LanceDB semantic `prefetch_relevant_facts()` (opt-in). SQL row is source of truth; LanceDB write is best-effort. Maturity-gated (STUDENT agents read-only). Never raises, never silently drops. See `docs/architecture/CONTEXT_MEMORY.md`
34. **Agent Memory Tools + Gap-Analysis Layer** (`tools/memory_tool.py`, `core/turn_fact_extractor.py`, `core/llm/byok_handler.py`): (a) `memory_remember` (INTERN+, complexity 2) / `memory_forget` (SUPERVISED+, complexity 3) — agent-callable tools for explicit persist/invalidate; deletion safety refuses blank targets. (b) Circuit breaker (`_CircuitBreaker`: 5 failures → 120s cooldown → half-open probe → close-on-success) prevents extraction storms during provider outages. (c) FTS5 lexical search (`search_reasoning_steps_lexical()` + migration `20260624_reasoning_fts`) — exact-match fallback for error strings/IDs. (d) `on_session_end` extraction hook (final pass over turn digest). (e) Context compression — `truncate_to_context` boundary protection (head+tail preserved, middle elided) + `sanitize_tool_pairs()` (stub injection prevents OpenAI 400). No LLM-summary phase (Hermes' own has 3 documented bugs). See `docs/architecture/HERMES_COMPARISON.md`
35. **Outcome Verification + Episodic Prefilter** (`core/tool_outcome_verifier.py`, `core/capability_graduation_service.py`, `core/episode_retrieval_service.py`, `core/episode_segmentation_service.py`): Two fixes for silent no-op propagation + cosine's inability to separate pass/fail snapshots. (a) Tri-state `verified` flag (`verified` | `unverified` | `failed_verification`) parsed from tool returns via `parse_tool_outcome()` — persisted on `AgentReasoningStep.verified` + `verification_evidence`. `CapabilityGraduationService.record_usage` gates on `verified='verified'` only; unverified successes still count in denominator (lower success ratio, can't inflate). Backward-compatible — plain-string returns default to `unverified`. (b) Episodic outcome prefilter — `EpisodeSegmentationService._derive_outcome()` computes success/failure/partial; stored in LanceDB metadata; `EpisodeRetrievalService.retrieve_semantic(outcome=...)` and `retrieve_failed_similar()` apply it as a native `WHERE outcome='failure'` prefilter BEFORE vector search (zero added latency). Migration `20260624_reasoning_verified` adds the `verified` column. See `docs/architecture/CONTEXT_MEMORY.md` § Reddit-Critique Follow-On
36. **Pre-Action Match-Confidence Layer** (`core/selector_confidence_service.py`, `core/llm/match_confidence_tiebreaker.py`, `tools/browser_tool.py`, `core/proposal_service.py`): Mirror of #35's post-action `VerifiedOutcome` tri-state, but pre-action. `MatchLevel ∈ {high, partial, ambiguous}` expresses selector-resolution certainty BEFORE `browser_click`/`browser_fill_form` runs. (a) Deterministic scorer — `max(0.0, 1.0 - 0.3*(N-1) - 0.15*text_only - 0.10*late)`; thresholds `MATCH_CONFIDENCE_HIGH_THRESHOLD=0.85`, `PARTIAL=0.50` (env-overridable). (b) LLM tiebreaker (`match_confidence_tiebreaker.py`) — budget-tier call with 2s timeout, circuit breaker (5 failures → 120s cooldown), OrderedDict result cache (256 entries, 10min TTL) keyed on hash(selectors + URL hostname). (c) Locator migration — `browser_tool.py` moved from legacy `query_selector*` to Playwright `page.locator()` strict mode; `match_confidence` JSON in every return dict (LLM-visible via `byok_handler` stringification, unlike DB-only `verified`). 0 matches return `ambiguous` deterministically (no 5s timeout burn); strict-mode violations caught and surfaced as `ambiguous`. (d) BrowserAudit writers — closes long-standing gap (model existed at `models.py:3454` but had no writers); `AuditService.create_browser_audit()` called at start (started) and end (success/failed/gated) of each action. (e) AUTONOMOUS override — partial/ambiguous matches route through `ProposalService.create_action_proposal` for ALL tiers including AUTONOMOUS (whose tier is routed by history not current-call certainty). `match_confidence_override=True` flag prevents re-gating loop on post-approval execution. (f) Form semantics — `browser_fill_form` does two-pass: resolve all fields, gate on worst-case BEFORE any fill (transactional integrity — partial fills leave page inconsistent). (g) `extract_text` exception — read-only, annotates but NEVER gates. Per-agent opt-out via `AgentRegistry.match_confidence_gating_enabled` (migration `20260628_add_match_confidence_gating_flag`). Shadow mode by default (`MATCH_CONFIDENCE_FORCE_PROPOSAL=false` — computation + audit always on, gating off). Kill switch: `SELECTOR_CONFIDENCE_ENABLED=false BROWSER_LOCATOR_API_ENABLED=false`. Frontend reviewer UI at `components/canvas/MatchConfidenceReviewer.tsx`. See `docs/architecture/MATCH_CONFIDENCE.md`
37. **Self-Consistency Voter + Shadow Audit** (`core/llm/self_consistency_voter.py`, `core/hallucination_config.py`, `core/llm_service.py`, `core/models.py:SelfConsistencyVote`): Parallel concept to #36 — where match-confidence answers "is the selector resolvable within one LLM call?", this layer answers "do N LLM calls agree on the plan?" via the Wang et al. 2022 self-consistency pattern. Two parts landed separately: (a) **Base port** (PR #548) — `SelfConsistencyVoter.vote()` returns the bare modal plan; cascade routing wired into `BYOKHandler.generate_structured_response` (Workstream B); AST-enforced import firebreak (test C1) keeps the voter from importing the executor. (b) **Shadow + audit extensions** (Round 42) — `VoteResult` dataclass with tri-state `level ∈ {high, partial, ambiguous}` mirroring `MatchConfidence`; `vote_with_consensus()` returns winner + agreement metadata; `SelfConsistencyVote` audit model + migration `20260629_add_self_consistency_votes` (guarded per SQLite hybrid-DB pattern); `LLMService.generate_structured` writes an audit row on every vote (shadow mode default — compute + audit always on, gating off); `generate_structured_with_consensus()` returns `(winner, VoteResult)` for callers that gate. Force-proposal gating (route `requires_review` outcomes through `ProposalService`) is the **caller's** responsibility, mirroring #36's `browser_tool._maybe_gate_with_proposal`. Tri-state thresholds `ATOM_SELF_CONSISTENCY_HIGH_THRESHOLD=0.85`, `PARTIAL=0.50` are env-overridable, identical knobs to #36. Per-sample failure isolation. Kill switch: `ATOM_SELF_CONSISTENCY=false`. 16 tests (C1-C16) green; match-confidence regression unaffected. See `docs/architecture/SELF_CONSISTENCY_VOTER.md`. Verified graduation gate (Workstream A) intentionally omitted in Personal edition (relies on `AgentCapabilityRegistry` which is SaaS-only).
38. **Execution Sandbox Layer** (`core/sandbox_policy.py`, `core/sandbox_config.py`, `core/sandbox_audit.py`, `core/sandbox_fs.py`, `core/sandbox_caps.py`, `core/sandbox_tripwire.py`, `core/sandbox_killrun.py`, `core/sandbox_egress_proxy.py`, `core/sandbox_runtime/`, `core/provenance.py`, `core/llm/action_judge.py`, `core/models.py:RunSandbox+SandboxViolation`): The deterministic blast-radius layer that §"Tier is routing, not security" calls for. Closes the gap documented in `docs/security/TRUST_VS_SANDBOX.md` and `docs/security/PROMPT_INJECTION_DEFENSE_PLAN.md`. Five phases (Rounds 43-47), each independently shippable and landed in shadow mode. **Phase A** (Round 43) — `SandboxPolicy` frozen dataclass + `PolicyIssuer` with tier-floor mapping (STUDENT read-only → AUTONOMOUS `*`); `RunSandbox` + `SandboxViolation` audit tables; migration `20260630_add_sandbox_tables` (chains on Round 42, guarded per SQLite hybrid-DB pattern); hooks in `mcp_service.execute_tool` and `atom_meta_agent._execute_tool_with_governance`. **Phase B** (Round 44) — `sandbox_fs.py` enforces `fs_roots`/`fs_write_roots` on every FS-touching tool; macOS-aware path normalization (checks both resolved `/private/etc` AND requested `/etc`); tripwires for `/proc/`, `/sys/`, `/etc/`, `~/.ssh/`, `~/.aws/`, `~/.env*`; RESTRICTED recovery via `rewrite_path_to_sandbox`. **Phase C** (Round 45) — 21 tripwire patterns across 6 categories (CREDENTIAL/DESTRUCTIVE/PRIVILEGE/CRON/ADMIN/REVERSE_SHELL+EXFIL); per-run resource caps (`max_tool_calls`, `max_exec_seconds`, `max_bytes_written`, `max_cost_usd`); KillRun state machine (`KillRunRegistry` + `KillRunAborted` propagation); `agent_governance_service.record_outcome` increments counters. **Phase D** (Round 46) — `SandboxRuntime` protocol unifies three existing Docker-based sandboxes; three backends (`DockerRuntime` default, `FirecrackerRuntime` self-hosted microVMs, `E2BRuntime` managed); HTTP CONNECT egress proxy with dual-proxy split per [INNOQ pattern](https://www.innoq.com/en/blog/2026/03/dev-sandbox-network/) — `LlmProxy` (LLM hosts only) vs `ToolProxy` (everything else); curated baseline (Anthropic/OpenAI/Gemini + pypi + GitHub). **Phase E** (Round 47) — `provenance.py` tags every context-window chunk by trust level (SYSTEM/USER trusted > MEMORY semi-trusted > TOOL_OUTPUT/FILE/FEDERATION/RETRIEVED untrusted); untrusted chunks spotlighted via `<provenance type="X" source="Y">...</provenance>` delimiters; `is_tool_invocation_from_trusted(text, offset)` lets the agent loop refuse to parse tool calls from untrusted chunks (closes indirect-prompt-injection gap); `ActionJudge` LLM-as-judge with tri-state verdict (proceed/escalate/block), budget-tier 2s timeout, `_CircuitBreaker` (5 failures → 120s cooldown→half-open→close-on-success), OrderedDict LRU cache (256 entries, 10min TTL), fail-open semantics. Kill switches per phase: `ATOM_SANDBOX_ENABLED` (master), `ATOM_SANDBOX_FS_ENABLED`, `ATOM_SANDBOX_TRIPWIRES_ENABLED`, `ATOM_SANDBOX_CAPS_ENABLED`, `ATOM_SANDBOX_RUNTIME=docker|firecracker|e2b`, `ATOM_SANDBOX_EGRESS_ENABLED`, `ATOM_SANDBOX_PROVENANCE_ENABLED`, `ATOM_SANDBOX_JUDGE_ENABLED`. Master shadow switch: `ATOM_SANDBOX_FORCE_ENFORCE=false` (compute + audit always on, enforcement off; KillRun only fires when both `TRIPWIRES_ENABLED=true` AND `FORCE_ENFORCE=true`). 166 tests (S1-S17 + B1-B15 + C1-C25 + D1-D20 + E1-E22) green across 5 files in `tests/unit/core/test_sandbox_*.py`; Phase A-E regression suites independent. See `docs/architecture/SANDBOX_LAYER.md`.
39. **Office Automation & Canvas Co-Editing** (`core/office_service.py`, `core/workbook_runtime.py`, `core/office_sync_service.py`, `api/office_routes.py`, `tools/office_tool.py`, `CanvasHost.tsx`): Direct python-based manipulation (read/write/render) of Word (.docx), Excel (.xlsx), and PowerPoint (.pptx) documents. Excel runs through `core/workbook_runtime.py` — a formula-evaluating runtime (LibreOffice headless primary → `formulas` library → openpyxl cached-values fallback) so writes return computed values, structural ops maintain references, and HTML render includes conditional formatting/charts. Incorporates bi-directional co-editing and real-time synchronization between the filesystem documents and the editable Canvas UI panel in the chat window. See `docs/architecture/WORKBOOK_RUNTIME.md`

---

## Recent Bug Hunt History (TDD)

All fixes use Red-Green-Refactor: failing test first, minimal fix, regression tests committed. Test files: `tests/test_roundN_fixes.py`, `tests/test_roundN_security.py`, `tests/test_security_bug_hunt.py`, `tests/test_auth_fixes.py`, etc.

### Rounds 18-40 — Full-Codebase Security Sweep (June 23, 2026) ✨

**~1,100 bugs fixed across 150+ files. 199 regression tests (all green).**

#### Bulk Cleanup Passes
- **str(e) leak sweep**: 992 `str(e)` leaks in `HTTPException detail`/`internal_error` across 133 backend files → generic `"Internal error"`. Logger calls retain `{e}` for server-side debugging only.
- **Auth sweep**: ~250 previously-unauthenticated API routes hardened with `Depends(get_current_user)` across 40+ modules.
- **Naive datetime sweep**: 12 remaining `datetime.utcnow` defaults in `models.py` → timezone-aware `datetime.now(timezone.utc)` (PostgreSQL TypeError fix; Round 13 only fixed 5).

#### Round 18 — Integrations (SSRF, OAuth, Webhooks)
9 bugs: `channel_routes` zero auth on 7 endpoints (IDOR) + broken `Channel`/`get_db` imports; `shopify_webhooks` signature header accepted but never verified; `atom_communication_memory_webhooks` 6 hardcoded webhook secrets + fail-open on missing signature; `ingestion_webhooks` fail-open on missing `slack_signing_secret` + `tenant_id` from query params (cross-tenant injection); `github_routes` 9 `str(e)` leaks; `admin_bootstrap` plaintext password logged → 0600 file; `auth_endpoints` reset link logged. 16 tests.

#### Round 19 — Workflow Engine (Auth + RCE + ReDoS)
6 bug classes: `advanced_workflow_endpoints` 17 routes zero auth + 17 `str(e)` leaks; `workflow_debugging_advanced` 5 routes zero auth; `workflow_analytics_routes` 3 routes zero auth; `workflow_template_routes` IDOR (get/update/instantiate); `scripts/workflow_engine.py` raw `eval(condition, ...)` → `safe_eval` (CWE-94 RCE); `workflow_parameter_validator` ReDoS via user regex (`MAX_REGEX_LENGTH=200` + nested-quantifier heuristic). 21 tests.

#### Round 20 — Agent Fleet Authorization
4 bugs: `maturity_routes` `user_id` from `Query(...)` on 4 approval endpoints (privilege escalation) → `Depends(get_current_user)`; `supervision_websocket` no auth (token check via `websocket.query_params`); `background_agent_routes.list_background_tasks` no auth; `fault_tolerance_service.py:104` broken SQL (`AgentRegistry.AgentRegistry.status`). 5 tests.

#### Round 21 — Data Ingestion & Compliance
4 bugs: `export_service` CSV injection (CWE-1236 — `=cmd|...` formula execution on accountant's workstation) → `_sanitize_csv_cell()`; `document_ingestion_routes` `/parse` and `/documents` no auth; `/parse` no file size limit (OOM DoS) → `MAX_UPLOAD_BYTES`; `data_ingestion_routes` `/usage` + `/sync-status` no auth. 7 tests.

#### Round 22 — Marketplace & Supply Chain
5 bugs: `package_routes` `/approve` + `/install` no auth (supply-chain takeover) + 14 `str(e)` leaks; `marketplace_routes` `/install` no auth; `skill_routes` `/import` + `/execute` + `/promote` no auth; `skill_dynamic_loader` accepts arbitrary `skill_path` (zip-slip/path-traversal → arbitrary `.py` execution) → `Path.resolve().relative_to(base)` containment. 8 tests.

#### Round 23 — Real-time Messaging
3 bug classes: `messaging_routes` 4 proactive-message routes no auth; `scheduled_messaging_routes.execute_due_messages` no auth; `notification_settings_routes` 3 routes no auth + `str(e)` leak; added missing `ProactiveMessageStatus` enum to `models.py` (broken import cascading through `proactive_messaging_service`). 10 tests.

#### Round 24 — Canvas Services
3 bug classes: `canvas_docs_routes` 4 routes no auth (document IDOR); `canvas_email_routes` 2 routes no auth; `canvas_terminal_routes` 2 routes no auth (terminal output injection). 8 tests.

#### Round 25 — LLM & Cognitive Systems
3 bug classes: `byok_routes` `store_api_key` + `get_ai_providers` — used `Depends(get_current_tenant)` but `get_current_tenant` is silently `None` (import fails), making the dependency a no-op; `llm_oauth_routes` `list_credentials` + `revoke_credential` + `refresh_credential` no auth; `cognitive_tier_routes` `update_budget` + `delete_preferences` no auth. 7 tests.

#### Round 26 — Memory / GraphRAG
4 bug classes: `memory_routes` `store_memory` + `delete_memory` no auth; `episode_routes` `promote_agent` (privilege escalation!) + 20 retrieval routes no auth; `graphrag_routes` `add_entity` + `ingest_document` no auth (graph poisoning); `entity_type_routes` `create_entity_type` no auth (schema injection). 7 tests.

#### Rounds 27-34 — Consolidated Finance/Analytics/Identity/Tools/Monitoring
13 handlers: `ai_accounting_routes.ingest_transaction`, `financial_ops_routes.add_invoice`, `financial_audit_routes` (6 handlers), `ab_testing.create_test`, `feedback_enhanced.submit_enhanced_feedback`, `feedback_analytics` (3 handlers), `oauth_routes.list_oauth_tokens` + `revoke_oauth_token`, `user_templates_endpoints` (10 handlers), `voice_routes.transcribe_audio`, `social_media_routes` (3 handlers), `monitoring_routes.create/delete_condition_monitor`. 13 tests.

#### Round 31 — Database Integrity
12 remaining naive `datetime.utcnow` column defaults in `models.py` → `lambda: datetime.now(timezone.utc)` (Round 13 fixed only 5). Plus naive `expires_at` comparison and `used_at` assignment. 2 tests.

#### Rounds 38-39 — Frontend & Mobile (Audit Reports)
- **Frontend** (`docs/FRONTEND_SECURITY_AUDIT.md`): 3 XSS sites via `dangerouslySetInnerHTML` + `marked.parse()` → **fixed with DOMPurify** (`lib/sanitize.ts`, `renderMarkdownSafe()`, 12 tests). Tokens in `localStorage` (documented for httpOnly cookie migration).
- **Mobile** (`docs/MOBILE_SECURITY_AUDIT.md`): auth tokens in unencrypted `AsyncStorage` (10 sites) → **fixed with `expo-secure-store`** (`storage/secureTokenStorage.ts`, transparent migration). No jailbreak detection (documented).

#### Round 40 — Final Regression
199 tests across rounds 4-31 + auth + security + TOCTOU — all green. Pushed to `rush86999/atom` main.

#### Round 41 — Pre-Action Match-Confidence Layer (June 28, 2026) ✨
**Feature, not bugfix.** Answers redditor critique that hidden a11y / canvas state expresses structure not uncertainty. New modules: `core/selector_confidence_service.py` (deterministic scorer + tri-state dataclasses mirroring post-action `VerifiedOutcome`), `core/llm/match_confidence_tiebreaker.py` (budget-tier LLM tiebreaker + circuit breaker + result cache). Modified: `tools/browser_tool.py` (Locator API migration, BrowserAudit writers, `_maybe_gate_with_proposal` for AUTONOMOUS override), `core/proposal_service.py` (reviewer-visible candidates block in description), frontend types + `MatchConfidenceReviewer.tsx`. 33 new tests across 4 backend test files + 7 jest tests, all green. Migration `20260628_add_match_confidence_gating_flag` adds per-agent opt-out column. Shadow mode default (`MATCH_CONFIDENCE_FORCE_PROPOSAL=false`). See `docs/architecture/MATCH_CONFIDENCE.md`.

#### Round 42 — Self-Consistency Shadow + Audit Extensions (June 29, 2026) ✨
**Feature, not bugfix.** Additive layer on PR #548's base port of the Wang et al. 2022 self-consistency voter. Where PR #548 shipped `vote()` (bare modal winner) + Workstream B cascade routing, this round adds the **shadow + audit + tri-state gating** surface that mirrors #36's match-confidence pattern. New modules: `SelfConsistencyVote` audit model (parallel to `BrowserAudit`), migration `20260629_add_self_consistency_votes` (guarded per SQLite hybrid-DB pattern). Modified: `core/llm/self_consistency_voter.py` (added `VoteResult` dataclass + `vote_with_consensus()` + `_level_from_agreement()` + `_hash_prompt()` — existing `vote()` left untouched to preserve C2-C4 contract), `core/hallucination_config.py` (added `is_self_consistency_force_proposal_enabled()` + `get_self_consistency_high_threshold()` + `get_self_consistency_partial_threshold()` — env-var only style matching PR #548's design philosophy), `core/llm_service.py` (`generate_structured` dispatch switched from `vote()` to `vote_with_consensus()` + audit-row write; new `generate_structured_with_consensus()` returns `(winner, VoteResult)` for callers that gate; new `_run_self_consistency_vote` + `_write_self_consistency_audit` helpers). 8 new tests (C9-C16) appended to `tests/unit/llm/test_self_consistency_voter.py` covering VoteResult shape, tri-state boundaries, frozen-dataclass invariant, prompt-hash determinism, force-proposal flag, additive resolver surface, model column regression. Shadow mode default (`ATOM_SELF_CONSISTENCY_FORCE_PROPOSAL=false`); audit row always written when voter runs. Force-proposal gating is the caller's responsibility via `generate_structured_with_consensus`. See `docs/architecture/SELF_CONSISTENCY_VOTER.md`.

#### Rounds 43-47 — Execution Sandbox Layer (June 30, 2026) ✨
**Feature, not bugfix.** Five-phase deterministic blast-radius layer that §"Tier is routing, not security" calls for. Closes the prompt-injection gap documented in `docs/security/TRUST_VS_SANDBOX.md` and `docs/security/PROMPT_INJECTION_DEFENSE_PLAN.md`. Each round is its own commit; each ships in shadow mode (compute + audit always on, enforcement off). See component #38 above and `docs/architecture/SANDBOX_LAYER.md` for full design.

- **Round 43 / Phase A** — Foundation. New: `core/sandbox_config.py` (env-var resolvers mirroring `hallucination_config.py`), `core/sandbox_policy.py` (`SandboxPolicy` frozen dataclass + `PolicyIssuer` with tier-floor mapping STUDENT→AUTONOMOUS), `core/sandbox_audit.py` (RunSandbox + SandboxViolation row writers), `core/models.py:RunSandbox+SandboxViolation`, migration `20260630_add_sandbox_tables` (chains on Round 42, guarded). Hooks: `mcp_service.execute_tool._sandbox_check` + `atom_meta_agent._meta_agent_sandbox_check` (shadow mode). Tri-state ALLOWED/RESTRICTED/BLOCKED mirrors MatchConfidence/VoteResult. 26 tests in `tests/unit/core/test_sandbox_policy.py`.
- **Round 44 / Phase B** — FS scope enforcement. New: `core/sandbox_fs.py` (path resolver + scope validator using `Path.resolve().relative_to()` containment). macOS-aware — checks both resolved (`/private/etc`) AND requested (`/etc`) paths so OS-level symlinks don't bypass tripwires. Tripwires for `/proc/`, `/sys/`, `/dev/`, `/etc/`, `/root/`, `/var/lib/docker/`, `~/.ssh/`, `~/.aws/`, `~/.config/`, `~/.env*`. RESTRICTED recovery via `rewrite_path_to_sandbox`. Modified: `mcp_service.py` + `atom_meta_agent.py` (Phase B hook after Phase A check, gated by `ATOM_SANDBOX_FS_ENABLED`), `tools/atom_cli_skill_wrapper.py` (accepts `cwd` kwarg for scoped tmpfs). 28 tests in `tests/unit/core/test_sandbox_fs.py`.
- **Round 45 / Phase C** — Tripwires + caps + KillRun. New: `core/sandbox_tripwire.py` (21 compiled regex patterns across 6 categories: CREDENTIAL/DESTRUCTIVE/PRIVILEGE/CRON/ADMIN/REVERSE_SHELL+EXFIL; false-positive avoidance via word boundaries + LLM-provider allowlist for curl/wget), `core/sandbox_caps.py` (per-run counters in `CounterRegistry` singleton — tool_calls, exec_seconds, bytes_written, cost_usd; check-before-increment), `core/sandbox_killrun.py` (`KillRunRegistry` + `KillRunAborted`; `trigger_killrun` marks `AgentExecution.status='killed_sandbox'`; `guard(run_id)` raises to abort in-flight execution). Modified: `mcp_service.py` + `atom_meta_agent.py` (Phase C hook; KillRun fires only when `FORCE_ENFORCE=true`; broad-except handlers re-raise `KillRunAborted` so kills propagate). 52 tests in `tests/unit/core/test_sandbox_caps_tripwires.py`.
- **Round 46 / Phase D** — Firecracker microVM + egress proxy. New: `core/sandbox_runtime/base.py` (`SandboxRuntime` async-first runtime_checkable Protocol, `SandboxExecResult` frozen dataclass, `get_runtime` factory, `NullRuntime` last-resort), `core/sandbox_runtime/docker_runner.py` (`DockerRuntime` adapter over existing `HazardSandbox` via `asyncio.to_thread`), `core/sandbox_runtime/firecracker_runner.py` (`FirecrackerRuntime` with lazy binary probe, per-VM config writer, asyncio subprocess invocation; only available on Linux+KVM), `core/sandbox_runtime/e2b_runner.py` (`E2BRuntime` managed microVMs via E2B SDK, lazy import, zero host deps), `core/sandbox_egress_proxy.py` (host normalization, allowlist matching with `*.wildcard` support, curated baseline = LLM providers + pypi + GitHub, `LlmProxy`/`ToolProxy` dual-proxy split per [INNOQ pattern](https://www.innoq.com/en/blog/2026/03/dev-sandbox-network/)). 31 tests in `tests/unit/core/test_sandbox_runtime_egress.py`.
- **Round 47 / Phase E** — Provenance + ActionJudge. New: `core/provenance.py` (`Provenance` enum with 7 trust levels forming strict lattice SYSTEM/USER trusted > MEMORY semi-trusted > TOOL_OUTPUT/FILE/FEDERATION/RETRIEVED untrusted; `ProvenanceTag` frozen dataclass with `render()` — trusted raw, untrusted delimited via `<provenance type="X" source="Y">...</provenance>` spotlighting; `ProvenanceTagger` factory; `parse_tags` + `is_tool_invocation_from_trusted(text, offset)` for agent loop to refuse tool calls from untrusted chunks), `core/llm/action_judge.py` (`ActionJudge` LLM-as-judge with tri-state verdict PROCEED/ESCALATE/BLOCK, `_CircuitBreaker` 5 failures→120s cooldown→half-open→close-on-success, `_ResultCache` OrderedDict LRU 256 entries 10min TTL, fail-open semantics on timeout/error/circuit-open; conservative ESCALATE default on malformed responses). 29 tests in `tests/unit/core/test_provenance_judge.py`. Canonical E21 integration test: indirect prompt injection via tool output correctly refused.

**Total: 166 new tests across 5 files in `tests/unit/core/test_sandbox_*.py`. All Phase A-E regression suites independent. Match-confidence (Round 41) + self-consistency voter (Round 42) + outcome-verification (#35) suites remain green — sandbox layer is additive.**

**Kill switches per phase** (all default off):
- `ATOM_SANDBOX_ENABLED=false` (Phase A master)
- `ATOM_SANDBOX_FS_ENABLED=false` (Phase B)
- `ATOM_SANDBOX_WHITELIST_ENABLED=false` + `ATOM_SANDBOX_TRIPWIRES_ENABLED=false` + `ATOM_SANDBOX_CAPS_ENABLED=false` (Phase C — each independently toggleable)
- `ATOM_SANDBOX_RUNTIME=docker` (Phase D — preserves pre-Round-46 behavior)
- `ATOM_SANDBOX_EGRESS_ENABLED=false` (Phase D)
- `ATOM_SANDBOX_PROVENANCE_ENABLED=false` + `ATOM_SANDBOX_JUDGE_ENABLED=false` (Phase E)
- `ATOM_SANDBOX_FORCE_ENFORCE=false` (master shadow switch — KillRun only fires when both `TRIPWIRES_ENABLED=true` AND `FORCE_ENFORCE=true`).

---

### Rounds 15+16 — Email Verification + 2FA (June 22, 2026) ✨
8 bugs: email enumeration in `/verify`, missing rate limits on verify/TOTP, weak entropy (`token_hex(3)`→`(4)`), `utcnow()` in comparisons, **hardcoded backup codes** (`UP-BACKUP-1234-5678` for all users), TOTP brute-force, `str(e)` leak. 7 tests.

### Round 14 — Auth Rate Limiting + Pydantic v2 (June 22, 2026) ✨
4 bugs: No rate limit on `/login`, `/register`, `/refresh` → `AuthRateLimiter` added (10/min, 3/5min, 30/min). Deprecated `@validator` → `@field_validator`. 5 tests.

### Round 13 — Timezone Bugs (June 22, 2026) ✨
9 bugs: `datetime.utcnow()` vs DB-aware datetimes (TypeError on Postgres) in `user_management_routes.py`, `github_routes.py`, `notion_service.py`, and 5 naive defaults in `models.py`. 3 tests.

### Round 12 — Test Infra + Security Headers (June 22, 2026) ✨
5 bugs: Unregistered `timeout` pytest marker (INTERNALERROR), langchain import breaking collection, security headers skipped on `/api/`, `SecurityHeadersMiddleware` never registered, `/docs` exposed in prod.

### Round 11 — Auth + Race Conditions (June 22, 2026) ✨
6 bugs: Refresh token reuse (7-day stolen tokens), `print()` debug leaks, `decide_hitl_action` double-spend (added `with_for_update`), `register_user` TOCTOU, `run_agent` TOCTOU, header logging. 4 tests.

### Rounds 9+10 — Deserialization + Secrets + eval (June 22, 2026) ✨
5 bugs: Hardcoded admin password `securePass123`, `webhook_security.py` fallback to `atom-secret-313`, **raw `eval()` in `event_bus.py` and `conductor_agent.py`** (CWE-94, bypassable sandbox) → `safe_evaluator.safe_eval`. 7 tests.

### Rounds 7+8 — Injection + IDOR + Broken Endpoints (June 22, 2026) ✨
11 bugs: Path traversal in `business_facts` upload, SQL interpolation in 3 generators, IDOR in `get_recording`, non-existent methods called (`promote_to_autonomous`, `get_playback_data`), missing `os` import (NameError), missing `await` on async, wrong params. 11 tests.

### Rounds 5+6 — BYOK + Router Audit (June 22, 2026) ✨
8 bugs: `require_admin` returning None (unauth admin), race in `get_byok_manager()`, 8 `str(e)` leaks, `BYOKHandler(self.db)` wrong arg, `LLMService(tenant_id=workspace_id)` mislabel, **15 endpoints in `workflow_debugging.py` with zero auth**, `shell_routes.py` `/sessions` no auth + leaks all users, `str(e)` leak. 12 tests.

### Security Sweep (June 21, 2026) ✨
11 bugs: Unauth WebSocket leaks, SQL injection in `episode_retrieval_service`, unauth `/api/shell/execute`, unauth `/api/local-agent/execute`, canvas/agent_status missing auth + impersonation, session ownership 200 vs 403, 12+ `str(e)` leaks, `browser_screenshot` path traversal, migration SQL interpolation. 26 tests.

### Auth Launch Hardening (June 21, 2026) ✨
10 bugs: Missing `UserStatus` import (SAML failures), JWT hard-required `sub`, **`X-User-ID` header trust = full auth bypass**, refresh as query param, `UserCredentials` dict subscript, DB session leaks in `agent_world_model.py`, singleton RSA I/O at import, singleton thread locks, bcrypt 71-byte truncation inconsistency. 29 tests.

### Earlier ✨
- **BYOK v6.0 Migration**: All LLM traffic via `LLMService`, health router mounted, GraphRAG regex fixed, `openie_schema_discovery.py` 100% coverage
- **Auto-Dev & Federation** (Apr 2026): Memento-Skills, AlphaEvolver, X-Federation-Key
- **Queen Agent & Marketplace** (Apr 2026): atomagentos.com
- **Phase 234 E2E** (Mar 2026): 486 functions, API-first auth
- **Phase 68 Cognitive Tiers** (Feb 2026): 5-tier routing, 100+ tests
- **Phase 35 Python Packages** (Feb 2026): Per-skill Docker, 117 tests

---

## Development Guidelines

### Feature Flags
```python
FEATURE_ENABLED = os.getenv("MY_FEATURE_ENABLED", "true").lower() == "true"
EMERGENCY_BYPASS = os.getenv("EMERGENCY_BYPASS", "false").lower() == "true"
```

### Database Session Patterns
```python
# Service layer (ALWAYS use context manager to avoid leaks)
with get_db_session() as db:
    agent = db.query(Agent).filter(Agent.id == agent_id).first()

# API routes (dependency injection)
@app.get("/agents/{agent_id}")
def get_agent(agent_id: str, db: Session = Depends(get_db)):
    return db.query(Agent).filter(Agent.id == agent_id).first()
```

### Error Handling (NEVER leak `str(e)` to clients)
```python
try:
    with SessionLocal() as db:
        # operation
        db.commit()
except Exception as e:
    logger.error(f"Operation failed: {e}")
    raise api_error(ErrorCode.DATABASE_ERROR, "Database operation failed")
```

### API Response Standards
```python
{"success": True, "data": {...}, "message": "...", "timestamp": "2026-02-06T10:30:00Z"}
{"success": False, "error_code": "AGENT_NOT_FOUND", "message": "...", "details": {...}}
```

---

## Coding Standards

### Python
- 3.11+, PEP 8, PascalCase classes / snake_case functions / UPPER_SNAKE constants
- Type hints required (MyPy enforced in CI), Google-style docstrings
- See `backend/docs/CODE_QUALITY_STANDARDS.md`

### Import Order
1. Standard library 2. Third-party 3. Local imports

### Performance Patterns
- `GovernanceCache` for hot data (<1ms lookups)
- Async/await for I/O, connection pooling, stream LLM via WebSocket

---

## Testing

### TDD for Bug Fixes (MANDATORY)
See `docs/testing/BUG_FIX_PROCESS.md`. **Never fix a bug without a failing test first.**

**Red-Green-Refactor:**
1. **Red**: Write failing test reproducing the bug
2. **Green**: Minimal fix to pass
3. **Refactor**: Improve while tests pass

```python
# RED
def test_agent_maturity_blocks_demotion():
    service = AgentGovernanceService(db)
    with pytest.raises(ValueError):
        service.update_maturity("test", AgentMaturity.STUDENT)

# GREEN then REFACTOR: add _is_demotion() helper
```

**Frontend (Jest/RTL)**: same pattern — failing assertion → add prop/mock → extract helper.

**Common patterns**: input validation (null/empty/negative checks), edge cases, state mutation (copy first), integration issues, timeouts (`waitFor`, fake timers).

### Unit & Integration
```bash
PYTHONPATH=/Users/rushiparikh/projects/atom/backend pytest tests/ -v
pytest tests/test_governance_streaming.py -v
pytest tests/ --cov=core --cov-report=html
```

### E2E UI (Phase 234)
```bash
cd backend/tests/e2e_ui && ./scripts/start-e2e-env.sh
pytest backend/tests/e2e_ui/ -v -n 4                    # 4 parallel workers
pytest backend/tests/e2e_ui/tests/test_auth_login.py -v # Specific file
pytest backend/tests/e2e_ui/ -v --alluredir=allure-results && allure serve allure-results
```

**Coverage** (486 tests, 68 files): AUTH-01..07 (login, JWT, session, refresh, mobile, API-first), AGNT-01..08 (creation, streaming, reconnection, concurrent, governance, lifecycle).

Test files: `backend/tests/e2e_ui/conftest.py`, `fixtures/auth_fixtures.py` (API-first, 10-100x faster), `pages/page_objects.py` (LoginPage, DashboardPage, ChatPage).

---

## Important File Locations

**Core**: `agent_governance_service.py`, `agent_context_resolver.py`, `governance_cache.py`, `llm/byok_handler.py`, `models.py`, `agent_world_model.py`, `graphrag_engine.py`, `entity_type_service.py`, `model_factory.py`, `turn_fact_extractor.py` (+ `turn_fact_queue.py`, `turn_fact_vector_store.py`, `turn_fact_categories.py` — see `docs/architecture/CONTEXT_MEMORY.md`), `selector_confidence_service.py` (pre-action scorer, see `docs/architecture/MATCH_CONFIDENCE.md`), `llm/match_confidence_tiebreaker.py` (LLM tiebreaker + circuit breaker), `hallucination_config.py` (Phase 2 hallucination-mitigation flag resolvers — Workstreams B/C), `llm/self_consistency_voter.py` (Workstream C — N-sample majority vote + VoteResult tri-state for shadow/audit, see `docs/architecture/SELF_CONSISTENCY_VOTER.md`)

**Memory Tools**: `tools/memory_tool.py` (`memory_remember` / `memory_forget` — agent-callable), `core/turn_fact_extractor.py` (extraction, circuit breaker, FTS5 search, recall). Comparison: `docs/architecture/HERMES_COMPARISON.md`

**API**: `atom_agent_endpoints.py`, `api/canvas_routes.py`, `api/browser_routes.py`, `api/device_capabilities.py`, `api/deeplinks.py`, `api/admin/business_facts_routes.py`, `api/entity_type_routes.py`, `api/graphrag_routes.py`, `api/health_routes.py`

**Frontend**: `frontend-nextjs/hooks/useCanvasState.ts`, `components/canvas/types/index.ts`

**Tools**: `tools/canvas_tool.py`, `tools/browser_tool.py`, `tools/device_tool.py`, `tools/atom_cli_skill_wrapper.py`

**Skills**: `skills/atom-cli/` (6 SKILL.md), `core/skill_adapter.py`

**E2E**: `backend/tests/e2e_ui/README.md`, `conftest.py`, `fixtures/auth_fixtures.py`, `pages/page_objects.py`

**BYOK**: `docs/architecture/BYOK_V6_MIGRATION_GUIDE.md`, `.planning/REQUIREMENTS-v6.0-BYOK.md`, `core/llm/llm_service.py`

**Security**: `core/safe_evaluator.py` (AST eval), `core/auth.py` (`get_current_user`), `frontend-nextjs/lib/sanitize.ts` (DOMPurify XSS guard), `mobile/src/storage/secureTokenStorage.ts` (SecureStore), `accounting/export_service.py` (`_sanitize_csv_cell`), `core/sandbox_policy.py` + `core/sandbox_fs.py` + `core/sandbox_tripwire.py` + `core/sandbox_killrun.py` + `core/sandbox_egress_proxy.py` + `core/provenance.py` + `core/llm/action_judge.py` (Execution Sandbox Layer — Rounds 43-47, see `docs/architecture/SANDBOX_LAYER.md`)

**Bug Hunt Tests**: `tests/test_round{4..17}_fixes.py`, `tests/test_round{18..31}_*.py`, `tests/test_rounds27_30_consolidated.py`, `tests/test_auth_fixes.py`, `tests/test_security_bug_hunt.py`, `tests/test_toctou_fixes.py`, `tests/test_turn_fact_extraction.py`, `tests/test_turn_fact_queue.py`, `tests/test_outcome_verification.py`, `tests/test_selector_confidence_service.py`, `tests/test_match_confidence_tiebreaker.py`, `tests/test_match_confidence_proposal_gating.py`, `tests/unit/llm/test_self_consistency_voter.py`, `tests/unit/llm/test_hallucination_config.py`, `tests/unit/core/test_sandbox_policy.py` (Phase A), `tests/unit/core/test_sandbox_fs.py` (Phase B), `tests/unit/core/test_sandbox_caps_tripwires.py` (Phase C), `tests/unit/core/test_sandbox_runtime_egress.py` (Phase D), `tests/unit/core/test_provenance_judge.py` (Phase E), `frontend-nextjs/lib/__tests__/sanitize.test.ts`, `frontend-nextjs/lib/__tests__/matchConfidence.test.ts`

**Audit Docs**: `docs/FRONTEND_SECURITY_AUDIT.md`, `docs/MOBILE_SECURITY_AUDIT.md`

---

## Environment Variables

```bash
# Database
DATABASE_URL=sqlite:///./atom_dev.db            # Personal (default)
# DATABASE_URL=postgresql://user:pass@host/atom # Production

# Governance
STREAMING_GOVERNANCE_ENABLED=true
CANVAS_GOVERNANCE_ENABLED=true
FORM_GOVERNANCE_ENABLED=true
BROWSER_GOVERNANCE_ENABLED=true
EMERGENCY_GOVERNANCE_BYPASS=false

BROWSER_HEADLESS=true
OPENAI_API_KEY=sk-...
ANTHROPIC_API_KEY=sk-...
MINIMAX_API_KEY=...        # Optional: M2.7 204K context

# Local LLM (Ollama) — free, on-device inference. No API key required.
OLLAMA_BASE_URL=http://localhost:11434/v1
OLLAMA_MODEL=llama3:8b
PORT=8000
LOG_LEVEL=INFO

# Monitoring
PROMETHEUS_ENABLED=true
STRUCTLOG_LEVEL=INFO
HEALTH_CHECK_DISK_THRESHOLD_GB=1

# Personal Edition
ATOM_HOST_MOUNT_ENABLED=false    # AUTONOMOUS gate
EMBEDDING_PROVIDER=fastembed
FASTEMBED_MODEL=BAAI/bge-small-en-v1.5
LANCEDB_PATH=./data/lancedb
LANCEDB_CLOUD_ENABLED=false              # Gate S3/R2 remote paths (Personal = embedded; SaaS = true)

# Per-Turn Fact Extraction (Hermes-style memory layer; see docs/architecture/CONTEXT_MEMORY.md)
TURN_FACT_EXTRACTION_ENABLED=false       # Per-turn LLM extraction (costs 1 fast-model call/turn)
TURN_FACT_PRE_COMPRESS_ENABLED=true      # Pre-truncation queue (free, additive — default ON)
TURN_FACT_VECTOR_RECALL_ENABLED=false    # LanceDB-backed semantic recall (adds embedding latency)
TURN_FACT_MAX_PER_TURN=5                 # Cap facts persisted per turn
TURN_FACT_EXTRACTION_SAMPLE_RATE=1.0     # Dial down in cost crunch (0.0=off, 1.0=always)
TURN_FACT_QUEUE_MAXSIZE=100              # ExtractionQueue capacity (overflow drops, never blocks)

# Hallucination Mitigation Phase 2 (PR #548 + Round 42)
# Workstream B — cascade routing (PR #548, fully wired)
ATOM_CASCADE_ROUTING=false                # Retry structured-gen on same-family frontier on validation failure
# Workstream C — self-consistency voter (PR #548 base + Round 42 shadow/audit)
ATOM_SELF_CONSISTENCY=false               # Master switch (lazy import only happens when True)
ATOM_SELF_CONSISTENCY_SAMPLES=3           # N samples per vote (Wang et al. sweet spot)
ATOM_SELF_CONSISTENCY_FORCE_PROPOSAL=false  # Shadow mode default — audit always, gating off (Round 42)
ATOM_SELF_CONSISTENCY_HIGH_THRESHOLD=0.85  # Tri-state high (mirrors MATCH_CONFIDENCE_HIGH_THRESHOLD)
ATOM_SELF_CONSISTENCY_PARTIAL_THRESHOLD=0.50  # Tri-state partial floor

# Execution Sandbox Layer (Rounds 43-47) — deterministic blast-radius layer
# See docs/architecture/SANDBOX_LAYER.md. All phases default OFF (shadow mode).
ATOM_SANDBOX_ENABLED=false                    # Master switch (Phase A+)
ATOM_SANDBOX_FORCE_ENFORCE=false              # Shadow mode default — audit always, enforcement off
ATOM_SANDBOX_POLICY_TENANT_OVERRIDE=false     # Allow tenant metadata_json to override policies
# Phase B — filesystem scope
ATOM_SANDBOX_FS_ENABLED=false
# Phase C — tripwires + caps + KillRun
ATOM_SANDBOX_WHITELIST_ENABLED=false
ATOM_SANDBOX_TRIPWIRES_ENABLED=false          # KillRun only fires when this AND FORCE_ENFORCE are both true
ATOM_SANDBOX_CAPS_ENABLED=false
ATOM_SANDBOX_MAX_TOOL_CALLS=200               # Per-run cumulative cap
ATOM_SANDBOX_MAX_EXEC_SECONDS=600             # Per-run wall-clock cap (10 min default)
ATOM_SANDBOX_MAX_BYTES_WRITTEN=104857600      # Per-run cumulative FS write cap (100 MiB default)
ATOM_SANDBOX_MAX_COST_USD=5.0                 # Per-run cumulative LLM spend cap
# Phase D — Firecracker microVM + egress proxy
ATOM_SANDBOX_RUNTIME=docker                   # docker | firecracker | e2b (default preserves pre-Round-46 behavior)
ATOM_SANDBOX_EGRESS_ENABLED=false
ATOM_SANDBOX_VM_MEM_MB=256                    # Per-microVM memory
ATOM_SANDBOX_VM_VCPUS=1                       # Per-microVM vCPU count
ATOM_SANDBOX_VM_BOOT_TIMEOUT_SECONDS=5        # MicroVM boot timeout
E2B_API_KEY=                                  # Required only when ATOM_SANDBOX_RUNTIME=e2b
# Phase E — provenance + ActionJudge
ATOM_SANDBOX_PROVENANCE_ENABLED=false
ATOM_SANDBOX_JUDGE_ENABLED=false
ATOM_SANDBOX_JUDGE_TIMEOUT_SECONDS=2.0        # Budget-tier LLM call timeout (fail-open)
ATOM_SANDBOX_JUDGE_CIRCUIT_THRESHOLD=5        # Failures before circuit opens
ATOM_SANDBOX_JUDGE_CIRCUIT_COOLDOWN_SECONDS=120

# Security (Rounds 18-40)
MAX_UPLOAD_BYTES=52428800              # Document upload size cap (50 MiB default)
ATOM_BOOTSTRAP_PASSWORD_FILE=          # Where generated admin password is written (0600)
SHOPIFY_WEBHOOK_SECRET=                # Shopify HMAC verification (fail-closed if missing)
ATOM_WHATSAPP_WEBHOOK_SECRET=          # Communication webhook secrets (env, never hardcode)
ATOM_SLACK_WEBHOOK_SECRET=
ATOM_DISCORD_WEBHOOK_SECRET=
ATOM_TELEGRAM_WEBHOOK_SECRET=
```

---

## Database Migrations

```bash
alembic revision -m "description"
alembic upgrade head
alembic downgrade -1
alembic current
alembic history
```

**SQLite compatibility (Personal Edition):** Migrations that change column types or add columns must use `op.batch_alter_table()` (SQLite has no native `ALTER COLUMN`) and guard with `_table_exists()` / `_column_exists()` so they no-op when the table is missing or the column already exists. The dev DB is a hybrid (schema advanced via `Base.metadata.create_all`, alembic bookkeeping lags), so unguarded migrations fail with "duplicate column" / "no such table". See `alembic/versions/20260624_add_turn_facts.py` for the canonical guarded pattern.

**Reconciling a hybrid DB:** if `alembic current` shows multiple divergent heads on a DB whose schema is already complete, stamp to the nearest mergepoint (`alembic stamp <merge_rev> --purge`) to collapse heads truthfully, then `alembic upgrade head` runs only the genuinely-pending migrations.

---

## Performance Targets

| Metric | Target | Current |
|--------|--------|---------|
| Cached governance check | <10ms | 0.027ms P99 |
| Agent resolution | <50ms | 0.084ms avg |
| Streaming overhead | <50ms | 1.06ms avg |
| Cache hit rate | >90% | 95% |
| Cache throughput | >5k ops/s | 616k ops/s |
| Browser session creation | <5s | ~1-2s avg |
| Health liveness | <10ms | 2ms P50, 10ms P99 |
| Health readiness | <100ms | 15ms P50, 40ms P99 |
| Metrics scrape | <50ms | 8ms P50, 25ms P99 |
| Vector embedding | <20ms | 10-20ms (FastEmbed) |

---

## Key Concepts

1. **Multi-Agent Architecture** - Specialized agents with maturity levels
2. **Governance First** - Every AI action attributable, governable, auditable
3. **Single-Tenant** - No workspace isolation, global dataset
4. **Graceful Degradation** - Log errors but allow requests if governance fails
5. **Performance** - Sub-ms cache
6. **Observability** - Health, metrics, structured logs
7. **E2E Excellence** - 486 functions, API-first auth, parallel
8. **Personal Edition** - Docker Compose local
9. **Type Safety** - MyPy in CI

---

## Quick Reference Commands

```bash
# Development (run from repo root — main.py uses backend.* imports)
cd /path/to/atom
PYTHONPATH=$PWD:$PWD/backend ./backend/venv/bin/python -m uvicorn main:app --reload --port 8000

# Auth (admin password auto-generated on first launch, written to
# backend/logs/bootstrap_admin_password.txt mode 0600 — or set ADMIN_PASSWORD)
cat backend/logs/bootstrap_admin_password.txt   # read the generated password
curl -X POST http://localhost:8000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"admin@example.com","password":"<from-file>"}'

# Daemon (Personal Edition)
atom-os daemon | status | stop | execute <command>

# Health
curl http://localhost:8000/health/live
curl http://localhost:8000/health/ready
curl http://localhost:8000/health/metrics

# Canvas State API (browser console)
window.atom.canvas.getState('canvas-id')
window.atom.canvas.getAllStates()

# Cognitive Tiers
python -c "from core.llm.cognitive_tier_system import CognitiveClassifier; print(CognitiveClassifier().classify('hello'))"
curl -X GET "/api/v1/cognitive-tier/compare-tiers"

# GraphRAG & Entity Types
python -c "from core.graphrag_engine import graphrag_engine; print(graphrag_engine.local_search('default', 'John Doe', depth=2))"
curl -X POST "/api/v1/graph/search/local" -d '{"query": "Project Alpha", "depth": 2}'
curl -X POST "/api/v1/entity-types" -d '{"slug":"invoice","display_name":"Invoice","json_schema":{...}}'

# Intent + Fleet Admiral
python -c "from core.intent_classifier import IntentClassifier; print(IntentClassifier().classify_intent('Research competitors'))"
python -c "from core.atom_meta_agent import AtomMetaAgent; print(AtomMetaAgent().spawn_agent('finance_analyst'))"
curl -X POST "/api/v1/agent/route" -d '{"request": "Analyze sales data"}'

# Playwright
playwright install chromium

# Database
alembic upgrade head | current | history

# Git
git status | add . | commit -m "feat: description" | push origin main

# Logs
tail -f logs/atom.log
grep "governance" logs/atom.log | tail -100

# E2E Tests
cd backend/tests/e2e_ui && ./scripts/start-e2e-env.sh
pytest backend/tests/e2e_ui/ -v -n 4
allure serve allure-results

# Personal Edition
docker-compose -f docker-compose-personal.yml up -d | logs -f | down
```

---

## Summary

Atom: AI-powered automation with multi-agent governance, episodic memory, real-time guidance, production monitoring. **Always consider agent attribution and governance** for any AI feature.

**Production-ready**: CI/CD, health checks, Prometheus, docs, type safety, 486 E2E tests. **Personal Edition**: Docker Compose local (see `docs/archive/legacy/PERSONAL_EDITION_GUIDE.md`).

*Full docs in `docs/`, `backend/docs/`, and test files.*
