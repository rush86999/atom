"""Structured EML parsing for the email canvas.

The memory-ingestion parser intentionally flattens an EML into text. The
canvas needs the opposite: envelope fields, body, thread headers and
attachments kept as separate authoritative fields. This module only parses;
persistence, ownership and authorization live in ``EmailCanvasService``.
"""
from __future__ import annotations

import hashlib
from email import policy
from email.parser import BytesParser
from email.utils import getaddresses, parsedate_to_datetime
from typing import Any, Dict, List


def _addresses(value: str) -> List[str]:
    if not value:
        return []
    return [addr for _name, addr in getaddresses([value]) if addr]


def _body_parts(message) -> tuple[str, str]:
    plain: List[str] = []
    html: List[str] = []
    for part in message.walk():
        if part.is_multipart():
            continue
        disposition = (part.get("Content-Disposition") or "").lower()
        if "attachment" in disposition or part.get_filename():
            continue
        content_type = part.get_content_type()
        try:
            payload = part.get_content()
        except Exception:
            raw = part.get_payload(decode=True) or b""
            payload = raw.decode(part.get_content_charset() or "utf-8", errors="replace")
        if not isinstance(payload, str):
            continue
        if content_type == "text/plain":
            plain.append(payload)
        elif content_type == "text/html":
            html.append(payload)
    return "\n".join(plain).strip(), "\n".join(html).strip()


def parse_eml(content: bytes, filename: str = "message.eml") -> Dict[str, Any]:
    """Parse an EML fixture without losing attachment bytes or thread refs."""
    message = BytesParser(policy=policy.default).parsebytes(content)
    plain, html = _body_parts(message)
    attachments: List[Dict[str, Any]] = []
    for part in message.walk():
        if part.is_multipart():
            continue
        part_filename = part.get_filename()
        disposition = (part.get("Content-Disposition") or "").lower()
        if not part_filename and "attachment" not in disposition:
            continue
        data = part.get_payload(decode=True) or b""
        attachments.append({
            "filename": part_filename or "attachment",
            "content_type": part.get_content_type() or "application/octet-stream",
            "size": len(data),
            "bytes": data,
            "content_id": part.get("Content-ID"),
            "inline": "inline" in disposition,
        })

    message_id = str(message.get("Message-ID") or "").strip()
    references = str(message.get("References") or "").strip()
    in_reply_to = str(message.get("In-Reply-To") or "").strip()
    sent_at = None
    try:
        parsed = parsedate_to_datetime(str(message.get("Date") or ""))
        sent_at = parsed.isoformat() if parsed else None
    except Exception:
        sent_at = str(message.get("Date") or "") or None
    subject = str(message.get("Subject") or "").strip()
    sender = _addresses(str(message.get("From") or ""))
    recipients = _addresses(str(message.get("To") or ""))
    cc = _addresses(str(message.get("Cc") or ""))

    return {
        "schema_version": 1,
        "source_file": filename,
        "source_sha256": hashlib.sha256(content).hexdigest(),
        "source_size": len(content),
        "message_id": message_id,
        "in_reply_to": in_reply_to,
        "references": references,
        "thread_key": (references.split()[-1] if references.split() else (in_reply_to or message_id)),
        "from_email": sender[0] if sender else "",
        "to_emails": recipients,
        "cc_emails": cc,
        "subject": subject,
        "sent_at": sent_at,
        "body_plain": plain,
        "body_html": html,
        "attachments": attachments,
        "headers": {
            "message_id": message_id,
            "in_reply_to": in_reply_to,
            "references": references,
            "date": str(message.get("Date") or ""),
        },
    }
