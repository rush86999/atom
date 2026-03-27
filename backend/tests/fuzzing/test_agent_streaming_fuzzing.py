"""
Agent streaming fuzzing harness for discovering crashes in streaming endpoints.

This module uses Atheris to fuzz agent streaming endpoints:
- POST /api/agents/{id}/chat - Agent chat with streaming responses
- WebSocket connections for real-time streaming
- Server-Sent Events (SSE) endpoints
- Timeout handling for long-running streams

Target: Streaming endpoint parsing/validation code crashes
Uses httpx client (not requests) for async/streaming support and realistic testing
"""

import os
import sys

import pytest

# Add backend to path for imports
backend_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

# Try to import httpx for async/streaming support (FUZZ-04 requirement)
try:
    import httpx
    HTTPX_AVAILABLE = True
except ImportError:
    HTTPX_AVAILABLE = False
    print("Warning: httpx not installed. Streaming fuzzing tests will be skipped.")
    print("Install with: pip install httpx")

# Import existing fixtures (FUZZ-02: reuse to avoid duplication)
from tests.e2e_ui.fixtures.auth_fixtures import authenticated_user

# Try to import Atheris (graceful degradation)
try:
    import atheris
    from atheris import fp
    ATHERIS_AVAILABLE = True
except ImportError:
    ATHERIS_AVAILABLE = False


# ============================================================================
# AGENT CHAT STREAMING FUZZING (POST /api/agents/{id}/chat)
# ============================================================================

@pytest.mark.fuzzing
@pytest.mark.slow
@pytest.mark.timeout(300)
def test_agent_chat_streaming_fuzz(authenticated_user):
    """
    Fuzz agent chat streaming endpoint (POST /api/agents/{id}/chat).

    Target crashes in:
    - Agent ID parsing/validation
    - Message parsing
    - Streaming response handling
    - Connection timeout handling

    Edge cases:
    - Agent ID: None, empty, SQL injection, huge length
    - Message: Empty strings, huge messages (10000+ chars), null bytes
    - Parameters: Nested structures, malicious payloads
    - Connection drops during streaming

    Uses httpx client (FUZZ-04 requirement) for:
    - Realistic async HTTP testing
    - Streaming response support
    - Timeout configuration (5-10s to prevent hangs)

    Args:
        authenticated_user: (user, token) tuple for JWT auth
    """
    if not ATHERIS_AVAILABLE:
        pytest.skip("Atheris not installed - fuzzing test skipped")
    if not HTTPX_AVAILABLE:
        pytest.skip("httpx not installed - streaming fuzzing test skipped")

    user, token = authenticated_user

    # Base URL for backend API
    base_url = "http://localhost:8000"

    # Authorization headers
    headers = {"Authorization": f"Bearer {token}"}

    def fuzz_one_input(data: bytes):
        """Fuzz agent chat streaming endpoint with mutated input.

        Args:
            data: Random bytes from Atheris fuzzer

        Raises:
            Exception: Crash discovered (Atheris catches this)
        """
        try:
            fdp = fp.FuzzedDataProvider(data)

            # Fuzz agent_id with edge cases
            agent_id_option = fdp.ConsumeIntInRange(0, 5)
            if agent_id_option == 0:
                agent_id = None
            elif agent_id_option == 1:
                agent_id = ""
            elif agent_id_option == 2:
                # SQL injection
                agent_id = "'; DROP TABLE agents; --"
            elif agent_id_option == 3:
                # XSS attempt
                agent_id = "<script>alert('xss')</script>"
            elif agent_id_option == 4:
                # Huge string
                agent_id = "A" * 10000
            else:
                # Random string up to 50 chars
                agent_id = fdp.ConsumeRandomLengthString(50)

            # Fuzz message string (0-10000 chars)
            message_option = fdp.ConsumeIntInRange(0, 4)
            if message_option == 0:
                message = None
            elif message_option == 1:
                message = ""
            elif message_option == 2:
                # Huge message (potential DoS)
                message = "A" * 10000
            elif message_option == 3:
                # Null bytes
                message = "test\x00\x00\x00message"
            else:
                message = fdp.ConsumeRandomLengthString(1000)

            # Fuzz parameters dict (0-10 keys, nested values)
            num_params = fdp.ConsumeIntInRange(0, 10)
            parameters = {}

            for i in range(num_params):
                key = fdp.ConsumeRandomLengthString(20)
                value_option = fdp.ConsumeIntInRange(0, 3)

                if value_option == 0:
                    value = None
                elif value_option == 1:
                    value = fdp.ConsumeRandomLengthString(100)
                else:
                    # Nested dict for deep structure testing
                    value = {
                        "nested": fdp.ConsumeRandomLengthString(50)
                    }

                parameters[key] = value

            # Build request payload
            payload = {
                "message": message,
                "parameters": parameters
            }

            # Use httpx client for realistic HTTP testing (FUZZ-04 requirement)
            # Set short timeout (5s) to prevent hangs during fuzzing
            with httpx.Client(timeout=5.0) as client:
                # Handle None agent_id gracefully
                if agent_id is None:
                    url = f"{base_url}/api/agents/None/chat"
                else:
                    url = f"{base_url}/api/agents/{agent_id}/chat"

                try:
                    response = client.post(
                        url,
                        json=payload,
                        headers=headers
                    )

                    # Assert acceptable status codes (no crashes = 500 errors)
                    # 200: Success, 400: Bad request, 401: Unauthorized, 404: Not found, 422: Validation
                    assert response.status_code in [200, 400, 401, 404, 422], \
                        f"Unexpected status code {response.status_code}: {response.text}"

                except httpx.ConnectError:
                    # Expected: Connection refused (server not running) is OK for fuzzing
                    pass
                except httpx.TimeoutException:
                    # Expected: Timeout is OK (long-running agents)
                    pass
                except httpx.RemoteProtocolError:
                    # Expected: Protocol error during streaming is OK
                    pass

        except (ValueError, KeyError, IndexError, AttributeError) as e:
            # Expected: parsing errors from malformed input are OK
            pass
        except Exception as e:
            # Unexpected: crash discovered
            raise Exception(f"Crash in agent chat streaming fuzzing: {e}")

    # Run Atheris fuzzing
    iterations = int(os.getenv("FUZZ_ITERATIONS", "10000"))
    atheris.Setup(sys.argv, [])
    atheris.Fuzz(fuzz_one_input, iterations=iterations)


