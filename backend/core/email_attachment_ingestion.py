"""Shared email-attachment ingestion: provider bytes → documents memory index.

One entry point for every channel that has attachment bytes — the live
poller (attachments expanded inline), the email canvas "Add to memory"
action, and the agent ingest tool — so all of them land identical rows:

- doc_id = ext_{sha1(provider:message_id:attachment_id)} — source-scoped and
  stable, so re-ingests upsert-skip via source_content_hash instead of
  duplicating.
- metadata carries email provenance (subject/from/received_at/source_url)
  plus source_type="email_attachment", so hybrid-recall spotlight rows can
  be attributed back to the email they arrived in.

Besides the always-on poller/webhook channels, the same module also owns the
ON-DEMAND fetch path (:func:`ingest_message_attachments_on_demand`): given a
mailbox message id, it asks the connected provider (Outlook Graph / Gmail)
for the attachment metadata and bytes, then routes each one through
``ingest_email_attachment_bytes``. That is what lets an agent add content to
memory when the poller never reached the message (the Graph webhook path
fetches no attachment bytes) or when the message predates the current
ingestion pipeline — instead of reporting the content as inaccessible.

Text-like attachments (txt/csv/…) are NOT routed here: the communication
pipeline already folds them into the comms record content, and a second
copy in the documents index would double-index the same text.

Images (png/jpg/tiff/…) ARE routed here: they are OCR'd via
``core.image_ocr`` (Docling → Tesseract → vision LLM), so a scanned
invoice or pasted screenshot becomes searchable instead of being dropped as
``no_text``. An image with NO text layer (product photo, machine picture) gets
a vision DESCRIPTION on explicit on-demand pulls (``describe_images``), so it
still lands in memory; the poller deliberately stays OCR-only. Inline body
images are handled too, but signature blocks, logos and tracking pixels are
filtered first — see ``inline`` below.
"""

import logging
import os
from typing import Any, Dict, List, Optional

from core.image_ocr import (
    is_image_content_type,
    is_image_filename,
    is_likely_signature_or_logo,
)

logger = logging.getLogger(__name__)

# Binary formats worth a Docling text layer (mirrors
# core.docling_processor.SUPPORTED_EXTENSIONS). Text-like formats are
# deliberately absent — see module docstring.
_BINARY_ATTACHMENT_EXTENSIONS = {
    "pdf", "doc", "docx", "ppt", "pptx", "xls", "xlsx",
    "png", "jpg", "jpeg", "tiff", "tif", "bmp",
    "html", "htm", "asciidoc",
}

# MIME fallback for attachments that arrive WITHOUT a filename (Gmail/Graph
# inline parts sometimes omit it). Matched by prefix; ``image/`` covers every
# raster format in the extension set above.
_BINARY_CONTENT_TYPES = (
    "application/pdf",
    "application/msword",
    "application/vnd.openxmlformats-officedocument",
    "application/vnd.ms-excel",
    "application/vnd.ms-powerpoint",
    "application/vnd.oasis.opendocument",
    "application/rtf",
    "text/html",
    "image/",
)

# Budget defaults: the poller path must never let one bulky mailbox turn a
# 15s poll into minutes of Docling work.
DEFAULT_MAX_ATTACHMENT_MB = 10

# Inline images below this OCR length are treated as signature/logo noise.
DEFAULT_INLINE_IMAGE_MIN_TEXT_CHARS = 16


def _env_int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)))
    except (TypeError, ValueError):
        return default


def attachment_ingestible(filename: str, content_type: str = "") -> bool:
    """True when the attachment is a binary format we text-extract.

    The extension decides when present; otherwise the MIME type does, so
    attachments that arrive without a filename (Gmail inline parts) are not
    silently ignored.
    """
    ext = os.path.splitext(filename or "")[1].lstrip(".").lower()
    if ext:
        return ext in _BINARY_ATTACHMENT_EXTENSIONS
    ctype = (content_type or "").strip().lower()
    return bool(ctype) and ctype.startswith(_BINARY_CONTENT_TYPES)


def inline_image_ocr_enabled() -> bool:
    """OCR images embedded inline in an email body (env > UI setting)."""
    from core.runtime_settings import get_bool_setting

    return bool(get_bool_setting("ATOM_EMAIL_INLINE_IMAGE_OCR", True))


