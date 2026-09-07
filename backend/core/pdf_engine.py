"""Deterministic PDF operations for the PDF canvas (bytes in → bytes out).

Every mutation the PDF canvas supports is a pure function here so both the
user's save button and (later) agent tools flow through ONE engine — the
audit trail can replay any version byte-for-byte. pypdf does the parsing/
assembly work (already a dependency, BSD-licensed); reportlab renders the
blank starter page (also already a dependency, used by apar_engine).

Kept free of DB/WS/session concerns by design — unit-testable without any
app context.
"""

from __future__ import annotations

import io
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from pypdf import PdfReader, PdfWriter
from pypdf.generic import DecodedStreamObject, NameObject
from reportlab.pdfgen import canvas as rl_canvas

logger = logging.getLogger(__name__)

VALID_ROTATIONS = (0, 90, 180, 270)


class PdfEngineError(ValueError):
    """Raised for invalid input (corrupt PDF, out-of-range page, bad rotation).

    Routes map this to 4xx; anything unexpected bubbles as 500.
    """


def blank_pdf(title: str = "") -> bytes:
    """A one-page blank A4/Letter PDF to start a canvas from (reportlab)."""
    from reportlab.pdfgen import canvas as rl_canvas

    buf = io.BytesIO()
    c = rl_canvas.Canvas(buf, pagesize=(612, 792))  # US Letter, matches most business docs
    if title:
        c.setFont("Helvetica", 14)
        c.drawString(72, 720, title[:80])
    c.showPage()
    c.save()
    return buf.getvalue()


def load_info(data: bytes) -> Dict[str, Any]:
    """Structural info for validation + the canvas header.

    Raises PdfEngineError on anything pypdf cannot open — uploads of corrupt
    or encrypted files fail at create time, never mid-lifecycle.
    """
    try:
        reader = _reader(data)
        pages = []
        for p in reader.pages:
            box = p.mediabox
            w, h = float(box.width), float(box.height)
            # Report the EFFECTIVE display size: a 90/270 /Rotate swaps what
            # the viewer (and our canvas UI) actually renders.
            if int(getattr(p, "rotation", 0) or 0) % 180 == 90:
                w, h = h, w
            pages.append({"width": round(w, 2), "height": round(h, 2)})
        return {"page_count": len(pages), "pages": pages}
    except PdfEngineError:
        raise
    except Exception as e:
        raise PdfEngineError(f"invalid or unreadable PDF: {e}") from e


def build_pages(data: bytes, page_specs: List[Dict[str, int]]) -> bytes:
    """Materialize a new PDF from an explicit page map — the single entry
    point for reorder + delete + rotate (delete = index absent from specs).

    page_specs: [{"src_index": int, "rotation": 0|90|180|270}, ...]
    Rotations are ABSOLUTE (clockwise degrees vs the source page), making the
    op idempotent and replayable from the audit trail: the same spec list on
    the same base bytes always yields the same result.
    """
    if not page_specs:
        raise PdfEngineError("page map would delete every page — keep at least one")
    from pypdf import PdfWriter

    reader = _reader(data)
    count = len(reader.pages)
    seen: set = set()
    writer = PdfWriter()
    for spec in page_specs:
        src = spec.get("src_index")
        rotation = spec.get("rotation", 0)
        if not isinstance(src, int) or src < 0 or src >= count:
            raise PdfEngineError(f"page index {src!r} out of range (document has {count} pages)")
        if src in seen:
            raise PdfEngineError(f"page {src} appears twice in the page map")
        if rotation not in VALID_ROTATIONS:
            raise PdfEngineError(f"rotation must be one of {VALID_ROTATIONS}, got {rotation!r}")
        seen.add(src)
        page = reader.pages[src]
        # /Rotate is cumulative in pypdf (rotate() adds); subtract the page's
        # current rotation so the spec's value stays absolute.
        current = int(getattr(page, "rotation", 0) or 0) % 360
        delta = (rotation - current) % 360
        if delta:
            page.rotate(delta)
        writer.add_page(page)
    return _write(writer)


