"""
Coverage wave 9b — core/office_sync_service.py (67% -> 90%+ target).

Bugs fixed (TDD):
1. Coroutine leak: broadcast_file_update creates an un-awaited coroutine
   when called WITHOUT a running event loop — asyncio.create_task raises
   RuntimeError AFTER constructing the coroutine, so it is abandoned and
   emits "coroutine ... was never awaited" at GC. Both the memory-ingest
   and the WS-broadcast call sites leak. Fixed by closing the coroutine
   on RuntimeError.
"""
import asyncio
import gc
import warnings
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


@pytest.fixture
def office_dir(tmp_path, monkeypatch):
    d = tmp_path / "office"
    d.mkdir()
    monkeypatch.setenv("ATOM_OFFICE_DIR", str(d))
    return d


def make_service(db=None):
    from core.office_sync_service import OfficeSyncService

    return OfficeSyncService(db or MagicMock())


class TestSyncCanvasToFile:
    def test_path_outside_dir_rejected(self, office_dir):
        svc = make_service()
        res = svc.sync_canvas_to_file("c1", str(office_dir.parent / "evil.xlsx"), "u1", "cell", {})
        assert res["success"] is False
        assert "outside" in res["error"].lower()

    def test_missing_file(self, office_dir):
        svc = make_service()
        res = svc.sync_canvas_to_file("c1", str(office_dir / "nope.xlsx"), "u1", "cell", {})
        assert res["success"] is False
        assert "not found" in res["error"].lower()

    def test_xlsx_cell_success(self, office_dir):
        (office_dir / "b.xlsx").write_bytes(b"x")
        svc = make_service()
        svc.broadcast_file_update = MagicMock()
        with patch.object(svc.office.excel, "write_cell", return_value={"success": True}):
            res = svc.sync_canvas_to_file(
                "c1", str(office_dir / "b.xlsx"), "u1", "cell",
                {"cell_path": "/Sheet1/A1", "value": 42, "is_formula": False},
            )
        assert res["success"] is True
        svc.broadcast_file_update.assert_called_once()

    def test_xlsx_cell_missing_cell_path(self, office_dir):
        (office_dir / "b.xlsx").write_bytes(b"x")
        svc = make_service()
        res = svc.sync_canvas_to_file("c1", str(office_dir / "b.xlsx"), "u1", "cell", {})
        assert res["success"] is False
        assert "cell_path" in res["error"]

    def test_xlsx_cell_write_failure_propagated(self, office_dir):
        (office_dir / "b.xlsx").write_bytes(b"x")
        svc = make_service()
        with patch.object(svc.office.excel, "write_cell", return_value={"success": False, "error": "boom"}):
            res = svc.sync_canvas_to_file(
                "c1", str(office_dir / "b.xlsx"), "u1", "cell",
                {"cell_path": "/Sheet1/A1", "value": 1},
            )
        assert res["success"] is False
        assert res["error"] == "boom"

    def test_docx_document_overwrite(self, office_dir):
        import docx

        target = office_dir / "d.docx"
        target.write_bytes(b"old")
        svc = make_service()
        svc.broadcast_file_update = MagicMock()
        res = svc.sync_canvas_to_file(
            "c1", str(target), "u1", "document", {"content": "line one\nline two"}
        )
        assert res["success"] is True
        saved = docx.Document(str(target))
        assert [p.text for p in saved.paragraphs] == ["line one", "line two"]
        svc.broadcast_file_update.assert_called_once()

    def test_unsupported_edit_type(self, office_dir):
        (office_dir / "b.xlsx").write_bytes(b"x")
        svc = make_service()
        res = svc.sync_canvas_to_file("c1", str(office_dir / "b.xlsx"), "u1", "typo", {})
        assert res["success"] is False
        assert "unsupported" in res["error"].lower()

    def test_exception_generic_no_str_leak(self, office_dir):
        (office_dir / "b.xlsx").write_bytes(b"x")
        svc = make_service()
        with patch.object(
            svc.office.excel, "write_cell",
            side_effect=RuntimeError("secret-internal-detail-xyz"),
        ):
            res = svc.sync_canvas_to_file(
                "c1", str(office_dir / "b.xlsx"), "u1", "cell",
                {"cell_path": "/Sheet1/A1", "value": 1},
            )
        assert res["success"] is False
        assert res["error"] == "Failed to sync canvas to file"
        assert "secret-internal-detail-xyz" not in res["error"]


