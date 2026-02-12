# Canvas and Browser Integration Tests with JavaScript Security

**Phase**: 03 - Integration & Security Tests
**Plan**: 05 - Canvas and Browser Integration Tests
**Status**: Pending
**Priority**: P1 (High)

## Objective

Build comprehensive integration tests for canvas presentation system and browser automation, including JavaScript security validation for canvas components.

## Success Criteria

1. Canvas CRUD operations tested (create, read, update, delete)
2. Canvas component system tested (charts, forms, sheets, custom components)
3. Canvas governance integration tested (maturity-based access)
4. Canvas JavaScript security tested (sandboxing, validation)
5. Browser automation tested (navigation, screenshot, form fill)
6. Browser governance integration tested
7. At least 15% increase in overall code coverage

## Key Areas to Cover

### Canvas CRUD Tests
```python
def test_create_canvas():
    """Test canvas creation"""
    response = client.post("/api/canvas", json={
        "title": "Test Canvas",
        "canvas_type": "generic",
        "components": []
    })
    assert response.status_code == 200
    data = response.json()
    assert data["canvas_id"] is not None
    assert data["title"] == "Test Canvas"

def test_create_canvas_with_charts():
    """Test canvas creation with chart components"""
    response = client.post("/api/canvas", json={
        "title": "Analytics Dashboard",
        "canvas_type": "orchestration",
        "components": [{
            "type": "line_chart",
            "data": {"x": [1,2,3], "y": [4,5,6]}
        }]
    })
    assert response.status_code == 200
    data = response.json()
    assert len(data["components"]) == 1

def test_update_canvas():
    """Test canvas update"""
    canvas = create_test_canvas()

    response = client.put(f"/api/canvas/{canvas.id}", json={
        "title": "Updated Title"
    })
    assert response.status_code == 200
    data = response.json()
    assert data["title"] == "Updated Title"

def test_delete_canvas():
    """Test canvas deletion"""
    canvas = create_test_canvas()

    response = client.delete(f"/api/canvas/{canvas.id}")
    assert response.status_code == 200

    # Verify deletion
    response = client.get(f"/api/canvas/{canvas.id}")
    assert response.status_code == 404
```

### Canvas Component Tests
```python
def test_add_text_component():
    """Test adding text component to canvas"""
    canvas = create_test_canvas()

    response = client.post(f"/api/canvas/{canvas.id}/components", json={
        "type": "text",
        "content": "Hello, World!"
    })
    assert response.status_code == 200
    data = response.json()
    assert data["type"] == "text"

def test_add_form_component():
    """Test adding form component to canvas"""
    canvas = create_test_canvas()

    response = client.post(f"/api/canvas/{canvas.id}/components", json={
        "type": "form",
        "fields": [
            {"name": "email", "type": "email", "required": True},
            {"name": "name", "type": "text", "required": True}
        ]
    })
    assert response.status_code == 200
    data = response.json()
    assert data["type"] == "form"
    assert len(data["fields"]) == 2

def test_submit_form():
    """Test form submission"""
    canvas = create_test_canvas()
    form = add_form_component_to_canvas(canvas)

    response = client.post(f"/api/canvas/{canvas.id}/submit", json={
        "component_id": form.id,
        "data": {
            "email": "test@example.com",
            "name": "Test User"
        }
    })
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True

def test_add_chart_component():
    """Test adding chart component to canvas"""
    canvas = create_test_canvas()

    response = client.post(f"/api/canvas/{canvas.id}/components", json={
        "type": "bar_chart",
        "data": {
            "labels": ["A", "B", "C"],
            "values": [10, 20, 30]
        }
    })
    assert response.status_code == 200

def test_add_custom_component():
    """Test adding custom HTML/CSS/JS component"""
    canvas = create_test_canvas()

    response = client.post(f"/api/canvas/{canvas.id}/components", json={
        "type": "custom",
        "html": "<div>Custom</div>",
        "css": "div { color: red; }",
        "javascript": "console.log('test');"
    })
    assert response.status_code == 200
    data = response.json()
    assert data["type"] == "custom"
```

