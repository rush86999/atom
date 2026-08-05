"""
Tests for Teams webhook dedup key (core/webhook_handlers.py).

The Teams dedup key used `raw_event.get('id', '')` — but Microsoft Graph
change notifications have NO top-level `id`; the message id lives inside
`value[*].id`. So every Teams webhook got the constant key "teams_", and
after the first message, ALL subsequent Teams messages were silently dropped
as duplicates.
"""

import pytest
from core.webhook_handlers import WebhookProcessor


@pytest.fixture
def proc():
    return WebhookProcessor()


class TestTeamsWebhookDedup:
    def test_two_distinct_teams_events_not_treated_as_duplicate(self, proc):
        """Two distinct Teams messages (each with no top-level 'id') must NOT
        collide on the dedup key 'teams_'."""
        # Microsoft Graph envelope: no top-level 'id', message id inside value[0].id
        event1_raw = {
            "value": [{"id": "msg-A", "@odata.type": "#Microsoft.Graph.chatMessage",
                        "body": {"content": "hello"}, "from": {"user": {"displayName": "Alice"}}}]
        }
        event2_raw = {
            "value": [{"id": "msg-B", "@odata.type": "#Microsoft.Graph.chatMessage",
                        "body": {"content": "world"}, "from": {"user": {"displayName": "Bob"}}}]
        }

        # Build the dedup keys the way process_teams_webhook does.
        key1 = proc._teams_dedup_key(event1_raw)
        key2 = proc._teams_dedup_key(event2_raw)

        assert key1 != key2, (
            f"Two distinct Teams events produced the same dedup key ({key1}) — "
            f"the second message would be silently dropped as a duplicate."
        )

    def test_teams_dedup_key_uses_message_id(self, proc):
        """The key should incorporate the actual message id from value[*]."""
        raw = {"value": [{"id": "msg-XYZ"}]}
        key = proc._teams_dedup_key(raw)
        assert "msg-XYZ" in key

    def test_teams_dedup_key_falls_back_on_missing_id(self, proc):
        """If no message id exists at all, the key should still be unique per payload."""
        raw1 = {"value": [{"body": {"content": "a"}}]}
        raw2 = {"value": [{"body": {"content": "b"}}]}
        key1 = proc._teams_dedup_key(raw1)
        key2 = proc._teams_dedup_key(raw2)
        assert key1 != key2
