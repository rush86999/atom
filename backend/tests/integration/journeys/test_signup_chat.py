"""
Journey 1: New user signup → get profile → first chat message.

Tests the full signup-to-first-use path that every new user takes.
Surfaces bugs in: registration (role, status), token issuance, and the
chat endpoint contract.
"""

import pytest


class TestSignupToChat:

    def test_register_returns_success(self, real_auth_client, unique_email):
        """Registration returns a success response (201 from enterprise auth)."""
        resp = real_auth_client.post("/api/auth/register", json={
            "email": unique_email,
            "password": "TestPass123!",
            "first_name": "Journey",
            "last_name": "Tester",
        })
        assert resp.status_code in (200, 201), f"Register failed: {resp.text}"
        data = resp.json()
        assert data.get("success") is True or data.get("access_token"), \
            f"Register response missing success or access_token: {data}"

    def test_get_profile_after_register(self, registered_user):
        """The /me endpoint returns the user's profile with workspace_id set."""
        client, email, password, token = registered_user
        resp = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 200, f"/me failed: {resp.text}"
        data = resp.json().get("data", resp.json())
        assert data["email"] == email
        assert data.get("workspace_id"), "workspace_id should be set after register"

    def test_login_after_register(self, registered_user):
        """A registered user can log in with their credentials."""
        client, email, password, token = registered_user
        resp = client.post("/api/auth/login", json={
            "username": email,
            "password": password,
        })
        assert resp.status_code == 200, f"Login failed: {resp.text}"
        assert resp.json().get("access_token"), "No token from login"

    def test_first_chat_message(self, registered_user):
        """After registering, the user can send their first chat message."""
        client, email, password, token = registered_user
        resp = client.post("/api/chat/message", json={
            "message": "Hello, what can you help me with?",
            "user_id": "default_user",
            "session_id": "new",
            "context": {},
        }, headers={"Authorization": f"Bearer {token}"})
        # The response should be 200 with a message (even if it's the
        # no_llm_provider sentinel — that's still a valid response shape).
        assert resp.status_code == 200, f"Chat failed: {resp.text}"
        data = resp.json()
        # If no provider is configured, we get the structured error — that's fine.
        # What we DON'T want is a 500 or a crash.
        if data.get("error_code") == "no_llm_provider":
            pytest.skip("No LLM provider configured — no_llm_provider sentinel is correct behavior")
        assert data.get("success") is True or data.get("message"), \
            f"Unexpected response: {data}"
