# Atom - AI-Powered Business Automation Platform

> **Project Context**: Atom is an intelligent business automation and integration platform that uses AI agents to help users automate workflows, integrate services, and manage business operations.

**Last Updated**: March 7, 2026

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
- `health_routes.py` - Health check endpoints
- `monitoring.py` - Prometheus metrics and structured logging
- `cli/daemon.py` - Daemon mode for background agent execution
- `useCanvasState.ts` - Canvas state subscription hook
- `canvas/types/index.ts` - Canvas state type definitions
- `core/llm/canvas_summary_service.py` - LLM canvas summary service

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
- **Docs**: `docs/CANVAS_IMPLEMENTATION_COMPLETE.md`, `docs/AGENT_GUIDANCE_IMPLEMENTATION.md`

### 5. Python Package Support ✨ (Phase 35)
**Files**: `core/package_governance_service.py`, `core/package_dependency_scanner.py`, `core/package_installer.py`
- Per-skill Docker images with dedicated packages
- Vulnerability scanning using pip-audit + Safety
- Maturity-based access control (STUDENT blocked, INTERN requires approval)
- Container security (network disabled, read-only filesystem, resource limits)
- **Performance**: <5min image build, <1ms permission checks
- **Tests**: 117 tests across 7 test files
- **Docs**: `docs/PYTHON_PACKAGES.md`, `docs/PACKAGE_SECURITY.md`

### 6. Canvas AI Accessibility System ✨
**Files**: `frontend-nextjs/hooks/useCanvasState.ts`, `docs/CANVAS_AI_ACCESSIBILITY.md`
- Hidden accessibility trees exposing canvas state as JSON
- Canvas State API: `window.atom.canvas.getState()`, `getAllStates()`, `subscribe()`
- TypeScript type definitions for all 7 canvas types
- **Performance**: <10ms serialization overhead per render

### 7. LLM Canvas Summaries ✨
**Files**: `core/llm/canvas_summary_service.py`, `docs/LLM_CANVAS_SUMMARIES.md`
- LLM-generated summaries (50-100 words) for enhanced episodic memory
- Support for all 7 canvas types with specialized prompts
- Summary cache by canvas state hash
- **Benefits**: Better episode retrieval, agent learning, semantic search

### 8. BYOK Cognitive Tier System ✨ (Phase 68)
**Files**: `core/llm/cognitive_tier_system.py`, `core/llm/cache_aware_router.py`, `core/llm/escalation_manager.py`
- 5-tier intelligent LLM routing (Micro, Standard, Versatile, Heavy, Complex)
- Multi-factor classification: token count + semantic complexity + task type
- Cache-aware routing: 90% cost reduction with prompt caching
- Auto-escalation: Quality-based tier escalation with 5-min cooldown
- MiniMax M2.5: Standard tier option at ~$1/M tokens
- **Performance**: <100ms routing, <50ms classification, 30%+ cost savings
- **Tests**: 100+ tests across 8 test files
- **Docs**: `docs/COGNITIVE_TIER_SYSTEM.md`

### 9. Browser Automation System
**Files**: `tools/browser_tool.py`, `api/browser_routes.py`
- Web scraping, form filling, screenshots via Playwright CDP
- **Governance**: INTERN+ required
- **Docs**: `docs/BROWSER_AUTOMATION.md`, `docs/BROWSER_QUICK_START.md`

### 10. Device Capabilities System
**Files**: `tools/device_tool.py`, `api/device_capabilities.py`
- Camera (INTERN+), Screen Recording (SUPERVISED+), Location (INTERN+), Notifications (INTERN+), Command Execution (AUTONOMOUS only)
- **Docs**: `docs/DEVICE_CAPABILITIES.md`

### 11. Atom CLI Skills System ✨
**Files**: `backend/tools/atom_cli_skill_wrapper.py`, `backend/skills/atom-cli/` (6 SKILL.md files)
- 6 built-in skills: atom-daemon, atom-status, atom-start, atom-stop, atom-execute, atom-config
- AUTONOMOUS maturity for daemon control, STUDENT for read-only operations
- Subprocess wrapper with 30s timeout, structured output, error handling
- **Docs**: `docs/ATOM_CLI_SKILLS_GUIDE.md`

### 12. Deep Linking System
**Files**: `core/deeplinks.py`, `api/deeplinks.py`
- `atom://agent/{id}`, `atom://workflow/{id}`, `atom://canvas/{id}`, `atom://tool/{name}`
- **Docs**: `docs/DEEPLINK_IMPLEMENTATION.md`

### 13. Enhanced Feedback System
**Files**: `api/feedback_enhanced.py`, `api/feedback_analytics.py`
- Thumbs up/down, star ratings, corrections, analytics dashboard
- Batch operations, promotion suggestions, A/B testing

