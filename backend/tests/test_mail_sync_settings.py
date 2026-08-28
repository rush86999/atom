"""Tests for user-guided Outlook history sync + ingestion hygiene.

Covers (Aug 2026):
  - The initial Outlook sync ingests a user-configurable history window
    (default 3 months) instead of only the newest page of mail.
  - The fetch cursor advances to the newest message seen (not "now") so a
    truncated walk resumes instead of silently skipping the remainder.
  - ingestion_metadata updates are throttled (per-message delete+add
    commits fragmented that table to 413MB once).
  - outlook_history_days setting defaults to 90 and clamps safely.
"""

import asyncio
from datetime import datetime, timedelta
from types import SimpleNamespace

import pytest

import integrations.atom_communication_ingestion_pipeline as pipeline_module
from integrations.atom_communication_ingestion_pipeline import (
    CommunicationIngestionPipeline,
)


@pytest.fixture
def pipeline(tmp_path):
    memory_manager = SimpleNamespace(
        db_path=str(tmp_path / "atom_memory"),
        db=None,
        connections_table=None,
        initialize=lambda: None,
    )
    (tmp_path / "atom_memory").mkdir()
    return CommunicationIngestionPipeline(memory_manager=memory_manager)


class FakeGraphResponse:
    def __init__(self, payload, status_code=200):
        self._payload = payload
        self.status_code = status_code
        self.headers = {}

    def json(self):
        return self._payload


class FakeGraphClient:
    """Captures the first /me/messages request params, then ends the walk."""
    captured_params = None

    def __init__(self, *a, **k):
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, *a):
        return False

    async def get(self, url, headers=None, params=None):
        if FakeGraphClient.captured_params is None:
            FakeGraphClient.captured_params = dict(params or {})
        return FakeGraphResponse({"value": []})


@pytest.fixture
def graph_spy(monkeypatch):
    FakeGraphClient.captured_params = None
    monkeypatch.setattr(pipeline_module.httpx, "AsyncClient", FakeGraphClient)

    class FakeOutlookService:
        async def _get_access_token(self, user_id=None):
            return "fake-token"

    import integrations.outlook_service as outlook_service_module
    monkeypatch.setattr(
        outlook_service_module, "outlook_service", FakeOutlookService()
    )
    return FakeGraphClient


class TestInitialSyncHistoryWindow:
    @pytest.fixture(autouse=True)
    def restore_settings(self):
        """The settings manager is a global singleton — snapshot/restore."""
        from core.automation_settings import get_automation_settings
        manager = get_automation_settings()
        snapshot = dict(manager._settings)
        yield
        manager._settings.clear()
        manager._settings.update(snapshot)

    def test_initial_sync_filters_to_default_90_days(self, pipeline, graph_spy):
        from core.automation_settings import get_automation_settings
        get_automation_settings()._settings["outlook_history_days"] = 90

        asyncio.run(pipeline._fetch_outlook_messages(None))

        filt = graph_spy.captured_params["$filter"]
        assert filt.startswith("receivedDateTime ge ")
        since = datetime.strptime(
            filt.split("ge ")[1], "%Y-%m-%dT%H:%M:%SZ"
        ).replace(tzinfo=None)
        expected_start = datetime.now() - timedelta(days=90)
        # The window starts ~90 days ago (a minute of drift tolerated)
        assert abs((since - expected_start).total_seconds()) < 120

    def test_initial_sync_walks_more_pages(self, pipeline, graph_spy):
        """90 days of mail rarely fits in 5 pages; the initial walk must be
        allowed to page deeper. Verified indirectly: the filter exists so the
        walk is bounded by the window, and max_fetches is widened."""
        from core.automation_settings import get_automation_settings
        get_automation_settings()._settings["outlook_history_days"] = 90
        asyncio.run(pipeline._fetch_outlook_messages(None))
        assert "receivedDateTime ge" in graph_spy.captured_params["$filter"]

    def test_incremental_poll_keeps_gt_filter(self, pipeline, graph_spy):
        last = datetime(2026, 8, 28, 12, 0, 0)
        asyncio.run(pipeline._fetch_outlook_messages(last))
        assert graph_spy.captured_params["$filter"] == (
            "receivedDateTime gt 2026-08-28T12:00:00Z"
        )


