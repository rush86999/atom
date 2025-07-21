import sys
import os
import unittest
from unittest.mock import patch, MagicMock

sys.path.append(os.path.dirname(os.path.realpath(__file__)))
from trello_integration import get_trello_data
from git_integration import get_git_data
from slack_integration import get_slack_data
from google_calendar_integration import get_google_calendar_data
import os
from datetime import datetime

class TestProjectHealthMonitoring(unittest.TestCase):

    @patch('trello_integration.requests.get')
    @patch.dict(os.environ, {"TRELLO_API_KEY": "test", "TRELLO_TOKEN": "test"})
    def test_get_trello_data(self, mock_get):
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "cards": [
                {"due": "2022-01-01T00:00:00.000Z", "id": "1"},
                {"due": None, "id": "2"}
            ],
            "lists": []
        }

        mock_actions_response = MagicMock()
        mock_actions_response.json.return_value = []

        mock_get.side_effect = [mock_response, mock_actions_response, mock_actions_response, mock_actions_response, mock_actions_response]

        trello_data = get_trello_data("some_board_id")
        self.assertEqual(trello_data["overdue_cards"], 1)

    @patch('git_integration.Repo')
    @patch('os.path.isdir')
    def test_get_git_data(self, mock_isdir, mock_repo):
        mock_isdir.return_value = True
        mock_commit = MagicMock()
        mock_commit.authored_datetime.date.return_value = datetime.now().date()
        mock_commit.stats.total = {'lines': 10}
        mock_repo.return_value.iter_commits.return_value = [mock_commit]
        git_data = get_git_data("some/repo/path")
        self.assertEqual(git_data["commits_today"], 1)
        self.assertEqual(git_data["lines_of_code_changed"], 10)

    @patch('slack_integration.WebClient')
    @patch.dict(os.environ, {"SLACK_API_KEY": "test"})
    def test_get_slack_data(self, mock_client):
        mock_response = {
            "messages": [
                {"text": "This is a great message!"},
                {"text": "This is a bad message."}
            ]
        }
        mock_client.return_value.conversations_history.return_value = mock_response
        slack_data = get_slack_data("some_channel_id")
        self.assertAlmostEqual(slack_data["average_sentiment"], 0.0, delta=0.1)

    @patch('google_calendar_integration.build')
    @patch.dict(os.environ, {
        "GOOGLE_TOKEN": "test",
        "GOOGLE_REFRESH_TOKEN": "test",
        "GOOGLE_TOKEN_URI": "test",
        "GOOGLE_CLIENT_ID": "test",
        "GOOGLE_CLIENT_SECRET": "test",
    })
    def test_get_google_calendar_data(self, mock_build):
        mock_service = MagicMock()
        mock_events = {
            "items": [
                {
                    "start": {"dateTime": "2022-01-01T10:00:00.000Z"},
                    "end": {"dateTime": "2022-01-01T11:00:00.000Z"}
                }
            ]
        }
        mock_service.events.return_value.list.return_value.execute.return_value = mock_events
        mock_build.return_value = mock_service
        calendar_data = get_google_calendar_data("some_calendar_id")
        self.assertEqual(calendar_data["meeting_count"], 1)
        self.assertEqual(calendar_data["total_meeting_duration"], 3600)

if __name__ == '__main__':
    unittest.main()
