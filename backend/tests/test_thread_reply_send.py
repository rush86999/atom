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
        # Graph returns conversation rows unordered (the conversationId
        # filter can't carry a $orderby) — the resolver must pick the
        # newest receivedDateTime itself.
        svc._make_graph_request = AsyncMock(
            return_value={
                "value": [
                    {"id": "m-old", "conversationId": "c1",
                     "receivedDateTime": "2026-09-01T10:00:00Z"},
                    {"id": "m-new", "conversationId": "c1",
                     "receivedDateTime": "2026-09-02T17:33:17Z"},
                ]
            }
        )

        resolved = await svc.get_latest_conversation_message_id("u1", "c1")

        assert resolved == "m-new"
        messages_calls = [
            c for c in svc._make_graph_request.await_args_list
            if "/me/messages" in str(c.args[1])
        ]
        assert messages_calls, "conversation lookup never hit /me/messages"
        endpoint = messages_calls[0].args[1]
        assert "conversationId" in endpoint
        # conversationId $filter + $orderby is a Graph 400 InefficientFilter.
        assert "$orderby" not in endpoint

    @pytest.mark.asyncio
    async def test_prefers_external_sender_in_mixed_thread(self):
        """Customer threads carry internal legs (colleague notes in the same
        conversation) — the reply anchor must be the newest EXTERNAL
        message, not the thread's overall newest (an internal note)."""
        svc = self._svc()

        async def fake_graph(user_id, endpoint, *args, **kwargs):
            if endpoint == "/me":
                return {"id": "u1", "mail": "rish@brennan.ca"}
            return {
                "value": [
                    {"id": "m-internal", "receivedDateTime": "2026-09-02T17:33:17Z",
                     "from": {"emailAddress": {"address": "vipul@brennan.ca"}}},
                    {"id": "m-external", "receivedDateTime": "2026-09-02T17:08:35Z",
                     "from": {"emailAddress": {"address": "jschulz@blumetric.ca"}}},
                ]
            }

        svc._make_graph_request = AsyncMock(side_effect=fake_graph)

        resolved = await svc.get_latest_conversation_message_id("u1", "c1")

        assert resolved == "m-external"

    @pytest.mark.asyncio
    async def test_internal_only_thread_falls_back_to_newest(self):
        svc = self._svc()

        async def fake_graph(user_id, endpoint, *args, **kwargs):
            if endpoint == "/me":
                return {"id": "u1", "mail": "rish@brennan.ca"}
            return {
                "value": [
                    {"id": "m-older", "receivedDateTime": "2026-09-01T10:00:00Z",
                     "from": {"emailAddress": {"address": "vipul@brennan.ca"}}},
                    {"id": "m-newest", "receivedDateTime": "2026-09-02T17:33:17Z",
                     "from": {"emailAddress": {"address": "chandrakant@brennan.ca"}}},
                ]
            }

        svc._make_graph_request = AsyncMock(side_effect=fake_graph)

        resolved = await svc.get_latest_conversation_message_id("u1", "c1")

        assert resolved == "m-newest"

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


