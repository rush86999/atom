"""
Coverage-push + bug-hunt tests for:
- integrations/github_service.py
- integrations/github_integration.py
- integrations/gitlab_service.py
- integrations/gitlab_routes.py
- integrations/airtable_service.py
- integrations/gmb_automation.py

Bugs surfaced (TDD red -> green):
1. AirtableService missing abstract methods (get_capabilities/execute_operation)
   -> TypeError on instantiation (breaks all callers + pre-existing tests).
2. airtable_service module missing module-level `airtable_service` instance
   -> ImportError in airtable_routes (airtable API surface dead).
3. airtable sync_to_postgres_cache filter_by(tenant_id=...) on IntegrationMetric
   (only workspace_id exists) -> sync always failed.
4. gmb_automation AI branch imports nonexistent integrations.ai_enhanced_service
   -> ModuleNotFoundError whenever ai is configured.
"""

import asyncio
import json
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import httpx
import pytest
from fastapi import HTTPException

from integrations.github_integration import GithubIntegration
from integrations.github_service import GitHubService
from integrations.gitlab_service import GitLabService


def _in_memory_metric_db():
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    engine = create_engine("sqlite:///:memory:")
    from core.database import Base

    import core.models  # noqa: F401

    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)


def _gh_response(payload, status_code=200, exc=None):
    resp = Mock()
    resp.status_code = status_code
    resp.json.return_value = payload
    if exc:
        resp.raise_for_status.side_effect = exc
    else:
        resp.raise_for_status = Mock()
    return resp


# =====================================================================
# GitHubService
# =====================================================================