class TestBroadcastFileUpdate:
    def test_invalid_path_silent(self, office_dir):
        svc = make_service()
        svc.broadcast_file_update("c1", str(office_dir.parent / "evil.docx"), "u1")

    def test_render_failure_degrades_to_html_none(self, office_dir):
        # A failed HTML render (e.g. mammoth missing for docx) must NOT abort
        # the broadcast — the structured snapshot is independent of the render,
        # and aborting left the canvas with no audit row (so /api/canvas/{id}
        # 404'd) and no WS update. The audit is still written, with html=None.
        f = office_dir / "d.docx"
        f.write_bytes(b"x")
        svc = make_service()
        with patch(
            "core.office_service.DocumentRenderer.render_to_html",
            return_value={"success": False, "error": "no"},
        ):
            svc.broadcast_file_update("c1", str(f), "u1")
        svc.db.add.assert_called_once()
        audit = svc.db.add.call_args[0][0]
        assert audit.details_json["html"] is None

    def test_success_audits_and_broadcasts(self, office_dir):
        f = office_dir / "d.docx"
        f.write_bytes(b"x")
        db = MagicMock()
        svc = make_service(db)

        async def run_broadcast():
            svc.broadcast_file_update("c1", str(f), "u1")
            await asyncio.sleep(0)

        with patch(
            "core.office_service.DocumentRenderer.render_to_html",
            return_value={"success": True, "html": "<p>hi</p>"},
        ), patch.object(
            svc, "_ingest_document_to_memory", new=AsyncMock()
        ) as ingest, patch(
            "core.office_sync_service.ws_manager.broadcast", new=AsyncMock()
        ) as broadcast:
            asyncio.run(run_broadcast())

        added = [a.args[0] for a in db.add.call_args_list]
        assert added
        assert added[0].canvas_id == "c1"
        assert added[0].user_id == "u1"
        assert added[0].details_json["html"] == "<p>hi</p>"
        db.commit.assert_called_once()
        ingest.assert_awaited_once()
        # Office co-editing now delivers on BOTH canvas:{id} and user:{uid}
        # channels (the user-channel leg fixed the dead-lettered delivery).
        assert broadcast.await_count == 2
        channels = {c.args[0] for c in broadcast.call_args_list}
        assert channels == {"canvas:c1", "user:u1"}

    def test_no_running_loop_uses_sync_fallback(self, office_dir):
        """RED (bug 1): sync caller must fall back to the sync ingestion AND
        not leak the un-awaited async-ingest coroutine."""
        f = office_dir / "d.docx"
        f.write_bytes(b"x")

        ingested_sync = []

        async def fake_async_ingest(file_path, user_id):
            ingested_sync.append(("async", file_path, user_id))
            return True

        svc = make_service()
        svc._ingest_document_to_memory = fake_async_ingest
        svc._ingest_document_to_memory_sync = lambda *a: ingested_sync.append(("sync", *a)) or True

        with patch(
            "core.office_service.DocumentRenderer.render_to_html",
            return_value={"success": True, "html": "<p>hi</p>"},
        ), patch(
            "core.office_sync_service.ws_manager.broadcast",
            new=AsyncMock(),
        ):
            # Deliberately NOT inside asyncio.run — sync caller path.
            with warnings.catch_warnings(record=True) as caught:
                warnings.simplefilter("always")
                svc.broadcast_file_update("c1", str(f), "u1")
                gc.collect()
            gc.collect()

        assert ingested_sync == [("sync", str(f), "u1")], (
            "sync fallback did not run"
        )
        leak_warnings = [
            w for w in caught
            if issubclass(w.category, RuntimeWarning)
            and "was never awaited" in str(w.message)
        ]
        assert not leak_warnings, f"leaked coroutine: {[str(w.message) for w in leak_warnings]}"

    def test_no_running_loop_broadcast_coroutine_closed(self, office_dir):
        """RED (bug 2): the ws broadcast coroutine must not leak either."""
        f = office_dir / "d.docx"
        f.write_bytes(b"x")

        svc = make_service()

        async def fake_broadcast(channel, message):
            return None

        with patch(
            "core.office_service.DocumentRenderer.render_to_html",
            return_value={"success": True, "html": "<p>hi</p>"},
        ), patch.object(svc, "_ingest_document_to_memory_sync", return_value=True), patch(
            "core.office_sync_service.ws_manager.broadcast", new=fake_broadcast
        ):
            with warnings.catch_warnings(record=True) as caught:
                warnings.simplefilter("always")
                svc.broadcast_file_update("c1", str(f), "u1")
                gc.collect()
            gc.collect()

        leak_warnings = [
            w for w in caught
            if issubclass(w.category, RuntimeWarning)
            and "was never awaited" in str(w.message)
        ]
        assert not leak_warnings, f"leaked coroutine: {[str(w.message) for w in leak_warnings]}"


    def test_broadcast_inner_exception_logged(self, office_dir):
        """Cover the broadcast guard: an inner failure is logged, not raised."""
        f = office_dir / "d.docx"
        f.write_bytes(b"x")
        db = MagicMock()
        db.add.side_effect = RuntimeError("audit-write-boom")
        svc = make_service(db)
        with patch(
            "core.office_service.DocumentRenderer.render_to_html",
            return_value={"success": True, "html": "<p>hi</p>"},
        ), patch.object(svc, "_ingest_document_to_memory_sync", return_value=True), patch(
            "core.office_sync_service.ws_manager.broadcast", new=AsyncMock()
        ):
            svc.broadcast_file_update("c1", str(f), "u1")  # must not raise


