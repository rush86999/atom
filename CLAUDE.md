# Atom - AI-Powered Business Automation Platform

> **Project Context**: Atom is an intelligent business automation and integration platform that uses AI agents to help users automate workflows, integrate services, and manage business operations.

**Last Updated**: February 16, 2026

---

## Quick Overview

**What is Atom?**
- AI-powered workflow automation platform with multi-agent system and governance
- Real-time streaming LLM responses with multi-provider support
- Canvas-based visual presentations with custom components
- Browser automation (CDP) and device capabilities
- Enhanced feedback system with A/B testing
- Mobile support architecture (React Native)
- **✨ Episodic Memory & Graduation Framework** - Agent learning from past experiences with constitutional compliance validation
- **✨ Personal Edition** - Run Atom on your local computer with Docker
- **✨ Production-Ready** - CI/CD pipeline, monitoring, health checks, and deployment runbooks

**Tech Stack**: Python 3.11, FastAPI, SQLAlchemy 2.0, SQLite/PostgreSQL, Multi-provider LLM, Playwright, Redis (WebSocket), Alembic

**Key Directories**: `backend/core/`, `backend/api/`, `backend/tools/`, `backend/tests/`, `mobile/`, `docs/`

**Key Services**:
- `agent_governance_service.py` - Agent lifecycle and permissions
- `trigger_interceptor.py` - Maturity-based trigger routing
- `student_training_service.py` - Training proposals and sessions
- `supervision_service.py` - Real-time supervision monitoring
- `governance_cache.py` - High-performance caching (<1ms lookups)
- **✨ `health_routes.py`** - Health check endpoints (`/health/live`, `/health/ready`, `/health/metrics`)
- **✨ `monitoring.py`** - Prometheus metrics and structured logging
- **✨ `cli/daemon.py`** - Daemon mode for background agent execution

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

**Key**: STUDENT agents learn through guided training scenarios before gaining autonomy.

### Action Complexity
- **1 (LOW)**: Presentations → STUDENT+ | **2 (MODERATE)**: Streaming → INTERN+ | **3 (HIGH)**: State changes → SUPERVISED+ | **4 (CRITICAL)**: Deletions → AUTONOMOUS only

---

## Core Components

### 1. Agent Governance System
- **Files**: `agent_governance_service.py`, `agent_context_resolver.py`, `governance_cache.py`
- Manages agent lifecycle, permissions, and maturity
- <1ms cached governance checks

### 2. Streaming LLM Integration
- **Files**: `llm/byok_handler.py`, `atom_agent_endpoints.py`
- Multi-provider support (OpenAI, Anthropic, DeepSeek, Gemini)
- Token-by-token streaming via WebSocket

### 3. Canvas Presentation System
- **Files**: `tools/canvas_tool.py`, `api/canvas_routes.py`
- Charts (line, bar, pie), markdown, forms with governance

### 3.5 Real-Time Agent Guidance System ✨ NEW
- **Files**: `tools/agent_guidance_canvas_tool.py`, `core/view_coordinator.py`, `core/error_guidance_engine.py`, `core/agent_request_manager.py`, `api/agent_guidance_routes.py`
- **Purpose**: Real-time agent operation visibility with learning integration
- **Features**:
  - Live operation tracking with progress bars and step-by-step updates
  - Contextual explanations (what/why/next) in plain English
  - Multi-view orchestration (browser/terminal/canvas) with layout management
  - Smart error resolution with 7 error categories and learning feedback
  - Interactive permission/decision requests with full audit trail
  - Integration guidance for OAuth flows with real-time status
  - Complete governance integration and bidirectional learning
- **Frontend**: `frontend-nextjs/components/canvas/` (5 React components)
- **Docs**: `docs/CANVAS_IMPLEMENTATION_COMPLETE.md`, `docs/AGENT_GUIDANCE_IMPLEMENTATION.md`
- **Tests**: `tests/test_agent_guidance_canvas.py`, `tests/test_view_coordinator.py`, `tests/test_error_guidance.py`

