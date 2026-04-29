# Atom - AI-Powered Business Automation Platform

> **Project Context**: Atom is an intelligent business automation and integration platform that uses AI agents to help users automate workflows, integrate services, and manage business operations.

**Last Updated**: April 10, 2026

---

## Quick Overview

**What is Atom?**
- AI-powered workflow automation platform with multi-agent system and governance
- Real-time streaming LLM responses with multi-provider support
- Canvas-based visual presentations with custom components
- Browser automation (CDP) and device capabilities
- Enhanced feedback system with A/B testing
- Mobile support architecture (React Native)
- **✨ Episodic Memory & Graduation Framework** - Agent learning from past experiences
- **✨ Auto-Dev Module** - Self-evolving agents that learn from failures and optimize skills
- **✨ Federation & Instance Identity** - Multi-instance communication and resource sharing
- **✨ Personal Edition** - Run Atom locally with Docker
- **✨ Production-Ready** - CI/CD pipeline, monitoring, health checks

**Tech Stack**: Python 3.11, FastAPI, SQLAlchemy 2.0, SQLite/PostgreSQL, Multi-provider LLM, Playwright, Redis (WebSocket), Alembic

**Key Directories**: `backend/core/`, `backend/api/`, `backend/tools/`, `backend/tests/`, `frontend-nextjs/`, `mobile/`, `docs/`

**Key Services**:
- `agent_governance_service.py` - Agent lifecycle and permissions
- `trigger_interceptor.py` - Maturity-based trigger routing
- `student_training_service.py` - Training proposals and sessions
- `supervision_service.py` - Real-time supervision monitoring
- `governance_cache.py` - High-performance caching (<1ms lookups)
- `intent_classifier.py` - Intent classification (CHAT/WORKFLOW/TASK routing)
- `queen_agent.py` - Structured workflow automation (Queen Hive)
- `fleet_admiral.py` - Dynamic agent recruitment for unstructured complex tasks
- `atom_meta_agent.py` - Central orchestrator with domain creation and fleet recruitment
- `auto_dev/` - Auto-Dev module (Memento-Skills, AlphaEvolver, EventBus, Sandbox)
- `atom_saas_client.py` - Marketplace client with federation headers
- `health_routes.py` - Health check endpoints
- `monitoring.py` - Prometheus metrics and structured logging
- `cli/daemon.py` - Daemon mode for background agent execution
- `useCanvasState.ts` - Canvas state subscription hook
- `canvas/types/index.ts` - Canvas state type definitions
- `core/llm/canvas_summary_service.py` - LLM canvas summary service

---

## ⚠️ Security: NEVER Commit These Files

**CRITICAL**: The following files and directories contain sensitive information and must NEVER be committed to the repository:

| File/Directory | Content | Risk |
|----------------|---------|------|
| **`.claude/`** | Claude Code API keys and configuration | API key exposure |
| **`.env*`** | Environment variables with secrets | Credential leakage |
| **`secrets.json`** | Secret keys and tokens | Full system compromise |
| **`*.pem`, `*.key`** | TLS certificates and private keys | Man-in-the-middle attacks |
| **`credentials.json`** | OAuth credentials, API keys | Unauthorized access |
| **`backend/token.json`** | Authentication tokens | Session hijacking |

### Verification Before Committing
Always run `git status` before committing. Verify these files are NOT in the staged changes.

### If You Accidentally Commit Secrets
1. **IMMEDIATELY rotate all compromised keys** - Change API keys, passwords, tokens
2. **Remove from git history** - Use `git filter-repo` or BFG Repo-Cleaner (NOT just `git rm`)
3. **Force push carefully** - Only after confirming history is clean
4. **Notify team** - Inform maintainers immediately

See [CONTRIBUTING.md](CONTRIBUTING.md) for detailed cleanup instructions.

---

## Architecture Overview

### Multi-Agent System with Governance

```
User Request → AgentContextResolver → GovernanceCache → AgentGovernanceService → Agent Execution → Response
```

### Maturity Levels

| Level | Confidence | Automated Triggers | Capabilities |
|-------|-----------|-------------------|--------------|
| STUDENT | <0.5 | **BLOCKED** → Route to Training | Read-only (charts, markdown) |
| INTERN | 0.5-0.7 | **PROPOSAL ONLY** → Human Approval Required | Streaming, form presentation |
| SUPERVISED | 0.7-0.9 | **RUN UNDER SUPERVISION** → Real-time Monitoring | Form submissions, state changes |
| AUTONOMOUS | >0.9 | **FULL EXECUTION** → No Oversight | Full autonomy, all actions |

**Action Complexity**: 1 (LOW): Presentations → STUDENT+ | 2 (MODERATE): Streaming → INTERN+ | 3 (HIGH): State changes → SUPERVISED+ | 4 (CRITICAL): Deletions → AUTONOMOUS only

---

## Core Components

### 1. Agent Governance System
**Files**: `agent_governance_service.py`, `agent_context_resolver.py`, `governance_cache.py`
- Manages agent lifecycle, permissions, and maturity
- <1ms cached governance checks

