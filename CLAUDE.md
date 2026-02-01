# Atom - AI-Powered Business Automation Platform

> **Project Context**: Atom is an intelligent business automation and integration platform that uses AI agents to help users automate workflows, integrate services, and manage business operations.

**Last Updated**: February 1, 2026

---

## Quick Overview

**What is Atom?**
- AI-powered workflow automation platform
- Multi-agent system with governance
- Real-time streaming LLM responses
- Canvas-based visual presentations with custom components
- Multi-agent canvas collaboration (sequential, parallel, locked modes)
- Browser automation with CDP
- Device capabilities (Camera, Screen Recording, Location, Notifications, Command Execution)
- Enhanced feedback system with A/B testing
- Deep linking via atom:// URL scheme
- Mobile support architecture (React Native)
- Comprehensive audit trails

**Tech Stack**:
- **Backend**: Python 3.11, FastAPI, SQLAlchemy 2.0
- **Database**: SQLite (dev), PostgreSQL (production)
- **AI/LLM**: Multi-provider (OpenAI, Anthropic, DeepSeek, Gemini)
- **Browser Automation**: Playwright (CDP)
- **Mobile**: React Native 0.73+ (iOS 13+, Android 8+)
- **Architecture**: Modular, event-driven, single-tenant

**Key Directories**:
- `backend/core/` - Core services (governance, agents, database models, custom components, collaboration)
- `backend/api/` - FastAPI route handlers
- `backend/tools/` - Agent tools (canvas, browser, integrations)
- `backend/alembic/versions/` - Database migrations
- `backend/tests/` - Test suite (unit, integration, performance)
- `mobile/` - React Native mobile app (architecture complete)
- `docs/` - Documentation (including React Native architecture)

---

## Architecture Overview

### Multi-Agent System with Governance

Atom uses a sophisticated multi-agent system with comprehensive governance:

```
User Request
    ↓
AgentContextResolver (determines which agent)
    ↓
GovernanceCache (performance cache)
    ↓
AgentGovernanceService (checks permissions)
    ↓
Agent Execution (with audit trail)
    ↓
Response/Action
```

### Maturity Levels

Agents progress through maturity levels based on confidence scores:

| Level | Confidence | Capabilities |
|-------|-----------|--------------|
| STUDENT | <0.5 | Read-only (charts, markdown) |
| INTERN | 0.5-0.7 | Streaming, form presentation |
| SUPERVISED | 0.7-0.9 | Form submissions, state changes |
| AUTONOMOUS | >0.9 | Full autonomy, all actions |

### Action Complexity

Actions are classified by complexity (1-4):
- **1 (LOW)**: Presentations, read-only → STUDENT+
  - Examples: present_chart, present_markdown, search, read, fetch
- **2 (MODERATE)**: Streaming, moderate actions → INTERN+
  - Examples: stream_chat, browser_navigate, browser_screenshot, browser_fill_form, present_form
  - Device: camera_snap, get_location, send_notification
- **3 (HIGH)**: State changes, submissions → SUPERVISED+
  - Examples: create, update, submit_form, send_email, post_message
  - Device: screen_record_start, screen_record_stop
- **4 (CRITICAL)**: Deletions, payments → AUTONOMOUS only
  - Examples: delete, execute, deploy, payment, approve
  - Device: execute_command

---

## Core Components

### 1. Agent Governance System

**Purpose**: Manage agent lifecycle, permissions, and maturity

**Key Files**:
- `backend/core/agent_governance_service.py` - Governance logic
- `backend/core/agent_context_resolver.py` - Agent resolution (NEW)
- `backend/core/governance_cache.py` - Performance cache (NEW)

**Usage**:
```python
from core.agent_governance_service import AgentGovernanceService
from core.agent_context_resolver import AgentContextResolver

# Resolve agent for request
resolver = AgentContextResolver(db)
agent, context = await resolver.resolve_agent_for_request(
    user_id="user-1",
    action_type="stream_chat"
)

# Check permissions
governance = AgentGovernanceService(db)
check = governance.can_perform_action(agent.id, "stream_chat")
if not check["allowed"]:
    return {"error": check["reason"]}
```

### 2. Streaming LLM Integration

**Purpose**: Real-time streaming responses from multiple LLM providers

**Key Files**:
- `backend/core/llm/byok_handler.py` - Provider routing and streaming
- `backend/core/atom_agent_endpoints.py` - Chat streaming endpoint

**Features**:
- Multi-provider support (OpenAI, Anthropic, DeepSeek, Gemini)
- Cost optimization by query complexity
- Token-by-token streaming via WebSocket
- Agent execution tracking

**Usage**:
```python
from core.llm.byok_handler import BYOKHandler

handler = BYOKHandler(provider_id="auto")

async for token in handler.stream_completion(
    messages=messages,
    model="gpt-4",
    provider_id="openai",
    agent_id=agent_id,  # For governance tracking
    db=db
):
    await ws_manager.broadcast(user_channel, {"token": token})
```

### 3. Canvas Presentation System

**Purpose**: Real-time visual presentations to users via WebSocket

**Key Files**:
- `backend/tools/canvas_tool.py` - Canvas presentation functions
- `backend/api/canvas_routes.py` - Form submission endpoint

