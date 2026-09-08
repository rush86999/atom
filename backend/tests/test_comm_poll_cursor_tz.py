"""Cursor timezone regression tests (Sep 2026).

The Outlook poller persisted NAIVE local ``datetime.now()`` cursors and
formatted them with a blind ``Z`` suffix — the watermark instant shifted by
the host offset (+05:30 here), so ``receivedDateTime gt <local-as-UTC>`` was
~5.5h in the FUTURE and every incremental poll returned an empty window
while the cursor happily advanced. The comms store stayed empty even though
new mail existed. These tests pin the fix: cursors are AWARE UTC end-to-end
(persist -> restore -> filter), and naive legacy values are assumed UTC.
"""
import json
from datetime import datetime, timezone
from pathlib import Path

from integrations.atom_communication_ingestion_pipeline import (
    CommunicationIngestionPipeline,
    _coerce_utc_ts,
    _format_graph_timestamp,
)


class TestFormatGraphTimestamp:
    def test_naive_is_assumed_utc(self):
        dt = datetime(2026, 9, 7, 23, 34, 56, 852060)  # legacy naive cursor
        assert _format_graph_timestamp(dt) == "2026-09-07T23:34:56.852060Z"

    def test_aware_utc_matches_naive_assumption(self):
        dt = datetime(2026, 9, 7, 23, 34, 56, 852060, tzinfo=timezone.utc)
        assert _format_graph_timestamp(dt) == "2026-09-07T23:34:56.852060Z"

    def test_whole_seconds_compact_form(self):
        assert _format_graph_timestamp(datetime(2026, 9, 1, 14, 42, 9)) == "2026-09-01T14:42:09Z"

    def test_offset_datetime_is_normalized(self):
        dt = datetime(2026, 9, 7, 14, 42, 9, tzinfo=timezone.utc)
        assert _format_graph_timestamp(dt) == "2026-09-07T14:42:09Z"


class TestCoerceUtcTs:
    def test_naive_string_to_aware_utc(self):
        out = _coerce_utc_ts("2026-09-07T23:34:56.852060")
        assert out is not None
        assert out.tzinfo is not None and out.utcoffset() == timezone.utc.utcoffset(None)
        assert out.hour == 23

    def test_z_string_to_aware_utc(self):
        out = _coerce_utc_ts("2026-09-07T14:42:09Z")
        assert out is not None and out.hour == 14

    def test_offset_string_to_aware_utc(self):
        out = _coerce_utc_ts("2026-09-07T14:42:09+00:00")
        assert out is not None and out.utcoffset() == timezone.utc.utcoffset(None)

    def test_naive_datetime_assumed_utc(self):
        out = _coerce_utc_ts(datetime(2026, 9, 7, 10, 0, 0))
        assert out is not None and out.tzinfo == timezone.utc and out.hour == 10

    def test_garbage_returns_none(self):
        assert _coerce_utc_ts("not-a-date") is None
        assert _coerce_utc_ts(None) is None


class TestLoadFetchState:
    def test_restores_cursors_as_aware_utc(self, tmp_path):
        state = {
            "fetch_timestamps": {
                # Legacy naive (local) value — must be assumed UTC, not crash.
                "last_fetch_outlook": "2026-09-07T23:34:56.858121",
                # Already-aware value round-tripped through isoformat().
                "last_fetch_outlook_owner1": "2026-09-07T14:42:09+00:00",
                "last_fetch_outlook_resume_owner1": "2026-09-01T09:00:00+00:00",
            },
            "seen_message_ids_by_owner": {},
        }
        path = Path(tmp_path) / "poll_fetch_state.json"
        path.write_text(json.dumps(state))

        obj = CommunicationIngestionPipeline.__new__(CommunicationIngestionPipeline)
        obj._fetch_state_path = path
        obj.fetch_timestamps = {}
        obj._seen_message_ids = {}
        obj._load_fetch_state()

        assert set(obj.fetch_timestamps) == set(state["fetch_timestamps"])
        for key, value in obj.fetch_timestamps.items():
            assert value.tzinfo is not None, f"{key} restored naive"
            assert value.utcoffset() == timezone.utc.utcoffset(None), key
        # The legacy naive 23:34 value must be treated as 23:34 UTC, which is
        # exactly what _format_graph_timestamp will send to Graph.
        assert _format_graph_timestamp(obj.fetch_timestamps["last_fetch_outlook"]) == (
            "2026-09-07T23:34:56.858121Z"
        )