def append_pdf(base: bytes, extra: bytes, max_result_pages: int = 500) -> bytes:
    """Concatenate two PDFs (merge-in). The source is appended whole; page-level
    arrangement happens through build_pages afterwards."""
    base_reader = _reader(base)
    extra_reader = _reader(extra)
    total = len(base_reader.pages) + len(extra_reader.pages)
    if total > max_result_pages:
        raise PdfEngineError(f"merge would exceed the {max_result_pages}-page canvas cap ({total} pages)")
    from pypdf import PdfWriter

    writer = PdfWriter()
    writer.append(base_reader)
    writer.append(extra_reader)
    return _write(writer)


def extract_text(data: bytes, max_pages: int = 50) -> List[Dict[str, Any]]:
    """Per-page text for the reading pane / (later) agent read-back. A page
    with no text layer (scan) yields "" — OCR arrives with Docling in P3."""
    reader = _reader(data)
    pages = []
    for i, page in enumerate(reader.pages):
        if i >= max_pages:
            break
        try:
            text = page.extract_text() or ""
        except Exception as e:  # a single pathological page must not kill the read
            logger.debug(f"Text extraction failed on page {i}: {e}")
            text = ""
        pages.append({"page": i, "text": text[:20000]})
    return pages


def _reader(data: bytes):
    from pypdf import PdfReader

    try:
        reader = PdfReader(io.BytesIO(data))
        if reader.is_encrypted:
            # No password source exists in the canvas flow — treat like corrupt.
            raise PdfEngineError("encrypted PDFs are not supported")
        if len(reader.pages) == 0:
            raise PdfEngineError("PDF has no pages")
        return reader
    except PdfEngineError:
        raise
    except Exception as e:
        raise PdfEngineError(f"invalid or unreadable PDF: {e}") from e


def _write(writer) -> bytes:
    buf = io.BytesIO()
    writer.write(buf)
    return buf.getvalue()


# ── P3/P4: trust operations & generation ─────────────────────────────────
# Each op below follows the same contract as build_pages: deterministic
# bytes-in → bytes-out, unit-testable, no app context. Redaction is the one
# destructive op — it rewrites content streams (never just paints a box) and
# VERIFIES by re-extraction, failing loudly if the target survives.

_SANITIZE_META_KEYS = ("/Title", "/Author", "/Subject", "/Keywords", "/Producer", "/Creator")


def get_form_fields(data: bytes) -> Dict[str, Dict[str, Any]]:
    """AcroForm field inventory: {name: {type, value}} for the fill UI and
    agent read-back. Empty dict when the PDF has no form."""
    reader = _reader(data)
    fields = reader.get_fields() or {}
    out: Dict[str, Dict[str, Any]] = {}
    for name, field in fields.items():
        try:
            out[name] = {
                "type": str(field.get("/FT", "/Text")),
                "value": None if field.get("/V") is None else str(field.get("/V")),
            }
        except Exception:
            continue
    return out


def set_form_fields(data: bytes, values: Dict[str, Any]) -> bytes:
    """Set AcroForm field VALUES (fields stay interactive). Unknown field
    names are refused so a typo'd fill fails loudly instead of silently
    skipping."""
    reader = _reader(data)
    known = set((reader.get_fields() or {}).keys())
    unknown = [k for k in values if k not in known]
    if unknown:
        raise PdfEngineError(f"unknown form fields: {', '.join(sorted(unknown))}")
    writer = PdfWriter()
    writer.append(reader)
    for page in writer.pages:
        writer.update_page_form_field_values(page, values)
    return _write(writer)


def _collect_widget_rects(page, values: Dict[str, Any]) -> Dict[str, Any]:
    """Widget name → rect + current value (for the flatten overlay)."""
    widgets: Dict[str, Any] = {}
    for annot in page.get("/Annots") or []:
        try:
            obj = annot.get_object()
            if str(obj.get("/Subtype")) != "/Widget":
                continue
            name = str(obj.get("/T") or "")
            if not name:
                continue
            rect = [float(x) for x in obj.get("/Rect", (0, 0, 0, 0))]
            widgets[name] = {"rect": rect, "value": values.get(name)}
        except Exception:
            continue
    return widgets


