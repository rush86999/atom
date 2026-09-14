"""Image OCR for attachment/document ingestion.

Covers ``core.image_ocr``:

- the engine ladder (Tesseract when present, vision-LLM fallback otherwise),
- the decorative/signature heuristic used to keep inline email images
  (logos, signature blocks, tracking pixels) out of memory,
- the ``DocumentParser`` image branch that makes image attachments
  searchable instead of silently skipped as ``no_text``.

Red-first: every behavior below was absent before image OCR landed —
images returned "" from the parser on any host without Docling, so the
attachment was never indexed at all.
"""

import io
import os

os.environ.setdefault("TESTING", "1")

from unittest.mock import AsyncMock, patch

import pytest
from PIL import Image

import core.image_ocr as image_ocr


# ─── helpers ─────────────────────────────────────────────────────────────────


def _image(width: int, height: int, fmt: str = "PNG", color: str = "white") -> bytes:
    img = Image.new("RGB", (width, height), color)
    buf = io.BytesIO()
    img.save(buf, format=fmt)
    return buf.getvalue()


# ─── filename / content-type detection ──────────────────────────────────────


@pytest.mark.parametrize(
    "filename,expected",
    [
        ("scan.png", True),
        ("receipt.JPG", True),
        ("photo.jpeg", True),
        ("fax.tif", True),
        ("fax.tiff", True),
        ("bitmap.bmp", True),
        ("report.pdf", False),
        ("notes.txt", False),
        ("noext", False),
        ("", False),
        (None, False),
    ],
)
def test_is_image_filename(filename, expected):
    assert image_ocr.is_image_filename(filename) is expected


def test_is_image_content_type():
    assert image_ocr.is_image_content_type("image/png") is True
    assert image_ocr.is_image_content_type("IMAGE/JPEG") is True
    assert image_ocr.is_image_content_type("application/pdf") is False
    assert image_ocr.is_image_content_type("") is False


# ─── decorative / signature heuristic ───────────────────────────────────────


def test_signature_detected_by_tiny_dimensions():
    """Icons, spacers and tracking pixels are not worth OCR'ing."""
    assert image_ocr.is_likely_signature_or_logo(_image(32, 32), "img.png") is True
    assert image_ocr.is_likely_signature_or_logo(_image(600, 40), "img.png") is True


def test_signature_detected_by_filename_token():
    assert image_ocr.is_likely_signature_or_logo(_image(800, 600), "company-logo.png") is True
    assert image_ocr.is_likely_signature_or_logo(_image(800, 600), "signature_block.jpg") is True


def test_real_screenshot_is_not_a_signature():
    """A pasted screenshot is inline but must survive the filter."""
    assert image_ocr.is_likely_signature_or_logo(_image(900, 700), "image001.png") is False
    assert image_ocr.is_likely_signature_or_logo(_image(1200, 300), "chart.png") is False


def test_signature_heuristic_never_false_positives_on_undecodable_bytes():
    """Unknown dimensions must not drop data — only a filename hint can."""
    assert image_ocr.is_likely_signature_or_logo(b"not-an-image", "scan.png") is False


# ─── OCR ladder ──────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_ocr_prefers_local_tesseract():
    with patch.object(image_ocr, "tesseract_command", return_value="/usr/bin/tesseract"), patch.object(
        image_ocr, "_tesseract_text", return_value="INVOICE 12345 TOTAL 987.65"
    ) as local, patch.object(
        image_ocr, "_vision_ocr_text", new=AsyncMock(return_value="vision answer")
    ) as vision:
        result = await image_ocr.ocr_image_bytes(_image(400, 120), "scan.png", "image/png")

    assert result["success"] is True
    assert result["engine"] == "tesseract"
    assert result["text"] == "INVOICE 12345 TOTAL 987.65"
    assert result["chars"] == len("INVOICE 12345 TOTAL 987.65")
    local.assert_called_once()
    vision.assert_not_awaited()


@pytest.mark.asyncio
async def test_ocr_falls_back_to_vision_when_no_local_engine():
    with patch.object(image_ocr, "tesseract_command", return_value=None), patch.object(
        image_ocr, "_vision_ocr_text", new=AsyncMock(return_value="Receipt total 42.00")
    ) as vision:
        result = await image_ocr.ocr_image_bytes(_image(800, 600), "scan.png", "image/png")

    assert result["success"] is True
    assert result["engine"] == "vision"
    assert result["text"] == "Receipt total 42.00"
    vision.assert_awaited_once()


@pytest.mark.asyncio
async def test_ocr_falls_back_to_vision_when_tesseract_yields_nothing():
    """A blank local read (photo of an object, handwriting) still reaches vision."""
    with patch.object(image_ocr, "tesseract_command", return_value="/usr/bin/tesseract"), patch.object(
        image_ocr, "_tesseract_text", return_value="   "
    ), patch.object(
        image_ocr, "_vision_ocr_text", new=AsyncMock(return_value="HANDWRITTEN NOTE")
    ):
        result = await image_ocr.ocr_image_bytes(_image(800, 600), "scan.png", "image/png")

    assert result["success"] is True
    assert result["engine"] == "vision"