def inline_image_min_text_chars() -> int:
    """OCR-text floor below which an inline image counts as decorative."""
    from core.runtime_settings import get_int_setting

    return max(
        0,
        int(
            get_int_setting(
                "ATOM_EMAIL_INLINE_IMAGE_MIN_TEXT_CHARS",
                DEFAULT_INLINE_IMAGE_MIN_TEXT_CHARS,
            )
        ),
    )


def max_ingest_bytes() -> int:
    """Per-attachment byte cap for memory indexing (env-overridable)."""
    return _env_int("MAX_EMAIL_ATTACHMENT_INGEST_MB", DEFAULT_MAX_ATTACHMENT_MB) * 1024 * 1024


def max_attachments_per_message() -> int:
    """Per-message cap on binary attachments indexed in one ingestion pass."""
    return _env_int("MAX_BINARY_ATTACHMENTS_INDEXED_PER_MESSAGE", 3)


async def ingest_email_attachment_bytes(
    *,
    provider: str,
    message_id: str,
    attachment_id: str,
    filename: str,
    content: bytes,
    content_type: str = "",
    size: int = 0,
    user_id: str = "system",
    workspace_id: Optional[str] = None,
    email_subject: str = "",
    email_from: str = "",
    email_received_at: str = "",
    source_url: str = "",
    inline: bool = False,
    describe_images: bool = False,
) -> Dict[str, Any]:
    """Index one email attachment's text into the documents memory index.

    Returns a small status dict:
      {"status": "indexed"|"skipped"|"unsupported"|"error",
       "doc_id": str|None, "chars": int, "cached": bool}

    ``inline`` marks an image embedded in the email body rather than a real
    file attachment. Inline images are OCR'd too (screenshots and receipts
    are frequently pasted rather than attached) but pass a minimum-text floor
    so signature blocks, logos and tracking pixels never enter memory. Real
    attachments keep every character.

    ``describe_images``: when an image has NO text layer, ask the vision model
    to describe it so it still becomes searchable (a product photo has no OCR
    text). The explicit on-demand pull sets this; the automatic poller does
    not, keeping bulk ingestion cheap.

    Never raises — callers treat failures as "attachment stays metadata-only".
    """
    try:
        if inline:
            if not inline_image_ocr_enabled():
                return {
                    "status": "skipped", "doc_id": None, "chars": 0,
                    "reason": "inline_disabled",
                }
            if (
                is_image_filename(filename) or is_image_content_type(content_type)
            ) and is_likely_signature_or_logo(content, filename):
                return {
                    "status": "skipped", "doc_id": None, "chars": 0,
                    "reason": "signature_or_decorative",
                }

        if not attachment_ingestible(filename, content_type):
            return {"status": "unsupported", "doc_id": None, "chars": 0}

        if len(content) > max_ingest_bytes():
            return {
                "status": "skipped",
                "doc_id": None,
                "chars": 0,
                "reason": "too_large",
            }

        from core.auto_document_ingestion import AutoDocumentIngestionService

        service = AutoDocumentIngestionService(workspace_id=workspace_id or "default")
        result = await service.process_file_bytes(
            content=content,
            file_name=filename,
            source=provider,
            user_id=user_id or "system",
            workspace_id=workspace_id,
            external_id=f"{message_id}:{attachment_id}",
            image_min_chars=inline_image_min_text_chars() if inline else 0,
            image_describe=bool(describe_images),
            extra_metadata={
                "source_type": "email_attachment",
                "email_message_id": message_id,
                "email_attachment_id": attachment_id,
                "email_subject": email_subject,
                "email_from": email_from,
                "email_received_at": email_received_at,
                "source_url": source_url,
                "content_type": content_type,
            },
        )

        status = result.get("status")
        if status == "ingested":
            return {
                "status": "indexed",
                "doc_id": result.get("doc_id"),
                "chars": result.get("chars_ingested", 0),
                # Extracted (post-redaction) text, so on-demand callers can
                # return the content immediately instead of re-parsing bytes
                # (a second OCR pass would double the vision-LLM cost).
                "text_preview": result.get("text_preview") or "",
            }
        if status == "skipped" and result.get("reason") == "unchanged":
            # Already indexed with identical content — report as indexed so
            # callers can stamp the attachment record as done.
            return {
                "status": "indexed",
                "doc_id": result.get("doc_id"),
                "chars": 0,
                "cached": True,
            }
        return {
            "status": "skipped" if status == "skipped" else "error",
            "doc_id": result.get("doc_id"),
            "chars": 0,
            "reason": result.get("reason", status),
        }
    except Exception as e:  # noqa: BLE001 — ingestion is best-effort by contract
        logger.warning(
            f"Attachment ingestion failed for {provider}:{message_id}:{attachment_id} "
            f"({filename}): {e}"
        )
        return {"status": "error", "doc_id": None, "chars": 0, "reason": str(e)}


