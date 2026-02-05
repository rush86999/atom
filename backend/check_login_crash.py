
import logging
import sys
import requests

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def test_login():
    url = "http://127.0.0.1:8000/api/auth/login"
    data = {"username": "admin@example.com", "password": "securePass123"}
    try:
        logger.info(f"Sending POST to {url}...")
        response = requests.post(url, data=data)
        logger.info(f"Status Code: {response.status_code}")
        with open("crash_response.txt", "w", encoding="utf-8") as f:
            f.write(response.text)
        logger.info("Response written to crash_response.txt")
    except Exception as e:
        logger.error(f"Request failed: {e}")

if __name__ == "__main__":
    test_login()
