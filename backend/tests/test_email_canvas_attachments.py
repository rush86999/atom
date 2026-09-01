"""Email-canvas attachment CRUD + send (Phase 3 of the attachment plan).

- core.email_attachment_store: staged-file lifecycle, traversal guard, caps.
- EmailCanvasService stage/list/remove/get_bytes/ingest + send with
  attachment_ids (policy payload, OutlookService passthrough, staged cleanup).
"""

import os

os.environ.setdefault("TESTING", "1")

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from core.email_attachment_store import (
    delete_staged,
    read_staged,
    save_staged,
    sweep_orphans,
)


@pytest.fixture
def db_session(tmp_path, monkeypatch):
    """Fresh SQLite session; staged files land inside tmp_path."""
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    from core.models import Base

    monkeypatch.setenv("ATOM_EMAIL_ATTACHMENT_DIR", str(tmp_path / "staged"))
    eng = create_engine(f"sqlite:///{tmp_path}/canvas.db")
    Base.metadata.create_all(bind=eng)
    Session = sessionmaker(bind=eng, expire_on_commit=False)
    with Session() as s:
        yield s


@pytest.fixture
def canvas(db_session):
    from core.canvas_email_service import EmailCanvasService

    result = EmailCanvasService(db_session).create_email_canvas(
        user_id="u-1", subject="Q3 report", recipients=["mark@external.test"]
    )
    assert result["success"]
    return result["canvas_id"]


# ─── staged store ────────────────────────────────────────────────────────────


def test_staged_save_read_delete_roundtrip(tmp_path, monkeypatch):
    monkeypatch.setenv("ATOM_EMAIL_ATTACHMENT_DIR", str(tmp_path / "staged"))
    rec = save_staged("u-1", "c-1", "report.pdf", b"%PDF fake", "application/pdf")
    assert rec["attachment_id"].startswith("staged_")
    assert rec["provider"] == "local"
    assert rec["origin"] == "staged"
    assert read_staged("u-1", "c-1", rec["attachment_id"]) == b"%PDF fake"
    assert delete_staged("u-1", "c-1", rec["attachment_id"])
    assert read_staged("u-1", "c-1", rec["attachment_id"]) is None


def test_staged_rejects_disallowed_extension(tmp_path, monkeypatch):
    monkeypatch.setenv("ATOM_EMAIL_ATTACHMENT_DIR", str(tmp_path / "staged"))
    with pytest.raises(ValueError):
        save_staged("u-1", "c-1", "evil.sh", b"#!/bin/sh", "text/x-sh")


def test_staged_rejects_oversized_upload(tmp_path, monkeypatch):
    monkeypatch.setenv("ATOM_EMAIL_ATTACHMENT_DIR", str(tmp_path / "staged"))
    monkeypatch.setenv("EMAIL_ATTACHMENT_MAX_UPLOAD_MB", "1")
    with pytest.raises(ValueError):
        save_staged("u-1", "c-1", "big.pdf", b"x" * (1024 * 1024 + 1))


def test_staged_per_canvas_cap(tmp_path, monkeypatch):
    monkeypatch.setenv("ATOM_EMAIL_ATTACHMENT_DIR", str(tmp_path / "staged"))
    monkeypatch.setenv("EMAIL_ATTACHMENT_MAX_CANVAS_STAGED_MB", "1")
    save_staged("u-1", "c-1", "a.pdf", b"x" * 600_000)
    with pytest.raises(ValueError):
        save_staged("u-1", "c-1", "b.pdf", b"x" * 600_000)


def test_staged_ids_are_path_safe(tmp_path, monkeypatch):
    monkeypatch.setenv("ATOM_EMAIL_ATTACHMENT_DIR", str(tmp_path / "staged"))
    assert read_staged("u-1", "c-1", "../u-2/secret") is None
    assert delete_staged("u-1", "c-1", "../u-2/secret") is False


def test_orphan_sweep_removes_old_files(tmp_path, monkeypatch):
    monkeypatch.setenv("ATOM_EMAIL_ATTACHMENT_DIR", str(tmp_path / "staged"))
    rec = save_staged("u-1", "c-1", "old.pdf", b"x")
    path = next((tmp_path / "staged").rglob(rec["attachment_id"]))
    import os as _os
    import time as _time

    old = _time.time() - 100 * 3600
    _os.utime(path, (old, old))
    save_staged("u-1", "c-1", "new.pdf", b"y")
    removed = sweep_orphans(max_age_hours=72)
    assert removed == 1
    assert read_staged("u-1", "c-1", rec["attachment_id"]) is None


# ─── canvas service CRUD ─────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_stage_list_remove_roundtrip(db_session, canvas, tmp_path):
    from core.canvas_email_service import EmailCanvasService

    svc = EmailCanvasService(db_session)
    staged = svc.stage_attachments(
        canvas, "u-1",
        [{"filename": "report.pdf", "content_bytes": b"%PDF fake",
          "content_type": "application/pdf"}],
    )
    assert staged["success"]
    att = staged["attachments"][0]

    listed = svc.list_attachments(canvas, "u-1")
    assert listed["success"] and len(listed["attachments"]) == 1
    assert listed["attachments"][0]["filename"] == "report.pdf"

    resolved = await svc.get_attachment_bytes(canvas, "u-1", att["attachment_id"])
    assert resolved["bytes"] == b"%PDF fake"

    removed = svc.remove_attachment(canvas, "u-1", att["attachment_id"])
    assert removed["success"] and removed["staged_deleted"]
    assert read_staged("u-1", canvas, att["attachment_id"]) is None
    assert svc.list_attachments(canvas, "u-1")["attachments"] == []