@pytest.mark.asyncio
async def test_ocr_reports_no_engine_when_nothing_available(monkeypatch):
    monkeypatch.setenv("ATOM_IMAGE_OCR_VISION_ENABLED", "false")
    with patch.object(image_ocr, "tesseract_command", return_value=None):
        result = await image_ocr.ocr_image_bytes(_image(800, 600), "scan.png", "image/png")

    assert result["success"] is False
    assert result["reason"] == "no_engine"
    assert result["text"] == ""


@pytest.mark.asyncio
async def test_ocr_reports_empty_text_when_engines_find_nothing(monkeypatch):
    monkeypatch.setenv("ATOM_IMAGE_OCR_VISION_ENABLED", "false")
    with patch.object(image_ocr, "tesseract_command", return_value="/usr/bin/tesseract"), patch.object(
        image_ocr, "_tesseract_text", return_value=""
    ):
        result = await image_ocr.ocr_image_bytes(_image(800, 600), "scan.png", "image/png")

    assert result["success"] is False
    assert result["reason"] == "empty_text"


@pytest.mark.asyncio
async def test_ocr_min_chars_drops_decorative_text():
    """Signature blocks OCR to a couple of words — below the inline floor."""
    with patch.object(image_ocr, "tesseract_command", return_value="/usr/bin/tesseract"), patch.object(
        image_ocr, "_tesseract_text", return_value="ACME"
    ):
        result = await image_ocr.ocr_image_bytes(
            _image(400, 120), "scan.png", "image/png", min_text_chars=16
        )

    assert result["success"] is False
    assert result["reason"] == "decorative"
    assert result["text"] == ""
    assert result["engine"] == "tesseract"


@pytest.mark.asyncio
async def test_ocr_min_chars_keeps_substantial_text():
    with patch.object(image_ocr, "tesseract_command", return_value="/usr/bin/tesseract"), patch.object(
        image_ocr, "_tesseract_text", return_value="Invoice 12345 total 987.65 due 2026-10-01"
    ):
        result = await image_ocr.ocr_image_bytes(
            _image(400, 120), "scan.png", "image/png", min_text_chars=16
        )

    assert result["success"] is True


@pytest.mark.asyncio
async def test_ocr_master_switch_disables_everything(monkeypatch):
    monkeypatch.setenv("ATOM_IMAGE_OCR_ENABLED", "false")
    with patch.object(image_ocr, "tesseract_command", return_value="/usr/bin/tesseract") as cmd:
        result = await image_ocr.ocr_image_bytes(_image(800, 600), "scan.png", "image/png")

    assert result["success"] is False
    assert result["reason"] == "disabled"
    cmd.assert_not_called()


@pytest.mark.asyncio
async def test_ocr_never_raises():
    with patch.object(image_ocr, "tesseract_command", return_value="/usr/bin/tesseract"), patch.object(
        image_ocr, "_tesseract_text", side_effect=RuntimeError("tesseract exploded")
    ), patch.object(
        image_ocr, "_vision_ocr_text", new=AsyncMock(side_effect=RuntimeError("no key"))
    ):
        result = await image_ocr.ocr_image_bytes(_image(800, 600), "scan.png", "image/png")

    assert result["success"] is False
    assert result["text"] == ""


@pytest.mark.asyncio
async def test_ocr_empty_content_is_rejected():
    result = await image_ocr.ocr_image_bytes(b"", "scan.png", "image/png")
    assert result["success"] is False
    assert result["reason"] == "empty_content"


# ─── DocumentParser wiring ───────────────────────────────────────────────────


@pytest.mark.parametrize("ext", ["png", "jpg", "jpeg", "tif", "tiff", "bmp"])
@pytest.mark.asyncio
async def test_parse_document_routes_images_through_ocr(ext):
    """Red-first: before image OCR this returned "" for every image type."""
    from core.auto_document_ingestion import DocumentParser

    with patch.object(DocumentParser, "_get_docling_processor", return_value=None), patch(
        "core.image_ocr.ocr_image_bytes",
        new=AsyncMock(return_value={
            "success": True, "text": "Scanned invoice total 987.65",
            "engine": "tesseract", "chars": 28, "reason": None,
        }),
    ) as ocr:
        text = await DocumentParser.parse_document(_image(800, 600), ext, f"scan.{ext}")

    assert text == "Scanned invoice total 987.65"
    ocr.assert_awaited_once()


@pytest.mark.asyncio
async def test_parse_document_propagates_image_min_chars():
    """Inline email images ask the parser to drop signature-length text."""
    from core.auto_document_ingestion import DocumentParser

    with patch.object(DocumentParser, "_get_docling_processor", return_value=None), patch(
        "core.image_ocr.ocr_image_bytes",
        new=AsyncMock(return_value={
            "success": False, "text": "", "engine": "tesseract", "chars": 4,
            "reason": "decorative",
        }),
    ) as ocr:
        text = await DocumentParser.parse_document(
            _image(400, 120), "png", "inline.png", image_min_chars=16
        )

    assert text == ""
    assert ocr.await_args.kwargs["min_text_chars"] == 16


