import unittest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient
from competitor_analysis.main import app, get_db_connection
from competitor_analysis.scheduler import start_scheduler

class CompetitorAnalysisTestCase(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)
        self.conn = get_db_connection()
        self.cursor = self.conn.cursor()
        self.cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS competitors (
                id INTEGER PRIMARY KEY,
                name TEXT,
                website TEXT,
                twitter_username TEXT,
                ticker TEXT
            )
            """
        )
        self.conn.commit()
        start_scheduler()

    def tearDown(self):
        self.cursor.execute("DROP TABLE competitors")
        self.conn.close()

    def test_create_competitor(self):
        response = self.client.post(
            "/competitors",
            params={
                "name": "Test Competitor",
                "website": "https://www.test.com",
                "twitter_username": "test",
                "ticker": "TEST",
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"message": "Competitor created successfully."})

    def test_get_competitors(self):
        response = self.client.get("/competitors")
        self.assertEqual(response.status_code, 200)
        self.assertIsInstance(response.json(), list)

if __name__ == "__main__":
    unittest.main()
