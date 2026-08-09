"""Coverage-push + TDD bug-hunt tests for assigned modules.

Modules under test (fixes allowed):
- integrations.bitbucket_service
- integrations.github_routes
- integrations.outlook_calendar_service

Bugs hunted here (red -> green):
  DEV-1  bitbucket full_sync reports success even when the postgres cache sync failed
  DEV-2  bitbucket execute_operation / sync_to_postgres_cache leak str(e) to callers
  DEV-3  bitbucket sync_to_postgres_cache filters IntegrationMetric on nonexistent
         `tenant_id` column (model uses `workspace_id`) -> sync always fails
  DEV-4  github_routes: module-level github_service singleton missing -> every route
         503s "GitHub service not available" (GITHUB_AVAILABLE False at import)
  DEV-5  github_routes: get_github_tokens(user_id) with no db session NEVER queries
         the database in OAUTH_STRICT_MODE -> all routes 401 despite valid token
  DEV-6  github_routes: list_issues/list_pull_requests call nonexistent service
         methods; create_issue/create_pull_request/search await synchronous methods;
         create_repository awaits nonexistent method -> every data route 500s
  DEV-7  github_routes: response builders use attribute access (repo.id) on dicts
         returned by GitHubService -> AttributeError -> 500
  DEV-8  github_routes: op="create" dispatch calls create_* handlers without the
         required current_user dependency -> TypeError -> 500
  DEV-9  github_routes /health leaks str(e) into the response body
  DEV-10 outlook_calendar check_conflicts crashes on naive datetime inputs
         (aware vs naive comparison raises TypeError -> silent failure)
  DEV-11 outlook_calendar _convert_outlook_to_unified crashes when location is null
  DEV-12 outlook_calendar execute_operation raises uncaught ValueError on tenant
         mismatch instead of returning {"success": False}
"""

import asyncio
import base64
import hashlib
import hmac
import json
import os
import sys
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

UTC = timezone.utc


def future_dt(minutes: float = 60) -> datetime:
    return datetime.now(UTC) + timedelta(minutes=minutes)


def past_dt(hours: float = 1) -> datetime:
    return datetime.now(UTC) - timedelta(hours=hours)


# ============================================================================
# integrations.bitbucket_service
# ============================================================================


class TestBitbucketServiceAuth:
    """OAuth URL building + token exchange/refresh."""

    def _svc(self, **config):
        from integrations.bitbucket_service import BitbucketService

        cfg = {
            "bitbucket_client_id": "cid",
            "bitbucket_client_secret": "csecret",
            "bitbucket_redirect_uri": "http://cb.example/bitbucket",
            "access_token": "tok",
        }
        cfg.update(config)
        return BitbucketService(tenant_id="t1", config=cfg)

    def test_get_authorization_url_default_state(self):
        svc = self._svc()
        url = svc.get_authorization_url()
        assert url.startswith("https://bitbucket.org/site/oauth2/authorize?")
        assert "client_id=cid" in url
        assert "response_type=code" in url
        assert "scope=repository+team+account" not in url
        assert "state=no_state" in url

    def test_get_authorization_url_custom_state(self):
        svc = self._svc()
        url = svc.get_authorization_url(state="s3cret")
        assert "state=s3cret" in url

    def test_exchange_code_for_token_success(self):
        svc = self._svc()
        with patch("integrations.bitbucket_service.requests.post") as post:
            resp = MagicMock()
            resp.json.return_value = {
                "access_token": "at",
                "refresh_token": "rt",
                "expires_in": 7200,
                "token_type": "bearer",
                "scope": "repository",
            }
            post.return_value = resp

            result = svc.exchange_code_for_token("auth-code")

            assert result["access_token"] == "at"
            assert result["refresh_token"] == "rt"
            assert result["expires_in"] == 7200
            assert result["token_type"] == "bearer"
            assert result["scope"] == "repository"
            post.assert_called_once()
            headers = post.call_args.kwargs["headers"]
            assert headers["Authorization"] == "Basic " + base64.b64encode(
                b"cid:csecret"
            ).decode()
            assert post.call_args.kwargs["data"]["grant_type"] == "authorization_code"

    def test_exchange_code_for_token_error_raises(self):
        svc = self._svc()
        with patch("integrations.bitbucket_service.requests.post") as post:
            post.side_effect = RuntimeError("boom")
            with pytest.raises(RuntimeError):
                svc.exchange_code_for_token("code")

    def test_refresh_access_token_success(self):
        svc = self._svc()
        with patch("integrations.bitbucket_service.requests.post") as post:
            resp = MagicMock()
            resp.json.return_value = {"access_token": "new-at", "expires_in": 3600}
            post.return_value = resp
            result = svc.refresh_access_token("old-rt")
            assert result["access_token"] == "new-at"
            assert post.call_args.kwargs["data"] == {
                "grant_type": "refresh_token",
                "refresh_token": "old-rt",
            }

    def test_refresh_access_token_error_raises(self):
        svc = self._svc()
        with patch("integrations.bitbucket_service.requests.post") as post:
            post.side_effect = ValueError("boom")
            with pytest.raises(ValueError):
                svc.refresh_access_token("rt")


