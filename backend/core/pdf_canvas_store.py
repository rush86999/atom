"""Content-addressed blob store for PDF canvas files.

Layout: {ATOM_PDF_CANVAS_DIR}/{user_id}/{canvas_id}/{sha256}.pdf
Every version's bytes are immutable and kept (the audit trail references
hashes — "which bytes went out with the email" must stay answerable), so
unlike the staged email-attachment store there is no sweep; canvas delete
removes the directory. Relative ATOM_PDF_CANVAS_DIR values are anchored to
backend/ (the documented launch dir; root-vs-backend launches caused
divergent stores before — same anchoring as email_attachment_store and
core.lancedb_handler).
"""

import hashlib
import logging
import os
import re
import shutil
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

_HASH_RE = re.compile(r"^[0-9a-f]{64}$")


def _backend_dir() -> Path:
    return Path(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _base() -> Path:
    raw = os.getenv("ATOM_PDF_CANVAS_DIR", os.path.join("data", "pdf_canvases"))
    p = Path(raw)
    if not p.is_absolute():
        p = _backend_dir() / p
    return p


def content_hash(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _blob_path(user_id: str, canvas_id: str, content_hash_hex: str) -> Path:
    # ids/hashes are generated here; the guards are defense in depth against
    # hand-crafted values arriving through the API (same stance as the staged
    # attachment store's `staged_` prefix check).
    h = str(content_hash_hex).lower()
    if not _HASH_RE.match(h):
        raise ValueError(f"invalid content hash: {content_hash_hex!r}")
    uid, cid = str(user_id), str(canvas_id)
    if "/" in uid or "\\" in uid or ".." in uid or "/" in cid or "\\" in cid or ".." in cid:
        raise ValueError("invalid user/canvas id for pdf blob path")
    return _base() / uid / cid / f"{h}.pdf"


def save_blob(user_id: str, canvas_id: str, data: bytes) -> str:
    """Store one immutable version, return its sha256. Content-addressing
    makes re-saving an unchanged document a no-op."""
    h = content_hash(data)
    path = _blob_path(user_id, canvas_id, h)
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
    return h


def read_blob(user_id: str, canvas_id: str, content_hash_hex: str) -> Optional[bytes]:
    try:
        path = _blob_path(user_id, canvas_id, content_hash_hex)
    except ValueError:
        return None
    try:
        return path.read_bytes()
    except OSError:
        return None


def delete_canvas_blobs(user_id: str, canvas_id: str) -> None:
    d = _base() / str(user_id) / str(canvas_id)
    try:
        if d.exists():
            shutil.rmtree(d, ignore_errors=True)
    except OSError as e:
        logger.warning(f"Failed to remove pdf canvas blobs for {canvas_id}: {e}")