### 4. Browser Automation System
- **Files**: `tools/browser_tool.py`, `api/browser_routes.py`
- Web scraping, form filling, screenshots via Playwright CDP
- **Governance**: INTERN+ required
- **Docs**: `docs/BROWSER_AUTOMATION.md`, `docs/BROWSER_QUICK_START.md`

### 5. Device Capabilities System
- **Files**: `tools/device_tool.py`, `api/device_capabilities.py`
- Camera (INTERN+), Screen Recording (SUPERVISED+), Location (INTERN+), Notifications (INTERN+), Command Execution (AUTONOMOUS only)
- **Docs**: `docs/DEVICE_CAPABILITIES.md`

### 6. Deep Linking System
- **Files**: `core/deeplinks.py`, `api/deeplinks.py`
- `atom://agent/{id}`, `atom://workflow/{id}`, `atom://canvas/{id}`, `atom://tool/{name}`
- **Docs**: `docs/DEEPLINK_IMPLEMENTATION.md`

### 7. Enhanced Feedback System
- **Files**: `api/feedback_enhanced.py`, `api/feedback_analytics.py`
- Thumbs up/down, star ratings, corrections, analytics dashboard
- Batch operations, promotion suggestions, A/B testing

### 8. Student Agent Training System ✨ NEW
- **Files**: `core/trigger_interceptor.py`, `core/student_training_service.py`, `core/meta_agent_training_orchestrator.py`, `core/proposal_service.py`, `core/supervision_service.py`, `api/maturity_routes.py`
- **Purpose**: Prevent STUDENT agents from automated triggers and route through graduated learning pathway
- **Features**:
  - Four-tier maturity routing: STUDENT → INTERN → SUPERVISED → AUTONOMOUS
  - AI-based training duration estimation with historical data analysis
  - Real-time supervision for SUPERVISED agents with intervention support
  - Action proposal workflow for INTERN agents (human approval required)
  - Comprehensive audit trail for all routing decisions
- **Performance**: <5ms routing decisions using GovernanceCache, <500ms proposal generation
- **Database**: 4 new models (BlockedTriggerContext, AgentProposal, SupervisionSession, TrainingSession)
- **API**: 20+ REST endpoints covering training, proposals, and supervision
- **Tests**: `tests/test_trigger_interceptor.py` (11 tests, all passing)
- **Docs**: `docs/STUDENT_AGENT_TRAINING_IMPLEMENTATION.md`

### 9. Database Models
- **File**: `core/models.py`
- Key models: AgentRegistry, AgentExecution, AgentFeedback, CanvasAudit, BrowserSession, DeviceSession, DeepLinkAudit, ChatSession
- **NEW**: AgentOperationTracker, AgentRequestLog, ViewOrchestrationState, OperationErrorResolution
- **NEW**: BlockedTriggerContext, AgentProposal, SupervisionSession, TrainingSession
- **✨ NEW**: Episode, EpisodeSegment, EpisodeAccessLog (Episodic Memory with graduation tracking)
- **✨ NEW**: CommunitySkill, SkillSecurityScan, SkillExecution (Community Skills with security validation)

### 10. Episodic Memory & Graduation Framework ✨ NEW
- **Files**: `episode_segmentation_service.py`, `episode_retrieval_service.py`, `episode_lifecycle_service.py`, `agent_graduation_service.py`
- **Purpose**: Agent learning from past experiences with constitutional compliance validation
- **✨ Canvas & Feedback Integration**: Episodes now include canvas presentations and user feedback for enriched reasoning
- **Features**:
  - Automatic episode segmentation (time gaps, topic changes, task completion)
  - Four retrieval modes: Temporal, Semantic, Sequential, Contextual
  - Hybrid PostgreSQL (hot) + LanceDB (cold) storage architecture
  - Episode lifecycle: decay, consolidation, archival
  - **Canvas-aware episodes**: Track canvas presentations (charts, forms, sheets) with action filtering
  - **Feedback-linked episodes**: Aggregate user feedback scores for retrieval weighting
  - **Enriched sequential retrieval**: Episodes include canvas_context and feedback_context
  - **Canvas type filtering**: Retrieve episodes by canvas type (sheets, charts, forms)
  - **Feedback-weighted analytics**: Prioritize high-rated episodes
  - **🎓 Graduation framework**: Validate agent promotion readiness using episodic memory
  - **Constitutional compliance**: Track interventions and validate against Knowledge Graph rules
  - **Audit trail**: EpisodeAccessLog for all memory operations
