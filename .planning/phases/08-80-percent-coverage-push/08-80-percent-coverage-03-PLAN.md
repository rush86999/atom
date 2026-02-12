---
phase: 08-80-percent-coverage-push
plan: 03
type: execute
wave: 1
depends_on: []
files_modified:
  - backend/tests/unit/test_byok_handler.py
  - backend/tests/unit/test_byok_endpoints.py
autonomous: true

must_haves:
  truths:
    - "Multi-provider LLM routing is tested across all providers"
    - "Token streaming functionality is verified"
    - "Provider failover and error recovery are covered"
    - "API key rotation and security validation are tested"
  artifacts:
    - path: "backend/tests/unit/test_byok_handler.py"
      provides: "Tests for multi-provider LLM handler"
      min_lines: 350
    - path: "backend/tests/unit/test_byok_endpoints.py"
      provides: "Tests for BYOK API endpoints"
      min_lines: 250
  key_links:
    - from: "backend/tests/unit/test_byok_handler.py"
      to: "backend/core/llm/byok_handler.py"
      via: "import BYOKHandler and provider classes"
      pattern: "from core.llm.byok_handler import"
    - from: "backend/tests/unit/test_byok_endpoints.py"
      to: "backend/core/byok_endpoints.py"
      via: "import FastAPI endpoint routes"
      pattern: "from core.byok_endpoints import"
---

<objective>
Create comprehensive tests for the LLM Bring Your Own Key (BYOK) handler and endpoints, covering multi-provider routing (OpenAI, Anthropic, DeepSeek, Gemini), token streaming, error handling, provider failover, and API key rotation.

Purpose: Ensure reliable LLM integration across multiple providers with proper failover, streaming, and key management for the agent chat/streaming system.
Output: Test suites for byok_handler.py and byok_endpoints.py achieving 80%+ coverage
</objective>

<execution_context>
@/Users/rushiparikh/.claude/get-shit-done/workflows/execute-plan.md
@/Users/rushiparikh/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/PROJECT.md
@.planning/ROADMAP.md
@backend/tests/coverage_reports/COVERAGE_PRIORITY_ANALYSIS.md
@backend/tests/conftest.py
@backend/core/llm/byok_handler.py
@backend/core/byok_endpoints.py
@backend/tests/test_browser_automation.py
@backend/core/models.py
</context>

<tasks>

<task type="auto">
  <name>Create BYOKHandler initialization and provider registration tests</name>
  <files>backend/tests/unit/test_byok_handler.py</files>
  <action>
    Create backend/tests/unit/test_byok_handler.py with initialization tests:

    Test BYOKHandler class setup:
    1. test_byok_handler_init() - verify handler initialization
    2. test_register_provider() - add LLM provider configuration
    3. test_get_provider() - retrieve registered provider
    4. test_get_default_provider() - default provider selection
    5. test_list_providers() - enumerate available providers
    6. test_provider_config_validation() - invalid config rejected

    Create provider fixtures:
    ```python
    @pytest.fixture
    def mock_openai_config():
        return {
            "provider": "openai",
            "api_key": "sk-test",
            "model": "gpt-4",
            "base_url": "https://api.openai.com/v1"
        }
    ```

    Test provider registration:
    - Valid providers added successfully
    - Duplicate provider names handled (replace or error)
    - Invalid provider names rejected
    - Missing required fields caught

    Verify provider storage in internal registry.
  </action>
  <verify>pytest backend/tests/unit/test_byok_handler.py::TestBYOKHandlerInit -v</verify>
  <done>All initialization tests pass (6+ tests)</done>
</task>