class TestIngestToMemory:
    @pytest.mark.asyncio
    async def test_ingested_status(self, office_dir):
        f = office_dir / "d.docx"
        f.write_bytes(b"content bytes")
        svc = make_service()
        with patch(
            "core.auto_document_ingestion.AutoDocumentIngestionService",
        ) as ing_cls:
            ing_cls.return_value.process_file_bytes = AsyncMock(
                return_value={"status": "ingested", "chars_ingested": 13}
            )
            ok = await svc._ingest_document_to_memory(str(f), "u1")
        assert ok is True

    @pytest.mark.asyncio
    async def test_skipped_status(self, office_dir):
        f = office_dir / "d.docx"
        f.write_bytes(b"content bytes")
        svc = make_service()
        with patch(
            "core.auto_document_ingestion.AutoDocumentIngestionService",
        ) as ing_cls:
            ing_cls.return_value.process_file_bytes = AsyncMock(
                return_value={"status": "skipped"}
            )
            ok = await svc._ingest_document_to_memory(str(f), "u1")
        assert ok is True

    @pytest.mark.asyncio
    async def test_failed_status_returns_false(self, office_dir):
        f = office_dir / "d.docx"
        f.write_bytes(b"content bytes")
        svc = make_service()
        with patch(
            "core.auto_document_ingestion.AutoDocumentIngestionService",
        ) as ing_cls:
            ing_cls.return_value.process_file_bytes = AsyncMock(
                return_value={"status": "failed"}
            )
            ok = await svc._ingest_document_to_memory(str(f), "u1")
        assert ok is False

    @pytest.mark.asyncio
    async def test_empty_file_returns_false(self, office_dir):
        f = office_dir / "d.docx"
        f.write_bytes(b"")
        svc = make_service()
        ok = await svc._ingest_document_to_memory(str(f), "u1")
        assert ok is False

    @pytest.mark.asyncio
    async def test_exception_non_fatal(self, office_dir):
        f = office_dir / "d.docx"
        f.write_bytes(b"content bytes")
        svc = make_service()
        with patch(
            "core.auto_document_ingestion.AutoDocumentIngestionService",
        ) as ing_cls:
            ing_cls.return_value.process_file_bytes = AsyncMock(
                side_effect=RuntimeError("ingest exploded")
            )
            ok = await svc._ingest_document_to_memory(str(f), "u1")
        assert ok is False

    def test_sync_fallback_runs_ingestion(self, office_dir):
        f = office_dir / "d.docx"
        f.write_bytes(b"content bytes")
        svc = make_service()
        with patch(
            "core.auto_document_ingestion.AutoDocumentIngestionService",
        ) as ing_cls:
            ing_cls.return_value.process_file_bytes = AsyncMock(
                return_value={"status": "ingested"}
            )
            ok = svc._ingest_document_to_memory_sync(str(f), "u1")
        assert ok is True

    def test_sync_fallback_empty_file(self, office_dir):
        f = office_dir / "d.docx"
        f.write_bytes(b"")
        svc = make_service()
        assert svc._ingest_document_to_memory_sync(str(f), "u1") is False

    def test_sync_fallback_exception_non_fatal(self, office_dir):
        f = office_dir / "d.docx"
        f.write_bytes(b"content bytes")
        svc = make_service()
        with patch(
            "core.auto_document_ingestion.AutoDocumentIngestionService",
        ) as ing_cls:
            ing_cls.return_value.process_file_bytes = AsyncMock(
                side_effect=RuntimeError("sync ingest exploded")
            )
            assert svc._ingest_document_to_memory_sync(str(f), "u1") is False


class TestReadFileBytes:
    def test_missing_file(self, office_dir):
        from core.office_sync_service import OfficeSyncService

        assert OfficeSyncService._read_file_bytes(str(office_dir / "nope.docx")) is None

    def test_empty_file(self, office_dir):
        from core.office_sync_service import OfficeSyncService

        f = office_dir / "e.docx"
        f.write_bytes(b"")
        assert OfficeSyncService._read_file_bytes(str(f)) is None

    def test_present_file(self, office_dir):
        from core.office_sync_service import OfficeSyncService

        f = office_dir / "p.docx"
        f.write_bytes(b"hello")
        assert OfficeSyncService._read_file_bytes(str(f)) == b"hello"

    def test_unreadable_path_returns_none(self, office_dir):
        """Cover the read guard: IO errors yield None (never raise)."""
        from core.office_sync_service import OfficeSyncService

        d = office_dir / "a-directory"
        d.mkdir()
        assert OfficeSyncService._read_file_bytes(str(d)) is None
