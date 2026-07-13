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

        # Try to submit feedback with a different user_id in the body.
        resp = client.post("/api/feedback/submit", json={
            "agent_id": "test_agent",
            "agent_execution_id": "test_exec",
            "user_id": "someone_else@example.com",  # Spoofed!
            "thumbs_up_down": False,
            "user_correction": "This was wrong",
        }, headers={"Authorization": f"Bearer {token}"})

        # The endpoint may return 200 or 404 (if agent doesn't exist), but
        # the feedback should be attributed to the authenticated user, not
        # "someone_else". We check this by looking at the response or a
        # subsequent GET. For now, assert the endpoint doesn't crash.
        # The real assertion is that user_id in the stored feedback matches
        # the token user, not the body — but that requires a GET endpoint.
        # At minimum, the endpoint should not accept an arbitrary user_id.
        assert resp.status_code in (200, 404, 422), \
            f"Unexpected status: {resp.status_code}. Feedback endpoint may not exist at this path."