class TestBitbucketServiceRequests:
    """_make_request + all API read/write methods (requests mocked)."""

    def _svc(self, **config):
        from integrations.bitbucket_service import BitbucketService

        return BitbucketService(
            tenant_id="t1",
            config={
                "bitbucket_client_id": "cid",
                "bitbucket_client_secret": "cs",
                "access_token": "tok",
            },
        )

    def _mock_response(self, payload: Any = None, content: bytes = b"{}"):
        resp = MagicMock()
        resp.content = content
        resp.json.return_value = payload if payload is not None else {}
        return resp

    @pytest.mark.parametrize(
        "method,call", [("GET", "get"), ("POST", "post"), ("PUT", "put"), ("DELETE", "delete")]
    )
    def test_make_request_all_methods(self, method, call):
        svc = self._svc()
        with patch.object(
            __import__("integrations.bitbucket_service", fromlist=["requests"]).requests, call
        ) as req:
            req.return_value = self._mock_response({"ok": True})
            result = svc._make_request("tok", "repositories/x", method)
            assert result == {"ok": True}

    def test_make_request_empty_body_returns_empty_dict(self):
        svc = self._svc()
        import integrations.bitbucket_service as mod

        with patch.object(mod.requests, "get") as req:
            req.return_value = self._mock_response(content=b"")
            assert svc._make_request("tok", "x") == {}

    def test_make_request_unsupported_method(self):
        svc = self._svc()
        with pytest.raises(ValueError):
            svc._make_request("tok", "x", "PATCH")

    def test_make_request_error_raises(self):
        svc = self._svc()
        import integrations.bitbucket_service as mod

        with patch.object(mod.requests, "get") as req:
            req.side_effect = RuntimeError("boom")
            with pytest.raises(RuntimeError):
                svc._make_request("tok", "x")

    def test_get_workspaces_success_and_error(self):
        svc = self._svc()
        with patch.object(svc, "_make_request", return_value={"values": [{"slug": "w1"}]}):
            assert svc.get_workspaces("tok") == [{"slug": "w1"}]
        with patch.object(svc, "_make_request", side_effect=RuntimeError("boom")):
            assert svc.get_workspaces("tok") == []

    def test_get_repositories_workspace_and_default(self):
        svc = self._svc()
        with patch.object(svc, "_make_request", return_value={"values": [{"slug": "r1"}]}) as mk:
            assert svc.get_repositories("tok", "ws") == [{"slug": "r1"}]
            assert mk.call_args.args[1] == "repositories/ws"
            assert svc.get_repositories("tok") == [{"slug": "r1"}]
            assert mk.call_args.args[1] == "repositories"
        with patch.object(svc, "_make_request", side_effect=RuntimeError("boom")):
            assert svc.get_repositories("tok") == []

    def test_get_repository(self):
        svc = self._svc()
        with patch.object(svc, "_make_request", return_value={"full_name": "ws/r"}) as mk:
            assert svc.get_repository("tok", "ws", "r") == {"full_name": "ws/r"}
            assert mk.call_args.args[1] == "repositories/ws/r"
        with patch.object(svc, "_make_request", side_effect=RuntimeError("boom")):
            assert svc.get_repository("tok", "ws", "r") == {}

    def test_get_branches(self):
        svc = self._svc()
        with patch.object(svc, "_make_request", return_value={"values": [{"name": "main"}]}) as mk:
            assert svc.get_branches("tok", "ws", "r") == [{"name": "main"}]
            assert mk.call_args.args[1] == "repositories/ws/r/refs/branches"
        with patch.object(svc, "_make_request", side_effect=RuntimeError("boom")):
            assert svc.get_branches("tok", "ws", "r") == []

    def test_get_pull_requests_state_param(self):
        svc = self._svc()
        with patch.object(svc, "_make_request", return_value={"values": [{"id": 1}]}) as mk:
            assert svc.get_pull_requests("tok", "ws", "r") == [{"id": 1}]
            assert mk.call_args.args[1] == "repositories/ws/r/pullrequests?state=OPEN"
            assert svc.get_pull_requests("tok", "ws", "r", "MERGED") == [{"id": 1}]
        with patch.object(svc, "_make_request", side_effect=RuntimeError("boom")):
            assert svc.get_pull_requests("tok", "ws", "r") == []

    def test_get_pull_request(self):
        svc = self._svc()
        with patch.object(svc, "_make_request", return_value={"id": 7}):
            assert svc.get_pull_request("tok", "ws", "r", "7") == {"id": 7}
        with patch.object(svc, "_make_request", side_effect=RuntimeError("boom")):
            assert svc.get_pull_request("tok", "ws", "r", "7") == {}

    def test_create_pull_request_with_and_without_reviewers(self):
        svc = self._svc()
        with patch.object(svc, "_make_request", return_value={"id": 8}) as mk:
            res = svc.create_pull_request("tok", "ws", "r", "Title", "feat", "main", "desc")
            assert res == {"id": 8}
            sent = mk.call_args
            assert sent.args[1] == "repositories/ws/r/pullrequests"
            assert sent.args[2] == "POST"
            assert sent.args[3]["title"] == "Title"
            assert sent.args[3]["source"]["branch"]["name"] == "feat"
            assert "reviewers" not in sent.args[3]

            svc.create_pull_request(
                "tok", "ws", "r", "T2", "feat", reviewers=["uuid-1"]
            )
            assert mk.call_args.args[3]["reviewers"] == [{"uuid": "uuid-1"}]
        with patch.object(svc, "_make_request", side_effect=RuntimeError("boom")):
            assert svc.create_pull_request("tok", "ws", "r", "T", "f") == {}

    def test_get_commits_with_and_without_branch(self):
        svc = self._svc()
        with patch.object(svc, "_make_request", return_value={"values": [{"hash": "h"}]}) as mk:
            assert svc.get_commits("tok", "ws", "r") == [{"hash": "h"}]
            assert mk.call_args.args[1] == "repositories/ws/r/commits"
            assert svc.get_commits("tok", "ws", "r", "main") == [{"hash": "h"}]
            assert mk.call_args.args[1] == "repositories/ws/r/commits?include=main"
        with patch.object(svc, "_make_request", side_effect=RuntimeError("boom")):
            assert svc.get_commits("tok", "ws", "r") == []

    def test_get_pipelines(self):
        svc = self._svc()
        with patch.object(svc, "_make_request", return_value={"values": [{"uuid": "p"}]}) as mk:
            assert svc.get_pipelines("tok", "ws", "r") == [{"uuid": "p"}]
            assert mk.call_args.args[1] == "repositories/ws/r/pipelines/"
        with patch.object(svc, "_make_request", side_effect=RuntimeError("boom")):
            assert svc.get_pipelines("tok", "ws", "r") == []

    def test_trigger_pipeline_with_and_without_variables(self):
        svc = self._svc()
        with patch.object(svc, "_make_request", return_value={"uuid": "p1"}) as mk:
            assert svc.trigger_pipeline("tok", "ws", "r") == {"uuid": "p1"}
            payload = mk.call_args.args[3]
            assert payload["target"]["ref_name"] == "main"
            assert "variables" not in payload
            svc.trigger_pipeline("tok", "ws", "r", "dev", {"K": "V"})
            payload = mk.call_args.args[3]
            assert payload["variables"] == [{"key": "K", "value": "V"}]
        with patch.object(svc, "_make_request", side_effect=RuntimeError("boom")):
            assert svc.trigger_pipeline("tok", "ws", "r") == {}

    def test_get_issues(self):
        svc = self._svc()
        with patch.object(svc, "_make_request", return_value={"values": [{"id": 1}]}):
            assert svc.get_issues("tok", "ws", "r") == [{"id": 1}]
        with patch.object(svc, "_make_request", side_effect=RuntimeError("boom")):
            assert svc.get_issues("tok", "ws", "r") == []

    def test_create_issue(self):
        svc = self._svc()
        with patch.object(svc, "_make_request", return_value={"id": 2}) as mk:
            res = svc.create_issue("tok", "ws", "r", "Bug")
            assert res == {"id": 2}
            assert mk.call_args.args[3]["content"] == {"raw": ""}
            assert mk.call_args.args[3]["kind"] == "bug"
            assert mk.call_args.args[3]["priority"] == "major"
        with patch.object(svc, "_make_request", side_effect=RuntimeError("boom")):
            assert svc.create_issue("tok", "ws", "r", "Bug") == {}

    def test_get_webhooks(self):
        svc = self._svc()
        with patch.object(svc, "_make_request", return_value={"values": [{"id": "h"}]}):
            assert svc.get_webhooks("tok", "ws", "r") == [{"id": "h"}]
        with patch.object(svc, "_make_request", side_effect=RuntimeError("boom")):
            assert svc.get_webhooks("tok", "ws", "r") == []

    def test_get_user_info(self):
        svc = self._svc()
        with patch.object(svc, "_make_request", return_value={"display_name": "Bob"}):
            assert svc.get_user_info("tok") == {"display_name": "Bob"}
        with patch.object(svc, "_make_request", side_effect=RuntimeError("boom")):
            assert svc.get_user_info("tok") == {}

    def test_search_code(self):
        svc = self._svc()
        with patch.object(svc, "_make_request", return_value={"values": [{"path": "a"}]}) as mk:
            assert svc.search_code("tok", "foo") == [{"path": "a"}]
            assert mk.call_args.args[1] == "search/code?search_query=foo"
            assert svc.search_code("tok", "foo", "ws") == [{"path": "a"}]
            assert mk.call_args.args[1] == "search/code?search_query=foo&workspace=ws"
        with patch.object(svc, "_make_request", side_effect=RuntimeError("boom")):
            assert svc.search_code("tok", "foo") == []

    def test_get_health_status(self):
        svc = self._svc()
        with patch.object(svc, "get_user_info", return_value={"display_name": "Bob"}):
            status = svc.get_health_status("tok")
            assert status["status"] == "healthy"
            assert status["user"] == "Bob"
        with patch.object(svc, "get_user_info", return_value={}):
            assert svc.get_health_status("tok")["status"] == "unhealthy"

    def test_get_capabilities_and_health_check(self):
        svc = self._svc()
        caps = svc.get_capabilities()
        assert any(op["id"] == "create_pr" for op in caps["operations"])
        assert caps["supports_webhooks"] is True
        health = svc.health_check()
        assert health["ok"] is True
        assert health["healthy"] is True
        assert health["service"] == "bitbucket"


