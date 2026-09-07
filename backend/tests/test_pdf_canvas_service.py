"""PdfCanvasService tests — lifecycle, versions, ownership, email handoff.

The service follows the email-canvas state model (latest pdf CanvasAudit
row IS the canvas), so these tests run against an in-memory SQLite with
just the Canvas + CanvasAudit tables, exactly like the playbook tests.
Blob storage is redirected to a tmp dir via ATOM_PDF_CANVAS_DIR (and the
staged attachment store to its own tmp via ATOM_EMAIL_ATTACHMENT_DIR) so
no test touches real data/.
"""
import io
import os

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from core.database import Base
from core.models import Canvas, CanvasAudit
from core.pdf_canvas_service import PdfCanvasService

TABLES = [Canvas.__table__, CanvasAudit.__table__]

USER = "user-1"
OTHER = "user-2"


@pytest.fixture()
def db(tmp_path, monkeypatch):
    monkeypatch.setenv("ATOM_PDF_CANVAS_DIR", str(tmp_path / "pdf_blobs"))
    monkeypatch.setenv("ATOM_EMAIL_ATTACHMENT_DIR", str(tmp_path / "staged"))
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine, tables=TABLES)
    session = sessionmaker(bind=engine)()
    yield session
    session.close()


@pytest.fixture()
def svc(db):
    return PdfCanvasService(db)


def _make_pdf(text: str, pages: int = 1) -> bytes:
    from reportlab.pdfgen import canvas as rl_canvas

    buf = io.BytesIO()
    c = rl_canvas.Canvas(buf, pagesize=(612, 792))
    for i in range(pages):
        c.setFont("Helvetica", 12)
        c.drawString(72, 700, f"{text} p{i + 1}")
        c.showPage()
    c.save()
    return buf.getvalue()


def test_create_blank_and_upload(svc):
    blank = svc.create_pdf_canvas(USER, title="Quote", filename="quote.pdf")
    assert blank["success"] is True
    state = blank["state"]
    assert state["file"]["page_count"] == 1
    assert state["source"] == "blank"
    assert state["lifecycle"]["state"] == "drafting"
    # canvas row exists with owner + type (generic canvas reads depend on it)
    row = svc.db.query(Canvas).filter(Canvas.id == blank["canvas_id"]).one()
    assert row.created_by == USER and row.canvas_type == "pdf"

    up = svc.create_pdf_canvas(USER, filename="contract.pdf", content_bytes=_make_pdf("contract", pages=2))
    assert up["success"] is True
    assert up["state"]["file"]["page_count"] == 2
    assert up["state"]["source"] == "upload"

    bad = svc.create_pdf_canvas(USER, filename="junk.pdf", content_bytes=b"garbage")
    assert bad["success"] is False


def test_page_ops_version_and_conflict_guard(svc):
    created = svc.create_pdf_canvas(USER, content_bytes=_make_pdf("p", pages=3))
    cid = created["canvas_id"]
    base_hash = created["state"]["file"]["hash"]

    result = svc.apply_page_ops(cid, USER, [
        {"src_index": 2, "rotation": 0},
        {"src_index": 0, "rotation": 90},
    ], base_hash=base_hash)
    assert result["success"] is True
    new_state = result["state"]
    assert new_state["file"]["page_count"] == 2
    assert new_state["file"]["hash"] != base_hash
    assert len(new_state["versions"]) == 2

    # stale save (same base_hash again) must conflict, not double-apply
    conflict = svc.apply_page_ops(cid, USER, [{"src_index": 0, "rotation": 0}], base_hash=base_hash)
    assert conflict["success"] is False and conflict.get("conflict") is True

    # out-of-range page is a clean policy error, not a 500
    bad = svc.apply_page_ops(cid, USER, [{"src_index": 9, "rotation": 0}])
    assert bad["success"] is False and "out of range" in bad["error"]


def test_ownership_is_enforced(svc):
    created = svc.create_pdf_canvas(USER, content_bytes=_make_pdf("p", pages=1))
    cid = created["canvas_id"]
    assert svc.apply_page_ops(cid, OTHER, [{"src_index": 0, "rotation": 0}])["success"] is False
    assert svc.get_bytes(cid, OTHER) is None
    assert svc.extract_text(cid, OTHER)["success"] is False
    assert svc.attach_to_email(cid, OTHER)["success"] is False


def test_merge_upload_and_extract_text(svc):
    created = svc.create_pdf_canvas(USER, content_bytes=_make_pdf("base", pages=1))
    cid = created["canvas_id"]
    merged = svc.merge_upload(cid, USER, "extra.pdf", _make_pdf("extra", pages=2))
    assert merged["success"] is True
    assert merged["state"]["file"]["page_count"] == 3

    extraction = svc.extract_text(cid, USER)
    assert extraction["success"] is True
    texts = " ".join(p["text"] for p in extraction["pages"])
    assert "base p1" in texts and "extra p2" in texts


def test_attach_to_email_stages_and_stamps_provenance(svc):
    from core.canvas_email_service import EmailCanvasService
    from core.email_attachment_store import read_staged

    created = svc.create_pdf_canvas(USER, filename="Q3 quote.pdf", content_bytes=_make_pdf("quote"))
    cid = created["canvas_id"]

    result = svc.attach_to_email(cid, USER)
    assert result["success"] is True
    assert result["created_email_canvas"] is True
    assert result["version_hash"] == created["state"]["file"]["hash"]

    # the email canvas really holds a staged pdf with the exact bytes
    email_svc = EmailCanvasService(svc.db)
    attachments = email_svc.list_attachments(result["email_canvas_id"], USER)["attachments"]
    assert len(attachments) == 1
    record = attachments[0]
    assert record["content_type"] == "application/pdf"
    staged = read_staged(USER, result["email_canvas_id"], record["attachment_id"])
    assert staged is not None and staged == svc.get_bytes(cid, USER)["bytes"]

    # the PDF canvas audit trail carries the provenance chain
    provenance = [
        row for row in svc.db.query(CanvasAudit)
        .filter(CanvasAudit.canvas_id == cid, CanvasAudit.canvas_type == "pdf")
        if row.action_type == "pdf_attached_to_email"
    ]
    assert len(provenance) == 1
    details = provenance[0].details_json or {}
    assert details["email_canvas_id"] == result["email_canvas_id"]
    assert details["version_hash"] == created["state"]["file"]["hash"]
    assert details["attachment_id"] == record["attachment_id"]


def test_attach_to_existing_email_canvas(svc):
    from core.canvas_email_service import EmailCanvasService

    created = svc.create_pdf_canvas(USER, content_bytes=_make_pdf("doc"))
    cid = created["canvas_id"]
    email_svc = EmailCanvasService(svc.db)
    email = email_svc.create_email_canvas(user_id=USER, subject="PO request", recipients=["a@b.com"])

    result = svc.attach_to_email(cid, USER, email_canvas_id=email["canvas_id"])
    assert result["success"] is True
    assert result["created_email_canvas"] is False
    attachments = email_svc.list_attachments(email["canvas_id"], USER)["attachments"]
    assert attachments and attachments[0]["origin"] == "staged"