class TestGitHubService:
    def test_init_default(self):
        from integrations.github_service import GitHubService

        svc = GitHubService()
        assert svc.tenant_id == "default"
        assert svc.access_token is None
        assert svc.base_url == "https://api.github.com"
        assert "Authorization" not in svc.session.headers

    def test_init_with_config(self):
        from integrations.github_service import GitHubService

        svc = GitHubService(tenant_id="t1", config={"access_token": "tok123"})
        assert svc.tenant_id == "t1"
        assert svc.session.headers["Authorization"] == "token tok123"
        assert svc.session.headers["Accept"] == "application/vnd.github.v3+json"

    def test_get_capabilities(self):
        from integrations.github_service import GitHubService

        caps = GitHubService().get_capabilities()
        op_ids = [op["id"] for op in caps["operations"]]
        assert "create_issue" in op_ids and "get_workflow_runs" in op_ids
        assert caps["required_params"] == ["access_token"]

    def test_health_check_ok(self):
        from integrations.github_service import GitHubService

        svc = GitHubService(config={"access_token": "t"})
        svc.session.get = Mock(return_value=_gh_response({"login": "octo"}))
        result = svc.health_check()
        assert result["healthy"] is True
        assert result["user"] == "octo"
        assert "last_check" in result

    def test_health_check_auth_failed(self):
        from integrations.github_service import GitHubService

        svc = GitHubService(config={"access_token": "t"})
        svc.session.get = Mock(return_value=_gh_response({}, status_code=401))
        result = svc.health_check()
        assert result["healthy"] is False
        assert "401" in result["message"]

    def test_health_check_exception(self):
        from integrations.github_service import GitHubService

        svc = GitHubService(config={"access_token": "t"})
        svc.session.get = Mock(side_effect=ValueError("boom"))
        result = svc.health_check()
        assert result["healthy"] is False
        assert "boom" not in json.dumps(result)

    def test_test_connection_ok(self):
        from integrations.github_service import GitHubService

        svc = GitHubService(config={"access_token": "t"})
        svc.session.get = Mock(return_value=_gh_response({"login": "octo"}))
        result = svc.test_connection()
        assert result["status"] == "success"
        assert result["authenticated"] is True

    def test_test_connection_failed(self):
        from integrations.github_service import GitHubService

        svc = GitHubService(config={"access_token": "t"})
        svc.session.get = Mock(return_value=_gh_response({}, status_code=403))
        result = svc.test_connection()
        assert result["status"] == "error"
        assert result["authenticated"] is False

    def test_test_connection_exception(self):
        from integrations.github_service import GitHubService

        svc = GitHubService(config={"access_token": "t"})
        svc.session.get = Mock(side_effect=RuntimeError("conn"))
        result = svc.test_connection()
        assert result["status"] == "error"
        assert result["message"] == "GitHub connection test failed"

    def test_get_user_repositories_ok(self):
        from integrations.github_service import GitHubService

        svc = GitHubService(config={"access_token": "t"})
        repos = [{"full_name": "a/b"}]
        svc.session.get = Mock(return_value=_gh_response(repos))
        result = svc.get_user_repositories(type="owner")
        assert result == repos
        svc.session.get.assert_called_once()
        assert svc.session.get.call_args[1]["params"]["type"] == "owner"

    def test_get_user_repositories_error(self):
        from integrations.github_service import GitHubService

        svc = GitHubService(config={"access_token": "t"})
        svc.session.get = Mock(return_value=_gh_response([], exc=httpx.HTTPError("x")))
        assert svc.get_user_repositories() == []

    def test_get_repository_ok(self):
        from integrations.github_service import GitHubService

        svc = GitHubService(config={"access_token": "t"})
        repo = {"full_name": "a/b", "stargazers_count": 5}
        svc.session.get = Mock(return_value=_gh_response(repo))
        assert svc.get_repository("a", "b") == repo

    def test_get_repository_error(self):
        from integrations.github_service import GitHubService

        svc = GitHubService(config={"access_token": "t"})
        svc.session.get = Mock(return_value=_gh_response(None, exc=httpx.HTTPError("x")))
        assert svc.get_repository("a", "b") is None

    def test_get_repository_issues_ok(self):
        from integrations.github_service import GitHubService

        svc = GitHubService(config={"access_token": "t"})
        issues = [{"number": 1}]
        svc.session.get = Mock(return_value=_gh_response(issues))
        assert svc.get_repository_issues("a", "b", state="closed") == issues

    def test_get_repository_issues_error(self):
        from integrations.github_service import GitHubService

        svc = GitHubService(config={"access_token": "t"})
        svc.session.get = Mock(return_value=_gh_response([], exc=httpx.HTTPError("x")))
        assert svc.get_repository_issues("a", "b") == []

    def test_get_repository_pulls_ok(self):
        from integrations.github_service import GitHubService

        svc = GitHubService(config={"access_token": "t"})
        pulls = [{"number": 7}]
        svc.session.get = Mock(return_value=_gh_response(pulls))
        assert svc.get_repository_pulls("a", "b") == pulls

    def test_get_repository_pulls_error(self):
        from integrations.github_service import GitHubService

        svc = GitHubService(config={"access_token": "t"})
        svc.session.get = Mock(return_value=_gh_response([], exc=httpx.HTTPError("x")))
        assert svc.get_repository_pulls("a", "b") == []

    def test_create_issue_ok(self):
        from integrations.github_service import GitHubService

        svc = GitHubService(config={"access_token": "t"})
        issue = {"number": 2}
        svc.session.post = Mock(return_value=_gh_response(issue))
        result = svc.create_issue("a", "b", "Title", "Body", ["bug"])
        assert result == issue
        payload = svc.session.post.call_args[1]["json"]
        assert payload["labels"] == ["bug"]

    def test_create_issue_error(self):
        from integrations.github_service import GitHubService

        svc = GitHubService(config={"access_token": "t"})
        svc.session.post = Mock(return_value=_gh_response(None, exc=httpx.HTTPError("x")))
        assert svc.create_issue("a", "b", "Title") is None

    def test_create_pull_request_ok(self):
        from integrations.github_service import GitHubService

        svc = GitHubService(config={"access_token": "t"})
        pr = {"number": 3}
        svc.session.post = Mock(return_value=_gh_response(pr))
        result = svc.create_pull_request("a", "b", "T", "feat", "main", "Body")
        assert result == pr
        payload = svc.session.post.call_args[1]["json"]
        assert payload["head"] == "feat" and payload["base"] == "main"

    def test_create_pull_request_error(self):
        from integrations.github_service import GitHubService

        svc = GitHubService(config={"access_token": "t"})
        svc.session.post = Mock(return_value=_gh_response(None, exc=httpx.HTTPError("x")))
        assert svc.create_pull_request("a", "b", "T", "f", "m") is None

    def test_get_user_commits_with_since(self):
        from integrations.github_service import GitHubService

        svc = GitHubService(config={"access_token": "t"})
        commits = [{"sha": "abc"}]
        svc.session.get = Mock(return_value=_gh_response(commits))
        since = datetime(2026, 1, 1, tzinfo=timezone.utc)
        assert svc.get_user_commits("a", "b", since=since) == commits
        assert "since" in svc.session.get.call_args[1]["params"]

    def test_get_user_commits_no_since(self):
        from integrations.github_service import GitHubService

        svc = GitHubService(config={"access_token": "t"})
        svc.session.get = Mock(return_value=_gh_response([]))
        assert svc.get_user_commits("a", "b") == []
        assert "since" not in svc.session.get.call_args[1]["params"]

    def test_get_user_commits_error(self):
        from integrations.github_service import GitHubService

        svc = GitHubService(config={"access_token": "t"})
        svc.session.get = Mock(return_value=_gh_response([], exc=httpx.HTTPError("x")))
        assert svc.get_user_commits("a", "b") == []

    def test_get_workflow_runs_ok(self):
        from integrations.github_service import GitHubService

        svc = GitHubService(config={"access_token": "t"})
        svc.session.get = Mock(return_value=_gh_response({"workflow_runs": [{"id": 1}]}))
        assert svc.get_workflow_runs("a", "b") == [{"id": 1}]

    def test_get_workflow_runs_error(self):
        from integrations.github_service import GitHubService

        svc = GitHubService(config={"access_token": "t"})
        svc.session.get = Mock(return_value=_gh_response(None, exc=httpx.HTTPError("x")))
        assert svc.get_workflow_runs("a", "b") == []

    def test_get_repository_stats_ok(self):
        from integrations.github_service import GitHubService

        svc = GitHubService(config={"access_token": "t"})
        svc.get_repository = Mock(
            return_value={
                "full_name": "a/b",
                "stargazers_count": 10,
                "forks_count": 2,
                "open_issues_count": 3,
                "language": "Python",
                "updated_at": "u",
                "created_at": "c",
            }
        )
        svc.get_repository_issues = Mock(return_value=[{"n": 1}, {"n": 2}])
        svc.get_repository_pulls = Mock(return_value=[{"n": 1}])
        stats = svc.get_repository_stats("a", "b")
        assert stats["name"] == "a/b"
        assert stats["total_issues"] == 2
        assert stats["total_prs"] == 1
        assert stats["stars"] == 10

    def test_get_repository_stats_missing_repo(self):
        from integrations.github_service import GitHubService

        svc = GitHubService(config={"access_token": "t"})
        svc.get_repository = Mock(return_value=None)
        assert svc.get_repository_stats("a", "b") == {}

    def test_get_repository_stats_exception(self):
        from integrations.github_service import GitHubService

        svc = GitHubService(config={"access_token": "t"})
        svc.get_repository = Mock(side_effect=ValueError("boom"))
        assert svc.get_repository_stats("a", "b") == {}

    def test_search_repositories_ok(self):
        from integrations.github_service import GitHubService

        svc = GitHubService(config={"access_token": "t"})
        svc.session.get = Mock(return_value=_gh_response({"items": [{"id": 1}]}))
        assert svc.search_repositories("atom") == [{"id": 1}]

    def test_search_repositories_error(self):
        from integrations.github_service import GitHubService

        svc = GitHubService(config={"access_token": "t"})
        svc.session.get = Mock(return_value=_gh_response(None, exc=httpx.HTTPError("x")))
        assert svc.search_repositories("atom") == []

    def test_get_user_profile_ok(self):
        from integrations.github_service import GitHubService

        svc = GitHubService(config={"access_token": "t"})
        svc.session.get = Mock(return_value=_gh_response({"login": "octo"}))
        assert svc.get_user_profile() == {"login": "octo"}

    def test_get_user_profile_error(self):
        from integrations.github_service import GitHubService

        svc = GitHubService(config={"access_token": "t"})
        svc.session.get = Mock(return_value=_gh_response(None, exc=httpx.HTTPError("x")))
        assert svc.get_user_profile() is None

    def test_sync_to_postgres_cache_new_metric(self):
        from integrations.github_service import GitHubService

        svc = GitHubService(config={"access_token": "t"})
        svc.get_user_repositories = Mock(return_value=[{"full_name": "a/b"}])
        with patch("core.database.SessionLocal", _in_memory_metric_db()):
            result = svc.sync_to_postgres_cache("ws-1")
        assert result["success"] is True
        assert result["metrics_synced"] == 1

    def test_sync_to_postgres_cache_updates_existing(self):
        from integrations.github_service import GitHubService

        SessionLocal = _in_memory_metric_db()
        db = SessionLocal()
        from core.models import IntegrationMetric

        db.add(
            IntegrationMetric(
                workspace_id="ws-1",
                integration_type="github",
                metric_key="github_repository_count",
                value=1.0,
                unit="count",
            )
        )
        db.commit()
        db.close()

        svc = GitHubService(config={"access_token": "t"})
        svc.get_user_repositories = Mock(return_value=[{"f": "a"}, {"f": "b"}])
        with patch("core.database.SessionLocal", SessionLocal):
            result = svc.sync_to_postgres_cache("ws-1")
        assert result["success"] is True
        db = SessionLocal()
        row = (
            db.query(IntegrationMetric)
            .filter_by(workspace_id="ws-1")
            .first()
        )
        assert row.value == 2.0
        db.close()

    def test_sync_to_postgres_cache_db_error(self):
        from integrations.github_service import GitHubService

        svc = GitHubService(config={"access_token": "t"})
        svc.get_user_repositories = Mock(return_value=[])
        fake_db = Mock()
        fake_db.query.return_value.filter_by.return_value.first.side_effect = Exception(
            "db boom"
        )
        with patch("core.database.SessionLocal", Mock(return_value=fake_db)):
            result = svc.sync_to_postgres_cache("ws-1")
        assert result == {"success": False, "error": "Failed to save GitHub metrics"}
        fake_db.rollback.assert_called_once()
        fake_db.close.assert_called_once()

    def test_sync_to_postgres_cache_outer_error(self):
        from integrations.github_service import GitHubService

        svc = GitHubService(config={"access_token": "t"})
        svc.get_user_repositories = Mock(side_effect=ValueError("boom"))
        with patch("core.database.SessionLocal", _in_memory_metric_db()):
            result = svc.sync_to_postgres_cache("ws-1")
        assert result == {"success": False, "error": "GitHub cache sync failed"}

    def test_full_sync(self):
        from integrations.github_service import GitHubService

        svc = GitHubService(config={"access_token": "t"})
        svc.sync_to_postgres_cache = Mock(return_value={"success": True})
        result = svc.full_sync("ws-1")
        assert result["success"] is True
        assert result["workspace_id"] == "ws-1"
        assert result["postgres_cache"]["success"] is True

    @pytest.mark.parametrize(
        "op,method,args",
        [
            ("list_repositories", "get_user_repositories", {"type": "all"}),
            ("list_issues", "get_repository_issues", {"owner": "a", "repo": "b", "state": "open"}),
            ("list_pulls", "get_repository_pulls", {"owner": "a", "repo": "b", "state": "open"}),
            ("search_repositories", "search_repositories", {"query": "", "sort": "updated", "order": "desc"}),
            ("get_commits", "get_user_commits", {"owner": "a", "repo": "b", "since": None}),
            ("get_workflow_runs", "get_workflow_runs", {"owner": "a", "repo": "b"}),
        ],
    )
    def test_execute_operation_listing(self, op, method, args):
        from integrations.github_service import GitHubService

        svc = GitHubService(config={"access_token": "t"})
        setattr(svc, method, Mock(return_value=[{"id": 1}]))
        result = asyncio.run(svc.execute_operation(op, args))
        assert result["success"] is True
        assert result["result"] == [{"id": 1}]

    def test_execute_operation_get_repository(self):
        from integrations.github_service import GitHubService

        svc = GitHubService(config={"access_token": "t"})
        svc.get_repository = Mock(return_value={"full_name": "a/b"})
        result = asyncio.run(svc.execute_operation("get_repository", {"owner": "a", "repo": "b"}))
        assert result["success"] is True
        svc.get_repository = Mock(return_value=None)
        result = asyncio.run(svc.execute_operation("get_repository", {"owner": "a", "repo": "b"}))
        assert result["success"] is False

    def test_execute_operation_create_issue_and_pull(self):
        from integrations.github_service import GitHubService

        svc = GitHubService(config={"access_token": "t"})
        svc.create_issue = Mock(return_value={"number": 1})
        result = asyncio.run(
            svc.execute_operation("create_issue", {"owner": "a", "repo": "b", "title": "T"})
        )
        assert result["success"] is True
        svc.create_pull_request = Mock(return_value=None)
        result = asyncio.run(
            svc.execute_operation("create_pull", {"owner": "a", "repo": "b", "title": "T", "head": "f", "base": "m"})
        )
        assert result["success"] is False

    def test_execute_operation_unknown(self):
        from integrations.github_service import GitHubService

        svc = GitHubService(config={"access_token": "t"})
        result = asyncio.run(svc.execute_operation("nope", {}))
        assert result["success"] is False
        assert "Unknown operation" in result["error"]

    def test_execute_operation_tenant_mismatch(self):
        from integrations.github_service import GitHubService

        svc = GitHubService(tenant_id="t1", config={"access_token": "t"})
        result = asyncio.run(
            svc.execute_operation("list_repositories", {}, context={"tenant_id": "t2"})
        )
        assert result["success"] is False
        assert result["error"] == "Tenant ID mismatch"

    def test_execute_operation_exception(self):
        from integrations.github_service import GitHubService

        svc = GitHubService(config={"access_token": "t"})
        svc.get_user_repositories = Mock(side_effect=ValueError("boom"))
        result = asyncio.run(svc.execute_operation("list_repositories", {}))
        assert result["success"] is False
        assert "boom" not in json.dumps(result)


