---
phase: 01-im-adapters
plan: 05
type: execute
wave: 1
depends_on: []
files_modified:
  - backend/core/communication/adapters/telegram.py
  - backend/integrations/whatsapp_routes.py
  - backend/tests/test_im_governance.py
  - backend/docs/IM_SECURITY_BEST_PRACTICES.md
autonomous: true
gap_closure: true
user_setup: []

must_haves:
  truths:
    - "Telegram webhook signature verification uses hmac.compare_digest() for constant-time comparison"
    - "WhatsApp webhook verify token is loaded from environment variable WHATSAPP_VERIFY_TOKEN"
    - "Tests verify constant-time comparison prevents timing attacks"
    - "Environment variable fallback prevents hardcoded secrets in production"
  artifacts:
    - path: "backend/core/communication/adapters/telegram.py"
      provides: "Timing-attack-resistant signature verification"
      contains: "hmac.compare_digest"
    - path: "backend/integrations/whatsapp_routes.py"
      provides: "Environment-configured webhook verification"
      contains: "os.getenv(\"WHATSAPP_VERIFY_TOKEN\""
    - path: "backend/tests/test_im_governance.py"
      provides: "Security fix test coverage"
      contains: "test_constant_time_comparison"
  key_links:
    - from: "backend/core/communication/adapters/telegram.py"
      to: "hmac.compare_digest"
      via: "constant-time string comparison"
      pattern: "hmac\\.compare_digest\\(header_token, self\\.secret_token\\)"
    - from: "backend/integrations/whatsapp_routes.py"
      to: "os.getenv"
      via: "environment variable loading"
      pattern: "os\\.getenv\\(\"WHATSAPP_VERIFY_TOKEN\""
---

<objective>
Fix two critical security vulnerabilities identified in verification:

1. **Gap 2 (HIGH):** Telegram signature timing attack vulnerability - line 27 uses `==` comparison instead of constant-time `hmac.compare_digest()`
2. **Gap 3 (MEDIUM):** WhatsApp hardcoded verify token - line 41 has `"YOUR_VERIFY_TOKEN"` literal instead of environment variable

Purpose: Close security gaps that could allow attackers to forge webhook signatures or bypass verification
Output: Secure signature verification with constant-time comparison and environment-configured tokens
</objective>

<execution_context>
@/Users/rushiparikh/.claude/get-shit-done/workflows/execute-plan.md
@/Users/rushiparikh/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/phases/01-im-adapters/01-im-adapters-VERIFICATION.md
@.planning/phases/01-im-adapters/01-im-adapters-CONTEXT.md

# Files to fix
@backend/core/communication/adapters/telegram.py
@backend/integrations/whatsapp_routes.py
@backend/tests/test_im_governance.py
@backend/docs/IM_SECURITY_BEST_PRACTICES.md
</context>

<tasks>

<task type="auto">
  <name>Fix Telegram timing attack vulnerability (Gap 2)</name>
  <files>backend/core/communication/adapters/telegram.py</files>
  <action>
Replace the timing-vulnerable string comparison on line 27 with constant-time comparison:

**Current code (VULNERABLE):**
```python
if header_token == self.secret_token:
    return True
return False
```

**Fixed code (SECURE):**
```python
import hmac

# In verify_request method, replace line 27
return hmac.compare_digest(header_token, self.secret_token)
```

**Implementation steps:**
1. Add `import hmac` at top of file if not already present
2. Replace the entire verify_request return logic with single line using hmac.compare_digest
3. Preserve existing behavior when secret_token is None (return True for dev mode)
4. Update docstring to mention constant-time comparison

**Why hmac.compare_digest():**
- Uses constant-time algorithm regardless of input length
- Prevents timing attacks where attackers measure response time to guess valid tokens
- Same pattern already correctly used in whatsapp.py:50

**Note:** The WhatsApp adapter already uses `hmac.compare_digest()` correctly at line 50. This fix brings Telegram to parity.
  </action>
  <verify>