### 14. Student Agent Training System ✨
**Files**: `core/trigger_interceptor.py`, `core/student_training_service.py`, `core/meta_agent_training_orchestrator.py`
- Four-tier maturity routing: STUDENT → INTERN → SUPERVISED → AUTONOMOUS
- AI-based training duration estimation with historical data analysis
- Real-time supervision for SUPERVISED agents with intervention support
- Action proposal workflow for INTERN agents (human approval required)
- **Performance**: <5ms routing decisions using GovernanceCache
- **Database**: 4 new models (BlockedTriggerContext, AgentProposal, SupervisionSession, TrainingSession)
- **API**: 20+ REST endpoints covering training, proposals, and supervision
- **Tests**: `tests/test_trigger_interceptor.py` (11 tests)
- **Docs**: `docs/STUDENT_AGENT_TRAINING_IMPLEMENTATION.md`

### 15. Database Models
**File**: `core/models.py`
- Key models: AgentRegistry, AgentExecution, AgentFeedback, CanvasAudit, BrowserSession, DeviceSession, DeepLinkAudit, ChatSession
- **NEW**: AgentOperationTracker, AgentRequestLog, ViewOrchestrationState, OperationErrorResolution
- **NEW**: BlockedTriggerContext, AgentProposal, SupervisionSession, TrainingSession
- **NEW**: Episode, EpisodeSegment, EpisodeAccessLog (Episodic Memory with graduation tracking)
- **NEW**: CommunitySkill, SkillSecurityScan, SkillExecution (Community Skills with security validation)

### 16. Episodic Memory & Graduation Framework ✨
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
- **Docs**: `docs/EPISODIC_MEMORY_IMPLEMENTATION.md`, `docs/AGENT_GRADUATION_GUIDE.md`, `docs/CANVAS_FEEDBACK_EPISODIC_MEMORY.md`

### 17. World Model & Business Facts ✨
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

### 18. Production Monitoring & Observability ✨
**Files**: `api/health_routes.py`, `core/monitoring.py`, `tests/test_health_routes.py`
- Health check endpoints: `/health/live` (liveness), `/health/ready` (readiness with DB/disk checks)
- Prometheus metrics: HTTP requests, agent executions, skill executions, DB queries
- Structured logging: JSON output with structlog, context binding (request_id, agent_id, skill_id)
- Performance benchmarks: <10ms (live), <100ms (ready), <50ms (metrics scrape)
- Orchestration Ready: Kubernetes/ECS health check configurations documented
- Grafana Integration: Dashboard setup instructions provided
- **Tests**: 13 tests covering liveness, readiness, metrics, and performance
- **Docs**: `backend/docs/MONITORING_SETUP.md`

### 19. CI/CD Pipeline & Deployment ✨
**File**: `.github/workflows/deploy.yml`
- Automated testing, Docker builds, staging/production deployments
- Jobs: test → build → deploy-staging (auto) → deploy-production (manual approval) → verify
- Automated rollback on failure with one-line command
- Database backup before production deployment
- Smoke tests for agent execution, canvas presentation, skill execution
- Metrics monitoring (error rate, latency) with automatic alerts
- Slack notifications for deployment status
- **Docs**: `backend/docs/DEPLOYMENT_RUNBOOK.md`, `backend/docs/OPERATIONS_GUIDE.md`, `backend/docs/TROUBLESHOOTING.md`

### 20. Personal Edition & Daemon Mode ✨
**Files**: `cli/daemon.py`, `cli/main.py`, `.env.personal`, `docker-compose-personal.yml`
- Personal Edition: Docker Compose setup with SQLite, simplified configuration
- Daemon Mode: Background service with PID tracking, graceful shutdown, status monitoring
- CLI Commands: `atom-os daemon`, `atom-os status`, `atom-os stop`, `atom-os execute <command>`
- Agent Control REST API: Trigger agents, stop execution, monitor status
- systemd Service: Auto-start on Linux systems
- Host Shell Access: Optional filesystem mount with AUTONOMOUS gate, command whitelist
- Vector Embeddings: FastEmbed (local) with 384-dim vectors, 10-20ms generation time
- **Performance**: <10ms liveness probe, <100ms readiness probe (includes DB check)
- **Docs**: `docs/PERSONAL_EDITION.md`, `docs/VECTOR_EMBEDDINGS.md`

### 21. Code Quality & Type Hints ✨
**Files**: `backend/docs/CODE_QUALITY_STANDARDS.md`, `mypy.ini`, `.github/workflows/ci.yml`
- MyPy configuration for static type checking
- Type hints on critical service functions (agent governance, LLM, episodic memory)
- CODE_QUALITY_STANDARDS.md (9,412 lines) covering Python standards, error handling, testing patterns
- API response standards, database session patterns, import ordering
- CI Integration: Type checking runs on every push via GitHub Actions

