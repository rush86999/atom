"""Slice 1 — generic email actions for the action registry (TDD).

GoalRun's ``integration_action`` step executor calls
``action_registry.execute_action(name, args, context)`` (the general
mechanism — 40+ integrations, no per-integration special cases). Email had
NO registered action, so a role-scoped sales run could not search, draft or
send.

These actions are deliberately GENERIC (ask the workspace's connected
provider, gmail/outlook/zoho_mail) — no per-customer business rules live
here (product feedback 2026-09-09: "this is a generalized app ... we are
going to be selling this").

Contracts pinned here:
- ``email.search`` — query the mailbox (one platform, or all connected).
- ``email.draft`` — threaded mailbox DRAFT (never sends).
- ``email.send`` — routes through the GOVERNED send path (deterministic
  email policy + tenant HITL); a policy BLOCK is surfaced, never bypassed.
"""
import pytest
from unittest.mock import AsyncMock


def _ctx():
    return {"user_id": "u1", "workspace_id": "default", "tenant_id": "default",
            "agent_id": "agent-1"}


class TestEmailActionsRegistered:
    def test_all_three_actions_are_registered(self):
        from core.action_registry import action_registry

        for name in ("email.search", "email.draft", "email.send"):
            action = action_registry.get_action(name)
            assert action is not None, f"{name} not registered"
            assert action.parameters_schema.get("properties"), name

    def test_descriptions_are_generic_not_customer_specific(self):
        """The registry is product surface — no Brennan/machinery wording."""
        from core.action_registry import action_registry

        for name in ("email.search", "email.draft", "email.send"):
            desc = (action_registry.get_action(name).description or "").lower()
            for banned in ("brennan", "tennsmith", "price list", "shear", "sr48p"):
                assert banned not in desc, f"{name} leaks customer wording: {banned}"


class TestEmailSearch:
    @pytest.mark.asyncio
    async def test_requires_query(self):
        from core.action_registry import action_registry

        out = await action_registry.execute_action("email.search", {}, _ctx())
        assert out["success"] is False
        assert "query" in out["error"]

    @pytest.mark.asyncio
    async def test_single_platform_delegates_to_universal(self, monkeypatch):
        import integrations.universal_integration_service as uis_mod
        from core.action_registry import action_registry

        calls = []

        async def fake_execute(self, service, action, params, context=None):
            calls.append((service, action, params))
            return {"status": "success", "data": [{"id": "m1", "subject": "Quote"}]}

        monkeypatch.setattr(uis_mod.UniversalIntegrationService, "execute", fake_execute)

        out = await action_registry.execute_action(
            "email.search", {"query": "quote", "platform": "outlook"}, _ctx())

        assert out["success"] is True
        assert calls == [("outlook", "list_messages",
                          {"query": "quote", "folder": "inbox", "max_results": 15})]

    @pytest.mark.asyncio
    async def test_no_platform_queries_every_connected_mail_provider(self, monkeypatch):
        """Same blind spot the agent's search_emails had: gmail-only misses
        Outlook mail. A platform-less search must ask all three."""
        import integrations.universal_integration_service as uis_mod
        from core.action_registry import action_registry

        seen = []

        async def fake_execute(self, service, action, params, context=None):
            seen.append(service)
            return {"status": "success", "data": []}

        monkeypatch.setattr(uis_mod.UniversalIntegrationService, "execute", fake_execute)

        out = await action_registry.execute_action("email.search", {"query": "x"}, _ctx())
        assert out["success"] is True
        assert set(seen) == {"gmail", "outlook", "zoho_mail"}

    @pytest.mark.asyncio
    async def test_one_provider_failure_is_surfaced_not_swallowed(self, monkeypatch):
        import integrations.universal_integration_service as uis_mod
        from core.action_registry import action_registry

        async def fake_execute(self, service, action, params, context=None):
            if service == "outlook":
                raise RuntimeError("token expired")
            return {"status": "success", "data": []}

        monkeypatch.setattr(uis_mod.UniversalIntegrationService, "execute", fake_execute)

        out = await action_registry.execute_action("email.search", {"query": "x"}, _ctx())
        assert out["success"] is True
        assert "error" in out["results"]["outlook"]


