# -*- coding: utf-8 -*-
"""Imported email files are first-class core data.

`.eml` is an RFC 822 message a user exports from a mail client. The parser
must preserve participants, date, subject and the plain body so a reader can
summarize, extract tasks or draft a reply — without needing a connected
mailbox.
"""
import asyncio
from email.message import EmailMessage

from core.auto_document_ingestion import DocumentParser


def _message() -> bytes:
    msg = EmailMessage()
    msg["From"] = "Dana Whitfield <dana@example.org>"
    msg["To"] = "Sam Patel <sam@example.org>"
    msg["Cc"] = "ops@example.org"
    msg["Date"] = "Mon, 26 Oct 2026 09:15:00 -0400"
    msg["Subject"] = "Renewal terms and open question"
    msg["In-Reply-To"] = "<thread-42@example.org>"
    msg.set_content(
        "Hi Sam,\n\n"
        "The renewal keeps the 2026 rate. Please confirm the start date.\n\n"
        "Thanks,\nDana\n"
    )
    msg.add_attachment(
        b"quarterly figures", maintype="text", subtype="plain",
        filename="figures.txt",
    )
    return bytes(msg)


def test_eml_preserves_participants_and_body():
    text = asyncio.run(DocumentParser.parse_document(_message(), "eml", "renewal.eml"))
    assert "From: Dana Whitfield <dana@example.org>" in text
    assert "To: Sam Patel <sam@example.org>" in text
    assert "Cc: ops@example.org" in text
    assert "Subject: Renewal terms and open question" in text
    assert "Date: Mon, 26 Oct 2026" in text
    assert "In-Reply-To: <thread-42@example.org>" in text
    assert "The renewal keeps the 2026 rate." in text
    assert "figures.txt" in text
    assert "quarterly figures" not in text  # names only, bytes not dumped


def test_eml_bad_bytes_fail_honestly():
    text = asyncio.run(DocumentParser.parse_document(b"\x00\x01not a message", "eml", "x.eml"))
    # Stdlib tolerates garbage as a body; the important contract is that it
    # never raises through the ingestion path and never invents headers.
    assert isinstance(text, str)
    assert "Subject:" not in text
