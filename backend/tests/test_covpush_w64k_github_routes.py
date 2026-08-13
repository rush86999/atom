"""Coverage-push tests for integrations.github_routes (W64k, TDD, 35% baseline).

Target: >=95% statement coverage STANDALONE (this file alone).

Covers: every endpoint (health, list/create repositories, issues, pulls,
search, user profile) x success / 401 no-token / 503 service-unavailable /
500 service-exception; the create-operation multiplexing paths (422 when
required create fields missing); get_github_tokens full branch matrix
(valid, expired strict/non-strict, decrypt failure, env fallback, no-token
strict/non-strict, own-session lifecycle, outer exception strict/non-strict);
module-level import guard (github_service ImportError -> GITHUB_AVAILABLE
False) and the OAUTH_STRICT_MODE=False startup warning via importlib reload.

No network: github_service is a MagicMock (session.post etc.); tokens come
from a mocked db session.
"""

import importlib
import os
import sys
import uuid
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from integrations import github_routes as gr
from core.auth import get_current_user
from core.models import User


REPO = {
    "id": 1, "name": "atom", "full_name": "dev/atom",
    "description": "platform", "private": False, "fork": False,
    "html_url": "https://github.com/dev/atom", "clone_url": "https://clone",
    "ssh_url": "git@ssh", "language": "Python", "stargazers_count": 3,
    "watchers_count": 2, "forks_count": 1, "open_issues_count": 4,
    "default_branch": "main", "created_at": "2026-01-01",
    "updated_at": "2026-02-01", "pushed_at": "2026-03-01", "size": 12,
    "owner": {"login": "dev", "avatar_url": "https://a"}, "topics": ["ai"],
    "license": {"key": "mit"},
}

ISSUE = {
    "id": 1, "number": 5, "title": "bug", "body": "body", "state": "open",
    "locked": False, "comments": 2, "created_at": "2026-01-01",
    "updated_at": "2026-02-01", "closed_at": None,
    "user": {"login": "dev", "avatar_url": "https://a"},
    "assignee": {"login": "dev", "avatar_url": "https://a"},
    "assignees": [{"login": "dev", "avatar_url": "https://a"}],
    "labels": [{"name": "bug"}], "milestone": None,
    "html_url": "https://github.com/dev/atom/issues/5",
    "reactions": {"+1": 1}, "repository_url": "https://repo",
}

PR = {
    "id": 1, "number": 9, "title": "pr", "body": "b", "state": "open",
    "locked": False, "created_at": "2026-01-01", "updated_at": "2026-02-01",
    "closed_at": None, "merged_at": None, "merge_commit_sha": "abc",
    "head": {"ref": "feat"}, "base": {"ref": "main"},
    "user": {"login": "dev"}, "assignees": [], "requested_reviewers": [],
    "labels": [], "milestone": None, "commits": 1, "additions": 2,
    "deletions": 1, "changed_files": 3, "html_url": "https://h",
    "diff_url": "https://d", "patch_url": "https://p",
}


@pytest.fixture
def user():
    u = MagicMock(spec=User)
    u.id = f"gh-{uuid.uuid4().hex[:8]}"
    u.email = "gh@x.com"
    u.tenant_id = "t-1"
    return u


@pytest.fixture
def client(user):
    app = FastAPI()
    app.include_router(gr.router)
    app.dependency_overrides[get_current_user] = lambda: user
    c = TestClient(app, raise_server_exceptions=False)
    yield c
    app.dependency_overrides.clear()


@pytest.fixture
def svc():
    """Patched module-level github_service (session.post etc. mocked)."""
    s = MagicMock()
    s.base_url = "https://api.github.com"
    s.session.post.return_value.raise_for_status = MagicMock()
    s.session.post.return_value.json.return_value = dict(REPO, id=99,
                                                         name="new-repo")
    s.get_user_repositories.return_value = [REPO]
    s.get_repository_issues.return_value = [ISSUE]
    s.create_issue.return_value = dict(ISSUE, id=10)
    s.get_repository_pulls.return_value = [PR]
    s.create_pull_request.return_value = dict(PR, id=11)
    s.search_repositories.return_value = {"items": [REPO], "total": 1}
    with patch.object(gr, "github_service", s):
        yield s


