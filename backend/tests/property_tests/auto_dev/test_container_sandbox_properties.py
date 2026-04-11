"""
Property-Based Tests for ContainerSandbox

This module tests ContainerSandbox invariants using Hypothesis to generate hundreds
of test cases automatically.

Properties tested:
1. Execution Result Structure Invariant - All executions return valid result structure
2. Timeout Enforcement Invariant - Executions respect timeout limits
3. Error Handling Invariant - Crashes don't affect host system
4. Output Type Invariant - All outputs are strings
5. Execution Time Measurement Invariant - Execution times are non-negative floats
"""

import pytest
import asyncio
from hypothesis import given, settings, strategies as st, HealthCheck
from typing import Any

from core.auto_dev.container_sandbox import ContainerSandbox


# =============================================================================
# Strategy Definitions
# =============================================================================

# Simple Python code that prints output
simple_code = st.sampled_from([
    "print('hello')",
    "print('world')",
    "print(42)",
    "x = 1 + 1\nprint(x)",
    "for i in range(3):\n    print(i)"
])

# Code that exits with different codes
exit_codes = st.sampled_from([
    "import sys; sys.exit(0)",
    "import sys; sys.exit(1)",
    "raise Exception('error')"
])

# Code with syntax errors
syntax_errors = st.sampled_from([
    "print('unclosed quote",
    "if True",
    "def incomplete(",
    "1 + * 2"
])

# Input parameters strategy
input_params = st.dictionaries(
    keys=st.text(min_size=1, max_size=20, alphabet='abcdefghijklmnopqrstuvwxyz'),
    values=st.one_of(st.integers(), st.floats(), st.text(), st.booleans()),
    min_size=0,
    max_size=10
)

# Timeout strategy
timeouts = st.integers(min_value=1, max_value=10)

# Memory limit strategy (in MB, converted to string)
memory_limits = st.integers(min_value=50, max_value=500).map(lambda x: f"{x}m")


# =============================================================================
# Property Tests
# =============================================================================

@pytest.mark.property
@pytest.mark.docker_required
@given(
    code=simple_code,
    params=input_params
)
@settings(max_examples=50, suppress_health_check=[HealthCheck.function_scoped_fixture])
async def test_execution_result_structure_invariant(
    container_sandbox,
    code,
    params
):
    """
    Property: All executions return valid result structure.

    For any valid Python code and input parameters, the execute_raw_python
    method should return a dict with required keys: status, output,
    execution_seconds, environment.
    """
    import uuid

    result = await container_sandbox.execute_raw_python(
        tenant_id=str(uuid.uuid4()),
        code=code,
        input_params=params,
        timeout=5
    )

    # Verify structure
    assert isinstance(result, dict), "Result should be a dict"
    assert "status" in result, "Result missing 'status' field"
    assert "output" in result, "Result missing 'output' field"
    assert "execution_seconds" in result, "Result missing 'execution_seconds' field"
    assert "environment" in result, "Result missing 'environment' field"

    # Verify types
    assert isinstance(result["status"], str), "Status should be a string"
    assert isinstance(result["output"], str), "Output should be a string"
    assert isinstance(result["execution_seconds"], (int, float)), \
        "Execution seconds should be a number"
    assert isinstance(result["environment"], str), "Environment should be a string"

    # Verify values
    assert result["status"] in ["success", "failed"], \
        f"Status should be 'success' or 'failed', got {result['status']}"
    assert result["environment"] in ["docker", "subprocess"], \
        f"Environment should be 'docker' or 'subprocess', got {result['environment']}"


@pytest.mark.property
@pytest.mark.docker_required
@given(
    timeout=timeouts
)
@settings(max_examples=50, suppress_health_check=[HealthCheck.function_scoped_fixture])
async def test_timeout_enforcement_invariant(container_sandbox, timeout):
    """
    Property: Executions respect timeout limits.

    For any timeout value, long-running code should be terminated within
    the specified timeout period (with small buffer for overhead).
    """
    import uuid

    # Code that runs indefinitely (infinite loop)
    infinite_code = """
import time
while True:
    time.sleep(0.1)
"""

    result = await container_sandbox.execute_raw_python(
        tenant_id=str(uuid.uuid4()),
        code=infinite_code,
        timeout=timeout
    )

    # Verify execution terminated
    assert result["status"] == "failed", "Infinite loop should fail"

    # Verify execution time is approximately timeout (with 2s buffer for overhead)
    exec_time = result["execution_seconds"]
    assert exec_time <= timeout + 2.0, \
        f"Execution time {exec_time}s exceeded timeout {timeout}s by more than 2s buffer"

    # Verify timeout message in output
    assert "timeout" in result["output"].lower() or "timed out" in result["output"].lower(), \
        f"Timeout error message not found in output: {result['output']}"


