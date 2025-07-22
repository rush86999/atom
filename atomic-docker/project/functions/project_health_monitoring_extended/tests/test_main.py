import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock

# It's important to set up the path correctly so that the app can be imported
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from main import app

client = TestClient(app)

@pytest.fixture
def mock_get_trello_data():
    with patch('main.get_trello_data') as mock:
        yield mock

@pytest.fixture
def mock_get_git_data():
    with patch('main.get_git_data') as mock:
        yield mock

@pytest.fixture
def mock_get_slack_data():
    with patch('main.get_slack_data') as mock:
        yield mock

@pytest.fixture
def mock_get_google_calendar_data():
    with patch('main.get_google_calendar_data') as mock:
        yield mock

@pytest.fixture
def mock_calculate_project_health_score():
    with patch('main.calculate_project_health_score') as mock:
        yield mock

@pytest.fixture
def mock_send_alert():
    with patch('main.send_alert') as mock:
        yield mock

def test_project_health_endpoint_success(
    mock_get_trello_data,
    mock_get_git_data,
    mock_get_slack_data,
    mock_get_google_calendar_data,
    mock_calculate_project_health_score,
    mock_send_alert
):
    # Arrange: Set up mock return values
    mock_get_trello_data.return_value = {"overdue_cards": 1, "average_list_movement_time": 3600, "average_comment_count": 5}
    mock_get_git_data.return_value = {"commits_per_day": {"2023-01-01": 5}, "pull_request_comments": 10, "lines_of_code_changed": 500}
    mock_get_slack_data.return_value = {"average_sentiment": 0.5}
    mock_get_google_calendar_data.return_value = {"number_of_meetings": 5, "total_meeting_length": 7200}
    mock_calculate_project_health_score.return_value = 95

    payload = {
        "trello_board_id": "test_board",
        "git_repo_path": "/path/to/repo",
        "github_repo_name": "owner/repo",
        "slack_channel_id": "C12345",
        "google_calendar_id": "primary",
        "project_manager_slack_id": "U12345"
    }

    # Act: Call the endpoint
    response = client.post("/project-health/", json=payload)

    # Assert: Check the response and that mocks were called
    assert response.status_code == 200
    assert response.json() == {"project_health_score": 95}
    mock_get_trello_data.assert_called_once_with("test_board")
    mock_get_git_data.assert_called_once_with("/path/to/repo", "owner/repo")
    mock_get_slack_data.assert_called_once_with("C12345")
    mock_get_google_calendar_data.assert_called_once_with("primary")
    mock_calculate_project_health_score.assert_called_once()
    mock_send_alert.assert_called_once()

def test_project_health_endpoint_integration_error(
    mock_get_trello_data,
    mock_get_git_data,
    mock_get_slack_data,
    mock_get_google_calendar_data,
):
    # Arrange: Simulate an error from one of the integrations
    mock_get_trello_data.return_value = {"error": "Failed to connect to Trello"}
    mock_get_git_data.return_value = {"commits_per_day": {}, "pull_request_comments": 0, "lines_of_code_changed": 0}
    mock_get_slack_data.return_value = {"average_sentiment": 0}
    mock_get_google_calendar_data.return_value = {"number_of_meetings": 0, "total_meeting_length": 0}


    payload = {
        "trello_board_id": "test_board_error",
        "git_repo_path": "/path/to/repo",
        "github_repo_name": "owner/repo",
        "slack_channel_id": "C12345",
        "google_calendar_id": "primary",
        "project_manager_slack_id": "U12345"
    }

    # Act
    response = client.post("/project-health/", json=payload)

    # Assert
    assert response.status_code == 500
    assert "Error fetching data" in response.json()["detail"]

def test_project_health_endpoint_unexpected_error(
    mock_get_trello_data
):
    # Arrange: Simulate an unexpected exception
    mock_get_trello_data.side_effect = Exception("A random error occurred")

    payload = {
        "trello_board_id": "test_board_unexpected_error",
        "git_repo_path": "/path/to/repo",
        "github_repo_name": "owner/repo",
        "slack_channel_id": "C12345",
        "google_calendar_id": "primary",
        "project_manager_slack_id": "U12345"
    }

    # Act
    response = client.post("/project-health/", json=payload)

    # Assert
    assert response.status_code == 500
    assert "An unexpected error occurred" in response.json()["detail"]