# =====================================================================
# GithubIntegration
# =====================================================================

class TestGithubIntegration:
    def test_init_and_env(self):
        with patch.dict(
            "os.environ",
            {"GITHUB_CLIENT_ID": "cid", "GITHUB_CLIENT_SECRET": "csec"},
            clear=False,
        ):
            gi = GithubIntegration()
        assert gi.client_id == "cid"
        assert gi.client_secret == "csec"
        assert gi.access_token is None

    def test_set_access_token(self):
        gi = GithubIntegration()
        gi.set_access_token("tok")
        assert gi.access_token == "tok"

    def test_get_headers_with_token(self):
        gi = GithubIntegration()
        gi.set_access_token("tok")
        headers = gi.get_headers()
        assert headers["Authorization"] == "token tok"

    def test_get_headers_without_token(self):
        gi = GithubIntegration()
        headers = gi.get_headers()
        assert "Authorization" not in headers

    def test_get_user_info_ok(self):
        gi = GithubIntegration()
        with patch(
            "integrations.github_integration.requests.get",
            return_value=_gh_response({"login": "octo"}),
        ):
            result = asyncio.run(gi.get_user_info())
        assert result == {"login": "octo"}

    def test_get_user_info_non_200(self):
        gi = GithubIntegration()
        with patch(
            "integrations.github_integration.requests.get",
            return_value=_gh_response({}, status_code=404),
        ):
            result = asyncio.run(gi.get_user_info())
        assert result is None

    def test_get_user_info_exception(self):
        gi = GithubIntegration()
        with patch(
            "integrations.github_integration.requests.get",
            side_effect=ValueError("boom"),
        ):
            result = asyncio.run(gi.get_user_info())
        assert result is None

    def test_list_items_ok(self):
        gi = GithubIntegration()
        with patch(
            "integrations.github_integration.requests.get",
            return_value=_gh_response([{"id": 1}]),
        ):
            result = asyncio.run(gi.list_items())
        assert result == [{"id": 1}]

    def test_list_items_non_200(self):
        gi = GithubIntegration()
        with patch(
            "integrations.github_integration.requests.get",
            return_value=_gh_response([], status_code=500),
        ):
            assert asyncio.run(gi.list_items()) == []

    def test_list_items_exception(self):
        gi = GithubIntegration()
        with patch(
            "integrations.github_integration.requests.get",
            side_effect=RuntimeError("boom"),
        ):
            assert asyncio.run(gi.list_items()) == []

    def test_create_item_ok(self):
        gi = GithubIntegration()
        with patch(
            "integrations.github_integration.requests.post",
            return_value=_gh_response({"id": 1}, status_code=201),
        ):
            result = asyncio.run(gi.create_item({"name": "x"}))
        assert result == {"id": 1}

    def test_create_item_non_2xx(self):
        gi = GithubIntegration()
        with patch(
            "integrations.github_integration.requests.post",
            return_value=_gh_response(None, status_code=422),
        ):
            assert asyncio.run(gi.create_item({"name": "x"})) is None

    def test_create_item_exception(self):
        gi = GithubIntegration()
        with patch(
            "integrations.github_integration.requests.post",
            side_effect=ValueError("boom"),
        ):
            assert asyncio.run(gi.create_item({"name": "x"})) is None

    def test_endpoints(self):
        gi = GithubIntegration()
        assert gi._get_user_endpoint() == "https://api.github.com/user"
        assert gi._get_list_endpoint() == "https://api.github.com/user/repos"
        assert gi._get_create_endpoint() == "https://api.github.com/user/repos"

    def test_global_instance(self):
        from integrations.github_integration import github_integration

        assert isinstance(github_integration, GithubIntegration)


