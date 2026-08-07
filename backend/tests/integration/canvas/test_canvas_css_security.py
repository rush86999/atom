"""
Canvas CSS security integration tests (INTG-15).

Tests cover:
- CSS sanitization
- Dangerous URL blocking

CSS reaches a canvas through the same server-side gate as HTML:
`PUT /api/canvas/{canvas_id}` bodies pass through
`core.security.middleware.InputValidationMiddleware`, which rejects
script-carrying and execution-vector CSS (javascript:/vbscript: URLs,
behavior/binding/expression IE-era execution properties) with HTTP 400
before persistence. The frontend additionally sanitizes rendered content
via DOMPurify (`frontend-nextjs/lib/sanitize.ts`).

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


DANGEROUS_CSS_PATTERNS = [
    "body { background: url('javascript:alert(1)'); }",
    "div { behavior: url(xss.htc); }",
    "a { binding: url('javascript:alert(1)'); }",
    "li { list-style-image: url('javascript:alert(1)'); }",
    "@import url('javascript:alert(1)');",
    "@font-face { src: url('javascript:alert(1)'); }",
    "body { -moz-binding: url('javascript:alert(1)'); }",
    "div { background-image: url('javascript:alert(1)'); }",
    # Entity-encoded bypasses: browsers decode character references when
    # resolving CSS urls(), so these are the same payloads as the literals.
    "body { background: url('jav&#x61;script:alert(1)'); }",
    "div { width: expression(alert(1)); }",
    "body { background: url('vbscript:msgbox(1)'); }",
]

SAFE_CSS_PATTERNS = [
    ".container { padding: 10px; }",
    "div { color: red; }",
    ".label { font-size: 14px; }",
    "#main { width: 100%; max-width: 1200px; }",
    "button { background-color: blue; border: none; }",
    ".flex { display: flex; justify-content: center; }",
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


class TestCSSSanitization:
    """Test CSS sanitization on the canvas content-write path."""

    def test_javascript_url_removed(self, client: TestClient, canvas_user, db_session: Session):
        """Test javascript: URLs in CSS are rejected before persistence."""
        dangerous_css = "body { background: url('javascript:alert(1)'); }"
        _, response = _write_canvas_content(
            client, db_session, canvas_user, {"css": dangerous_css}
        )
        assert response.status_code == 400

    def test_behavior_removed(self, client: TestClient, canvas_user, db_session: Session):
        """Test behavior property is rejected (IE CSS-execution vector)."""
        dangerous_css = "div { behavior: url(xss.htc); }"
        _, response = _write_canvas_content(
            client, db_session, canvas_user, {"css": dangerous_css}
        )
        assert response.status_code == 400

    def test_expression_removed(self, client: TestClient, canvas_user, db_session: Session):
        """Test CSS expressions are rejected (IE CSS-execution vector)."""
        dangerous_css = "div { width: expression(alert(1)); }"
        _, response = _write_canvas_content(
            client, db_session, canvas_user, {"css": dangerous_css}
        )
        assert response.status_code == 400

    def test_binding_removed(self, client: TestClient, canvas_user, db_session: Session):
        """Test CSS binding property is rejected (IE CSS-execution vector)."""
        dangerous_css = "a { binding: url('javascript:alert(1)'); }"
        _, response = _write_canvas_content(
            client, db_session, canvas_user, {"css": dangerous_css}
        )
        assert response.status_code == 400

    @pytest.mark.parametrize("safe_css", SAFE_CSS_PATTERNS)
    def test_safe_css_preserved(self, client: TestClient, canvas_user, db_session: Session, safe_css):
        """Test safe CSS is accepted and round-trips through the API."""
        canvas_id, response = _write_canvas_content(
            client, db_session, canvas_user, {"css": safe_css}
        )
        assert response.status_code == 200

        read = client.get(f"/api/canvas/{canvas_id}")
        assert read.status_code == 200
        stored = read.json().get("content", {})
        css = stored.get("css", "") if isinstance(stored, dict) else str(stored)
        assert css == safe_css


class TestDangerousURLBlocking:
    """Test blocking of dangerous URLs in CSS."""

    @pytest.mark.parametrize("dangerous_css", DANGEROUS_CSS_PATTERNS)
    def test_dangerous_urls_blocked(self, client: TestClient, canvas_user, db_session: Session, dangerous_css):
        """Test various dangerous URL patterns are rejected (never persisted)."""
        _, response = _write_canvas_content(
            client, db_session, canvas_user, {"css": dangerous_css}
        )
        assert response.status_code == 400

    def test_data_url_blocked(self, client: TestClient, canvas_user, db_session: Session):
        """Test script-carrying data: URLs in CSS are rejected."""
        data_url_css = "body { background: url('data:image/svg+xml,<script>alert(1)</script>'); }"
        _, response = _write_canvas_content(
            client, db_session, canvas_user, {"css": data_url_css}
        )
        assert response.status_code == 400

    def test_vbscript_blocked(self, client: TestClient, canvas_user, db_session: Session):
        """Test vbscript: URLs in CSS are rejected (IE execution vector)."""
        vbscript_css = "body { background: url('vbscript:msgbox(1)'); }"
        _, response = _write_canvas_content(
            client, db_session, canvas_user, {"css": vbscript_css}
        )
        assert response.status_code == 400


class TestCSSAtRules:
    """Test CSS @-rules security."""

    def test_dangerous_import_blocked(self, client: TestClient, canvas_user, db_session: Session):
        """Test dangerous @import rules are rejected."""
        import_css = "@import url('javascript:alert(1)');"
        _, response = _write_canvas_content(
            client, db_session, canvas_user, {"css": import_css}
        )
        assert response.status_code == 400

    def test_safe_import_allowed(self, client: TestClient, canvas_user, db_session: Session):
        """Test safe https @import rules are allowed."""
        import_css = "@import url('https://cdn.example.com/styles.css');"
        _, response = _write_canvas_content(
            client, db_session, canvas_user, {"css": import_css}
        )
        assert response.status_code == 200

    def test_font_face_security(self, client: TestClient, canvas_user, db_session: Session):
        """Test dangerous @font-face src URLs are rejected."""
        font_css = "@font-face { src: url('javascript:alert(1)'); }"
        _, response = _write_canvas_content(
            client, db_session, canvas_user, {"css": font_css}
        )
        assert response.status_code == 400


class TestCSSPropertyFiltering:
    """Test CSS property filtering."""

    def test_safe_properties_allowed(self, client: TestClient, canvas_user, db_session: Session):
        """Test safe CSS properties are preserved end-to-end."""
        safe_css = """
        .container {
            padding: 10px;
            margin: 20px;
            color: #333;
            background-color: #fff;
            font-size: 14px;
            display: flex;
        }
        """
        canvas_id, response = _write_canvas_content(
            client, db_session, canvas_user, {"css": safe_css}
        )
        assert response.status_code == 200

        read = client.get(f"/api/canvas/{canvas_id}")
        stored = read.json().get("content", {})
        css = stored.get("css", "") if isinstance(stored, dict) else str(stored)
        assert "padding:" in css
        assert "color:" in css
        assert "display:" in css

    def test_moz_binding_blocked(self, client: TestClient, canvas_user, db_session: Session):
        """Test -moz-binding CSS is rejected (javascript: URL)."""
        binding_css = "div { -moz-binding: url('javascript:alert(1)'); }"
        _, response = _write_canvas_content(
            client, db_session, canvas_user, {"css": binding_css}
        )
        assert response.status_code == 400


class TestCSSAuditLogging:
    """Test CSS security audit logging."""

    def test_dangerous_css_logged(self, client: TestClient, canvas_user, db_session: Session):
        """Test dangerous CSS attempts are rejected and never persisted."""
        canvas_id = _create_canvas(db_session, str(canvas_user.id))
        dangerous_css = "body { background: url('javascript:alert(1)'); }"

        response = client.put(
            f"/api/canvas/{canvas_id}",
            json={"css": dangerous_css},
        )
        assert response.status_code == 400

        audits = db_session.query(CanvasAudit).filter(
            CanvasAudit.canvas_id == canvas_id
        ).all()
        assert len(audits) >= 1
        for audit in audits:
            assert "javascript:alert(1)" not in str(audit.details_json)

    def test_sanitization_metadata(self, client: TestClient, canvas_user, db_session: Session):
        """Test safe CSS writes land in the audit trail with metadata."""
        canvas_id, response = _write_canvas_content(
            client, db_session, canvas_user, {"css": "div { color: red; }"}
        )
        assert response.status_code == 200

        audits = db_session.query(CanvasAudit).filter(
            CanvasAudit.canvas_id == canvas_id
        ).all()
        assert len(audits) >= 1
        assert isinstance(audits[0].details_json, dict)


class TestCSSEscaping:
    """Test CSS content escaping (style-tag breakout)."""

    def test_css_content_escaped(self, client: TestClient, canvas_user, db_session: Session):
        """Test </style> breakout via content property is rejected."""
        content_css = "div:before { content: '</style><script>alert(1)</script>'; }"
        _, response = _write_canvas_content(
            client, db_session, canvas_user, {"css": content_css}
        )
        assert response.status_code == 400

    def test_css_comments_sanitized(self, client: TestClient, canvas_user, db_session: Session):
        """Test style-tag breakout hidden in comments is rejected."""
        comment_css = "/* </style><script>alert(1)</script> */ div { color: red; }"
        _, response = _write_canvas_content(
            client, db_session, canvas_user, {"css": comment_css}
        )
        assert response.status_code == 400
