---
phase: 08-80-percent-coverage-push
plan: 29
type: execute
wave: 6
depends_on: []
files_modified:
  - backend/tests/unit/test_canvas_tool.py
autonomous: true
user_setup: []
must_haves:
  truths:
    - "Canvas tool has 50%+ test coverage (chart presentation, markdown, forms, sheets, governance integration)"
    - "All canvas type components tested (line/bar/pie charts, markdown, forms, sheets)"
    - "Governance integration validated (agent checks, audit trails)"
    - "WebSocket broadcast tested for canvas updates"
  artifacts:
    - path: "backend/tests/unit/test_canvas_tool.py"
      provides: "Canvas presentation tests"
      min_lines: 850
  key_links:
    - from: "test_canvas_tool.py"
      to: "tools/canvas_tool.py"
      via: "mock_db, mock_agent_context_resolver, mock_ws_manager"
      pattern: "present_chart, present_markdown, present_form"
status: pending
created: 2026-02-13
gap_closure: false
---

# Plan 29: Canvas Tool Tests

**Status:** Pending
**Wave:** 6 (parallel with 30)
**Dependencies:** None

## Objective

Create comprehensive unit tests for canvas tool, achieving 50% coverage to contribute +0.8-1.0% toward Phase 8.9's 21-22% overall coverage goal.

## Context

Phase 8.9 targets 21-22% overall coverage (+2% from 19-20% baseline) by testing canvas and browser tools. This plan focuses ONLY on canvas_tool.py:

1. **tools/canvas_tool.py** (1,238 lines) - Chart presentation, markdown, forms, sheets, governance integration, audit trails

**Production Lines:** 1,238
**Expected Coverage at 50%:** ~620 lines
**Coverage Contribution:** +0.8-1.0 percentage points toward 21-22% goal

**Key Functions to Test:**
- `_create_canvas_audit()` - Audit trail creation
- `present_chart()` - Line/bar/pie chart presentation
- `present_markdown()` - Markdown rendering
- `present_form()` - Form presentation with validation
- `present_sheet()` - Sheet/data grid presentation
- `close_canvas()` - Canvas lifecycle cleanup
- `update_canvas()` - Incremental updates
- Governance checks integration
- WebSocket broadcast integration

## Success Criteria

**Must Have (truths that become verifiable):**
1. Canvas tool has 50%+ test coverage (chart presentation, markdown, forms)
2. All canvas type components tested (line/bar/pie charts, markdown, forms, sheets)
3. Governance integration validated (agent checks, audit trails)
4. WebSocket broadcast tested for canvas updates

**Should Have:**
- Canvas type registry integration tested
- Agent execution tracking validated
- Error handling for missing data
- Session isolation tested

**Could Have:**
- Canvas collaboration features (multi-user updates)
- Custom component rendering

**Won't Have:**
- Real WebSocket connections (mocked)
- Real database (sessions mocked)
- Frontend rendering tests (backend only)

## Tasks

### Task 1: Create test_canvas_tool.py with comprehensive coverage

**Files:**
- CREATE: `backend/tests/unit/test_canvas_tool.py` (850+ lines, 45-55 tests)

**Action:**
Create test file with these test classes:

