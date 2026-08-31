"""Tests for CommunicationIngestionPipeline poll re-fetch protection.

Regression (Aug 2026): fetch cursors lived in an in-memory dict, so every
backend restart re-fetched the newest mailbox page and re-added it — 749
distinct Outlook messages had become 21k+ duplicate rows in
atom_communications (and 20GB of Lance version manifests). These tests pin
the two halves of the fix: persisted cursors + id-dedup of fetched messages.
"""

import json
from datetime import datetime, timedelta
from pathlib import Path
from types import SimpleNamespace

import pytest

from integrations.atom_communication_ingestion_pipeline import (
    CommunicationIngestionPipeline,
)


@pytest.fixture
def pipeline(tmp_path: Path) -> CommunicationIngestionPipeline:
    memory_manager = SimpleNamespace(
        db_path=str(tmp_path / "atom_memory"),
        db=None,
        connections_table=None,
        initialize=lambda: None,
    )
    (tmp_path / "atom_memory").mkdir()
    return CommunicationIngestionPipeline(memory_manager=memory_manager)


def _patch_fetch(pipeline, monkeypatch, captured):
    async def fake_fetch(last_fetch):
        captured["last_fetch"] = last_fetch
        return [dict(m) for m in captured["messages"]]

    monkeypatch.setattr(
        pipeline,
        "_fetch_outlook_messages",
        fake_fetch,
    )


class TestCursorPersistence:
    def test_cursors_survive_restart(self, pipeline, monkeypatch):
        pipeline.fetch_timestamps["last_fetch_outlook"] = datetime(2026, 8, 28, 12, 0, 0)
        pipeline._save_fetch_state()

        # A fresh pipeline (simulated restart) restores the cursor
        restarted = CommunicationIngestionPipeline(
            memory_manager=pipeline.memory_manager
        )
        assert restarted.fetch_timestamps["last_fetch_outlook"] == datetime(
            2026, 8, 28, 12, 0, 0
        )

    def test_corrupt_state_file_does_not_crash(self, pipeline):
        pipeline._fetch_state_path.write_text("{not json")
        restarted = CommunicationIngestionPipeline(
            memory_manager=pipeline.memory_manager
        )
        assert restarted.fetch_timestamps == {}


class TestRefetchDedup:
    @pytest.mark.asyncio
    async def test_same_ids_are_not_ingested_twice(self, pipeline, monkeypatch):
        message = {
            "id": "graph-msg-1",
            "app_type": "outlook",
            "subject": "New Quote Request From New Lead",
            "sender": "Zoho Forms",
            "sender_email": "notifications@zohoforms.ca",
            "content": "Name: Mark, Kellam",
        }
        captured = {"messages": [message], "last_fetch": "unset"}
        _patch_fetch(pipeline, monkeypatch, captured)

        ingested = []
        monkeypatch.setattr(
            pipeline,
            "ingest_message",
            lambda app_type, msg: ingested.append(msg["id"]) or __import__("asyncio").sleep(0),
        )

        first = await pipeline._fetch_new_messages("outlook")
        assert [m["id"] for m in first] == ["graph-msg-1"]

        # Second poll returns the same message (cold cursor / overlap):
        # the dedup guard must drop it instead of re-ingesting.
        second = await pipeline._fetch_new_messages("outlook")
        assert second == []

    @pytest.mark.asyncio
    async def test_seen_ids_seed_from_store(self, pipeline, monkeypatch):
        # Simulate an already-populated comms table
        pipeline.memory_manager.db = object()
        pipeline.memory_manager.connections_table = SimpleNamespace(
            to_arrow=lambda: SimpleNamespace(
                select=lambda col: SimpleNamespace(
                    to_pylist=lambda: [{"id": "already-stored-1"}]
                )
            )
        )

        captured = {"messages": [{"id": "already-stored-1", "subject": "dup"}]}
        _patch_fetch(pipeline, monkeypatch, captured)
        result = await pipeline._fetch_new_messages("outlook")
        assert result == []

    def test_seen_ids_bounded_in_state_file(self, pipeline):
        pipeline._seen_message_ids = {f"id-{i}" for i in range(25000)}
        pipeline.fetch_timestamps["last_fetch_outlook"] = datetime.now()
        pipeline._save_fetch_state()
        data = json.loads(pipeline._fetch_state_path.read_text())
        assert len(data["seen_message_ids"]) <= 20000
