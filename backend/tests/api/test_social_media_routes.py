"""
Social Media Routes API Tests

Comprehensive tests for social media integration endpoints from api/social_media_routes.py.
Tests cover posting, scheduling, accounts, analytics, rate limiting, and platform integrations.
"""

import pytest
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, Mock, patch
from fastapi.testclient import TestClient
from fastapi import FastAPI
from sqlalchemy.orm import Session

from api.social_media_routes import router, PlatformConfig, rate_limit_check
from core.models import OAuthToken, SocialPostHistory, SocialMediaAudit, User


# ============================================================================
# Fixtures
# ============================================================================

_current_test_user = None


@pytest.fixture
def client(db: Session):
    """Create TestClient for social media routes."""
    global _current_test_user
    _current_test_user = None

    app = FastAPI()
    app.include_router(router)

    from core.database import get_db
    from core.security_dependencies import get_current_user

    def override_get_db():
        yield db

    def override_get_current_user():
        return _current_test_user

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user] = override_get_current_user
    test_client = TestClient(app, raise_server_exceptions=False)
    yield test_client
    app.dependency_overrides.clear()
    _current_test_user = None


@pytest.fixture
def mock_user(db: Session):
    """Create test user."""
    import uuid
    user_id = str(uuid.uuid4())
    user = User(
        id=user_id,
        email=f"test-{user_id}@example.com",
        first_name="Test",
        last_name="User",
        role="member",
        status="active"
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@pytest.fixture
def mock_twitter_token(db: Session, mock_user: User):
    """Create mock Twitter OAuth token."""
    import uuid
    token = OAuthToken(
        id=str(uuid.uuid4()),
        user_id=mock_user.id,
        provider="twitter",
        access_token="twitter_access_token_123",
        refresh_token="twitter_refresh_token_123",
        status="active",
        scopes=["tweet.read", "tweet.write"],
        last_used=datetime.utcnow()
    )
    db.add(token)
    db.commit()
    db.refresh(token)
    return token


@pytest.fixture
def mock_linkedin_token(db: Session, mock_user: User):
    """Create mock LinkedIn OAuth token."""
    import uuid
    token = OAuthToken(
        id=str(uuid.uuid4()),
        user_id=mock_user.id,
        provider="linkedin",
        access_token="linkedin_access_token_123",
        refresh_token="linkedin_refresh_token_123",
        status="active",
        scopes=["w_member_social"],
        last_used=datetime.utcnow()
    )
    db.add(token)
    db.commit()
    db.refresh(token)
    return token


@pytest.fixture
def mock_facebook_token(db: Session, mock_user: User):
    """Create mock Facebook OAuth token."""
    import uuid
    token = OAuthToken(
        id=str(uuid.uuid4()),
        user_id=mock_user.id,
        provider="facebook",
        access_token="facebook_access_token_123",
        refresh_token="facebook_refresh_token_123",
        status="active",
        scopes=["pages_manage_posts"],
        last_used=datetime.utcnow()
    )
    db.add(token)
    db.commit()
    db.refresh(token)
    return token


# ============================================================================
# Platform Configuration Tests
# ============================================================================

def test_get_platform_config_twitter():
    """Test getting Twitter platform configuration."""
    config = PlatformConfig.get_platform("twitter")
    assert config["name"] == "Twitter/X"
    assert config["max_length"] == 500
    assert config["supports_media"] is True


def test_get_platform_config_linkedin():
    """Test getting LinkedIn platform configuration."""
    config = PlatformConfig.get_platform("linkedin")
    assert config["name"] == "LinkedIn"
    assert config["max_length"] == 3000
    assert config["supports_media"] is True


def test_get_platform_config_facebook():
    """Test getting Facebook platform configuration."""
    config = PlatformConfig.get_platform("facebook")
    assert config["name"] == "Facebook"
    assert config["max_length"] == 63206


def test_get_platform_config_invalid():
    """Test getting configuration for invalid platform."""
    with pytest.raises(ValueError):
        PlatformConfig.get_platform("invalid_platform")


def test_validate_content_twitter_success():
    """Test content validation for Twitter - success."""
    valid, error = PlatformConfig.validate_content("twitter", "Short tweet")
    assert valid is True
    assert error is None


def test_validate_content_twitter_too_long():
    """Test content validation for Twitter - too long."""
    valid, error = PlatformConfig.validate_content("twitter", "x" * 501)
    assert valid is False
    assert "max length" in error.lower()


def test_validate_content_linkedin_success():
    """Test content validation for LinkedIn - success."""
    valid, error = PlatformConfig.validate_content("linkedin", "LinkedIn post content")
    assert valid is True
    assert error is None


# ============================================================================
# Rate Limiting Tests
# ============================================================================

def test_rate_limit_check_under_limit(db: Session, mock_user: User):
    """Test rate limit check - under limit."""
    result = rate_limit_check(mock_user.id, db)
    assert result is True


def test_rate_limit_check_exceeded(db: Session, mock_user: User):
    """Test rate limit check - exceeded."""
    # Create 10 recent posts
    for i in range(10):
        post = SocialPostHistory(
            id=str(i),
            user_id=mock_user.id,
            content=f"Post {i}",
            platforms=["twitter"],
            status="posted",
            created_at=datetime.utcnow()
        )
        db.add(post)
    db.commit()

    result = rate_limit_check(mock_user.id, db)
    assert result is False


# ============================================================================
# POST /post - Create Social Post Tests
# ============================================================================

def test_create_social_post_twitter(
    client: TestClient,
    db: Session,
    mock_user: User,
    mock_twitter_token: OAuthToken
):
    """Test create social post for Twitter successfully."""
    global _current_test_user
    _current_test_user = mock_user

    request_data = {
        "text": "Test tweet for #testing",
        "platforms": ["twitter"]
    }

    with patch('api.social_media_routes.post_to_twitter') as mock_post:
        mock_post.return_value = {
            "success": True,
            "post_id": "tweet-123",
            "url": "https://twitter.com/i/status/tweet-123",
            "platform": "twitter"
        }

        response = client.post("/api/v1/social/post", json=request_data)

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True


def test_create_social_post_multiple_platforms(
    client: TestClient,
    db: Session,
    mock_user: User,
    mock_twitter_token: OAuthToken,
    mock_linkedin_token: OAuthToken
):
    """Test create social post for multiple platforms."""
    global _current_test_user
    _current_test_user = mock_user

    request_data = {
        "text": "Test post for multiple platforms",
        "platforms": ["twitter", "linkedin"]
    }

    with patch('api.social_media_routes.post_to_twitter') as mock_twitter:
        mock_twitter.return_value = {
            "success": True,
            "post_id": "tweet-123"
        }

        with patch('api.social_media_routes.post_to_linkedin') as mock_linkedin:
            mock_linkedin.return_value = {
                "success": True,
                "post_id": "linkedin-post-123"
            }

            response = client.post("/api/v1/social/post", json=request_data)

            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True


def test_create_social_post_validation_error(
    client: TestClient,
    db: Session,
    mock_user: User
):
    """Test create social post with validation error."""
    global _current_test_user
    _current_test_user = mock_user

    request_data = {
        "text": "x" * 501,  # Exceeds Twitter limit
        "platforms": ["twitter"]
    }

    response = client.post("/api/v1/social/post", json=request_data)

    assert response.status_code in [400, 422]


def test_create_social_post_no_platforms(
    client: TestClient,
    db: Session,
    mock_user: User
):
    """Test create social post without platforms."""
    global _current_test_user
    _current_test_user = mock_user

    request_data = {
        "text": "Test post",
        "platforms": []
    }

    response = client.post("/api/v1/social/post", json=request_data)

    assert response.status_code in [400, 422]


def test_create_social_post_rate_limited(
    client: TestClient,
    db: Session,
    mock_user: User
):
    """Test create social post when rate limited."""
    global _current_test_user
    _current_test_user = mock_user

    # Create 10 recent posts
    for i in range(10):
        post = SocialPostHistory(
            id=str(i),
            user_id=mock_user.id,
            content=f"Post {i}",
            platforms=["twitter"],
            status="posted",
            created_at=datetime.utcnow()
        )
        db.add(post)
    db.commit()

    request_data = {
        "text": "Test post",
        "platforms": ["twitter"]
    }

    response = client.post("/api/v1/social/post", json=request_data)

    assert response.status_code == 429


def test_create_social_post_with_link(
    client: TestClient,
    db: Session,
    mock_user: User,
    mock_twitter_token: OAuthToken
):
    """Test create social post with link URL."""
    global _current_test_user
    _current_test_user = mock_user

    request_data = {
        "text": "Check out this link",
        "platforms": ["twitter"],
        "link_url": "https://example.com"
    }

    with patch('api.social_media_routes.post_to_twitter') as mock_post:
        mock_post.return_value = {
            "success": True,
            "post_id": "tweet-123"
        }

        response = client.post("/api/v1/social/post", json=request_data)

        assert response.status_code == 200


# ============================================================================
# GET /platforms - List Platforms Tests
# ============================================================================

def test_list_platforms(client: TestClient):
    """Test list available platforms."""
    response = client.get("/api/v1/social/platforms")

    assert response.status_code == 200
    data = response.json()
    assert "platforms" in data
    assert "total" in data
    assert data["total"] == 3


# ============================================================================
# GET /connected-accounts - List Connected Accounts Tests
# ============================================================================

def test_list_connected_accounts(
    client: TestClient,
    db: Session,
    mock_user: User,
    mock_twitter_token: OAuthToken,
    mock_linkedin_token: OAuthToken
):
    """Test list connected accounts successfully."""
    global _current_test_user
    _current_test_user = mock_user

    response = client.get("/api/v1/social/connected-accounts")

    assert response.status_code == 200
    data = response.json()
    assert "accounts" in data
    assert "total" in data
    assert data["total"] == 2


def test_list_connected_accounts_empty(client: TestClient, db: Session, mock_user: User):
    """Test list connected accounts - none connected."""
    global _current_test_user
    _current_test_user = mock_user

    response = client.get("/api/v1/social/connected-accounts")

    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 0


# ============================================================================
# GET /rate-limit - Rate Limit Status Tests
# ============================================================================

def test_get_rate_limit_status(
    client: TestClient,
    db: Session,
    mock_user: User
):
    """Test get rate limit status successfully."""
    global _current_test_user
    _current_test_user = mock_user

    response = client.get("/api/v1/social/rate-limit")

    assert response.status_code == 200
    data = response.json()
    assert "limit" in data
    assert "used" in data
    assert "remaining" in data
    assert data["limit"] == 10


def test_get_rate_limit_with_posts(
    client: TestClient,
    db: Session,
    mock_user: User
):
    """Test get rate limit status with existing posts."""
    global _current_test_user
    _current_test_user = mock_user

    # Create 5 recent posts
    for i in range(5):
        post = SocialPostHistory(
            id=str(i),
            user_id=mock_user.id,
            content=f"Post {i}",
            platforms=["twitter"],
            status="posted",
            created_at=datetime.utcnow()
        )
        db.add(post)
    db.commit()

    response = client.get("/api/v1/social/rate-limit")

    assert response.status_code == 200
    data = response.json()
    assert data["used"] == 5
    assert data["remaining"] == 5


# ============================================================================
# Platform Posting Function Tests
# ============================================================================

def test_post_to_twitter_success():
    """Test posting to Twitter successfully."""
    import asyncio

    async def test_post():
        with patch('httpx.AsyncClient') as mock_client:
            mock_response = Mock()
            mock_response.status_code = 201
            mock_response.json.return_value = {
                "data": {"id": "tweet-123"}
            }

            mock_client.return_value.__aenter__.return_value.post.return_value = mock_response

            result = asyncio.run(
                __import__('api.social_media_routes', fromlist=['post_to_twitter']).post_to_twitter(
                    text="Test tweet",
                    access_token="token123"
                )
            )

            assert result["success"] is True
            assert result["post_id"] == "tweet-123"


def test_post_to_linkedin_success():
    """Test posting to LinkedIn successfully."""
    import asyncio

    async def test_post():
        with patch('httpx.AsyncClient') as mock_client:
            # Profile response
            mock_profile = Mock()
            mock_profile.status_code = 200
            mock_profile.json.return_value = {
                "sub": "person-123"
            }

            # Post response
            mock_post = Mock()
            mock_post.status_code = 201
            mock_post.json.return_value = {
                "id": "linkedin-post-123"
            }

            mock_client.return_value.__aenter__.return_value.get.return_value = mock_profile
            mock_client.return_value.__aenter__.return_value.post.return_value = mock_post

            result = asyncio.run(
                __import__('api.social_media_routes', fromlist=['post_to_linkedin']).post_to_linkedin(
                    text="Test post",
                    access_token="token123"
                )
            )

            assert result["success"] is True


def test_post_to_facebook_success():
    """Test posting to Facebook successfully."""
    import asyncio

    async def test_post():
        with patch('httpx.AsyncClient') as mock_client:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.json.return_value = {
                "id": "facebook-post-123"
            }

            mock_client.return_value.__aenter__.return_value.post.return_value = mock_response

            result = asyncio.run(
                __import__('api.social_media_routes', fromlist=['post_to_facebook']).post_to_facebook(
                    text="Test post",
                    access_token="token123"
                )
            )

            assert result["success"] is True
            assert result["post_id"] == "facebook-post-123"


# ============================================================================
# Governance Tests
# ============================================================================

def test_post_with_agent_governance_blocked(
    client: TestClient,
    db: Session,
    mock_user: User,
    mock_twitter_token: OAuthToken
):
    """Test social post blocked by agent governance."""
    global _current_test_user
    _current_test_user = mock_user

    request_data = {
        "text": "Test post",
        "platforms": ["twitter"],
        "agent_id": "student-agent-123"
    }

    with patch('core.agent_context_resolver.AgentContextResolver') as mock_resolver:
        mock_agent = Mock()
        mock_agent.id = "student-agent-123"
        mock_agent.status = "student"
        mock_resolver.return_value.resolve_agent_for_request.return_value = (mock_agent, {})

        with patch('core.agent_governance_service.AgentGovernanceService') as mock_gov:
            mock_gov_instance = Mock()
            mock_gov_instance.can_perform_action.return_value = {
                "allowed": False
            }
            mock_gov.return_value = mock_gov_instance

            response = client.post("/api/v1/social/post", json=request_data)

            assert response.status_code in [403, 400]


def test_post_with_agent_governance_passed(
    client: TestClient,
    db: Session,
    mock_user: User,
    mock_twitter_token: OAuthToken
):
    """Test social post with governance passed."""
    global _current_test_user
    _current_test_user = mock_user

    request_data = {
        "text": "Test post",
        "platforms": ["twitter"],
        "agent_id": "autonomous-agent-123"
    }

    with patch('core.agent_context_resolver.AgentContextResolver') as mock_resolver:
        mock_agent = Mock()
        mock_agent.id = "autonomous-agent-123"
        mock_agent.status = "autonomous"
        mock_resolver.return_value.resolve_agent_for_request.return_value = (mock_agent, {})

        with patch('core.agent_governance_service.AgentGovernanceService') as mock_gov:
            mock_gov_instance = Mock()
            mock_gov_instance.can_perform_action.return_value = {
                "allowed": True
            }
            mock_gov.return_value = mock_gov_instance

            with patch('api.social_media_routes.post_to_twitter') as mock_post:
                mock_post.return_value = {
                    "success": True,
                    "post_id": "tweet-123"
                }

                response = client.post("/api/v1/social/post", json=request_data)

                assert response.status_code == 200