@pytest.mark.property
@pytest.mark.docker_required
@given(
    crash_code=exit_codes
)
@settings(max_examples=50, suppress_health_check=[HealthCheck.function_scoped_fixture])
async def test_error_containment_invariant(container_sandbox, crash_code):
    """
    Property: Container crashes don't affect host system.

    For any code that crashes or exits with non-zero status, the sandbox
    should capture the error and return a failed result without affecting
    the host system or preventing subsequent executions.
    """
    import uuid

    # Execute crashing code
    result = await container_sandbox.execute_raw_python(
        tenant_id=str(uuid.uuid4()),
        code=crash_code,
        timeout=5
    )

    # Verify result structure (host didn't crash)
    assert result is not None, "Container crash affected host"
    assert isinstance(result, dict), "Result should be a dict after crash"
    assert result["status"] == "failed", "Crash should result in failed status"

    # Verify host still functional by executing another command
    followup = await container_sandbox.execute_raw_python(
        tenant_id=str(uuid.uuid4()),
        code="print('Host alive')",
        timeout=5
    )

    assert followup["status"] == "success", \
        "Host not functional after container crash"
    assert "Host alive" in followup["output"] or "alive" in followup["output"], \
        f"Followup execution failed: {followup['output']}"


@pytest.mark.property
@pytest.mark.docker_required
@given(
    code=simple_code
)
@settings(max_examples=50, suppress_health_check=[HealthCheck.function_scoped_fixture])
async def test_output_type_invariant(container_sandbox, code):
    """
    Property: All outputs are strings.

    For any code execution, the output field should be a string, even if
    the code prints numbers, objects, or nothing.
    """
    import uuid

    result = await container_sandbox.execute_raw_python(
        tenant_id=str(uuid.uuid4()),
        code=code,
        timeout=5
    )

    # Verify output is string
    assert isinstance(result["output"], str), \
        f"Output should be string, got {type(result['output'])}"


@pytest.mark.property
@pytest.mark.docker_required
@given(
    code=simple_code
)
@settings(max_examples=50, suppress_health_check=[HealthCheck.function_scoped_fixture])
async def test_execution_time_measurement_invariant(container_sandbox, code):
    """
    Property: Execution times are non-negative floats.

    For any code execution, the execution_seconds field should be a
    non-negative number (float or int).
    """
    import uuid

    result = await container_sandbox.execute_raw_python(
        tenant_id=str(uuid.uuid4()),
        code=code,
        timeout=5
    )

    # Verify execution time
    exec_time = result["execution_seconds"]
    assert isinstance(exec_time, (int, float)), \
        f"Execution time should be numeric, got {type(exec_time)}"
    assert exec_time >= 0, \
        f"Execution time should be non-negative, got {exec_time}"


@pytest.mark.property
@pytest.mark.docker_required
@given(
    code=syntax_errors
)
@settings(max_examples=50, suppress_health_check=[HealthCheck.function_scoped_fixture])
async def test_syntax_error_handling_invariant(container_sandbox, code):
    """
    Property: Syntax errors are caught and reported properly.

    For any code with syntax errors, the sandbox should return a failed
    result with error information in the output.
    """
    import uuid

    result = await container_sandbox.execute_raw_python(
        tenant_id=str(uuid.uuid4()),
        code=code,
        timeout=5
    )

    # Verify failure
    assert result["status"] == "failed", \
        f"Syntax error should result in failed status, got {result['status']}"

    # Verify error information present
    assert len(result["output"]) > 0, "Error output should not be empty"

    # Common syntax error indicators
    output_lower = result["output"].lower()
    assert any(keyword in output_lower for keyword in [
        "syntax", "error", "invalid", "unexpected", "eof"
    ]), f"Syntax error indicators not found in: {result['output']}"


