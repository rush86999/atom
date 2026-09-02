"""Agent can send into the same email thread (TDD).

Wires the previously-dead reply primitives into the agent's send path:
- MCP send_email accepts thread_id / reply_to_message_id / reply_all
- UniversalIntegrationService routes threaded sends to
  OutlookService.reply_to_email (Graph /reply) and
  GmailService.reply_to_message (In-Reply-To/References + threadId)
- A thread reply without explicit recipients requires human approval —
  the deterministic egress allowlist cannot see thread-derived recipients.

Zero network / LLM / DB: services are mocked at the registry boundary.
"""
import pytest
from unittest.mock import AsyncMock, MagicMock

from core.email_policy import APPROVE, BLOCK, evaluate_email_action
from integrations.universal_integration_service import UniversalIntegrationService


def _uis_with(comm):
    registry = AsyncMock()
    registry.get_service_instance = AsyncMock(return_value=comm)
    return UniversalIntegrationService(), {"registry": registry, "user_id": "u1", "tenant_id": "t1"}


class TestUISThreadedOutlook:
    """Outlook send_message with thread params replies via Graph /reply."""

    @pytest.mark.asyncio
    async def test_reply_to_message_id(self):
        comm = AsyncMock()
        comm.reply_to_email = AsyncMock(return_value=True)
        svc, ctx = _uis_with(comm)

        result = await svc._execute_communication(
            "outlook", "send_message",
            {"reply_to_message_id": "m1", "body": "Here is the update."},
            ctx,
        )

        assert result["status"] == "success"
        comm.send_email.assert_not_awaited()
        kwargs = comm.reply_to_email.await_args.kwargs
        assert kwargs["message_id"] == "m1"
        assert kwargs["comment"] == "Here is the update."
        assert kwargs["reply_all"] is False
        assert kwargs["user_id"] == "u1"

    @pytest.mark.asyncio
    async def test_reply_via_conversation_id_resolves_latest_message(self):
        comm = AsyncMock()
        comm.get_latest_conversation_message_id = AsyncMock(return_value="m-latest")
        comm.reply_to_email = AsyncMock(return_value=True)
        svc, ctx = _uis_with(comm)

        result = await svc._execute_communication(
            "outlook", "send_message",
            {"thread_id": "conv-9", "body": "Following up."},
            ctx,
        )

        assert result["status"] == "success"
        # Same auto-created attribute instance, so identity assert is exact.
        comm.get_latest_conversation_message_id.assert_awaited_once_with(
            "u1", "conv-9", token=comm.access_token,
        )
        assert comm.reply_to_email.await_args.kwargs["message_id"] == "m-latest"

    @pytest.mark.asyncio
    async def test_unknown_conversation_errors_without_replying(self):
        comm = AsyncMock()
        comm.get_latest_conversation_message_id = AsyncMock(return_value=None)
        comm.reply_to_email = AsyncMock(return_value=True)
        svc, ctx = _uis_with(comm)

        result = await svc._execute_communication(
            "outlook", "send_message",
            {"thread_id": "conv-404", "body": "hi"},
            ctx,
        )

        assert result["status"] == "error"
        assert "conv-404" in result["message"]
        comm.reply_to_email.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_reply_all_flag_reaches_graph(self):
        comm = AsyncMock()
        comm.reply_to_email = AsyncMock(return_value=True)
        svc, ctx = _uis_with(comm)

        await svc._execute_communication(
            "outlook", "send_message",
            {"reply_to_message_id": "m1", "body": "b", "reply_all": True},
            ctx,
        )

        assert comm.reply_to_email.await_args.kwargs["reply_all"] is True

    @pytest.mark.asyncio
    async def test_standalone_send_unaffected(self):
        comm = AsyncMock()
        comm.send_email = AsyncMock(return_value={"id": "s1"})
        svc, ctx = _uis_with(comm)

        result = await svc._execute_communication(
            "outlook", "send_message",
            {"to": "a@b.com", "subject": "s", "body": "b"},
            ctx,
        )

        assert result["status"] == "success"
        comm.reply_to_email.assert_not_awaited()
        comm.send_email.assert_awaited_once()