class TestInternalThreadQuoteGuard:
    """Threaded replies to an external audience must not carry text that
    exists only on the thread's internal legs (colleague notes riding a
    customer conversation)."""

    def _svc(self, anchor_from: str = "jschulz@blumetric.ca",
             with_sent_mail: bool = False):
        from integrations.outlook_service import OutlookService

        svc = OutlookService()

        async def fake_graph(user_id, endpoint, *args, **kwargs):
            if endpoint == "/me":
                return {"id": "u1", "mail": "rish@brennan.ca"}
            if endpoint.startswith("/me/messages/") and "$select=conversationId" in endpoint:
                return {
                    "conversationId": "conv-9",
                    "from": {"emailAddress": {"address": anchor_from}},
                    "toRecipients": [{"emailAddress": {"address": "rish@brennan.ca"}}],
                    "ccRecipients": [],
                }
            if endpoint.startswith("/me/messages?"):
                messages = [
                    {"receivedDateTime": "2026-09-02T17:33:17Z",
                     "from": {"emailAddress": {"address": "vipul@brennan.ca"}},
                     "body": {"content": "<div>Let's hold the 13k fallback "
                                         "price internal until Jacob pushes back.</div>"}},
                    {"receivedDateTime": "2026-09-02T17:08:35Z",
                     "from": {"emailAddress": {"address": "jschulz@blumetric.ca"}},
                     "body": {"content": "<div>We had our eyes on a Hydmech "
                                         "DM10 bandsaw for our shop floor.</div>"}},
                ]
                if with_sent_mail:
                    messages.append({
                        "receivedDateTime": "2026-09-03T09:00:00Z",
                        "from": {"emailAddress": {"address": "rish@brennan.ca"}},
                        "toRecipients": [
                            {"emailAddress": {"address": "jschulz@blumetric.ca"}}],
                        "body": {"content": "<div>The Linmac WG-350DSAV is in "
                                            "stock at our warehouse for immediate "
                                            "delivery.</div>"},
                    })
                return {"value": messages}
            if "/reply" in endpoint:
                return {}
            return None

        svc._make_graph_request = AsyncMock(side_effect=fake_graph)
        # Deterministic stub embedder: zero vectors keep the semantic tier
        # inert; it is exercised end-to-end in the dedicated test below.
        svc._thread_embed = AsyncMock(
            side_effect=lambda texts: [[0.0] * 8 for _ in texts]
        )
        return svc

    @pytest.mark.asyncio
    async def test_blocks_reply_quoting_internal_only_text(self):
        svc = self._svc()

        ok = await svc.reply_to_email(
            "u1", "m-anchor",
            "Hi Jacob — let's hold the 13k fallback price internal until "
            "Jacob pushes back. Regards.",
            to_recipients=["jschulz@blumetric.ca"],
        )

        assert ok is False
        detail = svc.last_send_error or {}
        assert detail.get("policy") == "internal_thread_quote"
        assert detail.get("quotes")
        assert not [
            c for c in svc._make_graph_request.await_args_list
            if "/reply" in str(c.args[1])
        ], "blocked reply must never reach the wire"

    @pytest.mark.asyncio
    async def test_customer_safe_body_sends(self):
        svc = self._svc()

        ok = await svc.reply_to_email(
            "u1", "m-anchor",
            "Hi Jacob — a Hydmech DM10 bandsaw equivalent is available for "
            "your shop floor. Regards.",
            to_recipients=["jschulz@blumetric.ca"],
        )

        assert ok is True
        assert svc.last_send_error is None

    @pytest.mark.asyncio
    async def test_own_prior_customer_mail_is_requotable(self):
        """Our own sent mail addressed to the customer is customer-visible —
        re-quoting it in a follow-up is normal, not an internal leak."""
        svc = self._svc(with_sent_mail=True)

        ok = await svc.reply_to_email(
            "u1", "m-anchor",
            "Following up: the Linmac WG-350DSAV is in stock at our "
            "warehouse for immediate delivery. Regards.",
            to_recipients=["jschulz@blumetric.ca"],
        )

        assert ok is True
        assert svc.last_send_error is None

    @pytest.mark.asyncio
    async def test_internal_audience_reply_not_gated(self):
        """Replying on an internal leg (colleague sender, no external
        recipients) may quote internal discussion freely."""
        svc = self._svc(anchor_from="vipul@brennan.ca")

        ok = await svc.reply_to_email(
            "u1", "m-anchor",
            "Noted — holding the 13k fallback price internal until Jacob "
            "pushes back.",
        )

        assert ok is True
        assert svc.last_send_error is None

    @pytest.mark.asyncio
    async def test_override_sends_with_explicit_decision(self):
        svc = self._svc()

        ok = await svc.reply_to_email(
            "u1", "m-anchor",
            "We can hold the 13k fallback price internal until Jacob pushes back.",
            to_recipients=["jschulz@blumetric.ca"],
            override_internal_quote=True,
        )

        assert ok is True

    @pytest.mark.asyncio
    async def test_semantic_tier_blocks_paraphrased_internal_quote(self):
        """A paraphrase with no verbatim overlap still blocks when the
        embedder scores it against internal-only text and content words
        corroborate the match."""
        svc = self._svc()

        async def embed_fn(texts):
            return [
                [1.0, 0.0] if "13k fallback" in t
                else [0.9, 0.4] if "strictly confidential" in t
                else [0.0, 1.0]
                for t in texts
            ]

        svc._thread_embed = embed_fn

        ok = await svc.reply_to_email(
            "u1", "m-anchor",
            "Hi Jacob — we should keep the 13k floor strictly confidential "
            "among ourselves. Regards.",
            to_recipients=["jschulz@blumetric.ca"],
        )

        assert ok is False
        detail = svc.last_send_error or {}
        assert detail.get("policy") == "internal_thread_quote"
        assert any(q.get("match") == "semantic" for q in detail.get("quotes") or [])


class TestLegPagination:
    @pytest.mark.asyncio
    async def test_pagination_reaches_beyond_first_page(self):
        """Internal-only text on page 2 of a long thread is still guarded —
        the resolver follows @odata.nextLink instead of stopping at page 1."""
        from integrations.outlook_service import OutlookService

        svc = OutlookService()
        list_calls = {"n": 0}

        async def paginated(user_id, endpoint, *args, **kwargs):
            if endpoint == "/me":
                return {"id": "u1", "mail": "rish@brennan.ca"}
            if endpoint.startswith("/me/messages/") and "$select=conversationId" in endpoint:
                return {"conversationId": "conv-9"}
            if endpoint.startswith("/me/messages?"):
                list_calls["n"] += 1
                if list_calls["n"] == 1:
                    return {
                        "value": [{
                            "receivedDateTime": "2026-09-01T10:00:00Z",
                            "from": {"emailAddress": {"address": "jschulz@blumetric.ca"}},
                            "body": {"content": "<div>Page one customer content.</div>"},
                        }],
                        "@odata.nextLink": (
                            "https://graph.microsoft.com/v1.0/me/messages?$skiptoken=abc"
                        ),
                    }
                return {"value": [{
                    "receivedDateTime": "2026-09-02T17:33:17Z",
                    "from": {"emailAddress": {"address": "vipul@brennan.ca"}},
                    "body": {"content": "<div>Keep the 13k fallback price "
                                        "internal until Jacob pushes back.</div>"},
                }]}
            if "/reply" in endpoint:
                return {}
            return None

        svc._make_graph_request = AsyncMock(side_effect=paginated)
        svc._thread_embed = AsyncMock(
            side_effect=lambda texts: [[0.0] * 8 for _ in texts]
        )

        ok = await svc.reply_to_email(
            "u1", "m-anchor",
            "Hi Jacob — keep the 13k fallback price internal until Jacob "
            "pushes back. Regards.",
            to_recipients=["jschulz@blumetric.ca"],
        )

        assert list_calls["n"] == 2, "nextLink page was never fetched"
        assert ok is False
        assert (svc.last_send_error or {}).get("policy") == "internal_thread_quote"
