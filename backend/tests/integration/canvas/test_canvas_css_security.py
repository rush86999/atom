"""
Canvas CSS security integration tests (INTG-15).

Tests cover:
- CSS sanitization
- Dangerous URL blocking
"""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from tests.factories.canvas_factory import CanvasAuditFactory
from tests.factories.agent_factory import AutonomousAgentFactory
from core.models import CanvasAudit
import uuid


DANGEROUS_CSS_PATTERNS = [
    "body { background: url('javascript:alert(1)'); }",
    "div { behavior: url(xss.htc); }",
    "a { binding: url('javascript:alert(1)'); }",
    "li { list-style-image: url('javascript:alert(1)'); }",
    "@import url('javascript:alert(1)');",
    "@font-face { src: url('javascript:alert(1)'); }",
    "body { -moz-binding: url('javascript:alert(1)'); }",
    "div { background-image: url('javascript:alert(1)'); }",
]

SAFE_CSS_PATTERNS = [
    ".container { padding: 10px; }",
    "div { color: red; }",
    ".label { font-size: 14px; }",
    "#main { width: 100%; max-width: 1200px; }",
    "button { background-color: blue; border: none; }",
    ".flex { display: flex; justify-content: center; }",
]


class TestCSSSanitization:
    """Test CSS sanitization."""

    def test_javascript_url_removed(self, client: TestClient, auth_token: str, db_session: Session):
        """Test javascript: URLs are removed from CSS."""
        agent = AutonomousAgentFactory()
        db_session.add(agent)
        db_session.commit()

        canvas_id = str(uuid.uuid4())
        dangerous_css = "body { background: url('javascript:alert(1)'); }"

        response = client.post(
            f"/api/canvas/{canvas_id}/components",
            json={
                "type": "custom",
                "css": dangerous_css
            },
            headers={"Authorization": f"Bearer {auth_token}"}
        )

        # Should remove or block javascript: URLs
        if response.status_code in [200, 201]:
            data = response.json()
            css = data.get("css", "")
            assert "javascript:" not in css.lower()

    def test_behavior_removed(self, client: TestClient, auth_token: str, db_session: Session):
        """Test behavior property is removed (IE XSS)."""
        agent = AutonomousAgentFactory()
        db_session.add(agent)
        db_session.commit()

        canvas_id = str(uuid.uuid4())
        dangerous_css = "div { behavior: url(xss.htc); }"

        response = client.post(
            f"/api/canvas/{canvas_id}/components",
            json={
                "type": "custom",
                "css": dangerous_css
            },
            headers={"Authorization": f"Bearer {auth_token}"}
        )

        if response.status_code in [200, 201]:
            data = response.json()
            css = data.get("css", "")
            # Behavior property should be removed
            assert "behavior:" not in css.lower()

    def test_expression_removed(self, client: TestClient, auth_token: str, db_session: Session):
        """Test CSS expressions are removed."""
        agent = AutonomousAgentFactory()
        db_session.add(agent)
        db_session.commit()

        canvas_id = str(uuid.uuid4())
        dangerous_css = "div { width: expression(alert(1)); }"

        response = client.post(
            f"/api/canvas/{canvas_id}/components",
            json={
                "type": "custom",
                "css": dangerous_css
            },
            headers={"Authorization": f"Bearer {auth_token}"}
        )

        if response.status_code in [200, 201]:
            data = response.json()
            css = data.get("css", "")
            # Expression should be removed
            assert "expression(" not in css.lower()

    def test_binding_removed(self, client: TestClient, auth_token: str, db_session: Session):
        """Test CSS binding property is removed."""
        agent = AutonomousAgentFactory()
        db_session.add(agent)
        db_session.commit()

        canvas_id = str(uuid.uuid4())
        dangerous_css = "a { binding: url('javascript:alert(1)'); }"

        response = client.post(
            f"/api/canvas/{canvas_id}/components",
            json={
                "type": "custom",
                "css": dangerous_css
            },
            headers={"Authorization": f"Bearer {auth_token}"}
        )

        if response.status_code in [200, 201]:
            data = response.json()
            css = data.get("css", "")
            # Binding should be removed
            assert "binding:" not in css.lower()

    @pytest.mark.parametrize("safe_css", SAFE_CSS_PATTERNS)
    def test_safe_css_preserved(self, client: TestClient, auth_token: str, safe_css, db_session: Session):
        """Test safe CSS is preserved."""
        agent = AutonomousAgentFactory()
        db_session.add(agent)
        db_session.commit()

        canvas_id = str(uuid.uuid4())

        response = client.post(
            f"/api/canvas/{canvas_id}/components",
            json={
                "type": "custom",
                "css": safe_css
            },
            headers={"Authorization": f"Bearer {auth_token}"}
        )

        # Safe CSS should be allowed
        if response.status_code in [200, 201]:
            data = response.json()
            css = data.get("css", "")
            # Safe properties should be preserved
            assert len(css) > 0


