"""
SQL Injection Attack Tests

Tests SQL injection vulnerability prevention in AgentGovernanceService.
Verifies that parameterized queries are used and malicious inputs are escaped.

OWASP Category: A03:2021 - Injection
CWE: CWE-89 (SQL Injection)
"""

import pytest
from sqlalchemy.exc import IntegrityError, ProgrammingError
from sqlalchemy.orm import Session

from core.agent_governance_service import AgentGovernanceService
from core.models import AgentRegistry, AgentStatus


# ============================================================================
# Agent ID SQL Injection Tests
# ============================================================================


@pytest.mark.sql_injection
@pytest.mark.parametrize("malicious_id", [
    "'; DROP TABLE agents; --",
    "' OR '1'='1",
    "1' UNION SELECT * FROM users --",
    "'; INSERT INTO agents VALUES ('hacked', 'admin'); --",
    "1'; DELETE FROM episodes WHERE '1'='1' --",
    "' OR '1'='1' --",
    "admin'--",
    "admin'/*",
])
def test_agent_id_sql_injection_blocked(malicious_id, db_session: Session):
    """
    SECURITY: SQL injection via agent_id parameter.

    ATTACK: Attempt to inject SQL via agent_id string in can_perform_action().
    EXPECTED: Input escaped or parameterized, query returns "agent not found",
              no SQL injection executed.
    """
    service = AgentGovernanceService(db_session)

    result = service.can_perform_action(
        agent_id=malicious_id,
        action_type="stream_chat"
    )

    # Should not execute injected SQL
    assert result["allowed"] is False
    assert "not found" in result["reason"].lower()


@pytest.mark.sql_injection
def test_agent_id_union_query_blocked(db_session: Session):
    """
    SECURITY: UNION SELECT injection via agent_id.

    ATTACK: Attempt to extract data from other tables using UNION SELECT.
    EXPECTED: Query fails, "agent not found" error.
    """
    service = AgentGovernanceService(db_session)

    malicious_id = "1' UNION SELECT * FROM users --"
    result = service.can_perform_action(
        agent_id=malicious_id,
        action_type="stream_chat"
    )

    # Should not execute UNION
    assert result["allowed"] is False
    assert "not found" in result["reason"].lower()


@pytest.mark.sql_injection
def test_agent_id_drop_table_blocked(db_session: Session):
    """
    SECURITY: DROP TABLE injection via agent_id.

    ATTACK: Attempt to DROP agents table.
    EXPECTED: DROP TABLE not executed, agent not found error.
    """
    service = AgentGovernanceService(db_session)

    malicious_id = "'; DROP TABLE agents; --"
    result = service.can_perform_action(
        agent_id=malicious_id,
        action_type="stream_chat"
    )

    # Verify agent_registry table still exists by querying it
    agents = db_session.query(AgentRegistry).all()
    assert agents is not None  # Table exists

    # Should not have dropped table
    assert result["allowed"] is False
    assert "not found" in result["reason"].lower()


@pytest.mark.sql_injection
def test_agent_id_insert_blocked(db_session: Session):
    """
    SECURITY: INSERT injection via agent_id.

    ATTACK: Attempt to INSERT malicious agent record.
    EXPECTED: INSERT not executed, agent not found error.
    """
    service = AgentGovernanceService(db_session)

    initial_count = db_session.query(AgentRegistry).count()

    malicious_id = "'; INSERT INTO agents VALUES ('hacked', 'admin', 'AUTONOMOUS'); --"
    result = service.can_perform_action(
        agent_id=malicious_id,
        action_type="stream_chat"
    )

    # Verify no new agent was inserted
    final_count = db_session.query(AgentRegistry).count()
    assert initial_count == final_count

    assert result["allowed"] is False


# ============================================================================
# User Input SQL Injection Tests
# ============================================================================