# =====================================================================
# GitLabService
# =====================================================================

class TestGitLabService:
    def test_init_with_config(self):
        svc = GitLabService(
            tenant_id="t1", config={"client_id": "c1", "client_secret": "s1"}
        )
        assert svc.tenant_id == "t1"
        assert svc.client_id == "c1"
        assert svc.client_secret == "s1"
        assert svc.base_url == "https://gitlab.com/api/v4"

    def test_init_env_fallback(self):
        with patch.dict(
            "os.environ",
            {"GITLAB_CLIENT_ID": "ec", "GITLAB_CLIENT_SECRET": "es"},
            clear=False,
        ):
            svc = GitLabService()
        assert svc.client_id == "ec"
        assert svc.client_secret == "es"

    def test_get_capabilities(self):
        caps = GitLabService().get_capabilities()
        op_ids = [op["id"] for op in caps["operations"]]
        assert "get_user" in op_ids and "sync_metrics" in op_ids

    def test_health_check_configured(self):
        svc = GitLabService(config={"client_id": "c", "client_secret": "s"})
        result = svc.health_check()
        assert result["healthy"] is True

    def test_health_check_not_configured(self):
        with patch.dict("os.environ", {}, clear=True):
            svc = GitLabService()
        svc.client_id = None
        result = svc.health_check()
        assert result["healthy"] is False
        assert "not configured" in result["message"]

    def test_get_headers(self):
        svc = GitLabService()
        headers = svc._get_headers("tok")
        assert headers["Authorization"] == "Bearer tok"
        assert headers["Accept"] == "application/json"

    def test_exchange_token_ok(self):
        svc = GitLabService(config={"client_id": "c", "client_secret": "s"})
        svc.client.post = AsyncMock(return_value=_gh_response({"access_token": "at"}))
        result = asyncio.run(svc.exchange_token("code", "http://cb"))
        assert result == {"access_token": "at"}
        posted = svc.client.post.call_args[1]["data"]
        assert posted["grant_type"] == "authorization_code"
        assert posted["client_id"] == "c"

    def test_exchange_token_http_error(self):
        svc = GitLabService(config={"client_id": "c", "client_secret": "s"})
        resp = Mock()
        resp.raise_for_status.side_effect = httpx.HTTPStatusError(
            "400", request=httpx.Request("POST", "https://gitlab.com/oauth/token"), response=httpx.Response(400)
        )
        svc.client.post = AsyncMock(return_value=resp)
        with pytest.raises(HTTPException) as exc_info:
            asyncio.run(svc.exchange_token("code", "http://cb"))
        assert exc_info.value.status_code == 400

    def test_get_user_ok(self):
        svc = GitLabService()
        svc.client.get = AsyncMock(return_value=_gh_response({"username": "gl"}))
        assert asyncio.run(svc.get_user("tok")) == {"username": "gl"}

    def test_get_user_error(self):
        svc = GitLabService()
        resp = Mock()
        resp.raise_for_status.side_effect = httpx.ConnectError("no route")
        svc.client.get = AsyncMock(return_value=resp)
        with pytest.raises(HTTPException) as exc_info:
            asyncio.run(svc.get_user("tok"))
        assert exc_info.value.status_code == 500

    def test_get_projects_ok(self):
        svc = GitLabService()
        svc.client.get = AsyncMock(return_value=_gh_response([{"id": 1}]))
        result = asyncio.run(svc.get_projects("tok", limit=5, membership=False))
        assert result == [{"id": 1}]
        params = svc.client.get.call_args[1]["params"]
        assert params["per_page"] == 5
        assert params["membership"] == "false"

    def test_get_projects_error(self):
        svc = GitLabService()
        resp = Mock()
        resp.raise_for_status.side_effect = httpx.ConnectError("no route")
        svc.client.get = AsyncMock(return_value=resp)
        with pytest.raises(HTTPException):
            asyncio.run(svc.get_projects("tok"))

    def test_get_issues_project(self):
        svc = GitLabService()
        svc.client.get = AsyncMock(return_value=_gh_response([{"iid": 1}]))
        result = asyncio.run(svc.get_issues("tok", project_id="42", limit=3))
        assert result == [{"iid": 1}]
        assert "/projects/42/issues" in svc.client.get.call_args[0][0]

    def test_get_issues_global(self):
        svc = GitLabService()
        svc.client.get = AsyncMock(return_value=_gh_response([]))
        assert asyncio.run(svc.get_issues("tok", limit=3)) == []
        assert svc.client.get.call_args[0][0].endswith("/issues")

    def test_get_issues_error(self):
        svc = GitLabService()
        resp = Mock()
        resp.raise_for_status.side_effect = httpx.ConnectError("no route")
        svc.client.get = AsyncMock(return_value=resp)
        with pytest.raises(HTTPException):
            asyncio.run(svc.get_issues("tok", project_id="42"))

    def test_search_projects_ok(self):
        svc = GitLabService()
        svc.client.get = AsyncMock(return_value=_gh_response([{"id": 1}]))
        assert asyncio.run(svc.search_projects("tok", "atom")) == [{"id": 1}]

    def test_search_projects_error(self):
        svc = GitLabService()
        resp = Mock()
        resp.raise_for_status.side_effect = httpx.ConnectError("no route")
        svc.client.get = AsyncMock(return_value=resp)
        with pytest.raises(HTTPException):
            asyncio.run(svc.search_projects("tok", "atom"))

    @pytest.mark.parametrize(
        "op,method",
        [
            ("get_user", "get_user"),
            ("list_projects", "get_projects"),
            ("list_issues", "get_issues"),
            ("search_projects", "search_projects"),
        ],
    )
    def test_execute_operation_dispatch(self, op, method):
        svc = GitLabService()
        setattr(svc, method, AsyncMock(return_value=[{"id": 1}]))
        result = asyncio.run(svc.execute_operation(op, {"access_token": "tok"}))
        assert result["success"] is True
        assert result["result"] == [{"id": 1}]

    def test_execute_operation_sync_metrics(self):
        svc = GitLabService()
        svc.sync_to_postgres_cache = AsyncMock(
            return_value={"success": True, "metrics_synced": 1}
        )
        result = asyncio.run(
            svc.execute_operation("sync_metrics", {"access_token": "tok", "workspace_id": "ws"})
        )
        assert result["success"] is True
        assert result["result"]["metrics_synced"] == 1

    def test_execute_operation_unknown(self):
        svc = GitLabService()
        result = asyncio.run(svc.execute_operation("nope", {}))
        assert result["success"] is False
        assert "Unknown operation" in result["error"]

    def test_execute_operation_tenant_mismatch(self):
        svc = GitLabService(tenant_id="t1")
        result = asyncio.run(
            svc.execute_operation("get_user", {}, context={"tenant_id": "t2"})
        )
        assert result["success"] is False
        assert result["error"] == "Tenant ID mismatch"

    def test_execute_operation_exception(self):
        svc = GitLabService()
        svc.get_user = AsyncMock(side_effect=ValueError("boom"))
        result = asyncio.run(svc.execute_operation("get_user", {"access_token": "tok"}))
        assert result["success"] is False
        assert "boom" not in json.dumps(result)

    def test_sync_to_postgres_cache_ok(self):
        svc = GitLabService()
        svc.get_projects = AsyncMock(return_value=[{"id": 1}, {"id": 2}])
        with patch("core.database.SessionLocal", _in_memory_metric_db()):
            result = asyncio.run(svc.sync_to_postgres_cache("ws-1", "tok"))
        assert result["success"] is True
        assert result["metrics_synced"] == 1

    def test_sync_to_postgres_cache_updates_existing(self):
        SessionLocal = _in_memory_metric_db()
        db = SessionLocal()
        from core.models import IntegrationMetric

        db.add(
            IntegrationMetric(
                workspace_id="ws-9",
                integration_type="gitlab",
                metric_key="gitlab_project_count",
                value=1.0,
                unit="count",
            )
        )
        db.commit()
        db.close()

        svc = GitLabService()
        svc.get_projects = AsyncMock(return_value=[{"id": 1}, {"id": 2}, {"id": 3}])
        with patch("core.database.SessionLocal", SessionLocal):
            result = asyncio.run(svc.sync_to_postgres_cache("ws-9", "tok"))
        assert result["success"] is True
        db = SessionLocal()
        row = (
            db.query(IntegrationMetric)
            .filter_by(workspace_id="ws-9", integration_type="gitlab")
            .first()
        )
        assert row.value == 3.0
        db.close()

    def test_sync_to_postgres_cache_db_error(self):
        svc = GitLabService()
        svc.get_projects = AsyncMock(return_value=[])
        fake_db = Mock()
        fake_db.query.return_value.filter_by.return_value.first.side_effect = Exception(
            "db boom"
        )
        with patch("core.database.SessionLocal", Mock(return_value=fake_db)):
            result = asyncio.run(svc.sync_to_postgres_cache("ws-1", "tok"))
        assert result == {"success": False, "error": "Failed to save GitLab metrics"}
        fake_db.rollback.assert_called_once()

    def test_sync_to_postgres_cache_outer_error(self):
        svc = GitLabService()
        svc.get_projects = AsyncMock(side_effect=ValueError("boom"))
        with patch("core.database.SessionLocal", _in_memory_metric_db()):
            result = asyncio.run(svc.sync_to_postgres_cache("ws-1", "tok"))
        assert result == {"success": False, "error": "GitLab cache sync failed"}

    def test_full_sync(self):
        svc = GitLabService()
        svc.sync_to_postgres_cache = AsyncMock(return_value={"success": True})
        result = asyncio.run(svc.full_sync("ws-1", "tok"))
        assert result["success"] is True
        assert result["workspace_id"] == "ws-1"


