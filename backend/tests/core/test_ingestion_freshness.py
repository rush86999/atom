"""Same-file freshness: re-ingesting a known file must UPDATE, never duplicate.

Traced gap (data-journey follow-up): the sync path already does this properly
(external_id + modified_at + content_hash + old-vector-row delete), but
``AutoDocumentIngestionService.process_file_bytes`` — the path every cloud-drive
connector's one-off ingest uses — minted a fresh ``file_<ts>`` row per call:
re-ingesting an updated file left BOTH versions live in the vector store.

Identity hierarchy (research-validated, per source type):
1. Source-native unique id  — Drive fileId / OneDrive driveItem id / Box file
   id / Zoho resource id / Dropbox path (each provider exposes an immutable
   per-file identifier; Microsoft Graph docs address items "by the driveItem
   unique identifier").
2. SHA-256 of extracted text — content-addressable fallback when no source id
   exists; identical content collapses to one row regardless of filename.
Titles are NEVER identity.

Freshness rule: probe the store by stable doc_id BEFORE writing — same
content_hash → skip (no-op); different/absent → aligned replace
(delete_documents_by_id + fresh add).
"""
import hashlib
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


class FakeDocStore:
    def __init__(self):
        self.rows = {}

    def get_document_by_id(self, table_name, doc_id):
        row = self.rows.get(doc_id)
        return dict(row, id=doc_id) if row else None

    def delete_documents_by_id(self, table_name, doc_id):
        return self.rows.pop(doc_id, None) is not None

    def add_document(self, table_name=None, text="", source="", metadata=None,
                     user_id="t", doc_id=None, **k):
        if doc_id is None:
            doc_id = f"auto-{len(self.rows)}"
        self.rows[doc_id] = {"text": text, "metadata": metadata or {}}
        return True


@pytest.fixture
def ingestor():
    from core.auto_document_ingestion import AutoDocumentIngestionService

    svc = AutoDocumentIngestionService()
    svc.memory_handler = FakeDocStore()
    svc.redactor = None
    return svc


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


@pytest.mark.asyncio
async def test_updated_content_replaces_same_external_id(ingestor):
    """Re-ingest v2 of a Drive file: v1 vector row GONE, exactly one row."""
    r1 = await ingestor.process_file_bytes(
        b"v1 bytes", file_name="q3.txt", source="google_drive",
        external_id="drv-123",
    )
    assert r1["status"] == "ingested"
    doc_id = r1["doc_id"]

    with patch.object(
        ingestor.parser, "parse_document",
        new=AsyncMock(return_value="Q3 revenue: $2M (updated figures)"),
    ):
        r2 = await ingestor.process_file_bytes(
            b"v2 bytes", file_name="q3.txt", source="google_drive",
            external_id="drv-123",
        )

    # Stable id: derived from source-native identity, identical across calls
    # even though content (and the timestamp) changed.
    assert r2["doc_id"] == doc_id
    assert list(ingestor.memory_handler.rows.keys()) == [doc_id], (
        "old version must be deleted — search must never see both"
    )
    assert "updated figures" in ingestor.memory_handler.rows[doc_id]["text"]
    meta = ingestor.memory_handler.rows[doc_id]["metadata"]
    assert meta["external_id"] == "drv-123"


@pytest.mark.asyncio
async def test_external_id_is_source_scoped(ingestor):
    """Two integrations reusing the same raw external-id string must NOT
    collide — one file's refresh must never delete the other's row."""
    with patch.object(
        ingestor.parser, "parse_document",
        new=AsyncMock(return_value="box payload"),
    ):
        r_box = await ingestor.process_file_bytes(
            b"a", file_name="x.pdf", source="box", external_id="shared-1",
        )
    with patch.object(
        ingestor.parser, "parse_document",
        new=AsyncMock(return_value="drive payload"),
    ):
        r_drive = await ingestor.process_file_bytes(
            b"b", file_name="x.pdf", source="google_drive", external_id="shared-1",
        )

    assert r_box["doc_id"] != r_drive["doc_id"], (
        "identity must be scoped by source integration"
    )
    assert len(ingestor.memory_handler.rows) == 2