def test_stage_rejects_non_owner(db_session, canvas):
    from core.canvas_email_service import EmailCanvasService

    svc = EmailCanvasService(db_session)
    result = svc.stage_attachments(
        canvas, "u-2",
        [{"filename": "x.pdf", "content_bytes": b"x", "content_type": "application/pdf"}],
    )
    assert not result["success"]
    assert svc.list_attachments(canvas, "u-2")["success"] is False


def test_stage_batch_fails_atomically(db_session, canvas, tmp_path, monkeypatch):
    """A disallowed file in the batch fails the WHOLE batch — no half-staged
    drafts with files silently missing."""
    from core.canvas_email_service import EmailCanvasService

    svc = EmailCanvasService(db_session)
    result = svc.stage_attachments(
        canvas, "u-1",
        [
            {"filename": "ok.pdf", "content_bytes": b"x", "content_type": "application/pdf"},
            {"filename": "bad.sh", "content_bytes": b"x", "content_type": "text/x-sh"},
        ],
    )
    assert not result["success"]
    assert "bad.sh" in result["error"]
    assert svc.list_attachments(canvas, "u-1")["attachments"] == []


# ─── send with attachments ───────────────────────────────────────────────────


def _mock_outlook():
    """Patch the OutlookService the canvas send path constructs; capture
    kwargs and simulate a successful send."""
    mock_cls = MagicMock()
    mock_cls.return_value.send_email = AsyncMock(return_value={"success": True})
    mock_cls.return_value.last_send_error = None
    return patch("integrations.outlook_service.OutlookService", mock_cls)


@pytest.mark.asyncio
async def test_send_with_attachments_passes_bytes_and_cleans_staged(
    db_session, canvas, tmp_path
):
    from core.canvas_email_service import EmailCanvasService

    svc = EmailCanvasService(db_session)
    staged = svc.stage_attachments(
        canvas, "u-1",
        [{"filename": "report.pdf", "content_bytes": b"%PDF fake",
          "content_type": "application/pdf"}],
    )
    att = staged["attachments"][0]

    with _mock_outlook() as mock_cls, patch.object(svc, "record_send"):
        result = await svc.send_email(
            canvas_id=canvas, user_id="u-1", to_emails=["mark@external.test"],
            subject="Q3 report", body="Attached.", attachment_ids=[att["attachment_id"]],
        )

    assert result["success"] is True
    kwargs = mock_cls.return_value.send_email.await_args.kwargs
    assert kwargs["attachments"][0]["filename"] == "report.pdf"
    assert kwargs["attachments"][0]["content_bytes"] == b"%PDF fake"
    # staged file deleted: the mailbox now holds the durable copy
    assert read_staged("u-1", canvas, att["attachment_id"]) is None
    listed = svc.list_attachments(canvas, "u-1")["attachments"]
    assert listed[0].get("sent_at")


@pytest.mark.asyncio
async def test_send_with_unknown_attachment_is_blocked(db_session, canvas):
    from core.canvas_email_service import EmailCanvasService

    svc = EmailCanvasService(db_session)
    with _mock_outlook() as mock_cls, patch.object(svc, "record_send"):
        result = await svc.send_email(
            canvas_id=canvas, user_id="u-1", to_emails=["a@b.com"],
            subject="S", body="B", attachment_ids=["staged_does_not_exist"],
        )
    assert result["success"] is False
    assert "Unknown attachment" in result["error"]
    mock_cls.return_value.send_email.assert_not_awaited()


@pytest.mark.asyncio
async def test_send_without_attachments_keeps_legacy_contract(db_session, canvas):
    from core.canvas_email_service import EmailCanvasService

    svc = EmailCanvasService(db_session)
    with _mock_outlook() as mock_cls, patch.object(svc, "record_send"):
        result = await svc.send_email(
            canvas_id=canvas, user_id="u-1", to_emails=["a@b.com"],
            subject="S", body="B",
        )
    assert result["success"] is True
    assert mock_cls.return_value.send_email.await_args.kwargs.get("attachments") is None


@pytest.mark.asyncio
async def test_attachment_csv_text_rides_policy_scan(db_session, canvas):
    """A text attachment carrying restricted content must BLOCK the send —
    the policy scans the attachment text, not just the body."""
    from core.canvas_email_service import EmailCanvasService

    svc = EmailCanvasService(db_session)
    pii_csv = (
        "ssn,name\n123-45-6789,John Doe\n"  # restricted-sensitivity content
    )
    staged = svc.stage_attachments(
        canvas, "u-1",
        [{"filename": "roster.csv", "content_bytes": pii_csv.encode(),
          "content_type": "text/csv"}],
    )
    att = staged["attachments"][0]
    assert svc._attachment_policy_text(pii_csv.encode(), "roster.csv").startswith("ssn")

    with _mock_outlook() as mock_cls, patch.object(svc, "record_send"):
        result = await svc.send_email(
            canvas_id=canvas, user_id="u-1", to_emails=["mark@external.test"],
            subject="Roster", body="See attached", attachment_ids=[att["attachment_id"]],
        )
    if result.get("blocked_by") == "email_policy":
        mock_cls.return_value.send_email.assert_not_awaited()
    else:
        # classifier didn't flag the fixture — the text must still have been
        # handed to the policy (fail loud here rather than silently untested)
        pytest.fail(f"policy did not classify fixture as restricted: {result}")