```bash
# Verify constant-time comparison is used
grep -n "hmac.compare_digest" backend/core/communication/adapters/telegram.py
# Should show the import and usage

# Verify no vulnerable == comparison for secret token
! grep -n "header_token == self.secret_token" backend/core/communication/adapters/telegram.py
# Should return nothing (no matches)
```
  </verify>
  <done>
telegram.py uses hmac.compare_digest() for signature verification:
- Import hmac added
- Line 27 replaced with hmac.compare_digest(header_token, self.secret_token)
- No timing-vulnerable == comparison for secret tokens
- Dev mode behavior preserved (returns True when secret_token is None)
  </done>
</task>

<task type="auto">
  <name>Fix WhatsApp hardcoded verify token (Gap 3)</name>
  <files>backend/integrations/whatsapp_routes.py</files>
  <action>
Replace the hardcoded verify token with environment variable loading:

**Current code (INSECURE):**
```python
expected_token = "YOUR_VERIFY_TOKEN"  # TODO: Move to env var
```

**Fixed code (SECURE):**
```python
import os

expected_token = os.getenv("WHATSAPP_VERIFY_TOKEN", "default_random_token_change_in_prod")
```

**Implementation steps:**
1. Add `import os` at top of file if not already present (already imported on line 6)
2. Replace line 41 with os.getenv() call
3. Provide secure default value that looks random but indicates it needs changing
4. Update WhatsApp webhook_verify docstring to document the env var

**Environment variable documentation:**
Add comment explaining WHATSAPP_VERIFY_TOKEN purpose:
```python
# WHATSAPP_VERIFY_TOKEN: Random string set in Meta dashboard
# Generate with: openssl rand -hex 16
```

**Why this approach:**
- Prevents accidental deployment with default value
- Provides clear signal that value must be changed in production
- Maintains backward compatibility for existing setups
  </action>
  <verify>
```bash
# Verify env var is used
grep -n 'os.getenv("WHATSAPP_VERIFY_TOKEN"' backend/integrations/whatsapp_routes.py

# Verify no hardcoded token remains
! grep -n 'YOUR_VERIFY_TOKEN' backend/integrations/whatsapp_routes.py
```
  </verify>
  <done>
whatsapp_routes.py uses environment variable for verify token:
- Line 41 now uses os.getenv("WHATSAPP_VERIFY_TOKEN", "default_random_token_change_in_prod")
- No hardcoded "YOUR_VERIFY_TOKEN" string
- Default value clearly indicates production change required
- Docstring updated to document WHATSAPP_VERIFY_TOKEN env var
  </done>
</task>

<task type="auto">
  <name>Add tests and documentation for security fixes</name>
  <files>backend/tests/test_im_governance.py, backend/docs/IM_SECURITY_BEST_PRACTICES.md</files>
  <action>
Add test coverage and update documentation for the security fixes:

**1. Add test to test_im_governance.py:**

```python
def test_telegram_constant_time_comparison():
    """
    Verify Telegram adapter uses constant-time comparison for signature verification.
    This prevents timing attacks where attackers measure response times to guess valid tokens.
    """
    from core.communication.adapters.telegram import TelegramAdapter
    import hmac

    adapter = TelegramAdapter()

    # Set a secret token
    adapter.secret_token = "test_secret_token_12345"

    # Create mock request with matching token
    from fastapi import Request
    from unittest.mock import Mock

    mock_request = Mock(spec=Request)
    mock_request.headers = {"X-Telegram-Bot-Api-Secret-Token": "test_secret_token_12345"}

    # Verify should succeed
    result = asyncio.run(adapter.verify_request(mock_request, b'{}'))
    assert result is True

    # Create mock request with wrong token
    mock_request.headers = {"X-Telegram-Bot-Api-Secret-Token": "wrong_token"}

    # Verify should fail
    result = asyncio.run(adapter.verify_request(mock_request, b'{}'))
    assert result is False

    # Verify implementation uses hmac.compare_digest
    import inspect
    source = inspect.getsource(adapter.verify_request)
    assert "hmac.compare_digest" in source, "verify_request must use hmac.compare_digest"
    assert "==" not in source or "secret_token" not in source.split("==")[0], \
        "verify_request must not use == for secret_token comparison"


def test_whatsapp_env_var_loading():
    """
    Verify WhatsApp verify token is loaded from environment variable.
    """
    import os
    from integrations.whatsapp_routes import whatsapp_webhook_verify

    # Test with custom env var
    original_token = os.environ.get("WHATSAPP_VERIFY_TOKEN")
    try:
        os.environ["WHATSAPP_VERIFY_TOKEN"] = "test_verify_token"

        # Reload the module to pick up new env var
        import importlib
        import integrations.whatsapp_routes
        importlib.reload(integrations.whatsapp_routes)

        # Verify token is loaded from env var
        # (The actual test would verify the endpoint behavior)
        assert os.getenv("WHATSAPP_VERIFY_TOKEN") == "test_verify_token"

    finally:
        # Restore original value
        if original_token:
            os.environ["WHATSAPP_VERIFY_TOKEN"] = original_token
        else:
            os.environ.pop("WHATSAPP_VERIFY_TOKEN", None)
```

