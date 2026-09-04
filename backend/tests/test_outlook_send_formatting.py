"""Outlook send_email body formatting + cc passthrough.

Regression 2026-09-01: /me/sendMail payloads declare contentType "HTML"
but callers pass editor plain text — Outlook collapsed every newline into
one blob ("poorly formatted … a blob of text"). The body is now converted
to HTML at the sink (plain text escaped + newlines → <br>; existing HTML
passes through untouched), and cc recipients ride through as ccRecipients.
"""

import os
os.environ.setdefault("TESTING", "1")

from unittest.mock import AsyncMock, patch

import pytest

from integrations.outlook_service import OutlookService


def _capture_payload():
    """Class-level patches (mirrors test_covpush_outlook.py): the service
    mock plugin in this suite intercepts instance-level patches and the
    token path, so patch the methods the send path actually uses."""
    captured = {}

    async def fake_graph(self, user_id, endpoint, method="GET", payload=None, **kw):
        captured["endpoint"] = endpoint
        captured["payload"] = payload
        return {"id": "sent-1"}

    async def fake_token(self, user_id):
        return "tok"

    async def fake_scope(self, user_id):
        # a grant that passes the Mail.Send consent pre-check (the test DB
        # may hold a seeded row with a scope that would fail it)
        return "https://graph.microsoft.com/Mail.Send https://graph.microsoft.com/Mail.ReadWrite"

    return captured, (
        patch("integrations.outlook_service.OutlookService._make_graph_request", new=fake_graph),
        patch("integrations.outlook_service.OutlookService._get_access_token", new=fake_token),
        patch("integrations.outlook_service.OutlookService._get_connection_scope", new=fake_scope),
    )


@pytest.mark.asyncio
async def test_plain_text_body_becomes_html_with_line_breaks():
    captured, patches = _capture_payload()
    with patches[0], patches[1], patches[2]:
        await OutlookService().send_email(
            "u-1", ["a@b.com"], "Hi",
            "Dear Mark,\n\nThanks for reaching out.\n\nBest,\nRish",
        )
    body = captured["payload"]["message"]["body"]
    assert body["contentType"] == "HTML"
    assert "<br>" in body["content"]
    assert "Dear Mark," in body["content"]
    assert "Best," in body["content"]
    # no raw newlines survive — that's what produced the text blob
    assert "\n" not in body["content"]


@pytest.mark.asyncio
async def test_html_body_passes_through_untouched():
    captured, patches = _capture_payload()
    with patches[0], patches[1], patches[2]:
        html = "<p>Hello <strong>Mark</strong></p>"
        await OutlookService().send_email("u-1", ["a@b.com"], "Hi", html)
    assert captured["payload"]["message"]["body"]["content"] == html


@pytest.mark.asyncio
async def test_html_escapes_user_text():
    captured, patches = _capture_payload()
    with patches[0], patches[1], patches[2]:
        await OutlookService().send_email(
            "u-1", ["a@b.com"], "Hi", "Price < $100 & shipping",
        )
    content = captured["payload"]["message"]["body"]["content"]
    assert "&lt; $100 &amp; shipping" in content


@pytest.mark.asyncio
async def test_cc_recipients_reach_the_graph_payload():
    captured, patches = _capture_payload()
    with patches[0], patches[1], patches[2]:
        await OutlookService().send_email(
            "u-1", ["a@b.com"], "Hi",
            cc_recipients=["c1@d.com", "c2@d.com"],
            body="line one\nline two",
        )
    msg = captured["payload"]["message"]
    assert msg["ccRecipients"] == [
        {"emailAddress": {"address": "c1@d.com"}},
        {"emailAddress": {"address": "c2@d.com"}},
    ]


def test_mixed_plain_draft_with_html_signature():
    """A plain-text draft with a styled HTML signature appended (CanvasPanel
    applySignature): draft lines convert, signature lines pass verbatim."""
    import os
    os.environ.setdefault("TESTING", "1")
    from integrations.outlook_service import OutlookService

    sig = (
        "Regards,<br><br><strong><em>Rish M.</em></strong><br>"
        "<strong><em>Brennan Machinery Inc.</em></strong>"
    )
    body = "Dear Mark,\n\nThanks for reaching out.\n\n" + sig
    out = OutlookService._body_to_html(body)
    assert "Dear Mark,<br><br>Thanks for reaching out." in out
    assert "<strong><em>Rish M.</em></strong>" in out
    assert "&lt;strong&gt;" not in out  # signature HTML must NOT be escaped


def test_styled_signature_with_link_and_color_survives():
    import os
    os.environ.setdefault("TESTING", "1")
    from integrations.outlook_service import OutlookService

    sig = (
        '<span style="color:#e8590c"><strong><em>How am I doing? </em></strong></span>'
        '<a href="https://www.brennan.ca"><strong><em>Rate my performance</em></strong></a>'
    )
    out = OutlookService._body_to_html("Thanks!\n\n" + sig)
    assert 'href="https://www.brennan.ca"' in out
    assert "color:#e8590c" in out


def test_font_tag_signature_lines_pass_through():
    """execCommand-produced <font> signature lines (size/face/color) must
    survive the line-aware conversion unescaped."""
    import os
    os.environ.setdefault("TESTING", "1")
    from integrations.outlook_service import OutlookService

    sig = '<font size="4" face="Georgia" color="#e8590c">How am I doing?</font>'
    out = OutlookService._body_to_html("Thanks!\n\n" + sig)
    assert '<font size="4" face="Georgia" color="#e8590c">How am I doing?</font>' in out
    assert "&lt;font" not in out


# ─── agent sends carry the user's styled signature (per-user learning) ───