def flatten_form(data: bytes) -> bytes:
    """Burn form field VALUES into page content and strip the interactive
    layer (AcroForm + widget annotations). Non-widget annotations survive.
    Cross-viewer-safe outbound output — the #1 AcroForm breakage is viewers
    dropping appearance streams."""
    reader = _reader(data)
    fields = {k: (str(v.get("/V")) if v.get("/V") is not None else "")
              for k, v in (reader.get_fields() or {}).items()}
    writer = PdfWriter()
    writer.append(reader)

    for page in writer.pages:
        widgets = _collect_widget_rects(page, fields)
        if widgets:
            buf = io.BytesIO()
            c = rl_canvas.Canvas(buf, pagesize=(612, 792))
            for name, info in widgets.items():
                rect = info["rect"]
                value = info["value"] or ""
                if not value:
                    continue
                x0, y0, x1, y1 = rect
                height = max(8, (y1 - y0) * 0.7)
                c.setFont("Helvetica", height)
                c.drawString(x0 + 2, y0 + (y1 - y0 - height) / 2 + 1, value[:120])
            c.showPage()
            c.save()
            page.merge_page(PdfReader(io.BytesIO(buf.getvalue())).pages[0])
        if "/Annots" in page:
            # keep non-widget annotations (comments/highlights), drop widgets
            kept = [a for a in page["/Annots"]
                    if str(a.get_object().get("/Subtype")) != "/Widget"]
            if kept:
                page[NameObject("/Annots")] = kept
            else:
                del page[NameObject("/Annots")]
    if "/AcroForm" in writer._root_object:
        del writer._root_object[NameObject("/AcroForm")]
    return _write(writer)


def annotate(data: bytes, items: List[Dict[str, Any]]) -> bytes:
    """Add real PDF annotations. items: [{page, kind: note|freetext|rect,
    rect: [x0, y0, x1, y1], text?}]. Coordinates are PDF space (origin
    bottom-left). Annotation OBJECTS — still selectable/editable, unlike a
    reportlab overlay."""
    from pypdf.annotations import FreeText, Rectangle, Text

    kind_map = {"note": Text, "freetext": FreeText, "rect": Rectangle}
    reader = _reader(data)
    writer = PdfWriter()
    writer.append(reader)
    for i, item in enumerate(items):
        page_no = item.get("page", 0)
        kind = item.get("kind", "note")
        cls = kind_map.get(kind)
        if cls is None:
            raise PdfEngineError(f"unknown annotation kind: {kind!r} (note|freetext|rect)")
        if page_no < 0 or page_no >= len(writer.pages):
            raise PdfEngineError(f"annotation page {page_no} out of range")
        rect = item.get("rect") or [72, 700, 300, 716]
        kwargs: Dict[str, Any] = {"rect": rect}
        if cls is Text:
            kwargs.update({"text": str(item.get("text", "")), "open": False})
        elif cls is FreeText:
            kwargs.update({"text": str(item.get("text", "")), "font": "Helvetica", "font_size": "10"})
        try:
            writer.add_annotation(page_number=page_no, annotation=cls(**kwargs))
        except Exception as e:
            raise PdfEngineError(f"annotation {i} failed: {e}") from e
    return _write(writer)