### 2. Streaming LLM Integration
**Files**: `llm/byok_handler.py`, `atom_agent_endpoints.py`
- Multi-provider support (OpenAI, Anthropic, DeepSeek, Gemini)
- Token-by-token streaming via WebSocket

### 3. Canvas Presentation System
**Files**: `tools/canvas_tool.py`, `api/canvas_routes.py`
- Charts (line, bar, pie), markdown, forms with governance

### 4. Real-Time Agent Guidance System ✨
**Files**: `tools/agent_guidance_canvas_tool.py`, `core/view_coordinator.py`, `core/error_guidance_engine.py`
- Live operation tracking with progress bars
- Multi-view orchestration (browser/terminal/canvas)
- Smart error resolution with 7 error categories
- Interactive permission/decision requests
- **Docs**: `docs/archive/CANVAS_IMPLEMENTATION_COMPLETE.md`

### 5. Python Package Support ✨ (Phase 35)
**Files**: `core/package_governance_service.py`, `core/package_dependency_scanner.py`, `core/package_installer.py`
- Per-skill Docker images with dedicated packages
- Vulnerability scanning using pip-audit + Safety
- Maturity-based access control (STUDENT blocked, INTERN requires approval)
- Container security (network disabled, read-only filesystem, resource limits)
- **Performance**: <5min image build, <1ms permission checks
- **Tests**: 117 tests across 7 test files
- **Docs**: See `.planning/phases/35-python-package-support/`

### 6. Canvas AI Accessibility System ✨
**Files**: `frontend-nextjs/hooks/useCanvasState.ts`
- Hidden accessibility trees exposing canvas state as JSON
- Canvas State API: `window.atom.canvas.getState()`, `getAllStates()`, `subscribe()`
- TypeScript type definitions for all 7 canvas types
- **Performance**: <10ms serialization overhead per render

### 7. LLM Canvas Summaries ✨
**Files**: `core/llm/canvas_summary_service.py`
- LLM-generated summaries (50-100 words) for enhanced episodic memory
- Support for all 7 canvas types with specialized prompts
- Summary cache by canvas state hash
- **Benefits**: Better episode retrieval, agent learning, semantic search

### 8. Queen Agent - Structured Workflow Automation ✨ (April 2026)
**Files**: `backend/core/agents/queen_agent.py`, `core/intent_classifier.py`
- **Queen Agent (Queen Hive)**: Orchestrator for structured, repeatable business processes with predefined blueprints
- **Workflow Automation**: Executes known business processes with reliable, repeatable steps (daily reports, data pipelines, CRM workflows)
- **Blueprint System**: Predefined workflow templates with parameterizable steps, validation, and error handling
- **Intent Routing**: WORKFLOW intents (structured tasks) → Queen Agent, TASK intents (unstructured) → Fleet Admiral
- **Governance Integration**: STUDENT blocked, INTERN requires approval, SUPERVISED/AUTONOMOUS full access
- **Performance**: <35ms blueprint loading, ~80ms error recovery, 1-5 minute typical execution
- **Docs**: `docs/QUEEN_AGENT.md`, `docs/guides/QUEEN_AGENT_USER_GUIDE.md`

### 9. Unstructured Complex Tasks & Domain Creation ✨
**Files**: `core/atom_meta_agent.py`, `core/intent_classifier.py`, `core/fleet_admiral.py`
- **Intent Classification**: CHAT (simple queries) → LLMService, WORKFLOW (structured tasks) → QueenAgent, TASK (unstructured complex) → FleetAdmiral
- **FleetAdmiral**: Dynamic agent recruitment for long-horizon unstructured tasks requiring multiple specialist agents
- **Domain Creation**: SpecialtyAgentTemplate system with 8+ domain templates
- **Agent Spawning**: `spawn_agent()` method for creating custom specialty agents with capability graduation tracking
- **Multi-Agent Fleet**: Blackboard-based coordination with recruitment intelligence
- **Governance-Gated Routing**: CHAT bypasses governance, WORKFLOW/TASK require maturity checks
- **Performance**: <100ms intent classification, <500ms fleet recruitment

### 10. BYOK Cognitive Tier System ✨ (Phase 68)
**Files**: `core/llm/cognitive_tier_system.py`, `core/llm/cache_aware_router.py`, `core/llm/escalation_manager.py`
- 5-tier intelligent LLM routing (Micro, Standard, Versatile, Heavy, Complex)
- Multi-factor classification: token count + semantic complexity + task type
- Cache-aware routing: 90% cost reduction with prompt caching
- Auto-escalation: Quality-based tier escalation with 5-min cooldown
- MiniMax M2.5: Standard tier option at ~$1/M tokens
- **Performance**: <100ms routing, <50ms classification, 30%+ cost savings
- **Tests**: 100+ tests across 8 test files
- **Docs**: `docs/COGNITIVE_TIER_SYSTEM.md`

### 11. Browser Automation System
**Files**: `tools/browser_tool.py`, `api/browser_routes.py`
- Web scraping, form filling, screenshots via Playwright CDP
- **Governance**: INTERN+ required
- **Docs**: `docs/archive/2025-12/BROWSER_IMPLEMENTATION_SUMMARY.md`

