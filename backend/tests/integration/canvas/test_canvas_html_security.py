"""
Canvas HTML security integration tests (INTG-14).

Tests cover:
- HTML sanitization
- XSS prevention

These suites exercise the live server-side canvas content gate:
`PUT /api/canvas/{canvas_id}` writes canvas content (the documented write
path used by the agent tools via `tools/canvas_crud_tool`) and every body
passes through `core.security.middleware.InputValidationMiddleware`, which
rejects script/handler/javascript: payloads with HTTP 400 before they can
be persisted to the canvas audit trail. The frontend additionally renders
all canvas HTML through DOMPurify (`frontend-nextjs/lib/sanitize.ts`).

The former `POST /api/canvas/{canvas_id}/components` endpoint no longer
exists (removed with the component-installation refactor), so the payloads
are exercised against the actual content-write surface.
"""
import uuid
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from core.auth import get_current_user
from core.models import Canvas, CanvasAudit
from main_api_app import app
from tests.factories.user_factory import AdminUserFactory


XSS_PAYLOADS = [
    "<script>alert('XSS')</script>",
    "<img src=x onerror=alert('XSS')>",
    "<svg onload=alert('XSS')>",
    "<iframe src='javascript:alert(XSS)'>",
    "<body onload=alert('XSS')>",
    "<input onfocus=alert('XSS') autofocus>",
    "<select onfocus=alert('XSS') autofocus>",
    "<textarea onfocus=alert('XSS') autofocus>",
    '<marquee onstart=alert("XSS")>',
    '<isindex formaction="javascript:alert(XSS)" type="submit">',
    'javascript:alert("XSS")',
    '<a href="javascript:alert(\'XSS\')">click</a>',
    # Entity-encoded bypasses: browsers decode character references during
    # HTML parsing, so these are the same payloads as the literal forms.
    "<img src=x onerror&#x3d;alert(1)>",
    "<a href='jav&#x61;script:alert(1)'>click</a>",
]

SAFE_HTML_PATTERNS = [
    "<div class='container'>Content</div>",
    "<p>Paragraph with <strong>bold</strong> text</p>",
    "<h1>Heading</h1>",
    "<ul><li>List item</li></ul>",
    "<span class='label'>Label</span>",
    "<a href='https://example.com'>Link</a>",
]


def _create_canvas(db_session: Session, user_id: str) -> str:
    """Create a canvas owned by ``user_id`` (Canvas row + initial audit row).

    Mirrors the audit-trail source-of-truth pattern used by the canvas tools:
    the Canvas row carries ownership, the CanvasAudit row carries content.
    """
    canvas_id = str(uuid.uuid4())
    db_session.add(Canvas(
        id=canvas_id,
        tenant_id="default",
        workspace_id="default",
        created_by=user_id,
        name="Security test canvas",
        canvas_type="generic",
        content={},
        status="active",
        last_edited_by=user_id,
        last_edited_at=datetime.now(timezone.utc),
    ))
    db_session.add(CanvasAudit(
        canvas_id=canvas_id,
        tenant_id="default",
        canvas_type="generic",
        action_type="present",
        user_id=user_id,
        details_json={"content": {}, "title": "Security test"},
        # Back-dated: the canvas tools read the audit trail as the source of
        # truth ordered by created_at desc, and SQLite CURRENT_TIMESTAMP only
        # has second resolution — a same-second "present" row would tie with
        # the "update" row and make the read-back nondeterministic.
        created_at=datetime.now(timezone.utc) - timedelta(seconds=60),
    ))
    db_session.commit()
    return canvas_id


@pytest.fixture
def canvas_user(client: TestClient, db_session: Session):
    """Pin a single user for the whole test.

    The shared ``client`` fixture mocks ``get_current_user`` with a *new*
    user per request, which would break the canvas ownership (IDOR) check on
    every read/update. Overriding the dependency with one fixed user keeps
    the ownership gate exercised for real.
    """
    user = AdminUserFactory(_session=db_session)
    app.dependency_overrides[get_current_user] = lambda: user
    yield user