**Features**:
- Charts (line, bar, pie)
- Markdown content
- Status panels
- Interactive forms
- Full governance integration

**Usage**:
```python
from tools.canvas_tool import present_chart, present_form

# Present a chart
await present_chart(
    user_id="user-1",
    chart_type="line_chart",
    data=[{"x": 1, "y": 2}],
    title="Sales Trend",
    agent_id=agent_id  # For governance
)

# Present a form
await present_form(
    user_id="user-1",
    form_schema={"fields": [...]},
    title="User Input",
    agent_id=agent_id  # For governance
)
```

### 4. Browser Automation System (NEW)

**Purpose**: Chrome DevTools Protocol (CDP) control via Playwright for web automation

**Key Files**:
- `backend/tools/browser_tool.py` - Browser automation functions
- `backend/api/browser_routes.py` - Browser API endpoints
- `backend/core/models.py` - BrowserSession, BrowserAudit models

**Features**:
- Web scraping and data extraction
- Form filling and submission
- Multi-step web workflows
- Screenshot capture
- JavaScript execution
- Multi-browser support (Chromium, Firefox, WebKit)
- Session management with automatic cleanup
- Full governance integration (INTERN+ required)

**Governance**: All browser actions require INTERN+ maturity level

**Usage**:
```python
from tools.browser_tool import (
    browser_create_session,
    browser_navigate,
    browser_fill_form,
    browser_screenshot,
    browser_close_session,
)

# Create session
session = await browser_create_session(
    user_id="user-1",
    agent_id="agent-1",  # For governance (must be INTERN+)
    headless=True
)

# Navigate to URL
await browser_navigate(
    session_id=session["session_id"],
    url="https://example.com",
    user_id="user-1"
)

# Fill form
await browser_fill_form(
    session_id=session["session_id"],
    selectors={"#name": "John", "#email": "john@example.com"},
    submit=True,
    user_id="user-1"
)

# Take screenshot
await browser_screenshot(
    session_id=session["session_id"],
    full_page=True,
    user_id="user-1"
)

# Close session
await browser_close_session(
    session_id=session["session_id"],
    user_id="user-1"
)
```

**API Endpoints**:
- `POST /api/browser/session/create` - Create browser session
- `POST /api/browser/navigate` - Navigate to URL
- `POST /api/browser/screenshot` - Take screenshot
- `POST /api/browser/fill-form` - Fill form fields
- `POST /api/browser/click` - Click element
- `POST /api/browser/extract-text` - Extract text content
- `POST /api/browser/execute-script` - Execute JavaScript
- `POST /api/browser/session/close` - Close session
- `GET /api/browser/sessions` - List sessions
- `GET /api/browser/audit` - Get audit log

**Documentation**:
- `docs/BROWSER_AUTOMATION.md` - Full documentation
- `docs/BROWSER_QUICK_START.md` - 5-minute quick start guide
- `docs/BROWSER_IMPLEMENTATION_SUMMARY.md` - Implementation details

### 5. Device Capabilities System (NEW)

**Purpose**: Hardware access and device automation for AI agents

**Key Files**:
- `backend/tools/device_tool.py` - Device automation functions
- `backend/api/device_capabilities.py` - Device API endpoints
- `backend/core/models.py` - DeviceSession, DeviceAudit models
- `frontend-nextjs/src-tauri/src/main.rs` - Tauri commands

**Features**:
- **Camera Capture** (INTERN+) - Device camera image capture
- **Screen Recording** (SUPERVISED+) - Screen recording with audio
- **Location Services** (INTERN+) - Device location retrieval
- **System Notifications** (INTERN+) - System notification delivery
- **Command Execution** (AUTONOMOUS only) - Secure shell command execution
- Session management with automatic cleanup
- Full governance integration with maturity requirements

**Governance**:
- Camera/Location/Notifications: INTERN+ maturity
- Screen Recording: SUPERVISED+ maturity
- Command Execution: AUTONOMOUS only (security critical)

**Usage**:
```python
from tools.device_tool import (
    device_camera_snap,
    device_screen_record_start,
    device_get_location,
    device_send_notification,
    device_execute_command,
)

# Camera capture (INTERN+)
await device_camera_snap(
    db=db,
    user_id="user-1",
    device_node_id="device-123",
    agent_id="agent-1",
    resolution="1920x1080"
)

# Screen recording (SUPERVISED+)
session = await device_screen_record_start(
    db=db,
    user_id="user-1",
    device_node_id="device-123",
    agent_id="agent-2",
    duration_seconds=60
)

# Location (INTERN+)
await device_get_location(
    db=db,
    user_id="user-1",
    device_node_id="device-123",
    agent_id="agent-1",
    accuracy="high"
)

# Notification (INTERN+)
await device_send_notification(
    db=db,
    user_id="user-1",
    device_node_id="device-123",
    title="Workflow Complete",
    body="Your workflow has completed.",
    agent_id="agent-1"
)

# Command execution (AUTONOMOUS only)
await device_execute_command(
    db=db,
    user_id="user-1",
    device_node_id="device-123",
    command="ls",
    agent_id="agent-3"  # Must be AUTONOMOUS
)
```