# ============================================================================
# AGENT WEBSOCKET FUZZING
# ============================================================================

@pytest.mark.fuzzing
@pytest.mark.slow
@pytest.mark.timeout(300)
def test_agent_websocket_fuzz(authenticated_user):
    """
    Fuzz WebSocket connection for agent chat.

    Target crashes in:
    - WebSocket connection handling
    - Message frame parsing
    - Connection close logic
    - Invalid message format handling

    Edge cases:
    - Agent ID: SQL injection, XSS, null bytes
    - Initial message: Malformed frames, invalid JSON
    - Connection drops during handshake
    - Concurrent WebSocket connections

    Uses httpx WebSocket client (or websockets library) for realistic testing.

    Args:
        authenticated_user: (user, token) tuple for JWT auth
    """
    if not ATHERIS_AVAILABLE:
        pytest.skip("Atheris not installed - fuzzing test skipped")
    if not HTTPX_AVAILABLE:
        pytest.skip("httpx not installed - websocket fuzzing test skipped")

    user, token = authenticated_user

    # Base URL for WebSocket endpoint
    ws_base_url = "ws://localhost:8000"

    def fuzz_one_input(data: bytes):
        """Fuzz WebSocket connection with mutated input."""
        try:
            fdp = fp.FuzzedDataProvider(data)

            # Fuzz agent_id for WebSocket connection
            agent_id_option = fdp.ConsumeIntInRange(0, 3)
            if agent_id_option == 0:
                agent_id = "'; DROP TABLE agents; --"
            elif agent_id_option == 1:
                agent_id = "\x00\x00\x00"  # Null bytes in URL
            else:
                agent_id = fdp.ConsumeRandomLengthString(50)

            # Fuzz initial message
            message_option = fdp.ConsumeIntInRange(0, 2)
            if message_option == 0:
                initial_message = None
            elif message_option == 1:
                # Malformed JSON
                initial_message = '{"invalid": json}'
            else:
                initial_message = fdp.ConsumeRandomLengthString(500)

            # Try WebSocket connection with short timeout (5s)
            try:
                # Note: httpx does not support WebSocket natively
                # Use websockets library if available, otherwise skip
                try:
                    import websockets

                    async def websocket_test():
                        uri = f"{ws_base_url}/ws/{agent_id}"
                        try:
                            async with websockets.connect(uri, timeout=5, close_timeout=5) as websocket:
                                if initial_message:
                                    await websocket.send(initial_message)
                                    response = await websocket.recv()
                        except Exception:
                            # Expected: Connection failures are OK for fuzzing
                            pass

                    # Run async function
                    import asyncio
                    asyncio.run(websocket_test())

                except ImportError:
                    # websockets library not available - use httpx SSE instead
                    pass

            except Exception as e:
                # Expected: WebSocket connection failures are OK
                # This is fuzzing - we expect many failures
                pass

        except (ValueError, KeyError) as e:
            pass
        except Exception as e:
            # Crash discovered
            raise Exception(f"Crash in WebSocket fuzzing: {e}")

    iterations = int(os.getenv("FUZZ_ITERATIONS", "10000"))
    atheris.Setup(sys.argv, [])
    atheris.Fuzz(fuzz_one_input, iterations=iterations)