class TestBitbucketServiceOps:
    """execute_operation + postgres cache sync + full_sync."""

    def _svc(self):
        from integrations.bitbucket_service import BitbucketService

        return BitbucketService(
            tenant_id="t1",
            config={"bitbucket_client_id": "cid", "bitbucket_client_secret": "cs"},
        )

    def test_execute_operation_create_repo_stub(self):
        svc = self._svc()
        res = asyncio.run(svc.execute_operation("create_repo", {"repo_name": "new"}))
        assert res["success"] is True
        assert res["result"]["name"] == "new"

    def test_execute_operation_list_repos_context_token(self):
        svc = self._svc()
        with patch.object(svc, "get_repositories", return_value=[{"slug": "r"}]):
            res = asyncio.run(svc.execute_operation("list_repos", {"workspace": "ws"}, {"access_token": "ctx"}))
            assert res == {"success": True, "result": [{"slug": "r"}]}

    def test_execute_operation_create_pr(self):
        svc = self._svc()
        with patch.object(svc, "create_pull_request", return_value={"id": 1}) as cpr:
            res = asyncio.run(svc.execute_operation(
                "create_pr",
                {
                    "access_token": "at",
                    "workspace": "ws",
                    "repo_slug": "r",
                    "title": "T",
                    "source_branch": "f",
                    "destination_branch": "d",
                    "description": "desc",
                    "reviewers": ["u"],
                },
            ))
            assert res["success"] is True
            cpr.assert_called_once_with("at", "ws", "r", "T", "f", "d", "desc", ["u"])

    def test_execute_operation_branches_commits_issues(self):
        svc = self._svc()
        with patch.object(svc, "get_branches", return_value=[{"name": "m"}]) as gb:
            res = asyncio.run(svc.execute_operation(
                "get_branches", {"access_token": "at", "workspace": "ws", "repo_slug": "r"}
            ))
            assert res["success"] is True
        with patch.object(svc, "get_commits", return_value=[{"hash": "h"}]) as gc:
            res = asyncio.run(svc.execute_operation(
                "get_commits",
                {"access_token": "at", "workspace": "ws", "repo_slug": "r", "branch": "b"},
            ))
            assert res["success"] is True
        with patch.object(svc, "get_issues", return_value=[{"id": 1}]) as gi:
            res = asyncio.run(svc.execute_operation(
                "get_issues", {"access_token": "at", "workspace": "ws", "repo_slug": "r"}
            ))
            assert res["success"] is True

    def test_execute_operation_create_issue(self):
        svc = self._svc()
        with patch.object(svc, "create_issue", return_value={"id": 5}) as ci:
            res = asyncio.run(svc.execute_operation(
                "create_issue",
                {
                    "access_token": "at",
                    "workspace": "ws",
                    "repo_slug": "r",
                    "title": "T",
                    "content": "c",
                },
            ))
            assert res["success"] is True
            ci.assert_called_once_with("at", "ws", "r", "T", "c", "bug", "major")

    def test_execute_operation_unknown_operation_no_str_leak(self):
        svc = self._svc()
        res = asyncio.run(svc.execute_operation("nope", {"access_token": "at"}))
        assert res["success"] is False
        assert "NotImplementedError" not in str(res)
        assert "boom" not in str(res)
        assert res["error"] == "Bitbucket operation failed"

    def test_execute_operation_underlying_error_no_str_leak(self):
        svc = self._svc()
        with patch.object(svc, "get_repositories", side_effect=RuntimeError("boom")):
            res = asyncio.run(svc.execute_operation("list_repos", {"access_token": "at"}))
            assert res["success"] is False
            assert "boom" not in str(res)

    @staticmethod
    @contextmanager
    def _mock_db():
        import core.database as dbmod

        session = MagicMock()
        with patch.object(dbmod, "SessionLocal", return_value=session):
            yield session

    def test_sync_to_postgres_cache_creates_metric(self):
        svc = self._svc()
        with self._mock_db() as session:
            session.query.return_value.filter_by.return_value.first.return_value = None
            with patch.object(svc, "get_repositories", return_value=[{"slug": "r1"}, {"slug": "r2"}]):
                result = svc.sync_to_postgres_cache("ws-1", "at")
            assert result["success"] is True
            assert result["metrics_synced"] == 1
            metric = session.add.call_args.args[0]
            assert metric.integration_type == "bitbucket"
            assert metric.metric_key == "bitbucket_repository_count"
            assert metric.value == 2.0
            assert metric.workspace_id == "ws-1"
            session.commit.assert_called_once()

    def test_sync_to_postgres_cache_updates_existing(self):
        svc = self._svc()
        with self._mock_db() as session:
            existing = MagicMock()
            existing.value = 1.0
            session.query.return_value.filter_by.return_value.first.return_value = existing
            with patch.object(svc, "get_repositories", return_value=[]):
                result = svc.sync_to_postgres_cache("ws-1", "at")
            assert result["success"] is True
            assert existing.value == 0.0
            assert existing.last_synced_at is not None

    def test_sync_to_postgres_cache_commit_failure_no_str_leak(self):
        svc = self._svc()
        with self._mock_db() as session:
            session.commit.side_effect = RuntimeError("boom")
            with patch.object(svc, "get_repositories", return_value=[{"slug": "r1"}]):
                result = svc.sync_to_postgres_cache("ws-1", "at")
            assert result["success"] is False
            assert "boom" not in str(result)
            session.rollback.assert_called_once()

    def test_sync_to_postgres_cache_repo_fetch_failure(self):
        svc = self._svc()
        with self._mock_db() as session:
            with patch.object(svc, "get_repositories", side_effect=RuntimeError("boom")):
                result = svc.sync_to_postgres_cache("ws-1", "at")
            assert result["success"] is False
            assert "boom" not in str(result)

    def test_full_sync_propagates_cache_failure(self):
        svc = self._svc()
        with patch.object(
            svc, "sync_to_postgres_cache", return_value={"success": False, "error": "x"}
        ):
            result = svc.full_sync("ws-1", "at")
        assert result["success"] is False
        assert result["postgres_cache"]["success"] is False

    def test_full_sync_success(self):
        svc = self._svc()
        with patch.object(
            svc, "sync_to_postgres_cache", return_value={"success": True, "metrics_synced": 1}
        ):
            result = svc.full_sync("ws-1", "at")
        assert result["success"] is True
        assert result["workspace_id"] == "ws-1"


# ============================================================================
# integrations.github_routes
# ============================================================================

REPO_DICT: Dict[str, Any] = {
    "id": 11,
    "name": "atom",
    "full_name": "owner/atom",
    "description": "d",
    "private": False,
    "fork": False,
    "html_url": "https://github.com/owner/atom",
    "clone_url": "https://github.com/owner/atom.git",
    "ssh_url": "git@github.com:owner/atom.git",
    "language": "Python",
    "stargazers_count": 3,
    "watchers_count": 3,
    "forks_count": 1,
    "open_issues_count": 2,
    "default_branch": "main",
    "created_at": "2026-01-01T00:00:00Z",
    "updated_at": "2026-01-02T00:00:00Z",
    "pushed_at": "2026-01-03T00:00:00Z",
    "size": 100,
    "owner": {"login": "owner", "avatar_url": "https://avatars/owner"},
    "topics": ["ai"],
    "license": {"spdx_id": "MIT"},
}