# =====================================================================
# gitlab_routes
# =====================================================================

class TestGitLabRoutes:
    @pytest.fixture
    def routes(self):
        import integrations.gitlab_routes as routes

        return routes

    def test_get_auth_url(self, routes):
        result = asyncio.run(routes.get_auth_url())
        assert "oauth/authorize" in result["url"]
        assert "timestamp" in result

    def test_auth_callback_ok(self, routes):
        with patch.object(
            routes.gitlab_service,
            "exchange_token",
            new=AsyncMock(return_value={"access_token": "at"}),
        ):
            result = asyncio.run(
                routes.gitlab_auth_callback(
                    routes.GitlabAuthRequest(code="c", redirect_uri="http://cb")
                )
            )
        assert result["ok"] is True
        assert result["service"] == "gitlab"
        assert result["data"]["access_token"] == "at"

    def test_auth_callback_error(self, routes):
        with patch.object(
            routes.gitlab_service,
            "exchange_token",
            new=AsyncMock(side_effect=HTTPException(status_code=400, detail="bad")),
        ):
            with pytest.raises(HTTPException) as exc_info:
                asyncio.run(
                    routes.gitlab_auth_callback(
                        routes.GitlabAuthRequest(code="c", redirect_uri="http://cb")
                    )
                )
        assert exc_info.value.status_code == 400

    def test_get_user(self, routes):
        with patch.object(
            routes.gitlab_service, "get_user", new=AsyncMock(return_value={"username": "gl"})
        ):
            result = asyncio.run(routes.get_user(access_token="tok"))
        assert result == {"ok": True, "data": {"username": "gl"}}

    def test_list_projects(self, routes):
        with patch.object(
            routes.gitlab_service, "get_projects", new=AsyncMock(return_value=[{"id": 1}])
        ):
            result = asyncio.run(routes.list_projects(access_token="tok", limit=10))
        assert result["ok"] is True
        assert result["count"] == 1

    def test_list_issues(self, routes):
        with patch.object(
            routes.gitlab_service,
            "get_issues",
            new=AsyncMock(return_value=[{"iid": 1}, {"iid": 2}]),
        ):
            result = asyncio.run(
                routes.list_issues(access_token="tok", project_id="42", limit=10)
            )
        assert result["count"] == 2

    def test_list_issues_no_project(self, routes):
        with patch.object(
            routes.gitlab_service, "get_issues", new=AsyncMock(return_value=[])
        ):
            result = asyncio.run(
                routes.list_issues(access_token="tok", project_id=None, limit=10)
            )
        assert result["count"] == 0

    def test_gitlab_search(self, routes):
        with patch.object(
            routes.gitlab_service,
            "search_projects",
            new=AsyncMock(return_value=[{"id": 1}]),
        ):
            result = asyncio.run(
                routes.gitlab_search(
                    request=routes.GitlabSearchRequest(query="atom"),
                    access_token="tok",
                )
            )
        assert result["query"] == "atom"
        assert result["count"] == 1

    def test_gitlab_status(self, routes):
        result = asyncio.run(routes.gitlab_status())
        assert result["ok"] is True
        assert result["status"] == "active"

    def test_gitlab_root(self, routes):
        result = asyncio.run(routes.gitlab_root())
        assert result["service"] == "gitlab"
        assert "/auth/callback" in result["endpoints"]