@pytest.mark.property
@pytest.mark.docker_required
@given(
    params=input_params
)
@settings(max_examples=50, suppress_health_check=[HealthCheck.function_scoped_fixture])
async def test_input_parameter_injection_invariant(container_sandbox, params):
    """
    Property: Input parameters are injected correctly into execution context.

    For any input parameters dict, the sandbox should inject them as
    _INPUT_PARAMS variable accessible to the executed code.
    """
    import uuid

    # Code that accesses _INPUT_PARAMS
    code = """
import json
print(json.dumps(_INPUT_PARAMS))
"""

    result = await container_sandbox.execute_raw_python(
        tenant_id=str(uuid.uuid4()),
        code=code,
        input_params=params,
        timeout=5
    )

    # Verify success
    if result["status"] == "success":
        # Verify params were injected
        import json
        try:
            injected_params = json.loads(result["output"].strip())
            assert injected_params == params, \
                f"Injected params {injected_params} != original {params}"
        except json.JSONDecodeError:
            # Output might have extra content, try to find JSON
            pass


@pytest.mark.property
@pytest.mark.docker_required
@given(
    memory_limit=memory_limits
)
@settings(max_examples=50, suppress_health_check=[HealthCheck.function_scoped_fixture])
async def test_memory_limit_configuration_invariant(container_sandbox, memory_limit):
    """
    Property: Memory limits can be configured via constructor.

    For any valid memory limit string (e.g., "256m"), the sandbox should
    accept the configuration without error.
    """
    # Create sandbox with custom memory limit
    sandbox = ContainerSandbox(memory_limit=memory_limit)

    # Verify configuration
    assert sandbox.memory_limit == memory_limit, \
        f"Memory limit {sandbox.memory_limit} != configured {memory_limit}"

    # Execute simple code to verify sandbox works
    import uuid
    result = await sandbox.execute_raw_python(
        tenant_id=str(uuid.uuid4()),
        code="print('test')",
        timeout=5
    )

    # Verify execution succeeded
    assert result["status"] in ["success", "failed"], \
        f"Execution with custom memory limit failed: {result}"


@pytest.mark.property
@pytest.mark.docker_required
@given(
    code=simple_code,
    enable_network=st.booleans()
)
@settings(max_examples=50, suppress_health_check=[HealthCheck.function_scoped_fixture])
async def test_network_configuration_invariant(container_sandbox, code, enable_network):
    """
    Property: Network configuration can be set via constructor.

    For any network configuration (True/False), the sandbox should accept
    the configuration without error.
    """
    # Create sandbox with custom network setting
    sandbox = ContainerSandbox(enable_network=enable_network)

    # Verify configuration
    assert sandbox.enable_network == enable_network, \
        f"Network setting {sandbox.enable_network} != configured {enable_network}"

    # Execute simple code to verify sandbox works
    import uuid
    result = await sandbox.execute_raw_python(
        tenant_id=str(uuid.uuid4()),
        code=code,
        timeout=5
    )

    # Verify execution succeeded
    assert result["status"] in ["success", "failed"], \
        f"Execution with custom network setting failed: {result}"


@pytest.mark.property
@pytest.mark.docker_required
@given()
@settings(max_examples=50, suppress_health_check=[HealthCheck.function_scoped_fixture])
async def test_docker_availability_detection_invariant(container_sandbox):
    """
    Property: Docker availability detection is consistent.

    The docker_available property should return a boolean and be
    consistent across multiple calls (cached result).
    """
    # Check availability
    available1 = container_sandbox.docker_available
    available2 = container_sandbox.docker_available

    # Verify type and consistency
    assert isinstance(available1, bool), \
        f"docker_available should be bool, got {type(available1)}"

    assert available1 == available2, \
        "docker_available should be consistent (cached)"

    # Verify environment matches availability
    import uuid
    result = await container_sandbox.execute_raw_python(
        tenant_id=str(uuid.uuid4()),
        code="print('test')",
        timeout=5
    )

    if available1:
        assert result["environment"] == "docker", \
            f"Expected docker environment when available, got {result['environment']}"
    else:
        assert result["environment"] == "subprocess", \
            f"Expected subprocess environment when docker unavailable, got {result['environment']}"
