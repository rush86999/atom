import pytest
from unittest.mock import patch, MagicMock
from datetime import datetime, timedelta

# Add project root to path to allow module imports
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from trello_integration import get_trello_data, TrelloManager
from git_integration import get_git_data, GitManager
from slack_integration import get_slack_data, SlackManager
from google_calendar_integration import get_google_calendar_data, GoogleCalendarManager
from project_health_score import calculate_project_health_score

# Trello Tests
@patch('trello_integration.TrelloManager')
def test_get_trello_data(MockTrelloManager):
    mock_manager = MockTrelloManager.return_value
    mock_manager.get_board_data.return_value = {
        "cards": [
            {"id": "1", "due": (datetime.now() + timedelta(days=1)).isoformat(), "name": "Card 1"},
            {"id": "2", "due": (datetime.now() - timedelta(days=1)).isoformat(), "name": "Card 2"}, # Overdue
        ]
    }
    mock_manager.get_card_actions.side_effect = [
        [], # No list movements for card 1
        [{"date": (datetime.now() - timedelta(hours=1)).isoformat()}], # 1 comment for card 1
        [{"date": (datetime.now() - timedelta(days=2)).isoformat()}, {"date": (datetime.now() - timedelta(days=3)).isoformat()}], # list movements for card 2
        [], # No comments for card 2
    ]

    with patch.dict(os.environ, {"TRELLO_API_KEY": "fake_key", "TRELLO_TOKEN": "fake_token"}):
        data = get_trello_data("some_board_id")

    assert data["overdue_cards"] == 1
    assert data["average_comment_count"] == 0.5
    assert data["average_list_movement_time"] > 0

# Git Tests
@patch('git_integration.GitManager')
def test_get_git_data(MockGitManager):
    mock_manager = MockGitManager.return_value
    mock_manager.get_commits_per_day.return_value = {"2023-01-10": 3}
    mock_manager.get_lines_of_code_changed.return_value = 250
    mock_manager.get_pull_request_comments.return_value = 8

    data = get_git_data("/fake/path", "owner/repo")

    assert data["commits_per_day"] == {"2023-01-10": 3}
    assert data["lines_of_code_changed"] == 250
    assert data["pull_request_comments"] == 8

# Slack Tests
@patch('slack_integration.SlackManager')
def test_get_slack_data(MockSlackManager):
    mock_manager = MockSlackManager.return_value
    mock_manager.get_channel_history.return_value = [
        {"text": "This is a great update!"},
        {"text": "I have some concerns about this."}
    ]
    # Let's assume the sentiment analyzer gives scores for these
    mock_manager.calculate_average_sentiment.return_value = 0.123

    with patch.dict(os.environ, {"SLACK_API_KEY": "fake_token"}):
        data = get_slack_data("C12345")

    assert "average_sentiment" in data
    assert data["average_sentiment"] == 0.123


# Google Calendar Tests
@patch('google_calendar_integration.GoogleCalendarManager')
def test_get_google_calendar_data(MockGoogleCalendarManager):
    mock_manager = MockGoogleCalendarManager.return_value
    mock_manager.get_upcoming_events.return_value = [
        {
            "start": {"dateTime": (datetime.now() + timedelta(hours=1)).isoformat()},
            "end": {"dateTime": (datetime.now() + timedelta(hours=2)).isoformat()}
        }
    ]

    data = get_google_calendar_data("primary")

    assert data["number_of_meetings"] == 1
    assert data["total_meeting_length"] == pytest.approx(3600, rel=1e-5)


# Project Health Score Calculation Test
def test_calculate_project_health_score():
    trello_data = {"overdue_cards": 10, "average_list_movement_time": 90000, "average_comment_count": 0.5}
    git_data = {"commits_per_day": {}, "pull_request_comments": 2, "lines_of_code_changed": 50}
    slack_data = {"average_sentiment": -0.5}
    gcal_data = {"number_of_meetings": 20, "total_meeting_length": 80000}

    score = calculate_project_health_score(trello_data, git_data, slack_data, gcal_data)

    # This score should be low based on the poor metrics
    assert score < 50
