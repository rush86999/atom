import sys
import os
import unittest
from unittest.mock import patch, MagicMock

sys.path.append(os.path.dirname(os.path.realpath(__file__)))
from main import personalized_learning_plan

class TestPersonalizedLearningAssistant(unittest.TestCase):

    def test_personalized_learning_plan(self):
        with patch('main.generate_personalized_learning_plan') as mock_generate_personalized_learning_plan:
            mock_generate_personalized_learning_plan.return_value = "personalized learning plan"

            response = personalized_learning_plan(
                coursera_user_id="test",
                udemy_user_id="test",
                edx_user_id="test",
                pocket_consumer_key="test",
                pocket_access_token="test",
                instapaper_consumer_key="test",
                instapaper_consumer_secret="test",
                instapaper_oauth_token="test",
                instapaper_oauth_token_secret="test",
                google_calendar_id="test",
                notion_database_id="test",
                learning_duration_minutes=60,
            )

            self.assertEqual(response, "personalized learning plan")

if __name__ == '__main__':
    unittest.main()