@pytest.mark.asyncio
async def test_parse_document_image_ocr_failure_returns_no_text():
    from core.auto_document_ingestion import DocumentParser

    with patch.object(DocumentParser, "_get_docling_processor", return_value=None), patch(
        "core.image_ocr.ocr_image_bytes",
        new=AsyncMock(return_value={
            "success": False, "text": "", "engine": None, "chars": 0,
            "reason": "no_engine",
        }),
    ):
        text = await DocumentParser.parse_document(_image(800, 600), "png", "scan.png")

    assert text == ""



# ─── vision failure messages must never become document text ────────────────


@pytest.mark.asyncio
async def test_vision_failure_message_is_not_treated_as_ocr_text():
    """A missing/misconfigured BYOK key makes the vision model reply with a
    conversational error; indexing that string as document content pollutes
    recall (live: three memory rows read "I'm sorry, I couldn't generate a
    response. Please check your API key configurati…")."""
    failure = (
        "I'm sorry, I couldn't generate a response. Please check your API key "
        "configuration and try again."
    )
    with patch.object(image_ocr, "tesseract_command", return_value=None), patch(
        "core.llm_service.get_llm_service"
    ) as get_llm:
        service = get_llm.return_value
        service.is_available.return_value = True
        service.generate_completion = AsyncMock(return_value={"content": failure})
        result = await image_ocr.ocr_image_bytes(_image(800, 600), "photo.png", "image/png")

    assert result["success"] is False
    assert result["text"] == ""


def test_looks_like_vision_failure_markers():
    assert image_ocr._looks_like_vision_failure(
        "I'm sorry, I couldn't generate a response."
    )
    assert image_ocr._looks_like_vision_failure("Error: insufficient balance")
    assert image_ocr._looks_like_vision_failure("Please check your API key configuration")
    # Real OCR content is never rejected.
    assert not image_ocr._looks_like_vision_failure("Invoice total 1,240.00 CAD")
    assert not image_ocr._looks_like_vision_failure("Sorry for the delay — see specs below")
    assert not image_ocr._looks_like_vision_failure("")


# ─── textless images: description fallback (explicit on-demand pulls) ───────


@pytest.mark.asyncio
async def test_textless_image_gets_description_when_requested():
    """A product photo has no text layer; without a description it is dropped
    as no_text and an agent can only report it inaccessible."""
    with patch.object(image_ocr, "tesseract_command", return_value=None), patch.object(
        image_ocr, "_vision_ocr_text", new=AsyncMock(return_value="")
    ), patch.object(
        image_ocr,
        "_vision_describe_text",
        new=AsyncMock(return_value="A metal bandsaw on a factory floor."),
    ):
        result = await image_ocr.ocr_image_bytes(
            _image(800, 600), "photo.png", "image/png", describe_when_textless=True
        )

    assert result["success"] is True
    assert result["engine"] == "vision-description"
    assert result["text"].startswith("Image description:")
    assert "bandsaw" in result["text"]


@pytest.mark.asyncio
async def test_textless_image_not_described_for_bulk_ingestion():
    """The poller must not pay for a description per decorative image."""
    with patch.object(image_ocr, "tesseract_command", return_value=None), patch.object(
        image_ocr, "_vision_ocr_text", new=AsyncMock(return_value="")
    ), patch.object(
        image_ocr, "_vision_describe_text", new=AsyncMock(return_value="A photo")
    ) as describe:
        result = await image_ocr.ocr_image_bytes(_image(800, 600), "photo.png", "image/png")

    assert result["success"] is False
    describe.assert_not_awaited()


@pytest.mark.asyncio
async def test_description_kill_switch(monkeypatch):
    monkeypatch.setenv("ATOM_IMAGE_DESCRIBE_ENABLED", "false")
    with patch.object(image_ocr, "tesseract_command", return_value=None), patch.object(
        image_ocr, "_vision_ocr_text", new=AsyncMock(return_value="")
    ), patch.object(
        image_ocr, "_vision_describe_text", new=AsyncMock(return_value="A photo")
    ) as describe:
        result = await image_ocr.ocr_image_bytes(
            _image(800, 600), "photo.png", "image/png", describe_when_textless=True
        )

    assert result["success"] is False
    describe.assert_not_awaited()


@pytest.mark.asyncio
async def test_parse_document_propagates_image_describe_flag():
    from core.auto_document_ingestion import DocumentParser

    with patch.object(DocumentParser, "_get_docling_processor", return_value=None), patch(
        "core.image_ocr.ocr_image_bytes",
        new=AsyncMock(return_value={
            "success": True, "text": "Image description: a bandsaw",
            "engine": "vision-description", "chars": 30, "reason": None,
        }),
    ) as ocr:
        text = await DocumentParser.parse_document(
            _image(800, 600), "png", "photo.png", image_describe=True
        )

    assert "a bandsaw" in text
    assert ocr.await_args.kwargs["describe_when_textless"] is True
