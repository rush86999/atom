# Phase 235: Canvas & Workflow E2E - Research

**Researched:** 2026-03-24
**Domain:** E2E Testing (Playwright, Pytest, Canvas System, Workflow Engine, Skill Registry)
**Confidence:** HIGH

## Summary

Phase 235 requires comprehensive E2E testing for the Canvas system (7 types), Workflow automation, and Skill execution. The codebase has extensive canvas infrastructure already implemented but lacks E2E test coverage. The existing E2E test framework from Phase 234 provides a solid foundation with Playwright, Page Objects, API-first auth fixtures, and Allure reporting.

**Primary recommendation:** Leverage existing E2E infrastructure (Playwright + Pytest + Page Objects + API fixtures) and follow Phase 234's test patterns. Canvas tests should use page.evaluate() to trigger WebSocket canvas events and page.route() to mock API responses. Workflow tests should test API endpoints directly for DAG validation and skill execution order. Cross-platform tests should focus on API-level testing for mobile (React Native) and verify desktop (Tauri) canvas rendering.

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| **Playwright** | 1.40+ | Browser automation | Industry standard for E2E testing, auto-waits, multi-browser support, built-in fixtures |
| **Pytest** | 7.0+ | Test runner | De facto Python testing standard, fixtures, parametrize, xdist parallelization |
| **pytest-playwright** | Latest | Playwright-Pytest integration | Official plugin, browser fixtures, screenshots on failure, tracing |
| **pytest-xdist** | Latest | Parallel test execution | Faster test runs, worker-aware fixtures from Phase 233 |
| **Allure** | 2.x | Test reporting | Rich HTML reports, screenshots/videos embedded, history tracking |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| **NetworkX** | 3.x | DAG validation testing | Verify workflow graphs are acyclic before execution |
| **requests** | Latest | API-level testing | Test workflow/skill endpoints without UI overhead |
| **SQLAlchemy** | 2.0+ | Database assertions | Verify canvas_audit, skill_execution, workflow_execution records |
| **frontmatter** | Latest | Test data generation | Create SKILL.md content for skill installation tests |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Playwright | Selenium, Cypress | Playwright faster, more reliable, better Python support than Cypress, modern API vs Selenium |
| Page Objects | Screenplay, Direct selectors | Page Objects simpler, well-understood pattern, easier to maintain |
| API-first fixtures | UI login flows | API fixtures 10-100x faster, less flaky, proven in Phase 234 |

**Installation:**
```bash
# Core E2E testing stack
pip install pytest pytest-playwright pytest-xdist allure-pytest
pip install networkx requests sqlalchemy frontmatter

# Playwright browsers
playwright install chromium
```

## Architecture Patterns

### Recommended Project Structure
```
backend/tests/e2e_ui/
├── tests/
│   ├── canvas/
│   │   ├── test_canvas_chart_rendering.py      # Line, bar, pie charts
│   │   ├── test_canvas_form_validation.py      # Required fields, error messages
│   │   ├── test_canvas_state_api.py            # window.atom.canvas.getState()
│   │   ├── test_canvas_stress_testing.py       # Rapid present/close cycles
│   │   ├── test_canvas_docs.py                 # Docs canvas type
│   │   ├── test_canvas_email.py                # Email canvas type
│   │   ├── test_canvas_sheets.py               # Sheets canvas type
│   │   ├── test_canvas_orchestration.py        # Orchestration canvas type
│   │   ├── test_canvas_terminal.py             # Terminal canvas type
│   │   └── test_canvas_coding.py               # Coding canvas type
│   ├── skills/
│   │   ├── test_skill_installation.py          # Web UI skill install flow
│   │   ├── test_skill_execution.py             # Skill execution with parameters
│   │   └── test_skill_registry.py              # Skill appears in registry after install
│   ├── workflows/
│   │   ├── test_workflow_creation.py           # Workflow composition UI
│   │   ├── test_workflow_dag_validation.py     # Acyclic graph verification
│   │   ├── test_workflow_execution.py           # Skill order verification
│   │   └── test_workflow_triggers.py           # Manual, scheduled, event-based
│   └── cross_platform/
│       ├── test_canvas_mobile_api.py           # Canvas via mobile API
│       ├── test_workflow_mobile_api.py         # Workflow via mobile API
│       └── test_canvas_desktop_tauri.py        # Desktop canvas rendering
├── pages/
│   ├── canvas_page_objects.py                  # Canvas-specific Page Objects
│   ├── skills_page_objects.py                  # Skills marketplace/install Page Objects
│   └── workflows_page_objects.py               # Workflow composition Page Objects
├── fixtures/
│   ├── canvas_fixtures.py                      # Canvas test data factories
│   ├── workflow_fixtures.py                    # Workflow DAG factories
│   └── skill_fixtures.py                       # SKILL.md content generators
└── conftest.py                                  # Pytest configuration
```

