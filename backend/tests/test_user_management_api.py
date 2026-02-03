"""
User Management API Tests
Tests for user management, email verification, tenant, admin, meeting, and financial endpoints
"""
import json
from datetime import datetime, timedelta
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from core.auth import create_access_token, get_password_hash
from core.database import SessionLocal
from core.models import (
    AdminRole,
    AdminUser,
    EmailVerificationToken,
    FinancialAccount,
    MeetingAttendanceStatus,
    NetWorthSnapshot,
    Tenant,
    User,
    UserSession,
    UserStatus,
)

# Import app for testing - use try/except for flexibility
try:
    from main_api_app import app
except ImportError:
    try:
        from core.main_api_app import app
    except ImportError:
        app = None

client = TestClient(app) if app else None


@pytest.fixture
def db_session():
    """Create a test database session"""
    db = SessionLocal()
    try:
        yield db
        db.rollback()
    finally:
        db.close()


@pytest.fixture
def test_user(db_session: Session):
    """Create a test user"""
    user = User(
        email="test@example.com",
        password_hash=get_password_hash("password123"),
        first_name="Test",
        last_name="User",
        role="member",
        status=UserStatus.ACTIVE.value,
        email_verified=True
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture
def test_user_with_session(db_session: Session, test_user: User):
    """Create a test user with an active session"""
    from uuid import uuid4

    # Create session token
    session_token = str(uuid4())

    # Create user session
    session = UserSession(
        id=str(uuid4()),
        user_id=test_user.id,
        session_token=session_token,
        ip_address="127.0.0.1",
        device_type="desktop",
        browser="test_browser",
        os="test_os",
        is_active=True,
        expires_at=datetime.utcnow() + timedelta(hours=24)
    )
    db_session.add(session)
    db_session.commit()

    return test_user


@pytest.fixture
def auth_headers(test_user: User):
    """Create authentication headers for a regular user"""
    access_token = create_access_token(data={"sub": test_user.id})
    return {"Authorization": f"Bearer {access_token}"}


@pytest.fixture
def authenticated_client(auth_headers):
    """Create an authenticated test client"""
    if not client:
        return None
    # Return client with headers pre-set
    return client


@pytest.fixture
def super_admin_user(db_session: Session):
    """Create a super admin user"""
    # Create admin role
    role = AdminRole(
        name="super_admin",
        permissions={"all": True},
        description="Super administrator with full access"
    )
    db_session.add(role)
    db_session.commit()

    # Create super admin user in User table
    user = User(
        email="superadmin@example.com",
        password_hash=get_password_hash("superadmin123"),
        first_name="Super",
        last_name="Admin",
        role="super_admin",
        status=UserStatus.ACTIVE.value,
        email_verified=True
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)

    # Also create in AdminUser table
    admin = AdminUser(
        id=user.id,
        email=user.email,
        name=f"{user.first_name} {user.last_name}",
        password_hash=user.password_hash,
        role_id=role.id,
        status="active"
    )
    db_session.add(admin)
    db_session.commit()
    db_session.refresh(admin)

    return user


@pytest.fixture
def super_admin_headers(super_admin_user: User):
    """Create authentication headers for a super admin"""
    access_token = create_access_token(data={"sub": super_admin_user.id})
    return {"Authorization": f"Bearer {access_token}"}


@pytest.fixture
def test_admin(db_session: Session):
    """Create a test admin role and user"""
    role = AdminRole(
        name="test_admin",
        permissions={"users": True, "workflows": True},
        description="Test admin role"
    )
    db_session.add(role)
    db_session.commit()

    admin = AdminUser(
        email="admin@example.com",
        name="Test Admin",
        password_hash=get_password_hash("admin123"),
        role_id=role.id,
        status="active"
    )
    db_session.add(admin)
    db_session.commit()
    db_session.refresh(admin)
    return admin


@pytest.mark.skipif(client is None, reason="FastAPI app not available")
class TestUserManagementAPI:
    """Test user management endpoints"""

    def test_get_current_user_requires_auth(self):
        """Test that getting current user requires authentication"""
        response = client.get("/api/users/me")
        # Should return 401 or redirect when not authenticated
        assert response.status_code in [401, 403]

    def test_get_current_user_with_auth(self, test_user):
        """Test getting current user with authentication"""
        access_token = create_access_token(data={"sub": test_user.id})
        response = client.get("/api/users/me", headers={"Authorization": f"Bearer {access_token}"})
        assert response.status_code == 200
        data = response.json()
        assert data["email"] == test_user.email
        assert data["id"] == test_user.id

    def test_list_sessions_requires_auth(self):
        """Test that listing sessions requires authentication"""
        response = client.get("/api/users/sessions")
        assert response.status_code in [401, 403]

    def test_list_sessions_with_auth(self, test_user_with_session, auth_headers):
        """Test listing sessions with authentication"""
        response = client.get("/api/users/sessions", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        # Should have at least one session
        assert len(data) >= 1

    def test_revoke_session_requires_auth(self):
        """Test that revoking a session requires authentication"""
        response = client.delete("/api/users/sessions/test-session-id")
        assert response.status_code in [401, 403, 404]

    def test_revoke_all_sessions_with_auth(self, test_user_with_session, auth_headers):
        """Test revoking all sessions except current"""
        response = client.delete("/api/users/sessions", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert "message" in data


@pytest.mark.skipif(client is None, reason="FastAPI app not available")
class TestEmailVerificationAPI:
    """Test email verification endpoints"""

    def test_verify_email_invalid_code(self, db_session: Session):
        """Test email verification with invalid code"""
        # Create a test user
        user = User(
            email="verify@example.com",
            password_hash=get_password_hash("password123"),
            status=UserStatus.ACTIVE.value
        )
        db_session.add(user)
        db_session.commit()

        response = client.post("/api/email-verification/verify", json={
            "email": "verify@example.com",
            "code": "000000"  # Invalid code
        })

        # Should fail with invalid code
        assert response.status_code == 400

    def test_verify_email_user_not_found(self):
        """Test email verification for non-existent user"""
        response = client.post("/api/email-verification/verify", json={
            "email": "nonexistent@example.com",
            "code": "123456"
        })

        assert response.status_code == 404

    def test_verify_email_success(self, db_session: Session):
        """Test successful email verification"""
        # Create a test user
        user = User(
            email="verify_success@example.com",
            password_hash=get_password_hash("password123"),
            status=UserStatus.ACTIVE.value,
            email_verified=False
        )
        db_session.add(user)
        db_session.commit()

        # Create verification token
        token = EmailVerificationToken(
            user_id=user.id,
            token="123456",
            expires_at=datetime.utcnow() + timedelta(hours=24)
        )
        db_session.add(token)
        db_session.commit()

        response = client.post("/api/email-verification/verify", json={
            "email": "verify_success@example.com",
            "code": "123456"
        })

        assert response.status_code == 200
        data = response.json()
        assert "message" in data

    def test_send_verification_email(self, db_session: Session):
        """Test sending verification email"""
        # Create a test user
        user = User(
            email="newuser@example.com",
            password_hash=get_password_hash("password123"),
            status=UserStatus.ACTIVE.value
        )
        db_session.add(user)
        db_session.commit()

        response = client.post("/api/email-verification/send", json={
            "email": "newuser@example.com"
        })

        # Should succeed (email sending is mocked/logged)
        assert response.status_code == 200
        data = response.json()
        assert "message" in data

    def test_send_verification_email_user_not_found(self):
        """Test sending verification email for non-existent user"""
        # Should return success to prevent email enumeration
        response = client.post("/api/email-verification/send", json={
            "email": "nonexistent@example.com"
        })

        assert response.status_code == 200


@pytest.mark.skipif(client is None, reason="FastAPI app not available")
class TestTenantAPI:
    """Test tenant endpoints"""

    def test_get_tenant_by_subdomain_not_found(self):
        """Test getting tenant with non-existent subdomain"""
        response = client.get("/api/tenants/by-subdomain/nonexistent")
        assert response.status_code == 404

    def test_get_tenant_context_requires_auth(self):
        """Test that getting tenant context requires authentication"""
        response = client.get("/api/tenants/context")
        assert response.status_code in [401, 403]


@pytest.mark.skipif(client is None, reason="FastAPI app not available")
class TestAdminAPI:
    """Test admin endpoints"""

    def test_list_admin_users_requires_auth(self):
        """Test that listing admin users requires authentication"""
        response = client.get("/api/admin/users")
        assert response.status_code in [401, 403]

    def test_list_admin_users_with_super_admin(self, super_admin_headers):
        """Test listing admin users with super admin credentials"""
        response = client.get("/api/admin/users", headers=super_admin_headers)
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)

    def test_list_admin_roles_with_super_admin(self, super_admin_headers):
        """Test listing admin roles"""
        response = client.get("/api/admin/roles", headers=super_admin_headers)
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)

    def test_create_admin_role(self, super_admin_headers):
        """Test creating a new admin role"""
        response = client.post("/api/admin/roles", headers=super_admin_headers, json={
            "name": "test_role_new",
            "permissions": {"users": True, "workflows": False},
            "description": "Test role for API testing"
        })
        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "test_role_new"

    def test_create_admin_user(self, super_admin_headers, db_session: Session):
        """Test creating a new admin user"""
        # First create a role
        role = AdminRole(
            name="role_for_user",
            permissions={"all": False},
            description="Role for test user"
        )
        db_session.add(role)
        db_session.commit()

        response = client.post("/api/admin/users", headers=super_admin_headers, json={
            "email": "newadmin@example.com",
            "name": "New Admin",
            "password": "password123",
            "role_id": role.id
        })
        assert response.status_code == 201
        data = response.json()
        assert data["email"] == "newadmin@example.com"

    def test_update_admin_role(self, super_admin_headers, db_session: Session):
        """Test updating an admin role"""
        role = AdminRole(
            name="role_to_update",
            permissions={"users": True},
            description="Role to be updated"
        )
        db_session.add(role)
        db_session.commit()

        response = client.patch(f"/api/admin/roles/{role.id}", headers=super_admin_headers, json={
            "description": "Updated description"
        })
        assert response.status_code == 200
        data = response.json()
        assert data["description"] == "Updated description"

    def test_delete_admin_role(self, super_admin_headers, db_session: Session):
        """Test deleting an admin role"""
        role = AdminRole(
            name="role_to_delete",
            permissions={"users": False},
            description="Role to be deleted"
        )
        db_session.add(role)
        db_session.commit()

        response = client.delete(f"/api/admin/roles/{role.id}", headers=super_admin_headers)
        assert response.status_code == 200
        data = response.json()
        assert "message" in data

    def test_update_admin_last_login_not_found(self):
        """Test updating last login for non-existent admin"""
        response = client.patch("/api/admin/users/nonexistent-id/last-login")
        assert response.status_code in [401, 403, 404]


@pytest.mark.skipif(client is None, reason="FastAPI app not available")
class TestMeetingAPI:
    """Test meeting endpoints"""

    def test_get_meeting_attendance_not_found(self):
        """Test getting non-existent meeting attendance"""
        response = client.get("/api/meetings/attendance/nonexistent-task")
        assert response.status_code in [401, 403, 404]

    def test_list_meeting_attendance_with_auth(self, test_user, auth_headers):
        """Test listing meeting attendance with authentication"""
        response = client.get("/api/meetings/attendance", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)

    def test_create_meeting_attendance(self, test_user, auth_headers):
        """Test creating meeting attendance record"""
        response = client.post("/api/meetings/attendance", headers=auth_headers, json={
            "task_id": "test-task-123",
            "platform": "zoom",
            "meeting_identifier": "123456789",
            "current_status_message": "Scheduled"
        })
        assert response.status_code == 201
        data = response.json()
        assert data["task_id"] == "test-task-123"
        assert data["platform"] == "zoom"

    def test_get_meeting_attendance_with_auth(self, test_user, auth_headers, db_session: Session):
        """Test getting specific meeting attendance"""
        # Create attendance record first
        attendance = MeetingAttendanceStatus(
            task_id="task-get-123",
            user_id=test_user.id,
            platform="teams",
            meeting_identifier="987654321",
            status_timestamp=datetime.utcnow(),
            current_status_message="In progress"
        )
        db_session.add(attendance)
        db_session.commit()

        response = client.get(f"/api/meetings/attendance/task-get-123", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert data["task_id"] == "task-get-123"

    def test_update_meeting_attendance(self, test_user, auth_headers, db_session: Session):
        """Test updating meeting attendance record"""
        # Create attendance record first
        attendance = MeetingAttendanceStatus(
            task_id="task-update-123",
            user_id=test_user.id,
            platform="zoom",
            meeting_identifier="111222333",
            status_timestamp=datetime.utcnow(),
            current_status_message="In progress"
        )
        db_session.add(attendance)
        db_session.commit()

        response = client.patch(f"/api/meetings/attendance/task-update-123", headers=auth_headers, json={
            "current_status_message": "Completed",
            "final_notion_page_url": "https://notion.so/page123"
        })
        assert response.status_code == 200
        data = response.json()
        assert data["current_status_message"] == "Completed"
        assert data["final_notion_page_url"] == "https://notion.so/page123"

    def test_delete_meeting_attendance(self, test_user, auth_headers, db_session: Session):
        """Test deleting meeting attendance record"""
        # Create attendance record first
        attendance = MeetingAttendanceStatus(
            task_id="task-delete-123",
            user_id=test_user.id,
            platform="zoom",
            meeting_identifier="444555666",
            status_timestamp=datetime.utcnow(),
            current_status_message="Cancelled"
        )
        db_session.add(attendance)
        db_session.commit()

        response = client.delete(f"/api/meetings/attendance/task-delete-123", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert "message" in data


@pytest.mark.skipif(client is None, reason="FastAPI app not available")
class TestFinancialAPI:
    """Test financial endpoints"""

    def test_get_net_worth_requires_auth(self):
        """Test that getting net worth requires authentication"""
        response = client.get("/api/financial/net-worth/summary")
        assert response.status_code in [401, 403]

    def test_list_financial_accounts_requires_auth(self):
        """Test that listing accounts requires authentication"""
        response = client.get("/api/financial/accounts")
        assert response.status_code in [401, 403]

    def test_list_financial_accounts_with_auth(self, test_user, auth_headers):
        """Test listing financial accounts with authentication"""
        response = client.get("/api/financial/accounts", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)

    def test_create_financial_account(self, test_user, auth_headers):
        """Test creating a financial account"""
        response = client.post("/api/financial/accounts", headers=auth_headers, json={
            "account_type": "checking",
            "provider": "Test Bank",
            "name": "My Checking",
            "balance": 1000.00,
            "currency": "USD"
        })
        assert response.status_code == 201
        data = response.json()
        assert data["account_type"] == "checking"
        assert data["balance"] == 1000.00

    def test_get_financial_account(self, test_user, auth_headers, db_session: Session):
        """Test getting a specific financial account"""
        # Create an account first
        account = FinancialAccount(
            user_id=test_user.id,
            account_type="savings",
            provider="Test Bank",
            balance=5000.0,
            currency="USD",
            name="My Savings"
        )
        db_session.add(account)
        db_session.commit()

        response = client.get(f"/api/financial/accounts/{account.id}", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == account.id

    def test_update_financial_account(self, test_user, auth_headers, db_session: Session):
        """Test updating a financial account"""
        # Create an account first
        account = FinancialAccount(
            user_id=test_user.id,
            account_type="investment",
            provider="Test Brokerage",
            balance=10000.0,
            currency="USD",
            name="My Investment"
        )
        db_session.add(account)
        db_session.commit()

        response = client.patch(f"/api/financial/accounts/{account.id}", headers=auth_headers, json={
            "balance": 15000.00
        })
        assert response.status_code == 200
        data = response.json()
        assert data["balance"] == 15000.00

    def test_delete_financial_account(self, test_user, auth_headers, db_session: Session):
        """Test deleting a financial account"""
        # Create an account first
        account = FinancialAccount(
            user_id=test_user.id,
            account_type="credit_card",
            provider="Test Bank",
            balance=-500.0,
            currency="USD",
            name="My Credit Card"
        )
        db_session.add(account)
        db_session.commit()

        response = client.delete(f"/api/financial/accounts/{account.id}", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert "message" in data

    def test_create_net_worth_snapshot(self, test_user, auth_headers):
        """Test creating a net worth snapshot"""
        response = client.post("/api/financial/net-worth/snapshot", headers=auth_headers, json={
            "net_worth": 50000.0,
            "assets": 75000.0,
            "liabilities": 25000.0
        })
        assert response.status_code == 201
        data = response.json()
        assert data["net_worth"] == 50000.0
        assert data["assets"] == 75000.0
        assert data["liabilities"] == 25000.0


class TestDatabaseModels:
    """Test database model relationships"""

    def test_email_verification_token_creation(self, db_session: Session, test_user):
        """Test creating email verification token"""
        token = EmailVerificationToken(
            user_id=test_user.id,
            token="123456",
            expires_at=datetime.utcnow() + timedelta(hours=24)
        )
        db_session.add(token)
        db_session.commit()

        retrieved = db_session.query(EmailVerificationToken).filter(
            EmailVerificationToken.user_id == test_user.id
        ).first()

        assert retrieved is not None
        assert retrieved.token == "123456"

    def test_tenant_creation(self, db_session: Session):
        """Test creating tenant"""
        tenant = Tenant(
            name="Test Organization",
            subdomain="testorg",
            plan_type="premium",
            status="active"
        )
        db_session.add(tenant)
        db_session.commit()

        retrieved = db_session.query(Tenant).filter(
            Tenant.subdomain == "testorg"
        ).first()

        assert retrieved is not None
        assert retrieved.name == "Test Organization"

    def test_admin_role_and_user(self, db_session: Session):
        """Test creating admin role and user"""
        role = AdminRole(
            name="security_admin",
            permissions={"users": True, "security": True},
            description="Security administrator"
        )
        db_session.add(role)
        db_session.commit()

        admin = AdminUser(
            email="security@example.com",
            name="Security Admin",
            password_hash=get_password_hash("secure123"),
            role_id=role.id,
            status="active"
        )
        db_session.add(admin)
        db_session.commit()

        # Test relationship
        retrieved_admin = db_session.query(AdminUser).filter(
            AdminUser.email == "security@example.com"
        ).first()

        assert retrieved_admin is not None
        assert retrieved_admin.role.name == "security_admin"
        assert retrieved_admin.role.permissions["security"] is True

    def test_meeting_attendance_status(self, db_session: Session, test_user):
        """Test creating meeting attendance status"""
        attendance = MeetingAttendanceStatus(
            task_id="task-123",
            user_id=test_user.id,
            platform="zoom",
            meeting_identifier="123456789",
            status_timestamp=datetime.utcnow(),
            current_status_message="In progress"
        )
        db_session.add(attendance)
        db_session.commit()

        retrieved = db_session.query(MeetingAttendanceStatus).filter(
            MeetingAttendanceStatus.task_id == "task-123"
        ).first()

        assert retrieved is not None
        assert retrieved.platform == "zoom"

    def test_financial_account(self, db_session: Session, test_user):
        """Test creating financial account"""
        account = FinancialAccount(
            user_id=test_user.id,
            account_type="checking",
            provider="Test Bank",
            balance=1000.0,
            currency="USD",
            name="My Checking Account"
        )
        db_session.add(account)
        db_session.commit()

        retrieved = db_session.query(FinancialAccount).filter(
            FinancialAccount.user_id == test_user.id
        ).first()

        assert retrieved is not None
        assert retrieved.balance == 1000.0

    def test_net_worth_snapshot(self, db_session: Session, test_user):
        """Test creating net worth snapshot"""
        snapshot = NetWorthSnapshot(
            user_id=test_user.id,
            snapshot_date=datetime.utcnow(),
            net_worth=50000.0,
            assets=75000.0,
            liabilities=25000.0
        )
        db_session.add(snapshot)
        db_session.commit()

        retrieved = db_session.query(NetWorthSnapshot).filter(
            NetWorthSnapshot.user_id == test_user.id
        ).first()

        assert retrieved is not None
        assert retrieved.net_worth == 50000.0
        assert retrieved.assets == 75000.0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
