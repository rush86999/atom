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

        async def fake_ingest(app_type, msg):
            ingested.append(msg["id"])
            return True

        monkeypatch.setattr(pipeline, "ingest_message", fake_ingest)

        first = await pipeline._fetch_new_messages("outlook")
        assert [m["id"] for m in first] == ["graph-msg-1"]
        # The id is marked seen only after a successful ingest.
        await pipeline._ingest_and_mark("outlook", first)

        # Second poll returns the same message (cold cursor / overlap):
        # the dedup guard must drop it instead of re-ingesting.
        second = await pipeline._fetch_new_messages("outlook")
        assert second == []

    @pytest.mark.asyncio
    async def test_failed_ingest_is_not_marked_seen(self, pipeline, monkeypatch):
        """A message whose ingest fails must stay eligible for re-ingestion
        (mark-after-success contract), not be silently lost."""
        message = {"id": "graph-msg-2", "app_type": "outlook", "subject": "x"}
        captured = {"messages": [message], "last_fetch": "unset"}
        _patch_fetch(pipeline, monkeypatch, captured)

        async def failing_ingest(app_type, msg):
            return False

        monkeypatch.setattr(pipeline, "ingest_message", failing_ingest)

        first = await pipeline._fetch_new_messages("outlook")
        await pipeline._ingest_and_mark("outlook", first)
        second = await pipeline._fetch_new_messages("outlook")
        assert [m["id"] for m in second] == ["graph-msg-2"], (
            "failed ingest must be retried on the next poll"
        )

    @pytest.mark.asyncio
    async def test_seen_ids_seed_from_store(self, pipeline, monkeypatch):
        # Simulate an already-populated comms table
        pipeline.memory_manager.db = object()
        pipeline.memory_manager.connections_table = SimpleNamespace(
            to_arrow=lambda: SimpleNamespace(
                select=lambda cols: SimpleNamespace(
                    to_pylist=lambda: [
                        {"id": "already-stored-1", "app_type": "outlook"}
                    ]
                )
            )
        )

        captured = {"messages": [{"id": "already-stored-1", "subject": "dup"}]}
        _patch_fetch(pipeline, monkeypatch, captured)
        result = await pipeline._fetch_new_messages("outlook")
        assert result == []

    def test_seen_ids_bounded_in_state_file(self, pipeline):
        pipeline._seen_message_ids = {
            "outlook": {f"id-{i}": "" for i in range(25000)},
            "slack": {"s-1": ""},
        }
        pipeline.fetch_timestamps["last_fetch_outlook"] = datetime.now()
        pipeline._save_fetch_state()
        data = json.loads(pipeline._fetch_state_path.read_text())
        assert len(data["seen_message_ids_by_owner"]["outlook"][""]) <= 20000
        assert data["seen_message_ids_by_owner"]["slack"][""] == ["s-1"]