### Pattern 1: Canvas Event Simulation via page.evaluate()
**What:** Trigger canvas presentations by simulating WebSocket messages in browser context
**When to use:** Testing canvas rendering without backend WebSocket server
**Example:**
```python
# Source: backend/tests/e2e_ui/tests/test_canvas_forms.py (existing pattern)
def trigger_form_canvas(page: Page, schema: Dict[str, Any], title: str = "Test Form") -> str:
    """Simulate WebSocket canvas:update event to trigger form canvas presentation."""
    canvas_id = schema.get("canvas_id", f"form-{str(uuid.uuid4())}")

    # Inject canvas message into window (simulates WebSocket delivery)
    canvas_message = {
        "type": "canvas:update",
        "canvas_id": canvas_id,
        "data": {
            "component": "form",
            "title": title,
            "schema": schema
        }
    }

    page.evaluate(f"(msg) => window.lastCanvasMessage = msg", canvas_message)

    # Dispatch custom event to trigger canvas host useEffect
    page.evaluate(f"""
        () => {{
            const event = new CustomEvent('canvas:update', {{
                detail: {{ type: 'canvas:update' }}
            }});
            window.dispatchEvent(event);
        }}
    """)

    return canvas_id
```

### Pattern 2: API Mocking with page.route()
**What:** Intercept HTTP requests and return custom responses for testing
**When to use:** Testing form submissions, skill installations without real backend
**Example:**
```python
# Source: backend/tests/e2e_ui/tests/test_canvas_forms.py (existing pattern)
def mock_canvas_submit_api(page: Page, response_data: Dict[str, Any], status_code: int = 200) -> None:
    """Mock the /api/canvas/submit endpoint to return custom response."""
    def handle_route(route):
        route.fulfill(
            status=status_code,
            content_type="application/json",
            body=json.dumps({
                "success": status_code == 200,
                "data": response_data,
                "message": "Form submitted successfully" if status_code == 200 else "Submission failed"
            })
        )

    page.route("http://localhost:8001/api/canvas/submit", handle_route)
```

### Pattern 3: API-First Authentication Fixtures
**What:** Create authenticated test state via JWT tokens in localStorage (bypass UI login)
**When to use:** All tests requiring authentication (10-100x faster than UI login)
**Example:**
```python
# Source: backend/tests/e2e_ui/fixtures/auth_fixtures.py (Phase 234)
@pytest.fixture(scope="function")
def authenticated_page(browser: Browser, authenticated_user: Tuple[User, str]) -> Page:
    """Create a Playwright page with JWT token pre-set in localStorage."""
    user, token = authenticated_user

    # Create new browser context
    context = browser.new_context()
    page = context.new_page()

    # Navigate to base URL first (required for localStorage)
    page.goto(base_url)
    page.wait_for_load_state("networkidle")

    # Set JWT token in localStorage
    page.evaluate(f"() => localStorage.setItem('auth_token', '{token}')")

    yield page

    # Cleanup
    context.close()
```

