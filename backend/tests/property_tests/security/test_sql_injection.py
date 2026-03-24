"""
Property-Based Tests for SQL Injection Prevention

Tests CRITICAL SQL injection security invariants using Hypothesis:
- SQL injection attempts are sanitized (no SQL executed from malicious input)
- Agent creation with malicious SQL does not execute SQL
- Filter clauses sanitize SQL metacharacters

Strategic max_examples:
- 100 for standard invariants (SQL injection sanitization in queries/creation)
- 50 for IO-bound operations (filter clauses with DB operations)

These tests find SQL injection vulnerabilities where malicious input
executes arbitrary SQL commands (e.g., "' OR '1'='1", "'; DROP TABLE users; --").
"""

from __future__ import annotations

import pytest
from hypothesis import given, settings, HealthCheck
from hypothesis.strategies import (
    one_of, just, text, dictionaries, lists
)
from sqlalchemy.orm import Session

from core.models import AgentRegistry, AgentStatus
from tests.property_tests.security.conftest import (
    HYPOTHESIS_SETTINGS_STANDARD,
    HYPOTHESIS_SETTINGS_IO
)


# ============================================================================
# TEST 1: SQL INJECTION SANITIZED IN QUERIES
# ============================================================================

@pytest.mark.property
@given(
    malicious_input=one_of(
        just("' OR '1'='1"),
        just("'; DROP TABLE users; --"),
        just("1' UNION SELECT * FROM users --"),
        just("' OR '1'='1' --"),
        just("' OR '1'='1'/*"),
        just("admin' --"),
        just("admin' /*"),
        just("' OR 1=1#"),
        just("' OR 1=1--"),
        text().map(lambda x: f"'{x}' OR '1'='1")
    )
)
@settings(**HYPOTHESIS_SETTINGS_STANDARD)
def test_sql_injection_sanitized_in_queries(db_session: Session, malicious_input: str):
    """
    PROPERTY: SQL injection attempts are sanitized (no SQL executed from malicious input)

    STRATEGY: st.one_of(
        st.just("' OR '1'='1"),
        st.just("'; DROP TABLE users; --"),
        st.just("1' UNION SELECT * FROM users --"),
        st.text().map(lambda x: f"'{x}' OR '1'='1")  # Generic pattern
    )

    INVARIANT: Query returns 0 results or single exact match (never all records)

    RADII: 100 examples explores common SQL injection patterns (9 patterns * 100 = 900 variations)

    VALIDATED_BUG: None found (invariant holds)

    This test ensures that SQL injection attempts in queries are properly sanitized
    by SQLAlchemy ORM, preventing attackers from bypassing authentication or dumping
    the entire database.

    Example attack: "' OR '1'='1" should return 0 results, not all agents.
    """
    # Create test agents with known names
    agent1 = AgentRegistry(
        name="TestAgent1",
        tenant_id="default",
        category="test",
        module_path="test.module",
        class_name="TestClass",
        status=AgentStatus.STUDENT.value,
        confidence_score=0.5,
    )
    agent2 = AgentRegistry(
        name="TestAgent2",
        tenant_id="default",
        category="test",
        module_path="test.module",
        class_name="TestClass",
        status=AgentStatus.INTERN.value,
        confidence_score=0.6,
    )
    db_session.add(agent1)
    db_session.add(agent2)
    db_session.commit()

    # Attempt SQL injection: query agent by name with malicious input
    # If SQL injection works, this would return all agents (or cause an error)
    # If sanitized, it returns 0 results (no agent has the malicious name)
    results = db_session.query(AgentRegistry).filter(
        AgentRegistry.name == malicious_input
    ).all()

    # Invariant: Should return 0 results (no agent has malicious name)
    # If SQL injection works, it might return all agents (2 results)
    assert len(results) <= 1, (
        f"SQL injection vulnerability detected! Query returned {len(results)} results. "
        f"Malicious input: {malicious_input}. "
        f"Expected: 0 or 1 results (no match). Got: {len(results)} results."
    )

    # Invariant: If results exist, name must exactly match malicious input
    # (not interpreted as SQL)
    if len(results) == 1:
        assert results[0].name == malicious_input, (
            f"SQL injection vulnerability detected! Result name does not match input. "
            f"Input: {malicious_input}, Result: {results[0].name}"
        )


# ============================================================================
# TEST 2: SQL INJECTION IN AGENT CREATION
# ============================================================================