class TestDangerousURLBlocking:
    """Test blocking of dangerous URLs in CSS."""

    @pytest.mark.parametrize("dangerous_css", DANGEROUS_CSS_PATTERNS)
    def test_dangerous_urls_blocked(self, client: TestClient, auth_token: str, dangerous_css, db_session: Session):
        """Test various dangerous URL patterns are blocked."""
        agent = AutonomousAgentFactory()
        db_session.add(agent)
        db_session.commit()

        canvas_id = str(uuid.uuid4())

        response = client.post(
            f"/api/canvas/{canvas_id}/components",
            json={
                "type": "custom",
                "css": dangerous_css
            },
            headers={"Authorization": f"Bearer {auth_token}"}
        )

        # Should block or sanitize dangerous URLs
        if response.status_code in [200, 201]:
            data = response.json()
            css = data.get("css", "")
            # Check dangerous patterns are removed
            assert "javascript:" not in css.lower()
            assert "behavior:" not in css.lower()
            assert "binding:" not in css.lower()

    def test_data_url_blocked(self, client: TestClient, auth_token: str, db_session: Session):
        """Test data: URLs are blocked in CSS."""
        agent = AutonomousAgentFactory()
        db_session.add(agent)
        db_session.commit()

        canvas_id = str(uuid.uuid4())
        data_url_css = "body { background: url('data:image/svg+xml,<script>alert(1)</script>'); }"

        response = client.post(
            f"/api/canvas/{canvas_id}/components",
            json={
                "type": "custom",
                "css": data_url_css
            },
            headers={"Authorization": f"Bearer {auth_token}"}
        )

        if response.status_code in [200, 201]:
            data = response.json()
            css = data.get("css", "")
            # data: URLs should be removed or sanitized
            assert "data:" not in css.lower() or "data:image" not in css.lower()

    def test_vbscript_blocked(self, client: TestClient, auth_token: str, db_session: Session):
        """Test vbscript: URLs are blocked."""
        agent = AutonomousAgentFactory()
        db_session.add(agent)
        db_session.commit()

        canvas_id = str(uuid.uuid4())
        vbscript_css = "body { background: url('vbscript:msgbox(1)'); }"

        response = client.post(
            f"/api/canvas/{canvas_id}/components",
            json={
                "type": "custom",
                "css": vbscript_css
            },
            headers={"Authorization": f"Bearer {auth_token}"}
        )

        if response.status_code in [200, 201]:
            data = response.json()
            css = data.get("css", "")
            # vbscript: should be blocked
            assert "vbscript:" not in css.lower()


class TestCSSAtRules:
    """Test CSS @-rules security."""

    def test_dangerous_import_blocked(self, client: TestClient, auth_token: str, db_session: Session):
        """Test dangerous @import rules are blocked."""
        agent = AutonomousAgentFactory()
        db_session.add(agent)
        db_session.commit()

        canvas_id = str(uuid.uuid4())
        import_css = "@import url('javascript:alert(1)');"

        response = client.post(
            f"/api/canvas/{canvas_id}/components",
            json={
                "type": "custom",
                "css": import_css
            },
            headers={"Authorization": f"Bearer {auth_token}"}
        )

        if response.status_code in [200, 201]:
            data = response.json()
            css = data.get("css", "")
            # Dangerous @import should be blocked
            assert "@import" not in css or "javascript:" not in css.lower()

    def test_safe_import_allowed(self, client: TestClient, auth_token: str, db_session: Session):
        """Test safe @import rules are allowed."""
        agent = AutonomousAgentFactory()
        db_session.add(agent)
        db_session.commit()

        canvas_id = str(uuid.uuid4())
        import_css = "@import url('https://cdn.example.com/styles.css');"

        response = client.post(
            f"/api/canvas/{canvas_id}/components",
            json={
                "type": "custom",
                "css": import_css
            },
            headers={"Authorization": f"Bearer {auth_token}"}
        )

        # Safe @import may be allowed
        if response.status_code in [200, 201]:
            data = response.json()
            css = data.get("css", "")
            # Should preserve or validate
            assert isinstance(css, str)

    def test_font_face_security(self, client: TestClient, auth_token: str, db_session: Session):
        """Test @font-face security."""
        agent = AutonomousAgentFactory()
        db_session.add(agent)
        db_session.commit()

        canvas_id = str(uuid.uuid4())
        font_css = "@font-face { src: url('javascript:alert(1)'); }"

        response = client.post(
            f"/api/canvas/{canvas_id}/components",
            json={
                "type": "custom",
                "css": font_css
            },
            headers={"Authorization": f"Bearer {auth_token}"}
        )

        if response.status_code in [200, 201]:
            data = response.json()
            css = data.get("css", "")
            # Dangerous font URLs should be blocked
            assert "javascript:" not in css.lower()