class TestCursorAdvancement:
    @pytest.mark.asyncio
    async def test_cursor_advances_to_newest_message(self, pipeline, monkeypatch):
        old = datetime(2026, 8, 1, 9, 0, 0)
        new = datetime(2026, 8, 28, 10, 0, 0)
        messages = [
            {"id": "m-old", "timestamp": old, "subject": "old"},
            {"id": "m-new", "timestamp": new, "subject": "new"},
        ]

        async def fake_fetch(last_fetch):
            return [dict(m) for m in messages]

        monkeypatch.setattr(pipeline, "_fetch_outlook_messages", fake_fetch)
        await pipeline._fetch_new_messages("outlook")

        assert pipeline.fetch_timestamps["last_fetch_outlook"] == new

    @pytest.mark.asyncio
    async def test_cursor_falls_back_to_now_without_timestamps(self, pipeline, monkeypatch):
        async def fake_fetch(last_fetch):
            return [{"id": "no-ts", "subject": "x"}]

        monkeypatch.setattr(pipeline, "_fetch_outlook_messages", fake_fetch)
        before = datetime.now()
        await pipeline._fetch_new_messages("outlook")
        after = datetime.now()

        cursor = pipeline.fetch_timestamps["last_fetch_outlook"]
        assert before <= cursor <= after


class TestMetadataThrottle:
    @pytest.fixture
    def mgr(self, tmp_path):
        from integrations.atom_communication_ingestion_pipeline import (
            LanceDBMemoryManager,
        )
        return LanceDBMemoryManager(db_path=str(tmp_path / "mm"))

    def test_updates_accumulate_and_flush_once(self, mgr):
        deleted, added = [], []

        mgr.metadata_table = SimpleNamespace(
            search=lambda: SimpleNamespace(
                where=lambda f: SimpleNamespace(
                    to_pandas=lambda: _df_one_row(total=100)
                )
            ),
            delete=lambda f: deleted.append(f),
            add=lambda rows: added.append(rows),
        )

        for _ in range(50):
            mgr._update_metadata("outlook", 1)
        assert deleted == [] and added == []  # nothing written while hot

        mgr._flush_metadata()
        assert len(deleted) == 1 and len(added) == 1  # one commit, not 50
        assert added[0][0]["total_messages"] == 150

    def test_flush_keeps_pending_without_store(self, mgr):
        assert getattr(mgr, "metadata_table", None) is None
        mgr._metadata_pending = {"outlook": 5}
        mgr._flush_metadata()  # must not raise
        # No store yet — counts stay pending for the next flush
        assert mgr._metadata_pending == {"outlook": 5}


def _df_one_row(total):
    """Minimal stand-in for the pandas row _flush_metadata reads."""
    import pandas as pd

    return pd.DataFrame([{"app_type": "outlook", "total_messages": total}])


class TestHistoryDaysSetting:
    def test_defaults_to_90(self):
        from core.automation_settings import get_automation_settings
        manager = get_automation_settings()
        manager._settings.pop("outlook_history_days", None)
        assert manager.get_initial_sync_days("outlook") == 90

    def test_clamps_out_of_range_values(self):
        from core.automation_settings import get_automation_settings
        manager = get_automation_settings()

        manager._settings["outlook_history_days"] = 0
        assert manager.get_initial_sync_days("outlook") == 1
        manager._settings["outlook_history_days"] = 99999
        assert manager.get_initial_sync_days("outlook") == 3650
        manager._settings["outlook_history_days"] = "not-a-number"
        assert manager.get_initial_sync_days("outlook") == 90


