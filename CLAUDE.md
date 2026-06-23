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

---

## Recent Bug Hunt History (TDD)

All fixes use Red-Green-Refactor: failing test first, minimal fix, regression tests committed. Test files: `tests/test_roundN_fixes.py`, `tests/test_security_bug_hunt.py`, `tests/test_auth_fixes.py`, etc.

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

**Core**: `agent_governance_service.py`, `agent_context_resolver.py`, `governance_cache.py`, `llm/byok_handler.py`, `models.py`, `agent_world_model.py`, `graphrag_engine.py`, `entity_type_service.py`, `model_factory.py`

**API**: `atom_agent_endpoints.py`, `api/canvas_routes.py`, `api/browser_routes.py`, `api/device_capabilities.py`, `api/deeplinks.py`, `api/admin/business_facts_routes.py`, `api/entity_type_routes.py`, `api/graphrag_routes.py`, `api/health_routes.py`

**Frontend**: `frontend-nextjs/hooks/useCanvasState.ts`, `components/canvas/types/index.ts`

**Tools**: `tools/canvas_tool.py`, `tools/browser_tool.py`, `tools/device_tool.py`, `tools/atom_cli_skill_wrapper.py`

**Skills**: `skills/atom-cli/` (6 SKILL.md), `core/skill_adapter.py`

**E2E**: `backend/tests/e2e_ui/README.md`, `conftest.py`, `fixtures/auth_fixtures.py`, `pages/page_objects.py`

**BYOK**: `docs/architecture/BYOK_V6_MIGRATION_GUIDE.md`, `.planning/REQUIREMENTS-v6.0-BYOK.md`, `core/llm/llm_service.py`

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