### 22. Advanced Skill Execution & Composition ✨
**Phase**: 60-advanced-skill-execution (February 19, 2026)
- Skill Marketplace: PostgreSQL-based with search, ratings, categories
- Dynamic Skill Loading: importlib-based hot-reload with watchdog file monitoring
- Skill Composition Engine: DAG workflows with NetworkX validation
- Auto-Installation: Python + npm with conflict detection and rollback
- E2E Supply Chain Security: 36 tests covering typosquatting, dependency confusion, postinstall malware
- **Performance**: Package installation <5s, skill loading <1s, marketplace search <100ms, workflow validation <50ms
- **Tests**: 82+ tests across 6 test files
- **Docs**: `docs/ADVANCED_SKILL_EXECUTION.md`, `docs/SKILL_MARKETPLACE_GUIDE.md`, `docs/SKILL_COMPOSITION_PATTERNS.md`

---

## Recent Major Changes

### Phase 68: BYOK Cognitive Tier System (Feb 20, 2026) ✨
- 5-tier cognitive classification (token count + semantic complexity + task type)
- Cache-aware routing with 90% cost reduction
- Automatic escalation on quality threshold breaches
- MiniMax M2.5 integration in Standard tier (~$1/M tokens)
- **Status**: ✅ COMPLETE - All 8 plans executed, 100+ tests, production-ready
- **See**: `docs/COGNITIVE_TIER_SYSTEM.md`

### Phase 35: Python Package Support (Feb 19, 2026) ✨
- Per-skill Docker images with dedicated packages (no dependency conflicts)
- Vulnerability scanning using pip-audit + Safety
- STUDENT blocked, INTERN requires approval, SUPERVISED/AUTONOMOUS need approved packages
- CVE vulnerability detection with pip-audit and Safety before installation
- **Status**: ✅ COMPLETE - All 7 plans executed, 117 tests, production-ready
- **See**: `docs/PYTHON_PACKAGES.md`, `docs/PACKAGE_SECURITY.md`

### Phase 25: Atom CLI as OpenClaw Skills (Feb 18, 2026) ✨
- 6 built-in skills with AUTONOMOUS maturity for daemon control
- Subprocess wrapper with 30s timeout, structured output, error handling
- Integration with Community Skills framework (import, security scan, governance)
- **Docs**: `docs/ATOM_CLI_SKILLS_GUIDE.md`

### Phase 21: LLM Canvas Summaries (Feb 18, 2026) ✨
- LLM-generated summaries (50-100 words) for enhanced episodic memory
- Support for all 7 canvas types with specialized prompts
- Quality metrics: >80% semantic richness, 0% hallucination target
- **Docs**: `docs/LLM_CANVAS_SUMMARIES.md`

### Phase 20: Canvas AI Context (Feb 18, 2026) ✨
- Hidden accessibility trees with role='log', aria-live exposing JSON state
- Global API: `window.atom.canvas.getState()`, `getAllStates()`, `subscribe()`
- TypeScript definitions for all 7 canvas types
- **Performance**: <10ms serialization overhead per render
- **Docs**: `docs/CANVAS_AI_ACCESSIBILITY.md`, `docs/CANVAS_STATE_API.md`

### Phase 15: Codebase Completion & Quality Assurance (Feb 16, 2026) ✨
- Production-ready codebase with comprehensive documentation
- Health check endpoints, Prometheus metrics, structured logging
- CI/CD pipeline with GitHub Actions, deployment runbooks
- MyPy configuration, type hints on critical service functions
- **Docs**: `backend/docs/API_DOCUMENTATION.md`, `backend/docs/DEPLOYMENT_RUNBOOK.md`, `backend/docs/CODE_QUALITY_STANDARDS.md`

### Personal Edition & Universal Agent Execution (Feb 16, 2026) ✨
- Docker Compose setup with SQLite database, simplified `.env.personal` configuration
- Daemon Mode: Background service with PID tracking, graceful shutdown, status monitoring
- CLI Commands: `atom-os daemon`, `atom-os status`, `atom-os stop`, `atom-os execute <command>`
- Agent Control REST API: Endpoints for triggering agents, stopping execution, monitoring status
- Host Shell Access: Optional filesystem mount with AUTONOMOUS maturity gate, command whitelist
- **Docs**: `docs/PERSONAL_EDITION.md`, `docs/VECTOR_EMBEDDINGS.md`