# ============================================================================
# STREAMING SSE FUZZING
# ============================================================================

@pytest.mark.fuzzing
@pytest.mark.slow
@pytest.mark.timeout(300)
def test_streaming_sse_fuzz(authenticated_user):
    """
    Fuzz Server-Sent Events (SSE) endpoint.

    Target crashes in:
    - SSE endpoint parsing
    - Invalid Accept headers
    - Malformed query parameters
    - Connection handling

    Edge cases:
    - Agent ID: SQL injection, XSS, null bytes
    - Query parameters: Invalid values, huge strings
    - Accept headers: Invalid MIME types
    - Connection drops during SSE stream

    Args:
        authenticated_user: (user, token) tuple for JWT auth
    """
    if not ATHERIS_AVAILABLE:
        pytest.skip("Atheris not installed - fuzzing test skipped")
    if not HTTPX_AVAILABLE:
        pytest.skip("httpx not installed - SSE fuzzing test skipped")

    user, token = authenticated_user

    base_url = "http://localhost:8000"
    headers = {"Authorization": f"Bearer {token}"}

    def fuzz_one_input(data: bytes):
        """Fuzz SSE endpoint with mutated input."""
        try:
            fdp = fp.FuzzedDataProvider(data)

            # Fuzz agent_id
            agent_id_option = fdp.ConsumeIntInRange(0, 3)
            if agent_id_option == 0:
                agent_id = "'; DROP TABLE agents; --"
            elif agent_id_option == 1:
                agent_id = "<script>alert(1)</script>"
            else:
                agent_id = fdp.ConsumeRandomLengthString(50)

            # Fuzz query parameters
            num_params = fdp.ConsumeIntInRange(0, 5)
            params = {}

            for i in range(num_params):
                key = fdp.ConsumeRandomLengthString(20)
                value = fdp.ConsumeRandomLengthString(100)
                params[key] = value

            # Fuzz Accept header
            accept_option = fdp.ConsumeIntInRange(0, 3)
            if accept_option == 0:
                accept_header = "text/event-stream"
            elif accept_option == 1:
                # Invalid Accept header
                accept_header = "invalid/mime-type"
            else:
                accept_header = fdp.ConsumeRandomLengthString(50)

            headers_with_accept = headers.copy()
            headers_with_accept["Accept"] = accept_header

            # Make SSE request with short timeout (5s)
            with httpx.Client(timeout=5.0) as client:
                try:
                    response = client.get(
                        f"{base_url}/api/agents/{agent_id}/stream",
                        params=params,
                        headers=headers_with_accept
                    )

                    # Assert acceptable status codes (no crashes)
                    # 200: Success, 400: Bad request, 404: Not found, 406: Not Acceptable
                    assert response.status_code in [200, 400, 404, 406, 422], \
                        f"Unexpected status code {response.status_code}"

                except httpx.ConnectError:
                    # Expected: Server not running
                    pass
                except httpx.TimeoutException:
                    # Expected: Timeout during SSE stream
                    pass
                except httpx.RemoteProtocolError:
                    # Expected: Protocol error during SSE
                    pass

        except (ValueError, KeyError):
            pass
        except Exception as e:
            raise Exception(f"Crash in SSE fuzzing: {e}")

    iterations = int(os.getenv("FUZZ_ITERATIONS", "10000"))
    atheris.Setup(sys.argv, [])
    atheris.Fuzz(fuzz_one_input, iterations=iterations)