def redact(data: bytes, items: List[Dict[str, Any]]) -> Dict[str, Any]:
    """TRUE redaction: remove exact text occurrences from the page content
    streams (glyphs replaced with blanks — the text is GONE, not covered),
    paint an opaque black rect over the located position, strip metadata,
    and VERIFY by re-extraction. items: [{page, text}].

    Returns {bytes, removed: [...], failed: [...]}. A target that can't be
    located in the content stream (e.g. split across kerning ops) lands in
    `failed` — the caller refuses the save rather than shipping a fake
    redaction. This is the rule that separates redaction from a black box.
    """
    reader = _reader(data)
    page_count = len(reader.pages)
    removed: List[Dict[str, Any]] = []
    failed: List[Dict[str, Any]] = []
    overlays: Dict[int, List[Dict[str, Any]]] = {}

    # pass 1 — locate positions + rewrite content streams
    for item in items:
        page_no = item.get("page", 0)
        target = str(item.get("text") or "")
        if not target:
            continue
        if page_no < 0 or page_no >= page_count:
            raise PdfEngineError(f"redaction page {page_no} out of range")

        page = reader.pages[page_no]
        spots: List[Dict[str, Any]] = []

        def visitor(text, cm, tm, font_dict, font_size, _target=target, _spots=spots):
            if _target in (text or ""):
                _spots.append({"x": float(tm[4]), "y": float(tm[5]),
                               "size": float(font_size or 10), "chunk": text})

        try:
            page.extract_text(visitor_text=visitor)
        except Exception as e:
            logger.debug(f"redact locator failed on page {page_no}: {e}")

        stream = page.get_contents()
        raw = stream.get_data() if stream is not None else b""
        needle = target.encode("latin-1", "replace")
        replaced = raw.count(needle)
        if replaced:
            new_stream = DecodedStreamObject()
            new_stream.set_data(raw.replace(needle, b" " * len(needle)))
            new_stream.update({NameObject("/Length"): len(raw)})
            page.replace_contents(new_stream)

        if replaced or spots:
            first = spots[0] if spots else None
            overlays.setdefault(page_no, []).append({
                "text": target,
                "x": (first or {}).get("x", 0),
                "y": (first or {}).get("y", 0),
                "size": (first or {}).get("size", 10),
            })
            removed.append({"page": page_no, "text": target, "occurrences": max(replaced, len(spots))})
        else:
            failed.append({"page": page_no, "text": target})

    # pass 2 — opaque rects over the located spots
    for page_no, rects in overlays.items():
        buf = io.BytesIO()
        c = rl_canvas.Canvas(buf, pagesize=(612, 792))
        c.setFillColorRGB(0, 0, 0)
        for r in rects:
            width = max(len(r["text"]) * r["size"] * 0.55 + 4, 12)
            c.rect(r["x"] - 2, r["y"] - 3, width, r["size"] + 5, fill=1, stroke=0)
        c.showPage()
        c.save()
        reader.pages[page_no].merge_page(PdfReader(io.BytesIO(buf.getvalue())).pages[0])

    writer = PdfWriter()
    writer.append(reader)
    writer.add_metadata({})  # sanitize: metadata often outlives its welcome
    out = _write(writer)

    # pass 3 — VERIFY by re-extraction; a surviving target is a hard failure
    verify_reader = _reader(out)
    for item in items:
        page_no = item.get("page", 0)
        target = str(item.get("text") or "")
        if not target or any(f["page"] == page_no and f["text"] == target for f in failed):
            continue
        try:
            page_text = verify_reader.pages[page_no].extract_text() or ""
        except Exception:
            page_text = ""
        if target in page_text:
            raise PdfEngineError(
                f"redaction verification FAILED: {target[:40]!r} still extractable on page {page_no}"
            )

    return {"bytes": out, "removed": removed, "failed": failed}


def stamp_signature(data: bytes, page_no: int, signature_lines: List[str],
                    rect: List[float], label: str = "") -> bytes:
    """Internal signing: stamp the signer's signature (TEXT lines — the
    composer's SignatureEditor value is styled HTML; its visible text lands
    here) at `rect` [x0, y0, x1, y1] in a script-style face, plus an
    attribution line beneath. Visual/approval stamp — cryptographic
    signatures are the DocuSign envelope path's job."""
    reader = _reader(data)
    if page_no < 0 or page_no >= len(reader.pages):
        raise PdfEngineError(f"signature page {page_no} out of range")
    buf = io.BytesIO()
    c = rl_canvas.Canvas(buf, pagesize=(612, 792))
    x0, y0, x1, y1 = rect
    c.setFont("Times-Italic", max(12, min(28, (y1 - y0) / max(1, len(signature_lines)))))
    ly = y1 - 14
    for line in (signature_lines or [""] )[:5]:
        if line.strip():
            c.drawString(x0, ly, line.strip()[:80])
        ly -= 16
    if label:
        c.setFont("Helvetica", 7.5)
        c.drawString(x0, y0 - 2, label[:160])
    c.showPage()
    c.save()
    reader.pages[page_no].merge_page(PdfReader(io.BytesIO(buf.getvalue())).pages[0])
    writer = PdfWriter()
    writer.append(reader)
    return _write(writer)


