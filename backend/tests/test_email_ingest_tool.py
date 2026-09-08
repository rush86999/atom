"""On-demand email ingestion: agent tool + pipeline single-message path.

- tools/email_ingest_tool.email_ingest_message: provider mapping, the
  email_attachment autonomy gate, and truthful status mapping (ingested /
  already_ingested / error).
- CommunicationIngestionPipeline.ingest_email_on_demand: seen-id
  short-circuit, mark-after-success, store-failure retry path, and the
  outlook/gmail normalizers (shared with the poller) landing identical
  shapes.
"""

import os

os.environ.setdefault("TESTING", "1")

import contextlib
import threading
from datetime import datetime
from unittest.mock import AsyncMock, patch

import pytest


# ---------------------------------------------------------------------------
# Tool-level tests (tools/email_ingest_tool.py)
# ---------------------------------------------------------------------------


@pytest.fixture
def auto_gate():
    """The gate consults gate_for_topic resolved in tools.email_attachment_tool
    (_gate lives there); a missing hire proposes, so pin it to execute."""
    import tools.email_attachment_tool as attachment_tool_mod

    with patch.object(attachment_tool_mod, "gate_for_topic") as fake_gate:
        fake_gate.return_value = {
            "topic": "email_attachment",
            "mode": "auto_if_mature",
            "outcome": "execute",
            "reason": "test gate",
        }
        yield fake_gate


@pytest.fixture
def propose_gate():
    import tools.email_attachment_tool as attachment_tool_mod

    with patch.object(attachment_tool_mod, "gate_for_topic") as fake_gate:
        fake_gate.return_value = {
            "topic": "email_attachment",
            "mode": "human_always",
            "outcome": "propose",
            "reason": "owner pinned this topic",
        }
        yield fake_gate


@pytest.fixture
def db_session_ctx(tmp_path):
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    from core.models import Base

    eng = create_engine(f"sqlite:///{tmp_path}/ingest_tool.db")
    Base.metadata.create_all(bind=eng)
    Session = sessionmaker(bind=eng, expire_on_commit=False)

    @contextlib.contextmanager
    def _ctx():
        with Session() as s:
            yield s

    with patch("core.database.get_db_session", _ctx):
        yield


@pytest.fixture
def pipeline_mock():
    from integrations.atom_communication_ingestion_pipeline import ingestion_pipeline

    with patch.object(
        ingestion_pipeline,
        "ingest_email_on_demand",
        new=AsyncMock(return_value={"status": "ingested", "subject": "Hi", "attachments": 1}),
    ) as mock:
        yield mock


@pytest.mark.asyncio
async def test_unsupported_provider_rejected_before_pipeline(auto_gate, db_session_ctx, pipeline_mock):
    import tools.email_ingest_tool as tool_mod

    result = await tool_mod.email_ingest_message(
        user_id="u-1", provider="slack", message_id="abc"
    )
    assert result["success"] is False
    assert "Unsupported provider" in result["error"]
    pipeline_mock.assert_not_awaited()


@pytest.mark.asyncio
async def test_missing_message_id_rejected(auto_gate, db_session_ctx, pipeline_mock):
    import tools.email_ingest_tool as tool_mod

    result = await tool_mod.email_ingest_message(
        user_id="u-1", provider="outlook", message_id="  "
    )
    assert result["success"] is False
    assert "message_id" in result["error"]
    pipeline_mock.assert_not_awaited()


@pytest.mark.asyncio
async def test_gate_propose_blocks_pipeline_call(propose_gate, db_session_ctx, pipeline_mock):
    import tools.email_ingest_tool as tool_mod

    result = await tool_mod.email_ingest_message(
        user_id="u-1", provider="outlook", message_id="abc"
    )
    assert result["success"] is False
    assert result["needs_approval"] is True
    assert result["topic"] == "email_attachment"
    pipeline_mock.assert_not_awaited()


@pytest.mark.asyncio
async def test_ingested_result_mapping(auto_gate, db_session_ctx, pipeline_mock):
    import tools.email_ingest_tool as tool_mod

    result = await tool_mod.email_ingest_message(
        user_id="u-1", provider="outlook", message_id="abc"
    )
    assert result["success"] is True
    assert result["status"] == "ingested"
    assert result["subject"] == "Hi"
    assert result["attachments"] == 1
    pipeline_mock.assert_awaited_once_with("outlook", "u-1", "abc")