### 12. Device Capabilities System
**Files**: `tools/device_tool.py`, `api/device_capabilities.py`
- Camera (INTERN+), Screen Recording (SUPERVISED+), Location (INTERN+), Notifications (INTERN+), Command Execution (AUTONOMOUS only)
- **Docs**: `docs/DEVICE_CAPABILITIES.md`

### 13. Atom CLI Skills System ✨
**Files**: `backend/tools/atom_cli_skill_wrapper.py`, `backend/skills/atom-cli/` (6 SKILL.md files)
- 6 built-in skills: atom-daemon, atom-status, atom-start, atom-stop, atom-execute, atom-config
- AUTONOMOUS maturity for daemon control, STUDENT for read-only operations
- Subprocess wrapper with 30s timeout, structured output, error handling
- **Docs**: `docs/ATOM_CLI_SKILLS_GUIDE.md`

### 14. Deep Linking System
**Files**: `core/deeplinks.py`, `api/deeplinks.py`
- `atom://agent/{id}`, `atom://workflow/{id}`, `atom://canvas/{id}`, `atom://tool/{name}`
- **Docs**: `docs/DEEPLINK_IMPLEMENTATION.md`

### 15. Enhanced Feedback System
**Files**: `api/feedback_enhanced.py`, `api/feedback_analytics.py`
- Thumbs up/down, star ratings, corrections, analytics dashboard
- Batch operations, promotion suggestions, A/B testing

### 16. Student Agent Training System ✨
**Files**: `core/trigger_interceptor.py`, `core/student_training_service.py`
- Four-tier maturity routing: STUDENT → INTERN → SUPERVISED → AUTONOMOUS
- AI-based training duration estimation with historical data analysis
- Real-time supervision for SUPERVISED agents with intervention support
- Action proposal workflow for INTERN agents (human approval required)
- **Performance**: <5ms routing decisions using GovernanceCache
- **Database**: 4 new models (BlockedTriggerContext, AgentProposal, SupervisionSession, TrainingSession)
- **API**: 20+ REST endpoints covering training, proposals, and supervision
- **Tests**: `tests/test_trigger_interceptor.py` (11 tests)

### 17. Database Models
**File**: `core/models.py`
- Key models: AgentRegistry, AgentExecution, AgentFeedback, CanvasAudit, BrowserSession, DeviceSession, DeepLinkAudit, ChatSession
- **NEW**: AgentOperationTracker, AgentRequestLog, ViewOrchestrationState, OperationErrorResolution
- **NEW**: BlockedTriggerContext, AgentProposal, SupervisionSession, TrainingSession
- **NEW**: Episode, EpisodeSegment, EpisodeAccessLog (Episodic Memory with graduation tracking)
- **NEW**: CommunitySkill, SkillSecurityScan, SkillExecution (Community Skills with security validation)

### 18. Episodic Memory & Graduation Framework ✨
**Files**: `episode_segmentation_service.py`, `episode_retrieval_service.py`, `episode_lifecycle_service.py`, `agent_graduation_service.py`
- Automatic episode segmentation (time gaps, topic changes, task completion)
- Four retrieval modes: Temporal, Semantic, Sequential, Contextual
- Hybrid PostgreSQL (hot) + LanceDB (cold) storage architecture
- Canvas-aware episodes: Track canvas presentations (charts, forms, sheets)
- Feedback-linked episodes: Aggregate user feedback scores for retrieval weighting
- LLM-powered summaries: 80%+ semantic richness with progressive detail levels
- **Graduation Criteria**:
  - STUDENT → INTERN: 10 episodes, 50% intervention rate, 0.70 constitutional score
  - INTERN → SUPERVISED: 25 episodes, 20% intervention rate, 0.85 constitutional score
  - SUPERVISED → AUTONOMOUS: 50 episodes, 0% intervention rate, 0.95 constitutional score
- **Performance**: Episode creation <5s, Temporal retrieval ~10ms, Semantic retrieval ~50-100ms
- **API**: 25+ REST endpoints for episodes, graduation, and canvas/feedback integration
- **Docs**: `docs/EPISODIC_MEMORY_IMPLEMENTATION.md`, `docs/DEVELOPMENT/AGENT_GRADUATION_GUIDE.md`, `docs/CANVAS_FEEDBACK_EPISODIC_MEMORY.md`

### 19. World Model & Business Facts ✨
**Files**: `core/agent_world_model.py`, `api/admin/business_facts_routes.py`, `core/policy_fact_extractor.py`
- Business Facts: Verified knowledge with citations (e.g., "Invoices > $500 need VP approval" with policy.pdf:p4)
- JIT Verification: Real-time citation validation via R2/S3 storage checks
- Semantic Fact Retrieval: Vector search in LanceDB for contextually relevant facts
- Knowledge Graph Integration: GraphRAG traversal for connected knowledge
- Multi-Source Memory: Combines facts, experiences, formulas, episodes, and conversations
- Real-Time Synthesis: LLM-powered answer generation from retrieved context
- Security: Secrets redaction, RBAC enforcement (ADMIN-only management)
- **Performance**: <100ms fact retrieval, <500ms citation verification, <50ms vector search
- **Docs**: `docs/JIT_FACT_PROVISION_SYSTEM.md`, `docs/CITATION_SYSTEM_GUIDE.md`

