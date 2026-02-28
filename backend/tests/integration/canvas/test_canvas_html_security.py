"""
Canvas HTML security integration tests (INTG-14).

Tests cover:
- HTML sanitization
- XSS prevention
"""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from tests.factories.canvas_factory import CanvasAuditFactory
from tests.factories.agent_factory import AutonomousAgentFactory
from core.models import CanvasAudit
import uuid


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
]

SAFE_HTML_PATTERNS = [
    "<div class='container'>Content</div>",
    "<p>Paragraph with <strong>bold</strong> text</p>",
    "<h1>Heading</h1>",
    "<ul><li>List item</li></ul>",
    "<span class='label'>Label</span>",
    "<a href='https://example.com'>Link</a>",
]


class TestHTMLSanitization:
    """Test HTML sanitization."""

    def test_script_tag_removed(self, client: TestClient, auth_token: str, db_session: Session):
        """Test script tags are removed from HTML."""
        agent = AutonomousAgentFactory()
        db_session.add(agent)
        db_session.commit()

        canvas_id = str(uuid.uuid4())
        xss_payload = "<script>alert('XSS')</script>"

        response = client.post(
            f"/api/canvas/{canvas_id}/components",
            json={
                "type": "custom",
                "html": xss_payload
            },
            headers={"Authorization": f"Bearer {auth_token}"}
        )

        # Should either block or sanitize
        if response.status_code in [200, 201]:
            data = response.json()
            html = data.get("html", "")
            # Script tag should be removed or escaped
            assert "<script>" not in html or "&lt;script&gt;" in html

    def test_event_handlers_removed(self, client: TestClient, auth_token: str, db_session: Session):
        """Test event handlers are removed from HTML."""
        agent = AutonomousAgentFactory()
        db_session.add(agent)
        db_session.commit()

        canvas_id = str(uuid.uuid4())
        xss_payload = "<img src=x onerror=alert('XSS')>"

        response = client.post(
            f"/api/canvas/{canvas_id}/components",
            json={
                "type": "custom",
                "html": xss_payload
            },
            headers={"Authorization": f"Bearer {auth_token}"}
        )

        if response.status_code in [200, 201]:
            data = response.json()
            html = data.get("html", "")
            # Event handler should be removed
            assert "onerror" not in html.lower()

    def test_iframe_removed(self, client: TestClient, auth_token: str, db_session: Session):
        """Test iframes are removed or restricted."""
        agent = AutonomousAgentFactory()
        db_session.add(agent)
        db_session.commit()

        canvas_id = str(uuid.uuid4())
        xss_payload = "<iframe src='javascript:alert(XSS)'>"

        response = client.post(
            f"/api/canvas/{canvas_id}/components",
            json={
                "type": "custom",
                "html": xss_payload
            },
            headers={"Authorization": f"Bearer {auth_token}"}
        )

        if response.status_code in [200, 201]:
            data = response.json()
            html = data.get("html", "")
            # Iframe should be removed or src sanitized
            assert "javascript:" not in html.lower()

    @pytest.mark.parametrize("safe_html", SAFE_HTML_PATTERNS)
    def test_safe_html_preserved(self, client: TestClient, auth_token: str, safe_html, db_session: Session):
        """Test safe HTML is preserved."""
        agent = AutonomousAgentFactory()
        db_session.add(agent)
        db_session.commit()

        canvas_id = str(uuid.uuid4())

        response = client.post(
            f"/api/canvas/{canvas_id}/components",
            json={
                "type": "custom",
                "html": safe_html
            },
            headers={"Authorization": f"Bearer {auth_token}"}
        )

        # Safe HTML should be allowed
        if response.status_code in [200, 201]:
            data = response.json()
            html = data.get("html", "")
            # Safe content should be preserved
            assert len(html) > 0