@pytest.mark.asyncio
async def test_provider_alias_maps_to_pipeline_app(auto_gate, db_session_ctx, pipeline_mock):
    import tools.email_ingest_tool as tool_mod

    await tool_mod.email_ingest_message(
        user_id="u-1", provider="Microsoft", message_id="abc"
    )
    pipeline_mock.assert_awaited_once_with("outlook", "u-1", "abc")


@pytest.mark.asyncio
async def test_already_ingested_is_truthful_noop(auto_gate, db_session_ctx, pipeline_mock):
    import tools.email_ingest_tool as tool_mod

    pipeline_mock.return_value = {"status": "already_ingested"}
    result = await tool_mod.email_ingest_message(
        user_id="u-1", provider="gmail", message_id="gm-1"
    )
    assert result["success"] is True
    assert result["status"] == "already_ingested"


@pytest.mark.asyncio
async def test_pipeline_error_mapped_to_failure(auto_gate, db_session_ctx, pipeline_mock):
    import tools.email_ingest_tool as tool_mod

    pipeline_mock.return_value = {
        "status": "error",
        "reason": "message_not_found_or_unreachable",
    }
    result = await tool_mod.email_ingest_message(
        user_id="u-1", provider="outlook", message_id="gone"
    )
    assert result["success"] is False
    assert result["error"] == "message_not_found_or_unreachable"


@pytest.mark.asyncio
async def test_pipeline_exception_mapped_to_failure(auto_gate, db_session_ctx, pipeline_mock):
    import tools.email_ingest_tool as tool_mod

    pipeline_mock.side_effect = RuntimeError("lancedb offline")
    result = await tool_mod.email_ingest_message(
        user_id="u-1", provider="outlook", message_id="abc"
    )
    assert result["success"] is False
    assert "lancedb offline" in result["error"]


# ---------------------------------------------------------------------------
# Pipeline-level tests (CommunicationIngestionPipeline.ingest_email_on_demand)
# ---------------------------------------------------------------------------


def _bare_pipeline():
    """Pipeline instance without __init__ (no LanceDB); only the state the
    on-demand path touches is provided."""
    from integrations.atom_communication_ingestion_pipeline import (
        CommunicationIngestionPipeline,
    )

    pipe = CommunicationIngestionPipeline.__new__(CommunicationIngestionPipeline)
    pipe._seen_message_ids = {}
    pipe._seen_state_lock = threading.Lock()
    pipe._save_fetch_state = lambda: None
    return pipe


def _raw_graph_message(message_id="AAMkGraph1"):
    return {
        "id": message_id,
        "subject": "Contract redline",
        "receivedDateTime": "2026-09-08T10:00:00Z",
        "from": {
            "emailAddress": {"name": "Dana Supplier", "address": "dana@corp.test"}
        },
        "toRecipients": [{"emailAddress": {"address": "u-1@corp.test"}}],
        "body": {"content": "<p>See attached.</p>", "contentType": "html"},
        "isRead": False,
        "importance": "normal",
        "conversationId": "thr-1",
        "attachments": [
            {
                "id": "att-1",
                "name": "contract.pdf",
                "size": 12345,
                "contentType": "application/pdf",
                "isInline": False,
                "contentBytes": "AAAA",
            }
        ],
    }


@pytest.mark.asyncio
async def test_on_demand_outlook_happy_path_marks_seen():
    pipe = _bare_pipeline()
    pipe.is_message_known = lambda *a, **k: False
    pipe.ingest_message = AsyncMock(return_value=True)
    pipe._fetch_outlook_message_by_id = AsyncMock(
        return_value=_raw_graph_message()
    )
    marked = []
    pipe.mark_message_ingested = lambda app, mid, owner: marked.append((app, mid, owner))

    result = await pipe.ingest_email_on_demand("outlook", "u-1", "AAMkGraph1")

    assert result["status"] == "ingested"
    assert result["subject"] == "Contract redline"
    assert result["attachments"] == 1
    pipe.ingest_message.assert_awaited_once()
    ingested_msg = pipe.ingest_message.await_args.args[1]
    assert ingested_msg["metadata"]["user_id"] == "u-1"
    assert marked == [("outlook", "AAMkGraph1", "u-1")]