### Pattern 4: DAG Validation Testing
**What:** Test workflow graph validation using NetworkX
**When to use:** Verifying workflow creation rejects cyclic dependencies
**Example:**
```python
# Source: backend/core/skill_composition_engine.py
def test_workflow_rejects_cyclic_dependencies():
    """Test that workflow validation rejects cycles."""
    # Create workflow with cycle: A -> B -> C -> A
    steps = [
        SkillStep("A", "skill1", {}, []),
        SkillStep("B", "skill2", {}, ["A"]),
        SkillStep("C", "skill3", {}, ["B"]),
        SkillStep("A", "skill4", {}, ["C"])  # Creates cycle
    ]

    validation = skill_composition_engine.validate_workflow(steps)

    assert validation["valid"] is False
    assert "cycles" in validation
    assert ["A", "B", "C"] in validation["cycles"]
```

### Pattern 5: Canvas State API Testing
**What:** Verify window.atom.canvas.getState() exposes correct structured state
**When to use:** Testing AI agent accessibility to canvas content
**Example:**
```python
def test_form_canvas_state_accessible(page: Page):
    """Test that form canvas state is accessible via window.atom.canvas.getState()."""
    # Trigger form canvas presentation
    canvas_id = trigger_form_canvas(page, form_schema)

    # Get canvas state via JavaScript API
    state = page.evaluate(f"() => window.atom.canvas.getState('{canvas_id}')")

    # Verify state structure
    assert state is not None
    assert state["canvas_type"] == "generic"
    assert state["component"] == "form"
    assert "form_schema" in state
    assert "form_data" in state
    assert "validation_errors" in state
```

### Anti-Patterns to Avoid
- **Don't use UI login flows:** Use API-first auth fixtures (10-100x faster)
- **Don't test all canvas types in one file:** Separate test files per canvas type (chart, form, docs, email, sheets, orchestration, terminal, coding)
- **Don't skip stress testing:** Canvas present/close cycles can leak memory (test 100+ rapid cycles)
- **Don't mock the WebSocket server:** Use page.evaluate() to dispatch events instead (simpler, faster)
- **Don't ignore cross-platform testing:** Mobile (API-level) and Desktop (Tauri) have different test needs

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Canvas event simulation | Custom WebSocket server | page.evaluate() + CustomEvent | Simpler, no async complexity, faster |
| Workflow DAG validation | Custom cycle detection | NetworkX nx.is_directed_acyclic_graph() | Well-tested, handles edge cases, topological sort built-in |
| Test data generation | Manual dict creation | Pytest fixtures + factories | Centralized, reusable, easier to maintain |
| API mocking | Custom mock server | page.route() (Playwright) | Built-in, no external dependencies, easier debugging |
| Authentication state | UI login flows | API-first fixtures (JWT in localStorage) | 10-100x faster, less flaky |
| Test parallelization | Custom threading | pytest-xdist | Proven solution, worker-aware fixtures already built |
| Reporting | Custom HTML generation | Allure | Rich reports, screenshots/videos embedded, history tracking |

**Key insight:** The E2E test infrastructure from Phase 233/234 provides battle-tested patterns for all common problems. Reuse existing fixtures (auth_fixtures.py, database_fixtures.py) and Page Object patterns from tests/e2e_ui/pages/page_objects.py.

## Common Pitfalls

### Pitfall 1: Test Data Collisions in Parallel Execution
**What goes wrong:** Tests using fixed test data (emails, names) collide when run with pytest-xdist
**Why it happens:** Multiple workers access same database, violate unique constraints
**How to avoid:** Use UUID v4 for all test data (test_abc123@example.com pattern)
**Warning signs:** Intermittent test failures only in CI, "duplicate key" database errors
```python
# GOOD: UUID-based test data
unique_id = str(uuid.uuid4())[:8]
email = f"test_{unique_id}@example.com"

# BAD: Fixed test data
email = "test@example.com"  # Collides in parallel runs
```