### 20. Production Monitoring & Observability ✨
**Files**: `api/health_routes.py`, `core/monitoring.py`, `tests/test_health_routes.py`
- Health check endpoints: `/health/live` (liveness), `/health/ready` (readiness with DB/disk checks)
- Prometheus metrics: HTTP requests, agent executions, skill executions, DB queries
- Structured logging: JSON output with structlog, context binding (request_id, agent_id, skill_id)
- Performance benchmarks: <10ms (live), <100ms (ready), <50ms (metrics scrape)
- Orchestration Ready: Kubernetes/ECS health check configurations documented
- Grafana Integration: Dashboard setup instructions provided
- **Tests**: 13 tests covering liveness, readiness, metrics, and performance
- **Docs**: `backend/docs/MONITORING_SETUP.md`

### 21. CI/CD Pipeline & Deployment ✨
**File**: `.github/workflows/deploy.yml`
- Automated testing, Docker builds, staging/production deployments
- Jobs: test → build → deploy-staging (auto) → deploy-production (manual approval) → verify
- Automated rollback on failure with one-line command
- Database backup before production deployment
- Smoke tests for agent execution, canvas presentation, skill execution
- Metrics monitoring (error rate, latency) with automatic alerts
- Slack notifications for deployment status
- **Docs**: `docs/DEPLOYMENT/DEPLOYMENT_RUNBOOK.md`, `backend/docs/OPERATIONS_GUIDE.md`, `backend/docs/TROUBLESHOOTING.md`

### 22. Personal Edition & Daemon Mode ✨
**Files**: `cli/daemon.py`, `cli/main.py`, `.env.personal`, `docker-compose-personal.yml`
- Personal Edition: Docker Compose setup with SQLite, simplified configuration
- Daemon Mode: Background service with PID tracking, graceful shutdown, status monitoring
- CLI Commands: `atom-os daemon`, `atom-os status`, `atom-os stop`, `atom-os execute <command>`
- Agent Control REST API: Trigger agents, stop execution, monitor status
- systemd Service: Auto-start on Linux systems
- Host Shell Access: Optional filesystem mount with AUTONOMOUS gate, command whitelist
- Vector Embeddings: FastEmbed (local) with 384-dim vectors, 10-20ms generation time
- **Performance**: <10ms liveness probe, <100ms readiness probe (includes DB check)
- **Docs**: `docs/archive/legacy/PERSONAL_EDITION_GUIDE.md`

### 23. Code Quality & Type Hints ✨
**Files**: `backend/docs/CODE_QUALITY_STANDARDS.md`, `mypy.ini`, `.github/workflows/ci.yml`
- MyPy configuration for static type checking
- Type hints on critical service functions (agent governance, LLM, episodic memory)
- CODE_QUALITY_STANDARDS.md (809 lines) covering Python standards, error handling, testing patterns
- API response standards, database session patterns, import ordering
- CI Integration: Type checking runs on every push via GitHub Actions

### 24. E2E Testing Infrastructure ✨ (Phase 234)
**Files**: `backend/tests/e2e_ui/conftest.py`, `backend/tests/e2e_ui/fixtures/`, `backend/tests/e2e_ui/pages/`
- **486 E2E test functions** across authentication and agent critical paths
- API-first authentication: 10-100x faster than UI login (JWT tokens in localStorage)
- Worker-based database isolation for parallel test execution
- Page Object Model for maintainable UI abstractions
- Comprehensive fixture suite: auth, database, API, factory fixtures
- **Performance**: Tests complete in under 10 minutes with parallel execution
- **Coverage**: AUTH-01 through AUTH-07, AGNT-01 through AGNT-08
- **Docs**: `backend/tests/e2e_ui/README.md`

### 25. Advanced Skill Execution & Composition ✨
**Phase**: 60-advanced-skill-execution (February 19, 2026)
- Skill Marketplace: PostgreSQL-based with search, ratings, categories
- Dynamic Skill Loading: importlib-based hot-reload with watchdog file monitoring
- Skill Composition Engine: DAG workflows with NetworkX validation
- Auto-Installation: Python + npm with conflict detection and rollback
- E2E Supply Chain Security: 36 tests covering typosquatting, dependency confusion, postinstall malware
- **Performance**: Package installation <5s, skill loading <1s, marketplace search <100ms, workflow validation <50ms
- **Tests**: 82+ tests across 6 test files
- **Docs**: `docs/ADVANCED_SKILL_EXECUTION.md`, `docs/SKILL_MARKETPLACE_GUIDE.md`, `docs/SKILL_COMPOSITION_PATTERNS.md`