- **Graduation Criteria**:
  - STUDENT → INTERN: 10 episodes, 50% intervention rate, 0.70 constitutional score
  - INTERN → SUPERVISED: 25 episodes, 20% intervention rate, 0.85 constitutional score
  - SUPERVISED → AUTONOMOUS: 50 episodes, 0% intervention rate, 0.95 constitutional score
- **Performance**: Episode creation <5s, Temporal retrieval ~10ms, Semantic retrieval ~50-100ms
- **API**: 25+ REST endpoints for episodes, graduation, and canvas/feedback integration
- **Tests**: `test_episode_segmentation.py`, `test_episode_integration.py`, `test_episode_performance.py`, `test_agent_graduation.py`, `test_canvas_feedback_episode_integration.py`
- **Docs**: `docs/EPISODIC_MEMORY_IMPLEMENTATION.md`, `docs/EPISODIC_MEMORY_QUICK_START.md`, `docs/AGENT_GRADUATION_GUIDE.md`, `docs/CANVAS_FEEDBACK_EPISODIC_MEMORY.md`

### 11. Production Monitoring & Observability ✨ NEW
- **Files**: `api/health_routes.py`, `core/monitoring.py`, `tests/test_health_routes.py`
- **Purpose**: Production-ready health checks, metrics collection, and structured logging
- **Features**:
  - Health check endpoints: `/health/live` (liveness probe), `/health/ready` (readiness probe with DB/disk checks)
  - Prometheus metrics: HTTP requests, agent executions, skill executions, DB queries (with duration histograms)
  - Structured logging: JSON output with structlog, context binding (request_id, agent_id, skill_id)
  - Performance benchmarks: <10ms (live), <100ms (ready), <50ms (metrics scrape)
- **Orchestration Ready**: Kubernetes/ECS health check configurations documented
- **Grafana Integration**: Dashboard setup instructions provided
- **Alert Thresholds**: Configured for p95 latency monitoring
- **Tests**: 13 tests covering liveness, readiness, metrics, and performance
- **Docs**: `backend/docs/MONITORING_SETUP.md`

### 12. CI/CD Pipeline & Deployment ✨ NEW
- **File**: `.github/workflows/deploy.yml`
- **Purpose**: Automated testing, Docker builds, staging/production deployments
- **Jobs**:
  1. **test** - Unit tests, integration tests, 25% coverage threshold
  2. **build** - Docker image build with GitHub Actions cache and metadata
  3. **deploy-staging** - Automatic deployment on merge to main
  4. **deploy-production** - Manual approval required deployment
  5. **verify** - Post-deployment health checks, smoke tests, metrics monitoring
- **Features**:
  - Automated rollback on failure with one-line command
  - Database backup before production deployment
  - Smoke tests for agent execution, canvas presentation, skill execution
  - Metrics monitoring (error rate, latency) with automatic alerts
  - Slack notifications for deployment status
- **Docs**: `backend/docs/DEPLOYMENT_RUNBOOK.md`, `backend/docs/OPERATIONS_GUIDE.md`, `backend/docs/TROUBLESHOOTING.md`

