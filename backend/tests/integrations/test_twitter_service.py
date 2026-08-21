"""
Tests for integrations/twitter_service.py and twitter_routes.py

Covers:
- Not-configured guard
- Happy path per operation (post tweet, user tweets, recent search)
- HTTP error propagation
- Basic route behaviour (status/health + endpoints when unconfigured)
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
from fastapi import HTTPException, FastAPI
from fastapi.testclient import TestClient

from integrations.twitter_service import TwitterService, twitter_configured
from integrations import twitter_routes


def make_response(status_code=200, json_data=None, content=b"json"):
    resp = MagicMock(spec=httpx.Response)
    resp.status_code = status_code
    resp.content = content
    resp.json.return_value = json_data if json_data is not None else {}
    if status_code >= 400:
        request = MagicMock()
        request.url = "https://api.twitter.com/2/test"
        resp.request = request
        resp.raise_for_status.side_effect = httpx.HTTPStatusError(
            "error", request=request, response=resp
        )
    else:
        resp.raise_for_status.return_value = None
    return resp


class TestTwitterConfiguration:
    def test_not_configured_when_env_missing(self, monkeypatch):
        monkeypatch.delenv("TWITTER_BEARER_TOKEN", raising=False)
        assert twitter_configured() is False

    def test_configured_when_env_set(self, monkeypatch):
        monkeypatch.setenv("TWITTER_BEARER_TOKEN", "tok123")
        assert twitter_configured() is True

    def test_bearer_token_from_env(self, monkeypatch):
        monkeypatch.setenv("TWITTER_BEARER_TOKEN", "tok123")
        service = TwitterService()
        assert service.bearer_token == "tok123"
        assert service._get_headers()["Authorization"] == "Bearer tok123"


class TestTwitterNotConfiguredGuard:
    async def test_operations_raise_when_not_configured(self, monkeypatch):
        monkeypatch.delenv("TWITTER_BEARER_TOKEN", raising=False)
        service = TwitterService()
        with pytest.raises(HTTPException) as exc:
            await service.post_tweet("hello")
        assert exc.value.status_code == 503


class TestTwitterHappyPaths:
    @pytest.fixture
    def service(self):
        svc = TwitterService(bearer_token="tok")
        svc.client = MagicMock()
        svc.client.request = AsyncMock()
        return svc

    async def test_post_tweet(self, service):
        service.client.request.return_value = make_response(json_data={
            "data": {"id": "123", "text": "Hello world"}
        })
        result = await service.post_tweet("Hello world")
        assert result["data"]["id"] == "123"
        call = service.client.request.call_args
        assert call.args[0] == "POST"
        assert call.args[1].endswith("/tweets")
        assert call.kwargs["json"] == {"text": "Hello world"}

    async def test_post_tweet_requires_text(self, service):
        with pytest.raises(HTTPException) as exc:
            await service.post_tweet("")
        assert exc.value.status_code == 400

    async def test_get_user_tweets(self, service):
        service.client.request.return_value = make_response(json_data={
            "data": [{"id": "1", "text": "tweet"}]
        })
        tweets = await service.get_user_tweets("atom_platform")
        assert tweets[0]["id"] == "1"
        call = service.client.request.call_args
        assert call.args[0] == "GET"
        assert "users/by/username/atom_platform/tweets" in call.args[1]

    async def test_search_recent_tweets(self, service):
        service.client.request.return_value = make_response(json_data={
            "data": [{"id": "2", "text": "match"}]
        })
        tweets = await service.search_recent_tweets("atom")
        assert tweets[0]["text"] == "match"
        call = service.client.request.call_args
        assert call.args[0] == "GET"
        assert "tweets/search/recent" in call.args[1]
        assert call.kwargs["params"]["query"] == "atom"


class TestTwitterHttpErrors:
    @pytest.fixture
    def service(self):
        svc = TwitterService(bearer_token="tok")
        svc.client = MagicMock()
        svc.client.request = AsyncMock()
        return svc

    async def test_http_status_error_propagates(self, service):
        service.client.request.return_value = make_response(status_code=429)
        with pytest.raises(HTTPException) as exc:
            await service.search_recent_tweets("q")
        assert exc.value.status_code == 429

    async def test_transport_error_raises_502(self, service):
        service.client.request.side_effect = httpx.ConnectError("boom")
        with pytest.raises(HTTPException) as exc:
            await service.get_user_tweets("someone")
        assert exc.value.status_code == 502


# ---------------- Route tests ----------------

route_app = FastAPI()
route_app.include_router(twitter_routes.router)
route_client = TestClient(route_app)


def _authed_route_client():
    """Client with get_current_user overridden (round 80: data/write routes
    now require authentication; /status and /health stay public)."""
    from unittest.mock import MagicMock

    from core.auth import get_current_user

    user = MagicMock()
    user.id = "tw-route-user"
    user.email = "tw@x.com"
    route_app.dependency_overrides[get_current_user] = lambda: user
    return TestClient(route_app)


class TestTwitterRoutes:
    def test_status_endpoint(self):
        response = route_client.get("/api/twitter/status")
        assert response.status_code == 200
        data = response.json()
        assert data["service"] == "twitter"
        assert data["available"] is True

    def test_health_endpoint(self):
        response = route_client.get("/api/twitter/health")
        assert response.status_code == 200
        assert "status" in response.json()

    def test_post_tweet_unconfigured_returns_mock(self, monkeypatch):
        monkeypatch.delenv("TWITTER_BEARER_TOKEN", raising=False)
        response = _authed_route_client().post("/api/twitter/tweets", json={"text": "hi"})
        assert response.status_code == 200
        assert response.json()["ok"] is True

    def test_user_tweets_unconfigured_returns_mock(self, monkeypatch):
        monkeypatch.delenv("TWITTER_BEARER_TOKEN", raising=False)
        response = _authed_route_client().get("/api/twitter/users/someone/tweets")
        assert response.status_code == 200
        assert response.json()["tweets"] == []

    def test_search_unconfigured_returns_mock(self, monkeypatch):
        monkeypatch.delenv("TWITTER_BEARER_TOKEN", raising=False)
        response = _authed_route_client().get("/api/twitter/search/recent?query=test")
        assert response.status_code == 200
        assert response.json()["tweets"] == []
