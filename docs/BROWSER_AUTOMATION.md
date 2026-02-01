# Browser Automation with CDP

## Overview

Atom now includes comprehensive browser automation capabilities using Chrome DevTools Protocol (CDP) via Playwright. This enables AI agents to perform web scraping, form filling, multi-step web workflows, screenshot capture, and browser-based testing.

## Features

### Core Capabilities

### Core Capabilities

- **Browser Session Management**: Create, manage, and close browser sessions with automatic cleanup
- **Local Browser Control**: Control local headful browsers via the Satellite bridge (Tauri Desktop App)
- **Navigation**: Navigate to URLs with configurable wait conditions (load, domcontentloaded, networkidle)
- **Screenshots**: Capture full page or viewport screenshots as base64 or files
- **Form Automation**: Fill forms by CSS selector, submit forms, handle various input types
- **Element Interaction**: Click elements, wait for selectors, handle dynamic content
- **Text Extraction**: Extract text from full page or specific elements
- **Script Execution**: Execute custom JavaScript in browser context
- **Multi-Browser Support**: Chromium (default), Firefox, WebKit
- **Headless Mode**: Run headless (default) or headed for debugging

### Governance Integration

- **INTERN+ Maturity Required**: All browser actions require INTERN maturity level or higher
- **Full Audit Trail**: Every browser action logged to `browser_audit` table
- **Agent Attribution**: All sessions and actions linked to specific agents
- **Execution Tracking**: Browser operations tracked in `AgentExecution` records
- **Permission Checks**: Governance validation before browser operations

## Architecture

```
User Request
    ↓
API Endpoint (/api/browser/*)
    ↓
Governance Check (AgentContextResolver → AgentGovernanceService)
    ↓
Browser Tool Function (browser_tool.py)
    ↓
BrowserSessionManager (session lifecycle)
    ↓
Playwright (CDP control)
    ↓
Audit Entry (browser_audit table)
```

## Database Models

### BrowserSession

Tracks browser sessions with configuration and state:

```python
class BrowserSession(Base):
    id: str                          # Primary key
    session_id: str                  # External session ID
    agent_id: str                    # Agent that created session
    user_id: str                     # User that owns session
    browser_type: str                # chromium, firefox, webkit
    headless: bool                   # Headless mode
    status: str                      # active, closed, error
    current_url: str                 # Current page URL
    page_title: str                  # Current page title
    created_at: datetime             # Session creation time
    closed_at: datetime              # Session close time
```

### BrowserAudit

Audit trail for all browser operations:

```python
class BrowserAudit(Base):
    id: str                          # Primary key
    session_id: str                  # Browser session ID
    agent_id: str                    # Agent that performed action
    user_id: str                     # User that initiated action
    action_type: str                 # navigate, click, fill, etc.
    action_target: str               # URL, selector, script
    action_params: JSON              # Full parameters
    success: bool                    # Action success status
    result_summary: str              # Human-readable result
    error_message: str               # Error details if failed
    result_data: JSON                # Structured result data
    duration_ms: int                 # Execution duration
    created_at: datetime             # Action timestamp
```

## API Endpoints

### Create Browser Session

```http
POST /api/browser/session/create
Content-Type: application/json

{
  "headless": true,
  "browser_type": "chromium",
  "agent_id": "agent-1"  // Optional, for governance
}

Response:
{
  "success": true,
  "session_id": "uuid",
  "browser_type": "chromium",
  "headless": true,
  "created_at": "2026-01-31T12:00:00Z"
}
```

### Navigate to URL

```http
POST /api/browser/navigate
Content-Type: application/json

{
  "session_id": "uuid",
  "url": "https://example.com",
  "wait_until": "load",
  "agent_id": "agent-1"  // Optional, for governance
}

Response:
{
  "success": true,
  "url": "https://example.com",
  "title": "Example Domain",
  "status": 200
}
```

### Take Screenshot

```http
POST /api/browser/screenshot
Content-Type: application/json

{
  "session_id": "uuid",
  "full_page": false,
  "path": "/path/to/screenshot.png"  // Optional
}

Response:
{
  "success": true,
  "data": "base64_encoded_png",
  "size_bytes": 12345,
  "format": "png"
}
```

### Fill Form

```http
POST /api/browser/fill-form
Content-Type: application/json

{
  "session_id": "uuid",
  "selectors": {
    "#name": "John Doe",
    "#email": "john@example.com",
    "#message": "Hello"
  },
  "submit": true
}

Response:
{
  "success": true,
  "fields_filled": 3,
  "submitted": true,
  "submission_method": "submit_button"
}
```

### Click Element

```http
POST /api/browser/click
Content-Type: application/json

{
  "session_id": "uuid",
  "selector": "#submit-button",
  "wait_for": ".success-message"  // Optional
}

Response:
{
  "success": true,
  "selector": "#submit-button"
}
```

### Extract Text

```http
POST /api/browser/extract-text
Content-Type: application/json

{
  "session_id": "uuid",
  "selector": ".content"  // Optional, null for full page
}

Response:
{
  "success": true,
  "text": "Extracted text content...",
  "length": 1234
}
```

