# Atom - AI-Powered Business Automation Platform

> **Project Context**: Atom is an intelligent business automation and integration platform that uses AI agents to help users automate workflows, integrate services, and manage business operations.

**Last Updated**: February 6, 2026

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

**Tech Stack**: Python 3.11, FastAPI, SQLAlchemy 2.0, SQLite/PostgreSQL, Multi-provider LLM, Playwright, Redis (WebSocket), Alembic

**Key Directories**: `backend/core/`, `backend/api/`, `backend/tools/`, `backend/tests/`, `mobile/`, `docs/`

**Key Services**:
- `agent_governance_service.py` - Agent lifecycle and permissions
- `trigger_interceptor.py` - Maturity-based trigger routing
- `student_training_service.py` - Training proposals and sessions
- `supervision_service.py` - Real-time supervision monitoring
- `governance_cache.py` - High-performance caching (<1ms lookups)

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

---

## Recent Major Changes

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
- **Type Hints**: Required for all function signatures
- **Docstrings**: Google-style with Args/Returns sections

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
DATABASE_URL=sqlite:///./atom_dev.db

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

---

## Key Concepts

1. **Multi-Agent Architecture** - Specialized agents with different maturity levels
2. **Governance First** - Every AI action is attributable, governable, and auditable
3. **Single-Tenant** - No workspace isolation, global dataset
4. **Graceful Degradation** - Log errors but allow requests if governance fails
5. **Performance Matters** - Cache provides sub-millisecond performance

---

## Quick Reference Commands

```bash
# Development
python -m uvicorn main:app --reload --port 8000

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
```

---

## Summary

Atom is an AI-powered automation platform with multi-agent governance, episodic memory, and real-time guidance. **Key**: Always think about **agent attribution** and **governance** when working with any AI feature.

---

*For comprehensive documentation, see `docs/` directory and test files for usage examples.*
