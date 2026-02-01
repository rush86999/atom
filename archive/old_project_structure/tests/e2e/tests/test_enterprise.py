"""
E2E Tests for Enterprise User Management
Tests workspaces, teams, and user management endpoints
"""

import pytest
import requests
from datetime import datetime

BASE_URL = "http://localhost:5063"

# Test Data
test_workspace_data = {
    "name": f"Test Workspace {datetime.now().timestamp()}",
    "description": "E2E test workspace",
    "plan_tier": "enterprise"
}

test_team_data = {
    "name": "Engineering Team",
    "description": "Core development team"
}

test_user_data = {
    "email": f"test_{datetime.now().timestamp()}@example.com",
    "password": "TestPass123!",
    "first_name": "Test",
    "last_name": "User"
}

class TestEnterpriseWorkspaces:
    """Test workspace CRUD operations"""
    
    @pytest.fixture(scope="class")
    def workspace_id(self):
        """Create a workspace for testing"""
        response = requests.post(f"{BASE_URL}/api/enterprise/workspaces", json=test_workspace_data)
        assert response.status_code == 201
        return response.json()["workspace_id"]
    
    def test_create_workspace(self):
        """Test workspace creation"""
        response = requests.post(f"{BASE_URL}/api/enterprise/workspaces", json=test_workspace_data)
        assert response.status_code == 201
        data = response.json()
        assert "workspace_id" in data
        assert data["workspace_id"] is not None
    
    def test_list_workspaces(self):
        """Test listing all workspaces"""
        response = requests.get(f"{BASE_URL}/api/enterprise/workspaces")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) > 0
    
    def test_get_workspace_details(self, workspace_id):
        """Test getting workspace details"""
        response = requests.get(f"{BASE_URL}/api/enterprise/workspaces/{workspace_id}")
        assert response.status_code == 200
        data = response.json()
        assert data["workspace_id"] == workspace_id
        assert "name" in data
        assert "status" in data
    
    def test_update_workspace(self, workspace_id):
        """Test updating workspace"""
        update_data = {"name": "Updated Workspace Name"}
        response = requests.patch(
            f"{BASE_URL}/api/enterprise/workspaces/{workspace_id}",
            json=update_data
        )
        assert response.status_code == 200
        
        # Verify update
        response = requests.get(f"{BASE_URL}/api/enterprise/workspaces/{workspace_id}")
        assert response.json()["name"] == update_data["name"]
    
    def test_get_workspace_teams(self, workspace_id):
        """Test getting teams in workspace"""
        response = requests.get(f"{BASE_URL}/api/enterprise/workspaces/{workspace_id}/teams")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
    
    def test_delete_workspace(self):
        """Test workspace deletion"""
        # Create a workspace to delete
        response = requests.post(f"{BASE_URL}/api/enterprise/workspaces", json=test_workspace_data)
        workspace_id = response.json()["workspace_id"]
        
        # Delete it
        response = requests.delete(f"{BASE_URL}/api/enterprise/workspaces/{workspace_id}")
        assert response.status_code == 200