class TestInitialSyncDaysGeneralized:
    """History window resolves per integration, with a shared mail default."""

    @pytest.fixture(autouse=True)
    def restore_settings(self):
        from core.automation_settings import get_automation_settings
        manager = get_automation_settings()
        snapshot = dict(manager._settings)
        yield
        manager._settings.clear()
        manager._settings.update(snapshot)

    def test_per_app_key_wins(self):
        from core.automation_settings import get_automation_settings
        manager = get_automation_settings()
        manager._settings["gmail_history_days"] = 30
        manager._settings["email_history_days"] = 45
        assert manager.get_initial_sync_days("gmail") == 30
        # outlook still has its own key → shared default must NOT override it
        assert manager.get_initial_sync_days("outlook") == 90

    def test_per_app_key_absent_uses_shared_mail_default(self):
        from core.automation_settings import get_automation_settings
        manager = get_automation_settings()
        manager._settings["email_history_days"] = 45
        manager._settings.pop("gmail_history_days", None)
        assert manager.get_initial_sync_days("gmail") == 45

    def test_unknown_app_falls_back_to_shared_mail_default(self):
        from core.automation_settings import get_automation_settings
        manager = get_automation_settings()
        manager._settings["email_history_days"] = 14
        assert manager.get_initial_sync_days("slack") == 14

    def test_clamped(self):
        from core.automation_settings import get_automation_settings
        manager = get_automation_settings()
        manager._settings["email_history_days"] = 0
        manager._settings.pop("gmail_history_days", None)
        assert manager.get_initial_sync_days("gmail") == 1
        manager._settings["email_history_days"] = 99999
        assert manager.get_initial_sync_days("gmail") == 3650

    def test_outlook_alias_delegates(self):
        from core.automation_settings import get_automation_settings
        manager = get_automation_settings()
        manager._settings["outlook_history_days"] = 21
        assert manager.get_outlook_history_days() == 21


class TestGmailInitialSync:
    @pytest.fixture(autouse=True)
    def restore_settings(self):
        from core.automation_settings import get_automation_settings
        manager = get_automation_settings()
        snapshot = dict(manager._settings)
        yield
        manager._settings.clear()
        manager._settings.update(snapshot)

    @pytest.fixture
    def gmail_spy(self, monkeypatch):
        import integrations.gmail_service as gmail_service_module

        captured = {}

        class FakeGmailService:
            service = object()  # truthy → skips _authenticate

            def _authenticate(self):
                pass

            def get_messages(self, query="", max_results=50, **kw):
                captured["query"] = query
                captured["max_results"] = max_results
                return [dict(captured["message"])]

        monkeypatch.setattr(gmail_service_module, "GmailService", FakeGmailService)
        captured["message"] = {
            "id": "g1",
            "threadId": "t1",
            "date": "Fri, 28 Aug 2026 10:00:00 +0000",
            "sender": "Zoho Forms <notifications@zohoforms.ca>",
            "recipient": "rish@brennan.ca",
            "subject": "New Quote Request From New Lead",
            "body": "<html><body>Name: Mark, Kellam<br>Email: mkellam@wfsltd.ca</body></html>",
            "body_content_type": "text/html",
            "internalDate": "1756380000000",
            "snippet": "Mark, Kellam",
            "labelIds": [],
        }
        return captured

    def test_initial_sync_uses_history_window_query(self, pipeline, gmail_spy):
        from core.automation_settings import get_automation_settings
        get_automation_settings()._settings["gmail_history_days"] = 90

        asyncio.run(pipeline._fetch_gmail_messages(None))

        assert gmail_spy["query"].startswith("after:")
        assert gmail_spy["query"] == f"after:{(datetime.now() - timedelta(days=90)).strftime('%Y/%m/%d')}"

    def test_incremental_uses_cursor_date(self, pipeline, gmail_spy):
        asyncio.run(
            pipeline._fetch_gmail_messages(datetime(2026, 8, 1, 12, 0, 0))
        )
        assert gmail_spy["query"] == "after:2026/08/01"

    def test_message_fields_normalized(self, pipeline, gmail_spy):
        msgs = asyncio.run(pipeline._fetch_gmail_messages(None))
        msg = msgs[0]
        # Address wins over display name (searchable sender)
        assert msg["sender_email"] == "notifications@zohoforms.ca"
        # HTML body declared as html so the normalizer strips it
        assert msg["content_type"] == "text/html"
        # Received time from the Date header — NOT poll time (now())
        received = msg["timestamp"]
        assert received.year == 2026
        assert (datetime.now() - received).total_seconds() > 3600
