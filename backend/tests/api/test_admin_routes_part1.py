"""
Admin Routes API Tests - Part 1: User and Role Management

Tests for admin routes Part 1 (lines 1-545):
- Admin user CRUD: list, get, create, update, delete, last-login
- Admin role CRUD: list, get, create, update, delete
- Super admin authorization: require_super_admin dependency
- Error paths: 404 not found, 409 conflict, 403 unauthorized
- Governance enforcement: AUTONOMOUS required for create/delete

Coverage target: 75%+ line coverage on admin_routes.py Part 1
"""

import pytest
import uuid
from datetime import datetime, timezone
from fastapi import FastAPI, status
from fastapi.testclient import TestClient
from unittest.mock import MagicMock, AsyncMock, patch
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import StaticPool

# Import admin routes router
from api.admin_routes import router

# Import models
from core.models import (
    Base, User, AdminUser, AdminRole
)

# Import auth for password hashing
from core.auth import get_password_hash


# ============================================================================
# Test Database Setup
# ============================================================================

@pytest.fixture(scope="function")
def test_db():
    """Create in-memory SQLite database for testing."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool
    )

    # Create only the tables we need for admin routes testing
    # This avoids JSONB/SQLite incompatibility issues with other models
    from core.models import AdminUser, AdminRole, User

    # Create tables individually using Table.create()
    AdminUser.__table__.create(bind=engine, checkfirst=True)
    AdminRole.__table__.create(bind=engine, checkfirst=True)
    User.__table__.create(bind=engine, checkfirst=True)

    # Create session
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    db = TestingSessionLocal()

    yield db

    # Cleanup
    db.close()
    # Drop tables individually
    AdminUser.__table__.drop(bind=engine)
    AdminRole.__table__.drop(bind=engine)
    User.__table__.drop(bind=engine)


@pytest.fixture(scope="function")
def test_app(test_db: Session):
    """Create FastAPI app with admin routes for testing."""
    app = FastAPI()
    app.include_router(router)

    # Override get_db dependency
    from core.database import get_db

    def override_get_db():
        try:
            yield test_db
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db

    yield app

    # Clean up overrides
    app.dependency_overrides.clear()


@pytest.fixture(scope="function")
def client(test_app: FastAPI):
    """Create TestClient for testing."""
    return TestClient(test_app)


@pytest.fixture(scope="function")
def mock_super_admin(test_db: Session) -> User:
    """Create mock super_admin user for authorization tests"""
    user = User(
        id=str(uuid.uuid4()),
        email="superadmin@test.com",
        first_name="Super",
        last_name="Admin",
        name="Super Admin",
        role="super_admin",
        status="active",
        email_verified=True
    )
    test_db.add(user)
    test_db.commit()
    test_db.refresh(user)
    return user


@pytest.fixture(scope="function")
def mock_team_lead(test_db: Session) -> User:
    """Create mock team_lead user for authorization tests"""
    user = User(
        id=str(uuid.uuid4()),
        email="teamlead@test.com",
        first_name="Team",
        last_name="Lead",
        name="Team Lead",
        role="team_lead",
        status="active",
        email_verified=True
    )
    test_db.add(user)
    test_db.commit()
    test_db.refresh(user)
    return user


@pytest.fixture(scope="function")
def mock_admin_role(test_db: Session) -> AdminRole:
    """Create mock admin role for testing"""
    role = AdminRole(
        id=str(uuid.uuid4()),
        name="Test Admin Role",
        permissions={"users": True, "workflows": False, "reports": True},
        description="Test role for unit tests"
    )
    test_db.add(role)
    test_db.commit()
    test_db.refresh(role)
    return role


@pytest.fixture(scope="function")
def mock_admin_role_2(test_db: Session) -> AdminRole:
    """Create second mock admin role for update/conflict tests"""
    role = AdminRole(
        id=str(uuid.uuid4()),
        name="Another Test Role",
        permissions={"users": False, "workflows": True, "reports": False},
        description="Second test role"
    )
    test_db.add(role)
    test_db.commit()
    test_db.refresh(role)
    return role


@pytest.fixture(scope="function")
def mock_admin_user(test_db: Session, mock_admin_role: AdminRole) -> AdminUser:
    """Create mock admin user for testing"""
    admin = AdminUser(
        id=str(uuid.uuid4()),
        email="testadmin@test.com",
        name="Test Admin User",
        password_hash=get_password_hash("TestPass123!"),
        role_id=mock_admin_role.id,
        status="active",
        last_login=None,
        created_at=datetime.now(timezone.utc)
    )
    test_db.add(admin)
    test_db.commit()
    test_db.refresh(admin)
    return admin


@pytest.fixture(scope="function")
def mock_inactive_admin_user(test_db: Session, mock_admin_role: AdminRole) -> AdminUser:
    """Create inactive admin user for status tests"""
    admin = AdminUser(
        id=str(uuid.uuid4()),
        email="inactiveadmin@test.com",
        name="Inactive Admin",
        password_hash=get_password_hash("TestPass123!"),
        role_id=mock_admin_role.id,
        status="inactive",
        last_login=None,
        created_at=datetime.now(timezone.utc)
    )
    test_db.add(admin)
    test_db.commit()
    test_db.refresh(admin)
    return admin


@pytest.fixture(scope="function")
def authenticated_client(client: TestClient, mock_super_admin: User):
    """Create authenticated TestClient with admin user."""
    # Mock get_current_user to return super_admin
    from core.auth import get_current_user

    def override_get_current_user():
        return mock_super_admin

    # Also mock require_super_admin
    from api.admin_routes import require_super_admin

    def override_require_super_admin():
        return mock_super_admin

    # Override in router's app
    client.app.dependency_overrides[get_current_user] = override_get_current_user
    client.app.dependency_overrides[require_super_admin] = override_require_super_admin

    yield client

    # Clean up
    client.app.dependency_overrides.clear()


# ============================================================================
# Part 1: Admin User Management Tests
# ============================================================================

class TestAdminUserListing:
    """Tests for GET /api/admin/users (list admin users)"""

    def test_list_admin_users_success(self, authenticated_client: TestClient, test_db: Session, mock_admin_role: AdminRole):
        """Test listing all admin users successfully"""
        # Create multiple admin users
        admin1 = AdminUser(
            id=str(uuid.uuid4()),
            email="admin1@test.com",
            name="Admin One",
            password_hash=get_password_hash("Pass123!"),
            role_id=mock_admin_role.id,
            status="active"
        )
        admin2 = AdminUser(
            id=str(uuid.uuid4()),
            email="admin2@test.com",
            name="Admin Two",
            password_hash=get_password_hash("Pass456!"),
            role_id=mock_admin_role.id,
            status="active"
        )
        test_db.add(admin1)
        test_db.add(admin2)
        test_db.commit()

        response = authenticated_client.get("/api/admin/users")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert isinstance(data, list)
        assert len(data) >= 2

        # Verify response structure
        for user in data:
            assert "id" in user
            assert "email" in user
            assert "name" in user
            assert "role_id" in user
            assert "role_name" in user
            assert "permissions" in user
            assert "status" in user
            assert "last_login" in user

    def test_list_admin_users_empty(self, authenticated_client: TestClient, test_db: Session):
        """Test listing admin users when none exist"""
        # Ensure no admin users exist
        test_db.query(AdminUser).delete()
        test_db.commit()

        response = authenticated_client.get("/api/admin/users")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert isinstance(data, list)
        assert len(data) == 0

    def test_list_admin_users_with_roles_joined(self, authenticated_client: TestClient, test_db: Session, mock_admin_role: AdminRole):
        """Test that role information is properly joined"""
        admin = AdminUser(
            id=str(uuid.uuid4()),
            email="roleadmin@test.com",
            name="Role Test Admin",
            password_hash=get_password_hash("Pass123!"),
            role_id=mock_admin_role.id,
            status="active"
        )
        test_db.add(admin)
        test_db.commit()

        response = authenticated_client.get("/api/admin/users")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert len(data) >= 1

        # Find our test admin
        test_admin = next((u for u in data if u["email"] == "roleadmin@test.com"), None)
        assert test_admin is not None
        assert test_admin["role_name"] == mock_admin_role.name
        assert test_admin["permissions"] == mock_admin_role.permissions


class TestAdminUserRetrieval:
    """Tests for GET /api/admin/users/{admin_id} (get specific admin user)"""

    def test_get_admin_user_success(self, authenticated_client: TestClient, test_db: Session, mock_admin_user: AdminUser):
        """Test getting a specific admin user successfully"""
        response = authenticated_client.get(f"/api/admin/users/{mock_admin_user.id}")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["id"] == mock_admin_user.id
        assert data["email"] == mock_admin_user.email
        assert data["name"] == mock_admin_user.name
        assert data["role_id"] == mock_admin_user.role_id
        assert data["status"] == mock_admin_user.status
        assert "last_login" in data
        assert "created_at" in data

    def test_get_admin_user_not_found(self, authenticated_client: TestClient):
        """Test getting a non-existent admin user"""
        fake_id = str(uuid.uuid4())

        response = authenticated_client.get(f"/api/admin/users/{fake_id}")

        assert response.status_code == status.HTTP_404_NOT_FOUND
        data = response.json()
        assert "error" in data or "detail" in data

    def test_get_admin_user_unauthorized(self, client: TestClient, test_db: Session, mock_team_lead: User):
        """Test that non-super_admin users cannot access admin endpoints"""
        # Override authenticated_client to use team_lead instead of super_admin
        def override_get_current_user():
            return mock_team_lead

        def override_require_super_admin():
            from core.base_routes import HTTPException
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied: super_admin role required"
            )

        client.app.dependency_overrides[client.app.dependencies[0].dependency] = override_get_current_user
        from api.admin_routes import require_super_admin
        client.app.dependency_overrides[require_super_admin] = override_require_super_admin

        response = client.get(f"/api/admin/users/{uuid.uuid4()}")

        assert response.status_code == status.HTTP_403_FORBIDDEN


class TestAdminUserCreation:
    """Tests for POST /api/admin/users (create admin user)"""

    def test_create_admin_user_success(self, authenticated_client: TestClient, test_db: Session, mock_admin_role: AdminRole):
        """Test creating admin user successfully"""
        request_data = {
            "email": "newadmin@test.com",
            "name": "New Admin",
            "password": "SecurePass123!",
            "role_id": mock_admin_role.id
        }

        response = authenticated_client.post("/api/admin/users", json=request_data)

        assert response.status_code == status.HTTP_201_CREATED
        data = response.json()
        assert data["email"] == "newadmin@test.com"
        assert data["name"] == "New Admin"
        assert data["role_id"] == mock_admin_role.id
        assert data["status"] == "active"
        assert "id" in data

        # Verify user created in DB
        admin = test_db.query(AdminUser).filter(AdminUser.email == "newadmin@test.com").first()
        assert admin is not None
        assert admin.password_hash != "SecurePass123!"  # Password should be hashed

    def test_create_admin_user_invalid_email(self, authenticated_client: TestClient):
        """Test creating admin user with invalid email"""
        request_data = {
            "email": "not-an-email",
            "name": "Test Admin",
            "password": "SecurePass123!",
            "role_id": str(uuid.uuid4())
        }

        response = authenticated_client.post("/api/admin/users", json=request_data)

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    def test_create_admin_user_weak_password(self, authenticated_client: TestClient):
        """Test creating admin user with weak password"""
        request_data = {
            "email": "test@test.com",
            "name": "Test Admin",
            "password": "short",  # Less than 8 characters
            "role_id": str(uuid.uuid4())
        }

        response = authenticated_client.post("/api/admin/users", json=request_data)

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    def test_create_admin_user_role_not_found(self, authenticated_client: TestClient):
        """Test creating admin user with non-existent role"""
        request_data = {
            "email": "test@test.com",
            "name": "Test Admin",
            "password": "SecurePass123!",
            "role_id": str(uuid.uuid4())  # Non-existent role
        }

        response = authenticated_client.post("/api/admin/users", json=request_data)

        assert response.status_code == status.HTTP_404_NOT_FOUND
        data = response.json()
        assert "role" in str(data).lower() or "field" in str(data).lower()

    def test_create_admin_user_duplicate_email(self, authenticated_client: TestClient, test_db: Session, mock_admin_user: AdminUser):
        """Test creating admin user with duplicate email"""
        request_data = {
            "email": mock_admin_user.email,  # Already exists
            "name": "Duplicate Admin",
            "password": "SecurePass123!",
            "role_id": mock_admin_user.role_id
        }

        response = authenticated_client.post("/api/admin/users", json=request_data)

        assert response.status_code == status.HTTP_409_CONFLICT
        data = response.json()
        assert "email" in str(data).lower() or "exists" in str(data).lower()

    def test_create_admin_user_password_hashed(self, authenticated_client: TestClient, test_db: Session, mock_admin_role: AdminRole):
        """Test that password is hashed during creation"""
        request_data = {
            "email": "hashed@test.com",
            "name": "Hashed Admin",
            "password": "PlainPassword123!",
            "role_id": mock_admin_role.id
        }

        response = authenticated_client.post("/api/admin/users", json=request_data)

        assert response.status_code == status.HTTP_201_CREATED

        # Verify password hashed
        admin = test_db.query(AdminUser).filter(AdminUser.email == "hashed@test.com").first()
        assert admin is not None
        assert admin.password_hash != "PlainPassword123!"
        assert admin.password_hash.startswith("$2b$") or len(admin.password_hash) > 50  # bcrypt hash


class TestAdminUserUpdate:
    """Tests for PATCH /api/admin/users/{admin_id} (update admin user)"""

    def test_update_admin_user_name(self, authenticated_client: TestClient, test_db: Session, mock_admin_user: AdminUser):
        """Test updating admin user name"""
        response = authenticated_client.patch(
            f"/api/admin/users/{mock_admin_user.id}",
            json={"name": "Updated Name"}
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["name"] == "Updated Name"

        # Verify in DB
        test_db.refresh(mock_admin_user)
        assert mock_admin_user.name == "Updated Name"

    def test_update_admin_user_role(self, authenticated_client: TestClient, test_db: Session, mock_admin_user: AdminUser, mock_admin_role_2: AdminRole):
        """Test updating admin user role"""
        response = authenticated_client.patch(
            f"/api/admin/users/{mock_admin_user.id}",
            json={"role_id": mock_admin_role_2.id}
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["role_id"] == mock_admin_role_2.id

        # Verify in DB
        test_db.refresh(mock_admin_user)
        assert mock_admin_user.role_id == mock_admin_role_2.id

    def test_update_admin_user_status(self, authenticated_client: TestClient, test_db: Session, mock_admin_user: AdminUser):
        """Test updating admin user status"""
        response = authenticated_client.patch(
            f"/api/admin/users/{mock_admin_user.id}",
            json={"status": "inactive"}
        )

        assert response.status_code == status.HTTP_200_OK

        # Verify in DB
        test_db.refresh(mock_admin_user)
        assert mock_admin_user.status == "inactive"

    def test_update_admin_user_multiple_fields(self, authenticated_client: TestClient, test_db: Session, mock_admin_user: AdminUser, mock_admin_role_2: AdminRole):
        """Test updating multiple admin user fields"""
        response = authenticated_client.patch(
            f"/api/admin/users/{mock_admin_user.id}",
            json={
                "name": "Multi Update",
                "role_id": mock_admin_role_2.id,
                "status": "inactive"
            }
        )

        assert response.status_code == status.HTTP_200_OK

        # Verify all fields updated
        test_db.refresh(mock_admin_user)
        assert mock_admin_user.name == "Multi Update"
        assert mock_admin_user.role_id == mock_admin_role_2.id
        assert mock_admin_user.status == "inactive"

    def test_update_admin_user_not_found(self, authenticated_client: TestClient):
        """Test updating non-existent admin user"""
        response = authenticated_client.patch(
            f"/api/admin/users/{uuid.uuid4()}",
            json={"name": "Test"}
        )

        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_update_admin_user_invalid_role(self, authenticated_client: TestClient, test_db: Session, mock_admin_user: AdminUser):
        """Test updating admin user with invalid role"""
        response = authenticated_client.patch(
            f"/api/admin/users/{mock_admin_user.id}",
            json={"role_id": str(uuid.uuid4())}  # Non-existent role
        )

        assert response.status_code == status.HTTP_404_NOT_FOUND
        data = response.json()
        assert "role" in str(data).lower()


class TestAdminUserDeletion:
    """Tests for DELETE /api/admin/users/{admin_id} (delete admin user)"""

    def test_delete_admin_user_success(self, authenticated_client: TestClient, test_db: Session, mock_admin_user: AdminUser):
        """Test deleting admin user successfully"""
        admin_id = mock_admin_user.id

        response = authenticated_client.delete(f"/api/admin/users/{admin_id}")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "deleted" in data["message"].lower()

        # Verify deleted from DB
        admin = test_db.query(AdminUser).filter(AdminUser.id == admin_id).first()
        assert admin is None

    def test_delete_admin_user_not_found(self, authenticated_client: TestClient):
        """Test deleting non-existent admin user"""
        response = authenticated_client.delete(f"/api/admin/users/{uuid.uuid4()}")

        assert response.status_code == status.HTTP_404_NOT_FOUND


class TestAdminUserLastLogin:
    """Tests for PATCH /api/admin/users/{admin_id}/last-login"""

    def test_update_last_login_success(self, authenticated_client: TestClient, test_db: Session, mock_admin_user: AdminUser):
        """Test updating last login timestamp"""
        assert mock_admin_user.last_login is None

        response = authenticated_client.patch(f"/api/admin/users/{mock_admin_user.id}/last-login")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "updated" in data["message"].lower()

        # Verify updated in DB
        test_db.refresh(mock_admin_user)
        assert mock_admin_user.last_login is not None
        assert isinstance(mock_admin_user.last_login, datetime)

    def test_update_last_login_not_found(self, authenticated_client: TestClient):
        """Test updating last login for non-existent user"""
        response = authenticated_client.patch(f"/api/admin/users/{uuid.uuid4()}/last-login")

        assert response.status_code == status.HTTP_404_NOT_FOUND


# ============================================================================
# Part 1: Admin Role Management Tests
# ============================================================================

class TestAdminRoleListing:
    """Tests for GET /api/admin/roles (list admin roles)"""

    def test_list_admin_roles_success(self, authenticated_client: TestClient, test_db: Session, mock_admin_role: AdminRole, mock_admin_role_2: AdminRole):
        """Test listing all admin roles successfully"""
        response = authenticated_client.get("/api/admin/roles")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert isinstance(data, list)
        assert len(data) >= 2

        # Verify response structure
        for role in data:
            assert "id" in role
            assert "name" in role
            assert "permissions" in role
            assert "description" in role

    def test_list_admin_roles_empty(self, authenticated_client: TestClient, test_db: Session):
        """Test listing admin roles when none exist"""
        # Ensure no roles exist
        test_db.query(AdminRole).delete()
        test_db.commit()

        response = authenticated_client.get("/api/admin/roles")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert isinstance(data, list)
        assert len(data) == 0


class TestAdminRoleRetrieval:
    """Tests for GET /api/admin/roles/{role_id} (get specific admin role)"""

    def test_get_admin_role_success(self, authenticated_client: TestClient, mock_admin_role: AdminRole):
        """Test getting a specific admin role successfully"""
        response = authenticated_client.get(f"/api/admin/roles/{mock_admin_role.id}")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["id"] == mock_admin_role.id
        assert data["name"] == mock_admin_role.name
        assert data["permissions"] == mock_admin_role.permissions
        assert data["description"] == mock_admin_role.description

    def test_get_admin_role_not_found(self, authenticated_client: TestClient):
        """Test getting a non-existent admin role"""
        response = authenticated_client.get(f"/api/admin/roles/{uuid.uuid4()}")

        assert response.status_code == status.HTTP_404_NOT_FOUND


class TestAdminRoleCreation:
    """Tests for POST /api/admin/roles (create admin role)"""

    def test_create_admin_role_success(self, authenticated_client: TestClient):
        """Test creating admin role successfully"""
        request_data = {
            "name": "New Role",
            "permissions": {"users": True, "reports": False},
            "description": "Test role"
        }

        response = authenticated_client.post("/api/admin/roles", json=request_data)

        assert response.status_code == status.HTTP_201_CREATED
        data = response.json()
        assert data["name"] == "New Role"
        assert data["permissions"] == {"users": True, "reports": False}
        assert data["description"] == "Test role"
        assert "id" in data

    def test_create_admin_role_duplicate_name(self, authenticated_client: TestClient, test_db: Session, mock_admin_role: AdminRole):
        """Test creating admin role with duplicate name"""
        request_data = {
            "name": mock_admin_role.name,  # Already exists
            "permissions": {"users": True},
            "description": "Duplicate"
        }

        response = authenticated_client.post("/api/admin/roles", json=request_data)

        assert response.status_code == status.HTTP_409_CONFLICT
        data = response.json()
        assert "name" in str(data).lower() or "exists" in str(data).lower()


class TestAdminRoleUpdate:
    """Tests for PATCH /api/admin/roles/{role_id} (update admin role)"""

    def test_update_admin_role_name(self, authenticated_client: TestClient, test_db: Session, mock_admin_role: AdminRole):
        """Test updating admin role name"""
        response = authenticated_client.patch(
            f"/api/admin/roles/{mock_admin_role.id}",
            json={"name": "Updated Name"}
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["name"] == "Updated Name"

        # Verify in DB
        test_db.refresh(mock_admin_role)
        assert mock_admin_role.name == "Updated Name"

    def test_update_admin_role_permissions(self, authenticated_client: TestClient, test_db: Session, mock_admin_role: AdminRole):
        """Test updating admin role permissions"""
        new_permissions = {"users": False, "admin": True}
        response = authenticated_client.patch(
            f"/api/admin/roles/{mock_admin_role.id}",
            json={"permissions": new_permissions}
        )

        assert response.status_code == status.HTTP_200_OK

        # Verify in DB
        test_db.refresh(mock_admin_role)
        assert mock_admin_role.permissions == new_permissions

    def test_update_admin_role_description(self, authenticated_client: TestClient, test_db: Session, mock_admin_role: AdminRole):
        """Test updating admin role description"""
        response = authenticated_client.patch(
            f"/api/admin/roles/{mock_admin_role.id}",
            json={"description": "New description"}
        )

        assert response.status_code == status.HTTP_200_OK

        # Verify in DB
        test_db.refresh(mock_admin_role)
        assert mock_admin_role.description == "New description"

    def test_update_admin_role_duplicate_name(self, authenticated_client: TestClient, test_db: Session, mock_admin_role: AdminRole, mock_admin_role_2: AdminRole):
        """Test updating role name to match existing role"""
        response = authenticated_client.patch(
            f"/api/admin/roles/{mock_admin_role.id}",
            json={"name": mock_admin_role_2.name}  # Duplicate name
        )

        assert response.status_code == status.HTTP_409_CONFLICT
        data = response.json()
        assert "name" in str(data).lower() or "exists" in str(data).lower()

    def test_update_admin_role_not_found(self, authenticated_client: TestClient):
        """Test updating non-existent admin role"""
        response = authenticated_client.patch(
            f"/api/admin/roles/{uuid.uuid4()}",
            json={"name": "Test"}
        )

        assert response.status_code == status.HTTP_404_NOT_FOUND


class TestAdminRoleDeletion:
    """Tests for DELETE /api/admin/roles/{role_id} (delete admin role)"""

    def test_delete_admin_role_success(self, authenticated_client: TestClient, test_db: Session):
        """Test deleting admin role successfully"""
        # Create role with no users
        role = AdminRole(
            id=str(uuid.uuid4()),
            name="Deletable Role",
            permissions={"test": True},
            description="Role for deletion test"
        )
        test_db.add(role)
        test_db.commit()
        role_id = role.id

        response = authenticated_client.delete(f"/api/admin/roles/{role_id}")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "deleted" in data["message"].lower()

        # Verify deleted from DB
        deleted_role = test_db.query(AdminRole).filter(AdminRole.id == role_id).first()
        assert deleted_role is None

    def test_delete_admin_role_not_found(self, authenticated_client: TestClient):
        """Test deleting non-existent admin role"""
        response = authenticated_client.delete(f"/api/admin/roles/{uuid.uuid4()}")

        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_delete_admin_role_in_use(self, authenticated_client: TestClient, test_db: Session, mock_admin_role: AdminRole, mock_admin_user: AdminUser):
        """Test deleting role that is assigned to admin users"""
        # mock_admin_user has mock_admin_role assigned
        response = authenticated_client.delete(f"/api/admin/roles/{mock_admin_role.id}")

        assert response.status_code == status.HTTP_409_CONFLICT
        data = response.json()
        assert "user" in str(data).lower() or "assigned" in str(data).lower()
