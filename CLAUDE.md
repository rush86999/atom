# Atom - AI-Powered Business Automation Platform

> **Project Context**: Atom is an intelligent business automation and integration platform that uses AI agents to help users automate workflows, integrate services, and manage business operations.

**Last Updated**: February 20, 2026

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
- **✨ Personal Edition** - Run Atom on your local computer with Docker
- **✨ Production-Ready** - CI/CD pipeline, monitoring, health checks
- **✨ Autonomous Coding Agents** - Full SDLC from natural language to deployed code (Phase 69)

**Tech Stack**: Python 3.11, FastAPI, SQLAlchemy 2.0, SQLite/PostgreSQL, Multi-provider LLM, Playwright, Redis (WebSocket), Alembic

**Key Directories**: `backend/core/`, `backend/api/`, `backend/tools/`, `backend/tests/`, `frontend-nextjs/`, `mobile/`, `docs/`

**Key Services**:
- `agent_governance_service.py` - Agent lifecycle and permissions
- `governance_cache.py` - High-performance caching (<1ms lookups)
- `health_routes.py` - Health check endpoints (`/health/live`, `/health/ready`, `/health/metrics`)
- `monitoring.py` - Prometheus metrics and structured logging
- `cli/daemon.py` - Daemon mode for background agent execution
- `useCanvasState.ts` - Canvas state subscription hook
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

### Action Complexity
- **1 (LOW)**: Presentations → STUDENT+
- **2 (MODERATE)**: Streaming → INTERN+
- **3 (HIGH)**: State changes → SUPERVISED+
- **4 (CRITICAL)**: Deletions → AUTONOMOUS only

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
- **✨ AI Accessibility**: Hidden trees expose state as JSON (role='log', aria-live)
- **✨ Canvas State API**: `window.atom.canvas.getState()`, `getAllStates()`, `subscribe()`

### 4. Real-Time Agent Guidance System ✨
- **Files**: `tools/agent_guidance_canvas_tool.py`, `core/view_coordinator.py`, `core/error_guidance_engine.py`
- Live operation tracking with progress bars
- Multi-view orchestration (browser/terminal/canvas)
- Smart error resolution with 7 error categories
- Interactive permission/decision requests

### 5. Python Package Support ✨ (Phase 35)
- **Files**: `core/package_governance_service.py`, `core/package_installer.py`, `api/package_routes.py`
- Per-skill Docker images with dedicated packages
- Vulnerability scanning using pip-audit + Safety
- Maturity-based access control (STUDENT blocked, INTERN requires approval)
- Container security (network disabled, read-only filesystem, resource limits)
- **Status**: ✅ COMPLETE - All 7 plans executed, production-ready

### 6. Browser Automation System
- **Files**: `tools/browser_tool.py`, `api/browser_routes.py`
- Web scraping, form filling, screenshots via Playwright CDP
- Governance: INTERN+ required

### 7. Device Capabilities System
- **Files**: `tools/device_tool.py`, `api/device_capabilities.py`
- Camera (INTERN+), Screen Recording (SUPERVISED+), Location (INTERN+), Notifications (INTERN+), Command Execution (AUTONOMOUS only)

### 8. Student Agent Training System ✨
- **Files**: `core/trigger_interceptor.py`, `core/student_training_service.py`, `core/proposal_service.py`, `core/supervision_service.py`
- Four-tier maturity routing: STUDENT → INTERN → SUPERVISED → AUTONOMOUS
- AI-based training duration estimation
- Real-time supervision for SUPERVISED agents
- Action proposal workflow for INTERN agents

### 9. Episodic Memory & Graduation Framework ✨
- **Files**: `episode_segmentation_service.py`, `episode_retrieval_service.py`, `episode_lifecycle_service.py`, `agent_graduation_service.py`
- **Canvas & Feedback Integration**: Episodes include canvas presentations and user feedback
- Automatic episode segmentation (time gaps, topic changes, task completion)
- Four retrieval modes: Temporal, Semantic, Sequential, Contextual
- Hybrid PostgreSQL (hot) + LanceDB (cold) storage
- **Graduation Criteria**:
  - STUDENT → INTERN: 10 episodes, 50% intervention rate, 0.70 constitutional score
  - INTERN → SUPERVISED: 25 episodes, 20% intervention rate, 0.85 constitutional score
  - SUPERVISED → AUTONOMOUS: 50 episodes, 0% intervention rate, 0.95 constitutional score