# =====================================================================
# AirtableService  (bugs: abstract methods, missing module instance,
#                    tenant_id filter, str(e) leaks)
# =====================================================================

class TestAirtableService:
    @pytest.fixture
    def svc(self):
        from integrations.airtable_service import AirtableService

        service = AirtableService(config={"api_key": "key123"})
        yield service
        asyncio.run(service.close())

    def _air_resp(self, payload, exc=None):
        resp = Mock()
        resp.json.return_value = payload
        if exc:
            resp.raise_for_status.side_effect = exc
        else:
            resp.raise_for_status = Mock()
        return resp

    def test_init(self):
        from integrations.airtable_service import AirtableService

        svc = AirtableService(tenant_id="t1", config={"api_key": "k"})
        assert svc.tenant_id == "t1"
        assert svc.api_key == "k"
        assert svc.base_url == "https://api.airtable.com/v0"

    def test_module_level_instance_exists(self):
        from integrations.airtable_service import airtable_service

        assert airtable_service is not None
        assert airtable_service.base_url == "https://api.airtable.com/v0"

    def test_get_capabilities(self):
        from integrations.airtable_service import AirtableService

        svc = AirtableService(config={"api_key": "k"})
        caps = svc.get_capabilities()
        op_ids = [op["id"] for op in caps["operations"]]
        assert "get_bases" in op_ids and "delete_record" in op_ids

    def test_close(self):
        from integrations.airtable_service import AirtableService

        svc = AirtableService(config={"api_key": "k"})
        svc.client.aclose = AsyncMock()
        asyncio.run(svc.close())
        svc.client.aclose.assert_called_once()

    def test_get_headers_with_token(self, svc):
        headers = svc._get_headers("custom")
        assert headers["Authorization"] == "Bearer custom"
        assert headers["Content-Type"] == "application/json"

    def test_get_headers_default(self, svc):
        headers = svc._get_headers()
        assert headers["Authorization"] == "Bearer key123"

    def test_get_bases_ok(self, svc):
        svc.http.get = AsyncMock(
            return_value=self._air_resp({"bases": [{"id": "b1"}, {"id": "b2"}]})
        )
        result = asyncio.run(svc.get_bases())
        assert len(result) == 2

    def test_get_bases_error(self, svc):
        svc.http.get = AsyncMock(
            return_value=self._air_resp({}, exc=httpx.HTTPError("boom"))
        )
        assert asyncio.run(svc.get_bases()) == []

    def test_get_tables_ok(self, svc):
        svc.http.get = AsyncMock(return_value=self._air_resp({"tables": [{"id": "t1"}]}))
        assert asyncio.run(svc.get_tables("b1")) == [{"id": "t1"}]

    def test_get_tables_error(self, svc):
        svc.http.get = AsyncMock(
            return_value=self._air_resp({}, exc=httpx.HTTPError("boom"))
        )
        assert asyncio.run(svc.get_tables("b1")) == []

    def test_list_records_ok_with_filters(self, svc):
        svc.http.get = AsyncMock(
            return_value=self._air_resp({"records": [{"id": "r1"}]})
        )
        result = asyncio.run(
            svc.list_records("b1", "T", max_records=50, view="Grid", filter_formula="{X}=1")
        )
        assert result == [{"id": "r1"}]
        params = svc.http.get.call_args[1]["params"]
        assert params["maxRecords"] == 50
        assert params["view"] == "Grid"
        assert params["filterByFormula"] == "{X}=1"

    def test_list_records_no_api_key(self):
        from integrations.airtable_service import AirtableService

        svc = AirtableService(config={"api_key": None})
        with pytest.raises(HTTPException) as exc_info:
            asyncio.run(svc.list_records("b1", "T"))
        assert exc_info.value.status_code == 401

    def test_list_records_http_error(self, svc):
        svc.http.get = AsyncMock(
            return_value=self._air_resp({}, exc=httpx.HTTPError("boom"))
        )
        with pytest.raises(HTTPException) as exc_info:
            asyncio.run(svc.list_records("b1", "T"))
        assert exc_info.value.status_code == 400

    def test_get_record_ok(self, svc):
        svc.http.get = AsyncMock(return_value=self._air_resp({"id": "r1"}))
        assert asyncio.run(svc.get_record("b1", "T", "r1")) == {"id": "r1"}

    def test_get_record_no_api_key(self):
        from integrations.airtable_service import AirtableService

        svc = AirtableService(config={"api_key": None})
        with pytest.raises(HTTPException) as exc_info:
            asyncio.run(svc.get_record("b1", "T", "r1"))
        assert exc_info.value.status_code == 401

    def test_get_record_http_error(self, svc):
        svc.http.get = AsyncMock(
            return_value=self._air_resp({}, exc=httpx.HTTPError("boom"))
        )
        with pytest.raises(HTTPException) as exc_info:
            asyncio.run(svc.get_record("b1", "T", "r1"))
        assert exc_info.value.status_code == 400

    def test_create_record_ok(self, svc):
        svc.http.post = AsyncMock(return_value=self._air_resp({"id": "r1"}))
        result = asyncio.run(svc.create_record("b1", "T", {"Name": "X"}))
        assert result["id"] == "r1"
        assert svc.http.post.call_args[1]["json"] == {"fields": {"Name": "X"}}

    def test_create_record_no_api_key(self):
        from integrations.airtable_service import AirtableService

        svc = AirtableService(config={"api_key": None})
        with pytest.raises(HTTPException) as exc_info:
            asyncio.run(svc.create_record("b1", "T", {"Name": "X"}))
        assert exc_info.value.status_code == 401

    def test_create_record_http_error(self, svc):
        svc.http.post = AsyncMock(
            return_value=self._air_resp({}, exc=httpx.HTTPError("boom"))
        )
        with pytest.raises(HTTPException) as exc_info:
            asyncio.run(svc.create_record("b1", "T", {"Name": "X"}))
        assert exc_info.value.status_code == 400

    def test_update_record_ok(self, svc):
        svc.http.patch = AsyncMock(return_value=self._air_resp({"id": "r1"}))
        result = asyncio.run(svc.update_record("b1", "T", "r1", {"Name": "Y"}))
        assert result["id"] == "r1"

    def test_update_record_no_api_key(self):
        from integrations.airtable_service import AirtableService

        svc = AirtableService(config={"api_key": None})
        with pytest.raises(HTTPException) as exc_info:
            asyncio.run(svc.update_record("b1", "T", "r1", {"Name": "Y"}))
        assert exc_info.value.status_code == 401

    def test_update_record_http_error(self, svc):
        svc.http.patch = AsyncMock(
            return_value=self._air_resp({}, exc=httpx.HTTPError("boom"))
        )
        with pytest.raises(HTTPException):
            asyncio.run(svc.update_record("b1", "T", "r1", {"Name": "Y"}))

    def test_delete_record_ok(self, svc):
        svc.http.delete = AsyncMock(return_value=self._air_resp({"deleted": True}))
        assert asyncio.run(svc.delete_record("b1", "T", "r1")) == {"deleted": True}

    def test_delete_record_no_api_key(self):
        from integrations.airtable_service import AirtableService

        svc = AirtableService(config={"api_key": None})
        with pytest.raises(HTTPException) as exc_info:
            asyncio.run(svc.delete_record("b1", "T", "r1"))
        assert exc_info.value.status_code == 401

    def test_delete_record_http_error(self, svc):
        svc.http.delete = AsyncMock(
            return_value=self._air_resp({}, exc=httpx.HTTPError("boom"))
        )
        with pytest.raises(HTTPException):
            asyncio.run(svc.delete_record("b1", "T", "r1"))

    def test_health_check(self, svc):
        result = asyncio.run(svc.health_check())
        assert result["ok"] is True
        assert result["status"] == "healthy"

    def test_execute_operation_get_bases(self, svc):
        svc.http.get = AsyncMock(return_value=self._air_resp({"bases": [{"id": "b1"}]}))
        result = asyncio.run(svc.execute_operation("get_bases", {}))
        assert result["success"] is True
        assert result["result"] == [{"id": "b1"}]

    def test_execute_operation_list_records(self, svc):
        svc.http.get = AsyncMock(return_value=self._air_resp({"records": [{"id": "r1"}]}))
        result = asyncio.run(
            svc.execute_operation("list_records", {"base_id": "b1", "table_name": "T"})
        )
        assert result["success"] is True
        assert result["result"] == [{"id": "r1"}]

    def test_execute_operation_get_tables(self, svc):
        svc.http.get = AsyncMock(return_value=self._air_resp({"tables": [{"id": "t1"}]}))
        result = asyncio.run(svc.execute_operation("get_tables", {"base_id": "b1"}))
        assert result["success"] is True
        assert result["result"] == [{"id": "t1"}]

    def test_execute_operation_get_record(self, svc):
        svc.http.get = AsyncMock(return_value=self._air_resp({"id": "r1"}))
        result = asyncio.run(
            svc.execute_operation("get_record", {"base_id": "b1", "table_name": "T", "record_id": "r1"})
        )
        assert result["success"] is True

    def test_execute_operation_create_record(self, svc):
        svc.http.post = AsyncMock(return_value=self._air_resp({"id": "r1"}))
        result = asyncio.run(
            svc.execute_operation("create_record", {"base_id": "b1", "table_name": "T", "fields": {"N": 1}})
        )
        assert result["success"] is True

    def test_execute_operation_update_record(self, svc):
        svc.http.patch = AsyncMock(return_value=self._air_resp({"id": "r1"}))
        result = asyncio.run(
            svc.execute_operation("update_record", {"base_id": "b1", "table_name": "T", "record_id": "r1", "fields": {"N": 2}})
        )
        assert result["success"] is True

    def test_execute_operation_delete_record(self, svc):
        svc.http.delete = AsyncMock(return_value=self._air_resp({"deleted": True}))
        result = asyncio.run(
            svc.execute_operation("delete_record", {"base_id": "b1", "table_name": "T", "record_id": "r1"})
        )
        assert result["success"] is True

    def test_execute_operation_unknown(self, svc):
        result = asyncio.run(svc.execute_operation("nope", {}))
        assert result["success"] is False
        assert "Unknown operation" in result["error"]

    def test_execute_operation_tenant_mismatch(self):
        from integrations.airtable_service import AirtableService

        svc = AirtableService(tenant_id="t1", config={"api_key": "k"})
        result = asyncio.run(
            svc.execute_operation("get_bases", {}, context={"tenant_id": "t2"})
        )
        assert result["success"] is False
        assert result["error"] == "Tenant ID mismatch"

    def test_execute_operation_exception(self, svc):
        svc.get_bases = AsyncMock(side_effect=ValueError("boom"))
        result = asyncio.run(svc.execute_operation("get_bases", {}))
        assert result["success"] is False
        assert "boom" not in json.dumps(result)

    def test_sync_to_postgres_cache_ok(self, svc):
        with patch("core.database.SessionLocal", _in_memory_metric_db()):
            result = asyncio.run(svc.sync_to_postgres_cache("ws-1"))
        assert result["success"] is True
        assert result["metrics_synced"] == 1

    def test_sync_to_postgres_cache_persists_workspace_id(self, svc):
        SessionLocal = _in_memory_metric_db()
        with patch("core.database.SessionLocal", SessionLocal):
            asyncio.run(svc.sync_to_postgres_cache("ws-77"))
        from core.models import IntegrationMetric

        db = SessionLocal()
        rows = db.query(IntegrationMetric).filter_by(
            workspace_id="ws-77", integration_type="airtable"
        ).all()
        db.close()
        assert len(rows) == 1
        assert rows[0].metric_key == "airtable_connected"

    def test_sync_to_postgres_cache_updates_existing(self, svc):
        SessionLocal = _in_memory_metric_db()
        db = SessionLocal()
        from core.models import IntegrationMetric

        db.add(
            IntegrationMetric(
                workspace_id="ws-9",
                integration_type="airtable",
                metric_key="airtable_connected",
                value=1.0,
                unit="boolean",
            )
        )
        db.commit()
        db.close()

        with patch("core.database.SessionLocal", SessionLocal):
            result = asyncio.run(svc.sync_to_postgres_cache("ws-9"))
        assert result["success"] is True
        db = SessionLocal()
        row = (
            db.query(IntegrationMetric)
            .filter_by(workspace_id="ws-9", integration_type="airtable")
            .first()
        )
        assert row.value == 1.0
        db.close()

    def test_sync_to_postgres_cache_db_error(self, svc):
        fake_db = Mock()
        fake_db.query.return_value.filter_by.return_value.first.side_effect = Exception(
            "db boom"
        )
        with patch("core.database.SessionLocal", Mock(return_value=fake_db)):
            result = asyncio.run(svc.sync_to_postgres_cache("ws-1"))
        assert result["success"] is False
        assert "db boom" not in json.dumps(result)
        fake_db.rollback.assert_called_once()
        fake_db.close.assert_called_once()

    def test_sync_to_postgres_cache_outer_error(self, svc):
        with patch("core.database.SessionLocal", side_effect=Exception("boom")):
            result = asyncio.run(svc.sync_to_postgres_cache("ws-1"))
        assert result["success"] is False
        assert "boom" not in json.dumps(result)

    def test_full_sync(self, svc):
        svc.sync_to_postgres_cache = AsyncMock(return_value={"success": True})
        result = asyncio.run(svc.full_sync("ws-1", "b1"))
        assert result["success"] is True
        assert result["workspace_id"] == "ws-1"
        assert result["postgres_cache"]["success"] is True


