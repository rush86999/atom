"""PDF canvas P3/P4 tests — trust operations, generation, sign & archive.

- Engine: AcroForm fill/flatten, TRUE redaction (content-stream removal +
  verify + failed-target honesty), real annotations, signature stamp,
  generate-from-data, sanitize/security survey.
- Service: versioned mutations (form/flatten/redact), attach flatten option
  (email carries the frozen copy; the canvas keeps its editable version),
  generate → new canvas, archive/DocuSign degrade cleanly when unconfigured.
- DocuSign service: JWT→envelope flow with a mocked transport; dormant
  (clean error) without credentials.
"""

import io
import os

os.environ.setdefault("TESTING", "1")

import pytest
from unittest.mock import patch

from core import pdf_engine
from core.pdf_engine import PdfEngineError


def _make_pdf(text: str = "doc", pages: int = 1) -> bytes:
    from reportlab.pdfgen import canvas as rl_canvas

    buf = io.BytesIO()
    c = rl_canvas.Canvas(buf, pagesize=(612, 792))
    for i in range(pages):
        c.setFont("Helvetica", 12)
        c.drawString(72, 700, f"{text} p{i + 1}")
        c.showPage()
    c.save()
    return buf.getvalue()


def _make_doc_with_secret() -> bytes:
    from reportlab.pdfgen import canvas as rl_canvas

    buf = io.BytesIO()
    c = rl_canvas.Canvas(buf, pagesize=(612, 792))
    c.setFont("Helvetica", 12)
    c.drawString(72, 700, "Client: Acme Corp")
    c.drawString(72, 680, "SSN: 123-45-6789")
    c.showPage()
    c.save()
    return buf.getvalue()


def _make_form_pdf() -> bytes:
    from reportlab.pdfgen import canvas as rl_canvas

    buf = io.BytesIO()
    c = rl_canvas.Canvas(buf, pagesize=(612, 792))
    c.setFont("Helvetica", 12)
    c.drawString(72, 700, "Purchase Order")
    c.acroForm.textfield(name="po_number", x=72, y=650, width=200, height=20,
                         borderWidth=0, value="PO-1")
    c.showPage()
    c.save()
    return buf.getvalue()


def _text(data: bytes, page: int = 0) -> str:
    from pypdf import PdfReader

    return PdfReader(io.BytesIO(data)).pages[page].extract_text() or ""


# ── engine: forms ────────────────────────────────────────────────────────


def test_form_fill_then_flatten():
    fields = pdf_engine.get_form_fields(_make_form_pdf())
    assert fields == {"po_number": {"type": "/Tx", "value": "PO-1"}}

    filled = pdf_engine.set_form_fields(_make_form_pdf(), {"po_number": "PO-777"})
    assert pdf_engine.get_form_fields(filled)["po_number"]["value"] == "PO-777"

    with pytest.raises(PdfEngineError, match="unknown form fields"):
        pdf_engine.set_form_fields(_make_form_pdf(), {"nope": "x"})

    flat = pdf_engine.flatten_form(filled)
    assert pdf_engine.get_form_fields(flat) == {}  # interactive layer gone
    assert "PO-777" in _text(flat)                 # value burned in


def test_flatten_without_form_is_a_noop_passthrough():
    data = _make_pdf("plain")
    flat = pdf_engine.flatten_form(data)
    assert pdf_engine.load_info(flat)["page_count"] == 1
    assert "plain p1" in _text(flat)


# ── engine: redaction ────────────────────────────────────────────────────


def test_redact_removes_text_and_verifies():
    outcome = pdf_engine.redact(_make_doc_with_secret(), [{"page": 0, "text": "SSN: 123-45-6789"}])
    assert outcome["removed"] == [{"page": 0, "text": "SSN: 123-45-6789", "occurrences": 1}]
    assert outcome["failed"] == []
    text = _text(outcome["bytes"])
    assert "SSN" not in text and "6789" not in text      # truly gone
    assert "Acme Corp" in text                            # neighbours intact