@pytest.fixture
def tokens():
    return {
        "access_token": "tok", "token_type": "bearer",
        "scope": "repo", "user_info": {"login": "dev"}, "source": "database",
    }


def _client_for(module):
    app = FastAPI()
    app.include_router(module.router)
    app.dependency_overrides[get_current_user] = lambda: MagicMock(id="u1")
    return TestClient(app, raise_server_exceptions=False)


# ============================================================================
# Module-level guards (import-time branches via reload)
# ============================================================================

class TestModuleLevelBranches:
    def test_github_service_import_error_branch(self):
        with patch.dict(sys.modules, {"integrations.github_service": None}):
            reloaded = importlib.reload(gr)
            assert reloaded.GITHUB_AVAILABLE is False
            assert reloaded.github_service is None
        importlib.reload(gr)
        assert gr.GITHUB_AVAILABLE is True
        assert gr.github_service is not None

    def test_oauth_strict_mode_false_warning(self, caplog):
        saved = os.environ.get("OAUTH_STRICT_MODE")
        os.environ["OAUTH_STRICT_MODE"] = "false"
        try:
            with caplog.at_level("WARNING", logger="integrations.github_routes"):
                reloaded = importlib.reload(gr)
                assert reloaded.OAUTH_STRICT_MODE is False
            assert any("OAUTH_STRICT_MODE is FALSE" in r.message for r in caplog.records)
        finally:
            if saved is None:
                os.environ.pop("OAUTH_STRICT_MODE", None)
            else:
                os.environ["OAUTH_STRICT_MODE"] = saved
            importlib.reload(gr)
            assert gr.OAUTH_STRICT_MODE is True


# ============================================================================
# get_github_tokens unit matrix
# ============================================================================

def _token_record(**overrides):
    rec = MagicMock()
    rec.user_id = "u1"
    rec.provider = "github"
    rec.status = "active"
    rec.access_token = "enc-token"
    rec.token_type = None
    rec.scope = None
    rec.expires_at = None
    rec.user_info = None
    for k, v in overrides.items():
        setattr(rec, k, v)
    return rec