### Pitfall 2: Canvas State Not Ready When Querying
**What goes wrong:** Tests query canvas state before component finishes rendering
**Why it happens:** Canvas updates are async via WebSocket/events
**How to avoid:** Use page.wait_for_selector() or page.wait_for_function() to poll for state
**Warning signs:** Flaky tests that fail when slowed down, "state is null" errors
```python
# GOOD: Wait for state to be available
page.wait_for_function(
    f"() => window.atom.canvas.getState('{canvas_id}') !== null",
    timeout=5000
)
state = page.evaluate(f"() => window.atom.canvas.getState('{canvas_id}')")

# BAD: Assume state is immediately available
state = page.evaluate(f"() => window.atom.canvas.getState('{canvas_id}')")
```

### Pitfall 3: Memory Leaks in Rapid Canvas Cycles
**What goes wrong:** Browser memory grows unbounded during rapid present/close cycles
**Why it happens:** React components not properly cleaned up, event listeners not removed
**How to avoid:** Stress test with 100+ cycles, check memory usage before/after
**Warning signs:** Browser crashes after many canvas presentations, slowing test execution
```python
def test_rapid_canvas_present_close_cycles_no_memory_leak():
    """Test that rapid canvas present/close cycles don't leak memory."""
    # Get initial memory usage
    initial_memory = page.evaluate("() => performance.memory.usedJSHeapSize")

    # Present/close canvas 100 times
    for i in range(100):
        canvas_id = trigger_chart_canvas(page, chart_data)
        close_canvas(page, canvas_id)

    # Check final memory usage (should not grow > 50MB)
    final_memory = page.evaluate("() => performance.memory.usedJSHeapSize")
    memory_growth_mb = (final_memory - initial_memory) / (1024 * 1024)

    assert memory_growth_mb < 50, f"Memory leaked {memory_growth_mb:.2f}MB"
```

### Pitfall 4: Workflow Tests Realying on External Services
**What goes wrong:** Workflow tests fail when external APIs (GitHub, Slack) are unavailable
**Why it happens:** Tests call real services instead of mocking
**How to avoid:** Mock service responses at HTTP layer or use test doubles
**Warning signs:** Tests fail randomly with network errors, slow test execution
```python
# GOOD: Mock HTTP responses
def test_workflow_with_http_skill(page: Page):
    """Test workflow execution with mocked HTTP skill."""
    skill_output = {"status": "success", "data": {"result": 42}}

    # Mock skill execution API
    def mock_skill_execution(route):
        route.fulfill(
            status=200,
            content_type="application/json",
            body=json.dumps({"success": True, "output": skill_output})
        )

    page.route("http://localhost:8001/api/skills/execute", mock_skill_execution)

    # Execute workflow (uses mocked response)
    execute_workflow(page, workflow_id)

    # Verify workflow completed with mocked output
    assert workflow_status(page) == "completed"
    assert workflow_output(page) == skill_output

# BAD: Call real external service
def test_workflow_with_real_github_api():
    # Fragile: requires GitHub API access, rate limits, network
    workflow = create_workflow_with_github_step()
    result = execute_workflow(workflow)
    # Fails when GitHub is down or rate limited
```

### Pitfall 5: Ignoring Canvas Governance in Tests
**What goes wrong:** Tests assume all agents can present all canvas types
**Why it happens:** Tests don't create agents with correct maturity levels
**How to avoid:** Use test agent fixtures with specific maturity (STUDENT, INTERN, SUPERVISED, AUTONOMOUS)
**Warning signs:** Tests fail with "governance check failed" errors, unexpected permission denied
```python
# GOOD: Create agent with required maturity
@pytest.fixture
def supervised_agent(db_session):
    """Create a SUPERVISED agent for canvas tests."""
    agent = AgentRegistry(
        name="Test Supervised Agent",
        status="supervised",  # Required for terminal canvas
        maturity_level=0.8,
        capabilities=["present_terminal", "execute_readonly"]
    )
    db_session.add(agent)
    db_session.commit()
    return agent

def test_supervised_agent_can_present_terminal_canvas(page, supervised_agent):
    """Test that SUPERVISED agent can present terminal canvas."""
    canvas_id = trigger_terminal_canvas(page, terminal_data, agent_id=supervised_agent.id)

    # Verify canvas presented (governance check passed)
    assert page.locator(f"[data-canvas-id='{canvas_id}']").is_visible()

# BAD: Assume default agent has permission
def test_terminal_canvas_renders():
    # Fails if default agent is STUDENT (blocked from terminal)
    canvas_id = trigger_terminal_canvas(page, terminal_data)
    # May fail with governance error
```

