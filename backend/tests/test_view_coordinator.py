"""
View Coordinator Tests

Tests for multi-view orchestration system.
"""

import pytest
import uuid
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime

from core.database import SessionLocal
from core.models import (
    User,
    Workspace,
    AgentRegistry,
    ViewOrchestrationState,
    CanvasAudit
)
from core.view_coordinator import ViewCoordinator


@pytest.fixture
def db():
    """Database session fixture."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture
def test_user(db):
    """Create test user."""
    user = User(
        id=str(uuid.uuid4()),
        email="test@example.com",
        password_hash="hash"
    )
    db.add(user)
    db.commit()
    return user


@pytest.fixture
def test_agent(db):
    """Create test agent."""
    agent = AgentRegistry(
        id=str(uuid.uuid4()),
        name="Test Agent",
        agent_type="assistant",
        status="intern",
        confidence_score=0.6
    )
    db.add(agent)
    db.commit()
    return agent


@pytest.fixture
def view_coordinator(db):
    """View coordinator fixture."""
    return ViewCoordinator(db)


@pytest.mark.asyncio
async def test_switch_to_browser_view(view_coordinator, test_user, test_agent):
    """Test switching to browser view."""
    with patch('core.websockets.manager.broadcast') as mock_broadcast:
        await view_coordinator.switch_to_browser_view(
            user_id=test_user.id,
            agent_id=test_agent.id,
            url="https://example.com",
            guidance="Opening browser for automation"
        )

        # Verify broadcast called
        mock_broadcast.assert_called_once()
        call_args = mock_broadcast.call_args
        assert call_args[0][0] == f"user:{test_user.id}"

        # Verify message structure
        message = call_args[0][1]
        assert message["type"] == "view:switch"
        assert message["data"]["view_type"] == "browser"
        assert message["data"]["url"] == "https://example.com"
        assert message["data"]["canvas_guidance"]["agent_id"] == test_agent.id


@pytest.mark.asyncio
async def test_switch_to_browser_view_creates_state(db, view_coordinator, test_user, test_agent):
    """Test that switch_to_browser_view creates orchestration state."""
    with patch('core.websockets.manager.broadcast'):
        await view_coordinator.switch_to_browser_view(
            user_id=test_user.id,
            agent_id=test_agent.id,
            url="https://slack.com/oauth",
            guidance="OAuth flow"
        )

    # Verify state created
    state = db.query(ViewOrchestrationState).filter(
        ViewOrchestrationState.user_id == test_user.id
    ).first()

    assert state is not None
    assert state.user_id == test_user.id
    assert state.controlling_agent == test_agent.id
    assert state.layout == "split_vertical"
    assert len(state.active_views) > 0


@pytest.mark.asyncio
async def test_switch_to_terminal_view(view_coordinator, test_user, test_agent):
    """Test switching to terminal view."""
    with patch('core.websockets.manager.broadcast') as mock_broadcast:
        await view_coordinator.switch_to_terminal_view(
            user_id=test_user.id,
            agent_id=test_agent.id,
            command="ls -la",
            guidance="Listing directory contents"
        )

        # Verify broadcast
        mock_broadcast.assert_called_once()
        message = mock_broadcast.call_args[0][1]
        assert message["data"]["view_type"] == "terminal"
        assert message["data"]["command"] == "ls -la"


@pytest.mark.asyncio
async def test_set_layout(view_coordinator, test_user):
    """Test setting view layout."""
    with patch('core.websockets.manager.broadcast') as mock_broadcast:
        # First create a state
        with patch('core.websockets.manager.broadcast'):
            await view_coordinator.switch_to_browser_view(
                user_id=test_user.id,
                agent_id=str(uuid.uuid4()),
                url="https://example.com",
                guidance="Test"
            )

        # Now change layout
        await view_coordinator.set_layout(
            user_id=test_user.id,
            layout="tabs"
        )

        # Verify broadcast
        mock_broadcast.assert_called()
        message = mock_broadcast.call_args[0][1]
        assert message["data"]["layout"] == "tabs"


@pytest.mark.asyncio
async def test_activate_view(view_coordinator, test_user):
    """Test activating a new view."""
    with patch('core.websockets.manager.broadcast') as mock_broadcast:
        await view_coordinator.activate_view(
            user_id=test_user.id,
            view_type="browser",
            position="left",
            size="1/2",
            url="https://example.com"
        )

        # Verify broadcast
        mock_broadcast.assert_called_once()
        message = mock_broadcast.call_args[0][1]
        assert message["type"] == "view:activated"
        assert message["data"]["view"]["view_type"] == "browser"


@pytest.mark.asyncio
async def test_update_view_guidance(view_coordinator, test_user):
    """Test updating view guidance."""
    view_id = "test_view_123"

    with patch('core.websockets.manager.broadcast') as mock_broadcast:
        await view_coordinator.update_view_guidance(
            user_id=test_user.id,
            view_id=view_id,
            guidance="New guidance message"
        )

        # Verify broadcast
        mock_broadcast.assert_called_once()
        message = mock_broadcast.call_args[0][1]
        assert message["type"] == "view:guidance_update"
        assert message["data"]["view_id"] == view_id
        assert message["data"]["guidance"] == "New guidance message"


@pytest.mark.asyncio
async def test_close_view(db, view_coordinator, test_user):
    """Test closing a view."""
    # First create a state with a view
    with patch('core.websockets.manager.broadcast'):
        await view_coordinator.switch_to_browser_view(
            user_id=test_user.id,
            agent_id=str(uuid.uuid4()),
            url="https://example.com",
            guidance="Test"
        )

    # Get the view_id
    state = db.query(ViewOrchestrationState).filter(
        ViewOrchestrationState.user_id == test_user.id
    ).first()
    view_id = state.active_views[0]["view_id"]

    # Now close it
    with patch('core.websockets.manager.broadcast') as mock_broadcast:
        await view_coordinator.close_view(
            user_id=test_user.id,
            view_id=view_id
        )

        # Verify broadcast
        mock_broadcast.assert_called_once()
        message = mock_broadcast.call_args[0][1]
        assert message["type"] == "view:closed"
        assert message["data"]["view_id"] == view_id


@pytest.mark.asyncio
async def test_multiple_views_same_session(db, view_coordinator, test_user, test_agent):
    """Test multiple views in same session."""
    session_id = "test_session_123"

    with patch('core.websockets.manager.broadcast'):
        # Add browser view
        await view_coordinator.switch_to_browser_view(
            user_id=test_user.id,
            agent_id=test_agent.id,
            url="https://example.com",
            guidance="Browser view",
            session_id=session_id
        )

        # Add terminal view
        await view_coordinator.switch_to_terminal_view(
            user_id=test_user.id,
            agent_id=test_agent.id,
            command="echo 'hello'",
            guidance="Terminal view",
            session_id=session_id
        )

    # Verify both views in state
    state = db.query(ViewOrchestrationState).filter(
        ViewOrchestrationState.session_id == session_id
    ).first()

    assert state is not None
    assert len(state.active_views) >= 2

    view_types = [v["view_type"] for v in state.active_views]
    assert "browser" in view_types
    assert "terminal" in view_types


def test_view_coordinator_instantiation(db):
    """Test ViewCoordinator can be instantiated."""
    from core.view_coordinator import get_view_coordinator

    coordinator = get_view_coordinator(db)
    assert coordinator is not None
    assert coordinator.db == db


@pytest.mark.asyncio
async def test_feature_flag_disabled(db, test_user, test_agent):
    """Test that operations skip when feature flag disabled."""
    coordinator = ViewCoordinator(db)

    with patch('core.view_coordinator.VIEW_COORDINATION_ENABLED', False):
        with patch('core.websockets.manager.broadcast') as mock_broadcast:
            await coordinator.switch_to_browser_view(
                user_id=test_user.id,
                agent_id=test_agent.id,
                url="https://example.com",
                guidance="Test"
            )

            # Should not broadcast
            mock_broadcast.assert_not_called()


@pytest.mark.asyncio
async def test_view_state_persistence(db, view_coordinator, test_user, test_agent):
    """Test that view state persists across operations."""
    session_id = "persistent_session"

    with patch('core.websockets.manager.broadcast'):
        # Create initial state
        await view_coordinator.switch_to_browser_view(
            user_id=test_user.id,
            agent_id=test_agent.id,
            url="https://example.com",
            guidance="Initial view",
            session_id=session_id
        )

    # Get state
    state = db.query(ViewOrchestrationState).filter(
        ViewOrchestrationState.session_id == session_id
    ).first()

    initial_view_count = len(state.active_views)

    # Add another view
    with patch('core.websockets.manager.broadcast'):
        await view_coordinator.switch_to_terminal_view(
            user_id=test_user.id,
            agent_id=test_agent.id,
            command="ls",
            guidance="Second view",
            session_id=session_id
        )

    # Verify state persisted and updated
    state = db.query(ViewOrchestrationState).filter(
        ViewOrchestrationState.session_id == session_id
    ).first()

    assert len(state.active_views) == initial_view_count + 1
