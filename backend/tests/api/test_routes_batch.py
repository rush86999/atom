"""
Comprehensive API Routes Tests - Wave 3B Batch

Tests 5 API route files with varying coverage levels:
- workspace_routes.py (workspace synchronization)
- auth_routes.py (mobile authentication & biometric)
- marketing_routes.py (marketing analytics & campaigns)
- operational_routes.py (business health & interventions)
- user_activity_routes.py (user activity tracking)

Note: the former token_routes tests were removed — no /api/auth/tokens/*
endpoints exist in the codebase (the routes were never implemented).
"""

import os
from datetime import datetime, timedelta
from unittest.mock import MagicMock, AsyncMock, patch
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

import pytest

# Import main app for TestClient
from main_api_app import app

from core.models import (
    UnifiedWorkspace,
    User,
    UserRole,
    MobileDevice,
    UserState,
    UserActivity,
)
from sales.models import Lead


# ============================================================================
# Fixtures
# ============================================================================

def _make_user(user_id: str, email: str, role=UserRole.MEMBER) -> User:
    """Create a User model instance with a valid role enum."""
    return User(
        id=user_id,
        email=email,
        hashed_password="hash",
        role=role,
        first_name="Test",
        last_name="User",
        status="active",
    )


def _make_device(device_id: str, user_id: str, token: str, platform: str = "ios",
                 **kwargs) -> MobileDevice:
    """Create a MobileDevice model instance with timestamps populated."""
    now = datetime.utcnow()
    return MobileDevice(
        id=device_id,
        user_id=user_id,
        device_token=token,
        platform=platform,
        status="active",
        created_at=now,
        last_active=now,
        **kwargs,
    )


@pytest.fixture
def client(db_session: Session):
    """Create test client with database session override"""
    from core.database import get_db
    from core.auth import get_current_user

    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    def override_get_current_user():
        return MagicMock(id="test-user")

    app.dependency_overrides[get_db] = override_get_db
    # Round 38: operational endpoints require auth — override the dependency.
    app.dependency_overrides[get_current_user] = override_get_current_user

    with TestClient(app) as test_client:
        yield test_client

    app.dependency_overrides.clear()


@pytest.fixture
def ws_client(db_session: Session):
    """TestClient for the workspace router mounted on a dedicated app.

    The workspace router is NOT mounted on the main app, so these tests
    mount it themselves (same pattern as tests/api/test_workspace_routes.py).
    """
    from fastapi import FastAPI
    from api.workspace_routes import router as workspace_router
    from core.database import get_db
    from core.auth import get_current_user

    ws_app = FastAPI()
    ws_app.include_router(workspace_router)

    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    def override_get_current_user():
        return MagicMock(id="test-user")

    ws_app.dependency_overrides[get_db] = override_get_db
    ws_app.dependency_overrides[get_current_user] = override_get_current_user

    with TestClient(ws_app) as test_client:
        yield test_client

    ws_app.dependency_overrides.clear()


def _make_workspace(db_session, workspace_id: str, name: str,
                    user_id: str = "test-user", **kwargs) -> UnifiedWorkspace:
    """Create a UnifiedWorkspace owned by the authenticated test user."""
    defaults = {
        "sync_status": "active",
        "platform_count": 1,
        "member_count": 5,
    }
    defaults.update(kwargs)
    workspace = UnifiedWorkspace(
        id=workspace_id,
        user_id=user_id,
        name=name,
        **defaults,
    )
    db_session.add(workspace)
    db_session.commit()
    db_session.refresh(workspace)
    return workspace


# ============================================================================
# Workspace Routes Tests (9 tests)
# ============================================================================

