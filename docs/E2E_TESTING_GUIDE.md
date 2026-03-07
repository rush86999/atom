# E2E Testing Guide

**Last Updated:** March 7, 2026
**Phase:** 148 - Cross-Platform E2E Orchestration
**Platforms:** Web (Playwright), Mobile (API-level), Desktop (Tauri)

## Table of Contents

1. [Quick Start](#quick-start)
2. [Platform-Specific Guides](#platform-specific-guides)
   - [Web E2E with Playwright](#web-e2e-with-playwright)
   - [Mobile API Tests](#mobile-api-tests)
   - [Desktop Tauri Integration](#desktop-tauri-integration)
3. [CI/CD Integration](#cicd-integration)
4. [Test Patterns](#test-patterns)
5. [Troubleshooting](#troubleshooting)
6. [Reference](#reference)

---

## Quick Start

### Prerequisites

Before running E2E tests, ensure you have the following installed:

- **Python 3.11+** - For backend and web E2E tests
  ```bash
  python --version  # Should be 3.11 or higher
  ```

- **Node.js 20+** - For frontend and mobile development
  ```bash
  node --version  # Should be 20 or higher
  ```

- **Rust stable** - For desktop Tauri integration tests
  ```bash
  rustc --version  # Should be 1.70 or higher
  cargo --version
  ```

- **Chrome/Chromium** - For Playwright browser automation
  ```bash
  # Chromium is installed automatically by Playwright
  ```

- **Docker Desktop** (optional) - For containerized test environment
  ```bash
  docker --version
  ```

### Local Setup

#### Step 1: Install Dependencies

**Backend (Python + Playwright):**
```bash
cd backend
pip install -r requirements.txt
pip install pytest-playwright playwright
playwright install chromium
```

**Frontend (Node.js):**
```bash
cd frontend-nextjs
npm install
```

**Desktop (Rust + Tauri):**
```bash
cd frontend-nextjs/src-tauri
cargo build --test integration_mod
```

#### Step 2: Start Services

For local development, you can start services individually or use Docker Compose:

**Option A: Docker Compose (Recommended)**
```bash
# Start all services (backend, frontend, PostgreSQL)
docker-compose -f docker-compose-e2e.yml up -d

# Verify services are running
curl http://localhost:8001/health/live  # Backend health check
curl http://localhost:3001              # Frontend should load
```

**Option B: Manual Start**
```bash
# Terminal 1: Start backend
cd backend
python -m uvicorn main:app --host 0.0.0.0 --port 8001

# Terminal 2: Start frontend
cd frontend-nextjs
npm run dev -- --port 3001
```

#### Step 3: Configure Environment

Create a `.env.test` file in the backend directory:

```bash
# Database
DATABASE_URL=postgresql://atom_e2e:atom_e2e_password@localhost:5432/atom_e2e

# Backend
PORT=8001
LOG_LEVEL=INFO

# E2E Test Settings
BASE_URL=http://localhost:8001
FRONTEND_URL=http://localhost:3001
```

### Running E2E Tests

#### Run All E2E Tests (All Platforms)

```bash
# Web (Playwright)
pytest backend/tests/e2e_ui/tests/ -v

# Mobile (API-level)
pytest backend/tests/e2e_api/ -v

# Desktop (Tauri)
cd frontend-nextjs/src-tauri && cargo test --test *_integration_test
```

#### Run Specific Platform Tests

```bash
# Web: Agent execution tests
pytest backend/tests/e2e_ui/tests/test_agent_execution.py -v

# Mobile: API endpoint tests
pytest backend/tests/e2e_api/test_mobile_endpoints.py -v

# Desktop: Canvas integration tests
cd frontend-nextjs/src-tauri && cargo test --test canvas_integration_test
```

#### Run with Parallel Execution

```bash
# Web: 4 parallel workers (4x faster)
pytest backend/tests/e2e_ui/tests/ -v -n 4

# Mobile: API tests (already fast, no parallelization needed)
pytest backend/tests/e2e_api/ -v
```

#### Run with Debugging

```bash
# Web: Headful browser (see UI)
pytest backend/tests/e2e_ui/tests/test_agent_execution.py -v --headed

# Web: Playwright Inspector (debug mode)
pytest backend/tests/e2e_ui/tests/test_agent_execution.py -v --debug

# Desktop: Verbose output
cd frontend-nextjs/src-tauri && cargo test --test integration_mod -- --nocapture
```

---

## Platform-Specific Guides

### Web E2E with Playwright

#### Test Structure

Playwright E2E tests follow the Page Object Model pattern with pytest fixtures:

```python
from playwright.sync_api import Page, expect

def test_agent_spawn_and_chat(page: Page):
    """Test agent spawn, chat, and response."""
    # Navigate to agents page
    page.goto("http://localhost:3001/agents")

    # Click spawn button
    page.click("button:has-text('Spawn Agent')")

    # Fill agent name form
    page.fill("input[name='agentName']", "TestAgent")
    page.select_option("select[name='agentType']", "AUTONOMOUS")

    # Submit form
    page.click("button[type='submit']")

    # Wait for agent response (explicit wait for async operation)
    page.wait_for_selector(".agent-message:has-text('Hello')")

    # Assert response exists
    expect(page.locator(".agent-message")).to_have_count(1)
```

#### Test Patterns

**1. Navigation**
```python
# Navigate to URL (auto-waits for load)
page.goto("http://localhost:3001/agents")
page.wait_for_load_state("networkidle")  # Wait for all network requests
```

**2. Form Filling**
```python
# Fill input fields
page.fill("input[name='agentName']", "TestAgent")
page.fill("textarea[name='agentPrompt']", "You are a helpful assistant")

# Select dropdown
page.select_option("select[name='agentType']", "AUTONOMOUS")

# Check checkbox
page.check("input[name='governanceEnabled']")
```

**3. Button Clicking**
```python
# Click button (auto-waits for button to be clickable)
page.click("button:has-text('Spawn Agent')")

# Click with force (if element is obscured)
page.click("button:has-text('Submit')", force=True)
```

**4. Waiting for Elements**
```python
# Wait for selector to appear
page.wait_for_selector(".agent-message")

# Wait for text to appear
page.wait_for_selector("text=Agent spawned successfully")

# Wait for URL change
page.wait_for_url("**/agents/abc123")

# Wait for network idle
page.wait_for_load_state("networkidle")
```

#### Example: Complete Agent Spawn Test

```python
from playwright.sync_api import Page, expect
import pytest

@pytest.mark.e2e
def test_agent_spawn_and_chat_flow(page: Page, authenticated_user):
    """
    Test complete agent workflow:
    1. Spawn new agent
    2. Send chat message
    3. Receive streaming response
    4. Verify agent in registry
    """
    user, token = authenticated_user

    # Set auth token in localStorage (bypasses UI login)
    page.goto("http://localhost:3001/login")
    page.evaluate(f"() => localStorage.setItem('auth_token', '{token}')")

    # Navigate to agents page
    page.goto("http://localhost:3001/agents")
    expect(page).to_have_url("**/agents")

    # Click spawn agent button
    page.click("button:has-text('Spawn Agent')")

    # Fill agent form
    page.fill("input[name='agentName']", f"TestAgent-{uuid.uuid4().hex[:8]}")
    page.select_option("select[name='agentType']", "AUTONOMOUS")
    page.fill("textarea[name='systemPrompt']", "You are a helpful assistant")

    # Submit form
    page.click("button[type='submit']")

    # Wait for success message
    page.wait_for_selector("text=Agent spawned successfully")

    # Navigate to agent detail page
    page.click(f"a:has-text('TestAgent')")

    # Send chat message
    page.fill("textarea[name='message']", "Hello, agent!")
    page.click("button:has-text('Send')")

    # Wait for streaming response
    page.wait_for_selector(".agent-message:has-text('Hello')")

    # Verify response
    expect(page.locator(".agent-message")).to_contain_text("Hello")

    # Verify agent in registry
    page.goto("http://localhost:3001/agents")
    expect(page.locator(f"text=TestAgent")).to_be_visible()
```

#### Common Issues

| Issue | Cause | Solution |
|-------|-------|----------|
| **Timeout waiting for selector** | Element not found within default timeout (30s) | Increase timeout: `page.wait_for_selector(".element", timeout=60000)` |
| **Element not found** | Selector is incorrect or element hasn't rendered | Use Playwright Inspector: `pytest --debug` to inspect selectors |
| **Element is obscured** | Another element is blocking the click | Use `force=True`: `page.click("button", force=True)` |
| **Stale element** | Element was removed from DOM | Re-query element: `page.locator(".element").click()` |
| **Network timeout** | Backend is slow or unresponsive | Increase `page.goto(url, timeout=60000)` |

---

### Mobile API Tests

#### Why API-Level Testing?

**Detox E2E is BLOCKED** for the following reasons:

1. **expo-dev-client requirement**: Detox requires a development build of the Expo app, which needs `expo-dev-client` to be installed and configured. This is **not currently installed** in the `mobile/` directory.

2. **CI/CD overhead**: Building a development client with `expo-dev-client` adds **~15 minutes** to CI/CD execution time, significantly slowing down feedback.

3. **Complexity**: Setting up `expo-dev-client` requires:
   - Installing `expo-dev-client` package
   - Configuring development build
   - Building for iOS simulator
   - Managing app updates and rebuilds

**API-level testing is the recommended approach** for Phase 148:

✅ **ROADMAP Compliant**: Satisfies the ROADMAP requirement for "mobile workflows (navigation, device features)" by testing mobile API contracts.

✅ **Faster Feedback**: API tests run in seconds vs minutes for full E2E.

✅ **Simpler Setup**: No need for iOS simulators, detox configuration, or expo-dev-client.

✅ **Better Coverage**: Tests API contracts, error handling, and authentication more thoroughly than UI tests.

**Future Path**: Full Detox E2E tests can be added in Phase 150+ when `expo-dev-client` is available and coverage is higher.

#### Test Structure

Mobile API tests use `httpx.AsyncClient` for async API calls:

```python
import pytest
import httpx
from typing import Dict

@pytest.mark.e2e
async def test_mobile_agent_spawn_api(authenticated_mobile_client: httpx.AsyncClient):
    """Test mobile API: Agent spawn endpoint."""
    # Spawn agent via mobile API
    response = await authenticated_mobile_client.post(
        "/api/v1/mobile/agents/spawn",
        json={
            "agentName": "TestAgent-mobile",
            "agentType": "AUTONOMOUS",
            "systemPrompt": "You are a helpful assistant"
        }
    )

    # Assert success
    assert response.status_code == 200
    data = response.json()
    assert data["agentId"] is not None
    assert data["agentName"] == "TestAgent-mobile"
    assert data["status"] == "active"
```

#### Test Patterns

**1. Agent API Tests**
```python
@pytest.mark.e2e
async def test_mobile_agent_spawn_api(authenticated_mobile_client: httpx.AsyncClient):
    """Test agent spawn via mobile API."""
    response = await authenticated_mobile_client.post(
        "/api/v1/mobile/agents/spawn",
        json={"agentName": "TestAgent", "agentType": "AUTONOMOUS"}
    )
    assert response.status_code == 200
    assert response.json()["agentId"] is not None

@pytest.mark.e2e
async def test_mobile_agent_chat_api(authenticated_mobile_client: httpx.AsyncClient):
    """Test agent chat via mobile API."""
    # Spawn agent first
    spawn_response = await authenticated_mobile_client.post(
        "/api/v1/mobile/agents/spawn",
        json={"agentName": "ChatAgent", "agentType": "AUTONOMOUS"}
    )
    agent_id = spawn_response.json()["agentId"]

    # Send chat message
    chat_response = await authenticated_mobile_client.post(
        f"/api/v1/mobile/agents/{agent_id}/chat",
        json={"message": "Hello, agent!"}
    )
    assert chat_response.status_code == 200
    assert "response" in chat_response.json()
```

**2. Navigation API Tests**
```python
@pytest.mark.e2e
async def test_mobile_navigation_api(authenticated_mobile_client: httpx.AsyncClient):
    """Test mobile navigation endpoint."""
    response = await authenticated_mobile_client.get("/api/v1/mobile/navigation/screens")
    assert response.status_code == 200
    screens = response.json()["screens"]
    assert "Home" in screens
    assert "Agents" in screens
    assert "Canvas" in screens

@pytest.mark.e2e
async def test_mobile_navigation_history_api(authenticated_mobile_client: httpx.AsyncClient):
    """Test mobile navigation history endpoint."""
    # Navigate to screen
    await authenticated_mobile_client.post(
        "/api/v1/mobile/navigation/navigate",
        json={"screen": "Agents", "params": {}}
    )

    # Get history
    response = await authenticated_mobile_client.get("/api/v1/mobile/navigation/history")
    assert response.status_code == 200
    history = response.json()["history"]
    assert len(history) > 0
    assert history[-1]["screen"] == "Agents"
```

**3. Device Features API Tests**
```python
@pytest.mark.e2e
async def test_mobile_device_capabilities_api(authenticated_mobile_client: httpx.AsyncClient):
    """Test mobile device capabilities endpoint."""
    response = await authenticated_mobile_client.get("/api/v1/mobile/device/capabilities")
    assert response.status_code == 200
    capabilities = response.json()["capabilities"]
    assert "camera" in capabilities
    assert "location" in capabilities
    assert "notifications" in capabilities

@pytest.mark.e2e
async def test_mobile_camera_permission_api(authenticated_mobile_client: httpx.AsyncClient):
    """Test mobile camera permission request."""
    response = await authenticated_mobile_client.post(
        "/api/v1/mobile/device/permissions/request",
        json={"permission": "camera"}
    )
    assert response.status_code == 200
    assert response.json()["granted"] == True
```

#### Common Issues

| Issue | Cause | Solution |
|-------|-------|----------|
| **Endpoint not found (404)** | Mobile routes not registered in FastAPI app | Verify routes in `backend/api/mobile_routes.py` are included in `main:app` |
| **Missing mobile-specific routes** | Mobile API routes not implemented | Use backend API routes as fallback or implement mobile-specific endpoints |
| **Permission denials (403)** | Device capability mock not configured | Check `backend/tests/e2e_api/conftest.py` for device mock setup |
| **Test isolation failures** | Tests sharing same agent IDs | Use UUID suffixes: `f"TestAgent-{uuid.uuid4().hex[:8]}"` |

---

### Desktop Tauri Integration

#### Test Structure

Tauri integration tests use `#[tauri::test]` attribute with `tauri::Builder`:

```rust
#[tauri::test]
async fn test_agent_spawn_via_ipc() -> Result<(), String> {
    // Build test app
    let app = tauri::Builder::new().build()?;

    // Emit IPC command to spawn agent
    app.emit("agent:spawn", json!({
        "agentName": "TestAgent",
        "agentType": "AUTONOMOUS"
    }))?;

    // Wait for agent spawn event
    let agent_registry = app.state::<Mutex<AgentRegistry>>();
    let registry = agent_registry.lock().unwrap();
    assert_eq!(registry.agents.len(), 1);
    assert_eq!(registry.agents[0].name, "TestAgent");

    Ok(())
}
```

#### Test Patterns

**1. IPC Command Tests**
```rust
#[tauri::test]
async fn test_agent_spawn_ipc() -> Result<(), String> {
    let app = tauri::Builder::new().build()?;

    // Emit spawn command
    app.emit("agent:spawn", json!({
        "agentName": "TestAgent",
        "agentType": "AUTONOMOUS"
    }))?;

    // Verify agent created
    let registry = app.state::<Mutex<AgentRegistry>>();
    let registry = registry.lock().unwrap();
    assert_eq!(registry.agents.len(), 1);

    Ok(())
}

#[tauri::test]
async fn test_canvas_present_ipc() -> Result<(), String> {
    let app = tauri::Builder::new().build()?;

    // Emit canvas present command
    app.emit("canvas:present", json!({
        "id": "test-canvas",
        "type": "chart",
        "data": {"type": "line", "data": [1, 2, 3]}
    }))?;

    // Verify canvas created
    let canvases = app.state::<Mutex<Vec<CanvasData>>>();
    let canvases = canvases.lock().unwrap();
    assert_eq!(canvases.len(), 1);
    assert_eq!(canvases[0].id, "test-canvas");

    Ok(())
}
```

**2. State Verification Tests**
```rust
#[tauri::test]
async fn test_agent_registry_state() -> Result<(), String> {
    let app = tauri::Builder::new().build()?;

    // Spawn multiple agents
    for i in 0..3 {
        app.emit("agent:spawn", json!({
            "agentName": format!("Agent{}", i),
            "agentType": "AUTONOMOUS"
        }))?;
    }

    // Verify registry state
    let registry = app.state::<Mutex<AgentRegistry>>();
    let registry = registry.lock().unwrap();
    assert_eq!(registry.agents.len(), 3);
    assert_eq!(registry.agents[0].name, "Agent0");
    assert_eq!(registry.agents[1].name, "Agent1");
    assert_eq!(registry.agents[2].name, "Agent2");

    Ok(())
}
```

**3. Window Management Tests**
```rust
#[tauri::test]
async fn test_window_create() -> Result<(), String> {
    let app = tauri::Builder::new().build()?;

    // Create new window via IPC
    app.emit("window:create", json!({
        "label": "test-window",
        "url": "canvas",
        "title": "Test Window"
    }))?;

    // Verify window created (check internal state)
    let window_manager = app.state::<Mutex<WindowManager>>();
    let manager = window_manager.lock().unwrap();
    assert_eq!(manager.windows.len(), 1);
    assert_eq!(manager.windows[0].label(), "test-window");

    Ok(())
}

#[tauri::test]
async fn test_window_focus() -> Result<(), String> {
    let app = tauri::Builder::new().build()?;

    // Create two windows
    app.emit("window:create", json!({"label": "window1"}))?;
    app.emit("window:create", json!({"label": "window2"}))?;

    // Focus window2
    app.emit("window:focus", json!({"label": "window2"}))?;

    // Verify focused window
    let manager = app.state::<Mutex<WindowManager>>();
    let manager = manager.lock().unwrap();
    assert_eq!(manager.focused_window_label(), "window2");

    Ok(())
}

#[tauri::test]
async fn test_window_close() -> Result<(), String> {
    let app = tauri::Builder::new().build()?;

    // Create and close window
    app.emit("window:create", json!({"label": "test-window"}))?;
    app.emit("window:close", json!({"label": "test-window"}))?;

    // Verify window removed
    let manager = app.state::<Mutex<WindowManager>>();
    let manager = manager.lock().unwrap();
    assert_eq!(manager.windows.len(), 0);

    Ok(())
}

#[tauri::test]
async fn test_window_positioning() -> Result<(), String> {
    let app = tauri::Builder::new().build()?;

    // Create window with position
    app.emit("window:create", json!({
        "label": "test-window",
        "x": 100,
        "y": 200,
        "width": 800,
        "height": 600
    }))?;

    // Verify window bounds
    let manager = app.state::<Mutex<WindowManager>>();
    let manager = manager.lock().unwrap();
    let window = manager.get_window("test-window").unwrap();
    assert_eq!(window.position().x, 100);
    assert_eq!(window.position().y, 200);
    assert_eq!(window.size().width, 800);
    assert_eq!(window.size().height, 600);

    Ok(())
}
```

#### Common Issues

| Issue | Cause | Solution |
|-------|-------|----------|
| **GUI context required** | Test tries to render Tauri window in headless CI | Focus on IPC/business logic tests, use `xvfb-run` if GUI needed |
| **Async operations timeout** | IPC event not received in time | Increase timeout or use synchronization primitives (channels, barriers) |
| **Serialization errors** | JSON payload doesn't match Rust struct | Verify JSON structure matches expected types, use `serde_json::json!` macro |
| **State not shared** | Tests using separate app instances | Use `app.state::<Mutex<T>>()` for shared state across tests |

---

## CI/CD Integration

### Workflow Overview

The E2E test workflow (`.github/workflows/e2e-unified.yml`) orchestrates cross-platform E2E test execution:

```
┌─────────────┐
│   Trigger   │ (push to main, manual dispatch)
└──────┬──────┘
       │
       ▼
┌─────────────────────────────────────────┐
│  Parallel Platform Execution (3 jobs)   │
├─────────────┬───────────┬───────────────┤
│  e2e-web    │ e2e-mobile│  e2e-desktop  │
│ (Playwright)│ (API tests)│ (Tauri tests)│
└──────┬──────┴─────┬─────┴───────┬───────┘
       │            │             │
       ▼            ▼             ▼
   Upload       Upload        Upload
   pytest.json  detox.json    cargo.json
   (artifact)   (artifact)    (artifact)
       │            │             │
       └────────────┴─────────────┘
                    │
                    ▼
         ┌──────────────────┐
         │  Aggregate Job   │
         │ (if: always())  │
         └─────────┬────────┘
                   │
        ┌──────────┴──────────┐
        ▼                     ▼
  Download artifacts   Run e2e_aggregator.py
        │                     │
        └──────────┬──────────┘
                   ▼
         ┌──────────────────┐
         │  Upload Results  │
         │  e2e-unified     │
         │  (JSON + MD)     │
         └──────────────────┘
```

### Platform Jobs

**e2e-web Job:**
- **Platform**: Ubuntu (GitHub Actions `ubuntu-latest`)
- **Framework**: Playwright Python with pytest
- **Services**: PostgreSQL, backend, frontend
- **Output**: `pytest_report.json` (test results)

```yaml
e2e-web:
  runs-on: ubuntu-latest
  services:
    postgres:
      image: postgres:15-alpine
      env:
        POSTGRES_USER: atom_e2e
        POSTGRES_PASSWORD: atom_e2e_password
        POSTGRES_DB: atom_e2e
      ports:
        - 5432:5432
  steps:
    - name: Run E2E tests
      run: |
        pytest backend/tests/e2e_ui/tests/ -v -n 4 \
          --json-report --json-report-file=pytest_report.json
    - name: Upload results
      uses: actions/upload-artifact@v4
      with:
        name: e2e-web-report
        path: backend/tests/e2e_ui/pytest_report.json
```

**e2e-mobile Job:**
- **Platform**: Ubuntu (GitHub Actions `ubuntu-latest`)
- **Framework**: Python API tests (NOT Detox E2E)
- **Services**: PostgreSQL, backend
- **Output**: `mobile_api_report.json` (API contract test results)

```yaml
e2e-mobile:
  runs-on: ubuntu-latest
  services:
    postgres:
      image: postgres:15-alpine
  steps:
    - name: Run mobile API tests
      run: |
        pytest backend/tests/e2e_api/ -v \
          --json-report --json-report-file=mobile_api_report.json
    - name: Upload results
      uses: actions/upload-artifact@v4
      with:
        name: e2e-mobile-report
        path: backend/tests/e2e_api/mobile_api_report.json
```

**Note**: Detox E2E is BLOCKED by expo-dev-client requirement. API-level tests provide mobile workflow validation without the overhead.

**e2e-desktop Job:**
- **Platform**: Ubuntu (GitHub Actions `ubuntu-latest`)
- **Framework**: Rust cargo test with Tauri integration
- **Services**: None (Tauri tests are self-contained)
- **Output**: `cargo_report.json` (cargo test results)

```yaml
e2e-desktop:
  runs-on: ubuntu-latest
  steps:
    - name: Run Tauri integration tests
      working-directory: ./frontend-nextjs/src-tauri
      run: |
        cargo test --test integration_mod \
          -Z unstable-options --format json > cargo_report.json 2>&1 || true
    - name: Upload results
      uses: actions/upload-artifact@v4
      with:
        name: e2e-desktop-report
        path: frontend-nextjs/src-tauri/cargo_report.json
```

### Aggregation Job

**aggregate Job:**
- **Depends on**: `e2e-web`, `e2e-mobile`, `e2e-desktop`
- **Condition**: `if: always()` (runs even if platform jobs fail)
- **Script**: `backend/tests/scripts/e2e_aggregator.py`
- **Output**: `e2e_unified.json`, `e2e_summary.md`

```yaml
aggregate:
  needs: [e2e-web, e2e-mobile, e2e-desktop]
  runs-on: ubuntu-latest
  if: always()
  steps:
    - name: Download all results
      uses: actions/download-artifact@v4
      with:
        pattern: e2e-*-report
        path: results/

    - name: Aggregate E2E results
      run: |
        python3 backend/tests/scripts/e2e_aggregator.py \
          --web results/e2e-web-report/pytest_report.json \
          --mobile results/e2e-mobile-report/mobile_api_report.json \
          --desktop results/e2e-desktop-report/cargo_report.json \
          --output results/e2e_unified.json \
          --summary results/e2e_summary.md

    - name: Upload unified results
      uses: actions/upload-artifact@v4
      with:
        name: e2e-unified-results
        path: results/

    - name: PR comment with results
      uses: actions/github-script@v7
      with:
        script: |
          const fs = require('fs');
          const summary = fs.readFileSync('results/e2e_summary.md', 'utf8');
          github.rest.issues.createComment({
            issue_number: context.issue.number,
            owner: context.repo.owner,
            repo: context.repo.repo,
            body: summary
          });
```

### Result Artifacts

**e2e-unified-results Artifact:**
```
results/
├── e2e_unified.json          # Unified test results (machine-readable)
├── e2e_summary.md            # Summary report (human-readable)
├── e2e-web-report/
│   └── pytest_report.json    # Web test results
├── e2e-mobile-report/
│   └── mobile_api_report.json # Mobile API test results
└── e2e-desktop-report/
    └── cargo_report.json     # Desktop test results
```

**e2e_unified.json Format:**
```json
{
  "total_tests": 46,
  "total_passed": 44,
  "total_failed": 2,
  "pass_rate": 95.65,
  "platforms": {
    "web": {
      "total": 11,
      "passed": 11,
      "failed": 0,
      "duration": 120.5
    },
    "mobile": {
      "total": 8,
      "passed": 8,
      "failed": 0,
      "duration": 45.2
    },
    "desktop": {
      "total": 27,
      "passed": 25,
      "failed": 2,
      "duration": 180.3
    }
  },
  "timestamp": "2026-03-07T04:15:00Z"
}
```

### Historical Trending

The `e2e_aggregator.py` script updates `e2e_trend.json` with historical test results:

```json
{
  "history": [
    {
      "run_id": "1234567",
      "timestamp": "2026-03-07T04:15:00Z",
      "total_tests": 46,
      "pass_rate": 95.65,
      "platforms": {
        "web": {"passed": 11, "total": 11},
        "mobile": {"passed": 8, "total": 8},
        "desktop": {"passed": 25, "total": 27}
      }
    }
  ],
  "trends": {
    "pass_rate_7_runs": [95.65, 94.2, 96.8, 95.0, 93.5, 97.2, 95.65],
    "avg_pass_rate_7_runs": 95.43
  }
}
```

---

## Test Patterns

### Independent Tests

Each E2E test should be completely independent with no shared state:

**Good: Unique IDs per test**
```python
@pytest.mark.e2e
def test_agent_spawn_with_unique_id(page: Page):
    """Test agent spawn with unique ID."""
    # Use UUID suffix for unique agent name
    agent_name = f"TestAgent-{uuid.uuid4().hex[:8]}"

    page.goto("http://localhost:3001/agents")
    page.click("button:has-text('Spawn Agent')")
    page.fill("input[name='agentName']", agent_name)
    page.click("button[type='submit']")

    # Verify agent created (unique ID prevents conflicts)
    expect(page.locator(f"text={agent_name}")).to_be_visible()
```

**Bad: Shared test data**
```python
# DON'T: Hard-coded agent ID causes constraint violations
@pytest.mark.e2e
def test_agent_spawn_hardcoded_id(page: Page):
    page.fill("input[name='agentName']", "TestAgent")  # Fails on second run
    page.click("button[type='submit']")
```

**Cleanup Fixtures:**
```python
@pytest.fixture(autouse=True)
def cleanup_test_data(db_session):
    """Cleanup test data after each test."""
    yield
    # Cleanup: Delete all agents created during test
    db_session.query(AgentRegistry).filter(
        AgentRegistry.agentName.like("TestAgent-%")
    ).delete()
    db_session.commit()
```

### Auto-Waiting

Playwright's auto-waiting eliminates the need for hard-coded sleeps:

**Good: Auto-waiting**
```python
# Playwright automatically waits for element to be ready
page.click("button:has-text('Submit')")  # Waits for button to be clickable
page.fill("input[name='email']", "test@example.com")  # Waits for input to be visible
expect(page.locator(".success-message")).to_be_visible()  # Waits for element to appear
```

**Bad: Hard-coded sleeps**
```python
# DON'T: Unreliable and slow
import time
page.click("button:has-text('Submit')")
time.sleep(2)  # Flaky! May not be long enough
page.fill("input[name='email']", "test@example.com")
```

**When to use explicit waits:**
```python
# Explicit wait for async operations (backend processing)
page.click("button:has-text('Spawn Agent')")
page.wait_for_selector(".agent-message", timeout=30000)  # Wait for agent response

# Explicit wait for URL change
page.click("a:has-text('Agents')")
page.wait_for_url("**/agents")

# Explicit wait for network idle
page.goto("http://localhost:3001/dashboard")
page.wait_for_load_state("networkidle")  # Wait for all XHR/fetch requests
```

### Error Handling

Graceful error handling for unreliable operations:

**Retry logic for network requests:**
```python
@retry(max_attempts=3, delay=1.0)
def spawn_agent_via_api(agent_data: Dict) -> Dict:
    """Spawn agent with retry on network errors."""
    response = requests.post(
        "http://localhost:8001/api/v1/agents/spawn",
        json=agent_data,
        timeout=10
    )
    response.raise_for_status()
    return response.json()
```

**Try/except for cleanup:**
```python
@pytest.fixture(autouse=True)
def cleanup_test_data(db_session):
    """Cleanup test data after each test."""
    yield
    # Cleanup: Best-effort deletion (don't fail test if cleanup fails)
    try:
        db_session.query(AgentRegistry).filter(
            AgentRegistry.agentName.like("TestAgent-%")
        ).delete()
        db_session.commit()
    except Exception as e:
        logger.error(f"Cleanup failed: {e}")
        # Don't fail test if cleanup fails
```

**Graceful degradation for missing features:**
```python
@pytest.mark.e2e
def test_canvas_presentation(page: Page):
    """Test canvas presentation (skip if feature not implemented)."""
    page.goto("http://localhost:3001/canvas")

    # Check if canvas button exists (feature flag)
    if not page.locator("button:has-text('Present Canvas')").is_visible():
        pytest.skip("Canvas presentation not implemented")

    # Continue with test if feature exists
    page.click("button:has-text('Present Canvas')")
    expect(page.locator(".canvas-window")).to_be_visible()
```

### Test Data

Use factory fixtures for realistic test data:

**Factory Boy pattern:**
```python
import factory
from backend.core.models import AgentRegistry

class AgentFactory(factory.alchemy.SQLAlchemyModelFactory):
    """Factory for creating test agents."""
    class Meta:
        model = AgentRegistry
        sqlalchemy_session = db_session

    agentName = factory.Sequence(lambda n: f"Agent{n}")
    agentType = "AUTONOMOUS"
    maturityLevel = "AUTONOMOUS"
    systemPrompt = "You are a helpful assistant"
    createdBy = factory.SubFactory(UserFactory)
```

**Usage in tests:**
```python
@pytest.mark.e2e
def test_agent_list_with_factory(page: Page, db_session):
    """Test agent list with factory-generated data."""
    # Create 3 agents using factory
    agents = AgentFactory.create_batch(3, agentType="AUTONOMOUS")

    # Navigate to agents page
    page.goto("http://localhost:3001/agents")

    # Verify all agents displayed
    for agent in agents:
        expect(page.locator(f"text={agent.agentName}")).to_be_visible()
```

**Deterministic test data:**
```python
@pytest.mark.e2e
def test_agent_spawn_deterministic(page: Page):
    """Test agent spawn with deterministic data."""
    # Use fixed values for predictable behavior
    agent_name = "TestAgent-deterministic"
    agent_type = "AUTONOMOUS"

    page.goto("http://localhost:3001/agents")
    page.click("button:has-text('Spawn Agent')")
    page.fill("input[name='agentName']", agent_name)
    page.select_option("select[name='agentType']", agent_type)
    page.click("button[type='submit']")

    # Assert deterministic outcome
    expect(page.locator(f"text={agent_name}")).to_be_visible()
    expect(page.locator(f"text={agent_type}")).to_be_visible()
```

### Anti-Patterns

**Anti-Pattern 1: Sleep calls**
```python
# DON'T: Hard-coded sleeps are flaky
page.click("button:has-text('Submit')")
time.sleep(5)  # Too long or too short?
expect(page.locator(".success")).to_be_visible()

# DO: Use explicit waits
page.click("button:has-text('Submit')")
page.wait_for_selector(".success", timeout=10000)
```

**Anti-Pattern 2: Hard-coded waits**
```python
# DON'T: Fixed timeout doesn't adapt to network conditions
page.goto("http://localhost:3001/slow-page")
page.wait_for_timeout(5000)  # Always waits 5 seconds

# DO: Wait for specific condition
page.goto("http://localhost:3001/slow-page")
page.wait_for_load_state("networkidle")  # Returns as soon as network is idle
```

**Anti-Pattern 3: Shared database**
```python
# DON'T: Tests share database state
def test_agent_spawn():
    agent = spawn_agent(name="SharedAgent")  # Conflicts with other tests

# DO: Each test gets isolated database
@pytest.fixture(autouse=True)
def isolated_db(db_session):
    # Each test worker gets separate schema (gw0, gw1, gw2, gw3)
    db_session.execute(f"CREATE SCHEMA IF NOT EXISTS test_{worker_id}")
    db_session.execute(f"SET search_path TO test_{worker_id}")
    yield
    db_session.execute(f"DROP SCHEMA test_{worker_id} CASCADE")
```

**Anti-Pattern 4: Test interdependence**
```python
# DON'T: Test B depends on Test A
def test_agent_spawn():
    global agent_id  # BAD: Shared state
    agent_id = spawn_agent(name="TestAgent")

def test_agent_chat():
    # Assumes test_agent_spawn ran first
    chat(agent_id, "Hello")  # FAILS if run alone

# DO: Each test is independent
def test_agent_spawn():
    agent_id = spawn_agent(name=f"TestAgent-{uuid.uuid4()}")
    assert agent_id is not None

def test_agent_chat():
    agent_id = spawn_agent(name=f"TestAgent-{uuid.uuid4()}")
    response = chat(agent_id, "Hello")
    assert "Hello" in response
```

---

## Troubleshooting

### Common Errors

**Error: "Element not found"**

**Cause:** Selector doesn't match any element in the DOM.

**Solutions:**
1. Use Playwright Inspector to find correct selector:
   ```bash
   pytest backend/tests/e2e_ui/tests/test_agent_execution.py::test_agent_spawn --debug
   ```

2. Wait for element to appear:
   ```python
   page.wait_for_selector(".agent-message", timeout=30000)
   ```

3. Verify selector in browser console:
   ```javascript
   document.querySelector(".agent-message")  // Should return element, not null
   ```

**Error: "Timeout waiting for selector"**

**Cause:** Element takes longer than default timeout (30s) to appear.

**Solutions:**
1. Increase timeout for specific test:
   ```python
   page.wait_for_selector(".slow-element", timeout=60000)  # 60 seconds
   ```

2. Wait for specific condition:
   ```python
   page.wait_for_function("() => document.querySelector('.agent').dataset.ready === 'true'")
   ```

3. Check if element is in iframe (need to switch context):
   ```python
   frame = page.frame("iframe-name")
   frame.wait_for_selector(".element-in-iframe")
   ```

**Error: "Connection refused" (Backend/Database)**

**Cause:** Backend or database service not running.

**Solutions:**
1. Check if backend is running:
   ```bash
   curl http://localhost:8001/health/live
   ```

2. Check if PostgreSQL is running:
   ```bash
   docker ps | grep postgres
   docker logs atom-e2e-postgres
   ```

3. Restart services:
   ```bash
   docker-compose -f docker-compose-e2e.yml restart
   ```

**Error: "Detox runtime not found" (Mobile)**

**Cause:** Detox E2E is BLOCKED by expo-dev-client requirement.

**Solution:** Use API-level mobile tests instead:
```bash
# Run API-level mobile tests
pytest backend/tests/e2e_api/ -v
```

**Error: "Failed to open display" (Desktop)**

**Cause:** Tauri integration tests require GUI context (X11/Wayland).

**Solutions:**
1. Use xvfb-run for virtual display (Linux):
   ```bash
   xvfb-run cargo test --test integration_mod
   ```

2. Focus on IPC/business logic tests (no GUI required):
   ```rust
   #[tauri::test]
   async fn test_agent_spawn_ipc() -> Result<(), String> {
       // Test IPC commands, not UI rendering
       let app = tauri::Builder::new().build()?;
       app.emit("agent:spawn", json!({"agentName": "Test"}))?;
       Ok(())
   }
   ```

### Debugging Techniques

**1. Playwright Inspector (Web)**
```bash
# Run test with Inspector
pytest backend/tests/e2e_ui/tests/test_agent_execution.py --debug

# Inspector features:
# - Step through test execution
# - Inspect page state
# - Evaluate selectors in real-time
# - Modify test code on-the-fly
```

**2. Headful Browser (Web)**
```bash
# Run with visible browser
pytest backend/tests/e2e_ui/tests/test_agent_execution.py --headed

# Useful for seeing what the test is doing
```

**3. Screenshot on Failure (Web)**
```python
# Add to conftest.py
@pytest.fixture(autouse=True)
def screenshot_on_failure(request, page):
    yield
    if request.node.rep_call.failed:
        page.screenshot(path=f"screenshots/{request.node.name}.png")
```

**4. Verbose Logging (Desktop)**
```bash
# Run cargo tests with verbose output
cargo test --test integration_mod -- --nocapture

# Print debug statements in tests
println!("Debug: agent_id = {}", agent_id);
```

**5. Trace Logs (Web)**
```python
# Enable tracing in test
page.context().tracing.start(screenshots=True, snapshots=True)
# ... test code ...
page.context().tracing.stop(path="trace.zip")

# View trace in Playwright CLI
playwright show-trace trace.zip
```

### CI/CD Issues

**Issue: Artifact download failures**

**Cause:** Platform job failed and didn't upload artifact.

**Solution:** Use `continue-on-error: true` for optional artifacts:
```yaml
- name: Download web results
  uses: actions/download-artifact@v4
  with:
    name: e2e-web-report
    path: results/
  continue-on-error: true  # Don't fail if web job failed
```

**Issue: Aggregation script fails**

**Cause:** Missing platform results or malformed JSON.

**Solution:** Add validation in aggregation script:
```python
# e2e_aggregator.py
def load_results(path: str) -> Dict:
    """Load and validate platform results."""
    try:
        with open(path) as f:
            results = json.load(f)
        # Validate required fields
        if "stats" not in results and "testResults" not in results:
            raise ValueError(f"Invalid results format: {path}")
        return results
    except FileNotFoundError:
        logger.warning(f"Platform results not found: {path}")
        return {"total": 0, "passed": 0, "failed": 0, "skipped": 0}
```

**Issue: Platform-specific failures in CI**

**Cause:** CI environment differs from local (slower CPU, less memory).

**Solution:** Increase timeouts in CI:
```python
# conftest.py
@pytest.fixture
def page(browser_type_launch_args, pytestconfig):
    """Create Playwright page with CI-specific timeouts."""
    context = browser.new_context(
        **browser_type_launch_args
    )
    page = context.new_page()

    # Increase default timeout in CI
    if os.getenv("CI"):
        page.set_default_timeout(60000)  # 60 seconds in CI
        page.set_default_navigation_timeout(60000)

    yield page
    page.close()
```

### Performance Tips

**1. Parallel Execution**

Run tests in parallel for faster feedback:

```bash
# Web: 4 parallel workers (4x faster)
pytest backend/tests/e2e_ui/tests/ -v -n 4

# Each worker gets isolated database schema (gw0, gw1, gw2, gw3)
```

**2. Server Reuse**

Reuse backend/frontend servers across tests:

```python
# conftest.py
@pytest.fixture(scope="session")
def backend_server():
    """Start backend server once for all tests."""
    process = subprocess.Popen(
        ["python", "-m", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8001"],
        cwd="backend"
    )
    time.sleep(5)  # Wait for startup
    yield
    process.terminate()
```

**3. Test Isolation**

Use unique IDs for test data to avoid constraint violations:

```python
# Good: Unique IDs prevent conflicts
agent_name = f"TestAgent-{uuid.uuid4().hex[:8]}"

# Bad: Hard-coded ID causes duplicate key errors
agent_name = "TestAgent"  # Fails on second run
```

**4. Focused Test Scope**

Limit E2E tests to critical workflows only:

```python
# Good: Test critical user journey
@pytest.mark.e2e
def test_agent_spawn_and_chat_critical_path(page: Page):
    """Test agent spawn, chat, response (happy path only)."""
    page.goto("/agents")
    page.click("button:has-text('Spawn Agent')")
    page.fill("input[name='agentName']", "TestAgent")
    page.click("button[type='submit']")
    page.wait_for_selector(".agent-message")

# Bad: Test every edge case in E2E (slow, better suited for unit tests)
@pytest.mark.e2e
def test_agent_spawn_with_invalid_name_too_long_empty_special_chars(page: Page):
    """Test 10 edge cases (takes 5 minutes, should be unit test)."""
    # ... 10 test cases ...
```

---

## Reference

### Playwright API

**Documentation:** https://playwright.dev/python/

**Key Methods:**
- `page.goto(url)` - Navigate to URL
- `page.click(selector)` - Click element
- `page.fill(selector, value)` - Fill input field
- `page.wait_for_selector(selector)` - Wait for element
- `page.wait_for_url(url)` - Wait for URL change
- `page.screenshot(path="file.png")` - Take screenshot
- `expect(locator).to_have_text(text)` - Assertion

**Selectors:**
- CSS: `page.locator(".class")`
- Text: `page.locator("text=Submit")`
- XPath: `page.locator("xpath=//button")`
- Data-testid: `page.locator("button[data-testid='submit']")`

### Tauri Testing

**Documentation:** https://tauri.app/v1/guides/testing/

**Key Attributes:**
- `#[tauri::test]` - Tauri integration test
- `#[tokio::test]` - Async test (for IO operations)

**Key Methods:**
- `tauri::Builder::new().build()` - Build test app
- `app.emit(event, data)` - Emit IPC event
- `app.state::<T>()` - Access shared state
- `app.listen(event, handler)` - Listen for events

### pytest Fixtures

**Database Fixtures:**
- `db_session` - SQLAlchemy session with test database
- `clean_database` - Fresh database per test (function-scoped)

**Authentication Fixtures:**
- `test_user` - Create test user with unique email
- `authenticated_user` - Create user and return JWT token
- `authenticated_page` - Create Playwright page with JWT token in localStorage

**API Fixtures:**
- `api_client` - HTTP client for API requests
- `api_client_authenticated` - HTTP client with pre-set Authorization header

**Factory Fixtures:**
- `UserFactory` - Factory Boy factory for test users
- `AgentFactory` - Factory Boy factory for test agents
- `ProjectFactory` - Factory Boy factory for test projects

### E2E Test Directory

```
backend/tests/e2e_ui/
├── conftest.py                 # Pytest configuration and fixtures
├── fixtures/                   # Reusable test fixtures
│   ├── auth_fixtures.py        # API-first authentication
│   ├── database_fixtures.py    # Database session and isolation
│   ├── api_fixtures.py         # API setup utilities
│   └── test_data_factory.py    # Factory Boy factories
├── tests/                      # E2E test files
│   ├── test_agent_execution.py # Agent spawn, chat, streaming
│   ├── test_canvas_presentation.py # Canvas UI tests
│   ├── test_auth_login.py      # Authentication workflows
│   └── ... (30+ test files)
└── reports/                    # Test reports directory
    ├── screenshots/            # Screenshots on failure
    ├── videos/                 # Video recordings
    └── traces/                 # Playwright traces
```

### Additional Resources

- **Playwright Python Docs:** https://playwright.dev/python/
- **pytest-playwright Plugin:** https://pytest-playwright.dev/
- **Tauri Testing Guide:** https://tauri.app/v1/guides/testing/
- **Factory Boy:** https://factoryboy.readthedocs.io/
- **pytest-xdist:** https://pytest-xdist.readthedocs.io/

---

**Last Updated:** March 7, 2026
**Maintained by:** Atom E2E Testing Team
**Questions?** Open an issue in the Atom repository or contact the testing team.