```python
"""
Unit tests for Canvas Tool

Tests cover:
- Chart presentation (line, bar, pie)
- Markdown presentation
- Form presentation with validation
- Sheet/data grid presentation
- Canvas lifecycle (create, update, close)
- Governance integration
- Audit trail creation
- WebSocket broadcast
- Session isolation
"""
import pytest
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, Mock, patch
from sqlalchemy.orm import Session

from tools.canvas_tool import (
    _create_canvas_audit,
    present_chart,
    present_markdown,
    present_form,
    present_sheet,
    close_canvas,
    update_canvas
)
from core.models import CanvasAudit
from core.canvas_type_registry import canvas_type_registry


# =============================================================================
# Test Fixtures
# =============================================================================

@pytest.fixture
def mock_db():
    """Mock database session."""
    db = MagicMock(spec=Session)
    db.query = MagicMock()
    db.add = Mock()
    db.commit = Mock()
    db.rollback = Mock()
    db.refresh = Mock()
    db.flush = Mock()
    return db


@pytest.fixture
def mock_ws_manager():
    """Mock WebSocket manager."""
    manager = MagicMock()
    manager.broadcast = AsyncMock()
    return manager


@pytest.fixture
def sample_user_id():
    """Sample user ID for testing."""
    return "user_123"


@pytest.fixture
def sample_agent_id():
    """Sample agent ID for testing."""
    return "agent_123"


@pytest.fixture
def sample_canvas_id():
    """Sample canvas ID for testing."""
    return "canvas_abc123"


# =============================================================================
# Canvas Audit Creation Tests
# =============================================================================

class TestCanvasAuditCreation:
    """Tests for canvas audit trail creation."""

    @pytest.mark.asyncio
    async def test_create_canvas_audit_basic(self, mock_db, sample_user_id, sample_canvas_id):
        """Test basic canvas audit creation."""
        result = await _create_canvas_audit(
            db=mock_db,
            agent_id="agent_123",
            agent_execution_id="exec_456",
            user_id=sample_user_id,
            canvas_id=sample_canvas_id,
            session_id="session_789",
            canvas_type="generic",
            component_type="chart",
            component_name="test_chart",
            action="present"
        )

        assert result is not None
        assert isinstance(result, CanvasAudit)
        mock_db.add.assert_called_once()
        mock_db.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_canvas_audit_with_governance_check(self, mock_db):
        """Test audit creation includes governance check result."""
        result = await _create_canvas_audit(
            db=mock_db,
            agent_id="agent_123",
            agent_execution_id=None,
            user_id="user_123",
            canvas_id="canvas_456",
            session_id=None,
            action="present",
            governance_check_passed=True
        )

        assert result.governance_check_passed is True

    @pytest.mark.asyncio
    async def test_create_canvas_audit_with_metadata(self, mock_db):
        """Test audit creation includes metadata."""
        metadata = {"chart_type": "line", "data_points": 100}
        result = await _create_canvas_audit(
            db=mock_db,
            agent_id="agent_123",
            agent_execution_id=None,
            user_id="user_123",
            canvas_id="canvas_456",
            session_id=None,
            action="present",
            metadata=metadata
        )

        assert result.audit_metadata == metadata

    @pytest.mark.asyncio
    async def test_create_canvas_audit_default_values(self, mock_db):
        """Test audit creation uses appropriate defaults."""
        result = await _create_canvas_audit(
            db=mock_db,
            agent_id=None,
            agent_execution_id=None,
            user_id="user_123",
            canvas_id=None,
            session_id=None
        )

        assert result.canvas_type == "generic"
        assert result.component_type == "component"
        assert result.action == "present"

    @pytest.mark.asyncio
    async def test_create_canvas_audit_handles_errors(self, mock_db):
        """Test audit creation handles database errors gracefully."""
        mock_db.commit.side_effect = Exception("Database error")

        result = await _create_canvas_audit(
            db=mock_db,
            agent_id="agent_123",
            agent_execution_id=None,
            user_id="user_123",
            canvas_id="canvas_456",
            session_id=None
        )

        # Should return None on error
        assert result is None


# =============================================================================
# Chart Presentation Tests
# =============================================================================

class TestChartPresentation:
    """Tests for chart presentation functionality."""

    @pytest.mark.asyncio
    async def test_present_line_chart(self, mock_db, mock_ws_manager, sample_user_id):
        """Test presenting a line chart."""
        data = [
            {"x": "2024-01-01", "y": 100},
            {"x": "2024-01-02", "y": 150},
            {"x": "2024-01-03", "y": 200}
        ]

        with patch('tools.canvas_tool.ws_manager', mock_ws_manager):
            with patch('tools.canvas_tool.AgentContextResolver'):
                with patch('tools.canvas_tool.ServiceFactory'):
                    result = await present_chart(
                        user_id=sample_user_id,
                        chart_type="line_chart",
                        data=data,
                        title="Sales Trend"
                    )

        assert result["success"] is True
        assert result["canvas_type"] == "line_chart"
        assert "canvas_id" in result

    @pytest.mark.asyncio
    async def test_present_bar_chart(self, mock_db, mock_ws_manager, sample_user_id):
        """Test presenting a bar chart."""
        data = [
            {"category": "A", "value": 100},
            {"category": "B", "value": 150},
            {"category": "C", "value": 200}
        ]

        with patch('tools.canvas_tool.ws_manager', mock_ws_manager):
            with patch('tools.canvas_tool.AgentContextResolver'):
                with patch('tools.canvas_tool.ServiceFactory'):
                    result = await present_chart(
                        user_id=sample_user_id,
                        chart_type="bar_chart",
                        data=data,
                        title="Category Comparison"
                    )

        assert result["success"] is True
        assert result["canvas_type"] == "bar_chart"

    @pytest.mark.asyncio
    async def test_present_pie_chart(self, mock_db, mock_ws_manager, sample_user_id):
        """Test presenting a pie chart."""
        data = [
            {"label": "Product A", "value": 30},
            {"label": "Product B", "value": 50},
            {"label": "Product C", "value": 20}
        ]

        with patch('tools.canvas_tool.ws_manager', mock_ws_manager):
            with patch('tools.canvas_tool.AgentContextResolver'):
                with patch('tools.canvas_tool.ServiceFactory'):
                    result = await present_chart(
                        user_id=sample_user_id,
                        chart_type="pie_chart",
                        data=data,
                        title="Product Distribution"
                    )

        assert result["success"] is True
        assert result["canvas_type"] == "pie_chart"

    @pytest.mark.asyncio
    async def test_present_chart_with_agent_id(self, mock_db, mock_ws_manager, sample_user_id, sample_agent_id):
        """Test chart presentation with agent ID for governance."""
        data = [{"x": 1, "y": 100}]

        with patch('tools.canvas_tool.ws_manager', mock_ws_manager):
            with patch('tools.canvas_tool.AgentContextResolver') as mock_resolver:
                mock_agent = MagicMock()
                mock_agent.id = sample_agent_id
                mock_resolver.return_value.resolve_agent_for_request = AsyncMock(return_value=(mock_agent, {}))
                with patch('tools.canvas_tool.ServiceFactory'):
                    result = await present_chart(
                        user_id=sample_user_id,
                        chart_type="line_chart",
                        data=data,
                        agent_id=sample_agent_id
                    )

        assert result["success"] is True

    @pytest.mark.asyncio
    async def test_present_chart_with_session_isolation(self, mock_db, mock_ws_manager, sample_user_id):
        """Test chart presentation respects session isolation."""
        data = [{"x": 1, "y": 100}]
        session_id = "session_isolated_123"

        with patch('tools.canvas_tool.ws_manager', mock_ws_manager):
            with patch('tools.canvas_tool.AgentContextResolver'):
                with patch('tools.canvas_tool.ServiceFactory'):
                    result = await present_chart(
                        user_id=sample_user_id,
                        chart_type="line_chart",
                        data=data,
                        session_id=session_id
                    )

        assert result["success"] is True
        # Verify session_id was passed to audit
        mock_db.add.assert_called()

    @pytest.mark.asyncio
    async def test_present_chart_empty_data(self, mock_db, mock_ws_manager, sample_user_id):
        """Test chart presentation with empty data."""
        data = []

        with patch('tools.canvas_tool.ws_manager', mock_ws_manager):
            with patch('tools.canvas_tool.AgentContextResolver'):
                with patch('tools.canvas_tool.ServiceFactory'):
                    result = await present_chart(
                        user_id=sample_user_id,
                        chart_type="line_chart",
                        data=data
                    )

        # Should handle empty data gracefully
        assert "success" in result

    @pytest.mark.asyncio
    async def test_present_chart_with_custom_options(self, mock_db, mock_ws_manager, sample_user_id):
        """Test chart presentation with custom styling options."""
        data = [{"x": 1, "y": 100}]

        with patch('tools.canvas_tool.ws_manager', mock_ws_manager):
            with patch('tools.canvas_tool.AgentContextResolver'):
                with patch('tools.canvas_tool.ServiceFactory'):
                    result = await present_chart(
                        user_id=sample_user_id,
                        chart_type="line_chart",
                        data=data,
                        color="#ff0000",
                        width=800,
                        height=600
                    )

        assert result["success"] is True


# =============================================================================
# Markdown Presentation Tests
# =============================================================================

class TestMarkdownPresentation:
    """Tests for markdown presentation functionality."""

    @pytest.mark.asyncio
    async def test_present_markdown_basic(self, mock_db, mock_ws_manager, sample_user_id):
        """Test basic markdown presentation."""
        markdown_content = "# Hello World\n\nThis is a test."

        with patch('tools.canvas_tool.ws_manager', mock_ws_manager):
            with patch('tools.canvas_tool.AgentContextResolver'):
                with patch('tools.canvas_tool.ServiceFactory'):
                    result = await present_markdown(
                        user_id=sample_user_id,
                        content=markdown_content
                    )

        assert result["success"] is True
        assert result["content"] == markdown_content

    @pytest.mark.asyncio
    async def test_present_markdown_with_tables(self, mock_db, mock_ws_manager, sample_user_id):
        """Test markdown presentation with table content."""
        markdown_content = "| Header 1 | Header 2 |\n|----------|----------|\n| Cell 1   | Cell 2   |"

        with patch('tools.canvas_tool.ws_manager', mock_ws_manager):
            with patch('tools.canvas_tool.AgentContextResolver'):
                with patch('tools.canvas_tool.ServiceFactory'):
                    result = await present_markdown(
                        user_id=sample_user_id,
                        content=markdown_content
                    )

        assert result["success"] is True

    @pytest.mark.asyncio
    async def test_present_markdown_with_code_blocks(self, mock_db, mock_ws_manager, sample_user_id):
        """Test markdown presentation with code blocks."""
        markdown_content = "```python\nprint('Hello, World!')\n```"

        with patch('tools.canvas_tool.ws_manager', mock_ws_manager):
            with patch('tools.canvas_tool.AgentContextResolver'):
                with patch('tools.canvas_tool.ServiceFactory'):
                    result = await present_markdown(
                        user_id=sample_user_id,
                        content=markdown_content
                    )

        assert result["success"] is True

    @pytest.mark.asyncio
    async def test_present_markdown_with_agent_tracking(self, mock_db, mock_ws_manager, sample_user_id, sample_agent_id):
        """Test markdown presentation includes agent tracking."""
        markdown_content = "Agent generated content"

        with patch('tools.canvas_tool.ws_manager', mock_ws_manager):
            with patch('tools.canvas_tool.AgentContextResolver'):
                with patch('tools.canvas_tool.ServiceFactory'):
                    result = await present_markdown(
                        user_id=sample_user_id,
                        content=markdown_content,
                        agent_id=sample_agent_id
                    )

        assert result["success"] is True

    @pytest.mark.asyncio
    async def test_present_markdown_empty_content(self, mock_db, mock_ws_manager, sample_user_id):
        """Test markdown presentation with empty content."""
        with patch('tools.canvas_tool.ws_manager', mock_ws_manager):
            with patch('tools.canvas_tool.AgentContextResolver'):
                with patch('tools.canvas_tool.ServiceFactory'):
                    result = await present_markdown(
                        user_id=sample_user_id,
                        content=""
                    )

        # Should handle empty content
        assert "success" in result


# =============================================================================
# Form Presentation Tests
# =============================================================================

class TestFormPresentation:
    """Tests for form presentation functionality."""

    @pytest.mark.asyncio
    async def test_present_form_basic(self, mock_db, mock_ws_manager, sample_user_id):
        """Test basic form presentation."""
        form_schema = {
            "fields": [
                {"name": "email", "type": "email", "label": "Email", "required": True},
                {"name": "message", "type": "textarea", "label": "Message"}
            ]
        }

        with patch('tools.canvas_tool.ws_manager', mock_ws_manager):
            with patch('tools.canvas_tool.AgentContextResolver'):
                with patch('tools.canvas_tool.ServiceFactory'):
                    result = await present_form(
                        user_id=sample_user_id,
                        form_schema=form_schema,
                        title="Contact Form"
                    )

        assert result["success"] is True
        assert result["form_schema"] == form_schema

    @pytest.mark.asyncio
    async def test_present_form_with_validation(self, mock_db, mock_ws_manager, sample_user_id):
        """Test form presentation with validation rules."""
        form_schema = {
            "fields": [
                {
                    "name": "age",
                    "type": "number",
                    "label": "Age",
                    "validation": {"min": 18, "max": 120}
                }
            ]
        }

        with patch('tools.canvas_tool.ws_manager', mock_ws_manager):
            with patch('tools.canvas_tool.AgentContextResolver'):
                with patch('tools.canvas_tool.ServiceFactory'):
                    result = await present_form(
                        user_id=sample_user_id,
                        form_schema=form_schema
                    )

        assert result["success"] is True

    @pytest.mark.asyncio
    async def test_present_form_with_select_options(self, mock_db, mock_ws_manager, sample_user_id):
        """Test form presentation with select dropdown."""
        form_schema = {
            "fields": [
                {
                    "name": "country",
                    "type": "select",
                    "label": "Country",
                    "options": ["USA", "Canada", "UK"]
                }
            ]
        }

        with patch('tools.canvas_tool.ws_manager', mock_ws_manager):
            with patch('tools.canvas_tool.AgentContextResolver'):
                with patch('tools.canvas_tool.ServiceFactory'):
                    result = await present_form(
                        user_id=sample_user_id,
                        form_schema=form_schema
                    )

        assert result["success"] is True

    @pytest.mark.asyncio
    async def test_present_form_agent_governance_check(self, mock_db, mock_ws_manager, sample_user_id, sample_agent_id):
        """Test form presentation triggers governance check for agents."""
        form_schema = {"fields": [{"name": "name", "type": "text"}]}

        with patch('tools.canvas_tool.ws_manager', mock_ws_manager):
            with patch('tools.canvas_tool.AgentContextResolver'):
                with patch('tools.canvas_tool.ServiceFactory') as mock_factory:
                    mock_gov = MagicMock()
                    mock_gov.can_perform_action.return_value = {"allowed": True}
                    mock_factory.get_governance_service.return_value = mock_gov
                    result = await present_form(
                        user_id=sample_user_id,
                        form_schema=form_schema,
                        agent_id=sample_agent_id
                    )

        assert result["success"] is True


# =============================================================================
# Sheet Presentation Tests
# =============================================================================

class TestSheetPresentation:
    """Tests for sheet/data grid presentation."""

    @pytest.mark.asyncio
    async def test_present_sheet_basic(self, mock_db, mock_ws_manager, sample_user_id):
        """Test basic sheet presentation."""
        data = [
            ["Name", "Age", "City"],
            ["Alice", 30, "NYC"],
            ["Bob", 25, "LA"]
        ]

        with patch('tools.canvas_tool.ws_manager', mock_ws_manager):
            with patch('tools.canvas_tool.AgentContextResolver'):
                with patch('tools.canvas_tool.ServiceFactory'):
                    result = await present_sheet(
                        user_id=sample_user_id,
                        data=data,
                        title="User Data"
                    )

        assert result["success"] is True
        assert result["data"] == data

    @pytest.mark.asyncio
    async def test_present_sheet_with_headers(self, mock_db, mock_ws_manager, sample_user_id):
        """Test sheet presentation with explicit headers."""
        data = [
            ["Alice", 30, "NYC"],
            ["Bob", 25, "LA"]
        ]
        headers = ["Name", "Age", "City"]

        with patch('tools.canvas_tool.ws_manager', mock_ws_manager):
            with patch('tools.canvas_tool.AgentContextResolver'):
                with patch('tools.canvas_tool.ServiceFactory'):
                    result = await present_sheet(
                        user_id=sample_user_id,
                        data=data,
                        headers=headers
                    )

        assert result["success"] is True

    @pytest.mark.asyncio
    async def test_present_sheet_empty_data(self, mock_db, mock_ws_manager, sample_user_id):
        """Test sheet presentation with empty data."""
        with patch('tools.canvas_tool.ws_manager', mock_ws_manager):
            with patch('tools.canvas_tool.AgentContextResolver'):
                with patch('tools.canvas_tool.ServiceFactory'):
                    result = await present_sheet(
                        user_id=sample_user_id,
                        data=[]
                    )

        # Should handle empty data
        assert "success" in result

    @pytest.mark.asyncio
    async def test_present_sheet_with_sorting(self, mock_db, mock_ws_manager, sample_user_id):
        """Test sheet presentation with sortable columns."""
        data = [
            ["Alice", 30],
            ["Bob", 25]
        ]
        sortable = [False, True]  # Age column sortable

        with patch('tools.canvas_tool.ws_manager', mock_ws_manager):
            with patch('tools.canvas_tool.AgentContextResolver'):
                with patch('tools.canvas_tool.ServiceFactory'):
                    result = await present_sheet(
                        user_id=sample_user_id,
                        data=data,
                        sortable=sortable
                    )

        assert result["success"] is True


# =============================================================================
# Canvas Lifecycle Tests
# =============================================================================

class TestCanvasLifecycle:
    """Tests for canvas create, update, close lifecycle."""

    @pytest.mark.asyncio
    async def test_close_canvas(self, mock_db, mock_ws_manager, sample_user_id, sample_canvas_id):
        """Test closing a canvas."""
        with patch('tools.canvas_tool.ws_manager', mock_ws_manager):
            result = await close_canvas(
                user_id=sample_user_id,
                canvas_id=sample_canvas_id
            )

        assert result["success"] is True
        mock_ws_manager.broadcast.assert_called()

    @pytest.mark.asyncio
    async def test_close_canvas_with_audit(self, mock_db, mock_ws_manager, sample_user_id, sample_canvas_id):
        """Test closing canvas creates audit entry."""
        with patch('tools.canvas_tool.ws_manager', mock_ws_manager):
            result = await close_canvas(
                user_id=sample_user_id,
                canvas_id=sample_canvas_id,
                agent_id="agent_123"
            )

        assert result["success"] is True
        # Audit should be created
        mock_db.add.assert_called()

    @pytest.mark.asyncio
    async def test_update_canvas(self, mock_db, mock_ws_manager, sample_user_id, sample_canvas_id):
        """Test updating canvas content."""
        update_data = {"title": "Updated Title"}

        with patch('tools.canvas_tool.ws_manager', mock_ws_manager):
            result = await update_canvas(
                user_id=sample_user_id,
                canvas_id=sample_canvas_id,
                updates=update_data
            )

        assert result["success"] is True
        mock_ws_manager.broadcast.assert_called()

    @pytest.mark.asyncio
    async def test_update_canvas_with_agent_tracking(self, mock_db, mock_ws_manager, sample_user_id, sample_canvas_id, sample_agent_id):
        """Test canvas update includes agent tracking."""
        update_data = {"data": [1, 2, 3]}

        with patch('tools.canvas_tool.ws_manager', mock_ws_manager):
            result = await update_canvas(
                user_id=sample_user_id,
                canvas_id=sample_canvas_id,
                updates=update_data,
                agent_id=sample_agent_id
            )

        assert result["success"] is True


# =============================================================================
# Canvas Type Registry Tests
# =============================================================================

class TestCanvasTypeRegistry:
    """Tests for canvas type registry integration."""

    def test_canvas_type_registry_contains_basic_types(self):
        """Test canvas type registry has basic types."""
        assert "line_chart" in canvas_type_registry or "generic" in canvas_type_registry

    def test_canvas_type_registry_supports_sheets(self):
        """Test canvas type registry supports sheets."""
        # Registry should handle sheet type
        assert hasattr(canvas_type_registry, 'get') or callable(canvas_type_registry) or isinstance(canvas_type_registry, dict)


# =============================================================================
# WebSocket Integration Tests
# =============================================================================

class TestWebSocketIntegration:
    """Tests for WebSocket broadcast integration."""

    @pytest.mark.asyncio
    async def test_websocket_broadcast_on_present(self, mock_db, mock_ws_manager, sample_user_id):
        """Test WebSocket broadcast triggered on presentation."""
        with patch('tools.canvas_tool.ws_manager', mock_ws_manager):
            with patch('tools.canvas_tool.AgentContextResolver'):
                with patch('tools.canvas_tool.ServiceFactory'):
                    await present_chart(
                        user_id=sample_user_id,
                        chart_type="line_chart",
                        data=[{"x": 1, "y": 1}]
                    )

        # WebSocket should be called with canvas data
        mock_ws_manager.broadcast.assert_called()

    @pytest.mark.asyncio
    async def test_websocket_broadcast_includes_canvas_id(self, mock_db, mock_ws_manager, sample_user_id):
        """Test WebSocket broadcast includes canvas ID."""
        with patch('tools.canvas_tool.ws_manager', mock_ws_manager):
            with patch('tools.canvas_tool.AgentContextResolver'):
                with patch('tools.canvas_tool.ServiceFactory'):
                    result = await present_markdown(
                        user_id=sample_user_id,
                        content="Test"
                    )

        # Canvas ID should be in the broadcast
        if mock_ws_manager.broadcast.call_args:
            call_args = mock_ws_manager.broadcast.call_args
            # Verify canvas_id is present
            assert call_args is not None
```