### Execute JavaScript

```http
POST /api/browser/execute-script
Content-Type: application/json

{
  "session_id": "uuid",
  "script": "return document.title;"
}

Response:
{
  "success": true,
  "result": "Page Title"
}
```

### Close Session

```http
POST /api/browser/session/close
Content-Type: application/json

{
  "session_id": "uuid"
}

Response:
{
  "success": true,
  "session_id": "uuid"
}
```

### List Sessions

```http
GET /api/browser/sessions

Response:
{
  "success": true,
  "sessions": [
    {
      "session_id": "uuid",
      "browser_type": "chromium",
      "status": "active",
      "current_url": "https://example.com",
      "page_title": "Example",
      "created_at": "2026-01-31T12:00:00Z"
    }
  ]
}
```

### Get Audit Log

```http
GET /api/browser/audit?session_id=uuid&limit=100

Response:
{
  "success": true,
  "audits": [
    {
      "id": "audit-1",
      "session_id": "uuid",
      "action_type": "navigate",
      "action_target": "https://example.com",
      "success": true,
      "result_summary": "Example Domain",
      "duration_ms": 1234,
      "created_at": "2026-01-31T12:00:00Z"
    }
  ]
}
```

## Usage Examples

### Example 1: Web Scraping

```python
from tools.browser_tool import (
    browser_create_session,
    browser_navigate,
    browser_extract_text,
    browser_close_session,
)

# Create session
session = await browser_create_session(
    user_id="user-1",
    headless=True
)

# Navigate
result = await browser_navigate(
    session_id=session["session_id"],
    url="https://example.com",
    user_id="user-1"
)

# Extract text
text_result = await browser_extract_text(
    session_id=session["session_id"],
    selector=".article-content",
    user_id="user-1"
)

print(f"Extracted: {text_result['text']}")

# Cleanup
await browser_close_session(
    session_id=session["session_id"],
    user_id="user-1"
)
```

### Example 2: Form Automation

```python
from tools.browser_tool import (
    browser_create_session,
    browser_navigate,
    browser_fill_form,
    browser_screenshot,
    browser_close_session,
)

# Create session
session = await browser_create_session(user_id="user-1")

# Navigate to form
await browser_navigate(
    session_id=session["session_id"],
    url="https://example.com/form",
    user_id="user-1"
)

# Fill form
await browser_fill_form(
    session_id=session["session_id"],
    selectors={
        "#name": "John Doe",
        "#email": "john@example.com",
        "#message": "Hello World"
    },
    submit=True,
    user_id="user-1"
)

# Take screenshot of result
await browser_screenshot(
    session_id=session["session_id"],
    full_page=True,
    user_id="user-1"
)

# Close session
await browser_close_session(
    session_id=session["session_id"],
    user_id="user-1"
)
```

### Example 3: Multi-Step Workflow

```python
from tools.browser_tool import (
    browser_create_session,
    browser_navigate,
    browser_click,
    browser_extract_text,
    browser_close_session,
)

# Create session
session = await browser_create_session(user_id="user-1")

# Step 1: Navigate to login
await browser_navigate(
    session_id=session["session_id"],
    url="https://example.com/login",
    user_id="user-1"
)

# Step 2: Fill and submit login form
await browser_fill_form(
    session_id=session["session_id"],
    selectors={
        "#username": "user@example.com",
        "#password": "password123"
    },
    submit=True,
    user_id="user-1"
)

# Step 3: Wait for redirect and extract data
await browser_extract_text(
    session_id=session["session_id"],
    selector=".dashboard-stats",
    user_id="user-1"
)

# Step 4: Click to navigate to reports
await browser_click(
    session_id=session["session_id"],
    selector="#reports-link",
    wait_for=".report-table",
    user_id="user-1"
)

# Step 5: Extract report data
reports = await browser_extract_text(
    session_id=session["session_id"],
    selector=".report-table",
    user_id="user-1"
)

# Cleanup
await browser_close_session(
    session_id=session["session_id"],
    user_id="user-1"
)
```

### Example 4: Agent Integration with Governance

```python
from tools.browser_tool import browser_create_session
from core.agent_context_resolver import AgentContextResolver
from core.agent_governance_service import AgentGovernanceService

# Agent-initiated browser session
# (Governance automatically checks INTERN+ maturity)
result = await browser_create_session(
    user_id="user-1",
    agent_id="intern-agent-1",  # Agent must be INTERN+ or governance blocks
    headless=True,
    db=db_session
)

if result["success"]:
    print(f"Session created: {result['session_id']}")

    # All subsequent actions tracked to agent
    # Audit entries include agent_id and agent_execution_id
```

## Environment Variables

```bash
# Browser Automation
BROWSER_GOVERNANCE_ENABLED=true        # Enable governance checks (default: true)
BROWSER_HEADLESS=true                  # Run headless mode (default: true)
EMERGENCY_GOVERNANCE_BYPASS=false     # Emergency bypass (default: false)
```

## Agent Maturity Requirements