def test_redact_reports_unfindable_targets():
    outcome = pdf_engine.redact(_make_doc_with_secret(), [{"page": 0, "text": "not-in-doc"}])
    assert outcome["failed"] == [{"page": 0, "text": "not-in-doc"}]
    assert outcome["bytes"]  # still returns usable bytes; caller decides


def test_redact_out_of_range_page_refuses():
    with pytest.raises(PdfEngineError, match="out of range"):
        pdf_engine.redact(_make_doc_with_secret(), [{"page": 5, "text": "x"}])


# ── engine: annotations / stamp / generate / sanitize ────────────────────


def test_annotate_adds_real_annotation_objects():
    from pypdf import PdfReader

    ann = pdf_engine.annotate(_make_pdf("doc"), [
        {"page": 0, "kind": "note", "rect": [72, 700, 90, 716], "text": "check"},
        {"page": 0, "kind": "freetext", "rect": [72, 640, 300, 660], "text": "reviewed"},
    ])
    annots = PdfReader(io.BytesIO(ann)).pages[0].get("/Annots") or []
    assert len(annots) == 2
    with pytest.raises(PdfEngineError, match="unknown annotation kind"):
        pdf_engine.annotate(_make_pdf("doc"), [{"page": 0, "kind": "underline"}])
    with pytest.raises(PdfEngineError, match="out of range"):
        pdf_engine.annotate(_make_pdf("doc"), [{"page": 9, "kind": "note"}])


def test_signature_stamp():
    stamped = pdf_engine.stamp_signature(
        _make_pdf("contract"), 0, ["Rishi P."], [72, 600, 272, 650],
        "signed 2026-09-04 via ATOM",
    )
    text = _text(stamped)
    assert "Rishi P." in text and "signed 2026-09-04" in text
    with pytest.raises(PdfEngineError, match="out of range"):
        pdf_engine.stamp_signature(_make_pdf("c"), 9, ["x"], [72, 600, 272, 650])


def test_generate_quote_renders_items_and_total():
    gen = pdf_engine.generate_document(
        "quote", {"company": "Atom", "customer": "Acme",
                  "items": [{"description": "License", "amount": 500},
                            {"description": "Support", "amount": 100}]},
        "Q3 Quote",
    )
    text = _text(gen)
    assert "Q3 Quote" in text and "License" in text and "600.00" in text
    with pytest.raises(PdfEngineError, match="unknown template"):
        pdf_engine.generate_document("brochure", {}, "x")


def test_sanitize_strips_metadata_and_survey_reports():
    survey = pdf_engine.security_survey(pdf_engine.sanitize(_make_pdf("doc")))
    assert survey["javascript"] is False and survey["attachments"] is False
    assert survey["encrypted"] is False


# ── service: versioned trust ops + unconfigured degradation ─────────────


@pytest.fixture
def db_session(tmp_path, monkeypatch):
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    from core.models import Base

    monkeypatch.setenv("ATOM_PDF_CANVAS_DIR", str(tmp_path / "pdf_blobs"))
    eng = create_engine(f"sqlite:///{tmp_path}/trust_ops.db")
    Base.metadata.create_all(bind=eng)
    Session = sessionmaker(bind=eng, expire_on_commit=False)
    with Session() as s:
        yield s


@pytest.fixture
def session_ctx(db_session):
    import contextlib

    with patch("core.database.get_db_session", contextlib.contextmanager(lambda: (yield db_session))):
        yield db_session


@pytest.fixture
def svc(session_ctx):
    from core.pdf_canvas_service import PdfCanvasService

    return PdfCanvasService(session_ctx)


@pytest.fixture
def form_canvas(svc):
    result = svc.create_pdf_canvas("u-1", filename="po.pdf", content_bytes=_make_form_pdf())
    assert result["success"]
    return result["canvas_id"]