@pytest.mark.asyncio
async def test_on_demand_known_message_short_circuits():
    pipe = _bare_pipeline()
    pipe.is_message_known = lambda *a, **k: True
    pipe.ingest_message = AsyncMock(return_value=True)

    result = await pipe.ingest_email_on_demand("outlook", "u-1", "AAMkGraph1")

    assert result["status"] == "already_ingested"
    pipe.ingest_message.assert_not_awaited()


@pytest.mark.asyncio
async def test_on_demand_unreachable_message_is_error_not_marked():
    pipe = _bare_pipeline()
    pipe.is_message_known = lambda *a, **k: False
    pipe.ingest_message = AsyncMock(return_value=True)
    pipe._fetch_outlook_message_by_id = AsyncMock(return_value=None)
    marked = []
    pipe.mark_message_ingested = lambda app, mid, owner: marked.append((app, mid, owner))

    result = await pipe.ingest_email_on_demand("outlook", "u-1", "gone")

    assert result["status"] == "error"
    assert result["reason"] == "message_not_found_or_unreachable"
    pipe.ingest_message.assert_not_awaited()
    assert marked == []


@pytest.mark.asyncio
async def test_on_demand_store_failure_stays_on_retry_path():
    pipe = _bare_pipeline()
    pipe.is_message_known = lambda *a, **k: False
    pipe.ingest_message = AsyncMock(return_value=False)
    pipe._fetch_outlook_message_by_id = AsyncMock(
        return_value=_raw_graph_message()
    )
    marked = []
    pipe.mark_message_ingested = lambda app, mid, owner: marked.append((app, mid, owner))

    result = await pipe.ingest_email_on_demand("outlook", "u-1", "AAMkGraph1")

    assert result["status"] == "error"
    assert result["reason"] == "store_write_failed"
    assert marked == []


@pytest.mark.asyncio
async def test_on_demand_rejects_non_email_provider():
    pipe = _bare_pipeline()
    result = await pipe.ingest_email_on_demand("slack", "u-1", "abc")
    assert result["status"] == "error"
    assert "unsupported provider" in result["reason"]


def test_outlook_normalizer_matches_poller_shape():
    pipe = _bare_pipeline()
    normalized = pipe._normalize_outlook_graph_message(_raw_graph_message(), "owner-9")

    assert normalized is not None
    assert normalized["id"] == "AAMkGraph1"
    assert normalized["app_type"] == "outlook"
    assert isinstance(normalized["timestamp"], datetime)
    assert normalized["sender"] == "Dana Supplier"
    assert normalized["sender_email"] == "dana@corp.test"
    assert normalized["recipient"] == "u-1@corp.test"
    assert normalized["status"] == "unread"
    assert normalized["metadata"]["user_id"] == "owner-9"
    assert normalized["attachments"][0]["contentBytes"] == "AAAA"
    assert normalized["attachments"][0]["content_type"] == "application/pdf"


def test_gmail_normalizer_matches_poller_shape():
    pipe = _bare_pipeline()
    msg = {
        "id": "gm-1",
        "threadId": "t-1",
        "subject": "Invoice",
        "sender": "Alice <alice@x.test>",
        "date": "Tue, 8 Sep 2026 10:00:00 +0000",
        "body": "Invoice attached",
        "body_content_type": "text",
        "labelIds": ["INBOX"],
        "attachments": [
            {"filename": "inv.pdf", "mimeType": "application/pdf", "attachmentId": "a1", "size": 10}
        ],
    }
    normalized = pipe._normalize_gmail_service_message(msg)

    assert normalized is not None
    assert normalized["id"] == "gm-1"
    assert normalized["app_type"] == "gmail"
    assert normalized["sender"] == "Alice"
    assert normalized["sender_email"] == "alice@x.test"
    assert isinstance(normalized["timestamp"], datetime)
    assert normalized["metadata"]["thread_id"] == "t-1"
    assert normalized["attachments"][0]["filename"] == "inv.pdf"
    assert "INBOX" in normalized["tags"]
