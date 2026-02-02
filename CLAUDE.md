# Atom - AI-Powered Business Automation Platform

> **Project Context**: Atom is an intelligent business automation and integration platform that uses AI agents to help users automate workflows, integrate services, and manage business operations.

**Last Updated**: February 2, 2026

---

## Quick Overview

**What is Atom?**
- AI-powered workflow automation platform with multi-agent system and governance
- Real-time streaming LLM responses with multi-provider support
- Canvas-based visual presentations with custom components
- Browser automation (CDP) and device capabilities
- Enhanced feedback system with A/B testing
- Mobile support architecture (React Native)

**Tech Stack**: Python 3.11, FastAPI, SQLAlchemy 2.0, SQLite/PostgreSQL, Multi-provider LLM, Playwright

**Key Directories**: `backend/core/`, `backend/api/`, `backend/tools/`, `backend/tests/`, `mobile/`, `docs/`

---

## Architecture Overview

### Multi-Agent System with Governance

```
User Request → AgentContextResolver → GovernanceCache → AgentGovernanceService → Agent Execution → Response
```

### Maturity Levels

| Level | Confidence | Capabilities |
|-------|-----------|--------------|
| STUDENT | <0.5 | Read-only (charts, markdown) |
| INTERN | 0.5-0.7 | Streaming, form presentation |
| SUPERVISED | 0.7-0.9 | Form submissions, state changes |
| AUTONOMOUS | >0.9 | Full autonomy, all actions |

### Action Complexity

- **1 (LOW)**: Presentations, read-only → STUDENT+
- **2 (MODERATE)**: Streaming, moderate actions → INTERN+
- **3 (HIGH)**: State changes, submissions → SUPERVISED+
- **4 (CRITICAL)**: Deletions, payments → AUTONOMOUS only

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

### 8. Database Models
- **File**: `core/models.py`
- Key models: AgentRegistry, AgentExecution, AgentFeedback, CanvasAudit, BrowserSession, DeviceSession, DeepLinkAudit, ChatSession
- **NEW**: AgentOperationTracker, AgentRequestLog, ViewOrchestrationState, OperationErrorResolution

---

## Recent Major Changes

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

### Mobile Support Architecture (Feb 1, 2026)
- React Native architecture (iOS 13+, Android 8+)
- **Status**: Architecture complete, implementation pending
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

# Testing
pytest tests/ -v
pytest tests/test_governance_streaming.py -v
pytest tests/test_browser_automation.py -v

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

Atom is a sophisticated AI-powered automation platform with:
- Multi-agent system with comprehensive governance
- Real-time streaming with <1ms governance overhead
- Canvas presentations with full audit trails
- Browser automation (CDP via Playwright)
- Device capabilities (Camera, Screen Recording, Location, Notifications, Command Execution)
- Sub-millisecond operations, production-ready

**Key Takeaway**: Always think about **agent attribution** and **governance** when working with any AI feature in Atom.

---

*For comprehensive documentation, see `docs/` directory and test files for usage examples.*