### Canvas Governance Tests
```python
def test_student_agent_can_present_read_only_canvas():
    """Test STUDENT agents can present read-only canvas"""
    student_agent = create_agent(maturity="STUDENT")
    canvas = create_canvas(type="generic", read_only=True)

    response = client.post(f"/api/agents/{student_agent.id}/present", json={
        "canvas_id": canvas.id
    })
    assert response.status_code == 200

def test_intern_agent_can_present_form():
    """Test INTERN agents can present forms with approval"""
    intern_agent = create_agent(maturity="INTERN")
    canvas = create_canvas(type="form")

    response = client.post(f"/api/agents/{intern_agent.id}/present", json={
        "canvas_id": canvas.id,
        "require_approval": True
    })
    assert response.status_code == 200
    data = response.json()
    assert data["approval_required"] is True

def test_supervised_agent_can_submit_form():
    """Test SUPERVISED agents can submit forms"""
    supervised_agent = create_agent(maturity="SUPERVISED")
    canvas = create_canvas_with_form()

    response = client.post(f"/api/agents/{supervised_agent.id}/execute", json={
        "canvas_id": canvas.id,
        "action": "submit_form",
        "data": {"field": "value"}
    })
    assert response.status_code == 200

def test_autonomous_agent_can_execute_javascript():
    """Test AUTONOMOUS agents can execute JavaScript"""
    autonomous_agent = create_agent(maturity="AUTONOMOUS")
    canvas = create_canvas_with_custom_component()

    response = client.post(f"/api/agents/{autonomous_agent.id}/execute", json={
        "canvas_id": canvas.id,
        "action": "execute_javascript"
    })
    assert response.status_code == 200
```

### Canvas JavaScript Security Tests
```python
def test_canvas_javascript_sandbox():
    """Test JavaScript execution is sandboxed"""
    canvas = create_canvas_with_javascript("process.exit(1)")

    response = client.post(f"/api/canvas/{canvas.id}/execute", json={
        "code": "process.exit(1)"
    })
    assert response.status_code == 403

def test_canvas_html_sanitization():
    """Test HTML is sanitized"""
    response = client.post("/api/canvas", json={
        "title": "Test",
        "components": [{
            "type": "custom",
            "html": "<script>alert('XSS')</script>"
        }]
    })
    assert response.status_code == 200
    data = response.json()
    # Script tags should be removed
    assert "<script>" not in data["components"][0]["html"]

def test_canvas_css_sanitization():
    """Test CSS is sanitized"""
    response = client.post("/api/canvas", json={
        "title": "Test",
        "components": [{
            "type": "custom",
            "css": "div { background: url('javascript:alert(1)'); }"
        }]
    })
    assert response.status_code == 200
    # Dangerous CSS should be removed

def test_canvas_javascript_validation():
    """Test JavaScript is validated before execution"""
    canvas = create_canvas()

    response = client.post(f"/api/canvas/{canvas.id}/validate", json={
        "javascript": "console.log('safe code');"
    })
    assert response.status_code == 200
    data = response.json()
    assert data["valid"] is True

    response = client.post(f"/api/canvas/{canvas.id}/validate", json={
        "javascript": "eval('malicious');"
    })
    assert response.status_code == 200
    data = response.json()
    assert data["valid"] is False
```

### Browser Automation Tests
```python
def test_browser_session_creation():
    """Test browser session creation"""
    response = client.post("/api/browser/session", json={
        "url": "https://example.com"
    })
    assert response.status_code == 200
    data = response.json()
    assert data["session_id"] is not None

def test_browser_navigation():
    """Test browser navigation"""
    session = create_browser_session()

    response = client.post(f"/api/browser/{session.id}/navigate", json={
        "url": "https://example.com/page2"
    })
    assert response.status_code == 200

def test_browser_screenshot():
    """Test browser screenshot"""
    session = create_browser_session()

    response = client.post(f"/api/browser/{session.id}/screenshot")
    assert response.status_code == 200
    data = response.json()
    assert "screenshot" in data

def test_browser_form_fill():
    """Test browser form filling"""
    session = create_browser_session()

    response = client.post(f"/api/browser/{session.id}/fill", json={
        "selector": "#email",
        "value": "test@example.com"
    })
    assert response.status_code == 200

def test_browser_governance():
    """Test browser automation governance"""
    student_agent = create_agent(maturity="STUDENT")

    response = client.post(f"/api/agents/{student_agent.id}/browser", json={
        "action": "navigate",
        "url": "https://example.com"
    })
    assert response.status_code == 403
```

## Tasks

### Wave 1: Canvas CRUD Tests (Priority: P0)

- [ ] **Task 1.1**: Create `backend/tests/integration/canvas/test_canvas_crud.py`
  - Test canvas creation
  - Test canvas retrieval
  - Test canvas update
  - Test canvas deletion
  - Test canvas listing
  - **Acceptance**: All canvas CRUD operations tested