| Action | Complexity | Required Maturity |
|--------|-----------|-------------------|
| browser_navigate | 2 | INTERN+ |
| browser_screenshot | 2 | INTERN+ |
| browser_extract_text | 2 | INTERN+ |
| browser_fill_form | 2 | INTERN+ |
| browser_click | 2 | INTERN+ |
| browser_execute_script | 2 | INTERN+ |

## Security Considerations

### Browser Isolation

- Each session runs in isolated browser context
- Sessions are scoped to individual users
- No cross-session data sharing

### Audit Trail

- Every browser action logged with full parameters
- Agent attribution for all operations
- Timing data for performance analysis

### Governance

- INTERN+ maturity required for browser automation
- Student agents cannot use browser features
- All operations governed by agent confidence scores

### Data Privacy

- Screenshots and extracted text stored in audit logs
- Sensitive data should be handled with care
- Consider data retention policies

## Testing

### Run Tests

```bash
# Run browser automation tests
cd backend
pytest tests/test_browser_automation.py -v

# Run with coverage
pytest tests/test_browser_automation.py --cov=tools.browser_tool --cov-report=html
```

### Test Coverage

The test suite includes:
- Browser session lifecycle (create, close, cleanup)
- All browser operations (navigate, screenshot, fill, click, extract, execute)
- Governance integration (permission checks, agent tracking)
- Audit trail creation
- Error handling (session not found, wrong user, etc.)
- Performance tests (session manager cleanup)

## Troubleshooting

### Issue: Session creation fails

**Symptoms**: `browser_create_session` returns error

**Solutions**:
1. Check Playwright installation: `playwright install chromium`
2. Verify dependencies: `pip install playwright`
3. Check system resources (memory, CPU)
4. Review logs for detailed error messages

### Issue: Navigation timeout

**Symptoms**: `browser_navigate` times out after 30 seconds

**Solutions**:
1. Increase timeout in the function
2. Check network connectivity
3. Try different `wait_until` value (domcontentloaded vs load)
4. Verify target URL is accessible

### Issue: Element not found

**Symptoms**: `browser_click` or `browser_fill_form` fails with element not found

**Solutions**:
1. Verify CSS selector is correct
2. Add explicit wait before action
3. Use browser DevTools to inspect element
4. Check if element is in iframe (requires context switching)

### Issue: Governance blocks agent

**Symptoms**: Browser operations fail with "Agent not permitted"

**Solutions**:
1. Check agent maturity level (must be INTERN+)
2. Verify agent confidence score
3. Review governance check logs
4. Promote agent to INTERN level if appropriate

## Performance Considerations

### Session Management

- Sessions auto-close after 30 minutes of inactivity
- Manual session closing recommended when done
- Limit concurrent sessions per user

### Resource Usage

- Each browser session consumes ~50-200MB RAM
- Headless mode reduces resource usage
- Consider resource limits for multi-user deployments

### Network Performance

- Navigation speed depends on target website
- Screenshots can be large (base64 encoding)
- Consider compression for network transfers

## Future Enhancements

### Planned Features

1. **Proxy Support**: Configure proxy per session
2. **Cookie Management**: Import/export cookies
3. **Download Handling**: Manage file downloads
4. **Multiple Pages**: Support multiple pages per session
5. **Interception**: Network request/response interception
6. **Emulation**: Device/mobile emulation
7. **PDF Generation**: Generate PDF from pages
8. **Video Recording**: Record session videos

### Researching

1. **Distributed Sessions**: Redis-backed session storage
2. **Session Pooling**: Reuse browser instances
3. **Smart Waits**: AI-powered wait strategies
4. **Visual Testing**: Screenshot comparison

## Comparison with OpenClaw

| Feature | Atom | OpenClaw |
|---------|------|----------|
| Browser Control | ✅ Playwright (CDP) | ✅ CDP |
| Governance | ✅ Deep integration | ⚠️ Basic |
| Audit Trail | ✅ Comprehensive | ⚠️ Limited |
| Multi-Browser | ✅ Chromium, Firefox, WebKit | ⚠️ Chromium only |
| Headless Mode | ✅ Yes | ✅ Yes |
| Agent Attribution | ✅ Full tracking | ⚠️ Limited |

## References

- [Playwright Documentation](https://playwright.dev/python/)
- [Chrome DevTools Protocol](https://chromedevtools.github.io/devtools-protocol/)
- [Atom Governance System](./GOVERNANCE_INTEGRATION_COMPLETE.md)
- [Agent Maturity Levels](./CLAUDE.md)

## Summary

Atom's browser automation feature provides **enterprise-grade web automation** with comprehensive governance, full audit trails, and seamless agent integration. It enables agents to perform complex web workflows while maintaining security and attribution.

**Key Takeaways**:
- Browser control requires **INTERN+** maturity level
- Every action is **audited** with full context
- **Session management** with automatic cleanup
- **Multi-browser support** (Chromium, Firefox, WebKit)
- **Headless mode** for server deployments

---

*For questions or issues, refer to the test files or check the logs.*