<task type="auto">
  <name>Create multi-provider routing tests</name>
  <files>backend/tests/unit/test_byok_handler.py</files>
  <action>
    Add provider routing tests to test_byok_handler.py:

    Test LLM provider selection and routing:
    1. test_route_to_openai() - OpenAI provider selected
    2. test_route_to_anthropic() - Anthropic provider selected
    3. test_route_to_deepseek() - DeepSeek provider selected
    4. test_route_to_gemini() - Google Gemini provider selected
    5. test_auto_provider_selection() - automatic provider based on availability
    6. test_provider_not_found_error() - missing provider raises error

    Mock HTTP client for each provider:
    ```python
    @pytest.fixture
    def mock_http_client():
        with patch('httpx.AsyncClient') as mock:
            yield mock
    ```

    Test routing logic:
    - Provider selection by name
    - Fallback to default when provider unspecified
    - Provider availability checking
    - Error handling for unknown providers

    Verify correct HTTP client configuration per provider:
    - Base URLs (api.openai.com, api.anthropic.com, etc.)
    - Headers (Authorization, x-api-key, etc.)
    - Timeout settings
  </action>
  <verify>pytest backend/tests/unit/test_byok_handler.py::TestProviderRouting -v</verify>
  <done>All routing tests pass (6+ tests)</done>
</task>

<task type="auto">
  <name>Create token streaming tests</name>
  <files>backend/tests/unit/test_byok_handler.py</files>
  <action>
    Add streaming tests to test_byok_handler.py:

    Test streaming LLM responses:
    1. test_stream_response_openai() - OpenAI streaming format
    2. test_stream_response_anthropic() - Anthropic streaming format
    3. test_stream_response_deepseek() - DeepSeek streaming format
    4. test_stream_response_gemini() - Gemini streaming format
    5. test_stream_yields_tokens() - async generator yields tokens
    6. test_stream_handles_errors() - errors during streaming

    Mock streaming response:
    ```python
    @pytest.mark.asyncio
    async def test_stream_yields_tokens():
        handler = BYOKHandler()
        mock_response = AsyncMock()
        mock_response.aiter_bytes.return_value = [b"data: ", b"Hello", b"data: [DONE]"]

        tokens = []
        async for token in handler._stream_response(mock_response):
            tokens.append(token)

        assert "Hello" in tokens
    ```

    Test SSE (Server-Sent Events) parsing:
    - "data: " prefix handling
    - "[DONE]" message detection
    - JSON chunk parsing
    - Delta content extraction

    Verify async generator pattern:
    - Tokens yielded incrementally
    - Stream properly closed
    - Resources cleaned up
  </action>
  <verify>pytest backend/tests/unit/test_byok_handler.py::TestTokenStreaming -v</verify>
  <done>All streaming tests pass (6+ tests)</done>
</task>

<task type="auto">
  <name>Create provider failover and error handling tests</name>
  <files>backend/tests/unit/test_byok_handler.py</files>
  <action>
    Add failover tests to test_byok_handler.py:

    Test provider failover scenarios:
    1. test_failover_on_provider_error() - switch to backup provider
    2. test_failover_exhaustion() - all providers fail
    3. test_retry_on_transient_error() - retry 429/503 errors
    4. test_no_retry_on_auth_error() - 401 errors fail immediately
    5. test_failover_preserves_context() - conversation context maintained
    6. test_failover_latency_tracking() - measure failover performance

    Mock provider responses:
    - Primary provider raises httpx.HTTPStatusError
    - Backup provider returns successful response
    - Transient errors (429, 503) trigger retries
    - Auth errors (401) trigger failover without retry

    Test failover configuration:
    ```python
    failover_config = {
        "primary": "openai",
        "fallback": ["anthropic", "gemini"],
        "max_retries": 3
    }
    ```

    Verify:
    - Failover order respected
    - Retry count enforced
    - Errors logged appropriately
    - Context passed to fallback provider
  </action>
  <verify>pytest backend/tests/unit/test_byok_handler.py::TestFailover -v</verify>
  <done>All failover tests pass (6+ tests)</done>
</task>

<task type="auto">
  <name>Create API key rotation and security tests</name>
  <files>backend/tests/unit/test_byok_handler.py</files>
  <action>
    Add security tests to test_byok_handler.py:

    Test API key management:
    1. test_rotate_api_key() - switch to new API key
    2. test_key_quota_exceeded() - handle quota limits
    3. test_key_validation() - validate key format
    4. test_multiple_keys_per_provider() - key pool management
    5. test_key_rate_limiting() - respect rate limits
    6. test_key_revocation() - handle revoked keys

    Test key rotation:
    - Old key marked inactive
    - New key activated
    - In-flight requests complete with old key
    - New requests use new key

    Test quota handling:
    - 429 Too Many Requests detected
    - Switch to different key for same provider
    - Quota tracking per key
    - Quota reset after time window

    Verify key storage:
    - Keys encrypted at rest
    - Keys never logged
    - Key rotation audit trail
  </action>
  <verify>pytest backend/tests/unit/test_byok_handler.py::TestKeyManagement -v</verify>
  <done>All key management tests pass (6+ tests)</done>
