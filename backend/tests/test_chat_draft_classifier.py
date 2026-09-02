"""Tests for the structural email-draft classifier and its canvas wiring.

Real-world shapes come from the incident that motivated the classifier: a
chat draft expanded via /api/chat/to-canvas was stored as canvas_type
"document" with the email's ``Subject:`` line embedded in the markdown
body, so /canvas/{id} rendered a plain document editor — no To/Subject
fields, no Send button.
"""

from __future__ import annotations

import json

import pytest

from core.chat_draft_classifier import (
    coerce_email_canvas,
    extract_email_draft,
    normalize_email_content,
    select_draft_message,
)


# The actual canvas content from the incident (audit row, lightly trimmed).
MARK_KELLAM_DRAFT = """**Subject:** Re: Your Inquiry — WFS Ltd

Hi Mark,

Thanks for reaching out to Brennan Machinery Inc. We appreciate your interest and the opportunity to help with your equipment needs.

To make sure we recommend the right solution, could you share a few quick details:

1. What type of equipment or application are you looking for?
2. Do you have a target timeline or budget in mind?
3. Are you replacing existing equipment or adding new capacity?

Happy to jump on a quick call to discuss — let me know what works for you.

Best regards,
Rish Maniar
Brennan Machinery Inc.
www.brennan.ca"""

# The ORIGINAL expansion (notes + draft mixed) — must stay a document.
NOTES_AND_DRAFT = """Here's what I found and drafted for you:

**What we quoted Mark before:**
- **Jan 16, 2026** — Vipul sent Mark pricing on a Baxter Model 115C.
- **Feb 4, 2026** — Vipul followed up.

**Draft first-contact email for Mark Kellam:**

---
**Subject:** Re: Your Inquiry — WFS Ltd

Hi Mark,

Thanks for reaching out."""

# The LIVE 2026-09-02 chat bubble (chat_messages row, conversation
# aca15165…, 02:14:28) that seeded canvas da27bb76… with an empty To, a
# truncated narration sentence as Subject, and the narration in the body.
# Narration preamble + UNFENCED draft: the shape the loose scan fixes.
NARRATED_UNFENCED_DRAFT = (
    "Based on the email thread, Mark Kellam is from WFS Ltd. "
    "(mkellam@wfsltd.ca), not Blumetric—Blumetric was a different lead we "
    "handled earlier. Since Mark asked specifically about 480V 3-phase "
    "confirmation for machines, I'll draft a reply to him accordingly.  \n"
    "\n"
    "**To:** mkellam@wfsltd.ca  \n"
    "**Cc:** vipul@brennan.ca, chandrakant@brennan.ca  \n"
    "**Subject:** Re: Brennan Machinery | 480V 3-Phase Confirmation  \n"
    "\n"
    '<font size="3" face="Aptos, Calibri, Arial, sans-serif">Hi Mark,  \n'
    "  \n"
    "Yes, the machines we discussed are available in 480V 3-phase "
    "configuration. To ensure we recommend the best fit for your needs, "
    "could you confirm:  \n"
    "- The material type and grade you're cutting?  \n"
    "- The cross-sectional dimensions or profiles?  \n"
    "  \n"
    "This will help us verify compatibility and provide accurate specs.\n"
    "\n"
    "Best regards,\n"
    "Chandrakant Sharma\n"
    "Brennan Machinery Inc.</font>"
)


class TestExtractEmailDraft:
    def test_plain_header_block(self):
        draft = extract_email_draft("Subject: Hello\n\nWorld, this is the body.")
        assert draft == {"to": "", "cc": "", "subject": "Hello", "body": "World, this is the body."}

    def test_bold_markdown_headers(self):
        draft = extract_email_draft(MARK_KELLAM_DRAFT)
        assert draft is not None
        assert draft["subject"] == "Re: Your Inquiry — WFS Ltd"
        assert draft["to"] == ""
        assert draft["body"].startswith("Hi Mark,")
        assert draft["body"].endswith("www.brennan.ca")
        assert "Subject:" not in draft["body"]

    def test_to_and_subject_headers(self):
        draft = extract_email_draft(
            "To: mark@example.com\nSubject: Hi\n\nSome meaningful body text here."
        )
        assert draft == {
            "to": "mark@example.com",
            "cc": "",
            "subject": "Hi",
            "body": "Some meaningful body text here.",
        }

    def test_cc_header_extracted(self):
        draft = extract_email_draft(
            "To: mark@example.com\nCc: audit@corp.com, boss@corp.com\n"
            "**Subject:** Hi\n\nSome meaningful body text here."
        )
        assert draft is not None
        assert draft["cc"] == "audit@corp.com, boss@corp.com"

    def test_doc_wrapped_shape(self):
        wrapped = {"type": "doc", "content": MARK_KELLAM_DRAFT}
        draft = extract_email_draft(wrapped)
        assert draft is not None
        assert draft["subject"] == "Re: Your Inquiry — WFS Ltd"

    def test_leading_separator_fences_are_ignored(self):
        draft = extract_email_draft("---\n**Subject:** Hi\n---\n\nBody with enough content to count.")
        assert draft is not None
        assert draft["subject"] == "Hi"
        assert draft["body"] == "Body with enough content to count."

    def test_narration_then_fenced_draft_extracts(self):
        """BEHAVIOR CHANGE (Sep 1, 2026 — the "couldn't apply it cleanly"
        incident): narration-wrapped drafts used to return None here, so
        chat→canvas seeded email canvases with a truncated narration as the
        Subject and EMPTY To/Cc even though the draft carried the headers.
        A header block fenced behind narration is now lifted into the
        structured fields; the narration and trailers stay out of the body.
        Update to notes/AGENT_COORDINATION.md documents this flip."""
        draft = extract_email_draft(NOTES_AND_DRAFT)
        assert draft is not None
        assert draft["subject"] == "Re: Your Inquiry — WFS Ltd"
        assert draft["body"].startswith("Hi Mark,")

    def test_unfenced_mid_document_subject_stays_a_document(self):
        """Without a fence isolating the draft, a Subject buried past the
        header window remains prose (the original conservative rule)."""
        buried = (
            "Meeting notes from the call:\n\nWe covered pricing and the "
            "timeline.\n\n**Subject:** Re: Your Inquiry — WFS Ltd\n\nHi "
            "Mark, thanks for reaching out to Brennan Machinery Inc today."
        )
        assert extract_email_draft(buried) is None

    def test_narration_then_unfenced_draft_extracts(self):
        """LIVE incident (2026-09-02, canvas da27bb76…): the chat bubble
        opens with narration prose and follows it DIRECTLY with the draft's
        **To:**/**Cc:**/**Subject:** lines — no --- fences, so the fenced
        rescan never reached them. The canvas was seeded with an EMPTY To,
        a truncated narration sentence as Subject, and the whole bubble
        (narration included) in the body. The loose mid-message scan lifts
        a recipient-first header block out of the narration; the narration
        stays out of the body."""
        draft = extract_email_draft(NARRATED_UNFENCED_DRAFT)
        assert draft is not None
        assert draft["to"] == "mkellam@wfsltd.ca"
        assert draft["cc"] == "vipul@brennan.ca, chandrakant@brennan.ca"
        assert draft["subject"] == "Re: Brennan Machinery | 480V 3-Phase Confirmation"
        # the live bubble wraps the body in a font tag
        assert draft["body"].lstrip().startswith("<font")
        assert "Hi Mark," in draft["body"]
        # the reasoning preamble must NOT leak into the artifact body
        assert "Blumetric" not in draft["body"]
        assert "I'll draft a reply" not in draft["body"]

    def test_loose_scan_requires_a_recipient(self):
        """The loose scan must not fire on a bare buried Subject — same
        conservative contract as the fenced rules, just deeper into the
        message. Without a To:/Cc: line opening the block, prose stays
        prose."""
        subject_only = (
            "Team sync notes:\n\nWe discussed the quote.\n\n"
            "**To do:** follow up with the dealer.\n\n**Subject:** Re: "
            "Your Inquiry\n\nMore meeting prose that is clearly not an "
            "email body."
        )
        assert extract_email_draft(subject_only) is None


    def test_doc_mentioning_subject_midtext_is_not_email(self):
        assert extract_email_draft(
            "# Meeting notes\n\nWe discussed the Subject: line format today "
            "and agreed it needs documenting properly in the wiki."
        ) is None

    def test_subject_without_body_is_not_email(self):
        assert extract_email_draft("Subject: Just a heading") is None

    def test_non_text_shapes_return_none(self):
        assert extract_email_draft(None) is None
        assert extract_email_draft(42) is None
        assert extract_email_draft([["a", "b"]]) is None
        assert extract_email_draft({"type": "doc", "content": {"nested": True}}) is None

    def test_empty_and_blank(self):
        assert extract_email_draft("") is None
        assert extract_email_draft("   \n\n") is None

    def test_greeting_only_body_below_minimum(self):
        assert extract_email_draft("Subject: Hi\n\nshort") is None

    def test_quoted_and_indented_headers(self):
        draft = extract_email_draft("> Subject: Quoted reply\n\nEnough body text to pass the minimum.")
        assert draft is not None
        assert draft["subject"] == "Quoted reply"