### 10. Production Monitoring & Observability ✨
- **Files**: `api/health_routes.py`, `core/monitoring.py`
- Health check endpoints: `/health/live` (liveness), `/health/ready` (readiness with DB/disk checks)
- Prometheus metrics: HTTP requests, agent executions, DB queries
- Structured logging: JSON output with structlog
- Performance benchmarks: <10ms (live), <100ms (ready), <50ms (metrics scrape)

### 11. CI/CD Pipeline & Deployment ✨
- **File**: `.github/workflows/deploy.yml`
- Jobs: test → build → deploy-staging → deploy-production → verify
- Automated rollback on failure
- Database backup before production deployment
- Smoke tests and metrics monitoring

### 12. Personal Edition & Daemon Mode ✨
- **Files**: `cli/daemon.py`, `cli/main.py`, `.env.personal`, `docker-compose-personal.yml`
- Docker Compose setup with SQLite, simplified configuration
- Daemon Mode: Background service with PID tracking, graceful shutdown
- CLI Commands: `atom-os daemon`, `atom-os status`, `atom-os stop`, `atom-os execute <command>`
- Host Shell Access: Optional filesystem mount with AUTONOMOUS gate

### 13. Code Quality & Type Hints ✨
- **Files**: `backend/docs/CODE_QUALITY_STANDARDS.md`, `mypy.ini`, `.github/workflows/ci.yml`
- MyPy configuration for static type checking
- Type hints on critical service functions
- CODE_QUALITY_STANDARDS.md (9,412 lines)

### 14. Advanced Skill Execution & Composition ✨ (Phase 60)
- **Purpose**: Marketplace for skill discovery, dynamic loading, workflow composition
- **Seven Plans Complete**: Marketplace, Dynamic Loading, Composition Engine, Auto-Installation, Testing, E2E Security, Documentation
- **Features**:
  - PostgreSQL full-text search with community ratings
  - importlib-based hot-reload (<1 second)
  - DAG validation with NetworkX cycle detection
  - Python + npm dependency resolution with conflict detection
  - 36 E2E security tests (typosquatting, dependency confusion, postinstall malware)
- **Status**: ✅ COMPLETE - All 7 plans executed, production-ready

### 15. BYOK Cognitive Tier System ✨ (Phase 68)
- **Files**: `core/llm/cognitive_tier_system.py`, `core/llm/cache_aware_router.py`, `core/llm/escalation_manager.py`
- **Purpose**: 5-tier intelligent LLM routing with cache-aware cost optimization
- **Features**:
  - 5 cognitive tiers: Micro, Standard, Versatile, Heavy, Complex
  - Multi-factor classification: token count + semantic complexity + task type
  - Cache-aware routing: 90% cost reduction with prompt caching
  - Auto-escalation: Quality-based tier escalation with 5-min cooldown
  - MiniMax M2.5: Standard tier option at ~$1/M tokens
- **Performance**: <100ms routing, 30%+ cost savings
- **Tests**: 100+ tests across 8 test files
- **Status**: ✅ COMPLETE - All 8 plans executed, production-ready

### 16. Autonomous Coding Agents ✨ (Phase 69)
- **Purpose**: Full SDLC from natural language feature request to deployed, tested, documented code
- **Ten Plans Complete**:
  1. Feature Request Parser - Natural language to structured requirements
  2. Codebase Researcher - AST parsing, embedding search, conflict detection
  3. Implementation Planner - HTN decomposition, DAG validation with NetworkX
  4. Code Generator - Backend (Python/FastAPI), Frontend (React/TS), Database (Alembic)
  5. Test Generator - AST-based, parametrized, property-based (Hypothesis)
  6. Test Runner & Auto-Fixer - Pytest execution, failure categorization, LLM-powered fixes
  7. Documentation Generator - OpenAPI specs, Markdown guides, Google-style docstrings
  8. Commit Manager - Conventional commits, GitHub PR creation
  9. Orchestrator - Central coordinator with checkpoint/rollback, human-in-the-loop
  10. CodingAgentCanvas - Real-time canvas UI with approval workflow, AI accessibility
- **Files Created**: 13 core services (10K+ lines), 10 test files (6K+ lines), frontend canvas component, comprehensive documentation
- **Key Features**:
  - End-to-end autonomous workflow: parse → research → plan → code → test → fix → docs → commit
  - Wave-based parallel execution for independent tasks
  - Git-based checkpoint/rollback system
  - Human-in-the-loop approval workflow
  - Real-time progress tracking via WebSocket
  - Episode integration for WorldModel recall
- **Performance**: Feature parsing <10s, code generation <30s, test generation <15s, auto-fixing <60s
- **Tests**: 300+ tests across all services
- **Docs**: `docs/AUTONOMOUS_CODING_AGENTS.md`, `docs/AUTONOMOUS_CODING_ARCHITECTURE.md`
- **Status**: ✅ COMPLETE - All 10 plans executed, production-ready