class TestEmailDraft:
    @pytest.mark.asyncio
    async def test_requires_body(self):
        from core.action_registry import action_registry

        out = await action_registry.execute_action(
            "email.draft", {"message_id": "m1"}, _ctx())
        assert out["success"] is False
        assert "body" in out["error"]

    @pytest.mark.asyncio
    async def test_requires_a_thread_or_recipient(self):
        from core.action_registry import action_registry

        out = await action_registry.execute_action("email.draft", {"body": "hi"}, _ctx())
        assert out["success"] is False
        assert "message_id" in out["error"] or "thread_id" in out["error"]

    @pytest.mark.asyncio
    async def test_threaded_draft_returns_draft_id(self, monkeypatch):
        import integrations.universal_integration_service as uis_mod
        from core.action_registry import action_registry

        calls = []

        async def fake_execute(self, service, action, params, context=None):
            calls.append((service, action, params))
            return {"status": "success", "data": {"draft_id": "d-1"}}

        monkeypatch.setattr(uis_mod.UniversalIntegrationService, "execute", fake_execute)

        out = await action_registry.execute_action(
            "email.draft",
            {"message_id": "m-9", "body": "Hi Andrew"}, _ctx())

        assert out["success"] is True
        assert out["draft_id"] == "d-1"
        assert calls == [("outlook", "create_draft",
                          {"body": "Hi Andrew", "message_id": "m-9"})]

    @pytest.mark.asyncio
    async def test_all_provider_failure_is_reported(self, monkeypatch):
        import integrations.universal_integration_service as uis_mod
        from core.action_registry import action_registry

        async def fake_execute(self, service, action, params, context=None):
            return {"status": "error", "message": f"{service} draft failed"}

        monkeypatch.setattr(uis_mod.UniversalIntegrationService, "execute", fake_execute)

        out = await action_registry.execute_action(
            "email.draft", {"message_id": "m1", "body": "hi"}, _ctx())
        assert out["success"] is False
        assert "draft failed" in out["error"]


class TestEmailSend:
    @pytest.mark.asyncio
    async def test_requires_body(self):
        from core.action_registry import action_registry

        out = await action_registry.execute_action("email.send", {"to": "a@b.com"}, _ctx())
        assert out["success"] is False
        assert "body" in out["error"]

    @pytest.mark.asyncio
    async def test_routes_through_the_governed_send_path(self, monkeypatch):
        """The send must reuse the SAME gate every agent send uses — the
        deterministic email policy + tenant HITL on the MCP send_email
        surface. No parallel send path."""
        import integrations.mcp_service as mcp_mod
        from core.action_registry import action_registry

        calls = []

        async def fake_execute_tool(self, server_id, tool_name, arguments, context=None):
            calls.append((server_id, tool_name, arguments))
            return {"status": "success", "data": {"id": "sent-1"}}

        monkeypatch.setattr(mcp_mod.MCPService, "execute_tool", fake_execute_tool)

        args = {"to": "a@b.com", "subject": "Quote", "body": "Here you go"}
        out = await action_registry.execute_action("email.send", dict(args), _ctx())

        assert out["success"] is True
        assert calls == [("local-tools", "send_email", args)]

    @pytest.mark.asyncio
    async def test_policy_block_is_surfaced_not_bypassed(self, monkeypatch):
        import integrations.mcp_service as mcp_mod
        from core.action_registry import action_registry

        async def fake_execute_tool(self, server_id, tool_name, arguments, context=None):
            return {"error": "Email blocked by deterministic policy: restricted data",
                    "blocked_by": "email_policy", "status": "BLOCKED"}

        monkeypatch.setattr(mcp_mod.MCPService, "execute_tool", fake_execute_tool)

        out = await action_registry.execute_action(
            "email.send", {"to": "a@b.com", "body": "secret"}, _ctx())

        assert out["success"] is False
        assert out["blocked_by"] == "email_policy"
        assert out.get("status") == "BLOCKED"

    @pytest.mark.asyncio
    async def test_pending_approval_is_surfaced_not_sent(self, monkeypatch):
        """A HITL-required send returns an approval payload, never a send."""
        import integrations.mcp_service as mcp_mod
        from core.action_registry import action_registry

        async def fake_execute_tool(self, server_id, tool_name, arguments, context=None):
            return {"action_id": "hitl-1", "requires_approval": True,
                    "reason": "Email policy: external recipient"}

        monkeypatch.setattr(mcp_mod.MCPService, "execute_tool", fake_execute_tool)

        out = await action_registry.execute_action(
            "email.send", {"to": "external@x.com", "body": "hi"}, _ctx())

        assert out["success"] is False
        assert out["requires_approval"] is True
        assert out["action_id"] == "hitl-1"