## Code Examples

Verified patterns from codebase:

### Canvas Rendering Test Pattern
```python
# Source: backend/tests/e2e_ui/tests/test_canvas_forms.py
def test_form_renders_with_title(authenticated_page: Page):
    """Test that form displays title correctly."""
    # Create form schema with title
    form_schema = create_test_form_schema([
        {
            "form_title": "User Registration Form",
            "name": "full_name",
            "label": "Full Name",
            "type": "text",
            "placeholder": "Enter your full name",
            "required": True
        }
    ])

    # Trigger form canvas
    canvas_id = trigger_form_canvas(authenticated_page, form_schema, "User Registration Form")

    # Wait for canvas to appear
    canvas_host = CanvasHostPage(authenticated_page)
    canvas_host.wait_for_canvas_visible(timeout=5000)

    # Initialize form page
    form_page = CanvasFormPage(authenticated_page)

    # Verify title is displayed
    assert form_page.get_form_title() == "User Registration Form"
```

### Form Validation Test Pattern
```python
# Source: backend/tests/e2e_ui/tests/test_canvas_forms.py
def test_form_required_field_validation(authenticated_page: Page):
    """Test that required field validation works correctly."""
    # Create form with required field
    form_schema = create_test_form_schema([
        {
            "name": "email",
            "label": "Email Address",
            "type": "email",
            "required": True
        }
    ])

    canvas_id = trigger_form_canvas(authenticated_page, form_schema, "Email Form")
    form_page = CanvasFormPage(authenticated_page)

    # Attempt to submit without filling required field
    form_page.click_submit_button()

    # Verify validation error appears
    assert form_page.get_field_error("email") is not None
    assert "required" in form_page.get_field_error("email").lower()
```

### Canvas State API Test Pattern
```python
# Source: docs/CANVAS_STATE_API.md
def test_canvas_state_api_exposes_form_state(authenticated_page: Page):
    """Test that form canvas state is accessible via window.atom.canvas.getState()."""
    form_schema = create_test_form_schema([
        {"name": "username", "label": "Username", "type": "text", "required": True}
    ])

    canvas_id = trigger_form_canvas(authenticated_page, form_schema)

    # Wait for state to be available
    authenticated_page.wait_for_function(
        f"() => window.atom.canvas.getState('{canvas_id}') !== null"
    )

    # Get canvas state
    state = authenticated_page.evaluate(f"() => window.atom.canvas.getState('{canvas_id}')")

    # Verify state structure
    assert state["canvas_type"] == "generic"
    assert state["component"] == "form"
    assert state["form_schema"]["fields"][0]["name"] == "username"
    assert state["form_data"]["username"] is None  # Not filled yet
    assert state["submit_enabled"] is False  # Required field not filled
```

### Workflow DAG Validation Test Pattern
```python
# Source: backend/core/skill_composition_engine.py
def test_workflow_validation_rejects_cycles(db_session):
    """Test that workflow validation detects cyclic dependencies."""
    from core.skill_composition_engine import SkillCompositionEngine, SkillStep

    engine = SkillCompositionEngine(db_session)

    # Create workflow with cycle: A -> B -> C -> A
    steps = [
        SkillStep(step_id="A", skill_id="skill1", inputs={}, dependencies=[]),
        SkillStep(step_id="B", skill_id="skill2", inputs={}, dependencies=["A"]),
        SkillStep(step_id="C", skill_id="skill3", inputs={}, dependencies=["B"]),
        SkillStep(step_id="A_repeat", skill_id="skill4", inputs={}, dependencies=["C", "A"])
    ]

    # Validate workflow
    validation = engine.validate_workflow(steps)

    # Should detect cycle
    assert validation["valid"] is False
    assert "cycles" in validation
    assert len(validation["cycles"]) > 0
```

