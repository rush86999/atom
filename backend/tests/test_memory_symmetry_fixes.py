"""P0.4 integration-symmetry audit follow-up fixes (TDD).

Red-first tests for the tracked follow-ups from the 2026-08-20 audit
(docs/architecture/AGENT_MEMORY_UNIFICATION_PLAN.md §7):

1. WhatsApp content bug — `_normalize_message` WhatsApp branch reads only
   `content` but `_transform_whatsapp_payload` emits `text` (ingestion_pipeline
   :3321) -> messages stored with EMPTY content / meaningless embeddings.
2. Slack modern bridge payload — slack_webhooks passes the inner
   `data.get("event", {})` instead of the full payload, so the UCB slack
   adapter (`payload.get("event", {})` -> empty) and `_transform_slack_payload`
   (needs top-level `type == "event_callback"`) both no-op.
3. Teams alias — `teams` is absent from `_KNOWN_COMM_INTEGRATIONS` (only
   `microsoft_teams` is listed), so the tiered A-path membership is accidental
   (shape heuristic) and the poller keyed on `microsoft_teams` never matches.
"""

import asyncio
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# ============================================================================
# 1. WhatsApp content/text/body field fallback
# ============================================================================


class TestWhatsAppNormalizeContentFallback:
    """The WhatsApp transformer emits `text` (ingestion_pipeline.py:3321) but
    the normalize branch reads only `content` -> empty content in the store."""

    def _pipeline(self):
        from integrations.atom_communication_ingestion_pipeline import (
            CommunicationIngestionPipeline,
        )

        return CommunicationIngestionPipeline(MagicMock())

    def test_whatsapp_text_field_is_preserved(self):
        pipe = self._pipeline()
        # This is exactly what _transform_whatsapp_payload emits (text key).
        record = {
            "id": "wa_msg_1",
            "direction": "inbound",
            "text": "Need the Q3 numbers by EOD",
            "sender_id": "15551234567",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        normalized = pipe._normalize_message("whatsapp", record)
        assert normalized["content"] == "Need the Q3 numbers by EOD"

    def test_whatsapp_body_field_fallback(self):
        pipe = self._pipeline()
        record = {"id": "w1", "body": "fallback body", "timestamp": datetime.now(timezone.utc).isoformat()}
        normalized = pipe._normalize_message("whatsapp", record)
        assert normalized["content"] == "fallback body"

    def test_whatsapp_content_still_wins_when_present(self):
        pipe = self._pipeline()
        record = {
            "id": "w2",
            "content": "explicit content",
            "text": "transformer text",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        normalized = pipe._normalize_message("whatsapp", record)
        assert normalized["content"] == "explicit content"

    def test_whatsapp_empty_stays_empty(self):
        pipe = self._pipeline()
        normalized = pipe._normalize_message("whatsapp", {})
        assert normalized["content"] == ""


# ============================================================================
# 2. Slack bridge full-payload dispatch
# ============================================================================


class TestSlackBridgeFullPayload:
    """slack_webhooks dispatches the inner event dict, not the full payload.
    The UCB slack adapter reads `payload.get("event", {})` and the tiered
    transformer expects a top-level `type == "event_callback"`, so the modern
    bridge A+B path was a silent no-op."""

    def test_route_passes_full_payload_to_bridge(self):
        import api.routes.webhooks.slack_webhooks as slack_mod

        full_payload = {
            "token": "x",
            "team_id": "T123",
            "type": "event_callback",
            "event": {
                "type": "message",
                "user": "U1",
                "text": "hello from slack",
                "channel": "C1",
                "ts": "1700000000.000100",
            },
        }
        req = MagicMock()
        req.body = AsyncMock(return_value=__import__("json").dumps(full_payload).encode())
        with patch.object(slack_mod, "verify_slack_webhook", return_value=True):
            with patch.object(slack_mod, "TenantDiscoveryService") as TDS:
                TDS.return_value.get_tenant_id_by_external_id = AsyncMock(return_value="tenant-1")
                with patch.object(slack_mod, "webhook_bridge") as bridge:
                    bridge.process_event = AsyncMock(return_value={"status": "processed"})
                    with patch.object(slack_mod, "get_webhook_registry"):
                        with patch.object(slack_mod, "get_db"):
                            from fastapi.testclient import TestClient

                            # Cannot easily build a full app; call the handler directly.
                            async def _call():
                                from sqlalchemy.orm import Session

                                db = MagicMock(spec=Session)
                                db.query.return_value.filter.return_value.first.return_value = MagicMock(
                                    config={"slack_signing_secret": "secret"}
                                )
                                registry = MagicMock()
                                return await slack_mod.slack_webhook(
                                    request=req,
                                    x_slack_signature="sig",
                                    x_slack_request_timestamp="1700000000",
                                    db=db,
                                    registry=registry,
                                )

                            result = asyncio.run(_call())

                assert bridge.process_event.called
                call_args = bridge.process_event.call_args[0]
                assert call_args[0] == "slack"
                # The FULL payload must be passed, not the inner event dict.
                assert call_args[2] == full_payload
                assert call_args[2].get("type") == "event_callback"

    def test_tiered_transform_accepts_full_payload(self):
        from core.ingestion_pipeline import IngestionPipelineService

        payload = {
            "team_id": "T123",
            "type": "event_callback",
            "event": {
                "type": "message",
                "user": "U1",
                "text": "hello from slack",
                "channel": "C1",
                "ts": "1700000000.000100",
            },
        }
        svc = IngestionPipelineService(tenant_id="tenant-1", workspace_id="ws-1")
        records = asyncio.run(svc._transform_slack_payload(payload))
        assert len(records) == 1
        assert records[0]["type"] == "slack_message"
        assert records[0]["text"] == "hello from slack"


# ============================================================================
# 3. Teams alias in the known-comm integration list
# ============================================================================


class TestTeamsKnownCommAlias:
    """`teams` is the platform name used by the bridge/route/poller, but only
    `microsoft_teams` is in _KNOWN_COMM_INTEGRATIONS, so the tiered A-path
    membership is accidental (record-shape heuristic) rather than explicit."""

    def test_teams_is_a_known_comm_integration(self):
        from core.ingestion_pipeline import IngestionPipelineService

        assert "teams" in IngestionPipelineService._KNOWN_COMM_INTEGRATIONS

    def test_teams_record_routes_to_comm_store(self):
        from core.ingestion_pipeline import IngestionPipelineService

        record = {
            "type": "teams_message",
            "id": "t1",
            "text": "team meeting at 3pm",
            "from": "bot",
        }
        assert IngestionPipelineService._is_communication_record("teams", record) is True

    def test_poller_accepts_teams_alias(self):
        from unittest.mock import AsyncMock, MagicMock, patch

        from integrations.atom_communication_ingestion_pipeline import (
            CommunicationIngestionPipeline,
        )

        pipe = CommunicationIngestionPipeline(MagicMock())
        with patch.object(pipe, "_fetch_teams_messages", new_callable=AsyncMock) as fetch:
            fetch.return_value = [
                {"id": "t1", "text": "meeting", "from": "user",
                 "timestamp": datetime.now(timezone.utc).isoformat()}
            ]
            messages = asyncio.run(pipe._fetch_new_messages("teams"))
            fetch.assert_awaited_once()
            assert len(messages) == 1


# ============================================================================
# 4. Email ingestion data-loss (poller + webhook key mismatch)
# ============================================================================


class TestEmailNormalizePreservesFields:
    """The email branch of _normalize_message reads `body`/`from`/`to`/`date`,
    but every live email producer emits `content`/`sender[_email]`/`recipient`/
    `timestamp` (Outlook poller :1610, Gmail poller :1466, Outlook webhook
    transform :2973). Result: sender=None, recipient=None, content="", and
    timestamp=now() in the stored atom_communications row — the full email body
    never reaches the graph/comms store."""

    def _pipeline(self):
        from integrations.atom_communication_ingestion_pipeline import (
            CommunicationIngestionPipeline,
        )

        return CommunicationIngestionPipeline(MagicMock())

    def test_outlook_poller_record_preserves_body_and_headers(self):
        pipe = self._pipeline()
        # Exactly what _fetch_outlook_messages emits (:1610-1635).
        record = {
            "id": "msg-1",
            "app_type": "outlook",
            "timestamp": datetime(2026, 8, 1, 12, 0, 0, tzinfo=timezone.utc),
            "direction": "inbound",
            "sender": "John Smith",
            "sender_email": "john@acme.com",
            "recipient": "sales@atom.io",
            "subject": "Q3 quote for ACME Fab",
            "content": "Hi, please find the full Q3 quote attached. Regards, John",
            "content_type": "text",
            "attachments": [],
            "metadata": {"conversation_id": "conv-1"},
        }
        normalized = pipe._normalize_message("outlook", record)
        assert normalized["content"] == "Hi, please find the full Q3 quote attached. Regards, John"
        assert normalized["sender"] == "John Smith"
        assert normalized["recipient"] == "sales@atom.io"
        assert normalized["subject"] == "Q3 quote for ACME Fab"
        assert normalized["timestamp"] == datetime(2026, 8, 1, 12, 0, 0, tzinfo=timezone.utc)

    def test_gmail_poller_record_preserves_fields(self):
        pipe = self._pipeline()
        record = {
            "id": "g1",
            "app_type": "gmail",
            "timestamp": datetime(2026, 8, 1, 9, 0, 0, tzinfo=timezone.utc),
            "direction": "inbound",
            "sender": "Jane Doe",
            "sender_email": "jane@example.com",
            "recipient": "me@atom.io",
            "subject": "Meeting notes",
            "content": "Notes from the meeting: budget approved.",
            "metadata": {"thread_id": "thread-1"},
        }
        normalized = pipe._normalize_message("gmail", record)
        assert normalized["content"] == "Notes from the meeting: budget approved."
        assert normalized["sender"] == "Jane Doe"
        assert normalized["recipient"] == "me@atom.io"
        assert normalized["timestamp"] == datetime(2026, 8, 1, 9, 0, 0, tzinfo=timezone.utc)

    def test_webhook_outlook_record_preserves_fields(self):
        pipe = self._pipeline()
        # Exactly what _transform_outlook_payload emits (:2973-2981).
        record = {
            "id": "w1",
            "sender_id": "sender@acme.com",
            "subject": "Re: budget",
            "content": "Saw your budget note, approved.",
            "timestamp": "2026-08-01T10:00:00Z",
            "metadata": {"web_link": "https://..."},
        }
        normalized = pipe._normalize_message("outlook", record)
        assert normalized["content"] == "Saw your budget note, approved."
        assert normalized["sender"] == "sender@acme.com"
        assert normalized["timestamp"] == datetime.fromisoformat("2026-08-01T10:00:00Z")

    def test_legacy_body_from_to_date_shape_still_works(self):
        # The classic MIME-ish shape (body/from/to/date) must keep working.
        pipe = self._pipeline()
        record = {
            "id": "e1",
            "date": "2026-08-01T08:00:00",
            "from": "user",
            "to": "x@y.z",
            "subject": "legacy",
            "body": "legacy body text",
        }
        normalized = pipe._normalize_message("email", record)
        assert normalized["content"] == "legacy body text"
        assert normalized["direction"] == "outbound"
        assert normalized["sender"] == "user"

    def test_webhook_body_preview_preferred_over_content(self):
        # The webhook transform sets content = bodyPreview or body.content; the
        # normalize should prefer bodyPreview when present (raw Graph body may
        # be HTML) but never fall back to empty.
        pipe = self._pipeline()
        record = {
            "id": "w2",
            "sender_id": "a@b.c",
            "subject": "preview",
            "bodyPreview": "The preview text",
            "content": "<html><body>Full HTML</body></html>",
            "timestamp": "2026-08-01T10:00:00Z",
        }
        normalized = pipe._normalize_message("outlook", record)
        assert normalized["content"] in ("The preview text", "<html><body>Full HTML</body></html>")
        assert normalized["content"] != ""