def _write_canvas_content(client: TestClient, db_session: Session, user, payload):
    """PUT ``payload`` as the canvas content body; return (id, response).

    ``PUT /api/canvas/{canvas_id}`` binds the entire request body to the
    ``content`` dict (the documented write path used by the canvas tools), so
    the body IS the content: ``{"html": ..., "css": ...}``.
    """
    canvas_id = _create_canvas(db_session, str(user.id))
    response = client.put(f"/api/canvas/{canvas_id}", json=payload)
    return canvas_id, response


class TestHTMLSanitization:
    """Test HTML sanitization on the canvas content-write path."""

    def test_script_tag_removed(self, client: TestClient, canvas_user, db_session: Session):
        """Test script tags are rejected before persistence."""
        _, response = _write_canvas_content(
            client, db_session, canvas_user, {"html": "<script>alert('XSS')</script>"}
        )
        assert response.status_code == 400

    def test_event_handlers_removed(self, client: TestClient, canvas_user, db_session: Session):
        """Test event handlers are rejected before persistence."""
        _, response = _write_canvas_content(
            client, db_session, canvas_user, {"html": "<img src=x onerror=alert('XSS')>"}
        )
        assert response.status_code == 400

    def test_iframe_removed(self, client: TestClient, canvas_user, db_session: Session):
        """Test javascript: iframes are rejected before persistence."""
        _, response = _write_canvas_content(
            client, db_session, canvas_user, {"html": "<iframe src='javascript:alert(XSS)'>"}
        )
        assert response.status_code == 400

    @pytest.mark.parametrize("safe_html", SAFE_HTML_PATTERNS)
    def test_safe_html_preserved(self, client: TestClient, canvas_user, db_session: Session, safe_html):
        """Test safe HTML is accepted and round-trips through the API."""
        canvas_id, response = _write_canvas_content(
            client, db_session, canvas_user, {"html": safe_html}
        )
        assert response.status_code == 200

        read = client.get(f"/api/canvas/{canvas_id}")
        assert read.status_code == 200
        stored = read.json().get("content", {})
        html = stored.get("html", "") if isinstance(stored, dict) else str(stored)
        assert html == safe_html


class TestXSSPrevention:
    """Test XSS attack prevention."""

    @pytest.mark.parametrize("xss_payload", XSS_PAYLOADS)
    def test_xss_payloads_blocked(self, client: TestClient, canvas_user, db_session: Session, xss_payload):
        """Test various XSS payloads are rejected (never persisted)."""
        _, response = _write_canvas_content(
            client, db_session, canvas_user, {"html": xss_payload}
        )
        assert response.status_code == 400

    def test_reflected_xss_prevented(self, client: TestClient, canvas_user, db_session: Session):
        """Test XSS reflected via query parameters is rejected."""
        canvas_id = _create_canvas(db_session, str(canvas_user.id))
        xss_input = "<img src=x onerror=alert('XSS')>"
        response = client.put(
            f"/api/canvas/{canvas_id}",
            params={"title": xss_input},
            json={"html": "<p>safe</p>"},
        )
        assert response.status_code == 400

    def test_stored_xss_prevented(self, client: TestClient, canvas_user, db_session: Session):
        """Test a blocked payload is never persisted to the canvas audit trail."""
        canvas_id = _create_canvas(db_session, str(canvas_user.id))
        xss_payload = "<script>alert('Stored XSS')</script>"

        response = client.put(
            f"/api/canvas/{canvas_id}",
            json={"html": xss_payload},
        )
        assert response.status_code == 400

        read = client.get(f"/api/canvas/{canvas_id}")
        assert read.status_code == 200
        assert "Stored XSS" not in str(read.json().get("content", {}))

    def test_dom_based_xss_prevented(self, client: TestClient, canvas_user, db_session: Session):
        """Test javascript: URLs in DOM-injection vectors are rejected."""
        _, response = _write_canvas_content(
            client, db_session, canvas_user, {"html": "<a href='javascript:alert(\"DOM XSS\")'>Click</a>"}
        )
        assert response.status_code == 400