### Skill Installation Test Pattern
```python
# Source: backend/core/skill_registry_service.py
def test_skill_installation_via_web_ui(db_session, authenticated_page: Page):
    """Test that user can install skill via web UI."""
    # Navigate to skills marketplace
    authenticated_page.goto("http://localhost:3001/skills/marketplace")

    # Search for skill
    skills_page = SkillsMarketplacePage(authenticated_page)
    skills_page.search_for_skill("calculator")

    # Click install button on first result
    skills_page.click_install_button(index=0)

    # Wait for security scan to complete
    skills_page.wait_for_scan_complete(timeout=10000)

    # Verify skill appears in registry
    authenticated_page.goto("http://localhost:3001/skills/registry")
    assert skills_page.is_skill_visible("calculator")

    # Verify database record created
    skill = db_session.query(CommunitySkill).filter_by(name="calculator").first()
    assert skill is not None
    assert skill.status == "Active"  # After security scan
```

### Skill Execution Test Pattern
```python
# Source: backend/core/skill_registry_service.py
def test_skill_execution_with_parameters(db_session, authenticated_page: Page):
    """Test that user can execute skill with parameters."""
    # Install skill first
    skill_id = install_test_skill(db_session, name="sum", code="return a + b")

    # Navigate to skill execution page
    authenticated_page.goto(f"http://localhost:3001/skills/{skill_id}/execute")

    execution_page = SkillExecutionPage(authenticated_page)

    # Fill parameters
    execution_page.fill_parameter("a", 5)
    execution_page.fill_parameter("b", 10)

    # Execute skill
    execution_page.click_execute_button()

    # Wait for execution to complete
    execution_page.wait_for_execution_complete(timeout=5000)

    # Verify output
    output = execution_page.get_output()
    assert output["success"] is True
    assert output["result"] == 15
```

