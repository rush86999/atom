"""Coverage wave 48 — api/admin_routes.py user/role CRUD branches (TDD).

Picks up from 78% (part2 covers websocket/ratings/conflicts). Targets the
user + role CRUD endpoints and their error branches:
- create_admin_user: role-not-found, email-exists conflict, success
- update_admin_user: not-found, role-not-found on role change, success
- delete_admin_user: not-found, success
- get_admin_user: found, not-found
- update_admin_last_login: not-found, success
- create_admin_role: duplicate-name conflict, success
- update_admin_role: not-found, duplicate-name conflict, success
- delete_admin_role: not-found, success
- get_admin_role: found, not-found
- list_admin_users / list_admin_roles
"""
import pytest
import tempfile
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import core.models  # noqa: F401 — ensure all tables registered
from api.admin_routes import router
from core.database import Base
from core.models import AdminRole, AdminUser, User


@pytest.fixture(scope="module")
def engine():
    fd, path = tempfile.mkstemp(suffix=".db")
    import os
    os.close(fd)
    engine = create_engine(
        f"sqlite:///{path}",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    yield engine
    engine.dispose()
    os.unlink(path)


@pytest.fixture
def db(engine):
    session = sessionmaker(bind=engine)()
    yield session
    session.close()


@pytest.fixture
def test_app(db):
    app = FastAPI()
    app.include_router(router)

    from core.database import get_db
    from core.auth import get_current_user

    def _get_db():
        try:
            yield db
        finally:
            pass

    admin = User(
        id="admin-1", email="admin@x.com", role="super_admin",
        tenant_id="t-1", first_name="A", last_name="B", status="active")
    db.add(admin)
    db.commit()

    def _get_current_user():
        return admin

    app.dependency_overrides[get_db] = _get_db
    app.dependency_overrides[get_current_user] = _get_current_user
    yield app
    app.dependency_overrides.clear()
    db.query(AdminUser).delete()
    db.query(AdminRole).delete()
    db.query(User).delete()
    db.commit()


@pytest.fixture
def client(test_app):
    return TestClient(test_app)


def _role(db, role_id="role-1", name="Admin Role"):
    role = AdminRole(
        id=role_id, name=name,
        permissions={"users": True, "workflows": False},
        description="d")
    db.add(role)
    db.commit()
    return role


def _admin_user(db, user_id="u-1", email="user@x.com", role_id="role-1"):
    user = AdminUser(
        id=user_id, email=email, name="User", password_hash="h",
        role_id=role_id, status="active")
    db.add(user)
    db.commit()
    return user


class TestUserCRUD:
    def test_list_admin_users(self, client, db):
        _role(db)
        _admin_user(db)
        response = client.get("/api/admin/users")
        assert response.status_code == 200
        assert any(u["email"] == "user@x.com" for u in response.json())

    def test_create_admin_user_success(self, client, db):
        _role(db)
        response = client.post("/api/admin/users", json={
            "email": "new@x.com", "name": "New", "password": "password123",
            "role_id": "role-1"})
        assert response.status_code == 201
        assert response.json()["email"] == "new@x.com"

    def test_create_admin_user_role_not_found(self, client, db):
        response = client.post("/api/admin/users", json={
            "email": "new@x.com", "name": "New", "password": "password123",
            "role_id": "ghost-role"})
        assert response.status_code == 404

    def test_create_admin_user_duplicate_email(self, client, db):
        _role(db)
        _admin_user(db, email="dup@x.com")
        response = client.post("/api/admin/users", json={
            "email": "dup@x.com", "name": "New", "password": "password123",
            "role_id": "role-1"})
        assert response.status_code == 409

    def test_get_admin_user_success(self, client, db):
        _role(db)
        _admin_user(db)
        response = client.get("/api/admin/users/u-1")
        assert response.status_code == 200
        assert response.json()["id"] == "u-1"

    def test_get_admin_user_not_found(self, client, db):
        response = client.get("/api/admin/users/ghost")
        assert response.status_code == 404

    def test_update_admin_user_success(self, client, db):
        _role(db)
        _admin_user(db)
        response = client.patch("/api/admin/users/u-1", json={
            "name": "Updated", "status": "inactive"})
        assert response.status_code == 200
        assert response.json()["name"] == "Updated"
        assert response.json()["status"] == "inactive"

    def test_update_admin_user_not_found(self, client, db):
        response = client.patch("/api/admin/users/ghost", json={"name": "X"})
        assert response.status_code == 404

    def test_update_admin_user_invalid_role(self, client, db):
        _role(db)
        _admin_user(db)
        response = client.patch("/api/admin/users/u-1", json={"role_id": "ghost"})
        assert response.status_code == 404

    def test_update_admin_user_invalid_status(self, client, db):
        _role(db)
        _admin_user(db)
        response = client.patch("/api/admin/users/u-1", json={"status": "bogus"})
        assert response.status_code == 422

    def test_delete_admin_user_success(self, client, db):
        _role(db)
        _admin_user(db)
        response = client.delete("/api/admin/users/u-1")
        assert response.status_code == 200
        assert response.json()["message"]

    def test_delete_admin_user_not_found(self, client, db):
        response = client.delete("/api/admin/users/ghost")
        assert response.status_code == 404

    def test_update_last_login_success(self, client, db):
        _role(db)
        _admin_user(db)
        response = client.patch("/api/admin/users/u-1/last-login")
        assert response.status_code == 200

    def test_update_last_login_not_found(self, client, db):
        response = client.patch("/api/admin/users/ghost/last-login")
        assert response.status_code == 404


class TestRoleCRUD:
    def test_list_admin_roles(self, client, db):
        _role(db)
        response = client.get("/api/admin/roles")
        assert response.status_code == 200
        assert any(r["id"] == "role-1" for r in response.json())

    def test_create_admin_role_success(self, client, db):
        response = client.post("/api/admin/roles", json={
            "name": "New Role", "permissions": {"users": True},
            "description": "d"})
        assert response.status_code == 201

    def test_create_admin_role_duplicate(self, client, db):
        _role(db)
        response = client.post("/api/admin/roles", json={
            "name": "Admin Role", "permissions": {"users": True}})
        assert response.status_code == 409

    def test_get_admin_role_success(self, client, db):
        _role(db)
        response = client.get("/api/admin/roles/role-1")
        assert response.status_code == 200
        assert response.json()["id"] == "role-1"

    def test_get_admin_role_not_found(self, client, db):
        response = client.get("/api/admin/roles/ghost")
        assert response.status_code == 404

    def test_update_admin_role_success(self, client, db):
        _role(db)
        response = client.patch("/api/admin/roles/role-1", json={
            "description": "updated"})
        assert response.status_code == 200

    def test_update_admin_role_not_found(self, client, db):
        response = client.patch("/api/admin/roles/ghost", json={"name": "X"})
        assert response.status_code == 404

    def test_update_admin_role_duplicate_name(self, client, db):
        _role(db, role_id="role-1", name="First")
        _role(db, role_id="role-2", name="Second")
        response = client.patch("/api/admin/roles/role-2", json={"name": "First"})
        assert response.status_code == 409

    def test_delete_admin_role_success(self, client, db):
        _role(db)
        response = client.delete("/api/admin/roles/role-1")
        assert response.status_code == 200

    def test_delete_admin_role_not_found(self, client, db):
        response = client.delete("/api/admin/roles/ghost")
        assert response.status_code == 404


class TestUserRoleBranches:
    def test_update_user_role_id(self, client, db):
        _role(db, role_id="role-1", name="First")
        _role(db, role_id="role-2", name="Second")
        _admin_user(db)
        response = client.patch("/api/admin/users/u-1", json={"role_id": "role-2"})
        assert response.status_code == 200
        assert response.json()["role_id"] == "role-2"

    def test_update_role_name_and_permissions(self, client, db):
        _role(db)
        response = client.patch("/api/admin/roles/role-1", json={
            "name": "Renamed", "permissions": {"users": False, "x": True}})
        assert response.status_code == 200
        assert response.json()["name"] == "Renamed"

    def test_delete_role_in_use_conflict(self, client, db):
        _role(db)
        _admin_user(db)
        response = client.delete("/api/admin/roles/role-1")
        assert response.status_code == 409

    def test_status_validator_success_returns_value(self):
        from api.admin_routes import UpdateAdminUserRequest
        req = UpdateAdminUserRequest(status="inactive")
        assert req.status == "inactive"
        req2 = UpdateAdminUserRequest(status=None)
        assert req2.status is None


class TestBulkResolveException:
    def test_bulk_resolve_resolver_exception(self, client, db):
        from unittest.mock import MagicMock, patch
        with patch("core.conflict_resolution_service.ConflictResolutionService") as mock_cls:
            mock_resolver = MagicMock()
            mock_resolver.resolve_conflict.side_effect = RuntimeError("boom")
            mock_cls.return_value = mock_resolver
            response = client.post("/api/admin/conflicts/bulk-resolve", json={
                "conflict_ids": [1, 2], "strategy": "merge",
                "resolved_by": "admin-1"})
        assert response.status_code == 200
        data = response.json()
        assert data["failed_count"] == 2
        assert data["resolved_count"] == 0