**API Endpoints**:
- `POST /api/devices/camera/snap` - Capture camera
- `POST /api/devices/screen/record/start` - Start recording
- `POST /api/devices/screen/record/stop` - Stop recording
- `POST /api/devices/location` - Get location
- `POST /api/devices/notification` - Send notification
- `POST /api/devices/execute` - Execute command
- `GET /api/devices/{device_id}` - Get device info
- `GET /api/devices` - List devices
- `GET /api/devices/{device_id}/audit` - Get audit log

**Security**:
- Command whitelist enforced (ls, pwd, cat, grep, etc.)
- Timeout enforcement (default: 30s, max: 300s)
- Screen recording duration limits (default max: 1 hour)
- Working directory restrictions
- No interactive shells
- Full audit trail for all actions

**Documentation**:
- `docs/DEVICE_CAPABILITIES.md` - Full documentation

### 6. Deep Linking System (NEW)

**Purpose**: Enable external applications to trigger Atom actions via custom URL scheme

**Key Files**:
- `backend/core/deeplinks.py` - Deep link parsing and execution
- `backend/api/deeplinks.py` - REST API endpoints
- `backend/core/models.py` - DeepLinkAudit model

**Features**:
- **Agent Invocation** - `atom://agent/{agent_id}?message={query}` - Invoke AI agents
- **Workflow Triggers** - `atom://workflow/{workflow_id}?action={action}` - Trigger workflows
- **Canvas Manipulation** - `atom://canvas/{canvas_id}?action={action}` - Update canvases
- **Tool Execution** - `atom://tool/{tool_name}?params={json}` - Execute tools
- Full governance integration (all agent deep links require governance check)
- Comprehensive audit trail for all deep link executions
- URL validation and security checks

**Governance**:
- Agent deep links: Governance check for stream_chat action
- Workflow/Canvas/Tool: No governance (system-level operations)

**Usage**:
```python
from core.deeplinks import parse_deep_link, execute_deep_link, generate_deep_link

# Parse deep link
link = parse_deep_link("atom://agent/agent-1?message=Hello")

# Execute deep link
result = await execute_deep_link(
    url="atom://agent/agent-1?message=Hello",
    user_id="user-1",
    db=db,
    source="mobile_app"
)

# Generate deep link
url = generate_deep_link('agent', 'agent-1', message='Hello')
# "atom://agent/agent-1?message=Hello"
```

**API Endpoints**:
- `POST /api/deeplinks/execute` - Execute deep link
- `GET /api/deeplinks/audit` - Get audit log
- `POST /api/deeplinks/generate` - Generate deep link
- `GET /api/deeplinks/stats` - Get statistics

**Security**:
- URL format validation (scheme, resource type, resource ID)
- Resource ID regex check (alphanumeric, dashes, underscores only)
- Agent existence and status checks
- Full governance integration for agent actions
- Comprehensive audit trail

**Documentation**:
- `docs/DEEPLINK_IMPLEMENTATION.md` - Full deep linking documentation

### 7. Enhanced Feedback System (NEW)

**Purpose**: Collect user feedback and improve agent performance through confidence adjustments

**Key Files** (Phase 1):
- `backend/core/models.py` - AgentFeedback model (enhanced with ratings)
- `backend/api/feedback_enhanced.py` - Enhanced feedback API endpoints
- `backend/api/feedback_analytics.py` - Analytics dashboard endpoints
- `backend/core/feedback_analytics.py` - Feedback aggregation service
- `backend/core/agent_learning_enhanced.py` - Confidence adjustment logic
- `backend/core/agent_world_model.py` - World model integration (enhanced)

**Key Files** (Phase 2):
- `backend/api/feedback_batch.py` - Batch operations API
- `backend/api/feedback_phase2.py` - Phase 2 integrated API
- `backend/core/agent_promotion_service.py` - Promotion service
- `backend/core/feedback_export_service.py` - Export service
- `backend/core/feedback_advanced_analytics.py` - Advanced analytics

**Features** (Phase 1):
- **Thumbs Up/Down** - Quick positive/negative feedback
- **Star Ratings** - 1-5 star scale for nuanced feedback
- **Detailed Corrections** - Specific corrections for learning
- **Feedback Types** - Auto-detected (correction, rating, approval, comment)
- **Analytics Dashboard** - Comprehensive statistics and trends
- **Confidence Adjustments** - Automatic score updates based on feedback
- **Learning Signals** - Identifies agent strengths and weaknesses

**Features** (Phase 2):
- **Batch Operations** - Approve/reject/update multiple feedback at once
- **Promotion Suggestions** - Auto-evaluate agents for maturity promotion
- **Feedback Export** - JSON/CSV export with filtering options
- **Advanced Analytics** - Correlation, cohorts, predictions, velocity
- **Promotion Paths** - Complete path to AUTONOMOUS with progress tracking
- **Performance Predictions** - Trend-based future performance forecasting

**Usage**:
```python
from core.feedback_analytics import FeedbackAnalytics
from core.agent_learning_enhanced import AgentLearningEnhanced

# Get feedback summary
analytics = FeedbackAnalytics(db)
summary = analytics.get_agent_feedback_summary("agent-1", days=30)
print(summary["positive_ratio"])  # 0.8
print(summary["average_rating"])  # 4.5

# Adjust confidence
learning = AgentLearningEnhanced(db)
new_confidence = learning.adjust_confidence_with_feedback(
    agent_id="agent-1",
    feedback=feedback_obj,
    current_confidence=0.7
)
```