# =====================================================================
# GMBAutomation  (bug: AI branch imported nonexistent module)
# =====================================================================

def _fake_ai_service_module():
    import enum
    import sys
    import types

    class AIModelType(enum.Enum):
        GPT_4O = "gpt-4o"

    class AITaskType(enum.Enum):
        CONTENT_GENERATION = "content_generation"

    class AIServiceType(enum.Enum):
        OPENAI = "openai"

    fake = types.ModuleType("integrations.ai_enhanced_service")
    fake.AIModelType = AIModelType
    fake.AITaskType = AITaskType
    fake.AIServiceType = AIServiceType
    fake.AIRequest = lambda **kwargs: SimpleNamespace(**kwargs)

    class Patcher:
        def __init__(self):
            self._name = "integrations.ai_enhanced_service"

        def __enter__(self):
            import sys

            self._had = self._name in sys.modules
            self._old = sys.modules.get(self._name)
            sys.modules[self._name] = fake
            return fake

        def __exit__(self, *exc):
            import sys

            if self._had:
                sys.modules[self._name] = self._old
            else:
                sys.modules.pop(self._name, None)
            return False

    return Patcher()


class TestGMBAutomation:
    def test_generate_weekly_update_no_ai(self):
        from integrations.gmb_automation import GMBAutomation

        gmb = GMBAutomation()
        result = asyncio.run(
            gmb.generate_weekly_update(
                {"name": "Cafe", "location": "NYC"}, ["New menu", "Happy hour"]
            )
        )
        assert "Cafe" in result
        assert "NYC" in result

    def test_generate_weekly_update_with_ai_dict_output(self):
        from integrations.gmb_automation import GMBAutomation

        ai = Mock()
        ai.process_ai_request = AsyncMock(
            return_value=SimpleNamespace(output_data={"content": "Fresh coffee near you!"})
        )
        gmb = GMBAutomation(ai_service=ai)
        with _fake_ai_service_module():
            result = asyncio.run(
                gmb.generate_weekly_update({"name": "Cafe", "location": "NYC"}, ["Offer"])
            )
        assert result == "Fresh coffee near you!"

    def test_generate_weekly_update_with_ai_plain_output(self):
        from integrations.gmb_automation import GMBAutomation

        ai = Mock()
        ai.process_ai_request = AsyncMock(return_value=SimpleNamespace(output_data="Plain text"))
        gmb = GMBAutomation(ai_service=ai)
        with _fake_ai_service_module():
            result = asyncio.run(
                gmb.generate_weekly_update({"name": "Cafe", "location": "NYC"}, [])
            )
        assert result == "Plain text"

    def test_generate_weekly_update_ai_unavailable_fallback(self):
        from integrations.gmb_automation import GMBAutomation

        ai = Mock()
        gmb = GMBAutomation(ai_service=ai)
        result = asyncio.run(
            gmb.generate_weekly_update({"name": "Cafe", "location": "NYC"}, ["Offer"])
        )
        assert "Cafe" in result
        ai.process_ai_request.assert_not_called()

    def test_draft_review_response_no_ai(self):
        from integrations.gmb_automation import GMBAutomation

        gmb = GMBAutomation()
        result = asyncio.run(gmb.draft_review_response("Great place", 5))
        assert "feedback" in result

    def test_draft_review_response_with_ai(self):
        from integrations.gmb_automation import GMBAutomation

        ai = Mock()
        ai.process_ai_request = AsyncMock(
            return_value=SimpleNamespace(output_data={"content": "Thanks for 5 stars!"})
        )
        gmb = GMBAutomation(ai_service=ai)
        with _fake_ai_service_module():
            result = asyncio.run(gmb.draft_review_response("Great place", 5))
        assert result == "Thanks for 5 stars!"

    def test_draft_review_response_ai_unavailable_fallback(self):
        from integrations.gmb_automation import GMBAutomation

        ai = Mock()
        gmb = GMBAutomation(ai_service=ai)
        result = asyncio.run(gmb.draft_review_response("Great place", 2))
        assert "feedback" in result
        ai.process_ai_request.assert_not_called()