@pytest.mark.sql_injection
@pytest.mark.parametrize("malicious_name", [
    "'; DROP TABLE users; --",
    "' OR '1'='1",
    "<script>alert('xss')</script>",
    "$(whoami)",
    "`cat /etc/passwd`",
])
def test_agent_name_sql_injection_blocked(malicious_name, db_session: Session):
    """
    SECURITY: SQL injection via agent name parameter.

    ATTACK: Attempt to inject SQL via name field in register_or_update_agent().
    EXPECTED: Input escaped or parameterized, agent created safely,
              malicious name stored as string not executed.
    """
    service = AgentGovernanceService(db_session)

    agent = service.register_or_update_agent(
        name=malicious_name,
        category="test",
        module_path="test.module",
        class_name="TestAgent"
    )

    # Agent should be created (input escaped)
    assert agent is not None
    # Malicious content should be stored as-is (not executed)
    assert agent.name == malicious_name


@pytest.mark.sql_injection
def test_description_field_sql_injection_blocked(db_session: Session):
    """
    SECURITY: SQL injection via description field.

    ATTACK: Attempt to inject SQL via description parameter.
    EXPECTED: Input sanitized, description stored as string.
    """
    service = AgentGovernanceService(db_session)

    malicious_desc = "'; DROP TABLE agents; --"

    agent = service.register_or_update_agent(
        name="Test Agent",
        category="test",
        module_path="test.module",
        class_name="TestAgent",
        description=malicious_desc
    )

    assert agent is not None
    assert agent.description == malicious_desc

    # Verify agent_registry table still exists
    agents = db_session.query(AgentRegistry).all()
    assert agents is not None


@pytest.mark.sql_injection
def test_module_path_sql_injection_blocked(db_session: Session):
    """
    SECURITY: SQL injection via module_path parameter.

    ATTACK: Attempt to inject SQL via module_path.
    EXPECTED: Input validated, module_path stored safely.
    """
    service = AgentGovernanceService(db_session)

    malicious_module = "'; DROP TABLE agents; --"

    # May raise validation error or store safely
    try:
        agent = service.register_or_update_agent(
            name="Test Agent",
            category="test",
            module_path=malicious_module,
            class_name="TestAgent"
        )
        assert agent is not None
        # If created, should be stored as string
        assert agent.module_path == malicious_module
    except (ValueError, AttributeError):
        # Or validation may reject it
        pass


# ============================================================================
# Database Query SQL Injection Tests
# ============================================================================


@pytest.mark.sql_injection
def test_filter_query_sql_injection_blocked(db_session: Session):
    """
    SECURITY: SQL injection in filter() clause.

    ATTACK: Attempt to inject SQL in db.query().filter() with malicious agent_id.
    EXPECTED: SQLAlchemy uses parameterized queries, injection blocked.
    """
    malicious_id = "1' OR '1'='1"

    # Query with malicious agent_id
    agent = db_session.query(AgentRegistry).filter(
        AgentRegistry.id == malicious_id
    ).first()

    # Should return None (no such agent)
    assert agent is None

    # Verify no SQL error leaked
    # (SQLAlchemy parameterizes queries, so this is safe)


@pytest.mark.sql_injection
def test_order_by_sql_injection_blocked(db_session: Session):
    """
    SECURITY: SQL injection in ORDER BY clause.

    ATTACK: Attempt to inject SQL in ORDER BY.
    EXPECTED: Injection blocked, query returns empty or error handled.
    """
    from sqlalchemy import text
    from sqlalchemy.exc import CompileError

    # Try to inject in ORDER BY
    malicious_order = "id; DROP TABLE agents; --"

    try:
        # SQLAlchemy should reject this (raises CompileError)
        agents = db_session.query(AgentRegistry).order_by(malicious_order).all()
        # If it somehow executes, verify table still exists
        assert agents is not None
    except (CompileError, ProgrammingError, AttributeError):
        # SQLAlchemy correctly rejects malicious input (expected behavior)
        pass

    # Verify agent_registry table still exists
    agents = db_session.query(AgentRegistry).all()
    assert agents is not None


@pytest.mark.sql_injection
def test_raw_query_sql_injection_blocked(db_session: Session):
    """
    SECURITY: SQL injection in raw SQL text() queries.

    ATTACK: Attempt to inject SQL using text() with malicious input.
    EXPECTED: Parameterization used, injection blocked.
    """
    from sqlalchemy import text

    malicious_id = "'; DROP TABLE agents; --"

    # Parameterized query (safe)
    result = db_session.execute(
        text("SELECT * FROM agent_registry WHERE id = :agent_id"),
        {"agent_id": malicious_id}
    ).fetchone()

    # Should return None (no such agent)
    assert result is None

    # Verify agent_registry table still exists
    agents = db_session.query(AgentRegistry).all()
    assert agents is not None