class TestStoreReconciliationSelfHeal:
    """The seen-id set is a cache of the durable store, never an authority.

    Sep 2026 incident: the state file's seen ids outlived their rows (table
    rebuild + root-vs-backend store fork) — ~5.9k fetched emails were
    permanently blocked from re-ingestion and the mailbox looked 'capped at
    50'. The reconciliation must drop ghosts and re-walk only the affected
    app's window."""

    def _with_store(self, pipeline, rows):
        pipeline.memory_manager.db = object()
        pipeline.memory_manager.connections_table = SimpleNamespace(
            to_arrow=lambda: SimpleNamespace(
                select=lambda cols: SimpleNamespace(to_pylist=lambda: rows)
            )
        )

    def test_ghosts_dropped_and_store_ids_seeded(self, pipeline):
        self._with_store(
            pipeline,
            [
                {"id": "stored-1", "app_type": "outlook"},
                {"id": "stored-2", "app_type": "slack"},
            ],
        )
        pipeline._seen_message_ids = {
            "outlook": {"stored-1": "", "ghost-1": "", "ghost-2": ""},
            "slack": {"stored-2": "", "ghost-3": ""},
        }
        report = pipeline._reconcile_seen_ids_with_store()

        assert report == {"outlook": 2, "slack": 1}
        assert pipeline._seen_message_ids["outlook"] == {"stored-1": ""}
        assert pipeline._seen_message_ids["slack"] == {"stored-2": ""}

    def test_mass_loss_clears_only_affected_app_cursors(self, pipeline):
        self._with_store(pipeline, [{"id": "s-1", "app_type": "slack"}])
        pipeline._seen_message_ids = {
            "outlook": {f"ghost-{i}": "" for i in range(100)},
            "slack": {"s-1": ""},
        }
        pipeline.fetch_timestamps.update(
            {
                "last_fetch_outlook": datetime(2026, 6, 16),
                "last_fetch_outlook_owner-1": datetime(2026, 6, 16),
                "last_fetch_outlook_resume_owner-1": datetime(2026, 7, 22),
                "last_fetch_slack": datetime(2026, 8, 1),
            }
        )
        pipeline._reconcile_seen_ids_with_store()

        assert "last_fetch_outlook" not in pipeline.fetch_timestamps
        assert "last_fetch_outlook_owner-1" not in pipeline.fetch_timestamps
        assert "last_fetch_outlook_resume_owner-1" not in pipeline.fetch_timestamps
        assert pipeline.fetch_timestamps["last_fetch_slack"] == datetime(2026, 8, 1), (
            "unaffected app's cursors must be untouched"
        )

    def test_small_ghost_count_keeps_cursors(self, pipeline):
        self._with_store(pipeline, [{"id": "s-1", "app_type": "slack"}])
        pipeline._seen_message_ids = {"slack": {"s-1": "", "ghost-1": "", "ghost-2": ""}}
        pipeline.fetch_timestamps["last_fetch_slack"] = datetime(2026, 8, 1)
        pipeline._reconcile_seen_ids_with_store()
        assert pipeline.fetch_timestamps["last_fetch_slack"] == datetime(2026, 8, 1)

    def test_state_file_roundtrip_per_app(self, pipeline):
        self._with_store(pipeline, [{"id": "s-1", "app_type": "slack"}])
        pipeline._seen_message_ids = {"slack": {"s-1": ""}}
        pipeline.fetch_timestamps["last_fetch_slack"] = datetime(2026, 8, 1)
        pipeline._save_fetch_state()
        restarted = CommunicationIngestionPipeline(
            memory_manager=pipeline.memory_manager
        )
        assert restarted._seen_message_ids == {"slack": {"s-1": ""}}
        assert restarted.fetch_timestamps["last_fetch_slack"] == datetime(2026, 8, 1)

    def test_legacy_flat_state_file_is_ignored_not_crashed(self, pipeline):
        pipeline._fetch_state_path.write_text(
            json.dumps({"seen_message_ids": ["legacy-1", "legacy-2"]})
        )
        restarted = CommunicationIngestionPipeline(
            memory_manager=pipeline.memory_manager
        )
        assert restarted._seen_message_ids == {}

    def test_dead_owner_stamp_does_not_shadow_live_owner(self, pipeline):
        """Rows stamped with a dead user id (DB wipe left the Lance store
        full of them) are invisible to the live owner's scoped search — so
        they must not block re-ingestion under the live owner's stamp."""
        self._with_store(
            pipeline,
            [
                {
                    "id": "m-1",
                    "app_type": "outlook",
                    "metadata": json.dumps({"user_id": "dead-owner"}),
                },
                {
                    "id": "m-2",
                    "app_type": "outlook",
                    "metadata": json.dumps({"user_id": "live-owner"}),
                },
                {"id": "m-3", "app_type": "outlook"},  # unstamped: global
            ],
        )
        pipeline._reconcile_seen_ids_with_store()
        assert pipeline._seen_message_ids["outlook"] == {
            "m-1": "dead-owner",
            "m-2": "live-owner",
            "m-3": "",
        }

        def msg(mid, owner):
            return {"id": mid, "metadata": {"user_id": owner}} if owner else {"id": mid}

        live = [msg("m-1", "live-owner"), msg("m-2", "live-owner"), msg("m-3", "")]
        fresh = pipeline._dedup_messages("outlook", live)
        # m-1: dead-owner stamp must NOT shadow the live owner's re-ingest.
        # m-2: same-owner stamp blocks. m-3: unstamped stamp blocks for all.
        assert [m["id"] for m in fresh] == ["m-1"]

        dead = [msg("m-1", "dead-owner"), msg("m-2", "dead-owner"), msg("m-3", "")]
        fresh_dead = pipeline._dedup_messages("outlook", dead)
        # Same rule in both directions: m-1 (stored under live-owner) does
        # not block the dead owner either; only same-owner/unstamped blocks.
        assert [m["id"] for m in fresh_dead] == ["m-2"]


