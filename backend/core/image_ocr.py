"""Image OCR for document and attachment ingestion.

Email attachments, cloud-drive syncs and direct uploads all funnel image
bytes through ``DocumentParser.parse_document``. Before this module existed
the only OCR path was Docling — an *optional* dependency
(``requirements-docling.txt``; not installed in the default image) — so on a
standard install every image parsed to ``""`` and the attachment was dropped
as ``no_text``: never indexed, never recallable.

Engine ladder (first engine that yields text wins):

1. **Docling** — attempted by ``DocumentParser`` *before* this module is
   consulted (it is the repo's unified parser/OCR service), so reaching here
   already means Docling was unavailable or produced nothing.
2. **Tesseract** — the local, zero-API-cost engine. Uses ``pytesseract`` when
   importable, else the ``tesseract`` CLI directly (no Python dependency);
   path overridable via ``ATOM_IMAGE_OCR_TESSERACT_CMD``.
3. **Vision LLM** — a vision-capable BYOK model, so the feature also works on
   hosts with no local OCR engine at all (the default Docker image). One call
   per image, bounded by the existing per-attachment size and per-message
   count caps.

Everything here is best-effort and never raises: ingestion callers treat a
failure as "the attachment stays metadata-only", exactly like the rest of the
email-attachment pipeline.
"""

from __future__ import annotations

import asyncio
import base64
import io
import logging
import os
import shutil
import subprocess
import tempfile
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# Formats Tesseract/Leptonica reads directly. Mirrors the image half of
# core.email_attachment_ingestion._BINARY_ATTACHMENT_EXTENSIONS plus webp/gif
# (upload paths may carry them even though the email gate is narrower).
IMAGE_FILENAME_EXTENSIONS = frozenset(
    {"png", "jpg", "jpeg", "tif", "tiff", "bmp", "webp", "gif"}
)

_EXT_MIME = {
    "png": "image/png",
    "jpg": "image/jpeg",
    "jpeg": "image/jpeg",
    "tif": "image/tiff",
    "tiff": "image/tiff",
    "bmp": "image/bmp",
    "webp": "image/webp",
    "gif": "image/gif",
}

# Decorative-image heuristics (inline email images). A signature block, logo
# or tracking pixel is inline by nature and would otherwise be OCR'd and
# indexed as noise on nearly every message. Conservative on purpose: when the
# bytes can't be decoded we return False (keep the data) — only a filename
# hint or real dimensions may reject an image.
_SIGNATURE_FILENAME_TOKENS = (
    "signature",
    "logo",
    "banner",
    "spacer",
    "pixel",
    "divider",
    "emblem",
    "icon",
)
_MIN_DECORATIVE_DIMENSION = 64
_BANNER_ASPECT_RATIO = 4.0
_BANNER_MAX_SHORT_SIDE = 120

_VISION_PROMPT = (
    "Extract every piece of readable text from this image verbatim, preserving "
    "numbers, currency amounts and line breaks. If the image contains no text, "
    "reply with an empty string. Do not describe the image or add commentary."
)

DEFAULT_TESSERACT_TIMEOUT_SECONDS = 30
DEFAULT_VISION_MAX_TOKENS = 2048


# ─── flags ───────────────────────────────────────────────────────────────────


def image_ocr_enabled() -> bool:
    """Master kill switch for image OCR (env > UI setting > default)."""
    from core.runtime_settings import get_bool_setting

    return bool(get_bool_setting("ATOM_IMAGE_OCR_ENABLED", True))


def vision_ocr_enabled() -> bool:
    """Allow the paid vision-LLM fallback when no local engine is available."""
    from core.runtime_settings import get_bool_setting

    return bool(get_bool_setting("ATOM_IMAGE_OCR_VISION_ENABLED", True))


def tesseract_command() -> Optional[str]:
    """Path to the tesseract binary, or None when no local engine exists."""
    explicit = (os.getenv("ATOM_IMAGE_OCR_TESSERACT_CMD") or "").strip()
    if explicit:
        return explicit
    return shutil.which("tesseract")