### 13. Personal Edition & Daemon Mode ✨ NEW
- **Files**: `cli/daemon.py`, `cli/main.py`, `.env.personal`, `docker-compose-personal.yml`
- **Purpose**: Run Atom on local computers for personal automation and development
- **Features**:
  - **Personal Edition**: Docker Compose setup with SQLite, simplified configuration
  - **Daemon Mode**: Background service with PID tracking, graceful shutdown, status monitoring
  - **CLI Commands**: `atom-os daemon`, `atom-os status`, `atom-os stop`, `atom-os execute <command>`
  - **Agent Control REST API**: Trigger agents, stop execution, monitor status
  - **systemd Service**: Auto-start on Linux systems
  - **Host Shell Access**: Optional filesystem mount with AUTONOMOUS gate, command whitelist
  - **Vector Embeddings**: FastEmbed (local) with 384-dim vectors, 10-20ms generation time
- **Performance**: <10ms liveness probe, <100ms readiness probe (includes DB check)
- **Docs**: `docs/PERSONAL_EDITION.md`, `docs/VECTOR_EMBEDDINGS.md`, `test-embeddings.py`

### 14. Code Quality & Type Hints ✨ NEW
- **Files**: `backend/docs/CODE_QUALITY_STANDARDS.md`, `mypy.ini`, `.github/workflows/ci.yml`
- **Purpose**: Type safety, code quality standards, and automated testing
- **Features**:
  - MyPy configuration for static type checking
  - Type hints on critical service functions (agent governance, LLM, episodic memory)
  - CODE_QUALITY_STANDARDS.md (9,412 lines) covering Python standards, error handling, testing patterns
  - API response standards, database session patterns, import ordering
  - Performance patterns (GovernanceCache, async/await, connection pooling)
- **CI Integration**: Type checking runs on every push via GitHub Actions
- **Impact**: Catch type errors before runtime, improved IDE support, better code documentation

---

## Recent Major Changes

### Phase 15: Codebase Completion & Quality Assurance (Feb 16, 2026) ✨ NEW
- **5 Plans Completed**: Production-ready codebase with comprehensive documentation
- **Plan 01 - Test Infrastructure**: Standardized `db_session` fixture, fixed async test patterns, evaluated 13 production TODOs, 82.8% skill test pass rate
- **Plan 02 - Production Monitoring**: Health check endpoints (`/health/live`, `/health/ready`), Prometheus metrics, structured logging with JSON output
- **Plan 03 - API Documentation**: Comprehensive API documentation, OpenAPI enhancements, testing guide with 1,828 lines
- **Plan 04 - Deployment & Operations**: CI/CD pipeline (GitHub Actions), deployment runbook with rollback procedures, operations guide, troubleshooting documentation
- **Plan 05 - Type Hints & Code Quality**: MyPy configuration, type hints on critical service functions, CODE_QUALITY_STANDARDS.md (9,412 lines)
- **Files Created**: 12 documentation files, 3 new services (health_routes, monitoring), 1 CI/CD workflow
- **Impact**: Production-ready with observability, automated deployments, and comprehensive operational documentation
- **Docs**: `backend/docs/API_DOCUMENTATION.md`, `backend/docs/DEPLOYMENT_RUNBOOK.md`, `backend/docs/OPERATIONS_GUIDE.md`, `backend/docs/TROUBLESHOOTING.md`, `backend/docs/CODE_QUALITY_STANDARDS.md`

### Personal Edition & Universal Agent Execution (Feb 16, 2026) ✨ NEW
- **Personal Edition**: Run Atom on local computers with Docker Compose, SQLite database, simplified `.env.personal` configuration
- **Daemon Mode**: Background service management with PID tracking, graceful shutdown, status monitoring
- **CLI Commands**: `atom-os daemon`, `atom-os status`, `atom-os stop`, `atom-os execute <command>`
- **Agent Control REST API**: Endpoints for triggering agents, stopping execution, monitoring status
- **systemd Service**: Auto-start configuration for Linux systems
- **Host Shell Access**: Optional filesystem mount with AUTONOMOUS maturity gate, command whitelist, blocked dangerous commands
- **Vector Embeddings Guide**: Comprehensive documentation for FastEmbed (local) and OpenAI/Cohere (cloud) with performance benchmarks
- **Files**: `backend/cli/daemon.py`, `backend/cli/main.py`, `.env.personal`, `docker-compose-personal.yml`, `docs/PERSONAL_EDITION.md`, `docs/VECTOR_EMBEDDINGS.md`, `test-embeddings.py`