class TestGetGithubTokens:
    def test_valid_token_record_with_db(self):
        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = _token_record()
        with patch("core.privsec.token_encryption.decrypt_token",
                   return_value="decrypted") as decrypt:
            result = gr.get_github_tokens("u1", db=db)
        assert result["access_token"] == "decrypted"
        assert result["token_type"] == "bearer"
        assert result["scope"] == "repo,user:email,read:org"
        assert result["user_info"] == {}
        assert result["source"] == "database"
        decrypt.assert_called_once_with("enc-token", allow_plaintext=True)

    def test_token_record_with_all_fields(self):
        rec = _token_record(
            token_type="token", scope="repo",
            user_info={"login": "dev"},
            expires_at=datetime.now(timezone.utc) + __import__("datetime").timedelta(days=1))
        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = rec
        with patch("core.privsec.token_encryption.decrypt_token",
                   return_value="decrypted"):
            result = gr.get_github_tokens("u1", db=db)
        assert result["token_type"] == "token"
        assert result["scope"] == "repo"
        assert result["user_info"] == {"login": "dev"}

    def test_expired_token_strict_raises_401(self):
        rec = _token_record(
            expires_at=datetime.now(timezone.utc).replace(year=2020))
        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = rec
        with pytest.raises(Exception) as exc_info:
            gr.get_github_tokens("u1", db=db)
        assert exc_info.value.status_code == 401
        assert exc_info.value.detail["error_code"] == "OAUTH_TOKEN_EXPIRED"

    def test_expired_token_non_strict_returns_none(self):
        rec = _token_record(
            expires_at=datetime.now(timezone.utc).replace(year=2020))
        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = rec
        with patch.object(gr, "OAUTH_STRICT_MODE", False):
            assert gr.get_github_tokens("u1", db=db) is None

    def test_query_exception_strict_raises_401(self):
        db = MagicMock()
        db.query.side_effect = RuntimeError("query failed")
        with patch("core.privsec.token_encryption.decrypt_token"):
            with pytest.raises(Exception) as exc_info:
                gr.get_github_tokens("u1", db=db)
        assert exc_info.value.status_code == 401
        assert exc_info.value.detail["error_code"] == "OAUTH_TOKEN_INVALID"

    def test_query_exception_non_strict_env_fallback(self):
        db = MagicMock()
        db.query.side_effect = RuntimeError("query failed")
        with patch.object(gr, "OAUTH_STRICT_MODE", False), \
             patch.dict(os.environ, {"GITHUB_ACCESS_TOKEN": "env-token"}, clear=False):
            result = gr.get_github_tokens("u1", db=db)
        assert result["access_token"] == "env-token"
        assert result["source"] == "environment"
        assert result["user_info"]["login"] == "testuser"

    def test_query_exception_non_strict_no_env_returns_none(self):
        db = MagicMock()
        db.query.side_effect = RuntimeError("query failed")
        with patch.object(gr, "OAUTH_STRICT_MODE", False), \
             patch.dict(os.environ, {}, clear=True):
            assert gr.get_github_tokens("u1", db=db) is None

    def test_no_token_strict_raises_401(self):
        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = None
        with pytest.raises(Exception) as exc_info:
            gr.get_github_tokens("u1", db=db)
        assert exc_info.value.status_code == 401
        assert exc_info.value.detail["error_code"] == "OAUTH_TOKEN_INVALID"

    def test_no_token_non_strict_returns_none(self):
        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = None
        with patch.object(gr, "OAUTH_STRICT_MODE", False), \
             patch.dict(os.environ, {}, clear=True):
            assert gr.get_github_tokens("u1", db=db) is None

    def test_owns_db_session_closed(self):
        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = _token_record()
        with patch.object(gr, "get_db_session", lambda: iter([db])), \
             patch("core.privsec.token_encryption.decrypt_token",
                   return_value="d"):
            result = gr.get_github_tokens("u1")
        assert result["access_token"] == "d"
        db.close.assert_called_once()

    def test_real_get_db_session_generator(self):
        """Cover github_routes.get_db_session body with SessionLocal patched."""
        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = None
        with patch("core.database.SessionLocal", return_value=db), \
             patch.dict(os.environ, {"OAUTH_STRICT_MODE": "false"}, clear=False):
            with patch.object(gr, "OAUTH_STRICT_MODE", False):
                assert gr.get_github_tokens("u1") is None
        assert db.close.called

    def test_outer_exception_strict_raises_500(self):
        with patch.object(gr, "get_db_session", side_effect=RuntimeError("boom")):
            with pytest.raises(Exception) as exc_info:
                gr.get_github_tokens("u1")
        assert exc_info.value.status_code == 500
        assert exc_info.value.detail == "Failed to retrieve GitHub token"

    def test_outer_exception_non_strict_returns_none(self):
        with patch.object(gr, "OAUTH_STRICT_MODE", False), \
             patch.object(gr, "get_db_session", side_effect=RuntimeError("boom")):
            assert gr.get_github_tokens("u1") is None


# ============================================================================
# /health
# ============================================================================

class TestHealth:
    def test_health_available_healthy(self, client, svc):
        svc.test_connection.return_value = {"status": "ok"}
        response = client.get("/api/github/health")
        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "healthy"
        assert body["ok"] is True
        assert body["service_info"] == {"status": "ok"}
        assert body["service_available"] is True

    def test_health_service_error_degraded(self, client, svc):
        svc.test_connection.side_effect = RuntimeError("down")
        response = client.get("/api/github/health")
        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "degraded"
        assert body["ok"] is False

    def test_health_unavailable(self, client):
        with patch.object(gr, "GITHUB_AVAILABLE", False):
            response = client.get("/api/github/health")
        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "unhealthy"
        assert body["error"] == "GitHub services not available"

    def test_health_outer_exception(self, client, svc):
        class ExplodingBool:
            def __bool__(self):
                raise RuntimeError("boom")

        with patch.object(gr, "GITHUB_AVAILABLE", ExplodingBool()):
            response = client.get("/api/github/health")
        assert response.status_code == 200
        assert response.json()["status"] == "unhealthy"
        assert response.json()["error"] == "GitHub health check failed"


# ============================================================================
# POST /repositories
# ============================================================================