### 26. GraphRAG & Entity Types System ✨
**Files**: `backend/core/graphrag_engine.py`, `backend/core/entity_type_service.py`, `backend/core/model_factory.py`
- **PostgreSQL-backed GraphRAG V2**: Stateless recursive CTEs for high-performance traversal (<100ms)
- **6 Canonical Entity Types**: user, workspace, team, task, ticket, formula with bidirectional sync
- **Dynamic Custom Entity Types**: JSON Schema-based runtime model creation with validation
- **LLM-Based Extraction**: Extract entities and relationships from unstructured text (documents, emails)
- **Local & Global Search**: Neighborhood traversal (depth-based) and community-based summarization
- **Entity Registry**: Centralized configuration for canonical-to-database mapping with field whitelisting
- **Community Detection**: NetworkX + Leiden algorithm for graph clustering
- **Performance**: Local search ~50-80ms, global search ~100-150ms, entity extraction ~2-3s
- **Tests**: 40+ tests across 4 test files
- **Docs**: `docs/GRAPHRAG_AND_ENTITY_TYPES.md`, `docs/GRAPHRAG_PORTED.md`, `docs/ai-world-model.md`

---

## Recent Major Changes

### Auto-Dev Module & Federation (April 10, 2026) ✨
Self-evolving agents with Memento-Skills (learn from failures) and AlphaEvolver (optimize via mutation). Federation enables multi-instance communication with X-Federation-Key headers.

[Auto-Dev Guide →](docs/guides/AUTO_DEV_USER_GUIDE.md) | [Federation Guide →](docs/guides/FEDERATION_INSTANCE_IDENTITY.md)

### Queen Agent & Marketplace (April 10, 2026) ✨
Structured workflow automation for repeatable business processes. Commercial marketplace at atomagentos.com for agents, skills, components, and domains.

[Queen Agent →](docs/QUEEN_AGENT.md) | [Marketplace →](docs/marketplace/)

### Phase 234: E2E Tests (March 24, 2026) ✨
486 E2E test functions across authentication and agent workflows. API-first auth (10-100x faster), worker-based DB isolation, Page Object Model.

[E2E Tests →](backend/tests/e2e_ui/README.md)

### Phase 68: Cognitive Tier System (Feb 20, 2026) ✨
5-tier LLM routing with cache-aware optimization (90% cost reduction), auto-escalation, MiniMax M2.5 support (~$1/M tokens). 100+ tests, production-ready.

[Cognitive Tiers →](docs/COGNITIVE_TIER_SYSTEM.md)

### Phase 35: Python Packages (Feb 19, 2026) ✨
Per-skill Docker images, vulnerability scanning (pip-audit + Safety), maturity-based access control. 117 tests, production-ready.

[Python Packages →](docs/PYTHON_PACKAGES.md)

### Earlier Phases ✨
- **Phase 25**: CLI Skills (6 built-in skills with AUTONOMOUS maturity)
- **Phase 21**: LLM Canvas Summaries (50-100 words for episodic memory)
- **Phase 20**: Canvas AI Context (hidden accessibility trees, TypeScript definitions)
- **Phase 15**: Codebase Completion (CI/CD, health checks, monitoring)
- **Phase 14**: Community Skills (5,000+ OpenClaw/ClawHub integration)
- **Episodic Memory**: Hybrid PostgreSQL + LanceDB, 4 retrieval modes, graduation framework
- **Student Training**: 4-tier maturity routing, AI-powered training estimation

---

## Development Guidelines

### Feature Flags
```python
FEATURE_ENABLED = os.getenv("MY_FEATURE_ENABLED", "true").lower() == "true"
EMERGENCY_BYPASS = os.getenv("EMERGENCY_BYPASS", "false").lower() == "true"
```

### Error Handling
```python
try:
    # Operation
    pass
except Exception as e:
    logger.error(f"Operation failed: {e}")
    return {"success": False, "error": str(e)}
```

### Database Operations
```python
with SessionLocal() as db:
    agent = db.query(AgentRegistry).filter(...).first()
    execution = AgentExecution(...)
    db.add(execution)
    db.commit()
```

---

## Coding Standards & Best Practices

### Python Standards
- **Version**: Python 3.11+
- **Style**: PEP 8 compliant
- **Naming**: Classes: `PascalCase`, Functions: `snake_case`, Constants: `UPPER_SNAKE_CASE`
- **Type Hints**: Required for all function signatures (enforced by MyPy in CI)
- **Docstrings**: Google-style with Args/Returns sections
- **See**: `backend/docs/CODE_QUALITY_STANDARDS.md`

### Error Handling Patterns
```python
try:
    with SessionLocal() as db:
        agent = db.query(AgentRegistry).filter(...).first()
        db.add(agent)
        db.commit()
except Exception as e:
    logger.error(f"Operation failed: {e}")
    raise api_error(ErrorCode.DATABASE_ERROR, "Database operation failed", {"error": str(e)})
```

### Database Session Patterns
1. **Context Manager** (Service Layer):
   ```python
   with get_db_session() as db:
       agent = db.query(Agent).filter(Agent.id == agent_id).first()
   ```

