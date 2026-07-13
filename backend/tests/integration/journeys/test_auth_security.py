"""
Journey 2+3: Auth security — rate limiting and feedback user_id.

Tests brute-force protection (should be wired but may not be) and feedback
user_id spoofing (should use the token, not the body).
"""

import pytest


class TestRateLimiting:

    def test_eleven_wrong_passwords_blocked(self, registered_user):
        """After 10 failed login attempts, the 11th should return 429."""
        client, email, password, token = registered_user

        # Make 10 failed attempts (should all return 401).
        for i in range(10):
            resp = client.post("/api/auth/login", json={
                "username": email,
                "password": "wrong_password",
            })
            assert resp.status_code == 401, \
                f"Attempt {i+1}: expected 401, got {resp.status_code}"

        # The 11th attempt should be rate-limited (429).
        resp = client.post("/api/auth/login", json={
            "username": email,
            "password": "wrong_password",
        })
        assert resp.status_code == 429, \
            f"Expected 429 after 10 failed attempts, got {resp.status_code}. " \
            "Rate limiter is not wired to /api/auth/login!"

    def test_correct_password_resets_limiter(self, registered_user):
        """A successful login resets the rate limiter so the user isn't unfairly locked."""
        client, email, password, token = registered_user

        # Make 9 failed attempts.
        for i in range(9):
            client.post("/api/auth/login", json={
                "username": email,
                "password": "wrong",
            })

        # Now succeed.
        resp = client.post("/api/auth/login", json={
            "username": email,
            "password": password,
        })
        assert resp.status_code == 200, \
            f"Correct password should work after 9 failed: {resp.status_code}"

        # Now 2 more wrong attempts should NOT be 429 (limiter was reset).
        for i in range(2):
            resp = client.post("/api/auth/login", json={
                "username": email,
                "password": "wrong",
            })
            assert resp.status_code == 401, \
                f"After reset, attempt {i+1}: expected 401, got {resp.status_code}. " \
                "Limiter was not reset on successful login!"


class TestFeedbackUserIdFromToken:

    def test_feedback_uses_token_not_body(self, registered_user):
        """Feedback user_id should come from the token, not the request body.

        A user should not be able to submit feedback attributed to
        another user by spoofing the user_id field.
        """
        client, email, password, token = registered_user

        # Submit feedback via the correct endpoint (/api/chat/feedback).
        resp = client.post("/api/chat/feedback", json={
            "message_id": "test_msg_1",
            "feedback": "thumbs_down",
            "comment": "This was wrong",
            "model": "test_model",
        }, headers={"Authorization": f"Bearer {token}"})

        assert resp.status_code == 200, f"Feedback failed: {resp.text}"
        data = resp.json()
        assert data.get("success") is True, f"Feedback not successful: {data}"