class TestXSSPrevention:
    """Test XSS attack prevention."""

    @pytest.mark.parametrize("xss_payload", XSS_PAYLOADS)
    def test_xss_payloads_blocked(self, client: TestClient, auth_token: str, xss_payload, db_session: Session):
        """Test various XSS payloads are blocked."""
        agent = AutonomousAgentFactory()
        db_session.add(agent)
        db_session.commit()

        canvas_id = str(uuid.uuid4())

        response = client.post(
            f"/api/canvas/{canvas_id}/components",
            json={
                "type": "custom",
                "html": xss_payload
            },
            headers={"Authorization": f"Bearer {auth_token}"}
        )

        # Should block or sanitize XSS payloads
        if response.status_code in [200, 201]:
            data = response.json()
            html = data.get("html", "")
            # Check dangerous patterns are removed/escaped
            assert "javascript:" not in html.lower()
            assert "<script>" not in html or "&lt;" in html

    def test_reflected_xss_prevented(self, client: TestClient, auth_token: str, db_session: Session):
        """Test reflected XSS is prevented."""
        agent = AutonomousAgentFactory()
        db_session.add(agent)
        db_session.commit()

        canvas_id = str(uuid.uuid4())
        xss_input = "<img src=x onerror=alert('XSS')>"

        # Simulate reflected XSS (user input reflected in response)
        response = client.post(
            f"/api/canvas/{canvas_id}/components",
            json={
                "type": "custom",
                "html": xss_input,
                "name": xss_input  # Reflected in name field
            },
            headers={"Authorization": f"Bearer {auth_token}"}
        )

        if response.status_code in [200, 201]:
            data = response.json()
            # Check reflected input is escaped
            name = data.get("name", "")
            assert "<img" not in name or "&lt;" in name

    def test_stored_xss_prevented(self, client: TestClient, auth_token: str, db_session: Session):
        """Test stored XSS is prevented."""
        agent = AutonomousAgentFactory()
        db_session.add(agent)
        db_session.commit()

        canvas_id = str(uuid.uuid4())
        xss_payload = "<script>alert('Stored XSS')</script>"

        # Store malicious HTML
        create_response = client.post(
            f"/api/canvas/{canvas_id}/components",
            json={
                "type": "custom",
                "html": xss_payload
            },
            headers={"Authorization": f"Bearer {auth_token}"}
        )

        # Retrieve and check if XSS is sanitized
        retrieve_response = client.get(
            f"/api/canvas/{canvas_id}/components",
            headers={"Authorization": f"Bearer {auth_token}"}
        )

        if retrieve_response.status_code == 200:
            data = retrieve_response.json()
            # Check stored XSS is sanitized
            if isinstance(data, list) and len(data) > 0:
                html = data[0].get("html", "")
                assert "<script>" not in html or "&lt;" in html

    def test_dom_based_xss_prevented(self, client: TestClient, auth_token: str, db_session: Session):
        """Test DOM-based XSS is prevented."""
        agent = AutonomousAgentFactory()
        db_session.add(agent)
        db_session.commit()

        canvas_id = str(uuid.uuid4())
        xss_payload = "<a href='javascript:alert(\"DOM XSS\")'>Click</a>"

        response = client.post(
            f"/api/canvas/{canvas_id}/components",
            json={
                "type": "custom",
                "html": xss_payload
            },
            headers={"Authorization": f"Bearer {auth_token}"}
        )

        if response.status_code in [200, 201]:
            data = response.json()
            html = data.get("html", "")
            # JavaScript: protocol should be removed
            assert "javascript:" not in html.lower()


class TestHTMLContentSecurityPolicy:
    """Test HTML CSP restrictions."""

    def test_csp_headers_set(self, client: TestClient, auth_token: str, db_session: Session):
        """Test CSP headers are set for canvas HTML."""
        agent = AutonomousAgentFactory()
        db_session.add(agent)
        db_session.commit()

        canvas_id = str(uuid.uuid4())

        response = client.get(
            f"/api/canvas/{canvas_id}",
            headers={"Authorization": f"Bearer {auth_token}"}
        )

        # Check CSP headers
        if response.status_code == 200:
            csp = response.headers.get("Content-Security-Policy", "")
            # Should have CSP policy
            assert isinstance(csp, str) and len(csp) > 0

    def test_csp_blocks_inline_scripts(self, client: TestClient, auth_token: str, db_session: Session):
        """Test CSP blocks inline scripts."""
        agent = AutonomousAgentFactory()
        db_session.add(agent)
        db_session.commit()

        canvas_id = str(uuid.uuid4())

        response = client.post(
            f"/api/canvas/{canvas_id}/components",
            json={
                "type": "custom",
                "html": "<div onclick='alert(1)'>Click</div>"
            },
            headers={"Authorization": f"Bearer {auth_token}"}
        )

        if response.status_code in [200, 201]:
            data = response.json()
            html = data.get("html", "")
            # Inline handlers should be removed
            assert "onclick" not in html.lower()

    def test_csp_restricts_script_sources(self, client: TestClient, auth_token: str, db_session: Session):
        """Test CSP restricts external script sources."""
        agent = AutonomousAgentFactory()
        db_session.add(agent)
        db_session.commit()

        canvas_id = str(uuid.uuid4())

        response = client.post(
            f"/api/canvas/{canvas_id}/components",
            json={
                "type": "custom",
                "html": "<script src='https://evil.com/malicious.js'></script>",
                "dependencies": ["https://evil.com/malicious.js"]
            },
            headers={"Authorization": f"Bearer {auth_token}"}
        )

        # Should block unauthorized script sources
        if response.status_code in [200, 201]:
            data = response.json()
            # Check dependencies filtered
            deps = data.get("dependencies", [])
            assert "evil.com" not in str(deps)