### Phase 14: Community Skills Integration (Feb 16, 2026) ✨ NEW
- **Purpose**: Enable Atom agents to use 5,000+ OpenClaw/ClawHub community skills while maintaining enterprise security
- **Three Major Components**:
  1. **Skill Adapter** - Parse SKILL.md files (YAML + Markdown), auto-detect prompt/Python skills, wrap in BaseTool
  2. **Hazard Sandbox** - Isolated Docker container for safe skill execution (no host access, resource limits, 5-min timeout)
  3. **Skills Registry** - Import UI, LLM security scanning, governance workflow (Untrusted → Active → Banned)
- **Implementation**: 3 plans completed with gap closure for episodic memory and graduation integration
- **Files Created**: 6 core services (skill_parser, skill_adapter, skill_sandbox, skill_security_scanner, skill_registry_service, skill_routes), 6 test files, 3 database models, 1 migration
- **Verification**: 13/13 success criteria verified (100%)
- **Key Features**:
  - Lenient parsing with auto-fix for malformed SKILL.md files
  - 21+ malicious pattern detection + GPT-4 semantic analysis
  - Governance integration: STUDENT blocked from Python skills, INTERN+ require approval
  - Episodic memory integration: All skill executions create EpisodeSegments
  - Graduation tracking: Skill usage metrics count toward agent readiness
- **Tests**: 82 tests across 6 test files, all passing
- **API**: 8 REST endpoints for import, list, execute, promote, episodes, learning-progress
- **Docs**: `docs/COMMUNITY_SKILLS.md` (comprehensive user guide), `docs/ATOM_VS_OPENCLAW.md`
- **Status**: ✅ COMPLETE - All 3 plans executed, verification passed (13/13 criteria)
- **See**: `.planning/phases/14-community-skills-integration/14-VERIFICATION.md`

### Documentation Fixes (Feb 6, 2026) ✨ NEW
- **Created**: CONTRIBUTING.md with comprehensive contribution guidelines
- **Fixed**: 5 broken links across docs/INDEX.md, MOBILE_QUICK_START.md, and MULTI_INTEGRATION_WORKFLOW_ENGINE.md
- **Impact**: All documentation navigation now functional
- **Files Modified**: 4 files, 1 file created
- **See**: CONTRIBUTING.md for contribution guidelines

### Incomplete Implementation Fixes (Feb 5, 2026) ✨ NEW
- **Backend**: Fixed workflow engine Slack and Asana action implementations
- **PDF Processing**: Implemented document listing, tag update, and image conversion
- **Mobile**: Implemented device permissions, improved auth flow, added SettingsScreen
- **All**: Removed mock/placeholder implementations, added real functionality
- **Files**: 9 files modified, 2 new files created
- **Tests**: Added comprehensive error handling and validation
- **Docs**: `backend/docs/INCOMPLETE_IMPLEMENTATIONS.md`
- **Impact**: Production-ready implementations replacing all critical stubs

### Canvas & Feedback Integration with Episodic Memory (Feb 4, 2026) ✨ NEW
- **Metadata-only linkage**: Episodes store lightweight references to CanvasAudit and AgentFeedback records
- **Canvas-aware episodes**: Track all canvas interactions (present, submit, close, update, execute) with type filtering
- **Feedback-linked episodes**: Aggregate user feedback scores (-1.0 to 1.0) for retrieval weighting
- **Enriched sequential retrieval**: Episodes include canvas_context and feedback_context by default
- **Canvas type filtering**: Retrieve episodes by canvas type (sheets, charts, forms) and action
- **Feedback-weighted retrieval**: Positive feedback gets +0.2 boost, negative gets -0.3 penalty
- **Agent decision-making**: Agents always fetch canvas/feedback context during episode recall
- **Coverage**: Supports all 7 built-in canvas types (generic, docs, email, sheets, orchestration, terminal, coding) and custom components
- **Performance**: <100ms retrieval overhead, ~100 bytes storage per episode
- **Files modified**: 7 files (models, 3 services, API routes, migration)
- **Tests**: 25+ comprehensive tests for creation, retrieval, enrichment, and performance
- **See**: `docs/CANVAS_FEEDBACK_EPISODIC_MEMORY.md`

