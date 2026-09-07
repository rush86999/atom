"""Poll watermark rollback when the store is offline.

Scenario (Sep 5, 2026): the external memory drive was disconnected. The
Outlook poll fetches mail fine (Graph API works), but every LanceDB write
fails — and the fetch had ALREADY promoted the per-owner cursor past the
fetched messages. Mark-after-success left them unmarked, and the promoted
watermark meant they were never re-fetched: mail fetched during an outage
was stranded until a restart re-walked the window.

Fix: the poll loop snapshots the cursors before fetching and rolls them
back when _ingest_and_mark reports failures, so the window is re-walked
next poll (mark-after-success seen-ids + the store-level dedup guard make
the re-walk idempotent).
"""
import os
os.environ.setdefault("TESTING", "1")

import asyncio
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from integrations.atom_communication_ingestion_pipeline import (
    CommunicationIngestionPipeline,
)

_WS = "rollback-test-ws"


@pytest.fixture()
def pipe():
    # Mock memory manager: with the external store disconnected (dangling
    # atom_memory symlink) the real LanceDB init fails in tests too.
    p = CommunicationIngestionPipeline(MagicMock())
    p._seen_ids_loaded = True  # skip boot store reconciliation
    p._save_fetch_state = MagicMock()
    yield p


def _seed_cursor(pipe, ts):
    key = "last_fetch_outlook_owner1"
    pipe.fetch_timestamps[key] = ts
    return key, ts


@pytest.mark.asyncio
async def test_failed_ingest_rolls_back_promoted_cursor(pipe):
    key, original = _seed_cursor(pipe, datetime(2026, 9, 5, 12, 0, 0))
    promoted = original + timedelta(minutes=5)

    async def fetch_and_promote(app_type):
        # Mimic _fetch_outlook_messages: promotes the cursor at fetch time,
        # before anyone knows whether the store write will succeed.
        pipe.fetch_timestamps[key] = promoted
        return [{"id": "m-offline-1", "timestamp": promoted, "metadata": {}}]

    pipe._fetch_new_messages = AsyncMock(side_effect=fetch_and_promote)
    pipe.ingest_message = AsyncMock(return_value=False)  # store offline
    pipe.memory_manager._flush_metadata = AsyncMock()

    # First cycle sleeps normally, second raises CancelledError (a
    # BaseException, so the loop's `except Exception` can't swallow it).
    with patch(
        "integrations.atom_communication_ingestion_pipeline.asyncio.sleep",
        AsyncMock(side_effect=[None, asyncio.CancelledError()]),
    ):
        with pytest.raises(asyncio.CancelledError):
            await pipe._real_time_ingestion("outlook")

    assert pipe.fetch_timestamps[key] == original, (
        "failed ingest must roll the promoted watermark back to pre-fetch"
    )


@pytest.mark.asyncio
async def test_successful_ingest_keeps_promoted_cursor(pipe):
    key, original = _seed_cursor(pipe, datetime(2026, 9, 5, 12, 0, 0))
    promoted = original + timedelta(minutes=5)

    async def fetch_and_promote(app_type):
        pipe.fetch_timestamps[key] = promoted
        return [{"id": "m-online-1", "timestamp": promoted, "metadata": {}}]

    pipe._fetch_new_messages = AsyncMock(side_effect=fetch_and_promote)
    pipe.ingest_message = AsyncMock(return_value=True)
    pipe.memory_manager._flush_metadata = AsyncMock()

    with patch(
        "integrations.atom_communication_ingestion_pipeline.asyncio.sleep",
        AsyncMock(side_effect=[None, asyncio.CancelledError()]),
    ):
        with pytest.raises(asyncio.CancelledError):
            await pipe._real_time_ingestion("outlook")

    assert pipe.fetch_timestamps[key] == promoted


def test_rollback_only_touches_this_apps_cursors(pipe):
    other = "last_fetch_slack"
    backup = {
        "last_fetch_outlook_owner1": datetime(2026, 9, 5, 12, 0, 0),
        "last_fetch_outlook_resume_owner1": datetime(2026, 9, 5, 12, 5, 0),
        other: datetime(2026, 9, 5, 13, 0, 0),
    }
    # Current state: outlook cursors promoted, slack cursor untouched.
    pipe.fetch_timestamps.update({
        "last_fetch_outlook_owner1": datetime(2026, 9, 5, 12, 9, 0),
        "last_fetch_outlook_resume_owner1": datetime(2026, 9, 5, 12, 9, 0),
        other: backup[other],
    })

    restored = pipe._rollback_cursors_for_app("outlook", backup)

    assert restored == 2
    assert pipe.fetch_timestamps["last_fetch_outlook_owner1"] == backup["last_fetch_outlook_owner1"]
    assert pipe.fetch_timestamps["last_fetch_outlook_resume_owner1"] == backup["last_fetch_outlook_resume_owner1"]
    assert pipe.fetch_timestamps[other] == backup[other], "other apps' cursors untouched"
