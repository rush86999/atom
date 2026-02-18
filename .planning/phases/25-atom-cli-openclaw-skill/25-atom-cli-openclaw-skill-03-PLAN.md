---
phase: 25-atom-cli-openclaw-skill
plan: 03
type: execute
wave: 2
depends_on: [01, 02]
files_modified:
  - backend/tests/test_atom_cli_skills.py
  - backend/tools/atom_cli_skill_wrapper.py
  - backend/core/skill_adapter.py
autonomous: true

must_haves:
  truths:
    - "All 6 CLI skills import successfully via /api/skills/import endpoint"
    - "SkillParser parses all SKILL.md files without errors"
    - "Skills execute commands via subprocess with correct maturity gates"
    - "AUTONOMOUS skills blocked for STUDENT/INTERN/SUPERVISED agents"
    - "STUDENT skills (status, config) accessible to all maturity levels"
  artifacts:
    - path: "backend/tests/test_atom_cli_skills.py"
      provides: "Test suite for CLI skill import and execution"
      contains: "test_import_all_cli_skills"
      contains: "test_execute_cli_command"
      contains: "test_maturity_gates"
  key_links:
    - from: "backend/tests/test_atom_cli_skills.py"
      to: "backend/core/skill_parser.py"
      via: "SkillParser.parse_skill_file"
      pattern: "parse_skill_file"
    - from: "backend/tests/test_atom_cli_skills.py"
      to: "backend/tools/atom_cli_skill_wrapper.py"
      via: "execute_atom_cli_command"
      pattern: "execute_atom_cli_command"
    - from: "backend/tests/test_atom_cli_skills.py"
      to: "backend/core/skill_registry_service.py"
      via: "import_skill endpoint"
      pattern: "import_skill"
---

<objective>
Create comprehensive test suite for Atom CLI skills import and execution.

Purpose: Validate that all 6 CLI skills import correctly, execute commands via subprocess, and enforce maturity gates as specified in governance configuration.

Output: test_atom_cli_skills.py with 15+ tests covering import, parsing, execution, and governance.
</objective>

<execution_context>
@/Users/rushiparikh/.claude/get-shit-done/workflows/execute-plan.md
@/Users/rushiparikh/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/phases/25-atom-cli-openclaw-skill/25-RESEARCH.md
@.planning/phases/25-atom-cli-openclaw-skill/25-atom-cli-openclaw-skill-01-SUMMARY.md
@.planning/phases/25-atom-cli-openclaw-skill/25-atom-cli-openclaw-skill-02-SUMMARY.md
@backend/tests/test_skill_parser.py (reference for test patterns)
@backend/core/skill_parser.py
@backend/tools/atom_cli_skill_wrapper.py
@backend/core/skill_adapter.py
@backend/core/skill_registry_service.py
@backend/core/agent_governance_service.py
</context>

<tasks>

<task type="auto">
  <name>Create test file with skill import and parsing tests</name>
  <files>backend/tests/test_atom_cli_skills.py</files>
  <action>
    Create backend/tests/test_atom_cli_skills.py with:

    1. Imports:
       - pytest, tempfile, Path
       - SkillParser from core.skill_parser
       - execute_atom_cli_command from tools.atom_cli_skill_wrapper
       - AgentRegistry factory from tests.factories

    2. Test class: TestAtomCliSkillParsing
       - test_parse_atom_daemon_skill(): Verify atom-daemon.md parses with AUTONOMOUS maturity
       - test_parse_atom_status_skill(): Verify atom-status.md parses with STUDENT maturity
       - test_parse_atom_start_skill(): Verify atom-start.md parses with AUTONOMOUS maturity
       - test_parse_atom_stop_skill(): Verify atom-stop.md parses with AUTONOMOUS maturity
       - test_parse_atom_execute_skill(): Verify atom-execute.md parses with AUTONOMOUS maturity
       - test_parse_atom_config_skill(): Verify atom-config.md parses with STUDENT maturity

    3. Test class: TestAtomCliSkillMetadata
       - test_all_skills_have_required_fields(): name, description, version, author, tags
       - test_governance_maturity_requirements(): Verify governance.maturity_requirement set
       - test_skill_names_match_cli_commands(): daemon, status, start, stop, execute, config
       - test_autonomous_skills_count(): 4 skills require AUTONOMOUS (daemon, start, stop, execute)
       - test_student_skills_count(): 2 skills allow STUDENT (status, config)

    4. Use Path(__file__).parent.parent / "skills/atom-cli" for skill directory
    5. Use SkillParser().parse_skill_file() for parsing
    6. Follow pattern from test_skill_parser.py

    8+ tests total.
  </action>
  <verify>
    Test file created with 8+ parsing tests
    All 6 CLI skills have test cases
    Tests verify metadata fields and maturity requirements
    Tests import SkillParser and use parse_skill_file
  </verify>
  <done>
    test_atom_cli_skills.py created with 8 parsing tests, all skills covered, metadata validation
  </done>