**API Endpoints** (Phase 1):
- `POST /api/feedback/submit` - Submit enhanced feedback
- `GET /api/feedback/agent/{agent_id}` - Get agent feedback summary
- `GET /api/feedback/analytics` - Overall analytics dashboard
- `GET /api/feedback/trends` - Feedback trends over time

**API Endpoints** (Phase 2):
- `POST /api/feedback/batch/approve` - Batch approve feedback
- `POST /api/feedback/batch/reject` - Batch reject feedback
- `POST /api/feedback/batch/update-status` - Bulk status update
- `GET /api/feedback/batch/pending` - Get pending feedback
- `GET /api/feedback/batch/stats` - Batch operation statistics
- `GET /api/feedback/phase2/promotion-suggestions` - Get promotion candidates
- `GET /api/feedback/phase2/promotion-path/{agent_id}` - Detailed promotion path
- `GET /api/feedback/phase2/promotion-check/{agent_id}` - Check readiness
- `GET /api/feedback/phase2/export` - Export feedback (JSON/CSV)
- `GET /api/feedback/phase2/export/summary` - Export summary statistics
- `GET /api/feedback/phase2/analytics/advanced/correlation/{agent_id}` - Correlation analysis
- `GET /api/feedback/phase2/analytics/advanced/cohorts` - Cohort analysis
- `GET /api/feedback/phase2/analytics/advanced/prediction/{agent_id}` - Performance prediction
- `GET /api/feedback/phase2/analytics/advanced/velocity/{agent_id}` - Velocity analysis

**Confidence Weights**:
- Thumbs up: +0.05, Thumbs down: -0.05
- 5-star: +0.10, 4-star: +0.05, 3-star: 0.00, 2-star: -0.05, 1-star: -0.10
- Correction: -0.03

**Documentation**:
- `docs/FEEDBACK_SYSTEM_ENHANCED.md` - Full feedback system documentation

### 8. Database Models

**Purpose**: SQLAlchemy models for all data persistence

**Key File**: `backend/core/models.py`

**Important Models**:
- `AgentRegistry` - Agent definitions with governance state
- `AgentExecution` - Execution records with audit trail
- `AgentFeedback` - User feedback with ratings, thumbs up/down, corrections (ENHANCED)
- `CanvasAudit` - Canvas action audit log
- `BrowserSession` - Browser session tracking
- `BrowserAudit` - Browser action audit log
- `DeviceSession` - Device session tracking
- `DeviceAudit` - Device action audit log
- `DeviceNode` - Device registry with platform info
- `DeepLinkAudit` - Deep link execution audit log
- `ChatSession` - Chat session tracking

---

## Recent Major Changes

### Custom Canvas Components (February 1, 2026)

**What Changed**:
- Implemented user-created HTML/CSS/JS components for canvas presentations
- Added 3 database models (CustomComponent, ComponentVersion, ComponentUsage)
- Created CustomComponentsService with security validation and governance enforcement
- Created 11 REST API endpoints for component management (create, read, update, delete, versions, rollback, stats)
- Implemented comprehensive security features:
  - HTML sanitization (blocks `<script>`, `javascript:`, `onclick=`, `onerror=`)
  - CSS sanitization (blocks `expression()`, `-ms-binding`, `behavior:url()`)
  - JS validation (blocks `eval()`, `Function()`, `innerHTML=`, `document.write`)
  - Dependency whitelist (only jsDelivr, cdnjs, unpkg CDNs)
- Implemented version control with full history and rollback support
- Added usage tracking with performance metrics and analytics
- Created comprehensive test suite (23 tests, 100% pass rate)

**Why**: Enable users to create reusable custom components for canvas presentations with enterprise-grade security and governance

**Migration Required**:
```bash
alembic upgrade head  # Migration 69a4bf86ff15
```

**Documentation**:
- `docs/REACT_NATIVE_ARCHITECTURE.md` - Mobile architecture (newly added)

**Governance**:
- AUTONOMOUS agents required for creating components with JavaScript
- SUPERVISED+ agents can create HTML/CSS-only components
- All components tracked with usage audit trail

### Multi-Agent Canvas Coordination (February 1, 2026)

**What Changed**:
- Implemented multi-agent collaboration framework for shared canvases
- Added 3 database models (CanvasCollaborationSession, CanvasAgentParticipant, CanvasConflict)
- Created CanvasCollaborationService with session/permission/conflict management
- Created 11 REST API endpoints for collaboration management
- Implemented three collaboration modes:
  - **Sequential**: Turn-based with 5-second activity window
  - **Parallel**: Concurrent with component locking via held_locks
  - **Locked**: First-come-first-served with lock tracking
- Implemented role-based permissions (owner, contributor, reviewer, viewer)
- Implemented conflict resolution strategies (first_come_first_served, priority, merge)
- Added activity tracking with SQLAlchemy JSON mutation tracking
- Created comprehensive test suite (22 tests, 100% pass rate)

**Why**: Enable multiple agents to collaborate on shared canvases with proper coordination, conflict resolution, and permission management