@pytest.mark.asyncio
async def test_unchanged_content_is_noop(ingestor):
    """Identical re-ingest: skipped, store untouched."""
    with patch.object(
        ingestor.parser, "parse_document",
        new=AsyncMock(return_value="same body"),
    ):
        r1 = await ingestor.process_file_bytes(
            b"x", file_name="a.txt", source="box", external_id="box-9",
        )
        r2 = await ingestor.process_file_bytes(
            b"x", file_name="a.txt", source="box", external_id="box-9",
        )

    assert r1["status"] == "ingested"
    assert r2["status"] == "skipped"
    assert r2["reason"] == "unchanged"
    assert len(ingestor.memory_handler.rows) == 1


@pytest.mark.asyncio
async def test_content_hash_identity_without_external_id(ingestor):
    """No source id → SHA-256(text) is the identity: identical content under
    DIFFERENT filenames still collapses to one row (content addressing)."""
    with patch.object(
        ingestor.parser, "parse_document",
        new=AsyncMock(return_value="identical payload"),
    ):
        r1 = await ingestor.process_file_bytes(
            b"a", file_name="copy1.txt", source="upload",
        )
        r2 = await ingestor.process_file_bytes(
            b"b", file_name="totally-different-name.txt", source="upload",
        )

    assert r1["status"] == "ingested"
    assert r2["status"] == "skipped"
    assert len(ingestor.memory_handler.rows) == 1
    assert r1["doc_id"] == r2["doc_id"]
    assert r1["doc_id"].startswith("doc_")


@pytest.mark.asyncio
async def test_metadata_stamps_identity_and_freshness(ingestor):
    r = await ingestor.process_file_bytes(
        b"data", file_name="r.csv", source="onedrive", external_id="od-7",
    )
    meta = ingestor.memory_handler.rows[r["doc_id"]]["metadata"]
    assert meta["pg_document_id"] == r["doc_id"]
    assert meta["source_type"] == "file"
    assert meta["source_content_hash"] == _sha("data")
    assert meta["external_id"] == "od-7"


# ---------------------------------------------------------------------------
# Connectors must plumb their NATIVE ids through
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
@pytest.mark.parametrize(
    "module,cls,call,download_patch,meta_patch,native_id",
    [
        (
            "integrations.google_drive_service", "GoogleDriveService",
            ("tok", "gdrive-file-77"),
            "download_file_bytes", "get_file_metadata", "gdrive-file-77",
        ),
        (
            "integrations.onedrive_service", "OneDriveService",
            ("tok", "od-item-5"),
            "_download_file_bytes", "get_file_metadata", "od-item-5",
        ),
        (
            "integrations.box_service", "BoxService",
            ("tok", "box-file-3"),
            "_download_file_bytes", "get_file_metadata", "box-file-3",
        ),
    ],
)
async def test_connectors_pass_native_file_ids(
    module, cls, call, download_patch, meta_patch, native_id, monkeypatch
):
    captured = {}

    async def fake_process(self, content, file_name="", source="", **kwargs):
        captured.update(kwargs)
        captured["source"] = source
        return {"status": "ingested", "doc_id": "x", "chars_ingested": 1}

    monkeypatch.setattr(
        "core.auto_document_ingestion.AutoDocumentIngestionService.process_file_bytes",
        fake_process,
    )
    mod = __import__(module, fromlist=[cls])
    service = getattr(mod, cls)()
    # Identity resolution + download must not touch the network.
    if hasattr(service, "_resolve_token"):
        monkeypatch.setattr(service, "_resolve_token", lambda t: t or "resolved")
    monkeypatch.setattr(
        service, download_patch, AsyncMock(return_value=b"bytes")
    )
    monkeypatch.setattr(
        service, meta_patch,
        AsyncMock(return_value={"status": "success", "data": {"name": "n.pdf"}}),
    )

    res = await service.ingest_file_to_memory(*call)

    assert res.get("success") is True, res
    assert captured.get("external_id") == native_id, (
        f"{cls} must forward its native unique id as external_id "
        "(titles are not identity)"
    )


