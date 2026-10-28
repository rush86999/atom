"""Structured EML import controls (scratch DB + scratch attachment store)."""
from __future__ import annotations

from email.message import EmailMessage as StdEmail
from types import SimpleNamespace

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from core.canvas_email_service import EmailCanvasService
from core.database import Base
from core.models import Canvas, CanvasAudit


def _eml() -> bytes:
    message = StdEmail()
    message["From"] = "Dana Whitfield <dana@example.com>"
    message["To"] = "pilot@atom.test"
    message["Cc"] = "ops@example.com"
    message["Subject"] = "Q3 invoice request"
    message["Message-ID"] = "<q3-invoice@example.com>"
    message["In-Reply-To"] = "<thread-root@example.com>"
    message["References"] = "<thread-root@example.com> <q3-invoice@example.com>"
    message["Date"] = "Tue, 27 Oct 2026 10:30:00 -0400"
    message.set_content("Please process the attached invoice for Q3.\n")
    message.add_alternative(
        "<p>Please process the attached invoice for Q3.</p>", subtype="html")
    message.add_attachment(
        b"Invoice ref,Amount\nINV-9,1250.00\n",
        maintype="text", subtype="csv", filename="invoice.csv",
    )
    return message.as_bytes()


@pytest.fixture()
def db():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture()
def canvas(db):
    row = Canvas(
        id="canvas_email_1", tenant_id="default", workspace_id="default",
        created_by="user-1", name="Inbox", canvas_type="sheet",
        content={}, status="active",
    )
    db.add(row)
    db.commit()
    return row


def test_eml_import_preserves_envelope_body_thread_and_attachment(
    db, canvas, tmp_path, monkeypatch,
):
    monkeypatch.setenv("ATOM_EMAIL_ATTACHMENT_DIR", str(tmp_path / "attachments"))
    user = SimpleNamespace(id="user-1", workspace_id="default", tenant_id="default")
    result = EmailCanvasService(db).import_eml(
        canvas_id=canvas.id, user_id="user-1", content=_eml(),
        filename="q3-invoice.eml",
    )
    assert result["success"] is True
    assert result["subject"] == "Q3 invoice request"
    assert result["draft_subject"] == "Re: Q3 invoice request"
    assert result["draft_to"] == ["dana@example.com"]
    assert result["source_identity"]["message_id"] == "<q3-invoice@example.com>"
    assert result["source_identity"]["references"].startswith("<thread-root@example.com>")

    fresh = db.query(Canvas).filter(Canvas.id == canvas.id).first()
    content = fresh.content
    assert fresh.canvas_type == "email"
    assert content["subject"] == "Re: Q3 invoice request"
    assert content["source_message_id"] == "<q3-invoice@example.com>"
    assert content["in_reply_to"] == "<thread-root@example.com>"
    assert content["attachments"][0]["filename"] == "invoice.csv"
    assert content["attachments"][0]["origin"] == "received"
    assert content["attachments"][0]["sendable"] is False
    assert "Please process" in content["body"]

    audit = (
        db.query(CanvasAudit)
        .filter(CanvasAudit.canvas_id == canvas.id,
                CanvasAudit.canvas_type == "email")
        .order_by(CanvasAudit.created_at.desc())
        .first()
    )
    assert audit is not None
    imported = audit.details_json["imported_message"]
    assert imported["from_email"] == "dana@example.com"
    assert imported["to_emails"] == ["pilot@atom.test"]
    assert imported["cc_emails"] == ["ops@example.com"]
    assert imported["body"].startswith("Please process")
    assert imported["attachments"][0]["filename"] == "invoice.csv"
    assert audit.details_json["draft"]["subject"] == "Re: Q3 invoice request"

    # Fresh service instance = restart-equivalent read from the audit trail.
    listed = EmailCanvasService(db).list_attachments(canvas.id, "user-1")
    assert listed["attachments"][0]["filename"] == "invoice.csv"
    loaded = db.query(Canvas).filter(Canvas.id == canvas.id).first()
    assert loaded.content["references"] == "<thread-root@example.com> <q3-invoice@example.com>"
    assert user.id == "user-1"


def test_imported_attachment_is_not_sendable_by_default(
    db, canvas, tmp_path, monkeypatch,
):
    monkeypatch.setenv("ATOM_EMAIL_ATTACHMENT_DIR", str(tmp_path / "attachments"))
    EmailCanvasService(db).import_eml(
        canvas_id=canvas.id, user_id="user-1", content=_eml(),
        filename="q3-invoice.eml",
    )
    service = EmailCanvasService(db)
    metadata = service._latest_email_metadata(canvas.id)
    record = metadata["attachments"][0]
    import asyncio
    with pytest.raises(ValueError):
        asyncio.run(service._resolve_send_attachments(
            metadata, canvas.id, "user-1", [record["attachment_id"]]))


def test_other_user_cannot_mutate_imported_email_canvas(db, canvas, tmp_path, monkeypatch):
    monkeypatch.setenv("ATOM_EMAIL_ATTACHMENT_DIR", str(tmp_path / "attachments"))
    service = EmailCanvasService(db)
    assert service.import_eml(
        canvas_id=canvas.id, user_id="user-1", content=_eml(),
        filename="q3-invoice.eml",
    )["success"] is True

    assert service.add_message_to_thread(
        canvas_id=canvas.id, user_id="user-2",
        from_email="attacker@example.com", to_emails=["victim@example.com"],
        subject="takeover", body="should not land",
    )["success"] is False
    assert service.save_draft(
        canvas_id=canvas.id, user_id="user-2",
        to_emails=["attacker@example.com"], subject="takeover", body="nope",
    )["success"] is False
    fresh = db.query(Canvas).filter(Canvas.id == canvas.id).first()
    assert fresh.content["subject"].startswith("Re: Q3 invoice request")


def test_save_draft_updates_public_canvas_content(db, canvas, tmp_path, monkeypatch):
    monkeypatch.setenv("ATOM_EMAIL_ATTACHMENT_DIR", str(tmp_path / "attachments"))
    service = EmailCanvasService(db)
    service.import_eml(
        canvas_id=canvas.id, user_id="user-1", content=_eml(),
        filename="q3-invoice.eml",
    )
    result = service.save_draft(
        canvas_id=canvas.id, user_id="user-1",
        to_emails=["dana@example.com"], cc_emails=[],
        subject="Re: Q3 invoice request", body="Draft body persisted.",
    )
    assert result["success"] is True
    fresh = db.query(Canvas).filter(Canvas.id == canvas.id).first()
    assert fresh.content["body"] == "Draft body persisted."
    assert fresh.content["source_message_id"] == "<q3-invoice@example.com>"