class TestUISThreadedGmail:
    """Gmail send_message with thread params replies via reply_to_message.

    GmailService methods are sync — the branch must run them off the event
    loop (they were awaited directly before, which raised TypeError on every
    gmail send).
    """

    @pytest.mark.asyncio
    async def test_thread_reply_without_recipient_uses_reply_to_message(self):
        comm = MagicMock()
        comm.reply_to_message = MagicMock(return_value={"id": "g1"})
        svc, ctx = _uis_with(comm)

        result = await svc._execute_communication(
            "gmail", "send_message",
            {"thread_id": "t1", "body": "b"},
            ctx,
        )

        assert result["status"] == "success"
        assert result["data"] == {"id": "g1"}
        assert comm.reply_to_message.call_args.args[:2] == ("t1", "b")
        comm.send_message.assert_not_called()

    @pytest.mark.asyncio
    async def test_explicit_recipient_keeps_send_message_with_thread(self):
        comm = MagicMock()
        comm.send_message = MagicMock(return_value={"id": "g2"})
        svc, ctx = _uis_with(comm)

        result = await svc._execute_communication(
            "gmail", "send_message",
            {"to": "a@b.com", "subject": "s", "body": "b", "thread_id": "t1"},
            ctx,
        )

        assert result["status"] == "success"
        comm.reply_to_message.assert_not_called()
        kwargs = comm.send_message.call_args.kwargs
        assert kwargs["to"] == "a@b.com"
        assert kwargs["thread_id"] == "t1"

    @pytest.mark.asyncio
    async def test_reply_to_message_id_resolves_thread_id(self):
        comm = MagicMock()
        comm.get_message = MagicMock(return_value={"id": "gm1", "threadId": "t9"})
        comm.reply_to_message = MagicMock(return_value={"id": "g3"})
        svc, ctx = _uis_with(comm)

        result = await svc._execute_communication(
            "gmail", "send_message",
            {"reply_to_message_id": "gm1", "body": "b"},
            ctx,
        )

        assert result["status"] == "success"
        assert comm.get_message.call_args.args[0] == "gm1"
        assert comm.reply_to_message.call_args.args[0] == "t9"

    @pytest.mark.asyncio
    async def test_message_without_thread_errors(self):
        comm = MagicMock()
        comm.get_message = MagicMock(return_value={})
        svc, ctx = _uis_with(comm)

        result = await svc._execute_communication(
            "gmail", "send_message",
            {"reply_to_message_id": "gm-orphan", "body": "b"},
            ctx,
        )

        assert result["status"] == "error"

    @pytest.mark.asyncio
    async def test_standalone_send_runs_off_event_loop(self):
        comm = MagicMock()
        comm.send_message = MagicMock(return_value={"id": "g4"})
        svc, ctx = _uis_with(comm)

        result = await svc._execute_communication(
            "gmail", "send_message",
            {"to": "a@b.com", "subject": "s", "body": "b"},
            ctx,
        )

        assert result["status"] == "success"
        assert comm.send_message.call_args.kwargs["thread_id"] is None


class TestOutlookConversationResolution:
    def _svc(self):
        from integrations.outlook_service import OutlookService

        return OutlookService()

    @pytest.mark.asyncio
    async def test_returns_latest_message_id(self):
        svc = self._svc()
        svc._make_graph_request = AsyncMock(
            return_value={"value": [{"id": "m1", "conversationId": "c1"}]}
        )

        resolved = await svc.get_latest_conversation_message_id("u1", "c1")

        assert resolved == "m1"
        endpoint = svc._make_graph_request.await_args.args[1]
        assert "/me/messages" in endpoint
        assert "conversationId" in endpoint
        assert "receivedDateTime" in endpoint

    @pytest.mark.asyncio
    async def test_returns_none_when_conversation_empty(self):
        svc = self._svc()
        svc._make_graph_request = AsyncMock(return_value={"value": []})

        assert await svc.get_latest_conversation_message_id("u1", "c1") is None

    @pytest.mark.asyncio
    async def test_returns_none_on_graph_failure(self):
        svc = self._svc()
        svc._make_graph_request = AsyncMock(return_value=None)

        assert await svc.get_latest_conversation_message_id("u1", "c1") is None


class TestEmailPolicyThreadReply:
    def test_thread_reply_without_recipients_requires_approval(self):
        dec = evaluate_email_action({"thread_id": "t1", "body": "hi"})
        assert dec["decision"] == APPROVE
        assert dec["policy"] == "thread_reply_recipients"

    def test_reply_to_message_id_requires_approval_too(self):
        dec = evaluate_email_action({"reply_to_message_id": "m1", "body": "hi"})
        assert dec["decision"] == APPROVE
        assert dec["policy"] == "thread_reply_recipients"

    def test_pii_in_thread_reply_still_blocks(self):
        """Sensitivity BLOCK outranks the reply-approval rule."""
        dec = evaluate_email_action(
            {"thread_id": "t1", "body": "My SSN is 123-45-6789"}
        )
        assert dec["decision"] == BLOCK
        assert dec["policy"] == "sensitivity"

    def test_explicit_recipient_keeps_normal_egress_gate(self, monkeypatch):
        monkeypatch.delenv("ATOM_EMAIL_ALLOWED_OUTBOUND_DOMAINS", raising=False)
        dec = evaluate_email_action(
            {"thread_id": "t1", "to": "attacker@gmail.com", "body": "hi"}
        )
        assert dec["decision"] == APPROVE
        assert dec["policy"] == "recipient_allowlist"

    def test_conversation_id_counts_as_thread_reply(self):
        dec = evaluate_email_action({"conversation_id": "c1", "body": "hi"})
        assert dec["decision"] == APPROVE
        assert dec["policy"] == "thread_reply_recipients"


class TestMCPSchemaExposesThreading:
    @pytest.mark.asyncio
    async def test_send_email_schema_documents_thread_params(self):
        from integrations.mcp_service import MCPService

        tools = await MCPService().get_server_tools("local-tools")
        send_email = next(t for t in tools if t["name"] == "send_email")
        assert "thread_id" in send_email["parameters"]
        assert "reply_to_message_id" in send_email["parameters"]
        assert "reply_all" in send_email["parameters"]
