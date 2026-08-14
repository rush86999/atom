"""Coverage wave 96 — integrations/obsidian_service.py (TDD, 0% baseline).

BUG FOUND + FIXED (wave 96, TDD RED->GREEN): the documented default
plugin_url "http://localhost:27123" was REJECTED by the constructor's own
SSRF guard — `ObsidianService()` (and every route default in
obsidian_routes.py) raised
  ValueError: Invalid plugin_url: Hostname 'localhost' resolves to blocked IP
The Obsidian Local REST API runs on the user's own machine (loopback is the
INTENDED destination, not an SSRF target), so the service was unusable out
of the box — every construction with the default config crashed. The guard
now exempts loopback literals (localhost / 127.0.0.1 / ::1 / 127.x) and
still validates every other URL (private IPs, non-loopback hostnames stay
blocked). RED: test_default_loopback_constructor_ok (ValueError before fix).

Covers: constructor (default / custom plugin_url / api_token headers /
blocked non-loopback URL -> ValueError), capabilities, health_check
(success + failure), execute_operation dispatch for all 6 operations
(success, missing-params, None-result, tenant-context mismatch,
NotImplementedError, exception), test_connection (200 / non-200 / error),
list_notes / get_note / create_note / append_note / search happy + error.
"""
from unittest.mock import MagicMock, patch

import pytest

from integrations.obsidian_service import ObsidianService


@pytest.fixture
def session():
    return MagicMock()


@pytest.fixture
def service(session):
    with patch("requests.Session", return_value=session):
        s = ObsidianService(tenant_id="t96", config={
            "plugin_url": "http://localhost:27123"})
    return s


# ── Constructor / SSRF guard ─────────────────────────────────────────────────
class TestConstructor:
    def test_default_loopback_constructor_ok(self):
        """RED before fix: ValueError from the SSRF guard on localhost."""
        with patch("requests.Session", return_value=MagicMock()):
            s = ObsidianService()
        assert s.plugin_url == "http://localhost:27123"
        assert s.api_token is None
        assert s.tenant_id == "default"

    def test_default_loopback_with_trailing_slash(self):
        with patch("requests.Session", return_value=MagicMock()):
            s = ObsidianService(config={"plugin_url": "http://127.0.0.1:27123/"})
        assert s.plugin_url == "http://127.0.0.1:27123"

    def test_api_token_sets_headers(self):
        session = MagicMock()
        with patch("requests.Session", return_value=session):
            ObsidianService(config={"api_token": "tok96"})
        session.headers.update.assert_called_once()
        headers = session.headers.update.call_args[0][0]
        assert headers["Authorization"] == "Bearer tok96"

    def test_blocked_private_ip_raises(self):
        with patch("requests.Session", return_value=MagicMock()):
            with pytest.raises(ValueError, match="Invalid plugin_url"):
                ObsidianService(config={"plugin_url": "http://10.0.0.5:27123"})

    def test_blocked_metadata_ip_raises(self):
        with patch("requests.Session", return_value=MagicMock()):
            with pytest.raises(ValueError, match="Invalid plugin_url"):
                ObsidianService(
                    config={"plugin_url": "http://169.254.169.254/latest"})

    def test_hostless_url_raises(self):
        with patch("requests.Session", return_value=MagicMock()):
            with pytest.raises(ValueError, match="Invalid plugin_url"):
                ObsidianService(config={"plugin_url": "http://"})

    def test_public_url_allowed(self):
        with patch("requests.Session", return_value=MagicMock()):
            s = ObsidianService(config={"plugin_url": "https://example.com"})
        assert s.plugin_url == "https://example.com"


# ── Capabilities / health ────────────────────────────────────────────────────
class TestCapabilitiesHealth:
    def test_capabilities(self, service):
        caps = service.get_capabilities()
        assert len(caps["operations"]) == 6
        assert caps["required_params"] == ["plugin_url"]
        assert caps["auth_type"] == "api_token"
        assert caps["supports_webhooks"] is False

    def test_health_check_success(self, service, session):
        session.get.return_value.status_code = 200
        result = service.health_check()
        assert result["healthy"] is True
        assert result["message"] == "Obsidian connection successful"

    def test_health_check_failure(self, service, session):
        session.get.return_value.status_code = 401
        result = service.health_check()
        assert result["healthy"] is False
        assert "Connection failed" in result["message"]