</task>

<task type="auto">
  <name>Create BYOK API endpoint tests</name>
  <files>backend/tests/unit/test_byok_endpoints.py</files>
  <action>
    Create backend/tests/unit/test_byok_endpoints.py:

    Test FastAPI endpoints for BYOK management:
    1. test_register_provider_endpoint() - POST /providers/register
    2. test_list_providers_endpoint() - GET /providers
    3. test_get_provider_endpoint() - GET /providers/{provider_id}
    4. test_delete_provider_endpoint() - DELETE /providers/{provider_id}
    5. test_rotate_key_endpoint() - POST /providers/{provider_id}/rotate-key
    6. test_test_provider_endpoint() - POST /providers/{provider_id}/test

    Use FastAPI TestClient:
    ```python
    from fastapi.testclient import TestClient

    @pytest.fixture
    def client():
        from core.byok_endpoints import app
        return TestClient(app)
    ```

    Test request/response validation:
    - Valid requests return 200
    - Invalid schemas return 422
    - Missing providers return 404
    - Auth errors return 401

    Mock handler methods:
    - BYOKHandler.register_provider()
    - BYOKHandler.list_providers()
    - BYOKHandler.delete_provider()

    Verify endpoints:
    - Accept JSON payloads
    - Return JSON responses
    - Include proper error messages
  </action>
  <verify>pytest backend/tests/unit/test_byok_endpoints.py -v</verify>
  <done>All endpoint tests pass (8+ tests)</done>
</task>

<task type="auto">
  <name>Create chat completion and prompt processing tests</name>
  <files>backend/tests/unit/test_byok_handler.py</files>
  <action>
    Add chat/prompt tests to test_byok_handler.py:

    Test LLM chat completion:
    1. test_chat_completion_openai() - OpenAI chat format
    2. test_chat_completion_anthropic() - Anthropic messages format
    3. test_system_prompt_handling() - system prompt injection
    4. test_conversation_history() - multi-turn conversation
    5. test_function_calling() - tool/function call support
    6. test_temperature_sampling() - temperature and top_p parameters

    Mock chat API responses:
    ```python
    mock_response = {
        "id": "chatcmpl-123",
        "choices": [{
            "message": {
                "role": "assistant",
                "content": "Hello!"
            }
        }],
        "usage": {"prompt_tokens": 10, "completion_tokens": 5}
    }
    ```

    Test prompt processing:
    - System prompt prepended
    - Conversation history formatted
    - Token count estimation
    - Max tokens enforcement

    Verify response parsing:
    - Content extracted correctly
    - Usage stats captured
    - Finish reason handled
  </action>
  <verify>pytest backend/tests/unit/test_byok_handler.py::TestChatCompletion -v</verify>
  <done>All chat completion tests pass (6+ tests)</done>
</task>

</tasks>

<verification>
1. Run pytest backend/tests/unit/test_byok_handler.py -v to verify handler tests pass
2. Run pytest backend/tests/unit/test_byok_endpoints.py -v to verify endpoint tests pass
3. Run pytest --cov=backend/core/llm/byok_handler backend/tests/unit/test_byok_handler.py to verify coverage
4. Run pytest --cov=backend/core/byok_endpoints backend/tests/unit/test_byok_endpoints.py to verify coverage
5. Check coverage.json shows 80%+ coverage for both files
6. Verify all HTTP calls are mocked (no actual API calls made)
</verification>

<success_criteria>
- test_byok_handler.py created with 35+ tests
- test_byok_endpoints.py created with 8+ tests
- 80%+ coverage on byok_handler.py
- 80%+ coverage on byok_endpoints.py
- All providers tested (OpenAI, Anthropic, DeepSeek, Gemini)
- Streaming, failover, key rotation all covered
</success_criteria>

<output>
After completion, create `.planning/phases/08-80-percent-coverage-push/08-80-percent-coverage-03-SUMMARY.md`
</output>