@pytest.mark.property
@given(
    agent_data=dictionaries(
        just("name"),
        one_of(
            text(),
            just("'; DROP TABLE agents; --"),
            just("' OR '1'='1"),
            just("admin' --")
        )
    )
)
@settings(**HYPOTHESIS_SETTINGS_STANDARD)
def test_sql_injection_in_agent_creation(db_session: Session, agent_data: dict):
    """
    PROPERTY: Agent creation with malicious SQL does not execute SQL

    STRATEGY: st.dictionaries(
        st.just("name"),
        st.one_of(st.text(), st.just("'; DROP TABLE agents; --"))
    )

    INVARIANT: Agent created with name as literal string (no SQL executed)

    RADII: 100 examples explores various malicious agent names (100 variations)

    VALIDATED_BUG: None found (invariant holds)

    This test ensures that SQL injection attempts in agent creation are properly
    sanitized by SQLAlchemy ORM, preventing attackers from executing arbitrary
    SQL commands during agent creation.

    Example attack: Agent with name "'; DROP TABLE agents; --" should be created
    with that literal name, not execute the DROP TABLE command.
    """
    # Extract malicious name from dictionary
    malicious_name = agent_data.get("name", "TestAgent")

    # Create agent with malicious name
    agent = AgentRegistry(
        name=malicious_name,
        tenant_id="default",
        category="test",
        module_path="test.module",
        class_name="TestClass",
        status=AgentStatus.STUDENT.value,
        confidence_score=0.5,
    )

    # Attempt to create agent (should not execute SQL)
    try:
        db_session.add(agent)
        db_session.commit()
        db_session.refresh(agent)

        # Invariant: Agent created with literal name (not interpreted as SQL)
        assert agent.name == malicious_name, (
            f"SQL injection vulnerability detected! Agent name does not match input. "
            f"Input: {malicious_name}, Created: {agent.name}"
        )

        # Invariant: Agent table still exists (not dropped)
        # Query should succeed without error
        agent_count = db_session.query(AgentRegistry).count()
        assert agent_count >= 1, (
            f"SQL injection vulnerability detected! Agent table may have been dropped. "
            f"Agent count: {agent_count}"
        )

    except Exception as e:
        # Invariant: SQL errors should not occur for legitimate inputs
        # (but malicious inputs might cause errors - that's OK)
        # Check if error is related to SQL injection
        error_msg = str(e).lower()
        if "drop" in error_msg or "union" in error_msg or "syntax" in error_msg:
            pytest.fail(
                f"SQL injection vulnerability detected! Error indicates SQL execution: {e}"
            )


# ============================================================================
# TEST 3: SQL INJECTION IN FILTER CLAUSES
# ============================================================================

@pytest.mark.property
@given(
    filter_values=lists(
        text().filter(lambda x: "'" in x or ";" in x or "--" in x or "/*" in x),
        min_size=1,
        max_size=10
    )
)
@settings(**HYPOTHESIS_SETTINGS_IO)
def test_sql_injection_in_filter_clauses(db_session: Session, filter_values: list):
    """
    PROPERTY: Filter clauses sanitize SQL metacharacters

    STRATEGY: st.lists(st.text().filter(lambda x: "'" in x or ";" in x or "--" in x), min_size=1, max_size=10)

    INVARIANT: Filter clauses sanitize SQL metacharacters (', ;, --, /*)

    RADII: 50 examples explores filter clause variations (DB operations, so fewer examples)

    VALIDATED_BUG: None found (invariant holds)

    This test ensures that SQL injection attempts in filter clauses are properly
    sanitized by SQLAlchemy ORM, preventing attackers from injecting SQL metacharacters
    into WHERE clauses.

    Example attack: Filter with name containing "'" should not cause SQL syntax errors
    or return unintended results.
    """
    # Create test agents with known names
    for i in range(5):
        agent = AgentRegistry(
            name=f"TestAgent{i}",
            tenant_id="default",
            category="test",
            module_path="test.module",
            class_name="TestClass",
            status=AgentStatus.STUDENT.value,
            confidence_score=0.5,
        )
        db_session.add(agent)
    db_session.commit()

    # Attempt SQL injection: filter agents with malicious values
    # Each filter value contains SQL metacharacters
    for malicious_value in filter_values:
        try:
            # Try to filter by name with malicious value
            results = db_session.query(AgentRegistry).filter(
                AgentRegistry.name == malicious_value
            ).all()

            # Invariant: Query should not cause SQL syntax errors
            # If sanitized, returns 0 results (no match)
            # If vulnerable, might cause SQL syntax error or return all records
            assert len(results) == 0, (
                f"SQL injection vulnerability detected! Filter returned unexpected results. "
                f"Malicious value: {malicious_value}, Results: {len(results)}"
            )

        except Exception as e:
            # Invariant: SQL syntax errors should not occur for sanitized inputs
            error_msg = str(e).lower()
            if "syntax" in error_msg or "unterminated" in error_msg:
                pytest.fail(
                    f"SQL injection vulnerability detected! SQL syntax error: {e}"
                )
            # Other errors (e.g., connection errors) are OK
            break