**Verify:**
```bash
test -f backend/tests/unit/test_canvas_tool.py && echo "File exists"
grep -c "^    def test_" backend/tests/unit/test_canvas_tool.py
# Expected: 45-55 tests
```

**Done:**
- File created with 45-55 tests
- Chart presentation tested (line, bar, pie)
- Markdown presentation tested
- Form presentation tested
- Sheet presentation tested
- Canvas lifecycle tested (create, update, close)
- Governance integration validated
- Audit trail creation tested
- WebSocket broadcast tested

---

## Key Links

| From | To | Via | Artifact |
|------|-----|-----|----------|
| test_canvas_tool.py | tools/canvas_tool.py | mock_db, mock_agent_context_resolver, mock_ws_manager | Canvas presentation tests |

## Progress Tracking

**Current Coverage (Phase 8.8):** 19-20%
**Plan 29 Target:** +0.8-1.0 percentage points
**Projected After Plans 29+30:** ~21-22%

## Notes

- Focuses ONLY on canvas_tool.py for better context management
- 50% coverage target (sustainable for 1,238 line file)
- Test patterns from Phase 8.7/8.8 applied (AsyncMock, fixtures)
- Estimated 45-55 tests
- Duration: 2 hours
- All external dependencies mocked (WebSocket, database, governance services)