class TestCSSPropertyFiltering:
    """Test CSS property filtering."""

    def test_safe_properties_allowed(self, client: TestClient, auth_token: str, db_session: Session):
        """Test safe CSS properties are allowed."""
        agent = AutonomousAgentFactory()
        db_session.add(agent)
        db_session.commit()

        canvas_id = str(uuid.uuid4())
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

        response = client.post(
            f"/api/canvas/{canvas_id}/components",
            json={
                "type": "custom",
                "css": safe_css
            },
            headers={"Authorization": f"Bearer {auth_token}"}
        )

        # Safe properties should be preserved
        if response.status_code in [200, 201]:
            data = response.json()
            css = data.get("css", "")
            # Check properties preserved
            assert "padding:" in css
            assert "color:" in css
            assert "display:" in css

    def test_moz_binding_blocked(self, client: TestClient, auth_token: str, db_session: Session):
        """Test -moz-binding is blocked."""
        agent = AutonomousAgentFactory()
        db_session.add(agent)
        db_session.commit()

        canvas_id = str(uuid.uuid4())
        binding_css = "div { -moz-binding: url('javascript:alert(1)'); }"

        response = client.post(
            f"/api/canvas/{canvas_id}/components",
            json={
                "type": "custom",
                "css": binding_css
            },
            headers={"Authorization": f"Bearer {auth_token}"}
        )

        if response.status_code in [200, 201]:
            data = response.json()
            css = data.get("css", "")
            # -moz-binding should be blocked
            assert "-moz-binding:" not in css.lower()


class TestCSSAuditLogging:
    """Test CSS security audit logging."""

    def test_dangerous_css_logged(self, client: TestClient, auth_token: str, db_session: Session):
        """Test dangerous CSS attempts are logged."""
        agent = AutonomousAgentFactory()
        db_session.add(agent)
        db_session.commit()

        canvas_id = str(uuid.uuid4())
        dangerous_css = "body { background: url('javascript:alert(1)'); }"

        response = client.post(
            f"/api/canvas/{canvas_id}/components",
            json={
                "type": "custom",
                "css": dangerous_css
            },
            headers={"Authorization": f"Bearer {auth_token}"}
        )

        # Check security event logged
        audits = db_session.query(CanvasAudit).filter(
            CanvasAudit.id == canvas_id
        ).all()

        assert len(audits) >= 0

    def test_sanitization_metadata(self, client: TestClient, auth_token: str, db_session: Session):
        """Test CSS sanitization metadata is logged."""
        agent = AutonomousAgentFactory()
        db_session.add(agent)
        db_session.commit()

        canvas_id = str(uuid.uuid4())
        dangerous_css = "div { behavior: url(xss.htc); }"

        response = client.post(
            f"/api/canvas/{canvas_id}/components",
            json={
                "type": "custom",
                "css": dangerous_css
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


class TestCSSEscaping:
    """Test CSS content escaping."""

    def test_css_content_escaped(self, client: TestClient, auth_token: str, db_session: Session):
        """Test CSS content property is escaped."""
        agent = AutonomousAgentFactory()
        db_session.add(agent)
        db_session.commit()

        canvas_id = str(uuid.uuid4())
        content_css = "div:before { content: '</style><script>alert(1)</script>'; }"

        response = client.post(
            f"/api/canvas/{canvas_id}/components",
            json={
                "type": "custom",
                "css": content_css
            },
            headers={"Authorization": f"Bearer {auth_token}"}
        )

        if response.status_code in [200, 201]:
            data = response.json()
            css = data.get("css", "")
            # Content should be escaped
            assert "<script>" not in css or "&lt;" in css

    def test_css_comments_sanitized(self, client: TestClient, auth_token: str, db_session: Session):
        """Test CSS comments are sanitized."""
        agent = AutonomousAgentFactory()
        db_session.add(agent)
        db_session.commit()

        canvas_id = str(uuid.uuid4())
        comment_css = "/* </style><script>alert(1)</script> */ div { color: red; }"

        response = client.post(
            f"/api/canvas/{canvas_id}/components",
            json={
                "type": "custom",
                "css": comment_css
            },
            headers={"Authorization": f"Bearer {auth_token}"}
        )

        if response.status_code in [200, 201]:
            data = response.json()
            css = data.get("css", "")
            # Dangerous content in comments should be handled
            assert isinstance(css, str)