class TestNormalizeEmailContent:
    def test_classifier_shape_passthrough_with_defaults(self):
        assert normalize_email_content({"subject": "Hi", "body": "Body text."}) == {
            "to": "",
            "cc": "",
            "subject": "Hi",
            "body": "Body text.",
        }

    def test_email_canvas_service_draft_details(self):
        details = {
            "canvas_type": "email",
            "subject": "Outer subject",
            "draft": {"to_emails": ["a@x.com", "b@x.com"], "subject": "Draft subject", "body": "Hello."},
        }
        assert normalize_email_content(details) == {
            "to": "a@x.com, b@x.com",
            "cc": "",
            "subject": "Draft subject",
            "body": "Hello.",
        }

    def test_draft_details_cc_list(self):
        details = {"draft": {"to_emails": ["a@x.com"], "cc_emails": ["c@x.com"], "subject": "S", "body": "B."}}
        assert normalize_email_content(details)["cc"] == "c@x.com"

    def test_bare_string_is_the_body(self):
        assert normalize_email_content("just body text") == {
            "to": "",
            "cc": "",
            "subject": "",
            "body": "just body text",
        }

    def test_doc_shape_body(self):
        assert normalize_email_content({"type": "doc", "content": "doc body"}) == {
            "to": "",
            "cc": "",
            "subject": "",
            "body": "doc body",
        }


class TestCoerceEmailCanvas:
    def test_document_with_email_draft_becomes_email(self):
        ctype, content = coerce_email_canvas("document", MARK_KELLAM_DRAFT)
        assert ctype == "email"
        assert content["subject"] == "Re: Your Inquiry — WFS Ltd"
        assert content["body"].startswith("Hi Mark,")

    def test_doc_wrapped_content(self):
        ctype, content = coerce_email_canvas("docs", {"type": "doc", "content": MARK_KELLAM_DRAFT})
        assert ctype == "email"
        assert content["subject"] == "Re: Your Inquiry — WFS Ltd"

    def test_plain_document_passthrough(self):
        ctype, content = coerce_email_canvas("document", "# Notes\n\nJust notes.")
        assert ctype == "document"
        assert content == "# Notes\n\nJust notes."

    def test_narration_wrapped_draft_coerces_with_clean_fields(self):
        """Aligned with test_narration_then_fenced_draft_extracts: the auto
        path now retypes a narration-wrapped, fenced email draft into an
        email canvas carrying the draft's REAL To/Subject — not the
        degenerate {to: "", subject: narration} seed the old conservatism
        produced (the "couldn't apply it cleanly" incident)."""
        ctype, content = coerce_email_canvas("document", NOTES_AND_DRAFT)
        assert ctype == "email"
        assert content["subject"] == "Re: Your Inquiry — WFS Ltd"
        assert content["body"].startswith("Hi Mark,")

    def test_sheet_and_code_types_never_coerced(self):
        cells = [["Subject:", "x"], ["y", "z"]]
        assert coerce_email_canvas("sheets", cells) == ("sheets", cells)
        code = "Subject: like line in code\nprint('hello world')"
        assert coerce_email_canvas("coding", code) == ("coding", code)

    def test_typed_email_content_normalized(self):
        ctype, content = coerce_email_canvas("email", {"draft": {"to_emails": ["a@x.com"], "subject": "S", "body": "B."}})
        assert ctype == "email"
        assert content == {"to": "a@x.com", "cc": "", "subject": "S", "body": "B."}

    def test_typed_email_bare_string_passthrough(self):
        assert coerce_email_canvas("email", "body only") == ("email", "body only")

    def test_none_type(self):
        ctype, _ = coerce_email_canvas(None, "just text, no headers")
        assert ctype == "generic"


# A conversational answer that merely EMBEDS a code snippet — the live
# wrong-canvas bug: newest-first selection used to open THIS message
# instead of the real draft sitting older in the history.
ANSWER_WITH_SNIPPET = (
    "Happy to explain!\n\n"
    "Here's a small piece of it:\n\n"
    "```python\nx = 1\ny = 2\nprint(x + y)\n```\n\n"
    "The full flow has more steps — the router picks the tool, the tool "
    "calls the API, and the result streams back into the chat.\n\n"
    "Want me to walk through any step in detail?"
)

# A draft-shaped code reply: the code outweighs the framing prose.
CODE_DRAFT = (
    "Here's the migration script:\n\n"
    "```bash\npsql $DB -c 'BEGIN'\nalembic upgrade head\n"
    "psql $DB -c 'COMMIT'\ncurl -s localhost:8000/health\necho done\n```\n\n"
    "Ping me if anything fails."
)