@pytest.mark.asyncio
async def test_agent_send_applies_user_stored_signature():
    """Agent-initiated sends on behalf of a user carry THAT user's styled
    signature, applied at dispatch (the composer path appends client-side;
    the agent path must not skip it)."""
    import contextlib
    from unittest.mock import MagicMock, patch

    from core.canvas_email_service import EmailCanvasService
    from core.user_preference_service import UserPreferenceService

    stored = "<strong><em>Rish M.</em></strong><br>Brennan Machinery Inc."
    svc = EmailCanvasService(MagicMock())

    @contextlib.contextmanager
    def fake_ctx():
        yield MagicMock()

    with patch.object(UserPreferenceService, "get_preference", return_value=stored), \
         patch.object(EmailCanvasService, "record_send"), \
         patch.object(EmailCanvasService, "_extract_signoff", return_value=None), \
         patch("integrations.outlook_service.OutlookService") as MockOS, \
         patch("core.student_learning_service.learn_user_style") as learn_mock:
        MockOS.return_value.send_email = AsyncMock(return_value={"success": True})
        MockOS.return_value.last_send_error = None
        result = await svc.send_email(
            canvas_id="c-1", user_id="u-1", to_emails=["mark@external.test"],
            subject="S", body="Hello from your hire.", agent_id="hire-1",
        )

    assert result["success"] is True
    sent_body = MockOS.return_value.send_email.await_args.kwargs["body"]
    assert stored in sent_body
    assert sent_body.startswith("Hello from your hire.")
    learn_mock.assert_called_once()


@pytest.mark.asyncio
async def test_human_send_does_not_double_apply_signature():
    """Human-clicked sends: the composer already includes the signature —
    no second application without agent_id."""
    import contextlib
    from unittest.mock import MagicMock, patch

    from core.canvas_email_service import EmailCanvasService
    from core.user_preference_service import UserPreferenceService

    svc = EmailCanvasService(MagicMock())

    @contextlib.contextmanager
    def fake_ctx():
        yield MagicMock()

    with patch.object(UserPreferenceService, "get_preference", return_value="<b>Sig</b>"), \
         patch.object(EmailCanvasService, "record_send"), \
         patch("integrations.outlook_service.OutlookService") as MockOS:
        MockOS.return_value.send_email = AsyncMock(return_value={"success": True})
        MockOS.return_value.last_send_error = None
        result = await svc.send_email(
            canvas_id="c-1", user_id="u-1", to_emails=["a@b.com"],
            subject="S", body="Plain body", agent_id=None,
        )

    assert result["success"] is True
    assert MockOS.return_value.send_email.await_args.kwargs["body"] == "Plain body"


def test_closing_tag_lines_pass_unescaped():
    """A line that is ONLY a closing tag (e.g. </div> from a composed HTML
    body) must pass verbatim — previously it failed the tag regex (leading
    slash) and got escaped into visible text in the sent email."""
    import os
    os.environ.setdefault("TESTING", "1")
    from integrations.outlook_service import OutlookService

    out = OutlookService._body_to_html("<div style=\"x\">Hi</div>\n</div>")
    assert out.count("&lt;/div&gt;") == 0
    assert "</div>" in out


# ── HTML tables in the email body (canvas "add table like outlook") ────────

def test_body_to_html_passes_multiline_html_table_through_verbatim():
    """A table inserted in the canvas email composer spans multiple lines
    (<tr>/<td> lines). Every table line carries a known tag → the whole
    body passes through verbatim; escaping would mangle the table into
    visible HTML text in Outlook."""
    body = (
        "<p>Hi Jacob,</p>"
        '<table style="border-collapse: collapse;">'
        "<tbody>"
        "<tr><td>Machine</td><td>Price</td></tr>"
        "<tr><td>Linmac WG-350DSAV</td><td>$12,400</td></tr>"
        "</tbody>"
        "</table>"
    )
    html = OutlookService._body_to_html(body)
    assert "<table" in html and "<td>Machine</td>" in html
    assert "&lt;table&gt;" not in html, "table must not be escaped into visible text"
    assert "12,400" in html


def test_body_to_html_still_converts_plain_text_lines():
    body = "Hi Jacob,\nHere are the specs.\nRegards,\nRish M."
    html = OutlookService._body_to_html(body)
    assert "<br>" in html and "Hi Jacob," in html


def test_body_to_html_rejoins_pretty_printed_table_before_line_pass():
    """Regression 2026-09-03 (canvas ff2dc9ee…): an agent-drafted table is
    pretty-printed one tag per line. The line-aware pass must re-join tags
    split across newlines FIRST — otherwise the table ships as <br>-joined
    fragments (<table>…</table> emptied, <tr> dropped, </tr> escaped into
    visible text) and Outlook renders a flattened line list."""
    body = "\n".join([
        "Hi Jacob,",
        "",
        '<table style="border-collapse: collapse; width: 100%;">',
        "<tr>",
        '<td style="border: 1pt solid #000; padding: 8px;"><strong>Description</strong></td>',
        "<td><strong>Price</strong></td>",
        "</tr>",
        "<tr>",
        "<td>Linmac WG-350DSAV</td>",
        "<td>See Consolidated Price List 2019</td>",
        "</tr>",
        "</table>",
        "",
        "Regards,",
        "Rish M.",
    ])
    html = OutlookService._body_to_html(body)
    assert "<td>Linmac WG-350DSAV</td>" in html
    assert "</td><td>" in html, "cells must stay adjacent inside the row, not <br>-joined"
    assert html.count("<tr>") == 2 and "&lt;/tr&gt;" not in html
    assert "<table" in html and "</table>" in html
    # plain-text lines around the table still convert
    assert "Hi Jacob,<br>" in html and "Regards,<br>" in html
