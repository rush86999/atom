import unittest
from unittest.mock import MagicMock
import sys
import os

# Add the functions directory to the path to allow imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from personalized_learning_assistant_extended.main import app
from fastapi.testclient import TestClient
from personalized_learning_assistant_extended.dependencies import (
    get_get_coursera_data,
    get_get_udemy_data,
    get_get_edx_data,
    get_get_pocket_data,
    get_get_instapaper_data,
    get_get_notion_data,
    get_create_user_profile,
    get_get_recommendations,
    get_schedule_learning_sessions,
)

class PersonalizedLearningAssistantTests(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)

    def test_personalized_learning_plan(self):
        # Mock the dependencies
        mock_get_coursera_data = MagicMock(return_value={"enrolled_courses": []})
        mock_get_udemy_data = MagicMock(return_value={"enrolled_courses": []})
        mock_get_edx_data = MagicMock(return_value={"enrolled_courses": []})
        mock_get_pocket_data = MagicMock(return_value={"unread_articles": []})
        mock_get_instapaper_data = MagicMock(return_value={"unread_articles": []})
        mock_get_notion_data = MagicMock(return_value={"pages": []})
        mock_create_user_profile = MagicMock(return_value={"interests": [], "knowledge": []})
        mock_get_recommendations = MagicMock(return_value={"courses": [], "articles": [], "books": []})
        mock_schedule_learning_sessions = MagicMock()

        app.dependency_overrides[get_get_coursera_data] = lambda: mock_get_coursera_data
        app.dependency_overrides[get_get_udemy_data] = lambda: mock_get_udemy_data
        app.dependency_overrides[get_get_edx_data] = lambda: mock_get_edx_data
        app.dependency_overrides[get_get_pocket_data] = lambda: mock_get_pocket_data
        app.dependency_overrides[get_get_instapaper_data] = lambda: mock_get_instapaper_data
        app.dependency_overrides[get_get_notion_data] = lambda: mock_get_notion_data
        app.dependency_overrides[get_create_user_profile] = lambda: mock_create_user_profile
        app.dependency_overrides[get_get_recommendations] = lambda: mock_get_recommendations
        app.dependency_overrides[get_schedule_learning_sessions] = lambda: mock_schedule_learning_sessions

        response = self.client.post(
            "/personalized-learning-plan",
            params={
                "coursera_user_id": "test",
                "udemy_user_id": "test",
                "edx_user_id": "test",
                "google_calendar_id": "test",
                "notion_database_id": "test",
                "learning_duration_minutes": 60,
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "success", "recommendations": {"courses": [], "articles": [], "books": []}})
        mock_get_coursera_data.assert_called_once_with("test")
        mock_get_udemy_data.assert_called_once_with("test")
        mock_get_edx_data.assert_called_once_with("test")
        mock_get_pocket_data.assert_called_once()
        mock_get_instapaper_data.assert_called_once()
        mock_get_notion_data.assert_called_once_with("test")
        mock_create_user_profile.assert_called_once()
        mock_get_recommendations.assert_called_once()
        mock_schedule_learning_sessions.assert_called_once()

if __name__ == "__main__":
    unittest.main()