- [ ] **Task 1.2**: Create `backend/tests/integration/canvas/test_canvas_components.py`
  - Test adding text component
  - Test adding form component
  - Test adding chart component
  - Test adding custom component
  - Test component update
  - Test component deletion
  - **Acceptance**: All canvas component operations tested

- [ ] **Task 1.3**: Create `backend/tests/integration/canvas/test_canvas_forms.py`
  - Test form submission
  - Test form validation
  - Test form data storage
  - **Acceptance**: All form scenarios tested

### Wave 2: Canvas Governance Tests (Priority: P0)

- [ ] **Task 2.1**: Create `backend/tests/integration/canvas/test_canvas_governance.py`
  - Test STUDENT agent access
  - Test INTERN agent access
  - Test SUPERVISED agent access
  - Test AUTONOMOUS agent access
  - **Acceptance**: All maturity levels tested

- [ ] **Task 2.2**: Create `backend/tests/integration/canvas/test_canvas_actions.py`
  - Test present action
  - Test submit action
  - Test execute action
  - **Acceptance**: All canvas actions tested

### Wave 3: Canvas Security Tests (Priority: P0)

- [ ] **Task 3.1**: Create `backend/tests/security/test_canvas_javascript_security.py`
  - Test JavaScript sandboxing
  - Test JavaScript validation
  - Test dangerous JavaScript blocking
  - **Acceptance**: All JavaScript security scenarios tested

- [ ] **Task 3.2**: Create `backend/tests/security/test_canvas_html_security.py`
  - Test HTML sanitization
  - Test XSS prevention
  - **Acceptance**: All HTML security scenarios tested

- [ ] **Task 3.3**: Create `backend/tests/security/test_canvas_css_security.py`
  - Test CSS sanitization
  - Test dangerous URL blocking
  - **Acceptance**: All CSS security scenarios tested

### Wave 4: Browser Automation Tests (Priority: P1)

- [ ] **Task 4.1**: Create `backend/tests/integration/browser/test_browser_crud.py`
  - Test browser session creation
  - Test browser navigation
  - Test browser screenshot
  - Test browser session termination
  - **Acceptance**: All browser CRUD operations tested

- [ ] **Task 4.2**: Create `backend/tests/integration/browser/test_browser_actions.py`
  - Test browser form fill
  - Test browser click
  - Test browser scroll
  - Test browser wait
  - **Acceptance**: All browser actions tested

- [ ] **Task 4.3**: Create `backend/tests/integration/browser/test_browser_governance.py`
  - Test STUDENT agent access
  - Test INTERN agent access
  - Test SUPERVISED agent access
  - Test AUTONOMOUS agent access
  - **Acceptance**: All browser governance scenarios tested

### Wave 5: Coverage & Verification (Priority: P1)

- [ ] **Task 5.1**: Run coverage report
  - Generate coverage report
  - Identify uncovered lines
  - **Acceptance**: Coverage report generated

- [ ] **Task 5.2**: Add missing tests
  - Review uncovered lines
  - Add edge case tests
  - **Acceptance**: At least 15% increase in coverage

- [ ] **Task 5.3**: Verify all tests pass
  - Run full test suite
  - Fix failures
  - **Acceptance**: All canvas and browser tests passing

## Dependencies

- Phase 1 (Test Infrastructure) - Complete
- Phase 2 (Core Property Tests) - Complete
- Canvas system implemented
- Browser automation implemented
- Governance system implemented

## Estimated Time

- Wave 1: 3-4 hours
- Wave 2: 2-3 hours
- Wave 3: 3-4 hours
- Wave 4: 2-3 hours
- Wave 5: 1-2 hours
- **Total**: 11-16 hours

## Definition of Done

1. Canvas CRUD operations tested
2. Canvas component system tested
3. Canvas governance integration tested
4. Canvas JavaScript security tested
5. Browser automation tested
6. Browser governance integration tested
7. At least 15% increase in overall code coverage
8. All tests passing
9. Documentation updated

## Verification Checklist

- [ ] Canvas CRUD tested
- [ ] Canvas components tested
- [ ] Canvas forms tested
- [ ] Canvas governance tested
- [ ] Canvas JavaScript security tested
- [ ] Canvas HTML security tested
- [ ] Canvas CSS security tested
- [ ] Browser automation tested
- [ ] Browser governance tested
- [ ] Coverage increased by at least 15%
- [ ] All tests passing
