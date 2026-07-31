# Atom - AI-Powered Business Automation Platform

> **Project Context**: Intelligent business automation/integration platform using AI agents to automate workflows, integrate services, and manage operations.

**Last Updated**: July 31, 2026

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

### Round 57 — Test-Infra: Stale `from main import app` Breaks Suite Collection (July 31, 2026) ✨
**Test-infra round.** `tests/property_tests/conftest.py:13` did `from main import app` — there is **no `main.py`** (the real app is `main_api_app.py`; the CLAUDE.md quick-reference is stale). Every consumer of its `db_session` fixture — `tests/security/`, `tests/scenarios/`, `tests/integration/websocket/`, `tests/integration/test_websocket_integration.py` — failed collection with `ModuleNotFoundError`, so whole suites never ran (flagged pre-existing since R44).

**Fix:** bulk-repaired **28 test files** (`sed` sweep + manual): `from main import app` → `from main_api_app import app` (including `import main as main_mod/module` forms), and `test_final_audit_fixes.py`'s `_startup_bootstrap` inspection → `lifespan` (where `create_all` actually lives). No source-code changes.

**Tests:** 3 new tests in `backend/tests/test_round57_property_conftest_repair.py` (conftest imports cleanly, security conftest chain resolves, property_tests/ collects). Previously-broken suites now collect and run (property_tests + security + websocket + regression: 116 passed, 27 failed, 25 errors — the failures/errors are newly-visible pre-existing test quality issues, e.g. MagicMock-await in websocket fixtures, unrunnable at baseline). All round suites (R14, R38, R49-R56, R57) run together: **99 passed, 0 failed** (the 28-failure scare in the first combined run traced to `test_auth_fixes.py`'s R43-documented mid-session `core.auth` reload — pre-existing isolation hazard, not caused by this round). Test-only changes — mypy N/A (tests excluded). `main_api_app` untouched.

### Round 56 — Password-Recovery Endpoints: Missing Rate Limits (July 31, 2026) ✨
**Bug hunt round.** `login`/`register`/`refresh` got `AuthRateLimiter` deps in R14 and verify/TOTP in R15/16 — but the three unauthenticated password-recovery endpoints had **no rate limiting at all**: `POST /api/auth/forgot-password` could be called unlimited times to **spam reset emails for any known address** (mailbox flooding + mailer DoS), and `/reset-password` + `/verify-token` were unthrottled token-guessing surfaces (256-bit `token_urlsafe(32)` tokens make brute force infeasible, but every other auth endpoint follows the per-IP throttle pattern).

**Fix:** three new `AuthRateLimiter` singletons + dependency functions in `core/auth_endpoints.py` — `_recovery_limiter` 5/5min on `/forgot-password`, `_verify_limiter` 10/5min on `/verify-token`, `_reset_limiter` 5/5min on `/reset-password` — wired into the endpoints as `_rl=Depends(...)`, mirroring `login_rate_limit`. Peer-IP keying (never spoofable) comes from the R44-hardened `AuthRateLimiter._client_ip`.

**Tests:** 5 new tests in `backend/tests/test_round56_password_recovery_rate_limit.py` (limit-then-429 for all three deps, per-IP isolation, endpoint-level 429 via HTTP after 5 requests). Zero regressions (comm-verified with `--continue-on-collection-errors`: baseline 36→34 failures — delta is exactly the R56 collection-error lines flipping green; `comm -13` empty = no new failures; the 17 `test_auth_routes_coverage.py` failures are pre-existing and identical in both runs — the file also carries the pre-existing `tests/property_tests/conftest.py` `from main import app` collection breakage noted in R44). mypy clean (0/0, identical). `main_api_app` imports clean. 5/5 round tests green.

### Round 55 — Unbounded Request Bodies: OOM DoS via Huge JSON Payloads (July 31, 2026) ✨
**Bug hunt round.** `InputValidationMiddleware` (registered on the real app) reads the **entire POST/PUT/PATCH body into memory with no size cap** — FastAPI/Starlette impose no default body limit, so every JSON-accepting endpoint was an OOM amplification point: a multi-GB JSON body was fully allocated (and regex-scanned) before any handler ran.

**Fix:** the middleware now stream-reads the body with a hard cap (`_read_body_with_limit` — drains the ASGI stream chunk-by-chunk and aborts as soon as the cap is exceeded, never allocating more than the cap) and returns **413** when exceeded. Cap: `MAX_BODY_BYTES` (env-overridable, **64 MiB default** — sized to cover the 50 MiB multipart uploads the R21/R50 caps allow). Handles the already-materialized case (upstream `request._body`) with a length check. Keeps the R52-era fail-closed scan behavior.

**Tests:** 4 new tests in `backend/tests/test_round55_body_size_limit.py` (oversized rejection with env cap + default cap, small-body regression, source guard asserting stream+cap). Zero regressions (comm-verified: 27→22 failures in affected suites — delta is exactly the 3 RED tests flipping green; `comm -13` empty = no new failures). mypy baseline identical (6 pre-existing errors, line shifts only). `main_api_app` imports clean. 4/4 round tests green.

### Round 54 — Workspace Routes: Identity Spoofing + Missing Ownership + str(e) (July 31, 2026) ✨
**Bug hunt round.** `api/workspace_routes.py` (mounted at `/api/v1/workspaces`) trusted client-supplied identity and skipped ownership checks on every endpoint:

**A. `POST /unified`** — `create_unified_workspace(user_id=request.user_id)` created workspaces **owned by any user_id the client supplied** (attribution spoofing). → now `user_id=current_user.id`; body field kept for backward compat but ignored.

**B. `GET /unified?user_id=X`** — list filtered by the client-supplied `user_id` → **cross-user workspace read** (names, platform configs, sync state). → always scoped to `current_user.id`.

**C. `GET /unified/{id}`, `POST /unified/{id}/platforms`, `POST /unified/{id}/sync`, `DELETE /unified/{id}`** — **zero ownership checks**: any user could read/modify/delete ANY user's workspace and — worst — `propagate_change` writes changes to **external connected platforms** (cross-user state corruption + external side effects). → new `_get_owned_workspace_or_error()` gate on all four (404 if missing, 403 if `workspace.user_id != current_user.id`).

**D. 5 `str(e)` leaks** in `details={"error": str(e)}` (R41 class) → generic; plus the same leak on `POST /api/ai/pricing/estimate` (`byok_routes` — `ApiResponse(message=str(e))`). Also added `except HTTPException: raise` so the ownership gates aren't swallowed into 500s (R42 lesson).

**Tests:** 7 new tests in `backend/tests/test_round54_workspace_identity.py` (token-identity assertion via captured kwargs, filter bind-param inspection, 403s for get/delete/sync on others' workspaces with service-not-called assertions, 2 secret-sentinel leak tests incl. HTTP `POST /api/ai/pricing/estimate`). Zero regressions (comm-verified: 140→126 failures in affected suites — delta is exactly the 7 RED tests flipping green; `comm -13` empty = no new failures; the 51+25 byok/workspace suite failures are pre-existing and identical in both runs). mypy baseline identical (25 pre-existing errors, line shifts only). `main_api_app` imports clean. 7/7 round tests green.

### Round 53 — Office Sync: Missing Path Containment — Arbitrary File Read/Overwrite (July 31, 2026) ✨
**Bug hunt round.** R52 fixed `office_service` `str(e)` leaks but exposed a deeper hole: `core/office_sync_service.py` (served by authenticated `POST /sync-update` + `/present` in `office_routes`) passed the **user-supplied `file_path` straight to the filesystem with no containment** — unlike every `OfficeService` entry point, which validates against `ATOM_OFFICE_DIR`:

**A. `sync_canvas_to_file()` docx branch** — `doc.save(file_path)` on an unvalidated path: any authenticated user could **overwrite any existing `.docx` the process can write** (arbitrary file modification).

**B. `broadcast_file_update()`** — rendered + read (and ingested to memory) any existing office file; the rendered HTML was pushed to the caller's own `canvas_id` WebSocket + `CanvasAudit` rows — **arbitrary file-read exfiltration** (read any existing `.docx`/`.xlsx`/`.pptx` on the host).

**C.** `sync_canvas_to_file()` also leaked `str(e)` in its failure dict (R52 class, missed because R52 swept `office_service` not `office_sync_service`).

**Fix:** validate `file_path` with the existing `office_service._validate_office_path()` at BOTH sync entry points (reject out-of-scope paths before any read/write); generic error string on the exception path. Excel-branch sync was already contained transitively via `write_cell` — now contained explicitly at the boundary.

**Tests:** 5 new tests in `backend/tests/test_round53_office_sync_path_containment.py` (victim-docx byte-equality after out-of-scope sync, xlsx rejection, broadcast not reading/ingesting/auditing out-of-scope files, secret-sentinel leak assertion, end-to-end HTTP `POST /sync-update` with byte-equality). Zero regressions (comm-verified: 10→2 failures in affected suites — delta is exactly the 4 RED tests flipping green; `comm -13` empty = no new failures; remaining 2 are pre-existing). mypy baseline identical (2 pre-existing errors, line shift only). `main_api_app` imports clean. 5/5 round tests green.

### Round 52 — Office Service str(e) Leaks + Dead Office Router (July 31, 2026) ✨
**Bug hunt round.** `core/office_service.py` returned raw exception strings in every failure dict, and `api/office_routes.py` (mounted via `safe_import_router`, 14 endpoints) forwarded those dicts verbatim into `HTTPException(detail=...)` — internal exception detail (filesystem paths, openpyxl/docx internals) reached clients on every office failure.

**A. str(e) sweep (`core/office_service.py`):** 9 `except Exception` sites (Excel read/write, Word read/modify, PPTX read/modify, 3 HTML-render paths) + `_validate_office_path` embedding `OSError` text (`Invalid file path: [Errno 13] ...`) → all now return operation-descriptive generic strings (`"Failed to read Excel range"`, etc.); logger retains `{e}`. Render sites previously had NO logger line — added.

**B. BONUS — dead office router (2 latent bugs):** the module was written against unimported names — `List` (used in `ExcelPivotTableRequest`, missing from the `typing` import) made the module raise `NameError` at import. `safe_import_router` swallows non-ImportError exceptions in dev (silently mounting an EMPTY router → all 14 office endpoints 404'd; the file's own comment claims the endpoints were auth-hardened but the router never loaded) and **raises in production (`ENVIRONMENT=production`) → app startup crash**. `uuid` was also missing (fires when `POST /present` runs). Both imports added; `office_routes.py` now mypy-clean (10 errors → 0 on that file).

**Tests:** 6 new tests in `backend/tests/test_round52_office_error_leaks.py` (secret-sentinel leak assertions for read_range/write_cell/read_document + end-to-end HTTP `GET /excel` with real service+route + module-import regression; pptx/mammoth tests skip when libs absent). Zero regressions (comm-verified: 12→4 failures in affected suites — delta is exactly the 5 RED tests + 3 pre-existing `test_office_service.py` tests flipping green; `comm -13` empty = no new failures; the 3 office tests also fail standalone at baseline — pre-existing `data_only` read-back flakiness). mypy improved 10→7 (fixed 3 `List` errors, zero new). `main_api_app` imports clean. 5/5 round tests green.

### Round 51 — CSV Injection in Feedback + GL Exports (CWE-1236) (July 31, 2026) ✨
**Bug hunt round.** R21's `_sanitize_csv_cell` fixed `accounting/export_service.py` but two mounted export paths still wrote user-controlled free text with **no sanitization** — opening the exported CSV in Excel executes attacker-controlled formulas:

**A. `core/feedback_export_service.py:export_to_csv`** (served by `GET /api/feedback/export` via `feedback_phase2`) — `original_output` / `user_correction` are user/agent free text; a comment starting with `=HYPERLINK(...)` became a live formula. DDE payloads (`+cmd|...`) also passed through.

**B. `core/ai_accounting_engine.py:export_general_ledger_csv`** (served by `GET /api/v1/accounting/export/gl` + `/api/ai-accounting/export/gl`) — `description` / `merchant` come from transaction intake (bank feed, manual entry) and were written raw into the **financial** export.

**Fix:** mirrored R21's pattern in both modules — `_CSV_INJECTION_PREFIXES = ("=", "+", "-", "@", "\t", "\r")` + `_sanitize_csv_cell()` prefixing dangerous cells with a single quote (spreadsheet apps strip it on display and render text). Applied to every cell in both writers (defense in depth, not just the free-text fields).

**Tests:** 5 new tests in `backend/tests/test_round51_csv_injection_exports.py` (formula in `original_output`, DDE in `user_correction`, formula in GL `description` + `merchant`, and an HTTP-surface test on `GET /export/gl` asserting sanitized CSV). Zero regressions (comm-verified: 113→106 failures in affected suites — delta is exactly the 5 RED tests flipping green; `comm -13` empty = no new failures). mypy baseline identical (5 pre-existing errors, line shifts only). `main_api_app` imports clean. 5/5 round tests green.

### Round 50 — Business-Facts Upload: Unbounded File Read (OOM DoS) (July 31, 2026) ✨
**Bug hunt round.** `api/admin/business_facts_routes.py` `POST /api/admin/governance/facts/upload` (mounted twice in `main_api_app.py`) read the **entire upload into memory with no size cap** — R21 capped `document_ingestion_routes` `/parse` + `/upload` but missed this sibling. A multi-GB upload exhausts worker memory (OOM denial of service) and then feeds the whole blob to the OCR/LLM policy-fact-extraction pipeline. Filename sanitization (R7) and the extension allowlist were already in place; the missing piece was the cap.

**Fix:** mirrored R21's pattern — `MAX_UPLOAD_BYTES` (env-overridable, 50 MiB default) checked on the declared `file.size` BEFORE reading and again on `len(content)` after reading, raising `router.validation_error` (422).

**Tests:** 4 new tests in `backend/tests/test_round50_business_facts_upload_size.py` (oversized rejection with env cap + default cap, small-upload regression through the mocked extraction pipeline, source-level guard mirroring R21's inspection test). Zero regressions (comm-verified: 85→80 failures in affected suites — delta is exactly the 3 RED tests flipping green; `comm -13` empty = no new failures). mypy: `Success: no issues` on the changed file. `main_api_app` imports clean. 4/4 round tests green.

### Round 49 — Financial Amount Validation: Non-Positive Amounts Accepted (July 31, 2026) ✨
**Bug hunt round.** Mounted financial routers accepted non-positive amounts with no validation, silently corrupting ledgers and inverting guardrails:

**A. `api/apar_routes.py`** — `POST /apar/ap/intake` + `/apar/ar/generate` accepted negative/zero `amount`. A **negative invoice was AUTO-APPROVED** (`-100 < 500` auto-approve threshold → `InvoiceStatus.APPROVED` with `approved_by="auto"`), then distorted AP/AR balances, payment schedules, and reconciliation. `APIntakeRequest.amount`/`ARGenerateRequest.amount` (already `Decimal` for money precision) → `Field(..., gt=0)`.

**B. `api/financial_ops_routes.py`** — `POST /api/financial-ops/budget/limits` accepted a negative `monthly_limit`, **inverting every guardrail comparison** — any positive spend exceeded the limit → category self-DoS (PAUSED/BLOCKED on first spend). `budget/check`, `/invoices`, `/contracts` also accepted negative amounts. All four request models → `Field(..., gt=0)`. (Also fixed a missing `Field` import that made the module raise `NameError` at import.)

**C. `api/ai_accounting_routes.py`** — `POST /transactions` accepted negative amounts (refunds could be entered as negative spend, skewing category totals). `TransactionRequest.amount` → `Field(..., gt=0)`.

**D. Engine-level guards (defense in depth for non-API callers):** `core/apar_engine.py:intake_invoice` and `core/financial_ops_engine.py:BudgetGuardrails.set_limit` now raise `ValueError` on non-positive amounts. Two `VALIDATED_BUG` tests in `tests/error_paths/test_finance_error_paths.py` (which documented exactly this bug — "Fix: Add validation in BudgetGuardrails.set_limit()") and two in `tests/core/test_apar_engine_coverage.py` were updated from asserting the buggy behavior to asserting the rejection.

**Tests:** 11 new tests in `backend/tests/test_round49_financial_amount_validation.py` (422 rejections at API layer for all 8 endpoints + positive-amount regression + 2 engine `ValueError` guards). Zero regressions (comm-verified: 89→67 failures in affected suites — delta is exactly the 11 new + 4 updated tests flipping green; `comm -13` empty = no new failures). mypy baseline identical (17 pre-existing errors, line shifts only). `main_api_app` imports clean. 11/11 round tests green.

### Round 48 — BYOK Test-Suite Repair: Phantom Routes + Session Env Pollution (July 31, 2026) ✨
**Test-infra round (zero source changes).** The long-flagged stale `tests/unit/api/test_byok_routes.py` was rewritten:

**A. Phantom routes** — all 15 tests hit `/api/byok/*` routes that never existed on this router (404s), and the fixture's `patch('core.auth')` required core.auth to be pre-imported (order-dependent setup crashes). Rewrote against the REAL surface (now working after R47): `/api/ai/keys` (list/register), `/api/ai/providers` + `/{id}` + `/{id}/keys` + `/{id}/keys/{name}` (status/delete), `/api/v1/byok/health`, `/api/ai/health`, `/api/ai/pricing`, `/api/ai/usage/stats`, `/api/ai/optimize-cost`, `/api/ai/pdf/providers` — 13 tests, fixture imports normally with an auth override. Previously 7 setup-errors → now 13/13 passing.

**B. `tests/api/test_byok_endpoints_coverage.py`** — 4 stale assertions fixed (nested response shapes `provider`/`pdf_providers`, key registration via query params on `api/byok_routes` vs JSON body on `core/byok_endpoints`, `key_name` must be alphanumeric+underscores) → 28/28 passing.

**C. Session env pollution exposed + fixed** — `tests/unit/conftest.py` sets `TESTING=1` at import (unit-test DB) and never restores it; collecting any `tests/unit/` file before `tests/test_round14_fixes.py` made `AuthRateLimiter.check()` hit its TESTING bypass, breaking `test_blocks_after_limit_exceeded`. Hardened the round-14 test with an autouse monkeypatch delenv (same pattern as R44's tests). 279 tests green across the combined byok + rounds 38-47 + auth suites.

### Round 47 — Missing get_current_tenant: Tenant-Scoped BYOK Endpoints Broken (July 31, 2026) ✨
**Bug hunt round.** `api/byok_routes.py` imported `get_current_tenant` with a silent fallback (`except ImportError: get_current_tenant = None`) — and **`core.auth` has never exported `get_current_tenant`**, so the fallback always fired. `Depends(None)` makes FastAPI treat the parameter as a REQUIRED QUERY PARAM, so every tenant-scoped endpoint (`GET /api/ai/providers`, `GET /api/ai/providers/{id}`, `POST /api/ai/providers/{id}/keys`, `POST /api/ai/usage/track`, `POST /api/ai/pdf/optimize`) returned **422 "Field required" on every call** — authenticated or not. The entire provider/key-management surface was unusable.

**Fix:** implemented `get_current_tenant` in `core/auth.py` (resolves the authenticated user's tenant via `personal_scope.resolve_tenant_id`, falls back to the first Tenant row — single-tenant semantics; 404 if none) and removed the silent-None fallback in `byok_routes.py` (direct import).

**Tests:** 3 new tests in `backend/tests/test_round47_byok_tenant_dependency.py` (auth'd GET /api/ai/providers, GET /api/ai/providers/{id}, POST .../keys all return 200 with a resolved tenant). Zero regressions (comm-verified: byok+auth suites 14→11 failed — delta is exactly the 3 RED tests flipping green). mypy identical (43/43 — line shifts only). 201 tests green across rounds 38-47.

### Round 46 — Outlook Webhook: clientState Verification Not Enforced (July 31, 2026) ✨
**Bug hunt round.** `outlook_webhook_handler` verifies Microsoft's `clientState` signed token but **ignored the result** — `if not is_valid: logger.warning(...)` with no rejection. Processing continued: tenant lookup via the client-controlled `Host`/`X-Forwarded-Host` header, connection resolution, enqueue — and for forged `changeType: "deleted"` events, **deletion of `DiscoveredEntity` rows**. A forged clientState (valid JSON, no signature — `verify_client_state` returns False, `get_client_state_data` returns it unchanged, `json.loads` succeeds) was enough; no HMAC knowledge required. Fixed to fail closed (`continue` on invalid state). Also fixed a `str(e)` leak in the outer exception handler (`message: str(e)` → generic "Webhook processing failed" — reachable via non-dict payloads).

**Tests:** 4 new tests in `backend/tests/test_round46_outlook_client_state.py` (forged-state not enqueued, forged "deleted" event does not delete rows, legitimately-signed state still enqueued — regression guard, no-leak on processing error). Zero regressions (webhook suites 13→10 failures — delta is exactly R45's 3 RED tests flipping green; R46's 4 tests all green). mypy baseline identical (24/24). 198 tests green across rounds 38-46.

### Round 45 — Fail-Open Webhook Signature Verification (July 31, 2026) ✨
**Bug hunt round.** Audited the mounted webhook surface (`api/routes/webhooks/ingestion_webhooks.py` — slack/hubspot/salesforce/gmail/notion/outlook/zoho/pm-crm) for fail-open signature handling.

**A. HubSpot / Salesforce / Notion webhooks — signature check skipped when unconfigured.** All three handlers claimed "Verifies HMAC signature" but wrapped the check in `if integration and integration.config: if client_secret:` — when the integration row, its config, or the `client_secret` was missing, the event was **processed with NO verification** (CRUD dispatch / ingestion → forged-event injection, data poisoning, workflow triggers). An attacker who knew the tenant's `portalId`/`orgId`/`workspace_id` could POST arbitrary events. Fixed to fail CLOSED (503 "Webhook verification not configured" / 401 bad signature), mirroring the already-correct Slack handler.

**B. Reviewed, NOT bugs:** Gmail uses Google Pub/Sub auth (no HMAC by design); Outlook relies on Microsoft's `clientState`/validationToken handshake model (weaker by protocol design); zoho/pm-crm don't claim HMAC; Slack url_verification challenge echo is Slack protocol.

**Tests:** 6 new tests in `backend/tests/test_round45_webhook_fail_open.py` (unconfigured → 401/503 + dispatch never called for all 3 handlers; configured + bad signature → still 401). Zero regressions (comm-verified: 13→10 failures in affected suites — delta is exactly the 3 RED tests flipping green). mypy baseline identical (line shifts only). 194 tests green across rounds 38-45.

### Round 44 — Rate-Limit Bypasses: Scheduler Header + XFF Key Spoofing (July 31, 2026) ✨
**Bug hunt round.** Two rate-limit bypasses found in the security middleware:

**A. `core/security/middleware.py` RateLimitMiddleware** — the global limiter (120/min, 5000/day) bypassed for ANY request carrying an `X-Scheduler-Secret` header — **presence check only, no value validation**, and nothing in the codebase ever sets the header. `/api/scheduler` paths were already exempted by prefix, so the header check was dead weight that let any client strip rate limiting on every endpoint. Removed the header condition; the path exemption stays.

**B. `core/security/auth_rate_limit.py` AuthRateLimiter._client_ip** — trusted the LAST `X-Forwarded-For` entry as the rate-limit key. Only safe behind a proxy that appends the peer IP; the **Personal Edition runs standalone** (`uvicorn main:app`), where the client's own header value is used verbatim — rotating XFF bypassed login/register/refresh limits (10/min, 3/5min, 30/min). Now defaults to the TCP peer (`request.client.host`, never spoofable); XFF is only trusted when `TRUST_X_FORWARDED_FOR=1` is set explicitly for proxy deployments. `enterprise_auth_endpoints.reset_ip` uses the same `_client_ip()` helper, so reset stays consistent.

**Tests:** 5 new tests in `backend/tests/test_round44_rate_limit_bypasses.py` (direct middleware dispatch with the header present/absent + scheduler-path exemption + XFF-rotation bucket test + missing-XFF peer test). 204 tests green across rounds 38-44 + auth/round-14 suites. mypy baseline identical (line shifts only). `test_scenarios/test_security_scenarios.py` is pre-existing broken (`from main import app` — no main.py exists) — unrelated.

### Round 43 — Deleted/Suspended-User Token Continuation (July 31, 2026) ✨
**Bug hunt round.** `login_for_access_token` rejects non-ACTIVE users, but `get_current_user`/`get_current_user_ws` never checked `user.status` — so an already-issued JWT (24h lifetime, `ACCESS_TOKEN_EXPIRE_MINUTES`) kept authenticating a user after an admin soft-deleted the account (`enterprise_user_management.deactivate_user` sets `status=DELETED`) or suspended it. Every `get_current_user`-protected endpoint was affected (including `get_current_session_token` and all `require_permission` chains, which wrap it).

**Fix (`core/auth.py`):** both auth paths now reject non-ACTIVE accounts (`user.status != UserStatus.ACTIVE` → 401 / `None`), mirroring the login check. Added `UserStatus` import. Deactivation now takes effect immediately for existing tokens instead of at expiry.

**Tests:** 6 new tests in `backend/tests/test_round43_user_status_tokens.py` (crafted-JWT rejection for suspended/deleted/pending + WS paths + active acceptance guards). Zero regressions (comm-verified: 162→155 failures — the 7 delta is exactly the 4 RED tests flipping green + pre-existing flake; `comm -13` empty = no new failures). Note: tests read `SECRET_KEY` at call time — `test_auth_fixes.py` reloads `core.auth` mid-session, which stale module-level imports (a pre-existing test-isolation hazard). mypy baseline identical (25/25). 183 tests green across rounds 38-43.

### Round 42 — Client-Supplied Identity Sweep + Phantom-Schema Repair (July 31, 2026) ✨
**Bug hunt round.** Swept mounted routers for identity that comes from query/body params instead of the token (the IDOR/attribution-spoofing class fixed case-by-case in R38-41).

**A. `api/user_templates_endpoints.py` — CRITICAL IDOR + attribution spoofing (8 endpoints):** `create_user_template` set `author_id`/`changed_by_id` from a client `user_id` query param (create templates AS any user); `list_user_templates` with no `user_id` returned **ALL templates including private** and with a supplied id read any user's private templates; `update`/`delete`/`publish`/`duplicate` ownership checks ran against the client-supplied id (modify/delete ANY user's template); `stats` read any user. All now keyed to `current_user.id`; list always scopes `author_id == current_user.id OR is_public`.

**B. BONUS — phantom-schema repair (git-history traced):** the router was built against the rich `WorkflowTemplate` (template_id/complexity/tags/is_featured/template_json/...) in `1177eff90`; the Hive port `36ed0f548` **replaced the model** (id/icon/steps/input_schema/is_approved) without touching the router — every create/update/delete/filtered-list/rate 500'd since. Repaired the router against the real model: real-column constructors, `_template_to_response()` bridge (TemplateResponse contract preserved with safe defaults), `is_featured→is_approved`, `rating_sum` → running average, real `TemplateVersion` columns (version_number/created_by/change_summary). Marketplace `workflow_template_system.py` is file-based — DB model's only consumer is this router, so the migration is safe. Also fixed handlers swallowing `HTTPException` (403/404 → converted to 500 by bare `except Exception`).

**C. `api/dashboard_data_routes.py`** — 5 endpoints filtered calendar/tasks/messages/stats by a client-supplied `user_id` (cross-user dashboard reads) → clamped to `current_user.id` (deeplinks R38 pattern).

**D. `api/supervised_queue_routes.py`** — `get_queue_stats` filter clamped to `current_user.id`.

**E. `api/messaging_routes.py`** — approve/reject attributed actions to client-supplied `approver_user_id`/`rejecter_user_id` → token identity (fields kept optional for backward compat). **Bonus: `reject` and `cancel` endpoints were completely anonymous** (R23 fixed send/schedule/queue/history but missed these) → auth'd.

**Reviewed, NOT bugs:** `feedback_batch.py` body `user_id` is declared but never used; `deeplinks` audit already clamps (R38).

**Tests:** 16 new tests in `backend/tests/test_round42_identity_sweep.py` (identity-attribution assertions via captured constructor kwargs, filter-expression bind params, ownership 403s, plus 2 anon-401 regressions for reject/cancel). Zero regressions vs baseline (comm-verified: 72 failed/80 passed/35 errors identical pre/post — pre-existing fixture breakage). mypy baseline identical (0-line diff). 177 tests green across rounds 38-42.

### Round 41 — str(e) Leak Sweep + Broken Social Posting Pipeline (July 31, 2026) ✨
**Bug hunt round.** Re-grepped `str(e)` reaching clients in *mounted* routers — R18 fixed 992 leaks, but code added since R19-40 re-introduced them.

**A. `api/canvas_recording_routes.py`** — start/event/stop/get/list returned `message=f"Failed to ...: {str(e)}"` (R38's sweep missed these 5) → generic messages, logs retain `{e}`.

**B. `api/social_media_routes.py`** — per-platform poster exceptions surfaced `{"error": str(e)}` in `platform_results` (5 sites: twitter/linkedin/facebook + loop ValueError/Exception handlers) and the outer 500 handler leaked via `details={"error": str(e)}` → all generic.

**C. `api/admin_routes.py`** — `bulk_resolve_conflicts` appended `f"Conflict {id}: {str(e)}"` to the client-visible errors list → generic "Failed to resolve" (logger keeps detail).

**D. BONUS — broken social posting pipeline (2 latent bugs found by the leak tests):**
- `post_id = str(uuid.uuid4())` with only `from uuid import uuid4` imported → **every successful post 500'd AFTER the platform post was already sent** (double-effect: post fires, client sees failure, may retry → duplicate posts). Fixed → `str(uuid4())`.
- The entire OAuth token path queried **phantom `OAuthToken` columns** (`provider`, `status`, `access_token`, `scopes`, `last_used` — none exist on the model; it has `is_active`/`access_token_hash`/`scope`/`last_used_at`) → `AttributeError` on EVERY request: social posting could never succeed and `GET /connected-accounts` always 500'd. Root cause: code was written against a legacy schema. Fixed by switching to the real `IntegrationToken` model (has `provider`, `access_token` encrypted-at-rest, `status`, `scope`). `api/oauth_routes.py` (unmounted dead code) writes the same phantom schema — flagged, not exploitable today.

**Reviewed, NOT leaks:** `validate_content` echoing the client's own platform name; `recording_review_routes` echoing the client's own recording_id; `device_capabilities` flow-control only. `api/line_routes.py` + `api/archive/*` leaks are unmounted dead code.

**Tests:** 11 new tests in `backend/tests/test_round41_leak_sweep.py` (sentinel-based leak assertions across 3 routers + happy-path regression for the uuid bug + connected-accounts 200 regression). Zero regressions vs baseline (comm-verified: 36 passed/28 skipped/63 errors identical pre/post — the 63 are pre-existing SQLAlchemy-2.0 fixture breakage in test_admin_routes.py etc.). mypy improved 19→18 errors (uuid fix), zero new. 161 tests green across rounds 38-41.

### Round 40 — Third-Pass Auth Sweep: Never-Touched Routers + Route Shadowing (July 31, 2026) ✨
**Bug hunt round.** Extended `backend/scripts/audit_all_route_auth.py` matcher (now recognizes `require_permission(Permission.X)` calls, `get_super_admin`, `get_current_session_token`, `admin` param names) and swept the remaining *mounted* routers that prior rounds never touched.

**A. `api/agent_control_routes.py`** — start/stop/restart/execute were `get_super_admin`-guarded, but `GET /api/agent/status` (daemon PID/uptime/memory/CPU) was anonymous → now super-admin-gated.

**B. `api/canvas_coding_routes.py`** — R24 fixed canvas docs/email/terminal; `GET /api/canvas/coding/{id}` returned full coding-canvas audit details (code diffs) anonymously → auth'd.

**C. `api/intelligence_routes.py`** — `GET /api/intelligence/{insights,entities}` exposed cross-platform business insights; `/insights` also auto-seeds and ingests platform data in development mode (side-effecting, cost-bearing) → auth'd.

**D. `api/skill_routes.py`** — R22 fixed import/execute/promote; the 4 reads (`list`, `get`, `{id}/episodes` — episodic execution memory, `{id}/learning-progress`) were anonymous → auth'd.

**E. `api/workflow_template_routes.py`** — R38 fixed create/import/execute; `list_templates`/`search_templates` were anonymous. **Bonus bug: `GET /search` was unreachable** — shadowed by `GET /{template_id}` declared earlier (searches always hit `get_template`). Moved `search_templates` above `get_template` + auth'd both. Also removed a `str(e)` leak in `list_templates` (`details={"error": str(e)}`).

**F. `api/byok_routes.py`** — key-management endpoints (`GET/POST /api/ai/keys` — mock but key surface) and all 5 pricing endpoints were anonymous; `POST /api/ai/pricing/refresh` triggers external fetches from LiteLLM/OpenRouter (anonymous network abuse). 5 remaining `str(e)` leaks in the pricing section (R25 fixed the earlier ones) → all auth'd + generic messages.

**G. `api/analytics_dashboard_routes.py`** — all 12 endpoints (message analytics, sentiment, `POST /correlations`, predictions, user patterns, overview) were anonymous → auth'd.

**Also:** `api/signal_routes.py`, `api/line_routes.py`, `api/google_chat_enhanced_routes.py`, `api/analytics_dashboard_endpoints.py`, `api/integration_dashboard_routes.py`, `api/learning_plan_routes.py`, `api/sales_routes.py`, `api/integrations/memory_backfill_routes.py`, `api/routes/webhooks/monitoring.py`, `api/tools.py`, `api/reports.py` are **unmounted dead code** with anonymous endpoints — flagged, not exploitable today. WebSocket endpoints (`websocket_routes`, `satellite_routes`, `canvas_state_websocket`) and `user_management_routes` sessions already do token checks (`get_current_user_ws` / `get_current_session_token` — scanner false positives). `admin/skill_routes.create_new_skill` is `get_super_admin`-guarded (scanner false positive).

**Tests:** 40 new tests in `backend/tests/test_round40_remaining_auth_sweep.py` (30 anon-401 + 10 positive/leak/regression incl. route-shadowing + `list_templates` leak). Fixed 2 existing test files (auth overrides: `test_byok_pricing_endpoints.py`, `test_skill_routes.py`) + updated 2 leak-assertion tests in `test_byok_pricing_endpoints.py` that asserted the OLD leaky messages. 311 tests green across rounds 38-40 + 9 affected suites; zero regressions vs baseline (verified by comm on failure lists — 7 pre-existing setup-ERROR tests in `test_byok_routes.py` merely converted to assertion failures, 8 previously-crashing tests now pass). mypy baseline identical (line-number shifts only, verified by diff).

### Round 39 — Second-Half Auth Sweep: Partially-Fixed Routers (July 31, 2026) ✨
**Bug hunt round.** Prior rounds (20/24/25/26/27/38) added auth to *some* endpoints in each file but left sibling endpoints anonymous. New AST scanner `backend/scripts/audit_all_route_auth.py` walks **every** `@router.*` handler (R38's script only checked `@require_governance`-decorated ones) and flags endpoints with no auth dep and no router-level dependency.

**A. `api/ai_accounting_routes.py` (mounted at `/api/v1/accounting` + `/api/ai-accounting`)** — R27 fixed only `ingest_transaction`. The other 12 endpoints were anonymous: `bank-feed` (bulk ingest), `review-queue` + `all-transactions` (full financial ledger read: amounts/merchants/reasoning), `update/delete/post/{id}` (financial writes/deletes), `auto-post` (mass posting), `audit-log`, `export/gl` (CSV), `export/trial-balance`, `forecast` (13-week cash flow), `scenario`. `categorize/update/delete/post` also trusted a client-supplied `user_id` (default `"user"`) for the audit trail → now `current_user.id`.

**B. `api/episode_routes.py`** — R26 fixed only ~6 of 20 endpoints. The remaining 14 (temporal/semantic/sequential/contextual/canvas-aware/business-data retrieval, `{id}/feedback/list`, `analytics/feedback-episodes`, `graduation/readiness|exam|audit`, `lifecycle/decay`, `stats/{id}`) were anonymous reads of episodic memory (reasoning steps, canvas state). `retrieve_temporal` trusted client-supplied `user_id` (cross-user read IDOR) → now `current_user.id`; `promote_agent` trusted client-supplied `validated_by` for audit attribution → now `current_user.id`.

**C. `api/agent_governance_routes.py`** — `approve_workflow` had auth + RBAC, but `reject_workflow` was **anonymous privilege escalation** (reject any pending approval as ANY approver) and `list_pending_approvals` was an anonymous read of the approval queue. `approve_workflow` ran RBAC against client-supplied `approver_id` instead of `current_user.id` (attribution spoof) → RBAC + `approve_intervention` + `reject_intervention` now keyed to the token identity.

**D. `api/entity_type_routes.py`** — `create_entity_type` fixed (R26); `list/get/update (PATCH schema modification)/suggest-schema (anonymous LLM cost abuse)` were not → all now auth'd.

**E. `api/graphrag_routes.py`** — `ingest_document`/`add_entity` fixed (R26); the other 9 (graph reads, `add_relationship` + `build-communities` — graph poisoning, `query` — LLM cost abuse) were anonymous → all now auth'd.

**F. `api/agent_status_endpoints.py`** — write endpoints had auth; all 5 read endpoints (`agent/status/{id}`, `agent/status`, `agents`, `agents/{id}`, `agent/metrics`) leaked agent task state anonymously → auth'd.

**G. `api/background_agent_routes.py`** — register/start/stop/status auth'd; `{agent_id}/logs` + `logs` leaked run logs anonymously → auth'd.

**H. `api/feedback_enhanced.py`** — submit fixed (R27); `agent/{id}`, `analytics`, `trends` aggregate reads were anonymous → auth'd.

**Also:** `api/operations_api.py` is dead code (never mounted) with a `str(e)` leak + no auth — flagged for future cleanup, not exploitable today. `episode_routes.list_canvas_types` intentionally left public (static metadata). Remaining audit hits are `get_super_admin`-guarded (agent_control), `require_permission(...)`-guarded (agent_routes), or unmounted archive — reviewed, not bugs.

**Tests:** 65 new tests in `backend/tests/test_round39_remaining_auth_sweep.py` (57 anon-401 assertions + 8 identity-attribution/positive tests). Fixed 2 pre-existing test files (auth override fixtures: `test_ai_accounting_routes.py`, `test_agent_governance_routes.py`) + repaired 19 stale-path tests in `test_ai_accounting_routes.py` (`/ai-accounting/...` → router's actual empty-prefix paths — pre-existing failures, verified identical in baseline via git stash). 230 tests green (round39 + round38 + 6 affected suites). mypy baseline identical (38 pre-existing errors, zero new — verified by diff).

### Round 38 — Remaining API Surface: Auth + Governance Wiring + Impersonation + Leak Sweep (July 31, 2026) ✨
**Bug hunt round.** AST-based audit (`backend/scripts/audit_governance_auth.py`) of every `@require_governance` endpoint and mounted-but-unauthenticated router.

**CRITICAL — unauthenticated endpoints (anonymous reads/writes):**
- `api/operational_routes.py` `/api/business-health/*` (7 endpoints) — anonymous **intervention execution**, decision simulation, financial-forensics reads
- `api/project_routes.py` `/api/projects/unified-tasks` — anonymous **MCP task creation on connected platforms**; `user_id` query param allowed cross-user access
- `api/ai_workflows_routes.py` — anonymous LLM usage (cost abuse) + provider-config disclosure
- `api/feedback_batch.py` — anonymous feedback adjudication + pending-feedback content exposure
- `api/zoho_workdrive_routes.py` — anonymous **cross-user file access/ingestion** via client-supplied `user_id`
- `api/workflow_template_routes.py` create/import/execute — anonymous template creation + **execution**
- `api/background_agent_routes.py` register/start/stop/status — anonymous background-agent control
- `api/data_ingestion_routes.py` `enable_auto_sync` — anonymous sync config
→ Added `Depends(get_current_user)` (router-level where every endpoint is sensitive; per-endpoint where `current_user.id` is needed). Identity now comes from the token, never from query/body params.

**HIGH — governance silently disabled (`core/api_governance.py`):**
The `require_governance` wrapper only looked up `kwargs['request']`. Endpoints whose JSON body is also named `request` used `http_request` — so the check was **silently skipped**, and worse, `extract_agent_id()` crashed with `AttributeError` (every such endpoint 500'd in production: `admin_routes` delete_admin_user/roles/websocket, background-agent register/start, `enable_auto_sync`, `create_template`). Fixed the wrapper to fall back to `http_request` when `request` isn't a `starlette.Request`; added the missing `request` param to `list_conflicts`/`get_conflict`. Side effect: ~110 pre-existing failing tests repaired.

**HIGH — impersonation (`api/deeplinks.py`):** `execute` trusted client-supplied `user_id` (deep links ran **as any user**); `audit` let any user read another user's deep-link history. Both now use the authenticated identity; audit scoping clamps to the caller's own id.

**MEDIUM — 17 `str(e)` leaks removed** across `forensics_api`, `canvas_recording_routes`, `document_ingestion_routes`, `workflow_template_routes`, `project_routes`, `ai_workflows_routes`, `background_agent_routes`, `deeplinks`. Added `min_length=1` name validation to template create/update; fixed `parameters={}` mutable default in `execute_template`.

**Tests:** 45 new tests in `backend/tests/test_round38_api_auth_governance.py` (auth 401s, governance wiring, impersonation, leaks). 0 new failures across ~30 affected suites; 13 existing test files updated with `get_current_user` overrides.

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
MAX_BODY_BYTES=67108864               # Request-body cap for POST/PUT/PATCH (64 MiB default, R55)
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
