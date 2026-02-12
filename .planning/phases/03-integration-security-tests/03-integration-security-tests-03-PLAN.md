# Authorization and Input Validation Security Tests

**Phase**: 03 - Integration & Security Tests
**Plan**: 03 - Authorization and Input Validation Security Tests
**Status**: Pending
**Priority**: P0 (Critical)

## Objective

Build comprehensive security tests for authorization (agent maturity permissions, action complexity matrix, episode access control, OAuth flows) and input validation (SQL injection, XSS, path traversal, canvas JavaScript security).

## Success Criteria

1. All authorization endpoints have security tests
2. Agent maturity permissions tested (STUDENT, INTERN, SUPERVISED, AUTONOMOUS)
3. Action complexity matrix tested (LOW, MODERATE, HIGH, CRITICAL)
4. Episode access control tested
5. OAuth flows tested
6. Input validation tested (SQL injection, XSS, path traversal)
7. Canvas JavaScript security tested
8. At least 15% increase in overall code coverage

## Key Areas to Cover

### Authorization Tests

#### Agent Maturity Permissions
```python
def test_student_agent_cannot_execute_triggers():
    """Test STUDENT agents are blocked from automated triggers"""
    student_agent = create_agent(maturity="STUDENT")

    response = client.post(f"/api/agents/{student_agent.id}/trigger", json={
        "action": "automated_task"
    })
    assert response.status_code == 403
    assert "blocked" in response.json()["detail"].lower()

def test_intern_agent_requires_approval_for_high_actions():
    """Test INTERN agents require approval for HIGH complexity actions"""
    intern_agent = create_agent(maturity="INTERN")

    response = client.post(f"/api/agents/{intern_agent.id}/execute", json={
        "action": "delete_database",  # CRITICAL complexity
        "complexity": "CRITICAL"
    })
    assert response.status_code == 403
    assert "approval required" in response.json()["detail"].lower()

def test_supervised_agent_can_execute_under_supervision():
    """Test SUPERVISED agents can execute with supervision"""
    supervised_agent = create_agent(maturity="SUPERVISED")

    response = client.post(f"/api/agents/{supervised_agent.id}/execute", json={
        "action": "moderate_task",
        "complexity": "MODERATE",
        "supervised": True
    })
    assert response.status_code == 200
```

#### Episode Access Control
```python
def test_user_can_only_access_own_episodes():
    """Test users can only access their own episodes"""
    user1 = create_user()
    user2 = create_user()

    # Create episode for user1
    episode = create_episode(user=user1, content="Private data")

    # User2 tries to access user1's episode
    response = client.get(
        f"/api/episodes/{episode.id}",
        headers={"Authorization": f"Bearer {user2.token}"}
    )
    assert response.status_code == 403

def test_admin_can_access_all_episodes():
    """Test admins can access all episodes"""
    admin = create_admin_user()
    episode = create_episode(user=regular_user, content="Data")

    response = client.get(
        f"/api/episodes/{episode.id}",
        headers={"Authorization": f"Bearer {admin.token}"}
    )
    assert response.status_code == 200
```

### Input Validation Tests

#### SQL Injection Tests
```python
def test_sql_injection_in_agent_name():
    """Test SQL injection in agent name parameter"""
    response = client.post("/api/agents", json={
        "name": "'; DROP TABLE agents; --",
        "maturity": "STUDENT"
    })
    # Should either sanitize or reject
    assert response.status_code in [400, 422]
    # Verify agents table still exists
    assert count_agents() >= 0

def test_sql_injection_in_canvas_title():
    """Test SQL injection in canvas title"""
    response = client.post("/api/canvas", json={
        "title": "'; DELETE FROM canvases WHERE 1=1; --"
    })
    assert response.status_code in [400, 422]
```

#### XSS Tests
```python
def test_xss_in_canvas_content():
    """Test XSS in canvas content"""
    response = client.post("/api/canvas", json={
        "title": "Test Canvas",
        "content": "<script>alert('XSS')</script>",
        "canvas_type": "generic"
    })
    assert response.status_code == 200
    data = response.json()
    # Content should be sanitized or escaped
    assert "<script>" not in data.get("content", "")

def test_xss_in_agent_description():
    """Test XSS in agent description"""
    response = client.post("/api/agents", json={
        "name": "TestAgent",
        "description": "<img src=x onerror=alert('XSS')>",
        "maturity": "STUDENT"
    })
    assert response.status_code == 200
    data = response.json()
    # Description should be sanitized
    assert "<img" not in data.get("description", "")
```

#### Path Traversal Tests
```python
def test_path_traversal_in_file_upload():
    """Test path traversal in file upload"""
    response = client.post("/api/files/upload", json={
        "filename": "../../../etc/passwd",
        "content": "test"
    })
    assert response.status_code == 400

def test_path_traversal_in_canvas_template():
    """Test path traversal in canvas template selection"""
    response = client.post("/api/canvas", json={
        "title": "Test",
        "template": "../../../sensitive/template.json"
    })
    assert response.status_code == 400
```