# An answer carrying a small comparison table — prose-dominated.
TABLE_ANSWER = (
    "Both options could work — here's a quick side-by-side:\n\n"
    "| Plan | Price |\n| --- | --- |\n| Basic | $10 |\n\n"
    "Overall I'd lean Basic for your volume, but happy to go deeper on either."
)

# A draft-shaped table reply: the table outweighs the framing prose.
TABLE_DRAFT = (
    "Here's the roster:\n\n"
    "| Name | Role |\n| --- | --- |\n| Ana | Ops |\n| Raj | Eng |\n"
    "| Mei | Design |\n| Zoe | Sales |\n"
)


class TestSelectDraftMessage:
    """Newest-first draft selection for "Open latest draft in canvas".

    Selection is stricter than detect_draft_kind: code/table candidates
    count only when the artifact dominates the message, so a later
    conversational answer can no longer shadow the real draft; dict
    candidates echo the picked message's id for UI transparency.
    """

    def test_bare_string_candidates_still_work(self):
        sel = select_draft_message(["just a conversational answer", MARK_KELLAM_DRAFT])
        assert sel == {"content": MARK_KELLAM_DRAFT, "kind": "email"}

    def test_dict_candidates_echo_message_id(self):
        cands = [
            {"id": "msg_answer", "content": ANSWER_WITH_SNIPPET},
            {"id": "msg_draft", "content": MARK_KELLAM_DRAFT},
        ]
        sel = select_draft_message(cands)
        assert sel["kind"] == "email"
        assert sel["message_id"] == "msg_draft"

    def test_snippet_answer_does_not_shadow_older_draft(self):
        sel = select_draft_message([ANSWER_WITH_SNIPPET, MARK_KELLAM_DRAFT])
        assert sel["kind"] == "email"
        assert sel["content"] == MARK_KELLAM_DRAFT

    def test_table_answer_does_not_shadow_older_draft(self):
        sel = select_draft_message([TABLE_ANSWER, MARK_KELLAM_DRAFT])
        assert sel["kind"] == "email"

    def test_dominating_code_draft_is_selected(self):
        sel = select_draft_message([CODE_DRAFT])
        assert sel["kind"] == "code"

    def test_dominating_table_draft_is_selected(self):
        sel = select_draft_message([TABLE_DRAFT])
        assert sel["kind"] == "table"

    def test_newest_draft_wins_among_two_drafts(self):
        sel = select_draft_message([CODE_DRAFT, MARK_KELLAM_DRAFT])
        assert sel["kind"] == "code"
        assert sel["content"] == CODE_DRAFT

    def test_no_qualifying_candidate_returns_none(self):
        assert select_draft_message(["hello", "how can I help?"]) is None
        assert select_draft_message([]) is None
        assert select_draft_message(None) is None

    def test_non_string_content_skipped(self):
        sel = select_draft_message([{"id": "m1", "content": 42}, MARK_KELLAM_DRAFT])
        assert sel["kind"] == "email"


