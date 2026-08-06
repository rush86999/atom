"""Round 79 — deep-link parse/execute edge cases.

Covers scheme rejection, resource-id security validation, the no-double-slash
``atom:`` form, multi-value params, disabled flag, and the workflow deep link
existence check (a nonexistent workflow used to be reported as success).

DB strategy: in-memory SQLite via the ``worker_database`` fixture — never the
dev DB that other deep-link tests use.
"""
import uuid

import pytest

from core.deeplinks import (
    DEEPLINK_ENABLED,
    DeepLinkParseException,
    DeepLinkSecurityException,
    execute_deep_link,
    execute_workflow_deep_link,
    generate_deep_link,
    parse_deep_link,
)


@pytest.fixture(autouse=True)
def _audit_off(monkeypatch):
    """Isolate from the dev-DB audit writes; audit rows are exercised by the
    existing test_deeplinks.py suite."""
    monkeypatch.setattr("core.deeplinks.DEEPLINK_AUDIT_ENABLED", False)


@pytest.fixture
def db(worker_database):
    from core.models import GatewayApiKey, User

    session = worker_database()
    session.query(GatewayApiKey).delete()
    session.query(User).delete()
    session.commit()
    yield session
    session.close()


class TestParseDeepLink:
    def test_parse_agent_without_double_slash(self):
        link = parse_deep_link("atom:agent/abc-123?message=Hello")
        assert link.resource_type == "agent"
        assert link.resource_id == "abc-123"
        assert link.parameters["message"] == "Hello"

    def test_parse_with_netloc_and_slash(self):
        link = parse_deep_link("atom://agent/abc-123?message=Hi")
        assert link.resource_type == "agent"
        assert link.resource_id == "abc-123"

    def test_parse_multi_value_params_becomes_list(self):
        link = parse_deep_link("atom://workflow/w-1?tag=a&tag=b")
        assert link.parameters["tag"] == ["a", "b"]

    def test_parse_json_params(self):
        link = parse_deep_link('atom://tool/chart?params={"x": 1}')
        assert link.parameters["params"] == {"x": 1}

    def test_unknown_scheme_rejected(self):
        with pytest.raises(DeepLinkParseException):
            parse_deep_link("https://agent/abc")

    def test_unknown_resource_type_rejected(self):
        with pytest.raises(DeepLinkParseException):
            parse_deep_link("atom://billing/invoice-1")

    def test_invalid_resource_id_raises_security_exception(self):
        with pytest.raises(DeepLinkSecurityException):
            parse_deep_link("atom://agent/../..%2Fetc%2Fpasswd")

    def test_empty_url_rejected(self):
        with pytest.raises(DeepLinkParseException):
            parse_deep_link("")

    def test_disabled_raises_security_exception(self, monkeypatch):
        monkeypatch.setattr("core.deeplinks.DEEPLINK_ENABLED", False)
        assert DEEPLINK_ENABLED  # module-level read for the default is unchanged
        with pytest.raises(DeepLinkSecurityException):
            parse_deep_link("atom://agent/abc-123")

    def test_generate_roundtrip(self):
        url = generate_deep_link("agent", "agent-42", message="Hello World", session="s-1")
        link = parse_deep_link(url)
        assert link.resource_type == "agent"
        assert link.resource_id == "agent-42"
        assert link.parameters["message"] == "Hello World"
        assert link.parameters["session"] == "s-1"


class TestExecuteDeepLink:
    @pytest.mark.asyncio
    async def test_execute_unknown_scheme_returns_failure(self, db):
        result = await execute_deep_link("https://example.com/x", user_id="u-1", db=db)
        assert result["success"] is False

    @pytest.mark.asyncio
    async def test_execute_invalid_resource_id_returns_failure(self, db):
        result = await execute_deep_link("atom://agent/../../etc", user_id="u-1", db=db)
        assert result["success"] is False

    @pytest.mark.asyncio
    async def test_execute_unknown_resource_type_returns_failure(self, db):
        result = await execute_deep_link("atom://billing/invoice-1", user_id="u-1", db=db)
        assert result["success"] is False


class TestWorkflowDeepLinkExistence:
    """atom://workflow/{id} must not claim success for a workflow that does
    not exist (the agent/tool executors already validate existence)."""

    @staticmethod
    def _seed_workflow(db):
        from core.models import Tenant, Workflow

        tenant = Tenant(id="default", name="Default", subdomain="default")
        db.add(tenant)
        db.flush()
        workflow = Workflow(
            id=f"wf-{uuid.uuid4().hex[:10]}",
            name="Test Flow",
            tenant_id="default",
            status="active",
        )
        db.add(workflow)
        db.commit()
        return workflow.id

    @pytest.mark.asyncio
    async def test_unknown_workflow_returns_failure(self, db):
        result = await execute_workflow_deep_link(
            parse_deep_link("atom://workflow/no-such-workflow?action=start"),
            user_id="u-1",
            db=db,
        )
        assert result["success"] is False
        assert "not found" in result["error"]

    @pytest.mark.asyncio
    async def test_execute_deep_link_unknown_workflow_returns_failure(self, db):
        result = await execute_deep_link(
            "atom://workflow/no-such-workflow?action=start", user_id="u-1", db=db
        )
        assert result["success"] is False

    @pytest.mark.asyncio
    async def test_existing_workflow_returns_success(self, db):
        wf_id = self._seed_workflow(db)
        result = await execute_workflow_deep_link(
            parse_deep_link(f"atom://workflow/{wf_id}?action=start"),
            user_id="u-1",
            db=db,
        )
        assert result["success"] is True
        assert result["workflow_id"] == wf_id