class TestListRepositories:
    def test_list_success(self, client, user, svc, tokens):
        with patch.object(gr, "get_github_tokens", return_value=tokens) as mock_tokens:
            response = client.post("/api/github/repositories", json={
                "user_id": "attacker", "repo_type": "all", "limit": 1,
                "page": 2, "sort": "updated", "direction": "desc"})
        assert response.status_code == 200
        body = response.json()
        assert body["ok"] is True
        data = body["data"]
        assert data["total_count"] == 1
        assert data["repositories"][0]["name"] == "atom"
        assert data["repositories"][0]["visibility"] == "public"
        assert data["repositories"][0]["owner"]["login"] == "dev"
        assert data["pagination"] == {"page": 2, "limit": 1, "has_more": True}
        assert body["endpoint"] == "list_repositories"
        assert body["source"] == "github_api"
        svc.get_user_repositories.assert_called_once_with("all")
        assert mock_tokens.call_args[0][0] == user.id
        assert mock_tokens.call_args[0][0] != "attacker"

    def test_list_private_repo_and_missing_owner(self, client, svc, tokens):
        svc.get_user_repositories.return_value = [
            dict(REPO, private=True, owner=None),
            dict(REPO, private=False, name="pub"),
        ]
        with patch.object(gr, "get_github_tokens", return_value=tokens):
            response = client.post("/api/github/repositories", json={
                "user_id": "u1", "repo_type": "owner", "limit": 50})
        data = response.json()["data"]
        assert data["repositories"][0]["visibility"] == "private"
        assert data["repositories"][0]["owner"] == {"login": None,
                                                    "avatar_url": None}
        assert data["pagination"]["has_more"] is False

    def test_list_no_tokens_401(self, client, svc):
        with patch.object(gr, "get_github_tokens", return_value=None):
            response = client.post("/api/github/repositories", json={"user_id": "u1"})
        assert response.status_code == 401
        assert response.json()["detail"] == "GitHub tokens not found"

    def test_list_unavailable_503(self, client):
        with patch.object(gr, "GITHUB_AVAILABLE", False):
            response = client.post("/api/github/repositories", json={"user_id": "u1"})
        assert response.status_code == 503

    def test_list_service_exception_500(self, client, svc, tokens):
        svc.get_user_repositories.side_effect = RuntimeError("down")
        with patch.object(gr, "get_github_tokens", return_value=tokens):
            response = client.post("/api/github/repositories", json={"user_id": "u1"})
        assert response.status_code == 500
        assert response.json()["detail"] == "Error listing repositories"

    def test_list_create_operation_missing_name_422(self, client, tokens):
        with patch.object(gr, "get_github_tokens", return_value=tokens):
            response = client.post("/api/github/repositories", json={
                "user_id": "u1", "operation": "create"})
        assert response.status_code == 422
        assert "name is required" in response.json()["detail"]

    def test_list_create_operation_delegates(self, client, svc, tokens):
        with patch.object(gr, "get_github_tokens", return_value=tokens):
            response = client.post("/api/github/repositories", json={
                "user_id": "u1", "operation": "create", "name": "new-repo",
                "description": "d", "private": True, "auto_init": False})
        assert response.status_code == 200
        data = response.json()["data"]
        assert data["repository"]["name"] == "new-repo"
        assert data["message"] == "Repository created successfully"
        assert svc.session.post.call_args.kwargs["json"]["name"] == "new-repo"
        assert svc.session.post.call_args.kwargs["json"]["private"] is True
        assert svc.session.post.call_args.kwargs["json"]["auto_init"] is False


# ============================================================================
# POST /repositories/create
# ============================================================================

class TestCreateRepository:
    def test_create_success(self, client, svc, tokens):
        with patch.object(gr, "get_github_tokens", return_value=tokens):
            response = client.post("/api/github/repositories/create", json={
                "user_id": "u1", "name": "new-repo", "description": "d",
                "private": False, "auto_init": True})
        assert response.status_code == 200
        body = response.json()
        assert body["ok"] is True
        data = body["data"]
        assert data["repository"]["repo_id"] == 99
        assert data["url"] == "https://github.com/dev/atom"
        assert data["message"] == "Repository created successfully"
        assert body["endpoint"] == "create_repository"
        svc.session.post.assert_called_once()

    def test_create_empty_result_500(self, client, svc, tokens):
        svc.session.post.return_value.json.return_value = {}
        with patch.object(gr, "get_github_tokens", return_value=tokens):
            response = client.post("/api/github/repositories/create", json={
                "user_id": "u1", "name": "x"})
        assert response.status_code == 500
        assert response.json()["detail"] == "Failed to create repository"

    def test_create_post_failure_500(self, client, svc, tokens):
        svc.session.post.return_value.raise_for_status.side_effect = RuntimeError("git down")
        with patch.object(gr, "get_github_tokens", return_value=tokens):
            response = client.post("/api/github/repositories/create", json={
                "user_id": "u1", "name": "x"})
        assert response.status_code == 500
        assert response.json()["detail"] == "Error creating repository"

    def test_create_no_tokens_401(self, client, svc):
        with patch.object(gr, "get_github_tokens", return_value=None):
            response = client.post("/api/github/repositories/create", json={
                "user_id": "u1", "name": "x"})
        assert response.status_code == 401

    def test_create_unavailable_503(self, client):
        with patch.object(gr, "GITHUB_AVAILABLE", False):
            response = client.post("/api/github/repositories/create", json={
                "user_id": "u1", "name": "x"})
        assert response.status_code == 503