</task>

<task type="auto">
  <name>Add subprocess wrapper execution tests</name>
  <files>backend/tests/test_atom_cli_skills.py</files>
  <action>
    Add execution tests to test_atom_cli_skills.py:

    1. Test class: TestAtomCliWrapperExecution (mock subprocess to avoid real CLI calls):
       - test_execute_status_command(): Mock subprocess.run for status, verify return format
       - test_execute_command_timeout(): Mock TimeoutExpired, verify timeout handling
       - test_execute_command_failure(): Mock returncode=1, verify success=False
       - test_execute_command_with_args(): Verify args passed to subprocess correctly
       - test_build_command_args(): Verify command list building [atom-os, cmd, arg1, arg2]

    2. Mock pattern:
       - Use patch('subprocess.run') to avoid real CLI execution
       - Mock return: MagicMock(stdout="...", stderr="", returncode=0)
       - Set mock_instance.returncode for different test scenarios

    3. Test class: TestDaemonHelperFunctions:
       - test_is_daemon_running(): Parse status output for "RUNNING"
       - test_get_daemon_pid(): Extract PID from status output
       - test_wait_for_daemon_ready(): Poll status until running

    4. Use pytest.mark.asyncio for async tests if needed

    7+ tests total (wrapper execution + daemon helpers).

    Follow 25-RESEARCH.md for subprocess patterns.
  </action>
  <verify>
    Wrapper execution tests added with subprocess mocking
    Timeout test verifies TimeoutExpired handling
    Daemon helper tests verify PID extraction and polling
    All tests use mock pattern (no real CLI execution)
  </verify>
  <done>
    Execution tests added with subprocess mocking, timeout handling, daemon helpers, 7+ new tests
  </done>
</task>

<task type="auto">
  <name>Add governance and integration tests</name>
  <files>backend/tests/test_atom_cli_skills.py</files>
  <action>
    Add governance and integration tests to test_atom_cli_skills.py:

    1. Test class: TestAtomCliGovernanceGates:
       - test_student_agent_blocked_from_autonomous_skills(): STUDENT agent blocked from daemon/start/stop/execute
       - test_student_agent_can_read_status_config(): STUDENT agent allowed status/config
       - test_autonomous_agent_can_execute_all_skills(): AUTONOMOUS agent has full access
       - test_governance_check_before_cli_execution(): Verify governance check happens before subprocess

    2. Test class: TestAtomCliSkillImport (integration with SkillRegistryService):
       - test_import_all_cli_skills_via_api(): Import all 6 skills, verify skill_id returned
       - test_imported_skills_have_correct_status(): Verify Untrusted/Active based on scan
       - test_execute_imported_skill(): Full integration test (import -> execute -> verify result)

    3. Mock pattern for governance:
       - Mock AgentGovernanceService.check_permission
       - Test with different agent maturity levels

    4. Fixtures:
       - cli_skill_files(): List all 6 SKILL.md file paths
       - mock_subprocess_run(): Shared mock for subprocess calls
       - mock_governance_service(): Shared mock for governance checks

    6+ tests total (governance + integration).

    Follow test_skill_parser.py and test_skill_registry_service.py patterns.
  </action>
  <verify>
    Governance tests verify maturity gates enforced
    Integration tests verify full import->execute flow
    Fixtures provide shared test data
    Tests cover all 4 maturity levels (STUDENT, INTERN, SUPERVISED, AUTONOMOUS)
  </verify>
  <done>
    Governance and integration tests added, maturity gates verified, full import flow tested
  </done>
</task>

</tasks>

<verification>
1. test_atom_cli_skills.py created with 20+ tests
2. Parsing tests verify all 6 skills import correctly
3. Execution tests verify subprocess wrapper with mocking
4. Governance tests verify maturity gates enforced
5. Integration tests verify full import->execute flow
6. All tests follow pytest conventions (fixtures, mocking, assertions)
7. Tests pass with pytest -v backend/tests/test_atom_cli_skills.py
</verification>

<success_criteria>
1. 20+ tests created covering parsing, execution, governance, integration
2. All 6 CLI skills have test coverage
3. Maturity gates verified (AUTONOMOUS blocked for STUDENT, STUDENT allowed for status/config)
4. Subprocess wrapper tests use mocking (no real CLI execution)
5. Integration tests verify full import->execute flow
6. All tests pass with pytest
</success_criteria>

<output>
After completion, create `.planning/phases/25-atom-cli-openclaw-skill/25-atom-cli-openclaw-skill-03-SUMMARY.md` with:
- Test count and coverage (20+ tests)
- Test categories (parsing, execution, governance, integration)
- Mock patterns used (subprocess, governance)
- Test results (pass rate, any failures)
- Governance verification results
- Next steps (Plan 04: documentation and verification)
</output>