### Episodic Memory & Graduation Framework (Feb 3, 2026) ✨ NEW
- Comprehensive episodic memory system with hybrid PostgreSQL + LanceDB storage
- Automatic episode segmentation using time gaps, topic changes, and task completion detection
- Four retrieval modes: Temporal (time-based), Semantic (vector search), Sequential (full episode), Contextual (hybrid)
- Episode lifecycle management: decay, consolidation, and archival to cold storage
- **🎓 Graduation Exam Framework**: Validate agent promotion readiness with 100% Constitutional Compliance
- Readiness Score calculation: 40% episode count, 30% intervention rate, 30% constitutional compliance
- Use cases: MedScribe (100 clinical episodes, zero errors for hospital board), Brennan.ca (Woodstock pricing validation)
- 4 core services, 3 database models, 20+ API endpoints, 4 test files, comprehensive documentation
- **See**: `docs/EPISODIC_MEMORY_IMPLEMENTATION.md`, `docs/AGENT_GRADUATION_GUIDE.md`

### Student Agent Training System (Feb 2, 2026) ✨ NEW
- Four-tier maturity-based routing prevents STUDENT agents from automated triggers
- AI-powered training duration estimation with user override capability
- Real-time supervision for SUPERVISED agents with pause/correct/terminate controls
- Action proposal workflow for INTERN agents requires human approval before execution
- Centralized TriggerInterceptor with <5ms routing decisions
- Comprehensive audit trail tracks all blocked triggers, proposals, and sessions
- 6 core services, 4 database models, 20+ API endpoints, 11 tests
- **See**: `docs/STUDENT_AGENT_TRAINING_IMPLEMENTATION.md`

### Real-Time Agent Guidance System (Feb 2, 2026) ✨ NEW
- Complete agent operation visibility with live progress tracking
- Multi-view orchestration (browser/terminal/canvas) with layout management
- Smart error resolution with 7 error categories and learning feedback
- Interactive permission/decision requests with full audit trail
- Integration guidance for OAuth flows
- 5 React components, 4 core services, 25+ tests, comprehensive documentation
- **See**: `docs/CANVAS_IMPLEMENTATION_COMPLETE.md`

### Custom Canvas Components (Feb 1, 2026)
- User-created HTML/CSS/JS components with security validation
- Version control with rollback, usage tracking
- **Governance**: AUTONOMOUS for JS, SUPERVISED+ for HTML/CSS

### Multi-Agent Canvas Coordination (Feb 1, 2026)
- Three collaboration modes: Sequential, Parallel, Locked
- Role-based permissions (owner, contributor, reviewer, viewer)
- Conflict resolution strategies

### Enhanced Feedback System (Feb 1, 2026)
- Comprehensive A/B testing framework
- Feedback analytics with aggregation and insights
- Batch approval and agent promotion suggestions

### Mobile Support Architecture (Feb 1, 2026) ✨ UPDATED
- React Native architecture (iOS 13+, Android 8+)
- **Status**: Implementation in progress
- **Completed** (Feb 5, 2026):
  - Device permissions using Expo modules (Camera, Location, Notifications, Biometric)
  - Authentication flow with device registration
  - SettingsScreen with user preferences
  - Proper error handling and validation
- **Pending**: Full app completion, testing, deployment
- **Docs**: `docs/REACT_NATIVE_ARCHITECTURE.md`