def test_service_form_fill_is_versioned(svc, form_canvas):
    base = svc.get_state(form_canvas, "u-1")["state"]
    result = svc.set_form_fields(form_canvas, "u-1", {"po_number": "PO-9"}, base_hash=base["file"]["hash"])
    assert result["success"]
    assert result["state"]["file"]["hash"] != base["file"]["hash"]
    assert result["state"]["versions"][-1]["action"] == "form_fill"
    # staged values readable back
    assert svc.get_form_fields(form_canvas, "u-1")["fields"]["po_number"]["value"] == "PO-9"


def test_service_redact_versioned_and_honest(svc):
    created = svc.create_pdf_canvas("u-1", content_bytes=_make_doc_with_secret())
    cid = created["canvas_id"]
    ok = svc.redact(cid, "u-1", [{"page": 0, "text": "SSN: 123-45-6789"}])
    assert ok["success"]
    assert "SSN" not in " ".join(
        p.get("text", "") for p in svc.extract_text(cid, "u-1")["pages"]
    )
    bad = svc.redact(cid, "u-1", [{"page": 0, "text": "not-there"}])
    assert bad["success"] is False and "redaction target not found" in bad["error"]


def test_service_generate_creates_canvas(svc):
    result = svc.generate("u-1", "default", "quote",
                          {"company": "Atom", "customer": "Acme",
                           "items": [{"description": "License", "amount": 500}]},
                          title="Q3 Quote")
    assert result["success"]
    text = " ".join(p["text"] for p in svc.extract_text(result["canvas_id"], "u-1")["pages"])
    assert "500.00" in text
    bad = svc.generate("u-1", "default", "brochure", {}, title="x")
    assert bad["success"] is False


def test_attach_flatten_stages_frozen_copy_without_mutating_canvas(svc, form_canvas):
    from core.email_attachment_store import read_staged
    from pypdf import PdfReader

    svc.set_form_fields(form_canvas, "u-1", {"po_number": "PO-9"})

    result = svc.attach_to_email(form_canvas, "u-1", flatten=True)
    assert result["success"] and result["flattened"] is True
    record = svc.db  # the staged bytes: no interactive fields, value burned in
    # fetch the staged record via the email side
    from core.canvas_email_service import EmailCanvasService

    email_svc = EmailCanvasService(svc.db)
    att = email_svc.list_attachments(result["email_canvas_id"], "u-1")["attachments"][0]
    staged = read_staged("u-1", result["email_canvas_id"], att["attachment_id"])
    assert PdfReader(io.BytesIO(staged)).get_fields() is None
    assert "PO-9" in _text(staged)

    # the canvas itself keeps its editable version
    assert svc.get_form_fields(form_canvas, "u-1")["fields"]["po_number"]["value"] == "PO-9"


def test_archive_and_docusign_degrade_cleanly_when_unconfigured(svc, form_canvas):
    import asyncio

    assert asyncio.run(svc.archive_to_onedrive(form_canvas, "u-1"))["success"] is False
    result = svc.send_to_docusign(form_canvas, "u-1", "signer@x.test", "Signer")
    assert result["success"] is False
    assert "not configured" in result["error"]


# ── docusign service: mocked transport ───────────────────────────────────


def test_docusign_dormant_without_env(monkeypatch):
    from integrations import docusign_service as ds

    for var in ("DOCUSIGN_INTEGRATION_KEY", "DOCUSIGN_USER_ID",
                "DOCUSIGN_ACCOUNT_ID", "DOCUSIGN_PRIVATE_KEY_B64"):
        monkeypatch.delenv(var, raising=False)
    assert ds.is_configured() is False
    result = ds.send_for_signature("a.pdf", b"%PDF-", "s@x.test", "Signer")
    assert result["success"] is False and "not configured" in result["error"]


