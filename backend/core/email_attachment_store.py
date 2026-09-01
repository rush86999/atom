"""Staged file store for outbound email-canvas attachments.

Received attachments stay mailbox-authoritative (Graph/Gmail is the durable
store; bytes are fetched on demand and never persisted). Outbound drafts are
different: the file has no mailbox home until send, so uploads are staged on
disk and deleted on send success, removal, or canvas delete.

Storage layout: {ATOM_EMAIL_ATTACHMENT_DIR}/{user_id}/{canvas_id}/{attachment_id}
Files are stored under the attachment id only — the display filename lives in
metadata, so a hostile filename can never traverse paths. Relative
ATOM_EMAIL_ATTACHMENT_DIR values are anchored to backend/ (the documented
launch dir; root-vs-backend launches caused divergent stores before — same
anchoring as core.lancedb_handler).
"""

import logging
import os
import shutil
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# Upload whitelist: documents/images/archives an email may carry. Mirrors the
# document-ingestion upload gate rather than accepting anything.
ALLOWED_UPLOAD_EXTENSIONS = {
    "pdf", "doc", "docx", "ppt", "pptx", "xls", "xlsx", "csv", "txt", "md",
    "rtf", "png", "jpg", "jpeg", "gif", "webp", "svg", "zip", "html", "json",
    "eml", "msg", "ics", "xml",
}

DEFAULT_MAX_UPLOAD_MB = 20
DEFAULT_MAX_CANVAS_STAGED_MB = 50
ORPHAN_SWEEP_HOURS = 72


def _backend_dir() -> Path:
    return Path(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _env_mb(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)))
    except (TypeError, ValueError):
        return default


def max_upload_bytes() -> int:
    return _env_mb("EMAIL_ATTACHMENT_MAX_UPLOAD_MB", DEFAULT_MAX_UPLOAD_MB) * 1024 * 1024


def max_canvas_staged_bytes() -> int:
    return _env_mb("EMAIL_ATTACHMENT_MAX_CANVAS_STAGED_MB", DEFAULT_MAX_CANVAS_STAGED_MB) * 1024 * 1024


def _staged_base() -> Path:
    raw = os.getenv("ATOM_EMAIL_ATTACHMENT_DIR", os.path.join("data", "email_attachments"))
    p = Path(raw)
    if not p.is_absolute():
        p = _backend_dir() / p
    return p


def upload_allowed(filename: str) -> bool:
    ext = os.path.splitext(filename or "")[1].lstrip(".").lower()
    return bool(ext) and ext in ALLOWED_UPLOAD_EXTENSIONS


def _canvas_dir(user_id: str, canvas_id: str) -> Path:
    return _staged_base() / str(user_id) / str(canvas_id)


def _attachment_path(user_id: str, canvas_id: str, attachment_id: str) -> Path:
    # attachment_id is generated here (staged_{hex}); the guard is defense in
    # depth against hand-crafted ids arriving through the API.
    safe = str(attachment_id)
    if not safe.startswith("staged_") or "/" in safe or "\\" in safe or ".." in safe:
        raise ValueError(f"invalid staged attachment id: {safe!r}")
    return _canvas_dir(user_id, canvas_id) / safe


def staged_bytes_used(user_id: str, canvas_id: str) -> int:
    total = 0
    d = _canvas_dir(user_id, canvas_id)
    if d.exists():
        for f in d.iterdir():
            try:
                if f.is_file():
                    total += f.stat().st_size
            except OSError:
                continue
    return total


def save_staged(
    user_id: str,
    canvas_id: str,
    filename: str,
    content: bytes,
    content_type: str = "",
) -> Dict[str, Any]:
    """Stage one upload and return its attachment record (plan schema D2).

    Raises ValueError on policy violations (extension/size caps) so callers
    can surface a 4xx instead of silently dropping the file.
    """
    if not upload_allowed(filename):
        raise ValueError(f"file type not allowed: {filename!r}")
    if len(content) > max_upload_bytes():
        raise ValueError(
            f"attachment exceeds the {max_upload_bytes() // (1024 * 1024)} MB upload cap"
        )
    if staged_bytes_used(user_id, canvas_id) + len(content) > max_canvas_staged_bytes():
        raise ValueError("canvas staged attachments exceed the per-canvas cap")

    attachment_id = f"staged_{uuid.uuid4().hex}"
    path = _attachment_path(user_id, canvas_id, attachment_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)

    return {
        "attachment_id": attachment_id,
        "message_id": None,
        "provider": "local",
        "filename": filename,
        "content_type": content_type or "application/octet-stream",
        "size": len(content),
        "is_inline": False,
        "origin": "staged",
        "ingestion": None,
        "added_by": {"actor": "user", "user_id": user_id, "agent_id": None},
        "created_at": datetime.now().isoformat(),
    }


def read_staged(user_id: str, canvas_id: str, attachment_id: str) -> Optional[bytes]:
    try:
        path = _attachment_path(user_id, canvas_id, attachment_id)
    except ValueError:
        return None
    try:
        return path.read_bytes()
    except OSError:
        return None


def delete_staged(user_id: str, canvas_id: str, attachment_id: str) -> bool:
    try:
        path = _attachment_path(user_id, canvas_id, attachment_id)
    except ValueError:
        return False
    try:
        path.unlink(missing_ok=True)
        return True
    except OSError as e:
        logger.warning(f"Failed to delete staged attachment {attachment_id}: {e}")
        return False


def delete_canvas_staged(user_id: str, canvas_id: str) -> None:
    """Drop every staged file for a canvas (canvas deleted / send cleanup)."""
    d = _canvas_dir(user_id, canvas_id)
    try:
        if d.exists():
            shutil.rmtree(d, ignore_errors=True)
    except OSError as e:
        logger.warning(f"Failed to clean staged attachments for canvas {canvas_id}: {e}")


def sweep_orphans(max_age_hours: int = ORPHAN_SWEEP_HOURS) -> int:
    """Remove staged files older than the window (send/delete paths normally
    clean these; this catches crashed sends and abandoned drafts)."""
    cutoff = datetime.now().timestamp() - max_age_hours * 3600
    removed = 0
    base = _staged_base()
    if not base.exists():
        return 0
    for f in base.rglob("*"):
        try:
            if f.is_file() and f.stat().st_mtime < cutoff:
                f.unlink(missing_ok=True)
                removed += 1
        except OSError:
            continue
    if removed:
        logger.info(f"Swept {removed} orphaned staged email attachments")
    return removed
