import unittest
from unittest.mock import MagicMock
import sys
import os

# Add the functions directory to the path to allow imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from project_health_monitoring_extended.main import app
from fastapi.testclient import TestClient
from project_health_monitoring_extended.dependencies import (
    get_get_trello_data,
    get_get_git_data,
    get_get_slack_data,
    get_get_google_calendar_data,
    get_calculate_project_health_score,
    get_send_alert,
)

class ProjectHealthMonitoringTests(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)

    def test_project_health(self):
        # Mock the dependencies
        mock_get_trello_data = MagicMock(return_value={
            "overdue_cards": 0,
            "average_list_movement_time": 0,
            "average_comment_count": 0,
        })
        mock_get_git_data = MagicMock(return_value={
            "commits_per_day": {},
            "pull_request_comments": 0,
            "lines_of_code_changed": 0,
        })
        mock_get_slack_data = MagicMock(return_value={"average_sentiment": 0})
        mock_get_google_calendar_data = MagicMock(return_value={
            "meeting_count": 0,
            "average_meeting_duration": 0,
        })
        mock_calculate_project_health_score = MagicMock(return_value=100)
        mock_send_alert = MagicMock()

        app.dependency_overrides[get_get_trello_data] = lambda: mock_get_trello_data
        app.dependency_overrides[get_get_git_data] = lambda: mock_get_git_data
        app.dependency_overrides[get_get_slack_data] = lambda: mock_get_slack_data
        app.dependency_overrides[get_get_google_calendar_data] = lambda: mock_get_google_calendar_data
        app.dependency_overrides[get_calculate_project_health_score] = lambda: mock_calculate_project_health_score
        app.dependency_overrides[get_send_alert] = lambda: mock_send_alert

        response = self.client.post(
            "/project-health",
            params={
                "trello_board_id": "test",
                "git_repo_path": "test",
                "slack_channel_id": "test",
                "google_calendar_id": "test",
                "project_manager_slack_id": "test",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"project_health_score": 100})
        mock_get_trello_data.assert_called_once_with("test")
        mock_get_git_data.assert_called_once_with("test")
        mock_get_slack_data.assert_called_once_with("test")
        mock_get_google_calendar_data.assert_called_once_with("test")
        mock_calculate_project_health_score.assert_called_once()
        mock_send_alert.assert_called_once()

if __name__ == "__main__":
    unittest.main()