# ─── on-demand provider fetch ("ingest from the integration") ────────────────

# Provider aliases for the on-demand path. The attachment fetch itself works
# for any provider with a download_attachment method; the pipeline-level
# on-demand email ingest (body + attachments) supports outlook/gmail, so the
# alias set matches that shared vocabulary.
_ON_DEMAND_PROVIDER_ALIASES = {
    "outlook": "outlook",
    "microsoft": "outlook",
    "microsoft_graph": "outlook",
    "msgraph": "outlook",
    "graph": "outlook",
    "office365": "outlook",
    "gmail": "gmail",
    "google": "gmail",
    "googlemail": "gmail",
}

# Deterministic preference when the caller names no provider and several
# mailboxes are connected.
_PROVIDER_PREFERENCE = ("outlook", "gmail")

DEFAULT_MAX_ON_DEMAND_ATTACHMENTS = 5


def normalize_mail_provider(platform: str) -> str:
    """Map a loose provider string to the canonical ``outlook``/``gmail``.

    Returns "" for unknown/empty input so callers can fall back to connected-
    provider inference instead of guessing.
    """
    key = (platform or "").strip().lower().replace("-", "_").replace(" ", "_")
    return _ON_DEMAND_PROVIDER_ALIASES.get(key, "")


def max_on_demand_attachments() -> int:
    """Per-call cap on attachments fetched from the provider."""
    return max(
        1,
        _env_int(
            "MAX_ON_DEMAND_ATTACHMENTS_FETCHED", DEFAULT_MAX_ON_DEMAND_ATTACHMENTS
        ),
    )


def _active_mail_providers(user_id: str) -> List[str]:
    """Connected mail providers for the user, in deterministic preference
    order. [] when the account has no connected mailbox (or on any lookup
    failure) — the caller then reports the honest "no mailbox connected"
    error instead of guessing a provider."""
    found = set()
    try:
        from core.database import get_db_session
        from core.models import IntegrationToken

        with get_db_session() as db:
            rows = (
                db.query(IntegrationToken.provider)
                .filter(
                    IntegrationToken.user_id == user_id,
                    IntegrationToken.status == "active",
                )
                .all()
            )
        for (provider,) in rows:
            normalized = normalize_mail_provider(str(provider))
            if normalized:
                found.add(normalized)
    except Exception as e:  # noqa: BLE001 — inference is best-effort
        logger.debug(f"mail provider lookup failed for {user_id}: {e}")
    return [p for p in _PROVIDER_PREFERENCE if p in found] + sorted(
        found.difference(_PROVIDER_PREFERENCE)
    )


async def _provider_attachment_metadata(
    provider: str, user_id: str, message_id: str
) -> List[Dict[str, Any]]:
    """Normalized attachment metadata (id/name/size/contentType) or []."""
    try:
        if provider == "outlook":
            from integrations.outlook_service import OutlookService

            return await OutlookService().get_attachment_metadata(user_id, message_id)
        from integrations.gmail_service import GmailService

        return await GmailService().get_attachment_metadata(user_id, message_id)
    except Exception as e:  # noqa: BLE001 — provider I/O is best-effort
        logger.warning(
            f"Attachment metadata fetch failed for {provider}:{message_id}: {e}"
        )
        return []


async def _provider_download_attachment(
    provider: str, user_id: str, message_id: str, attachment_id: str
) -> Optional[bytes]:
    """Raw attachment bytes from the provider, or None on any failure."""
    try:
        if provider == "outlook":
            from integrations.outlook_service import OutlookService

            return await OutlookService().download_attachment(
                user_id, message_id, attachment_id
            )
        from integrations.gmail_service import GmailService

        return await GmailService().download_attachment(
            user_id, message_id, attachment_id
        )
    except Exception as e:  # noqa: BLE001 — provider I/O is best-effort
        logger.warning(
            f"Attachment download failed for {provider}:{message_id}:{attachment_id}: {e}"
        )
        return None