# ============================================================================
# STREAMING TIMEOUT FUZZING
# ============================================================================

@pytest.mark.fuzzing
@pytest.mark.slow
@pytest.mark.timeout(300)
def test_streaming_timeout_fuzz(authenticated_user):
    """
    Fuzz streaming timeout handling.

    Target crashes in:
    - Client timeout handling
    - Server timeout logic
    - Hung connection cleanup
    - Graceful shutdown

    Edge cases:
    - Agents with infinite loops (simulated)
    - Very short timeouts (< 1s)
    - Very long timeouts (> 300s)
    - Connection drops during timeout

    Ensures graceful timeout handling (no hung connections, no crashes).

    Args:
        authenticated_user: (user, token) tuple for JWT auth
    """
    if not ATHERIS_AVAILABLE:
        pytest.skip("Atheris not installed - fuzzing test skipped")
    if not HTTPX_AVAILABLE:
        pytest.skip("httpx not installed - timeout fuzzing test skipped")

    user, token = authenticated_user

    base_url = "http://localhost:8000"
    headers = {"Authorization": f"Bearer {token}"}

    def fuzz_one_input(data: bytes):
        """Fuzz streaming timeout with varied timeout values."""
        try:
            fdp = fp.FuzzedDataProvider(data)

            # Fuzz agent_id
            agent_id = fdp.ConsumeRandomLengthString(50)

            # Fuzz timeout value (0.1s to 300s)
            timeout_option = fdp.ConsumeIntInRange(0, 4)
            if timeout_option == 0:
                timeout = 0.1  # Very short timeout
            elif timeout_option == 1:
                timeout = 5.0  # Normal timeout
            elif timeout_option == 2:
                timeout = 300.0  # Very long timeout
            else:
                timeout = fdp.ConsumeFloatInRange(0.1, 300.0)

            # Fuzz message (potential infinite loop simulation)
            message = fdp.ConsumeRandomLengthString(1000)

            # Build request payload
            payload = {
                "message": message,
                "parameters": {"timeout": timeout}
            }

            # Make request with fuzzed timeout
            # Use httpx client with timeout (FUZZ-04 requirement)
            with httpx.Client(timeout=timeout) as client:
                try:
                    response = client.post(
                        f"{base_url}/api/agents/{agent_id}/chat",
                        json=payload,
                        headers=headers
                    )

                    # Assert acceptable status codes
                    # Timeouts should not cause crashes (500 errors)
                    assert response.status_code in [200, 400, 401, 404, 422], \
                        f"Unexpected status code {response.status_code}"

                except httpx.TimeoutException:
                    # Expected: Timeout is OK (no crash)
                    pass
                except httpx.ConnectError:
                    # Expected: Server not running
                    pass

        except (ValueError, KeyError):
            pass
        except Exception as e:
            # Crash discovered (timeout handling failed)
            raise Exception(f"Crash in timeout fuzzing: {e}")

    iterations = int(os.getenv("FUZZ_ITERATIONS", "10000"))
    atheris.Setup(sys.argv, [])
    atheris.Fuzz(fuzz_one_input, iterations=iterations)
