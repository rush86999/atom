"""Tests for the email branch of
CommunicationIngestionPipeline._normalize_message_impl.

Regression (Aug 2026): the Outlook poller (_fetch_outlook_messages) emits
``sender/sender_email/recipient/content/timestamp/direction`` but the email
normalization branch only read ``from/to/body/date``. Every polled message
was therefore stored in atom_communications with EMPTY sender/recipient/
content and a poll-time (not received-time) timestamp, which made the whole
mailbox invisible to FTS/vector retrieval — chat agents concluded "Outlook
isn't connected" because nothing ever matched.
"""

from datetime import datetime

import pytest

from integrations.atom_communication_ingestion_pipeline import (
    CommunicationIngestionPipeline,
)


@pytest.fixture
def pipeline() -> CommunicationIngestionPipeline:
    """Normalization is a pure method — skip __init__ (heavy LanceDB/model
    init) and call it directly."""
    return CommunicationIngestionPipeline.__new__(CommunicationIngestionPipeline)


def make_poller_message(**overrides) -> dict:
    """Shape exactly as _fetch_outlook_messages emits it."""
    msg = {
        "id": "AAMkAD-graph-message-id",
        "app_type": "outlook",
        "timestamp": datetime(2026, 8, 28, 10, 51, 38),
        "direction": "inbound",
        "sender": "Zoho Forms",
        "sender_email": "notifications@zohoforms.ca",
        "recipient": "rish@brennan.ca, vipul@brennan.ca",
        "subject": "New Quote Request From New Lead",
        "content": (
            "<html><body><p>Name: Mark, Kellam</p>"
            "<p>Company: WFS Ltd</p>"
            "<p>Email: mkellam@wfsltd.ca</p></body></html>"
        ),
        "content_type": "html",
        "attachments": [],
        "metadata": {"conversation_id": "AAQkAD-conversation"},
    }
    msg.update(overrides)
    return msg


class TestOutlookPollerFieldMapping:
    def test_poller_payload_populates_sender_recipient_content(
        self, pipeline
    ):
        out = pipeline._normalize_message("outlook", make_poller_message())

        # The email ADDRESS wins for sender (searchable), not the display name
        assert out["sender"] == "notifications@zohoforms.ca"
        assert out["recipient"] == "rish@brennan.ca, vipul@brennan.ca"
        assert out["subject"] == "New Quote Request From New Lead"
        assert "Mark, Kellam" in out["content"]
        assert "mkellam@wfsltd.ca" in out["content"]

    def test_poller_payload_preserves_received_timestamp(self, pipeline):
        out = pipeline._normalize_message("outlook", make_poller_message())
        # Must be the received time, not poll-time now()
        assert out["timestamp"] == datetime(2026, 8, 28, 10, 51, 38)

    def test_html_body_is_stripped_to_text(self, pipeline):
        out = pipeline._normalize_message("outlook", make_poller_message())
        assert "<html>" not in out["content"]
        assert "<p>" not in out["content"]

    def test_direction_and_metadata_passthrough(self, pipeline):
        out = pipeline._normalize_message("outlook", make_poller_message())
        assert out["direction"] == "inbound"
        assert out["metadata"]["email_metadata"] == {
            "conversation_id": "AAQkAD-conversation"
        }
        assert out["id"] == "AAMkAD-graph-message-id"


class TestLegacyEmailFieldMapping:
    def test_from_to_body_payload_still_works(self, pipeline):
        legacy = {
            "id": "legacy-1",
            "from": "a@b.c",
            "to": "d@e.f",
            "body": "plain text body",
            "date": "2026-08-01T12:00:00",
        }
        out = pipeline._normalize_message("email", legacy)
        assert out["sender"] == "a@b.c"
        assert out["recipient"] == "d@e.f"
        assert out["content"] == "plain text body"
        assert out["timestamp"] == datetime(2026, 8, 1, 12, 0, 0)

    def test_from_user_is_outbound(self, pipeline):
        legacy = {"from": "user", "to": "x@y.z", "body": "hi"}
        out = pipeline._normalize_message("gmail", legacy)
        assert out["direction"] == "outbound"

    def test_missing_fields_fall_back_to_defaults(self, pipeline):
        out = pipeline._normalize_message("email", {"id": "empty-1"})
        assert out["sender"] is None
        assert out["recipient"] is None
        assert out["content"] == ""
        assert isinstance(out["timestamp"], datetime)