class TestHTMLContentSecurityPolicy:
    """Test CSP / security headers around canvas HTML."""

    def test_csp_headers_set(self, client: TestClient, canvas_user, db_session: Session):
        """Test canvas responses carry security headers and the UI carries a CSP."""
        canvas_id = _create_canvas(db_session, str(canvas_user.id))
        response = client.get(f"/api/canvas/{canvas_id}")
        assert response.status_code == 200
        # API responses: anti-MIME-sniffing + clickjacking headers.
        assert response.headers.get("X-Content-Type-Options") == "nosniff"
        assert response.headers.get("X-Frame-Options") == "DENY"

        # The canvas UI surface (non-API) carries the hardened CSP.
        ui = client.get("/")
        assert ui.status_code == 200
        csp = ui.headers.get("Content-Security-Policy", "")
        assert "script-src" in csp
        assert "style-src" in csp
        assert "connect-src" in csp

    def test_csp_blocks_inline_scripts(self, client: TestClient, canvas_user, db_session: Session):
        """Test inline event handlers are rejected before persistence."""
        _, response = _write_canvas_content(
            client, db_session, canvas_user, {"html": "<div onclick='alert(1)'>Click</div>"}
        )
        assert response.status_code == 400

    def test_csp_restricts_script_sources(self, client: TestClient, canvas_user, db_session: Session):
        """Test external script sources are rejected before persistence."""
        _, response = _write_canvas_content(
            client, db_session, canvas_user, {"html": "<script src='https://evil.com/malicious.js'></script>"}
        )
        assert response.status_code == 400


class TestHTMLAuditLogging:
    """Test HTML security audit logging."""

    def test_xss_attempt_logged(self, client: TestClient, canvas_user, db_session: Session):
        """Test XSS attempts are rejected and never written to the audit trail."""
        canvas_id = _create_canvas(db_session, str(canvas_user.id))
        xss_payload = "<script>alert('XSS')</script>"

        response = client.put(
            f"/api/canvas/{canvas_id}",
            json={"html": xss_payload},
        )
        assert response.status_code == 400

        audits = db_session.query(CanvasAudit).filter(
            CanvasAudit.canvas_id == canvas_id
        ).all()
        assert len(audits) >= 1
        for audit in audits:
            assert "alert('XSS')" not in str(audit.details_json)

    def test_sanitization_metadata_logged(self, client: TestClient, canvas_user, db_session: Session):
        """Test safe content writes land in the audit trail with metadata."""
        canvas_id, response = _write_canvas_content(
            client, db_session, canvas_user, {"html": "<img src=x onerror=alert('XSS')>Safe content"}
        )
        assert response.status_code == 400

        audits = db_session.query(CanvasAudit).filter(
            CanvasAudit.canvas_id == canvas_id
        ).all()
        assert len(audits) >= 1
        assert isinstance(audits[0].details_json, dict)

class TestHTMLWhitelist:
    """Test HTML tag and attribute whitelisting behavior."""

    def test_safe_tags_allowed(self, client: TestClient, canvas_user, db_session: Session):
        """Test safe HTML tags are preserved end-to-end."""
        safe_html = "<div><p>Text</p><span>Label</span></div>"
        canvas_id, response = _write_canvas_content(
            client, db_session, canvas_user, {"html": safe_html}
        )
        assert response.status_code == 200

        read = client.get(f"/api/canvas/{canvas_id}")
        stored = read.json().get("content", {})
        html = stored.get("html", "") if isinstance(stored, dict) else str(stored)
        assert all(tag in html for tag in ["div", "p", "span"])

    def test_safe_attributes_allowed(self, client: TestClient, canvas_user, db_session: Session):
        """Test safe HTML attributes are preserved end-to-end."""
        safe_html = "<div class='container' id='main' data-value='test'>Content</div>"
        canvas_id, response = _write_canvas_content(
            client, db_session, canvas_user, {"html": safe_html}
        )
        assert response.status_code == 200

        read = client.get(f"/api/canvas/{canvas_id}")
        stored = read.json().get("content", {})
        html = stored.get("html", "") if isinstance(stored, dict) else str(stored)
        assert "class" in html
        assert "id" in html
        assert "data-value" in html

    def test_dangerous_attributes_removed(self, client: TestClient, canvas_user, db_session: Session):
        """Test dangerous HTML attributes are rejected before persistence."""
        dangerous_html = "<div onmouseover='alert(1)' style='behavior:url(xss)'>Content</div>"
        _, response = _write_canvas_content(
            client, db_session, canvas_user, {"html": dangerous_html}
        )
        assert response.status_code == 400