# ── execute_operation ────────────────────────────────────────────────────────
class TestExecuteOperation:
    async def test_tenant_context_mismatch(self, service):
        result = await service.execute_operation("list_notes", {},
                                           context={"tenant_id": "other"})
        assert result["success"] is False
        assert result["error"] == "Tenant context validation failed"

    async def test_tenant_context_match_ok(self, service, session):
        session.get.return_value.status_code = 200
        result = await service.execute_operation(
            "test_connection", {}, context={"tenant_id": "t96"})
        assert result["success"] is True

    async def test_test_connection(self, service, session):
        session.get.return_value.status_code = 200
        result = await service.execute_operation("test_connection", {})
        assert result["success"] is True
        assert result["result"]["authenticated"] is True

    async def test_test_connection_failure(self, service, session):
        session.get.return_value.status_code = 500
        result = await service.execute_operation("test_connection", {})
        assert result["success"] is False

    async def test_list_notes(self, service, session):
        session.get.return_value.json.return_value = {"files": ["a.md", "b.md"]}
        result = await service.execute_operation("list_notes", {})
        assert result["success"] is True
        assert result["result"]["notes"] == ["a.md", "b.md"]
        assert result["details"]["count"] == 2

    async def test_get_note_success(self, service, session):
        session.get.return_value.text = "# Hello"
        result = await service.execute_operation("get_note", {"path": "a.md"})
        assert result["success"] is True
        assert result["result"]["content"] == "# Hello"

    async def test_get_note_missing_path(self, service):
        result = await service.execute_operation("get_note", {})
        assert result["success"] is False
        assert "Missing required parameter" in result["error"]

    async def test_get_note_none_result(self, service, session):
        session.get.side_effect = RuntimeError("vault down")
        result = await service.execute_operation("get_note", {"path": "a.md"})
        assert result["success"] is False
        assert "Failed to get note" in result["error"]

    async def test_create_note_success(self, service, session):
        session.put.return_value.raise_for_status.return_value = None
        result = await service.execute_operation(
            "create_note", {"path": "n.md", "content": "x"})
        assert result["success"] is True

    async def test_create_note_missing_params(self, service):
        result = await service.execute_operation("create_note", {"path": "n.md"})
        assert result["success"] is False
        assert "Missing required parameters" in result["error"]

    async def test_create_note_failure(self, service, session):
        session.put.side_effect = RuntimeError("boom")
        result = await service.execute_operation(
            "create_note", {"path": "n.md", "content": "x"})
        assert result["success"] is False

    async def test_append_note_success(self, service, session):
        session.post.return_value.raise_for_status.return_value = None
        result = await service.execute_operation(
            "append_note", {"path": "n.md", "content": "more"})
        assert result["success"] is True

    async def test_append_note_missing_params(self, service):
        result = await service.execute_operation("append_note", {"content": "x"})
        assert result["success"] is False
        assert "Missing required parameters" in result["error"]

    async def test_append_note_failure(self, service, session):
        session.post.side_effect = RuntimeError("boom")
        result = await service.execute_operation(
            "append_note", {"path": "n.md", "content": "x"})
        assert result["success"] is False

    async def test_search_success(self, service, session):
        session.post.return_value.json.return_value = [{"path": "a.md"}]
        result = await service.execute_operation("search", {"query": "budget"})
        assert result["success"] is True
        assert result["result"]["results"] == [{"path": "a.md"}]
        assert result["details"]["count"] == 1

    async def test_search_missing_query(self, service):
        result = await service.execute_operation("search", {})
        assert result["success"] is False
        assert "Missing required parameter" in result["error"]

    async def test_unknown_operation_not_implemented(self, service):
        result = await service.execute_operation("bogus", {})
        assert result["success"] is False
        assert "not supported" in result["error"]

    async def test_exception_in_operation(self, service, session):
        with patch.object(service, "list_notes",
                          side_effect=RuntimeError("boom")):
            result = await service.execute_operation("list_notes", {})
        assert result["success"] is False
        assert result["error"] == "boom"


# ── Direct service methods ───────────────────────────────────────────────────
class TestDirectMethods:
    def test_test_connection_200(self, service, session):
        session.get.return_value.status_code = 200
        result = service.test_connection()
        assert result["status"] == "success"
        assert result["timestamp"] == "http://localhost:27123"

    def test_test_connection_non_200(self, service, session):
        session.get.return_value.status_code = 403
        result = service.test_connection()
        assert result["status"] == "error"
        assert result["authenticated"] is False

    def test_test_connection_exception(self, service, session):
        session.get.side_effect = ConnectionError("refused")
        result = service.test_connection()
        assert result["status"] == "error"
        assert "refused" in result["message"]

    def test_list_notes_success(self, service, session):
        session.get.return_value.json.return_value = {"files": ["1.md"]}
        assert service.list_notes() == ["1.md"]
        assert session.get.call_args[0][0].endswith("/active/")

    def test_list_notes_error(self, service, session):
        session.get.return_value.json.side_effect = ValueError("bad json")
        assert service.list_notes() == []

    def test_get_note_success(self, service, session):
        session.get.return_value.text = "content"
        assert service.get_note("notes/a.md") == "content"
        url = session.get.call_args[0][0]
        assert url.endswith("/vault/notes/a.md")

    def test_get_note_error(self, service, session):
        session.get.side_effect = RuntimeError("boom")
        assert service.get_note("a.md") is None

    def test_create_note_success(self, service, session):
        session.put.return_value.raise_for_status.return_value = None
        assert service.create_note("n.md", "# New") is True
        call = session.put.call_args
        assert call[0][0].endswith("/vault/n.md")
        assert call[1]["headers"]["Content-Type"] == "text/markdown"

    def test_create_note_error(self, service, session):
        session.put.side_effect = RuntimeError("boom")
        assert service.create_note("n.md", "x") is False

    def test_append_note_success(self, service, session):
        session.post.return_value.raise_for_status.return_value = None
        assert service.append_note("n.md", "more") is True

    def test_append_note_error(self, service, session):
        session.post.side_effect = RuntimeError("boom")
        assert service.append_note("n.md", "more") is False

    def test_search_success(self, service, session):
        session.post.return_value.json.return_value = [{"path": "x.md"}]
        assert service.search("budget") == [{"path": "x.md"}]
        assert session.post.call_args[1]["json"] == {"query": "budget"}

    def test_search_error(self, service, session):
        session.post.side_effect = RuntimeError("boom")
        assert service.search("budget") == []