class TestOwnerStampRepairPlan:
    """After a world wipe/re-seed the memory store keeps stamps of users
    that no longer exist. Single-tenant, multi-user app: attribution to the
    re-created account goes by mailbox-address evidence (the owner's email
    appears in every one of their rows)."""

    def test_email_evidence_attributes_recreated_user(self, pipeline):
        # dead owner's rows were all in rish@brennan.ca's mailbox; that
        # address now belongs to the re-created account u-2.
        mapping = pipeline._plan_owner_restamps(
            {
                "dead-1": {"rish@brennan.ca": 50, "vipul@brennan.ca": 3},
            },
            {"u-1": "other@brennan.ca", "u-2": "rish@brennan.ca"},
        )
        assert mapping == {"dead-1": "u-2"}

    def test_multiple_users_same_mailbox_not_attributed(self, pipeline):
        # Two live users claim the same address — cannot pick one.
        mapping = pipeline._plan_owner_restamps(
            {"dead-1": {"rish@brennan.ca": 50}},
            {"u-1": "rish@brennan.ca", "u-2": "rish@brennan.ca"},
        )
        assert mapping == {}

    def test_new_email_address_not_attributed(self, pipeline):
        # Re-created with a different email: evidence doesn't match any live
        # user — no guess; the user's own re-walk re-ingests instead.
        mapping = pipeline._plan_owner_restamps(
            {"dead-1": {"old@brennan.ca": 50}},
            {"u-1": "new@brennan.ca"},
        )
        assert mapping == {}

    def test_no_evidence_single_live_user_fallback(self, pipeline):
        # No extractable addresses at all, exactly one live user: attribute.
        mapping = pipeline._plan_owner_restamps({"dead-1": {}}, {"u-1": "a@x.ca"})
        # The planner logs and omits evidence-less owners; the caller may
        # apply the single-live-user fallback — planner itself does not.
        assert mapping == {}

    def test_email_match_is_case_insensitive(self, pipeline):
        mapping = pipeline._plan_owner_restamps(
            {"dead-1": {"Rish@Brennan.ca": 20}},
            {"u-1": "rish@brennan.ca"},
        )
        assert mapping == {"dead-1": "u-1"}


class TestBypassPathDedup:
    """Ingestion paths that bypass the poll loop (webhook handler, telegram
    polling worker) must honor the same mark-after-success dedup contract —
    providers redeliver webhooks, and a restart re-poll re-delivers Telegram
    updates, which duplicated rows with no guard."""

    def _webhook_message(self):
        return {
            "id": "slack-ev-1",
            "app_type": "slack",
            "sender": "u1",
            "content": "hello from slack",
        }

    @pytest.mark.asyncio
    async def test_webhook_redelivery_ingested_once(self, pipeline, monkeypatch):
        calls = []

        async def fake_ingest(app_type, msg):
            calls.append(msg["id"])
            return True

        monkeypatch.setattr(pipeline, "ingest_message", fake_ingest)
        monkeypatch.setattr(pipeline, "is_webhook_enabled", lambda app: True)

        await pipeline._handle_webhook_message(self._webhook_message())
        await pipeline._handle_webhook_message(self._webhook_message())

        assert calls == ["slack-ev-1"], "redelivered webhook must be dropped"

    @pytest.mark.asyncio
    async def test_webhook_failure_is_retried(self, pipeline, monkeypatch):
        calls = []

        async def failing_ingest(app_type, msg):
            calls.append(msg["id"])
            return False

        monkeypatch.setattr(pipeline, "ingest_message", failing_ingest)
        monkeypatch.setattr(pipeline, "is_webhook_enabled", lambda app: True)

        await pipeline._handle_webhook_message(self._webhook_message())
        await pipeline._handle_webhook_message(self._webhook_message())

        assert calls == ["slack-ev-1", "slack-ev-1"], (
            "failed webhook ingest must not be marked seen"
        )

    @pytest.mark.asyncio
    async def test_telegram_worker_dedup_and_stable_id(self, pipeline, monkeypatch):
        """The telegram worker must key messages on a stable id and honor
        mark-after-success (restart re-poll re-delivers pending updates)."""
        ingested = []
        monkeypatch.setattr(
            "integrations.atom_communication_ingestion_pipeline."
            "get_ingestion_pipeline",
            lambda ws=None: pipeline,
        )
        # The worker passes the pipeline directly, not through the fixture's
        # memory_manager attribute naming — reuse the pipeline fixture.
        pipeline.memory_manager.db = None

        async def fake_ingest(app_type, msg):
            ingested.append(msg["id"])
            return True

        monkeypatch.setattr(pipeline, "ingest_message", fake_ingest)

        from workers.telegram_polling_worker import TelegramPollingWorker

        worker = TelegramPollingWorker()
        raw = {"message_id": 42, "chat": {"id": 7}, "text": "hi", "from": {"id": 1}}

        await worker._ingest_to_comm_store(raw)
        await worker._ingest_to_comm_store(raw)  # restart re-delivery

        assert ingested == ["tg_7_42"], (
            "stable id required for cross-restart dedup; redelivery dropped"
        )