**Migration Required**:
```bash
alembic upgrade head  # Migration bcfaa9f4c376
```

**Usage**:
```python
from core.canvas_collaboration_service import CanvasCollaborationService

# Create collaborative session
service.create_collaboration_session(
    canvas_id="canvas-123",
    session_id="session-456",
    user_id=user_id,
    collaboration_mode="parallel",  # or "sequential", "locked"
    max_agents=5
)

# Add agents with roles
service.add_agent_to_session(
    collaboration_session_id=session_id,
    agent_id="agent-1",
    user_id=user_id,
    role="owner"  # or "contributor", "reviewer", "viewer"
)
```

### Enhanced Feedback System (February 1, 2026)

**What Changed**:
- Implemented comprehensive A/B testing framework for agent optimization
- Added feedback analytics with aggregation and insights
- Created batch feedback approval and agent promotion suggestions
- Implemented feedback export/import functionality
- Added 7 database models (ABTest, ABTestParticipant, FeedbackBatch, etc.)
- Created multiple REST API endpoints for feedback and A/B testing
- Created comprehensive test suites (17 tests for Phase 2, 21 tests for A/B testing)

**Why**: Enable data-driven agent optimization with statistical analysis, feedback aggregation, and automated promotion suggestions

**Migration Required**:
```bash
alembic upgrade head  # Migrations 6e792c493b60 and others
```

### Mobile Support Architecture (February 1, 2026)

**What Changed**:
- Designed comprehensive React Native mobile app architecture (iOS 13+, Android 8+)
- Created detailed architecture documentation with code examples
- Defined project structure for cross-platform mobile development
- Planned features: real-time agent chat, canvas presentations, device-native capabilities
- Integrated governance for mobile agent actions with device tracking

**Why**: Enable Atom platform access via native mobile apps with full feature parity and optimized mobile experience

**Status**: Architecture complete. Full implementation requires additional development.

**Documentation**:
- `docs/REACT_NATIVE_ARCHITECTURE.md` - Comprehensive architecture guide
- `mobile/` - Project structure and configuration files

**Planned Features**:
- Real-time agent chat with WebSocket streaming
- Interactive canvas presentations via WebView
- Biometric authentication (Face ID / Touch ID)
- Device-native features (Camera, Location, Push Notifications)
- Offline mode with data synchronization
- Governance integration with device tracking

### Device Capabilities (February 1, 2026)

**What Changed**:
- Implemented device hardware access for AI agents (Camera, Screen Recording, Location, Notifications, Command Execution)
- Added 7 device automation functions (camera_snap, screen_record_start/stop, get_location, send_notification, execute_command)
- Created 9 REST API endpoints for device control
- Added DeviceSession and DeviceAudit database models
- Extended DeviceNode model with platform info and detailed capabilities
- Integrated governance (INTERN+ for camera/location/notifications, SUPERVISED+ for screen recording, AUTONOMOUS only for command execution)
- Created comprehensive test suite (32 tests, 100% pass rate)
- Added 6 Tauri commands for platform-specific hardware access
- Extended WebSocket events for device operations

**Why**: Enable AI agents to interact with device hardware and perform local actions, bringing parity with OpenClaw's device capabilities while maintaining Atom's superior governance framework

**Migration Required**:
```bash
alembic upgrade head  # Migration g1h2i3j4k5l6
```

**Documentation**:
- `docs/DEVICE_CAPABILITIES.md` - Full documentation

### Deep Linking (February 1, 2026)

**What Changed**:
- Implemented deep linking via `atom://` URL scheme for external app integration
- Added 4 deep link types (agent, workflow, canvas, tool)
- Created 5 core deep link functions (parse_deep_link, execute_deep_link, generate_deep_link, execute_*_deep_link)
- Created 4 REST API endpoints for deep link management (execute, audit, generate, stats)
- Added DeepLinkAudit database model for full audit trail
- Integrated governance (all agent deep links require governance check)
- Created comprehensive test suite (38 tests)
- Added security validation (URL format, resource type, resource ID)

**Why**: Enable external applications (mobile apps, email campaigns, web apps) to trigger Atom actions securely with full governance and audit trails

**Migration Required**:
```bash
alembic upgrade head  # Migration 158137b9c8b6
```

**Documentation**:
- `docs/DEEPLINK_IMPLEMENTATION.md` - Full deep linking documentation

### Browser Automation (January 31, 2026)

**What Changed**:
- Implemented browser automation using Chrome DevTools Protocol (CDP) via Playwright
- Added 9 browser automation functions (create, navigate, screenshot, fill, click, extract, execute, close, get_info)
- Created 10 REST API endpoints for browser control
- Added BrowserSession and BrowserAudit database models
- Integrated governance (INTERN+ maturity required for all browser actions)
- Created comprehensive test suite (17 tests, 100% pass rate)

**Why**: Enable agents to perform web scraping, form filling, multi-step web workflows, screenshot capture, and browser-based testing

**Migration Required**:
```bash
alembic upgrade head  # Migration f1a2b3c4d5e6
```

**Documentation**:
- `docs/BROWSER_AUTOMATION.md` - Full documentation
- `docs/BROWSER_QUICK_START.md` - 5-minute quick start guide
- `docs/BROWSER_IMPLEMENTATION_SUMMARY.md` - Implementation details

