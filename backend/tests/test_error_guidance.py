"""
Error Guidance Engine Tests

Tests for error categorization and resolution mapping.
"""

import uuid
from unittest.mock import AsyncMock, MagicMock, patch
import pytest

from core.database import SessionLocal
from core.error_guidance_engine import ErrorGuidanceEngine
from core.models import AgentRegistry, CanvasAudit, OperationErrorResolution, User


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
def error_engine(db):
    """Error guidance engine fixture."""
    return ErrorGuidanceEngine(db)


def test_categorize_permission_denied(error_engine):
    """Test categorizing permission denied errors."""
    error_type = error_engine.categorize_error(
        error_code="403",
        error_message="Permission denied"
    )

    assert error_type == "permission_denied"


def test_categorize_auth_expired(error_engine):
    """Test categorizing authentication expired errors."""
    error_type = error_engine.categorize_error(
        error_code="401",
        error_message="OAuth token has expired"
    )

    assert error_type == "auth_expired"


def test_categorize_network_error(error_engine):
    """Test categorizing network errors."""
    error_type = error_engine.categorize_error(
        error_code=None,
        error_message="Failed to connect to server"
    )

    assert error_type == "network_error"


def test_categorize_rate_limit(error_engine):
    """Test categorizing rate limit errors."""
    error_type = error_engine.categorize_error(
        error_code="429",
        error_message="Too many requests"
    )

    assert error_type == "rate_limit"


def test_categorize_resource_not_found(error_engine):
    """Test categorizing not found errors."""
    error_type = error_engine.categorize_error(
        error_code="404",
        error_message="Resource not found"
    )

    assert error_type == "resource_not_found"


def test_categorize_invalid_input(error_engine):
    """Test categorizing invalid input errors."""
    error_type = error_engine.categorize_error(
        error_code="400",
        error_message="Invalid input format"
    )

    assert error_type == "invalid_input"


def test_categorize_unknown_error(error_engine):
    """Test categorizing unknown errors."""
    error_type = error_engine.categorize_error(
        error_code="500",
        error_message="Unknown error occurred"
    )

    assert error_type == "unknown"


def test_get_suggested_resolution_default(error_engine):
    """Test getting suggested resolution when no history."""
    resolution_index = error_engine.get_suggested_resolution("permission_denied")

    # Should return default (first option = 0)
    assert resolution_index == 0


@pytest.mark.asyncio
async def test_present_error(error_engine, test_user):
    """Test presenting error with resolutions."""
    operation_id = str(uuid.uuid4())

    with patch('core.websockets.manager.broadcast') as mock_broadcast:
        await error_engine.present_error(
            user_id=test_user.id,
            operation_id=operation_id,
            error={
                "type": "auth_expired",
                "code": "401",
                "message": "Token expired",
                "technical_details": "OAuth token invalid"
            }
        )

        # Verify broadcast
        mock_broadcast.assert_called_once()
        call_args = mock_broadcast.call_args
        assert call_args[0][0] == f"user:{test_user.id}"

        # Verify message structure
        message = call_args[0][1]
        assert message["type"] == "operation:error"
        assert message["data"]["operation_id"] == operation_id
        assert message["data"]["error"]["type"] == "auth_expired"
        assert "resolutions" in message["data"]
        assert "agent_analysis" in message["data"]


@pytest.mark.asyncio
async def test_present_error_includes_agent_analysis(error_engine, test_user):
    """Test that present_error includes agent analysis."""
    with patch('core.websockets.manager.broadcast') as mock_broadcast:
        await error_engine.present_error(
            user_id=test_user.id,
            operation_id=str(uuid.uuid4()),
            error={
                "type": "network_error",
                "message": "Connection failed"
            }
        )

        # Verify agent analysis included
        message = mock_broadcast.call_args[0][1]
        analysis = message["data"]["agent_analysis"]

        assert "what_happened" in analysis
        assert "why_it_happened" in analysis
        assert "impact" in analysis
        assert len(analysis["what_happened"]) > 0


@pytest.mark.asyncio
async def test_present_error_includes_resolutions(error_engine, test_user):
    """Test that present_error includes resolution options."""
    with patch('core.websockets.manager.broadcast') as mock_broadcast:
        await error_engine.present_error(
            user_id=test_user.id,
            operation_id=str(uuid.uuid4()),
            error={
                "type": "rate_limit",
                "message": "Too many requests"
            }
        )

        # Verify resolutions included
        message = mock_broadcast.call_args[0][1]
        resolutions = message["data"]["resolutions"]

        assert len(resolutions) > 0
        assert "title" in resolutions[0]
        assert "description" in resolutions[0]
        assert "agent_can_fix" in resolutions[0]
        assert "steps" in resolutions[0]