# ============================================================================
# POST /issues
# ============================================================================

class TestListIssues:
    def test_list_success(self, client, svc, tokens):
        with patch.object(gr, "get_github_tokens", return_value=tokens):
            response = client.post("/api/github/issues", json={
                "user_id": "u1", "owner": "dev", "repo": "atom",
                "state": "open", "limit": 1})
        assert response.status_code == 200
        body = response.json()
        assert body["ok"] is True
        issue = body["data"]["issues"][0]
        assert issue["issue_id"] == 1
        assert issue["assignee"]["login"] == "dev"
        assert issue["assignees"][0]["login"] == "dev"
        assert body["data"]["pagination"]["has_more"] is True
        assert body["endpoint"] == "list_issues"
        svc.get_repository_issues.assert_called_once_with("dev", "atom", "open")

    def test_list_issue_without_assignee(self, client, svc, tokens):
        svc.get_repository_issues.return_value = [dict(ISSUE, assignee=None,
                                                       assignees=None)]
        with patch.object(gr, "get_github_tokens", return_value=tokens):
            response = client.post("/api/github/issues", json={
                "user_id": "u1", "owner": "dev", "repo": "atom", "limit": 50})
        issue = response.json()["data"]["issues"][0]
        assert issue["assignee"] is None
        assert issue["assignees"] == []

    def test_list_no_tokens_401(self, client, svc):
        with patch.object(gr, "get_github_tokens", return_value=None):
            response = client.post("/api/github/issues", json={"user_id": "u1"})
        assert response.status_code == 401

    def test_list_unavailable_503(self, client):
        with patch.object(gr, "GITHUB_AVAILABLE", False):
            response = client.post("/api/github/issues", json={"user_id": "u1"})
        assert response.status_code == 503

    def test_list_service_exception_500(self, client, svc, tokens):
        svc.get_repository_issues.side_effect = RuntimeError("down")
        with patch.object(gr, "get_github_tokens", return_value=tokens):
            response = client.post("/api/github/issues", json={"user_id": "u1"})
        assert response.status_code == 500
        assert response.json()["detail"] == "Error listing issues"

    def test_create_operation_missing_title_422(self, client, tokens):
        with patch.object(gr, "get_github_tokens", return_value=tokens):
            response = client.post("/api/github/issues", json={
                "user_id": "u1", "operation": "create"})
        assert response.status_code == 422

    def test_create_operation_delegates(self, client, svc, tokens):
        with patch.object(gr, "get_github_tokens", return_value=tokens):
            response = client.post("/api/github/issues", json={
                "user_id": "u1", "operation": "create", "owner": "dev",
                "repo": "atom", "title": "New issue", "body": "b",
                "labels": ["bug"], "assignees": ["dev"]})
        assert response.status_code == 200
        data = response.json()["data"]
        assert data["issue"]["issue_id"] == 10
        assert data["message"] == "Issue created successfully"
        svc.create_issue.assert_called_once_with("dev", "atom", "New issue",
                                                 "b", ["bug"])


# ============================================================================
# POST /issues/create
# ============================================================================