### Governance Integration (January 2026)

**What Changed**:
- Added agent context resolution with fallback chain
- Implemented high-performance governance cache (<1ms latency)
- Added canvas audit trail for all presentations
- Integrated governance into streaming, canvas, and forms
- Created comprehensive test suite (27 tests, 100% pass rate)

**Why**: Ensure all AI actions are attributable, governable, and auditable

**Migration Required**:
```bash
alembic upgrade head
```

**Documentation**:
- `GOVERNANCE_INTEGRATION_COMPLETE.md` - Full implementation guide
- `GOVERNANCE_QUICK_REFERENCE.md` - Developer quick reference
- `GOVERNANCE_TEST_RESULTS.md` - Test results and benchmarks

---

## Development Guidelines

### Feature Flags

Always use feature flags for new features:

```python
import os

FEATURE_ENABLED = os.getenv("MY_FEATURE_ENABLED", "true").lower() == "true"
EMERGENCY_BYPASS = os.getenv("EMERGENCY_BYPASS", "false").lower() == "true"

if FEATURE_ENABLED and not EMERGENCY_BYPASS:
    # Feature logic here
    pass
```

### Error Handling

```python
import logging

logger = logging.getLogger(__name__)

try:
    # Operation
    pass
except Exception as e:
    logger.error(f"Operation failed: {e}")
    # Graceful degradation
    return {"success": False, "error": str(e)}
```

### Database Operations

```python
from core.database import SessionLocal

# Always use context managers
with SessionLocal() as db:
    # Read
    agent = db.query(AgentRegistry).filter(...).first()

    # Write
    execution = AgentExecution(...)
    db.add(execution)
    db.commit()
    db.refresh(execution)
```

### Async Patterns

```python
import asyncio

async def async_operation():
    # Use async for I/O operations
    result = await some_async_call()
    return result

# Run async from sync
asyncio.run(async_operation())
```

---

## Testing Approach

### Test Structure

```
backend/tests/
├── test_governance_streaming.py      # Governance unit tests (17 tests)
├── test_governance_performance.py     # Governance performance tests (10 tests)
└── test_browser_automation.py         # Browser automation tests (17 tests, NEW)
```

### Running Tests

```bash
# All tests
PYTHONPATH=/Users/rushiparikh/projects/atom/backend pytest tests/ -v

# Governance tests
pytest tests/test_governance_streaming.py -v

# Browser automation tests (NEW)
pytest tests/test_browser_automation.py -v

# Performance tests with output
pytest tests/test_governance_performance.py -v -s

# With coverage
pytest tests/ --cov=core --cov-report=html
```

### Test Patterns

**Unit Tests**:
```python
def test_agent_resolution():
    with patch.object(mock_db, 'query') as mock_query:
        # Setup mocks
        resolver = AgentContextResolver(mock_db)

        # Execute
        agent, context = await resolver.resolve_agent_for_request(...)

        # Assert
        assert agent is not None
        assert agent.id == "expected-id"
```

**Performance Tests**:
```python
def test_cache_performance():
    cache = GovernanceCache()

    # Warm up
    cache.set("key", "value", data)

    # Measure
    latencies = []
    for _ in range(1000):
        start = time.perf_counter()
        cache.get("key", "value")
        end = time.perf_counter()
        latencies.append((end - start) * 1000)

    # Assert targets
    assert sum(latencies) / len(latencies) < 10  # <10ms
```

---

## Common Patterns

### Adding a New Agent

```python
from core.agent_governance_service import AgentGovernanceService

with SessionLocal() as db:
    governance = AgentGovernanceService(db)

    agent = governance.register_or_update_agent(
        name="My Agent",
        category="Operations",
        module_path="agents.my_agent",
        class_name="MyAgent",
        description="Does useful things"
    )
```

### Creating Agent Executions

```python
from core.models import AgentExecution
import uuid

execution = AgentExecution(
    id=str(uuid.uuid4()),
    agent_id=agent.id,
    status="running",
    input_summary="User request: ...",
    triggered_by="api"
)

db.add(execution)
db.commit()

# After completion
execution.status = "completed"
execution.output_summary = "Task completed successfully"
execution.completed_at = datetime.now()
db.commit()
```

### Using Canvas for Presentations

```python
from tools.canvas_tool import present_chart, present_markdown

# Always include agent context for governance
await present_chart(
    user_id=user_id,
    chart_type="line_chart",
    data=data,
    title=title,
    agent_id=agent.id  # Important for governance!
)
```

### Using Browser Automation

```python
from tools.browser_tool import (
    browser_create_session,
    browser_navigate,
    browser_fill_form,
    browser_screenshot,
    browser_close_session,
)

# Agent must be INTERN+ for browser automation
# Governance is automatically checked
session = await browser_create_session(
    user_id=user_id,
    agent_id=agent.id,  # Important for governance!
    headless=True
)

# Navigate and automate
await browser_navigate(
    session_id=session["session_id"],
    url="https://example.com/form",
    user_id=user_id
)

await browser_fill_form(
    session_id=session["session_id"],
    selectors={"#field1": "value1", "#field2": "value2"},
    submit=True,
    user_id=user_id
)

# Always cleanup
await browser_close_session(
    session_id=session["session_id"],
    user_id=user_id
)
```