class TestEnterpriseTeams:
    """Test team CRUD operations and membership"""
    
    @pytest.fixture(scope="class")
    def workspace_id(self):
        """Create workspace for teams"""
        response = requests.post(f"{BASE_URL}/api/enterprise/workspaces", json=test_workspace_data)
        return response.json()["workspace_id"]
    
    @pytest.fixture(scope="class")
    def team_id(self, workspace_id):
        """Create a team for testing"""
        team_data = {**test_team_data, "workspace_id": workspace_id}
        response = requests.post(f"{BASE_URL}/api/enterprise/teams", json=team_data)
        assert response.status_code == 201
        return response.json()["team_id"]
    
    def test_create_team(self, workspace_id):
        """Test team creation"""
        team_data = {**test_team_data, "workspace_id": workspace_id}
        response = requests.post(f"{BASE_URL}/api/enterprise/teams", json=team_data)
        assert response.status_code == 201
        data = response.json()
        assert "team_id" in data
    
    def test_list_teams(self):
        """Test listing all teams"""
        response = requests.get(f"{BASE_URL}/api/enterprise/teams")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
    
    def test_list_teams_by_workspace(self, workspace_id):
        """Test filtering teams by workspace"""
        response = requests.get(f"{BASE_URL}/api/enterprise/teams?workspace_id={workspace_id}")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        # All teams should belong to the workspace
        for team in data:
            assert team["workspace_id"] == workspace_id
    
    def test_get_team_details(self, team_id):
        """Test getting team details"""
        response = requests.get(f"{BASE_URL}/api/enterprise/teams/{team_id}")
        assert response.status_code == 200
        data = response.json()
        assert data["team_id"] == team_id
        assert "members" in data
    
    def test_update_team(self, team_id):
        """Test updating team"""
        update_data = {"name": "Updated Team Name"}
        response = requests.patch(f"{BASE_URL}/api/enterprise/teams/{team_id}", json=update_data)
        assert response.status_code == 200
    
    def test_add_user_to_team(self, team_id, workspace_id):
        """Test adding user to team"""
        # First create a user
        user_data = {**test_user_data, "workspace_id": workspace_id}
        auth_response = requests.post(f"{BASE_URL}/api/auth/register", json=user_data)
        assert auth_response.status_code == 200
        
        token = auth_response.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}
        
        # Get user ID
        me_response = requests.get(f"{BASE_URL}/api/auth/me", headers=headers)
        user_id = me_response.json()["id"]
        
        # Add user to team
        response = requests.post(f"{BASE_URL}/api/enterprise/teams/{team_id}/users/{user_id}")
        assert response.status_code == 200
        
        # Verify user is in team
        team_response = requests.get(f"{BASE_URL}/api/enterprise/teams/{team_id}")
        members = team_response.json()["members"]
        member_ids = [m["user_id"] for m in members]
        assert user_id in member_ids
    
    def test_remove_user_from_team(self, team_id, workspace_id):
        """Test removing user from team"""
        # Create and add user
        user_data = {**test_user_data, "workspace_id": workspace_id}
        auth_response = requests.post(f"{BASE_URL}/api/auth/register", json=user_data)
        token = auth_response.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}
        me_response = requests.get(f"{BASE_URL}/api/auth/me", headers=headers)
        user_id = me_response.json()["id"]
        
        requests.post(f"{BASE_URL}/api/enterprise/teams/{team_id}/users/{user_id}")
        
        # Remove user
        response = requests.delete(f"{BASE_URL}/api/enterprise/teams/{team_id}/users/{user_id}")
        assert response.status_code == 200
    
    def test_delete_team(self, workspace_id):
        """Test team deletion"""
        # Create a team to delete
        team_data = {**test_team_data, "workspace_id": workspace_id}
        response = requests.post(f"{BASE_URL}/api/enterprise/teams", json=team_data)
        team_id = response.json()["team_id"]
        
        # Delete it
        response = requests.delete(f"{BASE_URL}/api/enterprise/teams/{team_id}")
        assert response.status_code == 200