def _probe_doc_id(provider: str, message_id: str, attachment_id: str) -> str:
    """The doc id ``ingest_email_attachment_bytes`` will write for this
    attachment (``ext_sha1(source:external_id)``), so an already-ingested
    result can still name the row it refers to."""
    import hashlib

    external_id = f"{message_id}:{attachment_id}"
    digest = hashlib.sha1(f"{provider}:{external_id}".encode("utf-8")).hexdigest()
    return f"ext_{digest[:24]}"


def _spotlight_preview(
    text: str, filename: str, sender: str = "", subject: str = ""
) -> str:
    """Wrap an attachment text preview in the untrusted-content delimiters.

    Attachment text is attacker-authored email content: it must reach the
    model as DATA, never as instructions.
    """
    from core.email_policy import spotlight_email_content

    header = subject or f"attachment: {filename}"
    return spotlight_email_content(text, sender=sender or None, subject=header)


async def ingest_message_attachments_on_demand(
    *,
    user_id: str,
    message_id: str,
    attachment_id: str = "",
    platform: str = "",
    filename_hint: str = "",
    workspace_id: Optional[str] = None,
    agent_id: Optional[str] = None,
    max_attachments: Optional[int] = None,
) -> Dict[str, Any]:
    """Fetch a mailbox message's attachment(s) from the connected provider and
    index their text into memory — the on-demand counterpart of the poller's
    automatic attachment ingestion.

    Use it when the content the user needs is not in memory: the Graph webhook
    path fetches messages WITHOUT attachment bytes, so binary attachments that
    arrived on that channel were never indexed, and mail predating the current
    pipeline is absent too. This is the "go get it from the integration"
    leg — never claim content is inaccessible before trying it.

    Idempotent by construction: an attachment whose document is already in
    memory is reported ``already_ingested`` without a provider download, and
    the shared ingestion write dedups on content hash, so a repeat ask is a
    truthful no-op.

    Args:
        user_id: Mailbox-owning user id (provider auth is scoped to them).
        message_id: Provider message id.
        attachment_id: Ingest only this attachment. Empty = every attachment
            on the message (bounded by ``max_attachments``).
        platform: ``outlook``/``gmail`` (aliases accepted). Empty = infer from
            the user's connected mailboxes.
        filename_hint: Label to use when the provider metadata is unavailable.
        workspace_id: Memory workspace (defaults to the ``default`` store).
        agent_id: Calling agent id (audit attribution only).
        max_attachments: Override the per-call fetch cap.

    Returns:
        ``{"success", "platform", "message_id", "attachments": [...],
        "ingested", "already_ingested", "skipped", "message"}`` — one entry
        per attachment with ``status``/``doc_id``/``chars`` and a spotlight-
        wrapped ``text`` preview for freshly indexed content. Never raises.
    """
    message_id = str(message_id or "").strip()
    if not message_id:
        return {
            "success": False,
            "error": "message_id is required",
            "message_id": "",
            "attachments": [],
        }

    requested = normalize_mail_provider(platform)
    candidates = [requested] if requested else _active_mail_providers(user_id)
    if not candidates:
        return {
            "success": False,
            "error": (
                "No connected mailbox found for this user — connect Outlook or "
                "Gmail, or pass platform explicitly."
            ),
            "message_id": message_id,
            "attachments": [],
        }

    wanted = str(attachment_id or "").strip()
    provider = ""
    metadata: List[Dict[str, Any]] = []
    for candidate in candidates:
        meta = await _provider_attachment_metadata(candidate, user_id, message_id)
        if meta or (wanted and candidate == requested):
            provider, metadata = candidate, meta
            break
    if not provider:
        # Nothing matched on any candidate: report the first candidate as the
        # attempted provider so the caller can see WHAT was tried.
        return {
            "success": False,
            "error": "message_not_found_or_has_no_attachments",
            "platform": candidates[0],
            "message_id": message_id,
            "attachments": [],
        }

    selected: List[Dict[str, Any]] = []
    for att in metadata:
        att_id = str(att.get("id") or "")
        if not att_id:
            continue
        if wanted and att_id != wanted:
            continue
        selected.append(att)
    if wanted and not selected:
        # Explicit id absent from the metadata listing (Graph sometimes omits
        # reference attachments): still attempt the direct download — the id
        # is authoritative and the provider can resolve it.
        selected = [
            {
                "id": wanted,
                "name": filename_hint or "attachment",
                "size": 0,
                "contentType": "",
            }
        ]
    if not selected:
        return {
            "success": False,
            "error": "no_attachments_on_message",
            "platform": provider,
            "message_id": message_id,
            "attachments": [],
        }

    cap = max_on_demand_attachments() if max_attachments is None else max(1, int(max_attachments))
    selected = selected[:cap]

    service = None
    already: set = set()
    try:
        from core.auto_document_ingestion import AutoDocumentIngestionService

        service = AutoDocumentIngestionService(workspace_id=workspace_id or "default")
        external_ids = [
            f"{message_id}:{str(att.get('id'))}" for att in selected
        ]
        already = set(
            await service.ingested_external_ids(provider, external_ids) or []
        )
    except Exception as e:  # noqa: BLE001 — probe is best-effort
        logger.debug(f"already-ingested probe skipped: {e}")

    results: List[Dict[str, Any]] = []
    for att in selected:
        att_id = str(att.get("id") or "")
        filename = (
            str(att.get("name") or "").strip() or filename_hint or "attachment"
        )
        content_type = str(
            att.get("contentType") or att.get("content_type") or ""
        )
        external_id = f"{message_id}:{att_id}"

        if external_id in already:
            results.append(
                {
                    "attachment_id": att_id,
                    "filename": filename,
                    "content_type": content_type,
                    "status": "already_ingested",
                    "doc_id": _probe_doc_id(provider, message_id, att_id),
                    "chars": 0,
                }
            )
            continue

        data = await _provider_download_attachment(provider, user_id, message_id, att_id)
        if not data:
            results.append(
                {
                    "attachment_id": att_id,
                    "filename": filename,
                    "content_type": content_type,
                    "status": "error",
                    "reason": "download_failed",
                    "doc_id": None,
                    "chars": 0,
                }
            )
            continue

        if not attachment_ingestible(filename, content_type):
            results.append(
                {
                    "attachment_id": att_id,
                    "filename": filename,
                    "content_type": content_type,
                    "status": "unsupported",
                    "reason": "unsupported_format",
                    "doc_id": None,
                    "chars": 0,
                }
            )
            continue

        ingest = await ingest_email_attachment_bytes(
            provider=provider,
            message_id=message_id,
            attachment_id=att_id,
            filename=filename,
            content=bytes(data),
            content_type=content_type,
            size=att.get("size") or len(data),
            user_id=user_id,
            workspace_id=workspace_id,
            # EXPLICIT pull: the caller named this attachment, so the inline
            # decorative floor does not apply — the shared module still
            # ocr's it and dedups the write.
            inline=False,
            # Textless images (product photos) get a vision DESCRIPTION here:
            # this is the one path where "the user wants THIS image's content"
            # is explicit, so paying for a description is justified — and it is
            # what turns "the image isn't in any data I can access" into usable
            # memory. The automatic poller deliberately stays OCR-only.
            describe_images=True,
        )
        status = str(ingest.get("status") or "error")
        entry: Dict[str, Any] = {
            "attachment_id": att_id,
            "filename": filename,
            "content_type": content_type,
            "status": status,
            "doc_id": ingest.get("doc_id"),
            "chars": ingest.get("chars") or 0,
        }
        if ingest.get("reason"):
            entry["reason"] = ingest.get("reason")
        preview = str(ingest.get("text_preview") or "").strip()
        if status == "indexed" and preview:
            entry["text"] = _spotlight_preview(preview, filename)
        results.append(entry)

    indexed = sum(1 for r in results if r["status"] == "indexed")
    already_count = sum(1 for r in results if r["status"] == "already_ingested")
    skipped = len(results) - indexed - already_count
    if indexed:
        message = f"Ingested {indexed} attachment(s) into memory"
    elif already_count:
        message = (
            f"{already_count} attachment(s) were already in memory — nothing to do"
        )
    else:
        message = "No attachment content could be added to memory"
    return {
        "success": indexed > 0 or already_count > 0,
        "platform": provider,
        "message_id": message_id,
        "attachments": results,
        "ingested": indexed,
        "already_ingested": already_count,
        "skipped": skipped,
        "message": message,
    }