def test_docusign_send_envelope_mocked(monkeypatch):
    from integrations import docusign_service as ds

    monkeypatch.setenv("DOCUSIGN_INTEGRATION_KEY", "ik")
    monkeypatch.setenv("DOCUSIGN_USER_ID", "uid")
    monkeypatch.setenv("DOCUSIGN_ACCOUNT_ID", "acc")
    monkeypatch.setenv("DOCUSIGN_PRIVATE_KEY_B64", "bm90LWFueS1rZXk=")  # not used by the mock

    calls = {"token": 0, "envelope": None}

    class FakeResp:
        def __init__(self, status, payload):
            self.status_code, self._payload = status, payload

        def json(self):
            return self._payload

        def raise_for_status(self):
            assert self.status_code in (200, 201)

        @property
        def text(self):
            return ""

    def fake_post(url, **kw):
        if "oauth/token" in url:
            return FakeResp(200, {"access_token": "tok", "expires_in": 3600})
        # envelope creation: capture and return an envelope id
        assert "/envelopes" in url and kw["json"]["status"] == "sent"
        assert kw["json"]["documents"][0]["documentBase64"]  # base64 pdf aboard
        return FakeResp(201, {"envelopeId": "env-123", "status": "sent"})

    calls["envelope"] = None

    # sign_jwt would fail with a bogus key — patch it out; the transport mock
    # is what this test exercises.
    with patch.object(ds, "_sign_jwt", return_value="assertion"), \
         patch.object(ds.requests, "post", side_effect=fake_post), \
         patch.object(ds.requests, "get", return_value=FakeResp(200, {"status": "completed"})):
        sent = ds.send_for_signature("po.pdf", b"%PDF-fake", "s@x.test", "Signer", "subject")
        assert sent["success"] is True
        assert sent["envelope_id"]

        status = ds.envelope_status("tok", "https://demo.docusign.net/restapi", "acc", sent["envelope_id"])
        assert status["success"] and status["status"] == "completed"


# ── inbound flow: email attachment → PDF canvas ──────────────────────────


@pytest.mark.asyncio
async def test_create_from_email_attachment(session_ctx, tmp_path):
    """The inbound half of the lifecycle: a pdf attachment on an email canvas
    becomes a PDF canvas with provenance stamped on its audit trail."""
    import asyncio

    from reportlab.pdfgen import canvas as rl_canvas

    from core.canvas_email_service import EmailCanvasService
    from core.pdf_canvas_service import PdfCanvasService

    svc = PdfCanvasService(session_ctx)
    buf = io.BytesIO()
    c = rl_canvas.Canvas(buf, pagesize=(612, 792))
    c.setFont("Helvetica", 12)
    c.drawString(72, 700, "vendor quote p1")
    c.showPage()
    c.save()

    email = EmailCanvasService(session_ctx).create_email_canvas(
        user_id="u-1", subject="Vendor reply", recipients=[])
    assert email["success"]
    staged = EmailCanvasService(session_ctx).stage_attachments(
        email["canvas_id"], "u-1",
        [{"filename": "vendor quote.pdf", "content_bytes": buf.getvalue(),
          "content_type": "application/pdf"}])
    assert staged["success"]
    att = staged["attachments"][0]["attachment_id"]

    result = await svc.create_from_email_attachment(
        "u-1", "default", email["canvas_id"], att)
    assert result["success"] is True
    assert result["state"]["source"] == "email_attachment"
    assert result["state"]["source_ref"]["email_canvas_id"] == email["canvas_id"]
    assert result["state"]["file"]["page_count"] == 1

    # non-pdf attachments are refused
    text_staged = EmailCanvasService(session_ctx).stage_attachments(
        email["canvas_id"], "u-1",
        [{"filename": "notes.txt", "content_bytes": b"hello", "content_type": "text/plain"}])
    bad = await svc.create_from_email_attachment(
        "u-1", "default", email["canvas_id"], text_staged["attachments"][0]["attachment_id"])
    assert bad["success"] is False and "not a PDF" in bad["error"]