def tesseract_languages() -> str:
    """Optional ``-l`` language list for Tesseract (empty = Tesseract default)."""
    return (os.getenv("ATOM_IMAGE_OCR_LANGS") or "").strip()


def tesseract_timeout_seconds() -> int:
    try:
        return max(1, int(os.getenv("ATOM_IMAGE_OCR_TIMEOUT_SECONDS", "")))
    except (TypeError, ValueError):
        return DEFAULT_TESSERACT_TIMEOUT_SECONDS


# ─── detection helpers ───────────────────────────────────────────────────────


def is_image_filename(filename: Optional[str]) -> bool:
    """True when the filename's extension is a raster image format."""
    ext = os.path.splitext(filename or "")[1].lstrip(".").lower()
    return ext in IMAGE_FILENAME_EXTENSIONS


def is_image_content_type(content_type: Optional[str]) -> bool:
    """True for ``image/*`` MIME types (case-insensitive)."""
    return (content_type or "").strip().lower().startswith("image/")


def _mime_for(filename: str, content_type: str = "") -> str:
    if content_type:
        return content_type
    ext = os.path.splitext(filename or "")[1].lstrip(".").lower()
    return _EXT_MIME.get(ext, "image/png")


def _image_dimensions(content: bytes) -> Optional[Tuple[int, int]]:
    """(width, height) without fully decoding the image; None when unknown."""
    try:
        from PIL import Image
    except ImportError:  # pragma: no cover — Pillow is a hard requirement
        return None
    try:
        with Image.open(io.BytesIO(content)) as img:
            return int(img.width), int(img.height)
    except Exception:  # noqa: BLE001 — undecodable bytes are simply unknown
        return None


def is_likely_signature_or_logo(content: bytes, filename: str = "") -> bool:
    """True when an inline image looks like a signature block, logo or spacer.

    Best-effort by design: a false negative costs one OCR pass, a false
    positive silently drops real content, so undecodable/unknown inputs are
    never rejected on dimensions alone.
    """
    name = (filename or "").lower()
    if any(token in name for token in _SIGNATURE_FILENAME_TOKENS):
        return True

    dimensions = _image_dimensions(content)
    if dimensions is None:
        return False
    width, height = dimensions
    if width <= 0 or height <= 0:
        return False
    if width < _MIN_DECORATIVE_DIMENSION or height < _MIN_DECORATIVE_DIMENSION:
        return True
    long_side, short_side = max(width, height), min(width, height)
    return (
        short_side <= _BANNER_MAX_SHORT_SIDE
        and long_side / short_side >= _BANNER_ASPECT_RATIO
    )


# ─── engines ─────────────────────────────────────────────────────────────────


def _safe_image_suffix(filename: str) -> str:
    ext = os.path.splitext(filename or "")[1].lstrip(".").lower()
    return f".{ext}" if ext in IMAGE_FILENAME_EXTENSIONS else ".png"


def _tesseract_text(content: bytes, filename: str) -> str:
    """Blocking Tesseract read — call via ``asyncio.to_thread``.

    Prefers the ``pytesseract`` wrapper (in-memory, multi-page aware) and
    falls back to the CLI so no Python dependency is required for a host that
    already ships the tesseract binary.
    """
    command = tesseract_command()
    if not command:
        return ""

    try:
        import pytesseract
        from PIL import Image

        pytesseract.pytesseract.tesseract_cmd = command
        with Image.open(io.BytesIO(content)) as img:
            return pytesseract.image_to_string(img) or ""
    except ImportError:
        pass
    except Exception as exc:  # noqa: BLE001 — fall through to the CLI
        logger.debug(f"pytesseract read failed, using CLI: {exc}")

    tmp_fd, tmp_path = tempfile.mkstemp(suffix=_safe_image_suffix(filename))
    try:
        with os.fdopen(tmp_fd, "wb") as handle:
            handle.write(content)
        args: List[str] = [command]
        languages = tesseract_languages()
        if languages:
            args.extend(["-l", languages])
        args.extend([tmp_path, "stdout"])
        proc = subprocess.run(
            args,
            capture_output=True,
            text=True,
            timeout=tesseract_timeout_seconds(),
        )
        if proc.returncode != 0:
            logger.debug(f"tesseract exited {proc.returncode}: {proc.stderr[:200]}")
            return ""
        return proc.stdout or ""
    finally:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass


async def _vision_ocr_text(content: bytes, filename: str, content_type: str) -> str:
    """Vision-LLM OCR fallback. Returns "" when no vision-capable model exists."""
    from core.llm_service import get_llm_service

    service = get_llm_service()
    if not service.is_available():
        return ""

    data_url = (
        f"data:{_mime_for(filename, content_type)};base64,"
        f"{base64.b64encode(content).decode('ascii')}"
    )
    response = await service.generate_completion(
        messages=[
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": _VISION_PROMPT},
                    {"type": "image_url", "image_url": {"url": data_url}},
                ],
            }
        ],
        model="auto",
        temperature=0.0,
        max_tokens=DEFAULT_VISION_MAX_TOKENS,
        task_type="image_comprehension",
    )
    if not isinstance(response, dict):
        return ""
    return str(response.get("content") or response.get("text") or "").strip()


# ─── public entry point ──────────────────────────────────────────────────────


def _result(
    success: bool,
    *,
    text: str = "",
    engine: Optional[str] = None,
    chars: int = 0,
    reason: Optional[str] = None,
) -> Dict[str, Any]:
    return {
        "success": success,
        "text": text,
        "engine": engine,
        "chars": chars,
        "reason": reason,
    }


async def ocr_image_bytes(
    content: bytes,
    filename: str = "",
    content_type: str = "",
    *,
    min_text_chars: int = 0,
) -> Dict[str, Any]:
    """Extract text from one image via the local → vision ladder.

    Args:
        content: Raw image bytes.
        filename: Original filename (extension drives format hints/routing).
        content_type: MIME type when known.
        min_text_chars: Drop results shorter than this. Inline email images
            pass a floor so signature blocks and logos that OCR to a word or
            two are not indexed; real file attachments pass 0.

    Returns:
        ``{"success", "text", "engine", "chars", "reason"}``. Never raises.
        ``reason`` is one of ``disabled``, ``empty_content``, ``no_engine``,
        ``empty_text``, ``decorative``, ``error``.
    """
    try:
        if not image_ocr_enabled():
            return _result(False, reason="disabled")
        if not content:
            return _result(False, reason="empty_content")

        text = ""
        engine: Optional[str] = None
        attempted: List[str] = []

        if tesseract_command():
            attempted.append("tesseract")
            try:
                candidate = await asyncio.to_thread(_tesseract_text, content, filename)
            except Exception as exc:  # noqa: BLE001 — try the next engine
                logger.debug(f"tesseract OCR failed for {filename}: {exc}")
                candidate = ""
            if (candidate or "").strip():
                text, engine = candidate.strip(), "tesseract"

        if not text and vision_ocr_enabled():
            attempted.append("vision")
            try:
                candidate = await _vision_ocr_text(content, filename, content_type)
            except Exception as exc:  # noqa: BLE001 — OCR is best-effort
                logger.debug(f"vision OCR failed for {filename}: {exc}")
                candidate = ""
            if (candidate or "").strip():
                text, engine = candidate.strip(), "vision"

        if not text:
            return _result(
                False, engine=engine, reason="empty_text" if attempted else "no_engine"
            )

        stripped = text.strip()
        if min_text_chars and len(stripped) < min_text_chars:
            return _result(
                False,
                engine=engine,
                chars=len(stripped),
                reason="decorative",
            )
        return _result(True, text=text, engine=engine, chars=len(stripped))
    except Exception as exc:  # noqa: BLE001 — ingestion contract: never raise
        logger.warning(f"Image OCR failed for {filename}: {exc}")
        return _result(False, reason="error")