@pytest.mark.asyncio
async def test_dropbox_uses_path_as_identity(monkeypatch):
    from integrations.dropbox_service import DropboxService

    captured = {}

    async def fake_process(self, content, file_name="", source="", **kwargs):
        captured.update(kwargs)
        return {"status": "ingested", "doc_id": "x", "chars_ingested": 1}

    monkeypatch.setattr(
        "core.auto_document_ingestion.AutoDocumentIngestionService.process_file_bytes",
        fake_process,
    )
    svc = DropboxService()
    monkeypatch.setattr(svc, "download_file", AsyncMock(return_value=b"bytes"))

    res = await svc.ingest_file_to_memory("/reports/q3.pdf", access_token="t")

    assert res.get("success") is True
    assert captured.get("external_id") == "/reports/q3.pdf"


@pytest.mark.asyncio
async def test_zoho_uses_resource_id_as_identity(monkeypatch):
    from integrations.zoho_workdrive_service import ZohoWorkDriveService

    captured = {}

    async def fake_process(self, content, file_name="", source="", **kwargs):
        captured.update(kwargs)
        return {"status": "ingested", "doc_id": "x", "chars_ingested": 1}

    monkeypatch.setattr(
        "core.auto_document_ingestion.AutoDocumentIngestionService.process_file_bytes",
        fake_process,
    )
    svc = ZohoWorkDriveService()
    monkeypatch.setattr(svc, "get_access_token", AsyncMock(return_value="tok"))

    class _Resp:
        def raise_for_status(self):
            pass

        def json(self):
            return {"data": {"attributes": {"name": "z.pdf"}}}

        content = b""

    class _Client:
        async def get(self, *a, **k):
            return _Resp()

    svc.client = _Client()
    monkeypatch.setattr(svc, "download_file", AsyncMock(return_value=b"bytes"))

    res = await svc.ingest_file_to_memory("u1", "zoho-resource-11")

    assert res.get("success") is True
    assert captured.get("external_id") == "zoho-resource-11"


# ---------------------------------------------------------------------------
# Sync close-out must never block on the post-ingestion agent trigger
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_sync_closeout_not_blocked_by_agent_trigger(monkeypatch):
    """handle_data_event_trigger runs a FULL meta-agent turn. Awaiting it
    inline meant sync_integration blocked for minutes on LLM latency/retries
    (observed: 90s pytest-timeout via CreditsError backoff). It must be
    scheduled fire-and-forget instead."""
    import time

    from core.auto_document_ingestion import AutoDocumentIngestionService

    calls = {}

    async def slow_trigger(*args, **kwargs):
        calls["kwargs"] = kwargs
        import asyncio as _aio

        await _aio.sleep(30)  # simulate a long/retrying agent run

    monkeypatch.setattr(
        "core.atom_meta_agent.handle_data_event_trigger", slow_trigger
    )

    service = AutoDocumentIngestionService()
    settings = service.get_settings("google_drive")
    settings.enabled = True
    service.memory_handler = MagicMock()
    service.memory_handler.add_document.return_value = True

    async def fake_parse(content, ext, name):
        return "extracted body"

    monkeypatch.setattr(service.parser, "parse_document", fake_parse)
    monkeypatch.setattr(
        service, "_list_files",
        AsyncMock(return_value=[{"id": "file1", "name": "t.txt", "size": 10}]),
    )
    monkeypatch.setattr(
        service, "_download_file", AsyncMock(return_value=b"bytes")
    )

    started = time.monotonic()
    result = await service.sync_integration("google_drive", force=True)
    elapsed = time.monotonic() - started

    assert result["files_ingested"] == 1
    assert elapsed < 10, (
        f"sync close-out took {elapsed:.1f}s — it must not await the "
        "post-ingestion agent trigger"
    )
    # Let the scheduled task start before the loop closes.
    import asyncio as _aio

    for _ in range(3):
        await _aio.sleep(0)
    assert calls.get("kwargs", {}).get("integration_id") == "google_drive" or (
        calls.get("kwargs", {}).get("data", {}).get("integration_id")
        == "google_drive"
    ), "trigger must still be scheduled with the ingestion summary"