### Phase 14: Community Skills Integration (Feb 16, 2026) ✨
- Enable Atom agents to use 5,000+ OpenClaw/ClawHub community skills
- Three Major Components: Skill Adapter, Hazard Sandbox, Skills Registry
- Lenient parsing with auto-fix for malformed SKILL.md files
- 21+ malicious pattern detection + GPT-4 semantic analysis
- Governance integration: STUDENT blocked from Python skills, INTERN+ require approval
- Episodic memory integration: All skill executions create EpisodeSegments
- **Status**: ✅ COMPLETE - All 3 plans executed, verification passed (13/13 criteria)
- **See**: `.planning/phases/14-community-skills-integration/`

### Canvas & Feedback Integration with Episodic Memory (Feb 4, 2026) ✨
- Metadata-only linkage: Episodes store lightweight references to CanvasAudit and AgentFeedback records
- Canvas-aware episodes: Track all canvas interactions (present, submit, close, update, execute)
- Feedback-linked episodes: Aggregate user feedback scores (-1.0 to 1.0) for retrieval weighting
- Enriched sequential retrieval: Episodes include canvas_context and feedback_context by default
- Feedback-weighted retrieval: Positive feedback gets +0.2 boost, negative gets -0.3 penalty
- **Performance**: <100ms retrieval overhead, ~100 bytes storage per episode
- **See**: `docs/CANVAS_FEEDBACK_EPISODIC_MEMORY.md`

### Episodic Memory & Graduation Framework (Feb 3, 2026) ✨
- Comprehensive episodic memory system with hybrid PostgreSQL + LanceDB storage
- Automatic episode segmentation using time gaps, topic changes, and task completion detection
- Four retrieval modes: Temporal (time-based), Semantic (vector search), Sequential (full episode), Contextual (hybrid)
- Episode lifecycle management: decay, consolidation, and archival to cold storage
- Graduation Exam Framework: Validate agent promotion readiness with 100% Constitutional Compliance
- Readiness Score calculation: 40% episode count, 30% intervention rate, 30% constitutional compliance
- **See**: `docs/EPISODIC_MEMORY_IMPLEMENTATION.md`, `docs/AGENT_GRADUATION_GUIDE.md`

### Student Agent Training System (Feb 2, 2026) ✨
- Four-tier maturity-based routing prevents STUDENT agents from automated triggers
- AI-powered training duration estimation with user override capability
- Real-time supervision for SUPERVISED agents with pause/correct/terminate controls
- Action proposal workflow for INTERN agents requires human approval before execution
- Centralized TriggerInterceptor with <5ms routing decisions
- **See**: `docs/STUDENT_AGENT_TRAINING_IMPLEMENTATION.md`

### Real-Time Agent Guidance System (Feb 2, 2026) ✨
- Complete agent operation visibility with live progress tracking
- Multi-view orchestration (browser/terminal/canvas) with layout management
- Smart error resolution with 7 error categories and learning feedback
- Interactive permission/decision requests with full audit trail
- Integration guidance for OAuth flows
- **See**: `docs/CANVAS_IMPLEMENTATION_COMPLETE.md`

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

---

## Important File Locations

**Core Services**:
- `backend/core/agent_governance_service.py` - Agent governance
- `backend/core/agent_context_resolver.py` - Agent resolution
- `backend/core/governance_cache.py` - Performance cache
- `backend/core/llm/byok_handler.py` - LLM routing
- `backend/core/models.py` - Database models
- `backend/core/agent_world_model.py` - World Model & JIT Fact Provision

**API Endpoints**:
- `backend/core/atom_agent_endpoints.py` - Chat/streaming
- `backend/api/canvas_routes.py` - Canvas/forms
- `backend/api/browser_routes.py` - Browser automation
- `backend/api/device_capabilities.py` - Device control
- `backend/api/deeplinks.py` - Deep linking
- `backend/api/admin/business_facts_routes.py` - Business Facts & JIT Citation Verification

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
7. **Personal Edition** - Local deployment option with simplified setup (Docker Compose + SQLite)
8. **Type Safety** - MyPy type checking enforced in CI for code quality

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

# Personal Edition (Docker)
docker-compose -f docker-compose-personal.yml up -d
docker-compose -f docker-compose-personal.yml logs -f
docker-compose -f docker-compose-personal.yml down
```

---

## Summary

Atom is an AI-powered automation platform with multi-agent governance, episodic memory, real-time guidance, and production-ready monitoring. **Key**: Always think about **agent attribution** and **governance** when working with any AI feature.

**Production-ready**: CI/CD pipeline, health checks, Prometheus metrics, comprehensive documentation, and type safety enforcement.

**Personal Edition Available**: Run Atom locally with Docker Compose for personal automation and development (see `docs/PERSONAL_EDITION.md`).

---

*For comprehensive documentation, see `docs/` directory, `backend/docs/` for operational guides, and test files for usage examples.*
