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

Text-like attachments (txt/csv/…) are NOT routed here: the communication
pipeline already folds them into the comms record content, and a second
copy in the documents index would double-index the same text.
"""

import logging
import os
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

# Binary formats worth a Docling text layer (mirrors
# core.docling_processor.SUPPORTED_EXTENSIONS). Text-like formats are
# deliberately absent — see module docstring.
_BINARY_ATTACHMENT_EXTENSIONS = {
    "pdf", "doc", "docx", "ppt", "pptx", "xls", "xlsx",
    "png", "jpg", "jpeg", "tiff", "tif", "bmp",
    "html", "htm", "asciidoc",
}

# Budget defaults: the poller path must never let one bulky mailbox turn a
# 15s poll into minutes of Docling work.
DEFAULT_MAX_ATTACHMENT_MB = 10


def _env_int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)))
    except (TypeError, ValueError):
        return default


def attachment_ingestible(filename: str) -> bool:
    """True when the filename's extension is a binary format we text-extract."""
    ext = os.path.splitext(filename or "")[1].lstrip(".").lower()
    return bool(ext) and ext in _BINARY_ATTACHMENT_EXTENSIONS


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
) -> Dict[str, Any]:
    """Index one email attachment's text into the documents memory index.

    Returns a small status dict:
      {"status": "indexed"|"skipped"|"unsupported"|"error",
       "doc_id": str|None, "chars": int, "cached": bool}

    Never raises — callers treat failures as "attachment stays metadata-only".
    """
    try:
        if not attachment_ingestible(filename):
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
