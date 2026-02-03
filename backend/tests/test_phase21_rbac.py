import os
import sys
import unittest
from enum import Enum
from unittest.mock import MagicMock, patch

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.enterprise_security import AuditEvent, EnterpriseSecurity, EventType
from core.models import User, UserRole
from core.rbac_service import Permission, RBACService


class TestRBACService(unittest.TestCase):
    def test_get_user_permissions(self):
        # Test Member Permissions
        member = User(role=UserRole.MEMBER)
        perms = RBACService.get_user_permissions(member)
        self.assertIn(Permission.AGENT_VIEW, perms)
        self.assertIn(Permission.AGENT_RUN, perms)
        self.assertNotIn(Permission.AGENT_MANAGE, perms)

        # Test Workspace Admin Permissions
        admin = User(role=UserRole.WORKSPACE_ADMIN)
        perms = RBACService.get_user_permissions(admin)
        self.assertIn(Permission.AGENT_MANAGE, perms)
        self.assertIn(Permission.WORKFLOW_MANAGE, perms)
        
        # Test Guest Permissions
        guest = User(role=UserRole.GUEST)
        perms = RBACService.get_user_permissions(guest)
        self.assertIn(Permission.AGENT_VIEW, perms)
        self.assertNotIn(Permission.AGENT_RUN, perms)

    def test_check_permission(self):
        member = User(role=UserRole.MEMBER)
        self.assertTrue(RBACService.check_permission(member, Permission.AGENT_RUN))
        self.assertFalse(RBACService.check_permission(member, Permission.WORKFLOW_MANAGE))

        super_admin = User(role=UserRole.SUPER_ADMIN)
        self.assertTrue(RBACService.check_permission(super_admin, Permission.SYSTEM_ADMIN))
        self.assertTrue(RBACService.check_permission(super_admin, "any_random_permission"))


from fastapi.testclient import TestClient
from main_api_app import app

from core.auth import get_current_user
from core.security_dependencies import require_permission


class TestRBACIntegration(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)
        
    def tearDown(self):
        app.dependency_overrides = {}

    def test_agent_routes_enforcement(self):
        # Mock Member User
        mock_member = User(id="u1", email="member@test.com", role=UserRole.MEMBER)
        
        # Override dependency to return mock member
        app.dependency_overrides[get_current_user] = lambda: mock_member
        
        # 1. List Agents (Requires AGENT_VIEW) - Should Pass
        response = self.client.get("/api/v1/agents/")
        # Note: If agents list empty, returns empty list 200
        self.assertEqual(response.status_code, 200)

        # 2. Run Agent (Requires AGENT_RUN) - Should Pass
        # We need to mock AGENTS dict or use existing key
        # Using "competitive_intel" from existing code
        with patch("api.agent_routes.execute_agent_task"), \
             patch("core.enterprise_security.enterprise_security.log_audit_event") as mock_audit:
             
            response = self.client.post("/api/v1/agents/competitive_intel/run", json={"parameters": {}})
            self.assertEqual(response.status_code, 200)
            
            # Verify Audit Log
            mock_audit.assert_called_once()
            args = mock_audit.call_args[0]
            self.assertIsInstance(args[0], AuditEvent)
            self.assertEqual(args[0].action, "agent_run")
            self.assertEqual(args[0].user_id, "u1")

    def test_agent_routes_denial(self):
        # Mock Guest User
        mock_guest = User(id="u2", role=UserRole.GUEST)
        app.dependency_overrides[get_current_user] = lambda: mock_guest

        # 1. List Agents (Requires AGENT_VIEW) - Should Pass
        response = self.client.get("/api/v1/agents/")
        self.assertEqual(response.status_code, 200)

        # 2. Run Agent (Requires AGENT_RUN) - Should Fail 403
        response = self.client.post("/api/v1/agents/competitive_intel/run", json={"parameters": {}})
        self.assertEqual(response.status_code, 403)

    def test_workflow_routes_enforcement(self):
        # Mock Member User (Cannot Manage Workflow)
        mock_member = User(id="u1", role=UserRole.MEMBER)
        app.dependency_overrides[get_current_user] = lambda: mock_member

        # Create Workflow (Requires WORKFLOW_MANAGE) -> Fail
        response = self.client.post("/api/v1/workflows", json={
            "name": "Test", "nodes": [], "connections": []
        })
        self.assertEqual(response.status_code, 403)

        # Switch to Admin
        mock_admin = User(id="u3", role=UserRole.WORKSPACE_ADMIN)
        app.dependency_overrides[get_current_user] = lambda: mock_admin
        
        # Create Workflow -> Success (assuming payload valid, else 422 or 500 but not 403)
        # We'll pass a minimal valid payload
        payload = {
            "name": "Test Flow",
            "description": "desc",
            "version": "1.0",
            "nodes": [],
            "connections": [],
            "triggers": [],
            "enabled": True
        }
        # Mock save_workflows to avoid file IO
        with patch("core.workflow_endpoints.save_workflows"), \
             patch("core.workflow_endpoints.load_workflows", return_value=[]):
            response = self.client.post("/api/v1/workflows", json=payload)
            self.assertEqual(response.status_code, 200)

if __name__ == "__main__":
    unittest.main()