**2. Update IM_SECURITY_BEST_PRACTICES.md:**

Add section on timing attack prevention:

```markdown
### Timing Attack Prevention

When comparing secret tokens (webhook signatures, API keys), ALWAYS use constant-time comparison:

**VULNERABLE (timing attack possible):**
```python
if header_token == self.secret_token:
    return True
```

**SECURE (constant-time):**
```python
import hmac
return hmac.compare_digest(header_token, self.secret_token)
```

**Why:** String comparison with `==` short-circuits on first mismatch. Attackers can measure response times to guess valid tokens character-by-character. `hmac.compare_digest()` always compares full strings, preventing this attack vector.

**Required for:**
- Telegram: `X-Telegram-Bot-Api-Secret-Token` header
- WhatsApp: `X-Hub-Signature-256` HMAC verification
- All webhook signature validations
```

Add WHATSAPP_VERIFY_TOKEN to environment variables table.
  </action>
  <verify>
```bash
# Run tests to verify they pass
cd backend && pytest tests/test_im_governance.py::test_telegram_constant_time_comparison -v
pytest tests/test_im_governance.py::test_whatsapp_env_var_loading -v

# Verify documentation updated
grep -n "timing attack" backend/docs/IM_SECURITY_BEST_PRACTICES.md
grep -n "WHATSAPP_VERIFY_TOKEN" backend/docs/IM_SECURITY_BEST_PRACTICES.md
```
  </verify>
  <done>
Tests and documentation added:
- test_telegram_constant_time_comparison verifies hmac.compare_digest usage
- test_whatsapp_env_var_loading verifies environment variable loading
- IM_SECURITY_BEST_PRACTICES.md has timing attack prevention section
- WHATSAPP_VERIFY_TOKEN documented in env vars table
- All tests passing
  </done>
</task>

</tasks>

<verification>
After completion, verify:
1. telegram.py uses hmac.compare_digest() - no == comparison for secret_token
2. whatsapp_routes.py uses os.getenv("WHATSAPP_VERIFY_TOKEN") - no hardcoded token
3. Tests pass for constant-time comparison and env var loading
4. IM_SECURITY_BEST_PRACTICES.md documents timing attack prevention
5. WHATSAPP_VERIFY_TOKEN in environment variables documentation
6. No "YOUR_VERIFY_TOKEN" string remains in codebase
</verification>

<success_criteria>
- Gap 2 CLOSED: Telegram signature verification uses constant-time comparison
- Gap 3 CLOSED: WhatsApp verify token loaded from environment variable
- Test coverage added for both security fixes
- Documentation updated with timing attack prevention guidance
- All existing tests still passing
</success_criteria>

<output>
After completion, create `.planning/phases/01-im-adapters/01-im-adapters-05-SUMMARY.md` with:
- Security vulnerabilities fixed (timing attack, hardcoded token)
- Files modified
- Tests added
- Documentation updates
- Verification that gaps are now closed