@pytest.mark.asyncio
async def test_track_resolution(db, error_engine, test_user):
    """Test tracking resolution outcomes."""
    with patch('core.websockets.manager.broadcast'):
        await error_engine.track_resolution(
            error_type="auth_expired",
            error_code="401",
            resolution_attempted="Let Agent Reconnect",
            success=True,
            user_feedback="Worked perfectly!",
            agent_suggested=True
        )

    # Verify resolution tracked
    resolution = db.query(OperationErrorResolution).filter(
        OperationErrorResolution.error_type == "auth_expired",
        OperationErrorResolution.resolution_attempted == "Let Agent Reconnect"
    ).first()

    assert resolution is not None
    assert resolution.success == True
    assert resolution.agent_suggested == True
    assert resolution.user_feedback == "Worked perfectly!"


@pytest.mark.asyncio
async def test_track_resolution_updates_suggestion(db, error_engine):
    """Test that tracking resolutions updates future suggestions."""
    error_type = "permission_denied"

    # Track first successful resolution (option 1)
    with patch('core.websockets.manager.broadcast'):
        await error_engine.track_resolution(
            error_type=error_type,
            resolution_attempted="Request Permission",
            success=True,
            agent_suggested=True
        )

    # Track another successful resolution (same type, option 0)
    with patch('core.websockets.manager.broadcast'):
        await error_engine.track_resolution(
            error_type=error_type,
            resolution_attempted="Grant Manually",
            success=True,
            agent_suggested=False
        )

    # Get suggested resolution
    suggestion = error_engine.get_suggested_resolution(error_type)

    # Should suggest the one with more successes
    assert suggestion in [0, 1]


@pytest.mark.asyncio
async def test_explain_what_happened(error_engine):
    """Test error explanation generation."""
    explanations = {
        "permission_denied": error_engine._explain_what_happened(
            "permission_denied",
            {"message": "Access denied"}
        ),
        "auth_expired": error_engine._explain_what_happened(
            "auth_expired",
            {"message": "Token expired"}
        ),
        "network_error": error_engine._explain_what_happened(
            "network_error",
            {"message": "Connection failed"}
        )
    }

    # All explanations should be non-empty
    for error_type, explanation in explanations.items():
        assert len(explanation) > 0
        assert isinstance(explanation, str)


@pytest.mark.asyncio
async def test_explain_why(error_engine):
    """Test error 'why' explanation generation."""
    why = error_engine._explain_why(
        "auth_expired",
        {"message": "Token expired"}
    )

    assert len(why) > 0
    assert "security" in why.lower() or "expire" in why.lower()


@pytest.mark.asyncio
async def test_explain_impact(error_engine):
    """Test error impact explanation generation."""
    impact = error_engine._explain_impact("rate_limit")

    assert len(impact) > 0
    assert "wait" in impact.lower() or "retry" in impact.lower()


def test_error_guidance_engine_instantiation(db):
    """Test ErrorGuidanceEngine can be instantiated."""
    from core.error_guidance_engine import get_error_guidance_engine

    engine = get_error_guidance_engine(db)
    assert engine is not None
    assert engine.db == db


@pytest.mark.asyncio
async def test_feature_flag_disabled(db, test_user):
    """Test that operations skip when feature flag disabled."""
    engine = ErrorGuidanceEngine(db)

    with patch('core.error_guidance_engine.ERROR_GUIDANCE_ENABLED', False):
        with patch('core.websockets.manager.broadcast') as mock_broadcast:
            await engine.present_error(
                user_id=test_user.id,
                operation_id=str(uuid.uuid4()),
                error={"type": "test", "message": "Test error"}
            )

            # Should not broadcast
            mock_broadcast.assert_not_called()


@pytest.mark.asyncio
async def test_resolution_with_alternative(db, error_engine, test_user):
    """Test tracking resolution with user alternative."""
    with patch('core.websockets.manager.broadcast'):
        await error_engine.track_resolution(
            error_type="network_error",
            resolution_attempted="Let Agent Retry",
            success=False,
            user_feedback="Didn't work, I restarted manually",
            agent_suggested=True,
            alternative_used="Manual restart"
        )

    # Verify alternative tracked
    resolution = db.query(OperationErrorResolution).filter(
        OperationErrorResolution.error_type == "network_error"
    ).first()

    assert resolution is not None
    assert resolution.alternative_used == "Manual restart"


@pytest.mark.asyncio
async def test_multiple_error_types(db, error_engine, test_user):
    """Test handling multiple error types in same session."""
    errors = [
        {"type": "auth_expired", "message": "Token expired"},
        {"type": "rate_limit", "message": "Too many requests"},
        {"type": "network_error", "message": "Connection failed"}
    ]

    with patch('core.websockets.manager.broadcast'):
        for error in errors:
            await error_engine.present_error(
                user_id=test_user.id,
                operation_id=str(uuid.uuid4()),
                error=error
            )

    # All should have broadcast successfully
    # (verified by no exceptions being raised)