2. **Dependency Injection** (API Routes):
   ```python
   @app.get("/agents/{agent_id}")
   def get_agent(agent_id: str, db: Session = Depends(get_db)):
       return db.query(Agent).filter(Agent.id == agent_id).first()
   ```

### API Response Standards
```python
# Success Response
{"success": True, "data": {...}, "message": "Operation successful", "timestamp": "2026-02-06T10:30:00.000Z"}

# Error Response
{"success": False, "error_code": "AGENT_NOT_FOUND", "message": "Agent with ID 'abc123' not found", "details": {"agent_id": "abc123"}}
```

### Testing Patterns
- Test files: `backend/tests/test_*.py`
- Test naming: `test_specific_behavior()`
- Always clean up test data in `finally` blocks
- Use mocks for external services (AsyncMock, MagicMock)

### TDD Patterns for Bug Fixes ✨
**Follow Test-Driven Development for ALL bug fixes** - See `docs/testing/BUG_FIX_PROCESS.md`

**Red-Green-Refactor Cycle:**
1. **Red:** Write failing test that reproduces the bug
2. **Green:** Write minimal fix to make test pass
3. **Refactor:** Improve code while tests pass

**Why TDD for Bug Fixes?**
- Prevents regression (tests ensure bugs don't reoccur)
- Documents intent (tests explain what code should do)
- Enables refactoring (safe improvements with test safety net)
- Catches root causes (tests reveal deeper issues)

**Example Bug Fix:**
```python
# RED: Write failing test
def test_agent_maturity_blocks_demotion():
    agent = AgentRegistry(id="test", maturity=AgentMaturity.AUTONOMOUS)
    service = AgentGovernanceService(db)
    with pytest.raises(ValueError):
        service.update_maturity("test", AgentMaturity.STUDENT)

# GREEN: Minimal fix
def update_maturity(self, agent_id: str, new_maturity: AgentMaturity):
    if self._is_demotion(agent.maturity, new_maturity):
        raise ValueError(f"Invalid maturity transition")
    agent.maturity = new_maturity

# REFACTOR: Improve code
def _is_demotion(self, current: AgentMaturity, new: AgentMaturity) -> bool:
    levels = {STUDENT: 1, INTERN: 2, SUPERVISED: 3, AUTONOMOUS: 4}
    return levels[new] < levels[current]
```

**Key Principles:**
- Never fix bug without failing test first
- Commit test before fix
- Keep fixes minimal and focused
- Run full test suite after each fix
- Document root cause and lessons learned

**Frontend Test Fixes (Jest/React Testing Library):**
```typescript
// RED: Failing test for missing element
test('render user avatar', () => {
  render(<UserProfile userId="123" />);
  expect(screen.getByRole('img', { name: /avatar/i })).toBeInTheDocument();
  // FAILS: "Unable to find an img with accessible name: /avatar/i"
});

// GREEN: Add missing prop or mock
test('render user avatar', () => {
  render(<UserProfile userId="123" showAvatar={true} />);
  expect(screen.getByRole('img', { name: /avatar/i })).toBeInTheDocument();
});

// REFACTOR: Extract reusable render helper
function renderUserProfile(props = {}) {
  return render(<UserProfile userId="123" {...props} />);
}
```

**Common Bug Fix Patterns:**
- **Input validation:** Add null/undefined checks
- **Edge cases:** Handle empty/zero/negative values
- **State mutation:** Copy objects before modifying
- **Integration issues:** Fix component communication
- **Timeout errors:** Add waitFor, increase timeouts, fake timers

### Import Order
```python
# 1. Standard library
import os
from datetime import datetime

# 2. Third-party
from fastapi import FastAPI
from sqlalchemy.orm import Session

# 3. Local imports
from core.agent_governance_service import AgentGovernanceService
from core.models import AgentRegistry
```

### Performance Patterns
- Use `GovernanceCache` for frequently accessed data (<1ms lookups)
- Async/await for I/O operations
- Connection pooling for databases
- Stream LLM responses via WebSocket

---

## Testing

### Unit & Integration Tests
```bash
# All tests
PYTHONPATH=/Users/rushiparikh/projects/atom/backend pytest tests/ -v

# Specific tests
pytest tests/test_governance_streaming.py -v
pytest tests/test_browser_automation.py -v
pytest tests/test_governance_performance.py -v -s

# With coverage
pytest tests/ --cov=core --cov-report=html
```

### E2E UI Tests ✨
```bash
# E2E Test Infrastructure (Phase 234)
cd backend/tests/e2e_ui

# Start E2E test environment (Docker Compose)
./scripts/start-e2e-env.sh

# Run all E2E tests
pytest backend/tests/e2e_ui/ -v

# Run with 4 parallel workers
pytest backend/tests/e2e_ui/ -v -n 4

# Run specific authentication E2E tests
pytest backend/tests/e2e_ui/tests/test_auth_login.py -v
pytest backend/tests/e2e_ui/tests/test_auth_jwt_validation.py -v
pytest backend/tests/e2e_ui/tests/test_auth_session.py -v
pytest backend/tests/e2e_ui/tests/test_auth_protected_routes.py -v

# Run agent workflow E2E tests
pytest backend/tests/e2e_ui/tests/test_agent_creation.py -v
pytest backend/tests/e2e_ui/tests/test_agent_streaming.py -v
pytest backend/tests/e2e_ui/tests/test_agent_concurrent.py -v
pytest backend/tests/e2e_ui/tests/test_agent_governance.py -v

# Run with Allure reporting
pytest backend/tests/e2e_ui/ -v --alluredir=allure-results
allure serve allure-results
```

**E2E Test Coverage** (486 test functions across 68 test files):
- **Authentication** (AUTH-01 to AUTH-07): Login/logout, JWT validation, session persistence, token refresh, mobile auth, API-first auth
- **Agent Workflows** (AGNT-01 to AGNT-08): Creation, registry, streaming, WebSocket reconnection, concurrent execution, governance enforcement, lifecycle, cross-platform

**See**: `backend/tests/e2e_ui/README.md`, `.planning/phases/234-authentication-and-agent-e2e/`

---

## Important File Locations

**Core Services**:
- `backend/core/agent_governance_service.py` - Agent governance
- `backend/core/agent_context_resolver.py` - Agent resolution
- `backend/core/governance_cache.py` - Performance cache
- `backend/core/llm/byok_handler.py` - LLM routing
- `backend/core/models.py` - Database models
- `backend/core/agent_world_model.py` - World Model & JIT Fact Provision
- `backend/core/graphrag_engine.py` - GraphRAG V2 (PostgreSQL-backed)
- `backend/core/entity_type_service.py` - Dynamic entity type management
- `backend/core/model_factory.py` - Runtime model creation for custom entities

**API Endpoints**:
- `backend/core/atom_agent_endpoints.py` - Chat/streaming
- `backend/api/canvas_routes.py` - Canvas/forms
- `backend/api/browser_routes.py` - Browser automation
- `backend/api/device_capabilities.py` - Device control
- `backend/api/deeplinks.py` - Deep linking
- `backend/api/admin/business_facts_routes.py` - Business Facts & JIT Citation Verification
- `backend/api/entity_type_routes.py` - Entity type CRUD operations
- `backend/api/graphrag_routes.py` - Graph search and ingestion

**Canvas & Accessibility**:
- `frontend-nextjs/hooks/useCanvasState.ts` - Canvas state hook
- `frontend-nextjs/components/canvas/types/index.ts` - Canvas state types
- `core/llm/canvas_summary_service.py` - LLM canvas summary service

**Tools**:
- `backend/tools/canvas_tool.py` - Canvas presentations
- `backend/tools/browser_tool.py` - Browser automation
- `backend/tools/device_tool.py` - Device capabilities
- `backend/tools/atom_cli_skill_wrapper.py` - CLI command subprocess wrapper

**Skills**:
- `backend/skills/atom-cli/` - CLI skills SKILL.md files (daemon, status, start, stop, execute, config)
- `backend/core/skill_adapter.py` - Community Skills integration

**E2E Testing** ✨:
- `backend/tests/e2e_ui/README.md` - E2E test infrastructure guide
- `backend/tests/e2e_ui/conftest.py` - Pytest fixtures and configuration
- `backend/tests/e2e_ui/fixtures/auth_fixtures.py` - API-first authentication (10-100x faster)
- `backend/tests/e2e_ui/pages/page_objects.py` - Page Object Model (LoginPage, DashboardPage, ChatPage)
- `docs/testing/E2E_TESTING_PHASE_234.md` - Phase 234 test coverage summary (91 tests)

**BYOK Migration** ✨:
- `docs/ARCHITECTURE/BYOK_V6_MIGRATION_GUIDE.md` - v6.0 BYOK migration guide
- `.planning/REQUIREMENTS-v6.0-BYOK.md` - v6.0 BYOK requirements (31 requirements)
- `backend/core/llm/llm_service.py` - Unified LLM service API (target for migration)

---

## Environment Variables

```bash
# Database
DATABASE_URL=sqlite:///./atom_dev.db  # Personal Edition default
# DATABASE_URL=postgresql://user:pass@localhost/atom  # Production

# Governance
STREAMING_GOVERNANCE_ENABLED=true
CANVAS_GOVERNANCE_ENABLED=true
FORM_GOVERNANCE_ENABLED=true
BROWSER_GOVERNANCE_ENABLED=true
EMERGENCY_GOVERNANCE_BYPASS=false

# Browser
BROWSER_HEADLESS=true

# LLM Providers
OPENAI_API_KEY=sk-...
ANTHROPIC_API_KEY=sk--...
MINIMAX_API_KEY=...  # Optional: MiniMax M2.7 (204K context, OpenAI-compatible)

# Application
PORT=8000
LOG_LEVEL=INFO

# Monitoring (Production)
PROMETHEUS_ENABLED=true
STRUCTLOG_LEVEL=INFO
HEALTH_CHECK_DISK_THRESHOLD_GB=1

# Personal Edition
ATOM_HOST_MOUNT_ENABLED=false  # Enable host filesystem access (AUTONOMOUS only)

# Vector Embeddings (Personal Edition defaults)
EMBEDDING_PROVIDER=fastembed
FASTEMBED_MODEL=BAAI/bge-small-en-v1.5
LANCEDB_PATH=./data/lancedb
```

---

## Database Migrations

```bash
alembic revision -m "description"    # Create migration
alembic upgrade head                  # Upgrade to latest
alembic downgrade -1                  # Downgrade one step
alembic current                        # Check current version
alembic history                        # View history
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
| Health liveness probe | <10ms | 2ms P50, 10ms P99 |
| Health readiness probe | <100ms | 15ms P50, 40ms P99 |
| Prometheus metrics scrape | <50ms | 8ms P50, 25ms P99 |
| Vector embedding generation | <20ms | 10-20ms (FastEmbed) |

---

## Key Concepts

1. **Multi-Agent Architecture** - Specialized agents with different maturity levels
2. **Governance First** - Every AI action is attributable, governable, and auditable
3. **Single-Tenant** - No workspace isolation, global dataset
4. **Graceful Degradation** - Log errors but allow requests if governance fails
5. **Performance Matters** - Cache provides sub-millisecond performance
6. **Observability** - Health checks, metrics, and structured logs for production monitoring
7. **E2E Testing Excellence** - 486 E2E test functions with API-first auth (10-100x faster), worker isolation, and parallel execution
8. **Personal Edition** - Local deployment option with simplified setup (Docker Compose + SQLite)
9. **Type Safety** - MyPy type checking enforced in CI for code quality

---

## Quick Reference Commands

```bash
# Development
python -m uvicorn main:app --reload --port 8000

# Daemon mode (Personal Edition)
atom-os daemon              # Start background service
atom-os status              # Check daemon status
atom-os stop                # Stop daemon
atom-os execute <command>   # Run on-demand

# Health checks
curl http://localhost:8000/health/live    # Liveness probe
curl http://localhost:8000/health/ready   # Readiness probe (DB + disk)
curl http://localhost:8000/health/metrics # Prometheus metrics

# Canvas State API (browser console)
window.atom.canvas.getState('canvas-id')
window.atom.canvas.getAllStates()

# Cognitive Tier System
python -c "from core.llm.cognitive_tier_system import CognitiveClassifier; print(CognitiveClassifier().classify('hello world'))"
curl -X GET "/api/v1/cognitive-tier/compare-tiers"
curl -X GET "/api/v1/cognitive-tier/estimate-cost?prompt=test&estimated_tokens=100"

# GraphRAG & Entity Types
python -c "from core.graphrag_engine import graphrag_engine; print(graphrag_engine.local_search('default', 'John Doe', depth=2))"
curl -X POST "/api/v1/graph/search/local" -d '{"query": "Project Alpha", "depth": 2}'
curl -X POST "/api/v1/entity-types" -d '{"slug": "invoice", "display_name": "Invoice", "json_schema": {...}}'
curl -X GET "/api/v1/entity-types?is_active=true"

# Intent Classification & Fleet Admiral
python -c "from core.intent_classifier import IntentClassifier; print(IntentClassifier().classify_intent('Research competitors and build Slack integration'))"
python -c "from core.atom_meta_agent import AtomMetaAgent; print(AtomMetaAgent().spawn_agent('finance_analyst'))"
curl -X POST "/api/v1/agent/route" -d '{"request": "Analyze sales data and create marketing strategy"}'

# Playwright
playwright install chromium

# Database
alembic upgrade head
alembic current
alembic history

# Git
git status
git add .
git commit -m "feat: description"
git push origin main

# Logs
tail -f logs/atom.log
grep "governance" logs/atom.log | tail -100

# E2E Tests (Phase 234)
cd backend/tests/e2e_ui && ./scripts/start-e2e-env.sh  # Start test environment
pytest backend/tests/e2e_ui/ -v                          # Run all E2E tests
pytest backend/tests/e2e_ui/ -v -n 4                     # Run with 4 workers (10x faster)
pytest backend/tests/e2e_ui/tests/test_auth_login.py -v # Run specific test file
allure serve allure-results                              # View Allure reports

# Personal Edition (Docker)
docker-compose -f docker-compose-personal.yml up -d
docker-compose -f docker-compose-personal.yml logs -f
docker-compose -f docker-compose-personal.yml down
```

---

## Summary

Atom is an AI-powered automation platform with multi-agent governance, episodic memory, real-time guidance, and production-ready monitoring. **Key**: Always think about **agent attribution** and **governance** when working with any AI feature.

**Production-ready**: CI/CD pipeline, health checks, Prometheus metrics, comprehensive documentation, type safety enforcement, and 486 E2E test functions covering authentication and agent critical paths.

**Personal Edition Available**: Run Atom locally with Docker Compose for personal automation and development (see `docs/archive/legacy/PERSONAL_EDITION_GUIDE.md`).

---

*For comprehensive documentation, see `docs/` directory, `backend/docs/` for operational guides, and test files for usage examples.*