### Device Capabilities (Feb 1, 2026)
- Camera, Screen Recording, Location, Notifications, Command Execution
- 32 tests, full governance integration

### Deep Linking (Feb 1, 2026)
- `atom://` URL scheme for external app integration
- 38 tests, security validation

### Browser Automation (Jan 31, 2026)
- Playwright CDP integration
- 17 tests, INTERN+ governance required

### Governance Integration (Jan 2026)
- Agent context resolution with fallback chain
- <1ms governance cache, 27 tests

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
- **Naming**:
  - Classes: `PascalCase` (e.g., `AgentGovernanceService`)
  - Functions: `snake_case` (e.g., `submit_feedback`)
  - Constants: `UPPER_SNAKE_CASE` (e.g., `DATABASE_URL`)
- **Type Hints**: Required for all function signatures (enforced by MyPy in CI)
- **Docstrings**: Google-style with Args/Returns sections
- **See**: `backend/docs/CODE_QUALITY_STANDARDS.md` for comprehensive standards

### Error Handling Patterns
```python
# Standardized error handling
try:
    # Database operations
    with SessionLocal() as db:
        agent = db.query(AgentRegistry).filter(...).first()
        db.add(agent)
        db.commit()
except Exception as e:
    logger.error(f"Operation failed: {e}")
    raise api_error(
        ErrorCode.DATABASE_ERROR,
        "Database operation failed",
        {"error": str(e)}
    )
```

### Database Session Patterns
1. **Context Manager** (Service Layer):
   ```python
   with get_db_session() as db:
       # Auto-commits on success, auto-rolls back on exception
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
{
    "success": True,
    "data": {...},
    "message": "Operation successful",
    "timestamp": "2026-02-06T10:30:00.000Z"
}

# Error Response
{
    "success": False,
    "error_code": "AGENT_NOT_FOUND",
    "message": "Agent with ID 'abc123' not found",
    "details": {"agent_id": "abc123"}
}
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

**API Endpoints**:
- `backend/core/atom_agent_endpoints.py` - Chat/streaming
- `backend/api/canvas_routes.py` - Canvas/forms
- `backend/api/browser_routes.py` - Browser automation
- `backend/api/device_capabilities.py` - Device control
- `backend/api/deeplinks.py` - Deep linking

**Tools**:
- `backend/tools/canvas_tool.py` - Canvas presentations
- `backend/tools/browser_tool.py` - Browser automation
- `backend/tools/device_tool.py` - Device capabilities

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
| **✨ Health liveness probe** | **<10ms** | **2ms P50, 10ms P99** |
| **✨ Health readiness probe** | **<100ms** | **15ms P50, 40ms P99** |
| **✨ Prometheus metrics scrape** | **<50ms** | **8ms P50, 25ms P99** |
| **✨ Vector embedding generation** | **<20ms** | **10-20ms (FastEmbed)** |

---

## Key Concepts

1. **Multi-Agent Architecture** - Specialized agents with different maturity levels
2. **Governance First** - Every AI action is attributable, governable, and auditable
3. **Single-Tenant** - No workspace isolation, global dataset
4. **Graceful Degradation** - Log errors but allow requests if governance fails
5. **Performance Matters** - Cache provides sub-millisecond performance
6. **✨ Observability** - Health checks, metrics, and structured logs for production monitoring
7. **✨ Personal Edition** - Local deployment option with simplified setup (Docker Compose + SQLite)
8. **✨ Type Safety** - MyPy type checking enforced in CI for code quality

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

**✨ Phase 15 Complete**: Production-ready codebase with CI/CD pipeline, health checks, Prometheus metrics, comprehensive documentation, and type safety enforcement.

**✨ Personal Edition Available**: Run Atom locally with Docker Compose for personal automation and development (see `docs/PERSONAL_EDITION.md`).

---

*For comprehensive documentation, see `docs/` directory, `backend/docs/` for operational guides, and test files for usage examples.*