#### Canvas JavaScript Security
```python
def test_canvas_javascript_execution_restricted():
    """Test JavaScript execution in canvas is restricted"""
    canvas = create_canvas(type="coding")

    response = client.post(f"/api/canvas/{canvas.id}/execute", json={
        "code": "process.exit(1)"
    })
    assert response.status_code == 403
    assert "not allowed" in response.json()["detail"].lower()

def test_canvas_sanitizes_user_input():
    """Test canvas sanitizes user input before rendering"""
    response = client.post("/api/canvas", json={
        "title": "Test",
        "components": [{
            "type": "text",
            "content": "<script>document.cookie</script>"
        }]
    })
    assert response.status_code == 200
    data = response.json()
    # Script tags should be removed or escaped
    assert "<script>" not in str(data.get("components", []))
```

## Tasks

### Wave 1: Authorization Tests (Priority: P0)

- [ ] **Task 1.1**: Create `backend/tests/security/test_authorization_maturity.py`
  - Test STUDENT agent permissions
  - Test INTERN agent permissions
  - Test SUPERVISED agent permissions
  - Test AUTONOMOUS agent permissions
  - **Acceptance**: All maturity levels tested with appropriate permissions

- [ ] **Task 1.2**: Create `backend/tests/security/test_authorization_complexity.py`
  - Test LOW complexity actions
  - Test MODERATE complexity actions
  - Test HIGH complexity actions
  - Test CRITICAL complexity actions
  - **Acceptance**: All complexity levels tested with proper gating

- [ ] **Task 1.3**: Create `backend/tests/security/test_authorization_episode_access.py`
  - Test user can access own episodes
  - Test user cannot access others' episodes
  - Test admin can access all episodes
  - Test episode access logging
  - **Acceptance**: All episode access scenarios tested

- [ ] **Task 1.4**: Create `backend/tests/security/test_authorization_oauth.py`
  - Test OAuth flow authorization
  - Test OAuth token validation
  - Test OAuth scope validation
  - Test OAuth revocation
  - **Acceptance**: All OAuth authorization scenarios tested

### Wave 2: Input Validation Tests (Priority: P0)

- [ ] **Task 2.1**: Create `backend/tests/security/test_sql_injection.py`
  - Test SQL injection in agent name
  - Test SQL injection in canvas title
  - Test SQL injection in query parameters
  - Test SQL injection in all string inputs
  - **Acceptance**: All SQL injection attempts blocked

- [ ] **Task 2.2**: Create `backend/tests/security/test_xss.py`
  - Test XSS in canvas content
  - Test XSS in agent description
  - Test XSS in user-provided text
  - Test XSS in all text inputs
  - **Acceptance**: All XSS attempts sanitized

- [ ] **Task 2.3**: Create `backend/tests/security/test_path_traversal.py`
  - Test path traversal in file upload
  - Test path traversal in template selection
  - Test path traversal in all file paths
  - **Acceptance**: All path traversal attempts blocked

- [ ] **Task 2.4**: Create `backend/tests/security/test_canvas_javascript_security.py`
  - Test JavaScript execution restrictions
  - Test canvas input sanitization
  - Test canvas component validation
  - **Acceptance**: All canvas JavaScript security scenarios tested

### Wave 3: Coverage & Verification (Priority: P1)

- [ ] **Task 3.1**: Run coverage report on authz tests
  - Generate coverage report
  - Identify uncovered lines
  - **Acceptance**: Coverage report generated

- [ ] **Task 3.2**: Add missing tests
  - Review uncovered lines
  - Add edge case tests
  - **Acceptance**: At least 15% increase in coverage

- [ ] **Task 3.3**: Verify all tests pass
  - Run full authz test suite
  - Fix failures
  - **Acceptance**: All authorization and validation tests passing

## Dependencies

- Phase 1 (Test Infrastructure) - Complete
- Phase 2 (Core Property Tests) - Complete
- Authorization system implemented
- Input validation implemented

## Estimated Time

- Wave 1: 3-4 hours
- Wave 2: 3-4 hours
- Wave 3: 1-2 hours
- **Total**: 7-10 hours

## Definition of Done

1. All authorization endpoints have security tests
2. Agent maturity and complexity matrix tested
3. Episode access control tested
4. OAuth flows tested
5. Input validation tested (SQL injection, XSS, path traversal)
6. Canvas JavaScript security tested
7. At least 15% increase in overall code coverage
8. All tests passing
9. Documentation updated

## Verification Checklist

- [ ] All maturity levels tested
- [ ] All complexity levels tested
- [ ] Episode access control tested
- [ ] OAuth authorization tested
- [ ] SQL injection protection tested
- [ ] XSS protection tested
- [ ] Path traversal protection tested
- [ ] Canvas JavaScript security tested
- [ ] Coverage increased by at least 15%
- [ ] All tests passing