class _CanvasHarness:
    """Shared in-memory DB setup for canvas_crud_tool read/update tests."""

    @pytest.fixture()
    def db_session(self, monkeypatch):
        from sqlalchemy import create_engine
        from sqlalchemy.orm import sessionmaker
        from sqlalchemy.pool import StaticPool

        from core.models_registration import Base

        engine = create_engine(
            "sqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(engine)
        Session = sessionmaker(bind=engine)
        session = Session()

        import core.database as database_module
        import contextlib

        @contextlib.contextmanager
        def _session():
            yield session

        monkeypatch.setattr(database_module, "get_db_session", _session)
        yield session
        session.close()
        engine.dispose()

    @staticmethod
    def _make_canvas(db, canvas_id="c-email-1", canvas_type="document", content=None, owner="user-1"):
        from core.models import Canvas, CanvasAudit

        db.add(Canvas(
            id=canvas_id,
            tenant_id="default",
            workspace_id="default",
            created_by=owner,
            name="Draft",
            canvas_type=canvas_type,
            content=content,
            status="active",
        ))
        db.add(CanvasAudit(
            canvas_id=canvas_id,
            tenant_id="default",
            action_type="create",
            canvas_type=canvas_type,
            user_id=owner,
            details_json={"source": "chat_to_canvas", "title": "Draft", "content": content},
        ))
        db.commit()
        # Backdate the create audit: read_canvas orders by created_at with
        # second precision, and a same-second create+update would tie.
        from datetime import datetime, timedelta

        from core.models import CanvasAudit

        audit = db.query(CanvasAudit).filter(CanvasAudit.canvas_id == canvas_id).first()
        audit.created_at = datetime.utcnow() - timedelta(minutes=1)
        db.commit()


class TestReadCanvasCoercion(_CanvasHarness):

    @pytest.mark.asyncio
    async def test_historical_doc_canvas_reads_as_email(self, db_session):
        """The incident case: audit says document, content is an email draft
        with the Subject line embedded — the read must return the typed,
        structured email shape the composer renders."""
        from tools.canvas_crud_tool import read_canvas

        self._make_canvas(db_session, content={"type": "doc", "content": MARK_KELLAM_DRAFT})
        result = await read_canvas("user-1", "c-email-1")

        assert result["success"] is True
        assert result["canvas_type"] == "email"
        assert result["content"]["subject"] == "Re: Your Inquiry — WFS Ltd"
        assert result["content"]["body"].startswith("Hi Mark,")
        assert result["content"]["to"] == ""

    @pytest.mark.asyncio
    async def test_plain_doc_read_unchanged(self, db_session):
        from tools.canvas_crud_tool import read_canvas

        self._make_canvas(db_session, content={"type": "doc", "content": "# Notes\n\nPlain notes."})
        result = await read_canvas("user-1", "c-email-1")

        assert result["canvas_type"] == "document"
        assert result["content"] == {"type": "doc", "content": "# Notes\n\nPlain notes."}

    @pytest.mark.asyncio
    async def test_email_canvas_service_details_normalized(self, db_session):
        """EmailCanvasService.create_email_canvas writes draft-shaped
        details with no content key — the read must expose {to,subject,body}."""
        from tools.canvas_crud_tool import read_canvas

        self._make_canvas(
            db_session,
            canvas_type="email",
            content=None,
        )
        # Overwrite the audit details to the service shape.
        from core.models import CanvasAudit

        audit = db_session.query(CanvasAudit).filter(CanvasAudit.canvas_id == "c-email-1").first()
        audit.details_json = {
            "canvas_type": "email",
            "subject": "Quote follow-up",
            "draft": {"to_emails": ["mark@example.com"], "subject": "Quote follow-up", "body": "Hi Mark,"},
            "messages": [],
        }
        db_session.commit()

        result = await read_canvas("user-1", "c-email-1")
        assert result["canvas_type"] == "email"
        assert result["content"] == {
            "to": "mark@example.com",
            "cc": "",
            "subject": "Quote follow-up",
            "body": "Hi Mark,",
        }


class TestUpdateCanvasCoercion(_CanvasHarness):

    @pytest.mark.asyncio
    async def test_co_editor_rewrite_retypes_doc_to_email(self, db_session, monkeypatch):
        """The co-editor LLM returns doc-shaped content; when that content
        is a pure email draft the update must store canvas_type email."""
        from unittest.mock import AsyncMock

        import core.websockets as ws_module
        from tools.canvas_crud_tool import update_canvas_content

        monkeypatch.setattr(ws_module, "manager", AsyncMock())

        self._make_canvas(db_session, content={"type": "doc", "content": "# original notes\nwith more text here."})
        result = await update_canvas_content(
            "user-1", "c-email-1", {"type": "doc", "content": MARK_KELLAM_DRAFT}, "document", None
        )

        assert result["success"] is True
        assert result["canvas_type"] == "email"

        from tools.canvas_crud_tool import read_canvas

        reread = await read_canvas("user-1", "c-email-1")
        assert reread["canvas_type"] == "email"
        assert reread["content"]["subject"] == "Re: Your Inquiry — WFS Ltd"

    @pytest.mark.asyncio
    async def test_update_broadcast_includes_email_metadata(self, db_session, monkeypatch):
        from unittest.mock import AsyncMock

        import core.websockets as ws_module
        from tools.canvas_crud_tool import update_canvas_content

        ws_manager = AsyncMock()
        monkeypatch.setattr(ws_module, "manager", ws_manager)

        self._make_canvas(db_session, content={"type": "doc", "content": "# original notes\nwith more text here."})
        await update_canvas_content(
            "user-1", "c-email-1", {"type": "doc", "content": MARK_KELLAM_DRAFT}, "document", None
        )

        broadcast = ws_manager.broadcast.await_args[0][1]
        assert broadcast["data"]["component"] == "email"
        assert broadcast["data"]["metadata"]["subject"] == "Re: Your Inquiry — WFS Ltd"
        assert broadcast["data"]["data"]["body"].startswith("Hi Mark,")


class TestSuggestContacts:
    """EmailCanvasService.suggest_contacts — the To/Cc autocomplete source."""

    @pytest.mark.asyncio
    async def test_normalizes_dedupes_and_caps(self):
        from unittest.mock import AsyncMock, patch

        from core.canvas_email_service import EmailCanvasService

        raw = [
            {
                "display_name": "Mark Kellam",
                "email_addresses": [{"address": "Mark.Kellam@Example.com"}, {"address": "mark.kellam@example.com"}],
            },
            {"display_name": "", "email_addresses": [{"address": "nobody@corp.com"}]},
            {"display_name": "Ghost", "email_addresses": []},
            {"display_name": "Broken", "email_addresses": [{"address": None}]},
        ]
        with patch("integrations.outlook_service.OutlookService") as OutlookMock:
            OutlookMock.return_value.get_user_contacts = AsyncMock(return_value=raw)
            result = await EmailCanvasService(db=None).suggest_contacts("user-1", query="mar")

        OutlookMock.return_value.get_user_contacts.assert_awaited_once()
        assert result["success"] is True
        assert result["source"] == "outlook"
        assert result["contacts"] == [
            {"name": "Mark Kellam", "email": "Mark.Kellam@Example.com"},
            {"name": "", "email": "nobody@corp.com"},
        ]

    @pytest.mark.asyncio
    async def test_mailbox_failure_degrades_to_empty(self):
        from unittest.mock import AsyncMock, patch

        from core.canvas_email_service import EmailCanvasService

        with patch("integrations.outlook_service.OutlookService") as OutlookMock:
            OutlookMock.return_value.get_user_contacts = AsyncMock(side_effect=RuntimeError("no token"))
            result = await EmailCanvasService(db=None).suggest_contacts("user-1")

        assert result == {"success": True, "contacts": [], "source": None}

    @pytest.mark.asyncio
    async def test_empty_address_book(self):
        from unittest.mock import AsyncMock, patch

        from core.canvas_email_service import EmailCanvasService

        with patch("integrations.outlook_service.OutlookService") as OutlookMock:
            OutlookMock.return_value.get_user_contacts = AsyncMock(return_value=[])
            result = await EmailCanvasService(db=None).suggest_contacts("user-1", query="x")

        assert result == {"success": True, "contacts": [], "source": None}

    @pytest.mark.asyncio
    async def test_mail_history_fallback_when_address_book_denied(self):
        """Existing consents lack Contacts.Read (403 → []): suggestions fall
        back to correspondents mined from inbox + sent mail, ranked by
        frequency, excluding the user's own address."""
        from unittest.mock import AsyncMock, patch

        from core.canvas_email_service import EmailCanvasService, _CORRESPONDENT_CACHE

        _CORRESPONDENT_CACHE.clear()

        def msg(frm, to, cc=None):
            return {
                "from_field": {"emailAddress": {"name": frm[0], "address": frm[1]}},
                "to_recipients": [{"emailAddress": {"name": t[0], "address": t[1]}} for t in to],
                "cc_recipients": [{"emailAddress": {"name": c[0], "address": c[1]}} for c in (cc or [])],
            }

        inbox = [msg(("Mark Kellam", "mark@wfs.example"), [("Rish", "rish@brennan.example")])]
        sent = [
            msg(("Rish", "rish@brennan.example"), [("Mark Kellam", "mark@wfs.example")]),
            msg(("Rish", "rish@brennan.example"), [("Mark Kellam", "mark@wfs.example"), ("Ann", "ann@corp.example")]),
        ]
        with patch("integrations.outlook_service.OutlookService") as OutlookMock:
            inst = OutlookMock.return_value
            inst.get_user_contacts = AsyncMock(return_value=[])  # 403/empty
            inst.get_user_emails = AsyncMock(side_effect=lambda user_id, folder=None, max_results=25: {
                "inbox": inbox, "sent": sent,
            }[folder])
            result = await EmailCanvasService(db=None).suggest_contacts("user-1")

        assert result["success"] is True
        assert result["source"] == "outlook_mail_history"
        emails = [c["email"] for c in result["contacts"]]
        # Mark appears 3 times → first; rish (the user's own address) excluded.
        assert emails[0] == "mark@wfs.example"
        assert "rish@brennan.example" not in emails
        assert "ann@corp.example" in emails

    @pytest.mark.asyncio
    async def test_mail_history_fallback_respects_query(self):
        import time as time_mod
        from unittest.mock import AsyncMock, patch

        from core.canvas_email_service import EmailCanvasService, _CORRESPONDENT_CACHE

        _CORRESPONDENT_CACHE.clear()
        with patch("integrations.outlook_service.OutlookService") as OutlookMock:
            inst = OutlookMock.return_value
            inst.get_user_contacts = AsyncMock(return_value=[])
            inst.get_user_emails = AsyncMock(return_value=[])
            # Prime the cache with known correspondents.
            _CORRESPONDENT_CACHE["user-1"] = (
                time_mod.time(), [("mark@wfs.example", "Mark Kellam"), ("ann@corp.example", "Ann")]
            )
            result = await EmailCanvasService(db=None).suggest_contacts("user-1", query="zzz")
        assert result["contacts"] == []
        result2 = await EmailCanvasService(db=None).suggest_contacts("user-1", query="mark")
        assert [c["email"] for c in result2["contacts"]] == ["mark@wfs.example"]
        _CORRESPONDENT_CACHE.clear()


class TestResolveReplyRecipients:
    """EmailCanvasService.resolve_reply_recipients — To auto-fill for
    reply drafts (Re:/Fw: subject, empty recipient)."""

    @pytest.mark.asyncio
    async def test_reply_to_received_mail_fills_sender(self):
        from unittest.mock import AsyncMock, patch

        from core.canvas_email_service import EmailCanvasService

        thread = [{
            "subject": "Your Inquiry — WFS Ltd",
            "from_field": {"emailAddress": {"name": "Mark Kellam", "address": "mark@wfs.example"}},
            "to_recipients": [{"emailAddress": {"name": "Rish", "address": "rish@brennan.ca"}}],
            "cc_recipients": [],
            "received_date_time": "2026-08-28T10:00:00Z",
        }]
        with patch("integrations.outlook_service.OutlookService") as OutlookMock:
            inst = OutlookMock.return_value
            inst.search_emails = AsyncMock(return_value=thread)
            inst.get_user_profile = AsyncMock(return_value={"mail": "rish@brennan.ca"})
            result = await EmailCanvasService(db=None).resolve_reply_recipients(
                "user-1", "Re: Your Inquiry — WFS Ltd"
            )

        assert result["success"] is True
        assert result["to"] == "Mark Kellam <mark@wfs.example>"
        assert result["source"] == "thread"

    @pytest.mark.asyncio
    async def test_reply_to_own_sent_mail_fills_original_recipients(self):
        from unittest.mock import AsyncMock, patch

        from core.canvas_email_service import EmailCanvasService

        thread = [{
            "subject": "Re: Pricing",
            "from_field": {"emailAddress": {"name": "Rish", "address": "rish@brennan.ca"}},
            "to_recipients": [
                {"emailAddress": {"name": "Mark", "address": "mark@wfs.example"}},
                {"emailAddress": {"name": "Ann", "address": "ann@corp.example"}},
            ],
            "cc_recipients": [{"emailAddress": {"name": "Acc", "address": "accounting@brennan.ca"}}],
            "sent_date_time": "2026-08-27T10:00:00Z",
        }]
        with patch("integrations.outlook_service.OutlookService") as OutlookMock:
            inst = OutlookMock.return_value
            inst.search_emails = AsyncMock(return_value=thread)
            inst.get_user_profile = AsyncMock(return_value={"mail": "rish@brennan.ca"})
            result = await EmailCanvasService(db=None).resolve_reply_recipients("user-1", "Re: Pricing")

        assert result["to"] == "mark@wfs.example, ann@corp.example"
        assert result["cc"] == "accounting@brennan.ca"

    @pytest.mark.asyncio
    async def test_non_reply_subject_short_circuits(self):
        from core.canvas_email_service import EmailCanvasService

        result = await EmailCanvasService(db=None).resolve_reply_recipients("user-1", "New inquiry")
        assert result["to"] is None
        assert result["reason"] == "not_a_reply"

    @pytest.mark.asyncio
    async def test_no_thread_match_returns_none(self):
        from unittest.mock import AsyncMock, patch

        from core.canvas_email_service import EmailCanvasService

        with patch("integrations.outlook_service.OutlookService") as OutlookMock:
            inst = OutlookMock.return_value
            inst.search_emails = AsyncMock(return_value=[])
            inst.get_user_profile = AsyncMock(return_value={"mail": "rish@brennan.ca"})
            result = await EmailCanvasService(db=None).resolve_reply_recipients("user-1", "Re: Nothing matches")

        assert result["to"] is None
        assert result["source"] is None

    @pytest.mark.asyncio
    async def test_received_match_preferred_over_own_sent(self):
        from unittest.mock import AsyncMock, patch

        from core.canvas_email_service import EmailCanvasService

        results = [
            {
                "subject": "Re: Pricing",
                "from_field": {"emailAddress": {"name": "Rish", "address": "rish@brennan.ca"}},
                "to_recipients": [{"emailAddress": {"name": "Mark", "address": "mark@wfs.example"}}],
                "cc_recipients": [],
                "sent_date_time": "2026-08-20T10:00:00Z",
            },
            {
                "subject": "Re: Pricing",
                "from_field": {"emailAddress": {"name": "Mark Kellam", "address": "mark@wfs.example"}},
                "to_recipients": [{"emailAddress": {"name": "Rish", "address": "rish@brennan.ca"}}],
                "cc_recipients": [],
                "received_date_time": "2026-08-29T10:00:00Z",
            },
        ]
        with patch("integrations.outlook_service.OutlookService") as OutlookMock:
            inst = OutlookMock.return_value
            inst.search_emails = AsyncMock(return_value=results)
            inst.get_user_profile = AsyncMock(return_value={"mail": "rish@brennan.ca"})
            result = await EmailCanvasService(db=None).resolve_reply_recipients("user-1", "Re: Pricing")

        assert result["to"] == "Mark Kellam <mark@wfs.example>"

    @pytest.mark.asyncio
    async def test_token_leg_fills_from_lead_form_body(self):
        """The incident shape: agent-invented subject ("Re: Your Inquiry —
        WFS Ltd") that matches no thread; the real inquiry is a Zoho lead
        form whose BODY carries the person's address."""
        from unittest.mock import AsyncMock, patch

        from core.canvas_email_service import EmailCanvasService

        inquiry = {
            "subject": "New Quote Request From New Lead",
            "from_field": {"emailAddress": {"name": "Notifications", "address": "notifications@zohoforms.ca"}},
            "to_recipients": [{"emailAddress": {"name": "Rish", "address": "rish@brennan.ca"}}],
            "cc_recipients": [],
            "received_date_time": "2026-08-29T09:00:00Z",
            "body": {"content": "Name : Mark, Kellam Company : WFS Ltd Postal Code : N8X 3J3 Phone : 519-250-2484 Email : mkellam@wfsltd.ca https://brennan.ca/pages/contact"},
        }
        wfs_steel_thread = {
            "subject": "Crane rental schedule",
            "from_field": {"emailAddress": {"name": "Simon Ingram", "address": "singram@wfsteelandcrane.com"}},
            "to_recipients": [{"emailAddress": {"name": "Rish", "address": "rish@brennan.ca"}}],
            "cc_recipients": [],
            "received_date_time": "2026-08-28T09:00:00Z",
            "body": {"content": "<p>WFS Steel and Crane schedule. Contact singram@wfsteelandcrane.com.</p>"},
        }
        with patch("integrations.outlook_service.OutlookService") as OutlookMock:
            inst = OutlookMock.return_value
            inst.search_emails = AsyncMock(return_value=[inquiry, wfs_steel_thread])
            inst.get_user_profile = AsyncMock(return_value={"mail": "rish@brennan.ca"})
            result = await EmailCanvasService(db=None).resolve_reply_recipients(
                "user-1", "Re: Your Inquiry — WFS Ltd", body_hint="Hi Mark,\n\nThanks for reaching out."
            )

        # The name-token match (lead form: "Name : Mark … Email : mkellam…")
        # outweighs the other WFS-domain person (domain-only evidence).
        assert result["to"] == "mkellam@wfsltd.ca"
        assert result["source"] == "tokens"

    @pytest.mark.asyncio
    async def test_token_leg_ignores_marketing_noise(self):
        """'mark' as a substring of 'marketing@…' must NOT match — only
        whole local-part segments and domain roots count."""
        from unittest.mock import AsyncMock, patch

        from core.canvas_email_service import EmailCanvasService

        noise = {
            "subject": "July promo",
            "from_field": {"emailAddress": {"name": "Marketing", "address": "marketing@message.ofx.com"}},
            "to_recipients": [{"emailAddress": {"name": "Rish", "address": "rish@brennan.ca"}}],
            "cc_recipients": [],
            "received_date_time": "2026-08-29T09:00:00Z",
            "body": {"content": "marketing@message.ofx.com marketing=scotchman.com@bf02x.hs-send.com"},
        }
        with patch("integrations.outlook_service.OutlookService") as OutlookMock:
            inst = OutlookMock.return_value
            inst.search_emails = AsyncMock(return_value=[noise])
            inst.get_user_profile = AsyncMock(return_value={"mail": "rish@brennan.ca"})
            result = await EmailCanvasService(db=None).resolve_reply_recipients(
                "user-1", "Re: Follow up", body_hint="Hi Mark,\n\nJust following up."
            )

        assert result["to"] is None

    def test_reply_tokens_extraction(self):
        from core.canvas_email_service import EmailCanvasService

        svc = EmailCanvasService(db=None)
        name_tokens, domain_tokens = svc._reply_tokens(
            "Re: Your Inquiry — WFS Ltd", "Hi Mark,\n\nThanks for reaching out."
        )
        assert name_tokens == ["mark"]
        assert "wfs" in domain_tokens
        # Generic words are dropped.
        assert all(w not in domain_tokens for w in ("your", "inquiry", "ltd"))
        assert svc._reply_tokens("Re: Follow up", "") == ([], [])


class TestSignature:
    """Default email signature: stored override → integration-derived
    (sign-off block of the newest sent mail)."""

    def _svc(self):
        from core.canvas_email_service import EmailCanvasService, _SIGNATURE_CACHE

        _SIGNATURE_CACHE.clear()
        return EmailCanvasService(db=None), _SIGNATURE_CACHE

    def test_extract_signoff_standard(self):
        svc, _ = self._svc()
        body = {"content": "<p>Here is the quote.</p><p>Best regards,</p><p>Rish Maniar</p><p>Brennan Machinery Inc.</p><p>www.brennan.ca</p>"}
        assert svc._extract_signoff(body) == "Best regards,\nRish Maniar\nBrennan Machinery Inc.\nwww.brennan.ca"

    def test_extract_signoff_none_without_closing(self):
        svc, _ = self._svc()
        assert svc._extract_signoff({"content": "Just the body, no sign-off."}) is None

    def test_extract_signoff_single_line_block_rejected(self):
        svc, _ = self._svc()
        assert svc._extract_signoff({"content": "body\n\nThanks,"}) is None

    def test_extract_signoff_oversized_block_rejected(self):
        svc, _ = self._svc()
        huge = "\n".join(["Best regards,"] + [f"line {i}" for i in range(20)])
        assert svc._extract_signoff({"content": huge}) is None

    def test_extract_signoff_real_outlook_banner_signature(self):
        """The actual incident shape: the user's Outlook default is a long
        banner signature (11 lines, 'Regards, Rish M.' + promo lines) —
        short caps rejected it."""
        svc, _ = self._svc()
        body = {"content": (
            "I sent an email on this before so this is easier to use for new tender opportunities\n"
            "Regards,\nRish M.\nBrennan Machinery Inc.\nVisit Our Web Site\nwww.brennan.ca\n"
            "How am I doing?\nRate my performance\n.\n"
            "Reclaim your floor space and monetize your idle equipment.\n"
            "Simply reply with your machine specs, and we'll leverage our buyer network to get it sold for you.\n"
            "All quotes are valid for 15 days only, thank you for understanding."
        )}
        sig = svc._extract_signoff(body, owner_names={"rish", "maniar"})
        assert sig is not None
        assert sig.startswith("Regards,\nRish M.")
        assert sig.endswith("thank you for understanding.")

    def test_extract_signoff_owner_guard_rejects_quoted_colleague(self):
        svc, _ = self._svc()
        body = {"content": "My reply text.\n\nThanks\nSarp D.\nBrennan Machinery Inc.\nwww.brennan.ca"}
        assert svc._extract_signoff(body, owner_names={"rish", "maniar"}) is None

    @pytest.mark.asyncio
    async def test_stored_preference_wins(self):
        from unittest.mock import patch

        for svc, _ in [self._svc()]:
            with patch("core.user_preference_service.UserPreferenceService") as PrefMock:
                PrefMock.return_value.get_preference.return_value = "Custom sig\nLine 2"
                result = await svc.get_signature("user-1")
        assert result == {"success": True, "signature": "Custom sig\nLine 2", "source": "stored"}

    @pytest.mark.asyncio
    async def test_integration_default_mined_from_sent_mail(self):
        from unittest.mock import AsyncMock, patch

        svc, cache = self._svc()
        sent = [{
            "body": {"content": "Quote attached.\n\nBest regards,\nRish Maniar\nBrennan Machinery Inc.\nwww.brennan.ca"},
        }]
        with patch("core.user_preference_service.UserPreferenceService") as PrefMock, \
             patch("integrations.outlook_service.OutlookService") as OutlookMock:
            PrefMock.return_value.get_preference.return_value = None
            OutlookMock.return_value.get_user_emails = AsyncMock(return_value=sent)
            result = await svc.get_signature("user-1")

        assert result["source"] == "integration"
        assert result["signature"].startswith("Best regards,\nRish Maniar")
        # Cached — a second call does not rescan the mailbox.
        with patch("core.user_preference_service.UserPreferenceService") as PrefMock:
            PrefMock.return_value.get_preference.return_value = None
            again = await svc.get_signature("user-1")
        assert again["signature"] == result["signature"]
        cache.clear()

    @pytest.mark.asyncio
    async def test_no_signature_anywhere(self):
        from unittest.mock import AsyncMock, patch

        svc, cache = self._svc()
        with patch("core.user_preference_service.UserPreferenceService") as PrefMock, \
             patch("integrations.outlook_service.OutlookService") as OutlookMock:
            PrefMock.return_value.get_preference.return_value = None
            OutlookMock.return_value.get_user_emails = AsyncMock(return_value=[{"body": {"content": "no signoff here"}}])
            result = await svc.get_signature("user-1")
        assert result == {"success": True, "signature": None, "source": None}
        cache.clear()

    @pytest.mark.asyncio
    async def test_set_signature_persists_and_clears_cache(self):
        from unittest.mock import patch

        svc, cache = self._svc()
        cache["user-1"] = (1.0, "old mined")
        with patch("core.user_preference_service.UserPreferenceService") as PrefMock:
            result = svc.set_signature("user-1", "New sig")
            PrefMock.return_value.set_preference.assert_called_once()
        assert result["signature"] == "New sig"
        assert "user-1" not in cache

        with patch("core.user_preference_service.UserPreferenceService") as PrefMock:
            cleared = svc.set_signature("user-1", "   ")
        assert cleared["signature"] is None


class TestStripTrailingSignoff:
    """Agent-typed sign-offs are stripped at chat→canvas creation so the
    composer's real default signature is the only one applied."""

    def test_strips_plain_closing_block(self):
        from core.chat_draft_classifier import strip_trailing_signoff

        body = "Hi Mark,\n\nHere is the quote.\n\nBest regards,\nRish Maniar\nBrennan Machinery Inc."
        assert strip_trailing_signoff(body) == "Hi Mark,\n\nHere is the quote."

    def test_strips_bold_closing_and_placeholder(self):
        from core.chat_draft_classifier import strip_trailing_signoff

        body = "Body text.\n\n**Best regards,**\n[Your Name]\nBrennan Machinery"
        assert strip_trailing_signoff(body) == "Body text."

    def test_prose_thanks_is_not_a_signoff(self):
        from core.chat_draft_classifier import strip_trailing_signoff

        body = "Thanks for your patience while I checked on this."
        assert strip_trailing_signoff(body) == body

    def test_mid_body_regards_is_not_stripped(self):
        from core.chat_draft_classifier import strip_trailing_signoff

        body = "Regards to the team.\n\n" + "\n".join(f"point {i}" for i in range(20))
        assert strip_trailing_signoff(body) == body

    def test_body_without_closing_unchanged(self):
        from core.chat_draft_classifier import strip_trailing_signoff

        body = "Just the body."
        assert strip_trailing_signoff(body) == "Just the body."
        assert strip_trailing_signoff("") == ""

    def test_conditional_strip_keeps_closing_without_default(self):
        """User with NO default signature: the agent's closing is kept —
        stripping would send a bare draft."""
        from core.chat_draft_classifier import strip_agent_signoff

        body = "Hi Mark,\n\nQuote attached.\n\nBest regards,\nRish Maniar"
        assert strip_agent_signoff(body, None) == body
        assert strip_agent_signoff(body, "") == body
        assert strip_agent_signoff(body, "   ") == body

    def test_conditional_strip_replaces_when_default_exists(self):
        from core.chat_draft_classifier import strip_agent_signoff

        body = "Hi Mark,\n\nQuote attached.\n\nBest regards,\n[Your Name]"
        assert strip_agent_signoff(body, "Regards,\nRish M.\nBrennan") == "Hi Mark,\n\nQuote attached."


class TestSelectDraftMessage:
    """"Open latest draft in canvas" must open the draft, not the newest
    message: chat typically moves on after a draft lands. Generalizes to
    every artifact kind (email / code / table / doc)."""

    def test_most_recent_artifact_wins_regardless_of_kind(self):
        from core.chat_draft_classifier import select_draft_message

        candidates = [  # newest first
            "Sure — the tax filing deadline is April 30.",
            "Here's the pricing table you asked for:\n\n| A | B |\n|---|---|\n| 1 | 2 |",
            "Subject: Quote for Mark\n\nHi Mark,\n\nHere is the quote you requested. It was great talking.",
            "Anything else I can help with?",
        ]
        # The table is the most recent ARTIFACT — chatter on top of it is
        # skipped, but it still beats the older email draft.
        chosen = select_draft_message(candidates)
        assert chosen["kind"] == "table"

    def test_email_draft_found_when_only_artifact(self):
        from core.chat_draft_classifier import select_draft_message

        candidates = [
            "Sure — the tax filing deadline is April 30.",
            "Subject: Quote for Mark\n\nHi Mark,\n\nHere is the quote you requested. It was great talking.",
        ]
        chosen = select_draft_message(candidates)
        assert chosen["content"].startswith("Subject: Quote for Mark")
        assert chosen["kind"] == "email"

    def test_skips_conversational_replies_to_find_code_draft(self):
        from core.chat_draft_classifier import select_draft_message

        candidates = [  # newest first
            "Done! Let me know if you want any tweaks.",
            "```python\nimport csv\nwith open('out.csv') as f:\n    rows = list(csv.reader(f))\nprint(len(rows))\n```",
            "No problem, happy to help.",
        ]
        chosen = select_draft_message(candidates)
        assert chosen["kind"] == "code"
        assert "import csv" in chosen["content"]

    def test_finds_table_draft_under_newer_chatter(self):
        from core.chat_draft_classifier import select_draft_message

        candidates = [
            "The deadline is April 30.",
            "| Item | Qty |\n|---|---|\n| Bandsaw | 2 |\n| Crane | 1 |",
        ]
        chosen = select_draft_message(candidates)
        assert chosen["kind"] == "table"

    def test_finds_titled_document(self):
        from core.chat_draft_classifier import select_draft_message

        doc = "# Onboarding Playbook\n\n## Week 1\n\nSetup accounts. " + "Step details. " * 30
        chosen = select_draft_message(["Sure thing!", doc])
        assert chosen["kind"] == "doc"

    def test_none_when_no_draft(self):
        from core.chat_draft_classifier import select_draft_message

        assert select_draft_message(["One answer.", "Another answer."]) is None

    def test_empty_and_non_string_inputs(self):
        from core.chat_draft_classifier import select_draft_message

        assert select_draft_message([]) is None
        assert select_draft_message(None) is None
        assert select_draft_message([None, 42, ""]) is None


class TestDetectDraftKind:
    def test_short_inline_code_is_not_a_code_draft(self):
        from core.chat_draft_classifier import detect_draft_kind

        assert detect_draft_kind("Use `pip install x` to install it.") is None

    def test_prose_with_pipe_chars_is_not_a_table(self):
        from core.chat_draft_classifier import detect_draft_kind

        assert detect_draft_kind("Pick option A | or option B, whichever works.") is None

    def test_heading_decorated_answer_is_not_a_doc_draft(self):
        """Answers often use headings mid-text — only a LEADING titled
        document counts (the artifact must be the message)."""
        from core.chat_draft_classifier import detect_draft_kind

        answer = "Here's the rundown.\n\n## Details\n\n" + "Explanation. " * 40
        assert detect_draft_kind(answer) is None

    def test_kind_ordering_email_strongest(self):
        from core.chat_draft_classifier import detect_draft_kind

        both = "Subject: Hi\n\nBody text with a table:\n\n| A | B |\n|---|---|\n| 1 | 2 |"
        assert detect_draft_kind(both) == "email"


class TestOfficeDraftParsing:
    def test_markdown_table_rows(self):
        from core.chat_draft_classifier import markdown_table_rows

        text = "Intro line.\n\n| Item | Qty | Price |\n|---|---|---|\n| Bandsaw | 2 | 5200 |\n| Crane | 1 | 79500 |\n\nOutro."
        assert markdown_table_rows(text) == [
            ["Item", "Qty", "Price"],
            ["Bandsaw", "2", "5200"],
            ["Crane", "1", "79500"],
        ]

    def test_no_table_returns_none(self):
        from core.chat_draft_classifier import markdown_table_rows

        assert markdown_table_rows("No table, just prose | with pipes.") is None

    def test_slide_outline_detection_and_parse(self):
        from core.chat_draft_classifier import detect_draft_kind, extract_slide_outline

        outline = (
            "Here's the deck:\n\n"
            "Slide 1: Q3 Overview\n- Revenue up 12%\n- New leads 40\n\n"
            "**Slide 2: Pipeline**\nFocus on Baxter renewal.\n\n"
            "Slide 3 — Next steps\nClose the loop with Mark."
        )
        assert detect_draft_kind(outline) == "slides"
        slides = extract_slide_outline(outline)
        assert [s["title"] for s in slides] == ["Q3 Overview", "Pipeline", "Next steps"]
        assert "Revenue up 12%" in slides[0]["content"]
        assert "Baxter renewal" in slides[1]["content"]

    def test_single_slide_mention_is_not_a_deck(self):
        from core.chat_draft_classifier import detect_draft_kind

        assert detect_draft_kind("As I mentioned on slide 4 of the deck, costs rose.") is None

    def test_kind_ordering_slides_beats_code_and_table(self):
        from core.chat_draft_classifier import detect_draft_kind

        mixed = "Slide 1: Demo\n```python\nx = 1\ny = 2\nz = 3\n```\nSlide 2: Wrap"
        assert detect_draft_kind(mixed) == "slides"


class TestOfficeDraftCreation:
    """ExcelManager.create_spreadsheet — the xlsx leg of draft expansion."""

    def test_create_spreadsheet_writes_rows(self, tmp_path, monkeypatch):
        from core.office_service import ExcelManager

        monkeypatch.setenv("ATOM_OFFICE_DIR", str(tmp_path))
        target = str(tmp_path / "chat-test.xlsx")
        res = ExcelManager().create_spreadsheet(target, [["A", "B"], ["1", "2"]])
        assert res["success"] is True

        import openpyxl

        ws = openpyxl.load_workbook(target).active
        assert [[c.value for c in row] for row in ws.iter_rows()] == [["A", "B"], [1, 2]]

    def test_create_spreadsheet_rejects_paths_outside_office_dir(self, tmp_path, monkeypatch):
        from core.office_service import ExcelManager

        monkeypatch.setenv("ATOM_OFFICE_DIR", str(tmp_path / "office"))
        res = ExcelManager().create_spreadsheet(str(tmp_path / "evil.xlsx"), [["A"]])
        assert res["success"] is False
        assert "outside" in res["error"]


# ───────────── narration-tolerant extraction (Sep 1, live incident) ─────────────
# A chat reply wrapping the draft in prose + "---" fences seeded an email
# canvas with a truncated narration sentence as the Subject and EMPTY To/Cc
# even though the draft carried "**To:** jschulz@blumetric.ca" — the top-of-
# message header scan bailed on the prose. The canvas then made the co-editor
# edit request ("include to and cc emails as well") maximally hard: the fields
# it asked to fill were empty, and the polluted subject/body confused both
# patch and replace modes (the "couldn't apply it cleanly" incident).

NARRATION_WRAPPED_DRAFT = """I found the email for Jacob Schulz from BluMetric. It looks like Chandrakant already sent an initial email to him on August 31st, but if you'd like me to resend it due to the OAuth error, I can do that.<br><br>Here's the draft for the first contact email to Jacob Schulz:<br><br>---

**To:** jschulz@blumetric.ca
**Subject:** Brennan Machinery | Following Up on Your Inquiry

Hi Jacob,

Chandrakant here from Brennan Machinery. I received your contact form submission and wanted to reach out.

How can I assist you today? I'd be happy to discuss any equipment needs or answer any questions you may have about our machinery solutions.

Looking forward to hearing from you.

Best,
Chandrakant Sharma
Brennan Machinery Inc

---

This needs your approval — shall I send this email to Jacob Schulz at jschulz@blumetric.ca?
"""


def test_narration_wrapped_draft_extracts_headers_from_fenced_segment():
    draft = extract_email_draft(NARRATION_WRAPPED_DRAFT)
    assert draft is not None
    assert draft["to"] == "jschulz@blumetric.ca"
    assert draft["subject"] == "Brennan Machinery | Following Up on Your Inquiry"
    # the body is the ARTIFACT: no narration before the draft, no approval
    # trailer after the closing fence
    assert draft["body"].startswith("Hi Jacob,")
    assert "approval" not in draft["body"]
    assert "Here's the draft" not in draft["body"]


def test_top_block_draft_still_extracted_unchanged():
    plain = (
        "To: a@b.c\nCc: d@e.f\nSubject: Hello there\n\n"
        "A body long enough to clear the minimum length check for sure."
    )
    draft = extract_email_draft(plain)
    assert draft == {
        "to": "a@b.c", "cc": "d@e.f", "subject": "Hello there",
        "body": "A body long enough to clear the minimum length check for sure.",
    }


def test_pure_prose_without_headers_still_returns_none():
    assert extract_email_draft(
        "Just checking in about the meeting tomorrow. Let me know what works!"
    ) is None


def test_subjectless_fenced_segment_returns_none():
    fenced = "some narration\n\n---\n\nTo: a@b.c\n\nonly a To line, no subject here at all, so not a draft\n\n---\n\nmore prose"
    assert extract_email_draft(fenced) is None