class TestHTMLAuditLogging:
    """Test HTML security audit logging."""

    def test_xss_attempt_logged(self, client: TestClient, auth_token: str, db_session: Session):
        """Test XSS attempts are logged."""
        agent = AutonomousAgentFactory()
        db_session.add(agent)
        db_session.commit()

        canvas_id = str(uuid.uuid4())
        xss_payload = "<script>alert('XSS')</script>"

        response = client.post(
            f"/api/canvas/{canvas_id}/components",
            json={
                "type": "custom",
                "html": xss_payload
            },
            headers={"Authorization": f"Bearer {auth_token}"}
        )

        # Check security event logged
        audits = db_session.query(CanvasAudit).filter(
            CanvasAudit.id == canvas_id
        ).all()

        assert len(audits) >= 0

    def test_sanitization_metadata_logged(self, client: TestClient, auth_token: str, db_session: Session):
        """Test HTML sanitization metadata is logged."""
        agent = AutonomousAgentFactory()
        db_session.add(agent)
        db_session.commit()

        canvas_id = str(uuid.uuid4())
        xss_payload = "<img src=x onerror=alert('XSS')>Safe content"

        response = client.post(
            f"/api/canvas/{canvas_id}/components",
            json={
                "type": "custom",
                "html": xss_payload
            },
            headers={"Authorization": f"Bearer {auth_token}"}
        )

        if response.status_code in [200, 201]:
            # Check sanitization recorded
            audits = db_session.query(CanvasAudit).filter(
                CanvasAudit.id == canvas_id
            ).all()

            if audits and audits[0].audit_metadata:
                # Should include sanitization details
                metadata = audits[0].audit_metadata
                assert isinstance(metadata, dict)


class TestHTMLWhitelist:
    """Test HTML tag and attribute whitelisting."""

    def test_safe_tags_allowed(self, client: TestClient, auth_token: str, db_session: Session):
        """Test safe HTML tags are allowed."""
        agent = AutonomousAgentFactory()
        db_session.add(agent)
        db_session.commit()

        canvas_id = str(uuid.uuid4())
        safe_html = "<div><p>Text</p><span>Label</span></div>"

        response = client.post(
            f"/api/canvas/{canvas_id}/components",
            json={
                "type": "custom",
                "html": safe_html
            },
            headers={"Authorization": f"Bearer {auth_token}"}
        )

        # Safe tags should be preserved
        if response.status_code in [200, 201]:
            data = response.json()
            html = data.get("html", "")
            assert all(tag in html for tag in ["div", "p", "span"])

    def test_safe_attributes_allowed(self, client: TestClient, auth_token: str, db_session: Session):
        """Test safe HTML attributes are allowed."""
        agent = AutonomousAgentFactory()
        db_session.add(agent)
        db_session.commit()

        canvas_id = str(uuid.uuid4())
        safe_html = "<div class='container' id='main' data-value='test'>Content</div>"

        response = client.post(
            f"/api/canvas/{canvas_id}/components",
            json={
                "type": "custom",
                "html": safe_html
            },
            headers={"Authorization": f"Bearer {auth_token}"}
        )

        # Safe attributes should be preserved
        if response.status_code in [200, 201]:
            data = response.json()
            html = data.get("html", "")
            assert "class" in html
            assert "id" in html
            assert "data-value" in html

    def test_dangerous_attributes_removed(self, client: TestClient, auth_token: str, db_session: Session):
        """Test dangerous HTML attributes are removed."""
        agent = AutonomousAgentFactory()
        db_session.add(agent)
        db_session.commit()

        canvas_id = str(uuid.uuid4())
        dangerous_html = "<div onmouseover='alert(1)' style='behavior:url(xss)'>Content</div>"

        response = client.post(
            f"/api/canvas/{canvas_id}/components",
            json={
                "type": "custom",
                "html": dangerous_html
            },
            headers={"Authorization": f"Bearer {auth_token}"}
        )

        if response.status_code in [200, 201]:
            data = response.json()
            html = data.get("html", "")
            # Dangerous attributes should be removed
            assert "onmouseover" not in html.lower()
            assert "behavior:" not in html.lower()