---

## Recent Major Changes

### Phase 69: Autonomous Coding Agents (Feb 21, 2026) ✨ NEW
- **Purpose**: Full SDLC autonomous agents from natural language to deployed code
- **Implementation**: All 10 plans complete, production-ready
- **Files**: 13 core services (10K+ lines), 10 test files, 1 frontend canvas component
- **Impact**: Describe features in natural language → Get working, tested, documented code automatically

### Phase 68: BYOK Cognitive Tier System (Feb 20, 2026) ✨
- **Purpose**: Optimize LLM costs through 5-tier cognitive classification
- **Implementation**: All 8 plans complete, production-ready
- **Impact**: 30%+ cost reduction through cache optimization and tier routing

### Phase 35: Python Package Support (Feb 19, 2026) ✨
- **Purpose**: Enable skills to use Python packages with security scanning
- **Implementation**: All 7 plans complete, production-ready
- **Impact**: Per-skill Docker images, vulnerability scanning, maturity-based governance

### Phase 60: Advanced Skill Execution (Feb 19, 2026) ✨
- **Purpose**: Marketplace for skill discovery and workflow composition
- **Implementation**: All 7 plans complete, production-ready
- **Impact**: Dynamic skill loading, DAG workflows, E2E security testing

### Phase 15: Codebase Completion (Feb 16, 2026) ✨
- **Purpose**: Production-ready codebase with comprehensive documentation
- **Implementation**: 5 plans complete
- **Impact**: CI/CD pipeline, health checks, metrics, type safety

### Phase 14: Community Skills Integration (Feb 16, 2026) ✨
- **Purpose**: Enable 5,000+ OpenClaw/ClawHub community skills
- **Implementation**: 3 plans complete, verification passed
- **Impact**: Lenient parsing, security scanning, governance integration

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

### Error Handling Patterns
```python
try:
    with get_db_session() as db:
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

# With coverage
pytest tests/ --cov=core --cov-report=html
```

---

## Important File Locations

**Core Services**:
- `backend/core/agent_governance_service.py` - Agent governance
- `backend/core/governance_cache.py` - Performance cache
- `backend/core/llm/byok_handler.py` - LLM routing
- `backend/core/models.py` - Database models

**API Endpoints**:
- `backend/core/atom_agent_endpoints.py` - Chat/streaming
- `backend/api/canvas_routes.py` - Canvas/forms
- `backend/api/browser_routes.py` - Browser automation
- `backend/api/device_capabilities.py` - Device control

**Canvas & Accessibility**:
- `frontend-nextjs/hooks/useCanvasState.ts` - Canvas state hook
- `frontend-nextjs/components/canvas/types/index.ts` - Canvas state types

**Tools**:
- `backend/tools/canvas_tool.py` - Canvas presentations
- `backend/tools/browser_tool.py` - Browser automation
- `backend/tools/atom_cli_skill_wrapper.py` - CLI command subprocess wrapper

**Skills**:
- `backend/skills/atom-cli/` - CLI skills SKILL.md files
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
7. **Personal Edition** - Local deployment option with simplified setup
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
curl -X GET "/api/v1/cognitive-tier/compare-tiers"
curl -X GET "/api/v1/cognitive-tier/estimate-cost?prompt=test&estimated_tokens=100"

# Playwright
playwright install chromium

# Database
alembic upgrade head

# Git
git status
git add .
git commit -m "feat: description"
git push origin main

# Logs
tail -f logs/atom.log

# Personal Edition (Docker)
docker-compose -f docker-compose-personal.yml up -d
docker-compose -f docker-compose-personal.yml logs -f
docker-compose -f docker-compose-personal.yml down
```

---

## Summary

Atom is an AI-powered automation platform with multi-agent governance, episodic memory, real-time guidance, production-ready monitoring, and **autonomous coding agents** that execute the complete software development lifecycle from natural language to deployed code.

**Key**: Always think about **agent attribution** and **governance** when working with any AI feature.

**Latest Achievements**:
- ✅ Phase 69: Autonomous Coding Agents - Full SDLC implementation (10 plans)
- ✅ Phase 68: BYOK Cognitive Tier System - 30%+ cost reduction (8 plans)
- ✅ Phase 60: Advanced Skill Execution - Marketplace and composition (7 plans)
- ✅ Phase 35: Python Package Support - Security scanning and isolation (7 plans)

---

*For comprehensive documentation, see `docs/` directory, `backend/docs/` for operational guides, and test files for usage examples.*