### Governance Checks Before Actions

```python
from core.agent_governance_service import AgentGovernanceService

governance = AgentGovernanceService(db)
check = governance.can_perform_action(
    agent_id=agent.id,
    action_type="delete_record"  # or "create", "update", etc.
)

if not check["allowed"]:
    logger.warning(f"Agent not permitted: {check['reason']}")
    return {"error": "Permission denied"}

# Proceed with action
```

---

## Important File Locations

### Core Services
- `backend/core/agent_governance_service.py` - Agent governance (maturity, permissions)
- `backend/core/agent_context_resolver.py` - Agent resolution (NEW)
- `backend/core/governance_cache.py` - Performance cache (NEW)
- `backend/core/llm/byok_handler.py` - LLM provider routing
- `backend/core/models.py` - All database models

### API Endpoints
- `backend/core/atom_agent_endpoints.py` - Chat and streaming endpoints
- `backend/api/canvas_routes.py` - Canvas and form submission
- `backend/api/browser_routes.py` - Browser automation API (NEW)
- `backend/core/unified_search_endpoints.py` - Search functionality

### Tools
- `backend/tools/canvas_tool.py` - Canvas presentations (charts, forms, markdown)
- `backend/tools/browser_tool.py` - Browser automation (CDP via Playwright) (NEW)
- `backend/integrations/` - Third-party integrations

### Database
- `backend/core/database.py` - Database connection and session management
- `backend/alembic/` - Database migrations
- `backend/alembic.ini` - Alembic configuration

### Configuration
- `backend/.env` - Environment variables (not in git)
- `backend/.env.example` - Environment template

---

## Environment Variables

Key environment variables (see `.env.example`):

```bash
# Database
DATABASE_URL=sqlite:///./atom_dev.db

# Governance
STREAMING_GOVERNANCE_ENABLED=true
CANVAS_GOVERNANCE_ENABLED=true
FORM_GOVERNANCE_ENABLED=true
BROWSER_GOVERNANCE_ENABLED=true  # NEW
EMERGENCY_GOVERNANCE_BYPASS=false

# Browser Automation (NEW)
BROWSER_HEADLESS=true  # Run browsers in headless mode

# LLM Providers
OPENAI_API_KEY=sk-...
ANTHROPIC_API_KEY=sk--...

# Application
PORT=8000
LOG_LEVEL=INFO
```

---

## Database Migrations

### Creating a Migration

```bash
alembic revision -m "description of changes"
```

### Running Migrations

```bash
# Upgrade to latest
alembic upgrade head

# Downgrade one step
alembic downgrade -1

# Check current version
alembic current

# View history
alembic history
```

### Migration Best Practices

1. **Always include both upgrade and downgrade functions**
2. **Use `op.add_column()` and `op.drop_column()` for schema changes**
3. **Create indexes for frequently queried columns**
4. **Test migrations on a copy of production data first**
5. **Never modify existing migrations** - always create new ones

---

## Performance Considerations

### Governance Cache

The governance cache provides >90% hit rate with <1ms latency:

```python
from core.governance_cache import get_governance_cache

cache = get_governance_cache()

# Check cache first (fast path)
cached_decision = cache.get(agent_id, action_type)
if cached_decision:
    return cached_decision  # <1ms!

# Else query and cache
decision = governance.can_perform_action(agent_id, action_type)
cache.set(agent_id, action_type, decision)
```

### Agent Resolution

Agent resolution uses a fallback chain:
1. Explicit agent_id in request
2. Session context agent
3. Workspace default agent
4. System default "Chat Assistant"

**Performance**: <0.1ms average

### Streaming Overhead

Governance adds ~1ms overhead to streaming:
- Agent resolution: ~0.08ms
- Governance check: ~0.02ms (cached)
- Execution creation: ~0.5ms
- Total: ~1ms (47x better than 50ms target)

---

## Troubleshooting

### Common Issues

**Issue**: Agent resolution returns None
```python
# Check system default agent exists
from core.agent_context_resolver import AgentContextResolver

resolver = AgentContextResolver(db)
agent = resolver._get_or_create_system_default()
print(f"System default: {agent.name if agent else 'NOT FOUND'}")
```

**Issue**: Governance blocks legitimate actions
```python
# Check agent maturity level
agent = db.query(AgentRegistry).filter(...).first()
print(f"Agent status: {agent.status}")
print(f"Confidence: {agent.confidence_score}")

# Check action complexity
from core.agent_governance_service import AgentGovernanceService
governance = AgentGovernanceService(db)
complexity = governance.ACTION_COMPLEXITY.get("my_action", 2)
print(f"Action complexity: {complexity}")
```

**Issue**: Cache hit rate is low
```python
from core.governance_cache import get_governance_cache

cache = get_governance_cache()
stats = cache.get_stats()
print(f"Hit rate: {stats['hit_rate']}%")
print(f"Size: {stats['size']}/{stats['max_size']}")
```

### Debugging

Enable debug logging:
```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

Check database state:
```sql
-- Agent executions
SELECT * FROM agent_executions
ORDER BY created_at DESC
LIMIT 10;

