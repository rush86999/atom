import pytest
import requests
from config.test_config import TestConfig

class TestScheduling:
    def setup_method(self):
        self.base_url = f"{TestConfig.BACKEND_URL}/api/v1"
        self.calendar_url = f"{self.base_url}/calendar"

    def test_get_events(self):
        """Test fetching calendar events"""
        response = requests.get(f"{self.calendar_url}/events")
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert isinstance(data["events"], list)

    def test_create_event(self):
        """Test creating a new calendar event"""
        event_data = {
            "title": "E2E Test Event",
            "start": "2025-11-20T10:00:00",
            "end": "2025-11-20T11:00:00",
            "allDay": False,
            "description": "Created by E2E test"
        }
        response = requests.post(f"{self.calendar_url}/events", json=event_data)
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["event"]["title"] == event_data["title"]
        assert "id" in data["event"]
        
        # Cleanup
        event_id = data["event"]["id"]
        requests.delete(f"{self.calendar_url}/events/{event_id}")

    def test_update_event(self):
        """Test updating a calendar event"""
        # Create first
        event_data = {
            "title": "Event to Update",
            "start": "2025-11-21T10:00:00",
            "end": "2025-11-21T11:00:00"
        }
        create_res = requests.post(f"{self.calendar_url}/events", json=event_data)
        event_id = create_res.json()["event"]["id"]
        
        # Update
        update_data = {"title": "Updated Event Title"}
        response = requests.put(f"{self.calendar_url}/events/{event_id}", json=update_data)
        assert response.status_code == 200
        assert response.json()["event"]["title"] == "Updated Event Title"
        
        # Cleanup
        requests.delete(f"{self.calendar_url}/events/{event_id}")

    def test_delete_event(self):
        """Test deleting a calendar event"""
        # Create first
        event_data = {
            "title": "Event to Delete",
            "start": "2025-11-22T10:00:00",
            "end": "2025-11-22T11:00:00"
        }
        create_res = requests.post(f"{self.calendar_url}/events", json=event_data)
        event_id = create_res.json()["event"]["id"]
        
        # Delete
        response = requests.delete(f"{self.calendar_url}/events/{event_id}")
        assert response.status_code == 200
        
        # Verify deletion (optional, depending on API behavior)
        # get_res = requests.get(f"{self.calendar_url}/events")
        # events = get_res.json()
        # assert not any(e['id'] == event_id for e in events)