class TestCreateIssue:
    def test_create_success(self, client, svc, tokens):
        with patch.object(gr, "get_github_tokens", return_value=tokens):
            response = client.post("/api/github/issues/create", json={
                "user_id": "u1", "owner": "dev", "repo": "atom",
                "title": "T", "body": "b", "labels": [], "assignees": []})
        assert response.status_code == 200
        body = response.json()
        assert body["ok"] is True
        assert body["data"]["issue"]["number"] == 5
        assert body["data"]["url"] == "https://github.com/dev/atom/issues/5"
        assert body["endpoint"] == "create_issue"
        svc.create_issue.assert_called_once_with("dev", "atom", "T", "b", [])

    def test_create_empty_result_500(self, client, svc, tokens):
        svc.create_issue.return_value = {}
        with patch.object(gr, "get_github_tokens", return_value=tokens):
            response = client.post("/api/github/issues/create", json={
                "user_id": "u1", "title": "T"})
        assert response.status_code == 500
        assert response.json()["detail"] == "Failed to create issue"

    def test_create_service_exception_500(self, client, svc, tokens):
        svc.create_issue.side_effect = RuntimeError("down")
        with patch.object(gr, "get_github_tokens", return_value=tokens):
            response = client.post("/api/github/issues/create", json={
                "user_id": "u1", "title": "T"})
        assert response.status_code == 500

    def test_create_no_tokens_401(self, client, svc):
        with patch.object(gr, "get_github_tokens", return_value=None):
            response = client.post("/api/github/issues/create", json={
                "user_id": "u1", "title": "T"})
        assert response.status_code == 401

    def test_create_unavailable_503(self, client):
        with patch.object(gr, "GITHUB_AVAILABLE", False):
            response = client.post("/api/github/issues/create", json={
                "user_id": "u1", "title": "T"})
        assert response.status_code == 503


# ============================================================================
# POST /pulls
# ============================================================================

class TestListPullRequests:
    def test_list_success(self, client, svc, tokens):
        with patch.object(gr, "get_github_tokens", return_value=tokens):
            response = client.post("/api/github/pulls", json={
                "user_id": "u1", "owner": "dev", "repo": "atom",
                "state": "open", "limit": 1})
        assert response.status_code == 200
        body = response.json()
        assert body["ok"] is True
        pr = body["data"]["pull_requests"][0]
        assert pr["pr_id"] == 1
        assert pr["head"]["ref"] == "feat"
        assert body["data"]["repository"] == "dev/atom"
        assert body["data"]["pagination"]["has_more"] is True
        assert body["endpoint"] == "list_pull_requests"
        svc.get_repository_pulls.assert_called_once_with("dev", "atom", "open")

    def test_list_no_tokens_401(self, client, svc):
        with patch.object(gr, "get_github_tokens", return_value=None):
            response = client.post("/api/github/pulls", json={"user_id": "u1"})
        assert response.status_code == 401

    def test_list_unavailable_503(self, client):
        with patch.object(gr, "GITHUB_AVAILABLE", False):
            response = client.post("/api/github/pulls", json={"user_id": "u1"})
        assert response.status_code == 503

    def test_list_service_exception_500(self, client, svc, tokens):
        svc.get_repository_pulls.side_effect = RuntimeError("down")
        with patch.object(gr, "get_github_tokens", return_value=tokens):
            response = client.post("/api/github/pulls", json={"user_id": "u1"})
        assert response.status_code == 500

    def test_create_operation_missing_fields_422(self, client, tokens):
        with patch.object(gr, "get_github_tokens", return_value=tokens):
            response = client.post("/api/github/pulls", json={
                "user_id": "u1", "operation": "create", "title": "T"})
        assert response.status_code == 422

    def test_create_operation_delegates(self, client, svc, tokens):
        with patch.object(gr, "get_github_tokens", return_value=tokens):
            response = client.post("/api/github/pulls", json={
                "user_id": "u1", "operation": "create", "owner": "dev",
                "repo": "atom", "title": "T", "head": "feat", "base": "main",
                "body": "b"})
        assert response.status_code == 200
        data = response.json()["data"]
        assert data["pull_request"]["pr_id"] == 11
        assert data["message"] == "Pull request created successfully"
        svc.create_pull_request.assert_called_once_with(
            "dev", "atom", "T", "feat", "main", "b")


# ============================================================================
# POST /pulls/create
# ============================================================================

