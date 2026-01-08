import pytest
import requests
from config.test_config import TestConfig

class TestProjects:
    def setup_method(self):
        self.base_url = f"{TestConfig.BACKEND_URL}/api/v1"
        self.tasks_url = f"{self.base_url}/tasks/"  # Added trailing slash

    def test_get_tasks(self):
        """Test fetching tasks"""
        response = requests.get(self.tasks_url)
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert isinstance(data["tasks"], list)

    def test_create_task(self):
        """Test creating a new task"""
        task_data = {
            "title": "E2E Test Task",
            "status": "todo",
            "priority": "medium",
            "dueDate": "2025-12-31T23:59:59"  # Added required field
        }
        response = requests.post(self.tasks_url, json=task_data)
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["task"]["title"] == task_data["title"]
        assert "id" in data["task"]
        
        # Cleanup
        task_id = data["task"]["id"]
        requests.delete(f"{self.tasks_url}{task_id}")

    def test_update_task_status(self):
        """Test updating task status (drag and drop simulation)"""
        # Create first
        task_data = {
            "title": "Task to Move",
            "status": "todo",
            "dueDate": "2025-12-31T23:59:59"
        }
        create_res = requests.post(self.tasks_url, json=task_data)
        task_id = create_res.json()["task"]["id"]
        
        # Update status
        update_data = {"status": "in-progress"}
        response = requests.put(f"{self.tasks_url}{task_id}", json=update_data)
        assert response.status_code == 200
        assert response.json()["task"]["status"] == "in-progress"
        
        # Cleanup
        requests.delete(f"{self.tasks_url}{task_id}")

    def test_delete_task(self):
        """Test deleting a task"""
        # Create first
        task_data = {
            "title": "Task to Delete",
            "status": "todo",
            "dueDate": "2025-12-31T23:59:59"
        }
        create_res = requests.post(self.tasks_url, json=task_data)
        task_id = create_res.json()["task"]["id"]
        
        # Delete
        response = requests.delete(f"{self.tasks_url}{task_id}")
        assert response.status_code == 200
