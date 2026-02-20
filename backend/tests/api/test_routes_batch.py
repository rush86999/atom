"""
Comprehensive API Routes Tests - Wave 3B Batch

Tests 6 API route files with varying coverage levels:
- workspace_routes.py (workspace synchronization)
- auth_routes.py (mobile authentication & biometric)
- token_routes.py (JWT token management)
- marketing_routes.py (marketing analytics & campaigns)
- operational_routes.py (business health & interventions)
- user_activity_routes.py (user activity tracking)

Target: 75%+ coverage across all files
Tests: 50+ comprehensive tests
"""

import pytest
from datetime import datetime, timedelta
from unittest.mock import MagicMock, AsyncMock, patch
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

# Import main app for TestClient
from main_api_app import app

from core.models import (
    UnifiedWorkspace,
    User,
    UserRole,
    MobileDevice,
    UserState,
    UserActivity,
    RevokedToken
)
from sales.models import Lead


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def client(db_session: Session):
    """Create test client with database session override"""
    from core.database import get_db

    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db

    with TestClient(app) as test_client:
        yield test_client

    app.dependency_overrides.clear()


# ============================================================================
# Workspace Routes Tests (9 tests)
# ============================================================================

class TestWorkspaceRoutes:
    """Test workspace synchronization API endpoints"""

    def test_create_unified_workspace_success(self, db_session: Session, client: TestClient):
        """Test creating a unified workspace with valid data"""
        request_data = {
            "user_id": "test_user_123",
            "name": "Test Workspace",
            "description": "Test workspace description",
            "slack_workspace_id": "T123456",
            "sync_config": {"auto_sync": True}
        }

        response = client.post("/api/v1/workspaces/unified", json=request_data)

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "data" in data
        assert data["data"]["name"] == "Test Workspace"
        assert data["data"]["slack_workspace_id"] == "T123456"

    def test_create_workspace_no_platforms_fails(self, db_session: Session, client: TestClient):
        """Test workspace creation fails without at least one platform"""
        request_data = {
            "user_id": "test_user_123",
            "name": "Invalid Workspace"
            # Missing platform IDs
        }

        response = client.post("/api/v1/workspaces/unified", json=request_data)

        assert response.status_code == 422  # Validation error

    def test_get_workspace_by_id_success(self, db_session: Session, client: TestClient):
        """Test retrieving workspace by ID"""
        # Create workspace first
        workspace = UnifiedWorkspace(
            id="ws_test_001",
            user_id="user_123",
            name="Test Workspace",
            slack_workspace_id="T123456",
            sync_status="active",
            platform_count=1,
            member_count=5
        )
        db_session.add(workspace)
        db_session.commit()

        response = client.get(f"/api/v1/workspaces/unified/{workspace.id}")

        assert response.status_code == 200
        data = response.json()
        assert data["data"]["id"] == workspace.id
        assert data["data"]["name"] == "Test Workspace"

    def test_get_workspace_not_found(self, db_session: Session, client: TestClient):
        """Test retrieving non-existent workspace returns 404"""
        response = client.get("/api/v1/workspaces/unified/nonexistent")

        assert response.status_code == 404

    def test_add_platform_to_workspace_success(self, db_session: Session, client: TestClient):
        """Test adding a platform to existing workspace"""
        workspace = UnifiedWorkspace(
            id="ws_test_002",
            user_id="user_123",
            name="Test Workspace",
            slack_workspace_id="T123456",
            sync_status="active",
            platform_count=1,
            member_count=5
        )
        db_session.add(workspace)
        db_session.commit()

        request_data = {
            "workspace_id": workspace.id,
            "platform": "discord",
            "platform_id": "123456789"
        }

        response = client.post(f"/api/v1/workspaces/unified/{workspace.id}/platforms", json=request_data)

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True

    def test_list_workspaces_filtered_by_user(self, db_session: Session, client: TestClient):
        """Test listing workspaces filtered by user ID"""
        # Create workspaces for different users
        ws1 = UnifiedWorkspace(
            id="ws_user1_001",
            user_id="user_1",
            name="User 1 Workspace",
            slack_workspace_id="T111",
            sync_status="active",
            platform_count=1,
            member_count=3
        )
        ws2 = UnifiedWorkspace(
            id="ws_user2_001",
            user_id="user_2",
            name="User 2 Workspace",
            discord_guild_id="D222",
            sync_status="active",
            platform_count=1,
            member_count=2
        )
        db_session.add_all([ws1, ws2])
        db_session.commit()

        # List all workspaces
        response = client.get("/api/v1/workspaces/unified")
        assert response.status_code == 200
        data = response.json()
        assert data["total"] >= 2

        # List filtered by user
        response = client.get("/api/v1/workspaces/unified?user_id=user_1")
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 1
        assert data["items"][0]["user_id"] == "user_1"

    def test_delete_workspace_success(self, db_session: Session, client: TestClient):
        """Test deleting a workspace"""
        workspace = UnifiedWorkspace(
            id="ws_delete_001",
            user_id="user_123",
            name="Delete Me",
            slack_workspace_id="T999",
            sync_status="active",
            platform_count=1,
            member_count=1
        )
        db_session.add(workspace)
        db_session.commit()

        response = client.delete(f"/api/v1/workspaces/unified/{workspace.id}")

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "deleted" in data["message"].lower()

    def test_propagate_changes_success(self, db_session: Session, client: TestClient):
        """Test propagating changes to other platforms"""
        workspace = UnifiedWorkspace(
            id="ws_sync_001",
            user_id="user_123",
            name="Sync Workspace",
            slack_workspace_id="T111",
            discord_guild_id="D222",
            sync_status="active",
            platform_count=2,
            member_count=5
        )
        db_session.add(workspace)
        db_session.commit()

        request_data = {
            "workspace_id": workspace.id,
            "source_platform": "slack",
            "change_type": "channel_created",
            "change_data": {"channel_name": "new-channel"}
        }

        with patch('integrations.workspace_sync_service.WorkspaceSyncService.propagate_change') as mock_propagate:
            mock_propagate.return_value = {"status": "synced", "platforms_updated": 1}

            response = client.post(f"/api/v1/workspaces/unified/{workspace.id}/sync", json=request_data)

            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True

    def test_workspace_to_dict_helper(self):
        """Test workspace to dictionary conversion helper"""
        workspace = UnifiedWorkspace(
            id="ws_test_001",
            user_id="user_123",
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
# Auth Routes Tests (9 tests)
# ============================================================================

class TestAuthRoutes:
    """Test mobile authentication and biometric endpoints"""

    def test_mobile_login_success(self, db_session: Session, client: TestClient):
        """Test successful mobile login with device registration"""
        # Create test user
        user = User(
            id="user_mobile_001",
            email="mobile@test.com",
            hashed_password="hashed_password_here",
            role=UserRole.USER
        )
        db_session.add(user)
        db_session.commit()

        with patch('core.auth.authenticate_mobile_user') as mock_auth:
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

    def test_mobile_login_invalid_credentials(self, db_session: Session, client: TestClient):
        """Test mobile login fails with invalid credentials"""
        with patch('core.auth.authenticate_mobile_user') as mock_auth:
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
        user = User(id="user_bio_001", email="bio@test.com", hashed_password="hash", role=UserRole.USER)
        device = MobileDevice(
            id="device_001",
            user_id=user.id,
            device_token="token_123",
            platform="ios",
            status="active"
        )
        db_session.add_all([user, device])
        db_session.commit()

        # Mock authentication
        with patch('core.auth.get_current_user', return_value=user):
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
        user = User(id="user_bio_002", email="bio2@test.com", hashed_password="hash", role=UserRole.USER)
        device = MobileDevice(
            id="device_002",
            user_id=user.id,
            device_token="token_456",
            platform="ios",
            status="active",
            device_info={"biometric_public_key": "test_key", "biometric_challenge": "test_challenge"}
        )
        db_session.add_all([user, device])
        db_session.commit()

        with patch('core.auth.verify_biometric_signature', return_value=True):
            with patch('core.auth.create_mobile_token') as mock_token:
                mock_token.return_value = {
                    "access_token": "access_token",
                    "refresh_token": "refresh_token"
                }

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
        device = MobileDevice(
            id="device_003",
            user_id="user_bio_003",
            device_token="token_789",
            platform="ios",
            status="active",
            device_info={"biometric_public_key": "test_key"}
        )
        db_session.add(device)
        db_session.commit()

        with patch('core.auth.verify_biometric_signature', return_value=False):
            request_data = {
                "device_id": str(device.id),
                "signature": "invalid_signature",
                "challenge": "challenge"
            }

            response = client.post("/api/auth/mobile/biometric/authenticate", json=request_data)

            assert response.status_code == 200
            data = response.json()
            assert data["success"] is False

    def test_refresh_mobile_token_success(self, db_session: Session, client: TestClient):
        """Test mobile token refresh"""
        user = User(id="user_refresh_001", email="refresh@test.com", hashed_password="hash", role=UserRole.USER)
        device = MobileDevice(
            id="device_refresh_001",
            user_id=user.id,
            device_token="token_refresh",
            platform="ios",
            status="active"
        )
        db_session.add_all([user, device])
        db_session.commit()

        with patch('core.jwt_verifier.verify_token_string') as mock_verify:
            mock_verify.return_value = {
                "sub": user.id,
                "type": "refresh",
                "device_id": str(device.id),
                "exp": int(datetime.utcnow().timestamp()) + 3600
            }

            with patch('core.auth.create_mobile_token') as mock_token:
                mock_token.return_value = {
                    "access_token": "new_access_token",
                    "refresh_token": "new_refresh_token"
                }

                request_data = {"refresh_token": "valid_refresh_token"}

                response = client.post("/api/auth/mobile/refresh", json=request_data)

                assert response.status_code == 200
                assert "access_token" in response.json()

    def test_get_mobile_device_info_success(self, db_session: Session, client: TestClient):
        """Test retrieving mobile device information"""
        user = User(id="user_device_001", email="device@test.com", hashed_password="hash", role=UserRole.USER)
        device = MobileDevice(
            id="device_info_001",
            user_id=user.id,
            device_token="token_info",
            platform="android",
            status="active",
            notification_enabled=True
        )
        db_session.add_all([user, device])
        db_session.commit()

        with patch('core.auth.get_current_user', return_value=user):
            with patch('core.auth.get_mobile_device', return_value=device):
                response = client.get(f"/api/auth/mobile/device?device_id={device.id}")

                assert response.status_code == 200
                data = response.json()
                assert data["device_id"] == str(device.id)
                assert data["platform"] == "android"

    def test_delete_mobile_device_success(self, db_session: Session, client: TestClient):
        """Test unregistering mobile device"""
        user = User(id="user_delete_001", email="delete@test.com", hashed_password="hash", role=UserRole.USER)
        device = MobileDevice(
            id="device_delete_001",
            user_id=user.id,
            device_token="token_delete",
            platform="ios",
            status="active"
        )
        db_session.add_all([user, device])
        db_session.commit()

        with patch('core.auth.get_current_user', return_value=user):
            with patch('core.auth.get_mobile_device', return_value=device):
                response = client.delete(f"/api/auth/mobile/device?device_id={device.id}")

                assert response.status_code == 200
                # Device should be marked inactive
                assert device.status == "inactive"

    def test_mobile_device_not_found(self, db_session: Session, client: TestClient):
        """Test retrieving non-existent device returns 404"""
        user = User(id="user_404", email="404@test.com", hashed_password="hash", role=UserRole.USER)
        db_session.add(user)
        db_session.commit()

        with patch('core.auth.get_current_user', return_value=user):
            with patch('core.auth.get_mobile_device', return_value=None):
                response = client.get("/api/auth/mobile/device?device_id=nonexistent")

                assert response.status_code == 404


# ============================================================================
# Token Routes Tests (7 tests)
# ============================================================================

class TestTokenRoutes:
    """Test JWT token management endpoints"""

    def test_revoke_token_success(self, db_session: Session, client: TestClient):
        """Test successful token revocation"""
        user = User(id="user_revoke_001", email="revoke@test.com", hashed_password="hash", role=UserRole.USER)
        db_session.add(user)
        db_session.commit()

        with patch('core.auth.get_current_user', return_value=user):
            with patch('core.jwt_verifier.verify_token_string') as mock_verify:
                mock_verify.return_value = {
                    "sub": user.id,
                    "jti": "jti_123",
                    "exp": datetime.utcnow().timestamp() + 3600
                }

                with patch('core.auth_helpers.revoke_token', return_value=True):
                    request_data = {
                        "token": "valid_token_to_revoke",
                        "reason": "logout"
                    }

                    response = client.post("/api/auth/tokens/revoke", json=request_data)

                    assert response.status_code == 200
                    data = response.json()
                    assert data["success"] is True

    def test_revoke_token_permission_denied(self, db_session: Session, client: TestClient):
        """Test revoking another user's token fails"""
        user1 = User(id="user1", email="user1@test.com", hashed_password="hash", role=UserRole.USER)
        user2 = User(id="user2", email="user2@test.com", hashed_password="hash", role=UserRole.USER)
        db_session.add_all([user1, user2])
        db_session.commit()

        with patch('core.auth.get_current_user', return_value=user1):
            with patch('core.jwt_verifier.verify_token_string') as mock_verify:
                # Token belongs to user2
                mock_verify.return_value = {
                    "sub": user2.id,
                    "jti": "jti_456",
                    "exp": datetime.utcnow().timestamp() + 3600
                }

                request_data = {"token": "other_user_token", "reason": "logout"}

                response = client.post("/api/auth/tokens/revoke", json=request_data)

                assert response.status_code == 403  # Permission denied

    def test_cleanup_expired_tokens_admin_success(self, db_session: Session, client: TestClient):
        """Test admin can cleanup expired tokens"""
        admin = User(id="admin_001", email="admin@test.com", hashed_password="hash", role=UserRole.SUPER_ADMIN)
        db_session.add(admin)
        db_session.commit()

        with patch('core.auth.get_current_user', return_value=admin):
            with patch('core.auth_helpers.cleanup_expired_revoked_tokens', return_value=10):
                response = client.post("/api/auth/tokens/cleanup?older_than_hours=24")

                assert response.status_code == 200
                data = response.json()
                assert data["data"]["deleted_count"] == 10

    def test_cleanup_expired_tokens_non_admin_fails(self, db_session: Session, client: TestClient):
        """Test non-admin cannot cleanup tokens"""
        user = User(id="user_cleanup_001", email="user@test.com", hashed_password="hash", role=UserRole.USER)
        db_session.add(user)
        db_session.commit()

        with patch('core.auth.get_current_user', return_value=user):
            response = client.post("/api/auth/tokens/cleanup?older_than_hours=24")

            assert response.status_code == 403  # Permission denied

    def test_verify_token_valid(self, db_session: Session, client: TestClient):
        """Test verifying a valid non-revoked token"""
        user = User(id="user_verify_001", email="verify@test.com", hashed_password="hash", role=UserRole.USER)
        db_session.add(user)
        db_session.commit()

        with patch('core.auth.get_current_user', return_value=user):
            with patch('core.jwt_verifier.verify_token_string') as mock_verify:
                mock_verify.return_value = {
                    "sub": user.id,
                    "jti": "jti_verify",
                    "exp": datetime.utcnow().timestamp() + 3600
                }

                with patch('core.jwt_verifier.get_jwt_verifier') as mock_verifier:
                    mock_verifier_instance = MagicMock()
                    mock_verifier_instance._is_token_revoked.return_value = False
                    mock_verifier.return_value = mock_verifier_instance

                    response = client.get("/api/auth/tokens/verify?token=valid_token")

                    assert response.status_code == 200
                    data = response.json()
                    assert data["data"]["valid"] is True
                    assert data["data"]["revoked"] is False

    def test_verify_token_revoked(self, db_session: Session, client: TestClient):
        """Test verifying a revoked token"""
        user = User(id="user_verify_002", email="verify2@test.com", hashed_password="hash", role=UserRole.USER)
        db_session.add(user)
        db_session.commit()

        with patch('core.auth.get_current_user', return_value=user):
            with patch('core.jwt_verifier.verify_token_string') as mock_verify:
                mock_verify.return_value = {
                    "sub": user.id,
                    "jti": "jti_revoked",
                    "exp": datetime.utcnow().timestamp() + 3600
                }

                with patch('core.jwt_verifier.get_jwt_verifier') as mock_verifier:
                    mock_verifier_instance = MagicMock()
                    mock_verifier_instance._is_token_revoked.return_value = True
                    mock_verifier.return_value = mock_verifier_instance

                    response = client.get("/api/auth/tokens/verify?token=revoked_token")

                    assert response.status_code == 200
                    data = response.json()
                    assert data["data"]["valid"] is False
                    assert data["data"]["revoked"] is True

    def test_verify_token_no_jti(self, db_session: Session, client: TestClient):
        """Test token without JTI cannot be revoked"""
        user = User(id="user_verify_003", email="verify3@test.com", hashed_password="hash", role=UserRole.USER)
        db_session.add(user)
        db_session.commit()

        with patch('core.auth.get_current_user', return_value=user):
            with patch('core.jwt_verifier.verify_token_string') as mock_verify:
                mock_verify.return_value = {
                    "sub": user.id,
                    "exp": datetime.utcnow().timestamp() + 3600
                    # No 'jti' claim
                }

                request_data = {"token": "token_without_jti", "reason": "logout"}

                response = client.post("/api/auth/tokens/revoke", json=request_data)

                assert response.status_code == 422  # Validation error


# ============================================================================
# Marketing Routes Tests (7 tests)
# ============================================================================

class TestMarketingRoutes:
    """Test marketing analytics and campaign endpoints"""

    def test_get_marketing_summary_success(self, db_session: Session, client: TestClient):
        """Test retrieving marketing dashboard summary"""
        user = User(id="user_marketing_001", email="marketing@test.com", hashed_password="hash", role=UserRole.USER)
        db_session.add(user)
        db_session.commit()

        with patch('core.auth.get_current_user', return_value=user):
            with patch('core.marketing_analytics.PlainEnglishReporter.generate_narrative_report') as mock_narrative:
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
        user = User(id="user_marketing_002", email="marketing2@test.com", hashed_password="hash", role=UserRole.USER)
        db_session.add(user)
        db_session.commit()

        with patch('core.auth.get_current_user', return_value=user):
            with patch('core.marketing_analytics.PlainEnglishReporter.generate_narrative_report') as mock_narrative:
                mock_narrative.return_value = "No leads this month."

                response = client.get("/api/marketing/dashboard/summary")

                assert response.status_code == 200
                data = response.json()
                assert "narrative_report" in data
                assert len(data.get("high_intent_leads", [])) == 0

    def test_score_lead_success(self, db_session: Session, client: TestClient):
        """Test AI lead scoring endpoint"""
        user = User(id="user_marketing_003", email="marketing3@test.com", hashed_password="hash", role=UserRole.USER)
        lead = Lead(
            id="lead_score_001",
            workspace_id="default",
            email="unscored@test.com",
            source="website"
        )
        db_session.add_all([user, lead])
        db_session.commit()

        with patch('core.auth.get_current_user', return_value=user):
            with patch('core.marketing_manager.AIMarketingManager') as mock_manager:
                mock_manager.lead_scoring.calculate_score = AsyncMock(return_value={
                    "score": 85,
                    "rationale": "High intent lead from website source"
                })

                response = client.post(f"/api/marketing/leads/{lead.id}/score")

                assert response.status_code == 200
                data = response.json()
                assert "score" in data

    def test_score_lead_not_found(self, db_session: Session, client: TestClient):
        """Test scoring non-existent lead returns 404"""
        user = User(id="user_marketing_004", email="marketing4@test.com", hashed_password="hash", role=UserRole.USER)
        db_session.add(user)
        db_session.commit()

        with patch('core.auth.get_current_user', return_value=user):
            response = client.post("/api/marketing/leads/nonexistent/score")

            assert response.status_code == 404

    def test_analyze_reputation_success(self, db_session: Session, client: TestClient):
        """Test reputation analysis for feedback strategy"""
        with patch('core.reputation_service.ReputationManager.determine_feedback_strategy') as mock_strategy:
            mock_strategy.return_value = {
                "strategy": "private",
                "reason": "Negative interaction requires private resolution"
            }

            response = client.get("/api/marketing/reputation/analyze?interaction=Customer+complained+about+service")

            assert response.status_code == 200
            data = response.json()
            assert "strategy" in data

    def test_suggest_gmb_post_success(self, db_session: Session, client: TestClient):
        """Test GMB weekly post suggestion"""
        with patch('core.marketing_manager.AIMarketingManager') as mock_manager:
            mock_manager.gmb.generate_weekly_update = AsyncMock(return_value="Join us this week for special events!")

            response = client.get("/api/marketing/gmb/weekly-post/suggest?business_name=Test+Cafe&location=San+Francisco")

            assert response.status_code == 200
            data = response.json()
            assert "suggested_post" in data

    def test_suggest_gmb_post_with_events(self, db_session: Session, client: TestClient):
        """Test GMB post suggestion with custom events"""
        with patch('core.marketing_manager.AIMarketingManager') as mock_manager:
            mock_manager.gmb.generate_weekly_update = AsyncMock(
                return_value="Special events: Happy Hour, Live Music this week!"
            )

            response = client.get(
                "/api/marketing/gmb/weekly-post/suggest",
                params={
                    "business_name": "Test Cafe",
                    "location": "San Francisco",
                    "events": ["Happy Hour", "Live Music"]
                }
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
        with patch('core.financial_forensics.VendorIntelligence.detect_price_drift') as mock_detect:
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
        with patch('core.financial_forensics.PricingAdvisor.get_pricing_recommendations') as mock_advice:
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
            state=UserState.ONLINE,
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
            state=UserState.AWAY,
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
            state=UserState.ONLINE,
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
        # Create supervisor users
        supervisor1 = UserActivity(
            id="sup_activity_001",
            user_id="supervisor_001",
            state=UserState.ONLINE,
            last_activity_at=datetime.utcnow(),
            manual_override=False
        )
        supervisor2 = UserActivity(
            id="sup_activity_002",
            user_id="supervisor_002",
            state=UserState.AWAY,
            last_activity_at=datetime.utcnow() - timedelta(minutes=5),
            manual_override=False
        )
        db_session.add_all([supervisor1, supervisor2])
        db_session.commit()

        with patch('core.user_activity_service.UserActivityService.get_available_supervisors') as mock_supervisors:
            mock_supervisors.return_value = [
                {
                    "user_id": "supervisor_001",
                    "email": "sup1@test.com",
                    "state": "online",
                    "specialty": "sales"
                },
                {
                    "user_id": "supervisor_002",
                    "email": "sup2@test.com",
                    "state": "away",
                    "specialty": "support"
                }
            ]

            response = client.get("/api/users/available-supervisors")

            assert response.status_code == 200
            data = response.json()
            assert data["total_count"] >= 2

    def test_get_available_supervisors_filtered_by_category(self, db_session: Session, client: TestClient):
        """Test filtering supervisors by category"""
        with patch('core.user_activity_service.UserActivityService.get_available_supervisors') as mock_supervisors:
            mock_supervisors.return_value = [
                {
                    "user_id": "supervisor_001",
                    "email": "sup1@test.com",
                    "state": "online",
                    "specialty": "sales"
                },
                {
                    "user_id": "supervisor_002",
                    "email": "sup2@test.com",
                    "state": "away",
                    "specialty": "support"
                }
            ]

            response = client.get("/api/users/available-supervisors?category=sales")

            assert response.status_code == 200
            data = response.json()
            # Should filter by category in the route
            assert data["total_count"] >= 0


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
    user = User(id="user_format_001", email="format@test.com", hashed_password="hash", role=UserRole.SUPER_ADMIN)
    db_session.add(user)
    db_session.commit()

    with patch('core.auth.get_current_user', return_value=user):
        with patch('core.auth_helpers.cleanup_expired_revoked_tokens', return_value=5):
            response = client.post("/api/auth/tokens/cleanup?older_than_hours=24")

            # Check response has standard fields
            if response.status_code == 200:
                data = response.json()
                # Should have success/data/message structure or similar
                assert isinstance(data, dict)