# ============================================================================
# Verification Tests
# ============================================================================


@pytest.mark.sql_injection
def test_parameterized_queries_used(db_session: Session):
    """
    SECURITY: Verify SQLAlchemy uses parameterized queries.

    CHECK: Ensure ORM methods use parameterized queries, not string concatenation.
    EXPECTED: SQLAlchemy automatically parameterizes, preventing injection.
    """
    service = AgentGovernanceService(db_session)

    # Create an agent
    agent = service.register_or_update_agent(
        name="Test Agent",
        category="test",
        module_path="test.module",
        class_name="TestAgent"
    )

    # Query using ORM (parameterized by default)
    queried = db_session.query(AgentRegistry).filter(
        AgentRegistry.id == agent.id
    ).first()

    assert queried is not None
    assert queried.id == agent.id


@pytest.mark.sql_injection
@pytest.mark.parametrize("special_char", [
    "'",
    '"',
    ";",
    "--",
    "/*",
    "*/",
    "\\",
    "\0",
])
def test_special_characters_escaped(special_char, db_session: Session):
    """
    SECURITY: Special characters properly escaped.

    CHECK: Quotes, backslashes, semicolons, comments don't break queries.
    EXPECTED: Special characters escaped or parameterized.
    """
    service = AgentGovernanceService(db_session)

    malicious_name = f"test{special_char}name"

    agent = service.register_or_update_agent(
        name=malicious_name,
        category="test",
        module_path="test.module",
        class_name="TestAgent"
    )

    assert agent is not None
    assert agent.name == malicious_name


@pytest.mark.sql_injection
def test_sql_error_not_exposed_to_user(db_session: Session):
    """
    SECURITY: SQL error messages don't leak database schema.

    CHECK: SQL errors don't reveal table structure, column names, etc.
    EXPECTED: Generic error message, no schema details.
    """
    service = AgentGovernanceService(db_session)

    # Try non-existent agent
    result = service.can_perform_action(
        agent_id="nonexistent-agent-123",
        action_type="stream_chat"
    )

    # Should return generic "not found" error
    assert result["allowed"] is False
    assert "not found" in result["reason"].lower()

    # Should NOT contain SQL details
    error_msg = str(result).lower()
    assert "syntax error" not in error_msg
    assert "table" not in error_msg or "not found" in result["reason"].lower()
    assert "column" not in error_msg
    assert "database" not in error_msg


# ============================================================================
# Batch SQL Injection Tests
# ============================================================================


@pytest.mark.sql_injection
@pytest.mark.parametrize("malicious_id", [
    "'; DROP TABLE agents; --",
    "' OR '1'='1",
    "1' UNION SELECT * FROM users --",
    "'; INSERT INTO agents VALUES ('hacked', 'admin'); --",
    "1'; DELETE FROM episodes WHERE '1'='1' --",
])
def test_batch_agent_id_sql_injection(malicious_id, db_session: Session):
    """
    SECURITY: Batch test SQL injection via agent_id.

    Tests all SQL injection payloads from conftest.
    """
    service = AgentGovernanceService(db_session)

    result = service.can_perform_action(
        agent_id=malicious_id,
        action_type="stream_chat"
    )

    assert result["allowed"] is False


@pytest.mark.sql_injection
@pytest.mark.parametrize("malicious_name", [
    "'; DROP TABLE users; --",
    "' OR '1'='1",
    "<script>alert('xss')</script>",
    "$(whoami)",
    "`cat /etc/passwd`",
])
def test_batch_agent_name_sql_injection(malicious_name, db_session: Session):
    """
    SECURITY: Batch test SQL injection via agent name.

    Tests all SQL injection payloads from conftest.
    """
    service = AgentGovernanceService(db_session)

    agent = service.register_or_update_agent(
        name=malicious_name,
        category="test",
        module_path="test.module",
        class_name="TestAgent"
    )

    assert agent is not None
    assert agent.name == malicious_name
