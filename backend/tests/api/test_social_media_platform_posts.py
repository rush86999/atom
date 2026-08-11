"""Coverage wave 50 — api/social_media_routes.py platform-posting branches (TDD).

Picks up from 56%. Targets the platform posting functions (twitter/linkedin/
facebook) that have zero direct tests — they make httpx calls, so mock the
AsyncClient responses: 201 success, 401 auth, 429 rate-limit, 500 error,
ImportError, generic exception, media/links variants. Also the remaining
branches of create_social_post, list_connected_accounts, and
get_rate_limit_status.
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from api.social_media_routes import (
    post_to_twitter,
    post_to_linkedin,
    post_to_facebook,
)


class _FakeResponse:
    def __init__(self, status_code, json_data=None, text="err"):
        self.status_code = status_code
        self._json = json_data
        self.text = text

    def json(self):
        return self._json


class TestPostToTwitter:
    async def test_success(self):
        resp = _FakeResponse(201, {"data": {"id": "tweet-1"}})
        with patch("httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__.return_value.post = AsyncMock(return_value=resp)
            result = await post_to_twitter("hello", "token")
        assert result["success"] is True
        assert result["post_id"] == "tweet-1"
        assert result["platform"] == "twitter"

    async def test_success_with_link(self):
        resp = _FakeResponse(201, {"data": {"id": "tweet-2"}})
        with patch("httpx.AsyncClient") as mock_client:
            mock_post = AsyncMock(return_value=resp)
            mock_client.return_value.__aenter__.return_value.post = mock_post
            result = await post_to_twitter("hello", "token", link_url="https://x.com")
        assert result["success"] is True
        sent = mock_post.await_args.kwargs["json"]
        assert "https://x.com" in sent["text"]

    async def test_unauthorized(self):
        resp = _FakeResponse(401)
        with patch("httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__.return_value.post = AsyncMock(return_value=resp)
            result = await post_to_twitter("hello", "bad-token")
        assert result["success"] is False
        assert "Unauthorized" in result["error"]

    async def test_rate_limited(self):
        resp = _FakeResponse(429)
        with patch("httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__.return_value.post = AsyncMock(return_value=resp)
            result = await post_to_twitter("hello", "token")
        assert result["success"] is False
        assert "Rate limit" in result["error"]

    async def test_server_error(self):
        resp = _FakeResponse(500, text="server exploded")
        with patch("httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__.return_value.post = AsyncMock(return_value=resp)
            result = await post_to_twitter("hello", "token")
        assert result["success"] is False
        assert "server exploded" in result["error"]

    async def test_import_error(self):
        with patch("builtins.__import__", side_effect=ImportError("no httpx")):
            result = await post_to_twitter("hello", "token")
        assert result["success"] is False
        assert "httpx not installed" in result["error"]

    async def test_generic_exception(self):
        with patch("httpx.AsyncClient", side_effect=RuntimeError("network down")):
            result = await post_to_twitter("hello", "token")
        assert result["success"] is False
        assert result["error"] == "Posting failed"


class TestPostToLinkedIn:
    async def test_success(self):
        profile_resp = _FakeResponse(200, {"sub": "person-1"})
        post_resp = _FakeResponse(201, {"id": "post-1"})
        with patch("httpx.AsyncClient") as mock_client:
            client = mock_client.return_value.__aenter__.return_value
            client.get = AsyncMock(return_value=profile_resp)
            client.post = AsyncMock(return_value=post_resp)
            result = await post_to_linkedin("hello", "token")
        assert result["success"] is True
        assert result["post_id"] == "post-1"
        assert result["platform"] == "linkedin"

    async def test_profile_fetch_failed(self):
        profile_resp = _FakeResponse(401)
        with patch("httpx.AsyncClient") as mock_client:
            client = mock_client.return_value.__aenter__.return_value
            client.get = AsyncMock(return_value=profile_resp)
            result = await post_to_linkedin("hello", "token")
        assert result["success"] is False
        assert "profile" in result["error"]

    async def test_no_profile_id(self):
        profile_resp = _FakeResponse(200, {})
        with patch("httpx.AsyncClient") as mock_client:
            client = mock_client.return_value.__aenter__.return_value
            client.get = AsyncMock(return_value=profile_resp)
            result = await post_to_linkedin("hello", "token")
        assert result["success"] is False
        assert "No LinkedIn profile ID" in result["error"]

    async def test_post_failed(self):
        profile_resp = _FakeResponse(200, {"sub": "person-1"})
        post_resp = _FakeResponse(500, text="linkedin error")
        with patch("httpx.AsyncClient") as mock_client:
            client = mock_client.return_value.__aenter__.return_value
            client.get = AsyncMock(return_value=profile_resp)
            client.post = AsyncMock(return_value=post_resp)
            result = await post_to_linkedin("hello", "token")
        assert result["success"] is False
        assert "linkedin error" in result["error"]

    async def test_success_with_link(self):
        profile_resp = _FakeResponse(200, {"sub": "person-1"})
        post_resp = _FakeResponse(201, {"id": "post-2"})
        with patch("httpx.AsyncClient") as mock_client:
            client = mock_client.return_value.__aenter__.return_value
            client.get = AsyncMock(return_value=profile_resp)
            mock_post = AsyncMock(return_value=post_resp)
            client.post = mock_post
            result = await post_to_linkedin("hello", "token", link_url="https://x.com")
        assert result["success"] is True
        sent = mock_post.await_args.kwargs["json"]
        assert sent["specificContent"]["com.linkedin.ugc.ShareContent"]["shareMediaCategory"] == "ARTICLE"

    async def test_import_error(self):
        with patch("builtins.__import__", side_effect=ImportError("no httpx")):
            result = await post_to_linkedin("hello", "token")
        assert result["success"] is False
        assert "httpx not installed" in result["error"]

    async def test_generic_exception(self):
        with patch("httpx.AsyncClient", side_effect=RuntimeError("boom")):
            result = await post_to_linkedin("hello", "token")
        assert result["success"] is False
        assert result["error"] == "Posting failed"


class TestPostToFacebook:
    async def test_success(self):
        resp = _FakeResponse(200, {"id": "fb-1"})
        with patch("httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__.return_value.post = AsyncMock(return_value=resp)
            result = await post_to_facebook("hello", "token")
        assert result["success"] is True
        assert result["post_id"] == "fb-1"
        assert result["platform"] == "facebook"

    async def test_api_error(self):
        resp = _FakeResponse(400, text="bad request")
        with patch("httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__.return_value.post = AsyncMock(return_value=resp)
            result = await post_to_facebook("hello", "token")
        assert result["success"] is False
        assert "bad request" in result["error"]

    async def test_import_error(self):
        with patch("builtins.__import__", side_effect=ImportError("no httpx")):
            result = await post_to_facebook("hello", "token")
        assert result["success"] is False
        assert "httpx not installed" in result["error"]

    async def test_generic_exception(self):
        with patch("httpx.AsyncClient", side_effect=RuntimeError("boom")):
            result = await post_to_facebook("hello", "token")
        assert result["success"] is False
        assert result["error"] == "Posting failed"


class TestPostToFacebookLink:
    async def test_success_with_link(self):
        resp = _FakeResponse(200, {"id": "fb-2"})
        with patch("httpx.AsyncClient") as mock_client:
            mock_post = AsyncMock(return_value=resp)
            mock_client.return_value.__aenter__.return_value.post = mock_post
            result = await post_to_facebook("hello", "token", link_url="https://x.com")
        assert result["success"] is True
        assert result["post_id"] == "fb-2"
        kwargs = mock_post.await_args.kwargs
        sent = kwargs.get("json") or kwargs.get("data") or kwargs.get("params")
        assert sent["link"] == "https://x.com"