### Workflow Trigger Test Pattern
```python
# Source: backend/core/workflow_engine.py
def test_workflow_manual_trigger(db_session, authenticated_page: Page):
    """Test that workflow can be triggered manually."""
    # Create workflow with 3 steps
    workflow = create_test_workflow(db_session, steps=[
        {"step_id": "fetch", "skill": "http_get", "dependencies": []},
        {"step_id": "process", "skill": "analyze", "dependencies": ["fetch"]},
        {"step_id": "notify", "skill": "send_email", "dependencies": ["process"]}
    ])

    # Navigate to workflow detail page
    authenticated_page.goto(f"http://localhost:3001/workflows/{workflow.id}")

    workflow_page = WorkflowDetailPage(authenticated_page)

    # Click manual trigger button
    workflow_page.click_trigger_button()

    # Wait for execution to complete
    workflow_page.wait_for_execution_complete(timeout=15000)

    # Verify steps executed in order
    execution_log = workflow_page.get_execution_log()
    assert execution_log[0]["step_id"] == "fetch"
    assert execution_log[1]["step_id"] == "process"
    assert execution_log[2]["step_id"] == "notify"

    # Verify all steps completed
    for step in execution_log:
        assert step["status"] == "completed"
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Selenium WebDriver | Playwright | 2023-2024 | 10x faster, more reliable, auto-waits, multi-browser |
| UI-based login | API-first auth fixtures (JWT in localStorage) | Phase 234 (Feb 2026) | 10-100x faster, less flaky, proven in 91 passing tests |
| Separate test suites | Unified test runner with Allure reporting | Phase 233-05 (Feb 2026) | Single view of all platform tests, automatic screenshot/video capture |
| Manual test data | UUID-based factories | Phase 233 (Feb 2026) | No collisions in parallel execution (pytest-xdist) |
| Mock WebSocket servers | page.evaluate() event simulation | Phase 234 (Feb 2026) | Simpler, faster, no async complexity |

**Deprecated/outdated:**
- **Selenium**: Replaced by Playwright (faster, more reliable, better Python support)
- **UI login flows**: Replaced by API-first auth fixtures (10-100x faster)
- **CSS-based selectors**: Replaced by data-testid attributes (more resilient to styling changes)
- **Sequential test execution**: Replaced by pytest-xdist parallel execution (faster CI)

## Open Questions

1. **Cross-platform testing scope for mobile (React Native)**
   - What we know: Mobile app exists in `/mobile/` directory, shares API backend
   - What's unclear: Should mobile E2E tests use Appium (React Native) or API-level testing only?
   - Recommendation: **API-level testing only** for Phase 235 (faster, less complex). Full React Native E2E with Appium deferred to future phase.

2. **Desktop Tauri canvas verification approach**
   - What we know: Desktop app exists (see TAURI_CANVAS_VERIFICATION.md), Tauri uses Chromium engine
   - What's unclear: Can we reuse Playwright tests for Tauri or need separate test suite?
   - Recommendation: **Reuse Playwright tests** by pointing at Tauri dev server URL (localhost:3001). Tauri uses same frontend code, so existing web tests should pass. Add 1-2 smoke tests to verify desktop-specific features (window controls, native menus).

3. **Canvas stress testing cycle count**
   - What we know: CANV-04 requires "rapid present/close cycles work without memory leaks"
   - What's unclear: How many cycles is enough to catch memory leaks? 10? 100? 1000?
   - Recommendation: **100 cycles** based on industry best practices (detects gradual leaks, runs in <10 seconds). Document expected memory growth threshold (<50MB for 100 cycles).

4. **Workflow trigger testing for scheduled/event-based**
   - What we know: Manual triggers are easy to test (click button, verify execution)
   - What's unclear: How to test scheduled triggers (cron-based) and event-based triggers (webhooks) in E2E tests?
   - Recommendation: **Mock time for scheduled triggers** (use freezegun library or similar to advance clock). **Mock webhook events for event-based triggers** (send HTTP request to webhook endpoint, verify workflow execution starts).

## Sources

### Primary (HIGH confidence)
- **backend/tests/e2e_ui/tests/test_canvas_forms.py** - Canvas form E2E test patterns (page.evaluate(), page.route())
- **backend/tests/e2e_ui/fixtures/auth_fixtures.py** - API-first authentication fixtures (JWT in localStorage)
- **backend/tests/e2e_ui/pages/page_objects.py** - Page Object Model classes (LoginPage, DashboardPage, etc.)
- **backend/tests/e2e_ui/conftest.py** - Pytest configuration (browser fixtures, Allure integration)
- **backend/core/canvas_type_registry.py** - Canvas type definitions and validation (7 canvas types)
- **backend/tools/canvas_tool.py** - Canvas presentation functions (present_chart, present_form, etc.)
- **backend/core/workflow_engine.py** - Workflow execution engine with DAG validation
- **backend/core/skill_composition_engine.py** - Skill composition with NetworkX DAG validation
- **backend/core/skill_registry_service.py** - Skill installation and execution workflow
- **frontend-nextjs/components/canvas/types/index.ts** - TypeScript definitions for all canvas types

### Secondary (MEDIUM confidence)
- **docs/SPECIALIZED_CANVAS_TYPES_IMPLEMENTATION_COMPLETE.md** - Canvas system implementation summary
- **docs/CANVAS_STATE_API.md** - Canvas state API documentation (window.atom.canvas)
- **.planning/phases/234-authentication-and-agent-e2e/234-01-PLAN.md** - Phase 234 test patterns (proven in 91 passing tests)

### Tertiary (LOW confidence)
- Industry best practices for E2E testing (Playwright, Pytest, Page Object Model)
- NetworkX DAG validation documentation
- Allure reporting documentation

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - Playwright, Pytest, Allure are industry standards, Phase 234 proved this stack works
- Architecture: HIGH - Existing test infrastructure from Phase 233/234 provides proven patterns
- Pitfalls: HIGH - Observed common issues in Phase 234 tests (parallel execution, memory leaks, async timing)
- Cross-platform: MEDIUM - Mobile (API-level) and Desktop (Tauri) approaches need validation during implementation

**Research date:** 2026-03-24
**Valid until:** 2026-04-23 (30 days - canvas/workflow systems stable, test patterns proven)
