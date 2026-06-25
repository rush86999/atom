# Atom - AI-Powered Business Automation Platform

> **Project Context**: Intelligent business automation/integration platform using AI agents to automate workflows, integrate services, and manage operations.

**Last Updated**: June 22, 2026

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
26. **GraphRAG & Entity Types** (`core/graphrag_engine.py`, `entity_type_service.py`, `model_factory.py`): PostgreSQL recursive CTEs, 6 canonical types, dynamic custom types
27. **Frontend XSS Protection** (`frontend-nextjs/lib/sanitize.ts`): DOMPurify-based `sanitizeHtml()` + `renderMarkdownSafe()`, applied to all `dangerouslySetInnerHTML` sites
28. **Mobile Secure Storage** (`mobile/src/storage/secureTokenStorage.ts`): expo-secure-store wrapper for auth tokens (iOS Keychain / Android EncryptedSharedPreferences), transparent AsyncStorage migration
29. **Safe Expression Evaluator** (`core/safe_evaluator.py`): AST-validated `safe_eval()` replacing raw `eval()` in workflow conditions, event bus, and conductor
30. **CSV Injection Guard** (`accounting/export_service.py:_sanitize_csv_cell`): Prefixes `= + - @` cells with single quote in financial exports (CWE-1236)
31. **Workflow ReDoS Guard** (`core/workflow_parameter_validator.py`): `MAX_REGEX_LENGTH=200` + `_has_redos_risk()` heuristic on user-supplied regex patterns
32. **Ollama Local LLM** (`core/llm/byok_handler.py`, `core/byok_endpoints.py`): First-class provider for fully local inference via Ollama's OpenAI-compatible API (`OLLAMA_BASE_URL`); no API key required, registered in `PROVIDER_TIERS["budget"]` with zero cost
33. **Per-Turn Fact Extraction** (`core/turn_fact_extractor.py`, `core/turn_fact_queue.py`, `core/turn_fact_vector_store.py`, `core/turn_fact_categories.py`): Hermes-style memory-provider layer. Two entrypoints — `extract_from_turn()` (`sync_turn` hook, fires fire-and-forget after each ReAct step) and `extract_from_prompt_before_truncation()` (`on_pre_compress` hook, drained by `ExtractionQueue` worker). Extracts Mem0's 5 durable-fact categories (exact_value, hard_constraint, decision_reason, cross_task_dep, implicit_pref) using `model="fast"` + 2s timeout. Two-tier recall: Tier-1 pure-SQL `DURABLE FACTS` prompt block (sub-ms), Tier-2 LanceDB semantic `prefetch_relevant_facts()` (opt-in). SQL row is source of truth; LanceDB write is best-effort. Maturity-gated (STUDENT agents read-only). Never raises, never silently drops. See `docs/architecture/CONTEXT_MEMORY.md`
34. **Agent Memory Tools + Gap-Analysis Layer** (`tools/memory_tool.py`, `core/turn_fact_extractor.py`, `core/llm/byok_handler.py`): (a) `memory_remember` (INTERN+, complexity 2) / `memory_forget` (SUPERVISED+, complexity 3) — agent-callable tools for explicit persist/invalidate; deletion safety refuses blank targets. (b) Circuit breaker (`_CircuitBreaker`: 5 failures → 120s cooldown → half-open probe → close-on-success) prevents extraction storms during provider outages. (c) FTS5 lexical search (`search_reasoning_steps_lexical()` + migration `20260624_reasoning_fts`) — exact-match fallback for error strings/IDs. (d) `on_session_end` extraction hook (final pass over turn digest). (e) Context compression — `truncate_to_context` boundary protection (head+tail preserved, middle elided) + `sanitize_tool_pairs()` (stub injection prevents OpenAI 400). No LLM-summary phase (Hermes' own has 3 documented bugs). See `docs/architecture/HERMES_COMPARISON.md`

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

**Core**: `agent_governance_service.py`, `agent_context_resolver.py`, `governance_cache.py`, `llm/byok_handler.py`, `models.py`, `agent_world_model.py`, `graphrag_engine.py`, `entity_type_service.py`, `model_factory.py`, `turn_fact_extractor.py` (+ `turn_fact_queue.py`, `turn_fact_vector_store.py`, `turn_fact_categories.py` — see `docs/architecture/CONTEXT_MEMORY.md`)

**Memory Tools**: `tools/memory_tool.py` (`memory_remember` / `memory_forget` — agent-callable), `core/turn_fact_extractor.py` (extraction, circuit breaker, FTS5 search, recall). Comparison: `docs/architecture/HERMES_COMPARISON.md`

**API**: `atom_agent_endpoints.py`, `api/canvas_routes.py`, `api/browser_routes.py`, `api/device_capabilities.py`, `api/deeplinks.py`, `api/admin/business_facts_routes.py`, `api/entity_type_routes.py`, `api/graphrag_routes.py`, `api/health_routes.py`

**Frontend**: `frontend-nextjs/hooks/useCanvasState.ts`, `components/canvas/types/index.ts`

**Tools**: `tools/canvas_tool.py`, `tools/browser_tool.py`, `tools/device_tool.py`, `tools/atom_cli_skill_wrapper.py`

**Skills**: `skills/atom-cli/` (6 SKILL.md), `core/skill_adapter.py`

**E2E**: `backend/tests/e2e_ui/README.md`, `conftest.py`, `fixtures/auth_fixtures.py`, `pages/page_objects.py`

**BYOK**: `docs/architecture/BYOK_V6_MIGRATION_GUIDE.md`, `.planning/REQUIREMENTS-v6.0-BYOK.md`, `core/llm/llm_service.py`

**Security**: `core/safe_evaluator.py` (AST eval), `core/auth.py` (`get_current_user`), `frontend-nextjs/lib/sanitize.ts` (DOMPurify XSS guard), `mobile/src/storage/secureTokenStorage.ts` (SecureStore), `accounting/export_service.py` (`_sanitize_csv_cell`)

**Bug Hunt Tests**: `tests/test_round{4..17}_fixes.py`, `tests/test_round{18..31}_*.py`, `tests/test_rounds27_30_consolidated.py`, `tests/test_auth_fixes.py`, `tests/test_security_bug_hunt.py`, `tests/test_toctou_fixes.py`, `tests/test_turn_fact_extraction.py`, `tests/test_turn_fact_queue.py`, `frontend-nextjs/lib/__tests__/sanitize.test.ts`

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

# Auth (admin password auto-generated on first launch, check startup logs)
curl -X POST http://localhost:8000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"admin@example.com","password":"<from-log>"}'

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