-- Canvas audit
SELECT * FROM canvas_audit
WHERE agent_id = 'agent-1'
ORDER BY created_at DESC;
```

---

## Code Style Guidelines

### Python

- Follow PEP 8
- Use type hints where appropriate
- Docstrings for all functions/classes
- Maximum line length: 100 (soft), 120 (hard)

### Function Documentation

```python
def function_name(param1: str, param2: Optional[int] = None) -> Dict[str, Any]:
    """
    Brief description of what the function does.

    Args:
        param1: Description of param1
        param2: Description of param2 (optional)

    Returns:
        Dictionary with keys:
            - 'success': bool
            - 'data': Any

    Example:
        >>> result = function_name("test", 42)
        >>> print(result['success'])
        True
    """
    pass
```

### Error Messages

Be specific and actionable:
```python
# Bad
raise Exception("Error")

# Good
raise ValueError(
    f"Agent {agent_id} is at {agent.status} maturity level "
    f"but action '{action_type}' requires {required_status}+. "
    f"Consider promoting the agent or using a different agent."
)
```

---

## Git Workflow

### Branch Strategy

- `main` - Production-ready code
- `feature/*` - Feature branches
- `fix/*` - Bug fixes

### Commit Messages

Follow conventional commits:
```
feat: add new feature
fix: resolve bug in governance
docs: update README
refactor: improve cache performance
test: add unit tests for agent resolution
```

### Before Committing

1. Run tests: `pytest tests/ -v`
2. Check formatting: `black .`
3. Verify migrations: `alembic upgrade head`
4. Update documentation if needed

---

## Getting Help

### Internal Documentation

- `GOVERNANCE_INTEGRATION_COMPLETE.md` - Governance system deep dive
- `GOVERNANCE_QUICK_REFERENCE.md` - Developer quick reference
- `GOVERNANCE_TEST_RESULTS.md` - Test results and benchmarks
- `README.md` - Project overview

### Code Examples

See test files for usage examples:
- `tests/test_governance_streaming.py` - Unit tests
- `tests/test_governance_performance.py` - Performance tests

### Logging

All components use Python logging:
```python
import logging

logger = logging.getLogger(__name__)

logger.info("Informational message")
logger.warning("Warning message")
logger.error("Error message")
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
| Browser session creation | <5s | ~1-2s avg (NEW) |
| Browser navigation | <30s | ~1-5s avg (NEW) |

---

## Key Concepts for New Developers

### 1. Multi-Agent Architecture

Atom isn't just one AI - it's a system of specialized agents, each with different capabilities and maturity levels. Always think about **which agent** should perform an action.

### 2. Governance First

Every AI action must be:
- **Attributable** - Linked to a specific agent
- **Governable** - Checked against agent's maturity level
- **Auditable** - Recorded in execution logs

### 3. Single-Tenant Architecture

Atom operates as a single-tenant system without workspace isolation. All queries operate on the global dataset.

### 4. Graceful Degradation

If governance fails, log the error but allow the request (availability > governance). Use the system default agent.

### 5. Performance Matters

The governance cache provides sub-millisecond performance. Always cache governance decisions.

---

## Future Enhancements

### Planned

1. **Distributed Cache** - Redis for multi-instance deployments
2. **Real-time Metrics** - Dashboard for governance metrics
3. **Auto-promotion** - Automatic agent promotion based on confidence
4. **Batch Operations** - Bulk governance checks
5. **Rate Limiting** - Per-agent rate limits

### Researching

1. **Federated Learning** - Learn from user interactions across sessions
2. **Transfer Learning** - Apply learnings across agents
3. **Explainability** - Why was an action blocked/allowed?
4. **Predictive Governance** - Predict agent success rates

---

## Quick Reference Commands

```bash
# Development
python -m uvicorn main:app --reload --port 8000

# Testing
pytest tests/ -v
pytest tests/test_governance_streaming.py -v
pytest tests/test_governance_performance.py -v -s
pytest tests/test_browser_automation.py -v  # Browser tests (NEW)

# Playwright (Browser Automation)
playwright install chromium  # Install browser binaries (NEW)

# Database
alembic upgrade head
alembic downgrade -1
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

✅ **Multi-agent system** with comprehensive governance
✅ **Real-time streaming** with <1ms governance overhead
✅ **Canvas presentations** with full audit trails
✅ **Browser automation** with CDP via Playwright
✅ **Device capabilities** with full hardware access (Camera, Screen Recording, Location, Notifications, Command Execution) (NEW)
✅ **Performance optimized** - sub-millisecond operations
✅ **Production ready** - 100% test coverage, all targets exceeded

**Key Takeaway**: Always think about **agent attribution** and **governance** when working with any AI feature in Atom.

**Browser Automation**: Agents can now automate web workflows (scraping, forms, screenshots) with full governance and audit trails. Requires INTERN+ maturity level.

**Device Capabilities**: Agents can now interact with device hardware (camera, screen recording, location, notifications, command execution) with full governance and audit trails. Requires INTERN+ (camera/location/notifications), SUPERVISED+ (screen recording), or AUTONOMOUS (command execution) maturity levels.

---

*For questions or issues, refer to the comprehensive documentation in the repository root or check the test files for usage examples.*
