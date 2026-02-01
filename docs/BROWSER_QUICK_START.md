# Browser Automation Quick Start

## Installation

1. **Install Playwright** (already in requirements.txt):

```bash
cd backend
pip install playwright
playwright install chromium
```

2. **Run Database Migration**:

```bash
alembic upgrade head
```

3. **Start the Backend**:

```bash
python main_api_app.py
```

## Basic Usage

### 1. Create a Browser Session

```python
from tools.browser_tool import browser_create_session

# Create headless session
session = await browser_create_session(
    user_id="user-1",
    headless=True,
    browser_type="chromium"
)

session_id = session["session_id"]
print(f"Session created: {session_id}")
```

### 2. Navigate to a URL

```python
from tools.browser_tool import browser_navigate

result = await browser_navigate(
    session_id=session_id,
    url="https://example.com",
    user_id="user-1"
)

print(f"Navigated to: {result['url']}")
print(f"Page title: {result['title']}")
```

### 3. Take a Screenshot

```python
from tools.browser_tool import browser_screenshot

# Get screenshot as base64
screenshot = await browser_screenshot(
    session_id=session_id,
    full_page=True,
    user_id="user-1"
)

# Save to file
import base64
with open("screenshot.png", "wb") as f:
    f.write(base64.b64decode(screenshot["data"]))
```

### 4. Fill a Form

```python
from tools.browser_tool import browser_fill_form

result = await browser_fill_form(
    session_id=session_id,
    selectors={
        "#name": "John Doe",
        "#email": "john@example.com",
        "#message": "Hello World"
    },
    submit=True,
    user_id="user-1"
)

print(f"Filled {result['fields_filled']} fields")
```

### 5. Extract Text

```python
from tools.browser_tool import browser_extract_text

# Extract full page text
text_result = await browser_extract_text(
    session_id=session_id,
    user_id="user-1"
)

print(f"Extracted {text_result['length']} characters")
print(f"Content: {text_result['text'][:100]}...")
```

### 6. Close the Session

```python
from tools.browser_tool import browser_close_session

await browser_close_session(
    session_id=session_id,
    user_id="user-1"
)
```

## Using with Agents

### Agent-Initiated Browser Session

```python
from tools.browser_tool import browser_create_session
from core.database import SessionLocal

# Agent creates browser session
# (Automatically checks INTERN+ maturity)
with SessionLocal() as db:
    session = await browser_create_session(
        user_id="user-1",
        agent_id="intern-agent-1",  # Agent must be INTERN+
        headless=True,
        db=db  # Required for governance
    )

    if session["success"]:
        print(f"Agent created session: {session['session_id']}")
```

### Governance Checks

```python
from core.agent_governance_service import AgentGovernanceService
from core.database import SessionLocal

with SessionLocal() as db:
    governance = AgentGovernanceService(db)

    # Check if agent can use browser
    check = governance.can_perform_action(
        agent_id="intern-agent-1",
        action_type="browser_navigate"
    )

    if check["allowed"]:
        print("Agent can use browser automation")
    else:
        print(f"Blocked: {check['reason']}")
```

## API Usage

### Create Session via REST API

```bash
curl -X POST http://localhost:8000/api/browser/session/create \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -d '{
    "headless": true,
    "browser_type": "chromium"
  }'
```

### Navigate via REST API

```bash
curl -X POST http://localhost:8000/api/browser/navigate \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -d '{
    "session_id": "SESSION_ID",
    "url": "https://example.com"
  }'
```

### Get Screenshot via REST API

```bash
curl -X POST http://localhost:8000/api/browser/screenshot \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -d '{
    "session_id": "SESSION_ID",
    "full_page": true
  }'
```

## Common Workflows

### Web Scraping Workflow

```python
# 1. Create session
session = await browser_create_session(user_id="user-1")

# 2. Navigate to page
await browser_navigate(
    session_id=session["session_id"],
    url="https://example.com/data",
    user_id="user-1"
)

# 3. Extract data
data = await browser_extract_text(
    session_id=session["session_id"],
    selector=".data-table",
    user_id="user-1"
)

# 4. Process data
print(data["text"])

# 5. Cleanup
await browser_close_session(
    session_id=session["session_id"],
    user_id="user-1"
)
```

### Form Automation Workflow

```python
# 1. Create session
session = await browser_create_session(user_id="user-1")

# 2. Navigate to form
await browser_navigate(
    session_id=session["session_id"],
    url="https://example.com/form",
    user_id="user-1"
)

# 3. Fill and submit form
await browser_fill_form(
    session_id=session["session_id"],
    selectors={
        "#field1": "value1",
        "#field2": "value2"
    },
    submit=True,
    user_id="user-1"
)

# 4. Take screenshot of result
await browser_screenshot(
    session_id=session["session_id"],
    user_id="user-1"
)

# 5. Cleanup
await browser_close_session(
    session_id=session["session_id"],
    user_id="user-1"
)
```

## Troubleshooting

### Session Creation Fails

```bash
# Check Playwright installation
playwright install chromium

# Check permissions
ls -la ~/.cache/ms-playwright/
```

### Timeout Errors

```python
# Increase wait time in navigation
result = await browser_navigate(
    session_id=session_id,
    url="https://slow-website.com",
    wait_until="networkidle",  # Wait for all network requests
    user_id="user-1"
)
```

### Element Not Found

```python
# Add wait before action
import asyncio
await asyncio.sleep(2)

result = await browser_click(
    session_id=session_id,
    selector="#dynamic-button",
    user_id="user-1"
)
```

## Environment Variables

```bash
# .env file
BROWSER_GOVERNANCE_ENABLED=true    # Enable governance checks
BROWSER_HEADLESS=true              # Run headless by default
EMERGENCY_GOVERNANCE_BYPASS=false  # Emergency bypass
```

## Testing

```bash
# Run browser automation tests
cd backend
pytest tests/test_browser_automation.py -v

# Run with coverage
pytest tests/test_browser_automation.py --cov=tools.browser_tool --cov-report=html
```

## Next Steps

- Read [BROWSER_AUTOMATION.md](./BROWSER_AUTOMATION.md) for full documentation
- Review [GOVERNANCE_INTEGRATION_COMPLETE.md](./GOVERNANCE_INTEGRATION_COMPLETE.md) for governance details
- Check test files for more usage examples

## Summary

✅ Browser automation with **Playwright (CDP)**
✅ **INTERN+** maturity required for agents
✅ Full **audit trail** for all operations
✅ **Multi-browser** support (Chromium, Firefox, WebKit)
✅ **Headless mode** for server deployments

Ready to automate! 🚀