class TestCreatePullRequest:
    def test_create_success(self, client, svc, tokens):
        with patch.object(gr, "get_github_tokens", return_value=tokens):
            response = client.post("/api/github/pulls/create", json={
                "user_id": "u1", "owner": "dev", "repo": "atom",
                "title": "T", "head": "feat", "base": "main", "body": "b"})
        assert response.status_code == 200
        body = response.json()
        assert body["ok"] is True
        assert body["data"]["pull_request"]["number"] == 9
        assert body["data"]["diff_url"] == "https://d"
        assert body["endpoint"] == "create_pull_request"

    def test_create_empty_result_500(self, client, svc, tokens):
        svc.create_pull_request.return_value = {}
        with patch.object(gr, "get_github_tokens", return_value=tokens):
            response = client.post("/api/github/pulls/create", json={
                "user_id": "u1", "title": "T", "head": "feat"})
        assert response.status_code == 500
        assert response.json()["detail"] == "Failed to create pull request"

    def test_create_service_exception_500(self, client, svc, tokens):
        svc.create_pull_request.side_effect = RuntimeError("down")
        with patch.object(gr, "get_github_tokens", return_value=tokens):
            response = client.post("/api/github/pulls/create", json={
                "user_id": "u1", "title": "T", "head": "feat"})
        assert response.status_code == 500

    def test_create_no_tokens_401(self, client, svc):
        with patch.object(gr, "get_github_tokens", return_value=None):
            response = client.post("/api/github/pulls/create", json={
                "user_id": "u1", "title": "T", "head": "feat"})
        assert response.status_code == 401

    def test_create_unavailable_503(self, client):
        with patch.object(gr, "GITHUB_AVAILABLE", False):
            response = client.post("/api/github/pulls/create", json={
                "user_id": "u1", "title": "T", "head": "feat"})
        assert response.status_code == 503


# ============================================================================
# POST /search
# ============================================================================

class TestSearch:
    def test_search_success(self, client, svc, tokens):
        with patch.object(gr, "get_github_tokens", return_value=tokens):
            response = client.post("/api/github/search", json={
                "user_id": "u1", "query": "atom", "search_type": "repositories",
                "sort": "stars", "order": "desc"})
        assert response.status_code == 200
        body = response.json()
        assert body["items"][0]["name"] == "atom"
        svc.search_repositories.assert_called_once_with("atom", "stars", "desc")

    def test_search_no_tokens_401(self, client, svc):
        with patch.object(gr, "get_github_tokens", return_value=None):
            response = client.post("/api/github/search", json={
                "user_id": "u1", "query": "q"})
        assert response.status_code == 401

    def test_search_unavailable_503(self, client):
        with patch.object(gr, "GITHUB_AVAILABLE", False):
            response = client.post("/api/github/search", json={
                "user_id": "u1", "query": "q"})
        assert response.status_code == 503

    def test_search_service_exception_500(self, client, svc, tokens):
        svc.search_repositories.side_effect = RuntimeError("down")
        with patch.object(gr, "get_github_tokens", return_value=tokens):
            response = client.post("/api/github/search", json={
                "user_id": "u1", "query": "q"})
        assert response.status_code == 500
        assert response.json()["detail"] == "Error searching GitHub"


# ============================================================================
# POST /user/profile
# ============================================================================

class TestUserProfile:
    def test_profile_success(self, client, tokens):
        with patch.object(gr, "get_github_tokens", return_value=tokens):
            response = client.post("/api/github/user/profile", json={
                "user_id": "u1"})
        assert response.status_code == 200
        body = response.json()
        assert body["ok"] is True
        assert body["data"]["user"] == {"login": "dev"}
        assert body["endpoint"] == "get_user_profile"

    def test_profile_no_tokens_401(self, client, svc):
        with patch.object(gr, "get_github_tokens", return_value=None):
            response = client.post("/api/github/user/profile", json={
                "user_id": "u1"})
        assert response.status_code == 401

    def test_profile_unavailable_503(self, client):
        with patch.object(gr, "GITHUB_AVAILABLE", False):
            response = client.post("/api/github/user/profile", json={
                "user_id": "u1"})
        assert response.status_code == 503

    def test_profile_service_exception_500(self, client, svc, tokens):
        with patch.object(gr, "get_github_tokens", side_effect=RuntimeError("down")):
            response = client.post("/api/github/user/profile", json={
                "user_id": "u1"})
        assert response.status_code == 500
        assert response.json()["detail"] == "Error getting user profile"