ISSUE_DICT: Dict[str, Any] = {
    "id": 21,
    "number": 5,
    "title": "Issue",
    "body": "body",
    "state": "open",
    "locked": False,
    "comments": 1,
    "created_at": "2026-01-01T00:00:00Z",
    "updated_at": "2026-01-02T00:00:00Z",
    "closed_at": None,
    "user": {"login": "owner", "avatar_url": "https://avatars/owner"},
    "assignee": {"login": "owner", "avatar_url": "https://avatars/owner"},
    "assignees": [{"login": "owner", "avatar_url": "https://avatars/owner"}],
    "labels": [{"name": "bug"}],
    "milestone": None,
    "html_url": "https://github.com/owner/atom/issues/5",
    "reactions": {"total_count": 0},
    "repository_url": "https://api.github.com/repos/owner/atom",
}

PR_DICT: Dict[str, Any] = {
    "id": 31,
    "number": 7,
    "title": "PR",
    "body": "b",
    "state": "open",
    "locked": False,
    "created_at": "2026-01-01T00:00:00Z",
    "updated_at": "2026-01-02T00:00:00Z",
    "closed_at": None,
    "merged_at": None,
    "merge_commit_sha": "abc",
    "head": {"ref": "feat", "sha": "s"},
    "base": {"ref": "main", "sha": "s"},
    "user": {"login": "owner"},
    "assignees": [],
    "requested_reviewers": [],
    "labels": [],
    "milestone": None,
    "commits": 2,
    "additions": 10,
    "deletions": 2,
    "changed_files": 3,
    "html_url": "https://github.com/owner/atom/pull/7",
    "diff_url": "https://github.com/owner/atom/pull/7.diff",
    "patch_url": "https://github.com/owner/atom/pull/7.patch",
}


def make_github_service_mock() -> MagicMock:
    """Fake service mirroring GitHubService behavior (returns dicts)."""
    svc = MagicMock()
    svc.base_url = "https://api.github.com"
    svc.session = MagicMock()
    post_resp = MagicMock()
    post_resp.json.return_value = dict(REPO_DICT)
    svc.session.post.return_value = post_resp
    svc.get_user_repositories.return_value = [dict(REPO_DICT)]
    svc.get_repository_issues.return_value = [dict(ISSUE_DICT)]
    svc.get_repository_pulls.return_value = [dict(PR_DICT)]
    svc.create_issue.return_value = dict(ISSUE_DICT)
    svc.create_pull_request.return_value = dict(PR_DICT)
    svc.search_repositories.return_value = [dict(REPO_DICT)]
    svc.test_connection.return_value = {"status": "success", "user": "owner", "authenticated": True}
    return svc