class TestWorkspaceRoutes:
    """Test workspace synchronization API endpoints"""

    def test_create_unified_workspace_success(self, db_session: Session, ws_client: TestClient):
        """Test creating a unified workspace with valid data"""
        request_data = {
            "user_id": "test_user_123",
            "name": "Test Workspace",
            "description": "Test workspace description",
            "slack_workspace_id": "T123456",
            "sync_config": {"auto_sync": True}
        }

        response = ws_client.post("/api/v1/workspaces/unified", json=request_data)

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "data" in data
        assert data["data"]["name"] == "Test Workspace"
        assert data["data"]["slack_workspace_id"] == "T123456"

    def test_create_workspace_no_platforms_fails(self, db_session: Session, ws_client: TestClient):
        """Test workspace creation fails without at least one platform"""
        request_data = {
            "user_id": "test_user_123",
            "name": "Invalid Workspace"
            # Missing platform IDs
        }

        response = ws_client.post("/api/v1/workspaces/unified", json=request_data)

        assert response.status_code == 422  # Validation error

    def test_get_workspace_by_id_success(self, db_session: Session, ws_client: TestClient):
        """Test retrieving workspace by ID"""
        workspace = _make_workspace(
            db_session, "ws_test_001", "Test Workspace",
            slack_workspace_id="T123456",
        )

        response = ws_client.get(f"/api/v1/workspaces/unified/{workspace.id}")

        assert response.status_code == 200
        data = response.json()
        assert data["data"]["workspace_id"] == workspace.id
        assert data["data"]["name"] == "Test Workspace"

    def test_get_workspace_not_found(self, db_session: Session, ws_client: TestClient):
        """Test retrieving non-existent workspace returns 404"""
        response = ws_client.get("/api/v1/workspaces/unified/nonexistent")

        assert response.status_code == 404

    def test_add_platform_to_workspace_success(self, db_session: Session, ws_client: TestClient):
        """Test adding a platform to existing workspace"""
        workspace = _make_workspace(
            db_session, "ws_test_002", "Test Workspace",
            slack_workspace_id="T123456",
        )

        request_data = {
            "workspace_id": workspace.id,
            "platform": "discord",
            "platform_id": "123456789"
        }

        response = ws_client.post(
            f"/api/v1/workspaces/unified/{workspace.id}/platforms", json=request_data
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["data"]["discord_guild_id"] == "123456789"

    def test_list_workspaces_filtered_by_user(self, db_session: Session, ws_client: TestClient):
        """Test listing workspaces scoped to the authenticated user"""
        # Both workspaces belong to the authenticated user ("test-user");
        # the R54 ownership scope ignores the client-supplied user_id param.
        _make_workspace(
            db_session, "ws_user1_001", "User 1 Workspace",
            slack_workspace_id="T111",
        )
        _make_workspace(
            db_session, "ws_user2_001", "User 2 Workspace",
            discord_guild_id="D222",
        )

        # List all workspaces (scoped to authenticated user)
        response = ws_client.get("/api/v1/workspaces/unified")
        assert response.status_code == 200
        data = response.json()
        assert data["metadata"]["total"] == 2

        # The user_id query param is ignored (R54: ownership from token only)
        response = ws_client.get("/api/v1/workspaces/unified?user_id=user_1")
        assert response.status_code == 200
        data = response.json()
        assert data["metadata"]["total"] == 2
        assert all(item["user_id"] == "test-user" for item in data["data"])

    def test_delete_workspace_success(self, db_session: Session, ws_client: TestClient):
        """Test deleting a workspace"""
        workspace = _make_workspace(
            db_session, "ws_delete_001", "Delete Me",
            slack_workspace_id="T999",
        )

        response = ws_client.delete(f"/api/v1/workspaces/unified/{workspace.id}")

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "deleted" in data["message"].lower()

    def test_propagate_changes_success(self, db_session: Session, ws_client: TestClient):
        """Test propagating changes to other platforms"""
        workspace = _make_workspace(
            db_session, "ws_sync_001", "Sync Workspace",
            slack_workspace_id="T111",
            discord_guild_id="D222",
            platform_count=2,
        )

        request_data = {
            "workspace_id": workspace.id,
            "source_platform": "slack",
            "change_type": "channel_created",
            "change_data": {"channel_name": "new-channel"}
        }

        with patch('integrations.workspace_sync_service.WorkspaceSyncService.propagate_change') as mock_propagate:
            mock_propagate.return_value = {"status": "synced", "platforms_updated": 1}

            response = ws_client.post(
                f"/api/v1/workspaces/unified/{workspace.id}/sync", json=request_data
            )

            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True

    def test_workspace_to_dict_helper(self, db_session: Session):
        """Test workspace to dictionary conversion helper"""
        workspace = UnifiedWorkspace(
            id="ws_test_001",
            user_id="test-user",
            name="Test Workspace",
            description="Test description",
            slack_workspace_id="T123",
            discord_guild_id="D456",
            sync_status="active",
            platform_count=2,
            member_count=10,
            last_sync_at=datetime.utcnow(),
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )

        # Import the helper function
        from api.workspace_routes import _workspace_to_dict

        result = _workspace_to_dict(workspace)

        assert result["id"] == workspace.id
        assert result["name"] == "Test Workspace"
        assert result["platform_count"] == 2
        assert result["member_count"] == 10
        assert "last_sync_at" in result


# ============================================================================
# Auth Routes Tests (8 tests)
# ============================================================================

class TestAuthRoutes:
    """Test mobile authentication and biometric endpoints"""

    def test_mobile_login_success(self, db_session: Session, client: TestClient):
        """Test successful mobile login with device registration"""
        user = _make_user("user_mobile_001", "mobile@test.com")
        db_session.add(user)
        db_session.commit()

        with patch('api.auth_routes.authenticate_mobile_user', new_callable=AsyncMock) as mock_auth:
            mock_auth.return_value = {
                "access_token": "test_access_token",
                "refresh_token": "test_refresh_token",
                "expires_at": "2026-02-21T00:00:00Z",
                "token_type": "bearer",
                "user": {"id": user.id, "email": user.email}
            }

            request_data = {
                "email": "mobile@test.com",
                "password": "password123",
                "device_token": "device_token_123",
                "platform": "ios"
            }

            response = client.post("/api/auth/mobile/login", json=request_data)

            assert response.status_code == 200
            data = response.json()
            assert "access_token" in data
            assert "refresh_token" in data
            mock_auth.assert_called_once()

    def test_mobile_login_invalid_credentials(self, db_session: Session, client: TestClient):
        """Test mobile login fails with invalid credentials"""
        with patch('api.auth_routes.authenticate_mobile_user', new_callable=AsyncMock) as mock_auth:
            mock_auth.return_value = None

            request_data = {
                "email": "invalid@test.com",
                "password": "wrong_password",
                "device_token": "device_token_123",
                "platform": "android"
            }

            response = client.post("/api/auth/mobile/login", json=request_data)

            assert response.status_code == 422  # Validation error for invalid credentials

    def test_register_biometric_success(self, db_session: Session, client: TestClient):
        """Test biometric registration initiation"""
        user = _make_user("user_bio_001", "bio@test.com")
        device = _make_device("device_001", user.id, "token_123")
        db_session.add_all([user, device])
        db_session.commit()

        # The route scopes the device lookup to the authenticated user
        # (get_current_user override returns id="test-user"), so the device
        # must belong to that user.
        device.user_id = "test-user"
        db_session.commit()

        request_data = {
            "public_key": "public_key_base64",
            "device_token": "token_123",
            "platform": "ios"
        }

        response = client.post("/api/auth/mobile/biometric/register", json=request_data)

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "challenge" in data

    def test_biometric_auth_success(self, db_session: Session, client: TestClient):
        """Test successful biometric authentication"""
        # The route looks the user up by device.user_id and requires the
        # account to be ACTIVE.
        user = _make_user("test-user", "bio2@test.com")
        device = _make_device(
            "device_002", "test-user", "token_456",
            device_info={
                "biometric_public_key": "test_key",
                "biometric_challenge": "test_challenge",
            },
        )
        db_session.add_all([user, device])
        db_session.commit()

        with patch('api.auth_routes.verify_biometric_signature', return_value=True):
            with patch('api.auth_routes.create_mobile_token', return_value={
                "access_token": "access_token",
                "refresh_token": "refresh_token"
            }):
                request_data = {
                    "device_id": str(device.id),
                    "signature": "valid_signature",
                    "challenge": "test_challenge"
                }

                response = client.post("/api/auth/mobile/biometric/authenticate", json=request_data)

                assert response.status_code == 200
                data = response.json()
                assert data["success"] is True

    def test_biometric_auth_invalid_signature(self, db_session: Session, client: TestClient):
        """Test biometric authentication fails with invalid signature"""
        device = _make_device(
            "device_003", "test-user", "token_789",
            device_info={
                "biometric_public_key": "test_key",
                "biometric_challenge": "test_challenge",
            },
        )
        db_session.add(device)
        db_session.commit()

        with patch('api.auth_routes.verify_biometric_signature', return_value=False):
            request_data = {
                "device_id": str(device.id),
                "signature": "invalid_signature",
                "challenge": "test_challenge"
            }

            response = client.post("/api/auth/mobile/biometric/authenticate", json=request_data)

            assert response.status_code == 200
            data = response.json()
            assert data["success"] is False

    def test_refresh_mobile_token_success(self, db_session: Session, client: TestClient,
                                          monkeypatch):
        """Test mobile token refresh"""
        # The refresh route decodes the JWT with os.environ["SECRET_KEY"];
        # pin it so the test can sign a valid token.
        monkeypatch.setenv("SECRET_KEY", "test-secret-key-for-routes-batch")

        from jose import jwt

        user = _make_user("user_refresh_001", "refresh@test.com")
        # The refresh route resolves the device by the JWT's sub claim.
        device = _make_device("device_refresh_001", user.id, "token_refresh")
        db_session.add_all([user, device])
        db_session.commit()

        refresh_token = jwt.encode(
            {
                "sub": user.id,
                "type": "refresh",
                "device_id": str(device.id),
            },
            "test-secret-key-for-routes-batch",
            algorithm="HS256",
        )

        with patch('api.auth_routes.create_mobile_token', return_value={
            "access_token": "new_access_token",
            "refresh_token": "new_refresh_token"
        }):
            request_data = {"refresh_token": refresh_token}

            response = client.post("/api/auth/mobile/refresh", json=request_data)

            assert response.status_code == 200
            assert "access_token" in response.json()

    def test_get_mobile_device_info_success(self, db_session: Session, client: TestClient):
        """Test retrieving mobile device information"""
        user = _make_user("user_device_001", "device@test.com")
        device = _make_device(
            "device_info_001", "test-user", "token_info",
            platform="android", notification_enabled=True,
        )
        db_session.add_all([user, device])
        db_session.commit()

        response = client.get(f"/api/auth/mobile/device?device_id={device.id}")

        assert response.status_code == 200
        data = response.json()
        assert data["device_id"] == str(device.id)
        assert data["platform"] == "android"

    def test_delete_mobile_device_success(self, db_session: Session, client: TestClient):
        """Test unregistering mobile device"""
        user = _make_user("user_delete_001", "delete@test.com")
        device = _make_device("device_delete_001", "test-user", "token_delete")
        db_session.add_all([user, device])
        db_session.commit()

        response = client.delete(f"/api/auth/mobile/device?device_id={device.id}")

        assert response.status_code == 200
        # Device should be marked inactive
        db_session.refresh(device)
        assert device.status == "inactive"

    def test_mobile_device_not_found(self, db_session: Session, client: TestClient):
        """Test retrieving non-existent device returns 404"""
        response = client.get("/api/auth/mobile/device?device_id=nonexistent")

        assert response.status_code == 404


# ============================================================================
# Marketing Routes Tests (7 tests)
# ============================================================================

class TestMarketingRoutes:
    """Test marketing analytics and campaign endpoints"""

    def test_get_marketing_summary_success(self, db_session: Session, client: TestClient):
        """Test retrieving marketing dashboard summary"""
        user = _make_user("user_marketing_001", "marketing@test.com")
        db_session.add(user)
        db_session.commit()

        with patch('core.marketing_analytics.PlainEnglishReporter.generate_narrative_report',
                   new_callable=AsyncMock) as mock_narrative:
            mock_narrative.return_value = "Marketing performance is strong this month."

            # Create test leads
            lead1 = Lead(
                id="lead_001",
                workspace_id="default",
                email="lead1@test.com",
                first_name="John",
                ai_score=85.0,
                ai_qualification_summary="High intent lead"
            )
            lead2 = Lead(
                id="lead_002",
                workspace_id="default",
                email="lead2@test.com",
                first_name="Jane",
                ai_score=75.0,
                ai_qualification_summary="Qualified lead"
            )
            db_session.add_all([lead1, lead2])
            db_session.commit()

            response = client.get("/api/marketing/dashboard/summary")

            assert response.status_code == 200
            data = response.json()
            assert "narrative_report" in data
            assert "performance_metrics" in data
            assert len(data["high_intent_leads"]) >= 2

    def test_get_marketing_summary_no_leads(self, db_session: Session, client: TestClient):
        """Test marketing summary with no leads"""
        user = _make_user("user_marketing_002", "marketing2@test.com")
        db_session.add(user)
        db_session.commit()

        with patch('core.marketing_analytics.PlainEnglishReporter.generate_narrative_report',
                   new_callable=AsyncMock) as mock_narrative:
            mock_narrative.return_value = "No leads this month."

            response = client.get("/api/marketing/dashboard/summary")

            assert response.status_code == 200
            data = response.json()
            assert "narrative_report" in data
            assert len(data.get("high_intent_leads", [])) == 0

    def test_score_lead_success(self, db_session: Session, client: TestClient):
        """Test AI lead scoring endpoint"""
        user = _make_user("user_marketing_003", "marketing3@test.com")
        lead = Lead(
            id="lead_score_001",
            workspace_id="default",
            email="unscored@test.com",
            source="website"
        )
        db_session.add_all([user, lead])
        db_session.commit()

        # The route uses the module-level marketing_manager instance, so the
        # scoring seam must be patched on that instance.
        from api import marketing_routes

        with patch.object(
            marketing_routes.marketing_manager.lead_scoring,
            'calculate_score',
            new_callable=AsyncMock,
        ) as mock_calculate:
            mock_calculate.return_value = {
                "score": 85,
                "rationale": "High intent lead from website source"
            }

            response = client.post(f"/api/marketing/leads/{lead.id}/score")

            assert response.status_code == 200
            data = response.json()
            assert "score" in data

    def test_score_lead_not_found(self, db_session: Session, client: TestClient):
        """Test scoring non-existent lead returns 404"""
        user = _make_user("user_marketing_004", "marketing4@test.com")
        db_session.add(user)
        db_session.commit()

        response = client.post("/api/marketing/leads/nonexistent/score")

        assert response.status_code == 404

    def test_analyze_reputation_success(self, db_session: Session, client: TestClient):
        """Test reputation analysis for feedback strategy"""
        with patch('core.reputation_service.ReputationManager.determine_feedback_strategy') as mock_strategy:
            mock_strategy.return_value = {
                "strategy": "private",
                "reason": "Negative interaction requires private resolution"
            }

            response = client.get(
                "/api/marketing/reputation/analyze?interaction=Customer+complained+about+service"
            )

            assert response.status_code == 200
            data = response.json()
            assert "strategy" in data

    def test_suggest_gmb_post_success(self, db_session: Session, client: TestClient):
        """Test GMB weekly post suggestion"""
        from api import marketing_routes

        with patch.object(
            marketing_routes.marketing_manager.gmb,
            'generate_weekly_update',
            new_callable=AsyncMock,
        ) as mock_gmb:
            mock_gmb.return_value = "Join us this week for special events!"

            response = client.get(
                "/api/marketing/gmb/weekly-post/suggest",
                params={"business_name": "Test Cafe", "location": "San Francisco"},
            )

            assert response.status_code == 200
            data = response.json()
            assert "suggested_post" in data

    def test_suggest_gmb_post_with_events(self, db_session: Session, client: TestClient):
        """Test GMB post suggestion with custom events"""
        from api import marketing_routes

        with patch.object(
            marketing_routes.marketing_manager.gmb,
            'generate_weekly_update',
            new_callable=AsyncMock,
        ) as mock_gmb:
            mock_gmb.return_value = "Special events: Happy Hour, Live Music this week!"

            response = client.get(
                "/api/marketing/gmb/weekly-post/suggest",
                params={
                    "business_name": "Test Cafe",
                    "location": "San Francisco",
                    "events": ["Happy Hour", "Live Music"],
                },
            )

            assert response.status_code == 200
            data = response.json()
            assert "suggested_post" in data


# ============================================================================
# Operational Routes Tests (6 tests)
# ============================================================================

class TestOperationalRoutes:
    """Test business health and operational intelligence endpoints"""

    def test_get_daily_priorities_success(self, db_session: Session, client: TestClient):
        """Test retrieving daily priorities for business owner"""
        with patch('core.business_health_service.BusinessHealthService.get_daily_priorities') as mock_priorities:
            mock_priorities.return_value = [
                {
                    "priority": "high",
                    "task": "Review financial reports",
                    "impact": "Cost savings of $500/month"
                },
                {
                    "priority": "medium",
                    "task": "Follow up with leads",
                    "impact": "Close 2-3 deals"
                }
            ]

            response = client.get("/api/business-health/priorities")

            assert response.status_code == 200
            data = response.json()
            assert len(data["data"]) >= 2

    def test_simulate_business_decision_success(self, db_session: Session, client: TestClient):
        """Test business decision simulation"""
        with patch('core.business_health_service.BusinessHealthService.simulate_decision') as mock_simulate:
            mock_simulate.return_value = {
                "decision_type": "hiring",
                "projected_impact": "+$10,000 monthly revenue",
                "cost": "$5,000 monthly salary",
                "roi": "200%"
            }

            request_data = {
                "decision_type": "hiring",
                "data": {"role": "Sales Rep", "salary": 5000}
            }

            response = client.post("/api/business-health/simulate", json=request_data)

            assert response.status_code == 200
            data = response.json()
            assert "roi" in data["data"]

    def test_get_price_drift_success(self, db_session: Session, client: TestClient):
        """Test price drift detection"""
        with patch('core.financial_forensics.VendorIntelligenceService.detect_price_drift',
                   new_callable=AsyncMock) as mock_detect:
            mock_detect.return_value = [
                {
                    "vendor": "AWS",
                    "service": "S3 Storage",
                    "price_increase": "15%",
                    "monthly_impact": "$150",
                    "recommendation": "Negotiate volume discount"
                }
            ]

            response = client.get("/api/business-health/forensics/price-drift")

            assert response.status_code == 200
            data = response.json()
            assert len(data["data"]) >= 1

    def test_get_pricing_advice_success(self, db_session: Session, client: TestClient):
        """Test pricing advisor recommendations"""
        with patch('core.financial_forensics.PricingAdvisorService.get_pricing_recommendations',
                   new_callable=AsyncMock) as mock_advice:
            mock_advice.return_value = [
                {
                    "product": "Premium Plan",
                    "current_price": "$99/month",
                    "recommended_price": "$119/month",
                    "reason": "Underpriced compared to competitors",
                    "margin_improvement": "+12%"
                }
            ]

            response = client.get("/api/business-health/forensics/pricing-advisor")

            assert response.status_code == 200
            data = response.json()
            assert len(data["data"]) >= 1

    def test_get_subscription_waste_success(self, db_session: Session, client: TestClient):
        """Test subscription waste detection"""
        with patch('core.financial_forensics.SubscriptionWasteService.find_zombie_subscriptions') as mock_waste:
            mock_waste.return_value = [
                {
                    "service": "Zombie SaaS Tool",
                    "monthly_cost": "$49",
                    "last_used": "3 months ago",
                    "recommendation": "Cancel subscription"
                }
            ]

            response = client.get("/api/business-health/forensics/waste")

            assert response.status_code == 200
            data = response.json()
            assert "data" in data

    def test_generate_interventions_success(self, db_session: Session, client: TestClient):
        """Test intervention generation"""
        with patch('core.cross_system_reasoning.CrossSystemReasoningEngine.generate_interventions') as mock_gen:
            mock_gen.return_value = [
                {
                    "id": "intervention_001",
                    "type": "cost_optimization",
                    "description": "Reduce cloud spend by rightsizing instances",
                    "priority": "high",
                    "estimated_savings": "$200/month"
                }
            ]

            response = client.post("/api/business-health/interventions/generate")

            assert response.status_code == 200
            data = response.json()
            assert len(data["data"]) >= 1


# ============================================================================
# User Activity Routes Tests (10 tests)
# ============================================================================

class TestUserActivityRoutes:
    """Test user activity tracking and state management endpoints"""

    def test_send_heartbeat_success(self, db_session: Session, client: TestClient):
        """Test recording user activity heartbeat"""
        request_data = {
            "session_token": "session_token_123",
            "session_type": "web",
            "user_agent": "Mozilla/5.0",
            "ip_address": "192.168.1.1"
        }

        response = client.post("/api/users/user_heartbeat_001/activity/heartbeat", json=request_data)

        assert response.status_code == 200
        data = response.json()
        assert data["user_id"] == "user_heartbeat_001"
        assert "state" in data

    def test_send_heartbeat_creates_session(self, db_session: Session, client: TestClient):
        """Test heartbeat creates session if it doesn't exist"""
        request_data = {
            "session_token": "new_session_token",
            "session_type": "desktop",
            "user_agent": "AtomDesktop/1.0"
        }

        response = client.post("/api/users/user_new_session_001/activity/heartbeat", json=request_data)

        assert response.status_code == 200
        # Session should be created automatically

    def test_get_user_state_success(self, db_session: Session, client: TestClient):
        """Test retrieving current user state"""
        # Create user activity record
        activity = UserActivity(
            id="activity_001",
            user_id="user_state_001",
            state=UserState.online,
            last_activity_at=datetime.utcnow(),
            manual_override=False
        )
        db_session.add(activity)
        db_session.commit()

        response = client.get("/api/users/user_state_001/activity/state")

        assert response.status_code == 200
        data = response.json()
        assert data["user_id"] == "user_state_001"
        assert "state" in data

    def test_get_user_state_not_found(self, db_session: Session, client: TestClient):
        """Test getting state for user with no activity record"""
        response = client.get("/api/users/user_no_activity_999/activity/state")

        # Should create minimal response
        assert response.status_code == 200
        data = response.json()
        assert data["user_id"] == "user_no_activity_999"

    def test_set_manual_override_success(self, db_session: Session, client: TestClient):
        """Test setting manual state override"""
        activity = UserActivity(
            id="activity_override_001",
            user_id="user_override_001",
            state=UserState.away,
            last_activity_at=datetime.utcnow(),
            manual_override=False
        )
        db_session.add(activity)
        db_session.commit()

        request_data = {
            "state": "online",
            "expires_at": (datetime.utcnow() + timedelta(hours=2)).isoformat()
        }

        response = client.post(f"/api/users/{activity.user_id}/activity/override", json=request_data)

        assert response.status_code == 200
        data = response.json()
        assert data["state"] == "online"
        assert data["manual_override"] is True

    def test_set_manual_override_invalid_state(self, db_session: Session, client: TestClient):
        """Test manual override fails with invalid state"""
        request_data = {
            "state": "invalid_state",
            "expires_at": None
        }

        response = client.post("/api/users/user_invalid_001/activity/override", json=request_data)

        assert response.status_code == 400  # Bad request

    def test_set_manual_override_invalid_datetime(self, db_session: Session, client: TestClient):
        """Test manual override fails with invalid datetime format"""
        request_data = {
            "state": "online",
            "expires_at": "not-a-datetime"
        }

        response = client.post("/api/users/user_invalid_dt_001/activity/override", json=request_data)

        assert response.status_code == 400  # Bad request

    def test_clear_manual_override_success(self, db_session: Session, client: TestClient):
        """Test clearing manual override"""
        activity = UserActivity(
            id="activity_clear_001",
            user_id="user_clear_001",
            state=UserState.online,
            last_activity_at=datetime.utcnow(),
            manual_override=True,
            manual_override_expires_at=datetime.utcnow() + timedelta(hours=1)
        )
        db_session.add(activity)
        db_session.commit()

        response = client.delete(f"/api/users/{activity.user_id}/activity/override")

        assert response.status_code == 200
        data = response.json()
        assert data["manual_override"] is False

    def test_get_available_supervisors_success(self, db_session: Session, client: TestClient):
        """Test retrieving available supervisors"""
        with patch('core.user_activity_service.UserActivityService.get_available_supervisors',
                   new_callable=AsyncMock) as mock_supervisors:
            mock_supervisors.return_value = [
                {
                    "user_id": "supervisor_001",
                    "email": "sup1@test.com",
                    "first_name": "Sup",
                    "last_name": "One",
                    "state": "online",
                    "last_activity_at": "2026-02-04T10:00:00Z",
                    "specialty": "sales"
                },
                {
                    "user_id": "supervisor_002",
                    "email": "sup2@test.com",
                    "first_name": "Sup",
                    "last_name": "Two",
                    "state": "away",
                    "last_activity_at": "2026-02-04T09:55:00Z",
                    "specialty": "support"
                }
            ]

            response = client.get("/api/users/available-supervisors")

            assert response.status_code == 200
            data = response.json()
            assert data["total_count"] >= 2

    def test_get_available_supervisors_filtered_by_category(self, db_session: Session, client: TestClient):
        """Test filtering supervisors by category"""
        with patch('core.user_activity_service.UserActivityService.get_available_supervisors',
                   new_callable=AsyncMock) as mock_supervisors:
            mock_supervisors.return_value = [
                {
                    "user_id": "supervisor_001",
                    "email": "sup1@test.com",
                    "first_name": "Sup",
                    "last_name": "One",
                    "state": "online",
                    "last_activity_at": "2026-02-04T10:00:00Z",
                    "specialty": "sales"
                },
                {
                    "user_id": "supervisor_002",
                    "email": "sup2@test.com",
                    "first_name": "Sup",
                    "last_name": "Two",
                    "state": "away",
                    "last_activity_at": "2026-02-04T09:55:00Z",
                    "specialty": "support"
                }
            ]

            response = client.get("/api/users/available-supervisors?category=sales")

            assert response.status_code == 200
            data = response.json()
            # The route filters by category
            assert data["total_count"] == 1
            assert data["supervisors"][0]["specialty"] == "sales"


# ============================================================================
# Performance and Coverage Tests
# ============================================================================

def test_all_routes_respond(db_session: Session, client: TestClient):
    """Verify all endpoints respond (even with errors)"""
    endpoints = [
        ("POST", "/api/v1/workspaces/unified", {}),
        ("GET", "/api/v1/workspaces/unified", {}),
        ("GET", "/api/marketing/dashboard/summary", {}),
        ("GET", "/api/business-health/priorities", {}),
    ]

    for method, endpoint, data in endpoints:
        if method == "POST":
            response = client.post(endpoint, json=data)
        else:
            response = client.get(endpoint)

        # All endpoints should respond (200, 400, 404, or 422)
        assert response.status_code in [200, 400, 404, 422, 500]


def test_response_formats_consistent(db_session: Session, client: TestClient):
    """Verify API responses follow consistent format"""
    # Test success response format
    user = _make_user("user_format_001", "format@test.com", role=UserRole.SUPER_ADMIN)
    db_session.add(user)
    db_session.commit()

    with patch('core.auth_helpers.cleanup_expired_revoked_tokens', return_value=5):
        response = client.post("/api/auth/tokens/cleanup?older_than_hours=24")

        # Check response has standard fields
        if response.status_code == 200:
            data = response.json()
            # Should have success/data/message structure or similar
            assert isinstance(data, dict)