class TestEnterpriseUsers:
    """Test user management operations"""
    
    @pytest.fixture(scope="class")
    def workspace_id(self):
        """Create workspace for users"""
        response = requests.post(f"{BASE_URL}/api/enterprise/workspaces", json=test_workspace_data)
        return response.json()["workspace_id"]
    
    @pytest.fixture(scope="class")
    def user_credentials(self, workspace_id):
        """Create a user and return credentials"""
        user_data = {**test_user_data, "workspace_id": workspace_id}
        response = requests.post(f"{BASE_URL}/api/auth/register", json=user_data)
        assert response.status_code == 200
        token = response.json()["access_token"]
        
        headers = {"Authorization": f"Bearer {token}"}
        me_response = requests.get(f"{BASE_URL}/api/auth/me", headers=headers)
        user_id = me_response.json()["id"]
        
        return {"user_id": user_id, "token": token}
    
    def test_list_users(self):
        """Test listing all users"""
        response = requests.get(f"{BASE_URL}/api/enterprise/users")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
    
    def test_list_users_by_workspace(self, workspace_id):
        """Test filtering users by workspace"""
        response = requests.get(f"{BASE_URL}/api/enterprise/users?workspace_id={workspace_id}")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
    
    def test_get_user_details(self, user_credentials):
        """Test getting user details"""
        user_id = user_credentials["user_id"]
        response = requests.get(f"{BASE_URL}/api/enterprise/users/{user_id}")
        assert response.status_code == 200
        data = response.json()
        assert data["user_id"] == user_id
        assert "email" in data
        assert "teams" in data
    
    def test_update_user(self, user_credentials):
        """Test updating user"""
        user_id = user_credentials["user_id"]
        update_data = {"first_name": "Updated"}
        response = requests.patch(f"{BASE_URL}/api/enterprise/users/{user_id}", json=update_data)
        assert response.status_code == 200
    
    def test_get_user_teams(self, user_credentials, workspace_id):
        """Test getting user's teams"""
        user_id = user_credentials["user_id"]
        
        # Create a team and add user
        team_data = {**test_team_data, "workspace_id": workspace_id}
        team_response = requests.post(f"{BASE_URL}/api/enterprise/teams", json=team_data)
        team_id = team_response.json()["team_id"]
        
        requests.post(f"{BASE_URL}/api/enterprise/teams/{team_id}/users/{user_id}")
        
        # Get user's teams
        response = requests.get(f"{BASE_URL}/api/enterprise/users/{user_id}/teams")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        team_ids = [t["team_id"] for t in data]
        assert team_id in team_ids
    
    def test_deactivate_user(self, workspace_id):
        """Test user deactivation"""
        # Create a user to deactivate
        user_data = {**test_user_data, "workspace_id": workspace_id}
        response = requests.post(f"{BASE_URL}/api/auth/register", json=user_data)
        token = response.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}
        me_response = requests.get(f"{BASE_URL}/api/auth/me", headers=headers)
        user_id = me_response.json()["id"]
        
        # Deactivate
        response = requests.delete(f"{BASE_URL}/api/enterprise/users/{user_id}")
        assert response.status_code == 200


class TestDataPersistence:
    """Test that data persists across requests"""
    
    def test_workspace_persistence(self):
        """Verify workspace data persists"""
        # Create workspace
        response = requests.post(f"{BASE_URL}/api/enterprise/workspaces", json=test_workspace_data)
        workspace_id = response.json()["workspace_id"]
        
        # Retrieve it multiple times
        for _ in range(3):
            response = requests.get(f"{BASE_URL}/api/enterprise/workspaces/{workspace_id}")
            assert response.status_code == 200
            assert response.json()["workspace_id"] == workspace_id
    
    def test_team_membership_persistence(self):
        """Verify team membership persists"""
        # Create workspace, team, and user
        ws_response = requests.post(f"{BASE_URL}/api/enterprise/workspaces", json=test_workspace_data)
        workspace_id = ws_response.json()["workspace_id"]
        
        team_data = {**test_team_data, "workspace_id": workspace_id}
        team_response = requests.post(f"{BASE_URL}/api/enterprise/teams", json=team_data)
        team_id = team_response.json()["team_id"]
        
        user_data = {**test_user_data, "workspace_id": workspace_id}
        auth_response = requests.post(f"{BASE_URL}/api/auth/register", json=user_data)
        token = auth_response.json()["access_token"]
        me_response = requests.get(f"{BASE_URL}/api/auth/me", headers={"Authorization": f"Bearer {token}"})
        user_id = me_response.json()["id"]
        
        # Add user to team
        requests.post(f"{BASE_URL}/api/enterprise/teams/{team_id}/users/{user_id}")
        
        # Verify membership persists
        for _ in range(3):
            response = requests.get(f"{BASE_URL}/api/enterprise/teams/{team_id}")
            members = response.json()["members"]
            member_ids = [m["user_id"] for m in members]
            assert user_id in member_ids


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