def gh_tokens_dict(user_info: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    return {
        "access_token": "gh-tok",
        "token_type": "bearer",
        "scope": "repo",
        "user_info": user_info if user_info is not None else {"login": "owner", "id": "1"},
        "source": "database",
    }


@pytest.fixture
def gh_client():
    import fastapi
    from fastapi.testclient import TestClient

    import integrations.github_routes as gr

    app = fastapi.FastAPI()
    app.include_router(gr.router)

    class FakeUser:
        id = "u-auth-1"

    app.dependency_overrides[gr.get_current_user] = lambda: FakeUser()
    return TestClient(app)


@pytest.fixture
def gh_mocks(gh_client):
    """Patch GITHUB_AVAILABLE + github_service + token lookup onto the module."""
    import integrations.github_routes as gr

    service = make_github_service_mock()
    with patch.object(gr, "GITHUB_AVAILABLE", True), patch.object(
        gr, "github_service", service
    ), patch.object(gr, "get_github_tokens", return_value=gh_tokens_dict()):
        yield gr, service

class TestGithubRoutesTokens:
    """get_github_tokens behavior."""

    class _TokenRecord:
        def __init__(self, **overrides):
            self.user_id = "u-1"
            self.provider = "github"
            self.access_token = "encrypted-tok"
            self.refresh_token = None
            self.token_type = "bearer"
            self.scope = "repo,user:email"
            self.expires_at = None
            self.status = "active"
            for k, v in overrides.items():
                setattr(self, k, v)

    def _token_record(self, **overrides):
        return self._TokenRecord(**overrides)

    @pytest.fixture(autouse=True)
    def _strict_on(self):
        import integrations.github_routes as gr

        with patch.object(gr, "OAUTH_STRICT_MODE", True):
            yield

    def _patch_decrypt(self, plain: str = "db-tok"):
        return patch(
            "core.privsec.token_encryption.decrypt_token", return_value=plain
        )

    def test_uses_db_session_when_none_provided(self):
        """DEV-5: db=None must still query the DB (docstring promises it)."""
        import integrations.github_routes as gr

        record = self._token_record()
        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = record

        with patch.object(gr, "get_db_session", return_value=iter([db])), self._patch_decrypt():
            result = gr.get_github_tokens("u-1")

        assert result is not None
        assert result["access_token"] == "db-tok"
        assert result["source"] == "database"
        assert result["user_info"] == {}
        db.close.assert_called_once()

    def test_uses_provided_db(self):
        import integrations.github_routes as gr

        record = self._token_record()
        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = record
        with self._patch_decrypt():
            result = gr.get_github_tokens("u-1", db)
        assert result["access_token"] == "db-tok"
        assert result["token_type"] == "bearer"
        assert result["scope"] == "repo,user:email"

    def test_decrypt_plaintext_legacy_token(self):
        import integrations.github_routes as gr

        record = self._token_record()
        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = record
        with patch(
            "core.privsec.token_encryption.decrypt_token",
            side_effect=lambda tok, allow_plaintext=False: tok,
        ):
            result = gr.get_github_tokens("u-1", db)
        assert result["access_token"] == "encrypted-tok"

    def test_expired_token_strict_raises_401(self):
        import integrations.github_routes as gr

        record = self._token_record(expires_at=past_dt())
        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = record
        with pytest.raises(gr.HTTPException) as exc:
            gr.get_github_tokens("u-1", db)
        assert exc.value.status_code == 401
        assert exc.value.detail["error_code"] == "OAUTH_TOKEN_EXPIRED"

    def test_expired_token_non_strict_returns_none(self):
        import integrations.github_routes as gr

        record = self._token_record(expires_at=past_dt())
        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = record
        with patch.object(gr, "OAUTH_STRICT_MODE", False):
            assert gr.get_github_tokens("u-1", db) is None

    def test_no_token_strict_raises_401(self):
        import integrations.github_routes as gr

        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = None
        with pytest.raises(gr.HTTPException) as exc:
            gr.get_github_tokens("u-1", db)
        assert exc.value.status_code == 401
        assert exc.value.detail["error_code"] == "OAUTH_TOKEN_INVALID"

    def test_db_query_error_strict_falls_through_401(self):
        import integrations.github_routes as gr

        db = MagicMock()
        db.query.side_effect = RuntimeError("boom")
        with pytest.raises(gr.HTTPException) as exc:
            gr.get_github_tokens("u-1", db)
        assert exc.value.status_code == 401
        assert exc.value.detail["error_code"] == "OAUTH_TOKEN_INVALID"

    def test_db_session_creation_error_strict_raises_500(self):
        import integrations.github_routes as gr

        def broken():
            raise RuntimeError("boom")
            yield

        with patch.object(gr, "get_db_session", broken):
            with pytest.raises(gr.HTTPException) as exc:
                gr.get_github_tokens("u-1")
        assert exc.value.status_code == 500
        assert "boom" not in str(exc.value.detail)

    def test_no_token_non_strict_returns_none(self):
        import integrations.github_routes as gr

        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = None
        with patch.object(gr, "OAUTH_STRICT_MODE", False):
            assert gr.get_github_tokens("u-1", db) is None

    def test_env_fallback_non_strict(self):
        import integrations.github_routes as gr

        with patch.object(gr, "OAUTH_STRICT_MODE", False), patch.dict(
            os.environ, {"GITHUB_ACCESS_TOKEN": "env-tok"}
        ):
            result = gr.get_github_tokens("u-1", MagicMock())
        assert result["access_token"] == "env-tok"
        assert result["source"] == "environment"


class TestGithubRoutesEndpoints:
    """All data endpoints against a mocked service (dict-shaped responses)."""

    def test_health_unavailable(self, gh_client):
        import integrations.github_routes as gr

        with patch.object(gr, "GITHUB_AVAILABLE", False):
            resp = gh_client.get("/api/github/health")
        assert resp.status_code == 200
        assert resp.json()["ok"] is False

    def test_health_available(self, gh_client, gh_mocks):
        gr, service = gh_mocks
        resp = gh_client.get("/api/github/health")
        assert resp.status_code == 200
        assert resp.json()["ok"] is True
        assert resp.json()["status"] == "healthy"

    def test_health_service_error_no_str_leak(self, gh_client, gh_mocks):
        gr, service = gh_mocks
        service.test_connection.side_effect = RuntimeError("boom")
        resp = gh_client.get("/api/github/health")
        assert resp.status_code == 200
        assert resp.json()["ok"] is False
        assert resp.json()["status"] == "degraded"
        assert "boom" not in resp.text

    def test_health_internal_error_no_str_leak(self, gh_client, gh_mocks):
        gr, service = gh_mocks
        calls = [0]

        def boom_now(tz=None):
            calls[0] += 1
            if calls[0] <= 2:
                raise RuntimeError("boom")
            return datetime(2026, 1, 1, tzinfo=UTC)

        boom_dt = type("BoomDateTime", (), {"now": staticmethod(boom_now)})
        with patch.object(gr, "datetime", boom_dt):
            resp = gh_client.get("/api/github/health")
        assert resp.status_code == 200
        assert resp.json()["ok"] is False
        assert resp.json()["status"] == "unhealthy"
        assert "boom" not in resp.text

    def test_list_repositories_parses_dict_response(self, gh_client, gh_mocks):
        gr, service = gh_mocks
        resp = gh_client.post("/api/github/repositories", json={"user_id": "x"})
        assert resp.status_code == 200
        body = resp.json()
        assert body["ok"] is True
        assert body["data"]["total_count"] == 1
        assert body["data"]["repositories"][0]["repo_id"] == 11
        assert body["data"]["repositories"][0]["visibility"] == "public"
        assert body["data"]["repositories"][0]["owner"] == {"login": "owner", "avatar_url": "https://avatars/owner"}
        assert body["endpoint"] == "list_repositories"

    def test_list_repositories_service_error_500(self, gh_client, gh_mocks):
        gr, service = gh_mocks
        service.get_user_repositories.side_effect = RuntimeError("boom")
        resp = gh_client.post("/api/github/repositories", json={"user_id": "x"})
        assert resp.status_code == 500
        assert "boom" not in resp.text

    def test_list_repositories_no_tokens_401(self, gh_client, gh_mocks):
        gr, service = gh_mocks
        gr.get_github_tokens.return_value = None
        resp = gh_client.post("/api/github/repositories", json={"user_id": "x"})
        assert resp.status_code == 401

    def test_list_repositories_service_unavailable_503(self, gh_client):
        import integrations.github_routes as gr

        with patch.object(gr, "GITHUB_AVAILABLE", False), patch.object(
            gr, "get_github_tokens", return_value=gh_tokens_dict()
        ):
            resp = gh_client.post("/api/github/repositories", json={"user_id": "x"})
        assert resp.status_code == 503

    def test_create_repository_route(self, gh_client, gh_mocks):
        gr, service = gh_mocks
        resp = gh_client.post(
            "/api/github/repositories/create",
            json={"user_id": "x", "name": "new-repo", "description": "desc"},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["ok"] is True
        assert body["data"]["repository"]["repo_id"] == 11
        assert body["data"]["url"] == REPO_DICT["html_url"]
        sent = service.session.post.call_args
        assert sent.args[0] == "https://api.github.com/user/repos"
        assert sent.kwargs["json"]["name"] == "new-repo"

    def test_repositories_dispatch_create_operation(self, gh_client, gh_mocks):
        gr, service = gh_mocks
        resp = gh_client.post(
            "/api/github/repositories",
            json={"user_id": "x", "operation": "create", "name": "r2"},
        )
        assert resp.status_code == 200
        assert resp.json()["data"]["repository"]["name"] == REPO_DICT["name"]

    def test_list_issues_parses_dict_response(self, gh_client, gh_mocks):
        gr, service = gh_mocks
        resp = gh_client.post("/api/github/issues", json={"user_id": "x"})
        assert resp.status_code == 200
        body = resp.json()
        assert body["ok"] is True
        issue = body["data"]["issues"][0]
        assert issue["issue_id"] == 21
        assert issue["number"] == 5
        assert issue["assignee"]["login"] == "owner"
        assert issue["assignees"][0]["login"] == "owner"
        service.get_repository_issues.assert_called_once()

    def test_create_issue_route(self, gh_client, gh_mocks):
        gr, service = gh_mocks
        resp = gh_client.post(
            "/api/github/issues/create",
            json={"user_id": "x", "title": "T", "labels": ["bug"]},
        )
        assert resp.status_code == 200
        assert resp.json()["data"]["issue"]["issue_id"] == 21
        assert resp.json()["data"]["message"] == "Issue created successfully"

    def test_issues_dispatch_create_operation(self, gh_client, gh_mocks):
        gr, service = gh_mocks
        resp = gh_client.post(
            "/api/github/issues",
            json={"user_id": "x", "operation": "create", "title": "T"},
        )
        assert resp.status_code == 200
        assert resp.json()["data"]["issue"]["issue_id"] == 21

    def test_create_issue_failure_500(self, gh_client, gh_mocks):
        gr, service = gh_mocks
        service.create_issue.return_value = None
        resp = gh_client.post(
            "/api/github/issues/create", json={"user_id": "x", "title": "T"}
        )
        assert resp.status_code == 500

    def test_list_pull_requests_parses_dict_response(self, gh_client, gh_mocks):
        gr, service = gh_mocks
        resp = gh_client.post(
            "/api/github/pulls",
            json={"user_id": "x", "owner": "owner", "repo": "atom"},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["ok"] is True
        pr = body["data"]["pull_requests"][0]
        assert pr["pr_id"] == 31
        assert pr["merge_commit_sha"] == "abc"
        assert body["data"]["repository"] == "owner/atom"
        service.get_repository_pulls.assert_called_once()

    def test_create_pull_request_route(self, gh_client, gh_mocks):
        gr, service = gh_mocks
        resp = gh_client.post(
            "/api/github/pulls/create",
            json={"user_id": "x", "title": "T", "head": "feat", "base": "main"},
        )
        assert resp.status_code == 200
        assert resp.json()["data"]["pull_request"]["pr_id"] == 31

    def test_pulls_dispatch_create_operation(self, gh_client, gh_mocks):
        gr, service = gh_mocks
        resp = gh_client.post(
            "/api/github/pulls",
            json={"user_id": "x", "operation": "create", "title": "T", "head": "f"},
        )
        assert resp.status_code == 200
        assert resp.json()["data"]["pull_request"]["pr_id"] == 31

    def test_search_route(self, gh_client, gh_mocks):
        gr, service = gh_mocks
        resp = gh_client.post("/api/github/search", json={"user_id": "x", "query": "atom"})
        assert resp.status_code == 200
        assert resp.json()[0]["id"] == 11
        service.search_repositories.assert_called_once()

    def test_user_profile(self, gh_client, gh_mocks):
        gr, service = gh_mocks
        resp = gh_client.post("/api/github/user/profile", json={"user_id": "x"})
        assert resp.status_code == 200
        assert resp.json()["data"]["user"]["login"] == "owner"


# ============================================================================
# integrations.outlook_calendar_service
# ============================================================================


class TestOutlookCalendarAuth:
    def _svc(self, tmp_path, **config):
        from integrations.outlook_calendar_service import OutlookCalendarService

        cfg = {"client_id": "cli-1"}
        cfg.update(config)
        svc = OutlookCalendarService(tenant_id="t-cov", config=cfg)
        svc.token_cache_file = tmp_path / "outlook_cache.json"
        return svc

    def test_missing_client_id_fails(self, tmp_path):
        svc = self._svc(tmp_path, client_id=None)
        with patch.dict(os.environ, {}, clear=True):
            assert svc.authenticate() is False

    def test_authenticate_silent_cache_hit(self, tmp_path):
        svc = self._svc(tmp_path)
        with patch("integrations.outlook_calendar_service.PublicClientApplication") as pca:
            app = MagicMock()
            pca.return_value = app
            app.get_accounts.return_value = [{"home_account_id": "1"}]
            app.acquire_token_silent.return_value = {"access_token": "t1", "expires_in": 3600}
            assert svc.authenticate() is True
            assert svc.access_token == "t1"
            assert svc.token_expiry is not None

    def test_authenticate_device_flow_success(self, tmp_path):
        svc = self._svc(tmp_path)
        with patch("integrations.outlook_calendar_service.PublicClientApplication") as pca:
            app = MagicMock()
            pca.return_value = app
            app.get_accounts.return_value = []
            app.initiate_device_flow.return_value = {
                "user_code": "ABC",
                "message": "visit https://microsoft.com/devicelogin",
            }
            app.acquire_token_by_device_flow.return_value = {
                "access_token": "t2",
                "expires_in": 7200,
            }
            assert svc.authenticate() is True
            assert svc.access_token == "t2"

    def test_authenticate_device_flow_user_error(self, tmp_path):
        svc = self._svc(tmp_path)
        with patch("integrations.outlook_calendar_service.PublicClientApplication") as pca:
            app = MagicMock()
            pca.return_value = app
            app.get_accounts.return_value = []
            app.initiate_device_flow.return_value = {
                "user_code": "ABC",
                "message": "go",
            }
            app.acquire_token_by_device_flow.return_value = {
                "error": "authorization_pending",
                "error_description": "still waiting",
            }
            assert svc.authenticate() is False

    def test_authenticate_device_flow_missing_user_code(self, tmp_path):
        svc = self._svc(tmp_path)
        with patch("integrations.outlook_calendar_service.PublicClientApplication") as pca:
            app = MagicMock()
            pca.return_value = app
            app.get_accounts.return_value = []
            app.initiate_device_flow.return_value = {}
            assert svc.authenticate() is False

    def test_authenticate_exception(self, tmp_path):
        svc = self._svc(tmp_path)
        with patch("integrations.outlook_calendar_service.PublicClientApplication") as pca:
            pca.side_effect = RuntimeError("boom")
            assert svc.authenticate() is False

    def test_ensure_authenticated_no_token(self, tmp_path):
        svc = self._svc(tmp_path)
        with patch.object(svc, "authenticate", return_value=True):
            assert svc._ensure_authenticated() is True

    def test_ensure_authenticated_expired_token(self, tmp_path):
        svc = self._svc(tmp_path)
        svc.access_token = "old"
        svc.token_expiry = past_dt()
        with patch.object(svc, "authenticate", return_value=True) as auth:
            assert svc._ensure_authenticated() is True
            auth.assert_called_once()

    def test_ensure_authenticated_valid_token(self, tmp_path):
        svc = self._svc(tmp_path)
        svc.access_token = "valid"
        svc.token_expiry = future_dt(minutes=30)
        assert svc._ensure_authenticated() is True

    def test_token_cache_load_save(self, tmp_path):
        svc = self._svc(tmp_path)
        svc.token_cache_file.write_text('{"access_token": "cached"}')
        assert svc._load_token_cache() == {"access_token": "cached"}
        svc._save_token_cache({"k": "v"})
        assert json.loads(svc.token_cache_file.read_text()) == {"k": "v"}

    def test_token_cache_corrupt_and_missing(self, tmp_path):
        svc = self._svc(tmp_path)
        svc.token_cache_file.write_text("not json")
        assert svc._load_token_cache() == {}
        (tmp_path / "other.json")
        svc.token_cache_file.unlink()
        assert svc._load_token_cache() == {}

    def test_token_cache_save_failure_swallowed(self, tmp_path):
        svc = self._svc(tmp_path)
        svc.token_cache_file = tmp_path / "missing_dir" / "cache.json"
        svc._save_token_cache({"k": "v"})
        assert not (tmp_path / "missing_dir").exists()

    def test_get_capabilities(self, tmp_path):
        svc = self._svc(tmp_path)
        caps = svc.get_capabilities()
        assert any(op["id"] == "check_conflicts" for op in caps["operations"])
        assert caps["supports_webhooks"] is True

    def test_health_check(self, tmp_path):
        svc = self._svc(tmp_path)
        health = svc.health_check()
        assert health["healthy"] is True
        svc.client_id = None
        health = svc.health_check()
        assert health["healthy"] is False


def make_graph_response(status: int = 200, payload: Optional[Dict] = None, text: str = ""):
    """Build aiohttp ClientSession() mock for the Graph call sites.

    The service uses `async with session.get(...)` without awaiting the call,
    so session request methods must return the response context manager
    synchronously (mirroring aiohttp's _RequestContextManager).
    """
    response = AsyncMock()
    response.status = status
    response.json = AsyncMock(return_value=payload if payload is not None else {})
    response.text = AsyncMock(return_value=text)
    response.__aenter__ = AsyncMock(return_value=response)
    response.__aexit__ = AsyncMock(return_value=False)

    session = MagicMock()
    session.get = MagicMock(return_value=response)
    session.post = MagicMock(return_value=response)
    session.patch = MagicMock(return_value=response)
    session.delete = MagicMock(return_value=response)

    client_session = AsyncMock()
    client_session.__aenter__ = AsyncMock(return_value=session)
    client_session.__aexit__ = AsyncMock(return_value=False)
    return client_session, response


def make_authed_calendar(tmp_path) -> Any:
    from integrations.outlook_calendar_service import OutlookCalendarService

    svc = OutlookCalendarService(tenant_id="t-cov", config={"client_id": "cli-1"})
    svc.token_cache_file = tmp_path / "outlook_cache.json"
    svc.access_token = "graph-tok"
    svc.token_expiry = future_dt(minutes=30)
    return svc


class TestOutlookCalendarGraph:
    """Graph API calls (aiohttp mocked) + conversions."""

    def test_get_events_success(self, tmp_path):
        svc = make_authed_calendar(tmp_path)
        payload = {
            "value": [
                {
                    "id": "e1",
                    "subject": "Standup",
                    "start": {"dateTime": "2026-01-01T10:00:00Z"},
                    "end": {"dateTime": "2026-01-01T10:30:00Z"},
                    "body": {"content": "notes"},
                    "attendees": [{"emailAddress": {"address": "a@x.com"}}],
                    "location": {"displayName": "Zoom"},
                    "createdDateTime": "2026-01-01T00:00:00Z",
                    "lastModifiedDateTime": "2026-01-01T01:00:00Z",
                }
            ]
        }
        client_session, response = make_graph_response(200, payload)
        with patch(
            "integrations.outlook_calendar_service.aiohttp.ClientSession",
            return_value=client_session,
        ) as cs:
            events = asyncio.run(svc.get_events())
        assert len(events) == 1
        event = events[0]
        assert event["id"] == "e1"
        assert event["title"] == "Standup"
        assert event["platform"] == "outlook"
        assert event["attendees"] == ["a@x.com"]
        assert event["location"] == "Zoom"
        sent = client_session.__aenter__.return_value.get.call_args
        assert sent.kwargs["params"]["$top"] == 100

    def test_get_events_explicit_range_and_naive_times(self, tmp_path):
        svc = make_authed_calendar(tmp_path)
        client_session, response = make_graph_response(200, {"value": []})
        with patch(
            "integrations.outlook_calendar_service.aiohttp.ClientSession",
            return_value=client_session,
        ):
            events = asyncio.run(
                svc.get_events(
                    time_min=datetime(2026, 1, 1, 9, 0),
                    time_max=datetime(2026, 1, 1, 17, 0),
                    max_results=5,
                )
            )
        assert events == []
        params = client_session.__aenter__.return_value.get.call_args.kwargs["params"]
        assert params["$top"] == 5
        assert params["startDateTime"].endswith("+00:00")

    def test_get_events_api_error_returns_empty(self, tmp_path):
        svc = make_authed_calendar(tmp_path)
        client_session, response = make_graph_response(401, text="unauthorized")
        with patch(
            "integrations.outlook_calendar_service.aiohttp.ClientSession",
            return_value=client_session,
        ):
            assert asyncio.run(svc.get_events()) == []

    def test_get_events_exception_returns_empty(self, tmp_path):
        svc = make_authed_calendar(tmp_path)
        client_session, response = make_graph_response(200, {"value": []})
        response.json.side_effect = RuntimeError("boom")
        with patch(
            "integrations.outlook_calendar_service.aiohttp.ClientSession",
            return_value=client_session,
        ):
            assert asyncio.run(svc.get_events()) == []

    def test_get_events_not_authenticated(self, tmp_path):
        svc = make_authed_calendar(tmp_path)
        svc.access_token = None
        svc.token_expiry = None
        with patch.object(svc, "authenticate", return_value=False):
            assert asyncio.run(svc.get_events()) == []

    def test_create_event_success(self, tmp_path):
        svc = make_authed_calendar(tmp_path)
        created = {
            "id": "e2",
            "subject": "New",
            "start": {"dateTime": "2026-01-02T10:00:00Z"},
            "end": {"dateTime": "2026-01-02T11:00:00Z"},
            "location": {"displayName": "Room"},
        }
        client_session, response = make_graph_response(201, created)
        with patch(
            "integrations.outlook_calendar_service.aiohttp.ClientSession",
            return_value=client_session,
        ):
            result = asyncio.run(
                svc.create_event(
                    {
                        "title": "New",
                        "description": "d",
                        "start_time": "2026-01-02T10:00:00Z",
                        "end_time": "2026-01-02T11:00:00Z",
                        "location": "Room",
                        "attendees": ["a@x.com"],
                    }
                )
            )
        assert result["id"] == "e2"
        sent = client_session.__aenter__.return_value.post.call_args
        assert sent.kwargs["json"]["subject"] == "New"
        assert sent.kwargs["json"]["attendees"] == [
            {"emailAddress": {"address": "a@x.com"}, "type": "required"}
        ]

    def test_create_event_api_error_returns_none(self, tmp_path):
        svc = make_authed_calendar(tmp_path)
        client_session, response = make_graph_response(400, text="bad")
        with patch(
            "integrations.outlook_calendar_service.aiohttp.ClientSession",
            return_value=client_session,
        ):
            assert asyncio.run(svc.create_event({"title": "T"})) is None

    def test_update_event_all_fields(self, tmp_path):
        svc = make_authed_calendar(tmp_path)
        updated = {
            "id": "e3",
            "subject": "Updated",
            "start": {"dateTime": "2026-01-03T10:00:00Z"},
            "end": {"dateTime": "2026-01-03T11:00:00Z"},
        }
        client_session, response = make_graph_response(200, updated)
        with patch(
            "integrations.outlook_calendar_service.aiohttp.ClientSession",
            return_value=client_session,
        ):
            result = asyncio.run(
                svc.update_event(
                    "e3",
                    {
                        "title": "Updated",
                        "description": "d2",
                        "start_time": "2026-01-03T10:00:00Z",
                        "end_time": "2026-01-03T11:00:00Z",
                    },
                )
            )
        assert result["id"] == "e3"
        sent = client_session.__aenter__.return_value.patch.call_args
        payload = sent.kwargs["json"]
        assert payload["subject"] == "Updated"
        assert payload["body"]["content"] == "d2"
        assert payload["start"]["dateTime"] == "2026-01-03T10:00:00Z"
        assert payload["end"]["timeZone"] == "UTC"

    def test_update_event_partial_fields_and_error(self, tmp_path):
        svc = make_authed_calendar(tmp_path)
        client_session, response = make_graph_response(200, {"id": "e4"})
        with patch(
            "integrations.outlook_calendar_service.aiohttp.ClientSession",
            return_value=client_session,
        ):
            result = asyncio.run(svc.update_event("e4", {"title": "Only title"}))
        assert result["id"] == "e4"
        client_session2, response2 = make_graph_response(404, text="missing")
        with patch(
            "integrations.outlook_calendar_service.aiohttp.ClientSession",
            return_value=client_session2,
        ):
            assert asyncio.run(svc.update_event("e4", {"title": "x"})) is None

    def test_delete_event_success_and_error(self, tmp_path):
        svc = make_authed_calendar(tmp_path)
        client_session, response = make_graph_response(204)
        with patch(
            "integrations.outlook_calendar_service.aiohttp.ClientSession",
            return_value=client_session,
        ):
            assert asyncio.run(svc.delete_event("e5")) is True
        client_session2, response2 = make_graph_response(500, text="err")
        with patch(
            "integrations.outlook_calendar_service.aiohttp.ClientSession",
            return_value=client_session2,
        ):
            assert asyncio.run(svc.delete_event("e5")) is False

    def test_convert_unified_requires_location_dict(self, tmp_path):
        """DEV-11: location null must not crash conversion."""
        svc = make_authed_calendar(tmp_path)
        raw = {
            "id": "e6",
            "subject": "S",
            "start": {"dateTime": "2026-01-01T10:00:00Z"},
            "end": {"dateTime": "2026-01-01T11:00:00Z"},
            "body": {"content": "c"},
            "attendees": [{"emailAddress": {"address": "a@x.com"}}],
            "location": None,
        }
        converted = svc._convert_outlook_to_unified(raw)
        assert converted["location"] == ""
        assert converted["title"] == "S"

    def test_convert_unified_missing_body(self, tmp_path):
        svc = make_authed_calendar(tmp_path)
        converted = svc._convert_outlook_to_unified(
            {"id": "x", "start": {}, "end": {}, "location": {}}
        )
        assert converted["title"] == "Untitled Event"
        assert converted["description"] == ""
        assert converted["start_time"] == ""
        assert converted["attendees"] == []

    def test_convert_to_outlook_defaults(self, tmp_path):
        svc = make_authed_calendar(tmp_path)
        outlook = svc._convert_unified_to_outlook({"title": "T"})
        assert outlook["subject"] == "T"
        assert outlook["start"]["dateTime"] is None
        assert "location" not in outlook


class TestOutlookCalendarConflicts:
    def test_check_conflicts_finds_overlap_with_naive_input(self, tmp_path):
        """DEV-10: naive datetimes must be normalized before comparison."""
        svc = make_authed_calendar(tmp_path)
        svc.get_events = AsyncMock(
            return_value=[
                {
                    "id": "e1",
                    "title": "Busy",
                    "start_time": "2026-01-01T10:00:00Z",
                    "end_time": "2026-01-01T11:00:00Z",
                }
            ]
        )
        result = asyncio.run(
            svc.check_conflicts(
                datetime(2026, 1, 1, 9, 30), datetime(2026, 1, 1, 12, 0)
            )
        )
        assert result["success"] is True
        assert result["has_conflicts"] is True
        assert result["conflict_count"] == 1
        assert result["conflicts"][0]["event_id"] == "e1"

    def test_check_conflicts_no_overlap(self, tmp_path):
        svc = make_authed_calendar(tmp_path)
        svc.get_events = AsyncMock(
            return_value=[
                {
                    "id": "e1",
                    "title": "Busy",
                    "start_time": "2026-01-01T10:00:00Z",
                    "end_time": "2026-01-01T11:00:00Z",
                }
            ]
        )
        result = asyncio.run(
            svc.check_conflicts(
                datetime(2026, 1, 1, 11, 30, tzinfo=UTC), datetime(2026, 1, 1, 12, 0, tzinfo=UTC)
            )
        )
        assert result["has_conflicts"] is False
        assert result["conflict_count"] == 0

    def test_check_conflicts_not_authenticated(self, tmp_path):
        svc = make_authed_calendar(tmp_path)
        svc.access_token = None
        svc.token_expiry = None
        with patch.object(svc, "authenticate", return_value=False):
            result = asyncio.run(
                svc.check_conflicts(future_dt(), future_dt(minutes=120))
            )
        assert result["has_conflicts"] is False
        assert result["error"] == "Not authenticated"

    def test_check_conflicts_exception(self, tmp_path):
        svc = make_authed_calendar(tmp_path)
        svc.get_events = AsyncMock(side_effect=RuntimeError("boom"))
        result = asyncio.run(svc.check_conflicts(future_dt(), future_dt(minutes=60)))
        assert result["success"] is False
        assert "boom" not in str(result)


class TestOutlookCalendarOps:
    """execute_operation + postgres cache sync."""

    @staticmethod
    @contextmanager
    def _mock_db():
        import core.database as dbmod

        session = MagicMock()
        with patch.object(dbmod, "SessionLocal", return_value=session):
            yield session

    def test_execute_operation_get_events(self, tmp_path):
        svc = make_authed_calendar(tmp_path)
        with patch.object(svc, "get_events", AsyncMock(return_value=[{"id": "e"}])):
            res = asyncio.run(
                svc.execute_operation(
                    "get_events", {"time_min": "x", "time_max": "y", "max_results": 10}
                )
            )
        assert res == {"success": True, "result": [{"id": "e"}]}

    def test_execute_operation_create_event(self, tmp_path):
        svc = make_authed_calendar(tmp_path)
        with patch.object(svc, "create_event", AsyncMock(return_value={"id": "e"})):
            res = asyncio.run(
                svc.execute_operation("create_event", {"event_data": {"title": "T"}})
            )
        assert res == {"success": True, "result": {"id": "e"}}

    def test_execute_operation_update_event(self, tmp_path):
        svc = make_authed_calendar(tmp_path)
        with patch.object(svc, "update_event", AsyncMock(return_value={"id": "e"})):
            res = asyncio.run(
                svc.execute_operation("update_event", {"event_id": "e", "updates": {}})
            )
        assert res == {"success": True, "result": {"id": "e"}}
        with patch.object(svc, "update_event", AsyncMock(return_value=None)):
            res = asyncio.run(
                svc.execute_operation("update_event", {"event_id": "e", "updates": {}})
            )
        assert res["success"] is False

    def test_execute_operation_delete_event(self, tmp_path):
        svc = make_authed_calendar(tmp_path)
        with patch.object(svc, "delete_event", AsyncMock(return_value=True)):
            res = asyncio.run(svc.execute_operation("delete_event", {"event_id": "e"}))
        assert res == {"success": True, "result": None}

    def test_execute_operation_check_conflicts(self, tmp_path):
        svc = make_authed_calendar(tmp_path)
        with patch.object(
            svc, "check_conflicts", AsyncMock(return_value={"has_conflicts": False, "conflicts": []})
        ):
            res = asyncio.run(
                svc.execute_operation(
                    "check_conflicts",
                    {"start_time": "s", "end_time": "e"},
                )
            )
        assert res["success"] is True

    def test_execute_operation_unknown(self, tmp_path):
        svc = make_authed_calendar(tmp_path)
        res = asyncio.run(svc.execute_operation("nope", {}))
        assert res["success"] is False
        assert "get_events" in res["details"]

    def test_execute_operation_tenant_mismatch_returns_error(self, tmp_path):
        """DEV-12: tenant mismatch must not raise out of execute_operation."""
        svc = make_authed_calendar(tmp_path)
        res = asyncio.run(
            svc.execute_operation("get_events", {}, {"tenant_id": "other-tenant"})
        )
        assert res["success"] is False
        assert "mismatch" in res["error"].lower()

    def test_execute_operation_inner_exception_generic(self, tmp_path):
        svc = make_authed_calendar(tmp_path)
        with patch.object(svc, "get_events", AsyncMock(side_effect=RuntimeError("boom"))):
            res = asyncio.run(svc.execute_operation("get_events", {}))
        assert res["success"] is False
        assert "boom" not in str(res)

    def test_sync_to_postgres_cache_success(self, tmp_path):
        svc = make_authed_calendar(tmp_path)
        with self._mock_db() as session:
            session.query.return_value.filter_by.return_value.first.return_value = None
            with patch.object(svc, "get_events", AsyncMock(return_value=[{"id": "e1"}, {"id": "e2"}])):
                result = asyncio.run(svc.sync_to_postgres_cache("ws-1"))
            assert result["success"] is True
            assert result["metrics_synced"] == 1
            metric = session.add.call_args.args[0]
            assert metric.integration_type == "outlook_calendar"
            assert metric.value == 2.0
            session.commit.assert_called_once()

    def test_sync_to_postgres_cache_update_existing(self, tmp_path):
        svc = make_authed_calendar(tmp_path)
        with self._mock_db() as session:
            existing = MagicMock()
            session.query.return_value.filter_by.return_value.first.return_value = existing
            with patch.object(svc, "get_events", AsyncMock(return_value=[])):
                result = asyncio.run(svc.sync_to_postgres_cache("ws-1"))
            assert result["success"] is True
            assert existing.value == 0.0

    def test_sync_to_postgres_cache_commit_failure(self, tmp_path):
        svc = make_authed_calendar(tmp_path)
        with self._mock_db() as session:
            session.commit.side_effect = RuntimeError("boom")
            with patch.object(svc, "get_events", AsyncMock(return_value=[{"id": "e"}])):
                result = asyncio.run(svc.sync_to_postgres_cache("ws-1"))
            assert result["success"] is False
            assert "boom" not in str(result)
            session.rollback.assert_called_once()

    def test_sync_to_postgres_cache_events_failure_uses_zero(self, tmp_path):
        svc = make_authed_calendar(tmp_path)
        with self._mock_db() as session:
            session.query.return_value.filter_by.return_value.first.return_value = None
            with patch.object(svc, "get_events", AsyncMock(side_effect=RuntimeError("boom"))):
                result = asyncio.run(svc.sync_to_postgres_cache("ws-1"))
            assert result["success"] is True
            assert session.add.call_args.args[0].value == 0.0

    def test_full_sync(self, tmp_path):
        svc = make_authed_calendar(tmp_path)
        with patch.object(
            svc, "sync_to_postgres_cache", AsyncMock(return_value={"success": True})
        ):
            result = asyncio.run(svc.full_sync("ws-1"))
        assert result["success"] is True
        assert result["workspace_id"] == "ws-1"