def generate_document(template: str, doc: Dict[str, Any], title: str = "") -> bytes:
    """Render a business document from structured data — quote/invoice/
    letter templates (the Zoho-adjacent outbound path). Deterministic:
    same data in, same bytes out."""
    if template not in ("quote", "invoice", "letter"):
        raise PdfEngineError(f"unknown template: {template!r} (quote|invoice|letter)")

    buf = io.BytesIO()
    c = rl_canvas.Canvas(buf, pagesize=(612, 792))
    width, _ = 612, 792
    y = 750

    c.setFont("Helvetica-Bold", 18)
    c.drawString(72, y, (title or doc.get("title") or template.title())[:60])
    y -= 28

    c.setFont("Helvetica", 10)
    for block, keys in (("From", ("company", "from_email")),
                        ("Bill To", ("customer", "customer_email"))):
        label = doc.get(keys[0])
        if label:
            c.setFont("Helvetica-Bold", 10)
            c.drawString(72, y, f"{block}:")
            c.setFont("Helvetica", 10)
            c.drawString(120, y, str(label)[:70])
            y -= 14
            contact = doc.get(keys[1])
            if contact:
                c.drawString(120, y, str(contact)[:70])
                y -= 14
    y -= 10

    items = doc.get("items") or []
    if items:
        c.setFont("Helvetica-Bold", 10)
        c.drawString(72, y, "Description")
        c.drawRightString(540, y, "Amount")
        y -= 6
        c.line(72, y, 540, y)
        y -= 14
        c.setFont("Helvetica", 10)
        total = 0.0
        for item in items[:40]:
            desc = str(item.get("description", ""))[:60]
            amount = float(item.get("amount", 0) or 0)
            total += amount
            c.drawString(80, y, desc)
            c.drawRightString(540, y, f"{amount:,.2f}")
            y -= 14
        c.line(380, y + 4, 540, y + 4)
        y -= 14
        c.setFont("Helvetica-Bold", 11)
        c.drawString(380, y, "Total")
        c.drawRightString(540, y, f"{total:,.2f}")
        y -= 20

    if template == "letter" or doc.get("body"):
        c.setFont("Helvetica", 10)
        for line in str(doc.get("body", ""))[:4000].split("\n")[:40]:
            c.drawString(72, y, line[:95])
            y -= 13

    c.setFont("Helvetica", 7)
    c.drawString(72, 40, f"Generated by ATOM · {template} · {datetime.now(timezone.utc).isoformat()}")
    c.showPage()
    c.save()
    return buf.getvalue()


def sanitize(data: bytes) -> bytes:
    """Archival export: rebuild (drops attachments/embedded JS carried in
    the source), scrub metadata, and report what would betray the document.
    NOT certified PDF/A — a validated PDF/A converter is a Phase-4-later
    decision (requires embedded ICC profiles); this is the honest
    'clean, self-contained copy' step."""
    reader = _reader(data)
    writer = PdfWriter()
    writer.append(reader)
    meta = {k: "" for k in _SANITIZE_META_KEYS}
    writer.add_metadata(meta)
    return _write(writer)


def security_survey(data: bytes) -> Dict[str, Any]:
    """Post-redaction/archival check: what does the file still carry?"""
    reader = _reader(data)
    has_js = False
    has_attachments = False
    try:
        root = reader.trailer["/Root"]
        names = root.get_object().get("/Names", {})
        if names and names.get_object().get("/JavaScript"):
            has_js = True
        if names and names.get_object().get("/EmbeddedFiles"):
            has_attachments = True
    except Exception:
        pass
    return {
        "javascript": has_js,
        "attachments": has_attachments,
        "encrypted": bool(reader.is_encrypted),
        "metadata_keys": sorted((reader.metadata or {}).keys()),
    }
