"""
Custom assertion functions for common test validations.

These assertions provide better error messages and ensure
consistent validation patterns across tests.
"""

import time
from typing import Optional
from sqlalchemy.orm import Session

from core.models import AgentRegistry, AgentStatus, Episode, CanvasAudit
from core.governance_cache import governance_cache


def assert_agent_maturity(
    agent: AgentRegistry,
    expected_maturity: str,
    confidence_delta: float = 0.01
) -> None:
    """
    Assert agent has expected maturity level.

    Args:
        agent: Agent to check
        expected_maturity: Expected maturity (STUDENT, INTERN, SUPERVISED, AUTONOMOUS)
        confidence_delta: Allowed variance in confidence score

    Raises:
        AssertionError: If maturity doesn't match or confidence out of range

    Usage:
        assert_agent_maturity(agent, "AUTONOMOUS")
        assert_agent_maturity(agent, "STUDENT", confidence_delta=0.05)
    """
    actual_status = AgentStatus(agent.status)
    expected_status = AgentStatus[expected_maturity]

    # Check status matches
    assert actual_status == expected_status, \
        f"Agent {agent.name} has maturity {actual_status.value}, expected {expected_status.value}"

    # Check confidence is in expected range for maturity
    confidence = agent.confidence_score
    if expected_maturity == "STUDENT":
        assert confidence < 0.5, \
            f"STUDENT agent has confidence {confidence}, expected < 0.5"
    elif expected_maturity == "INTERN":
        assert 0.5 <= confidence < 0.7, \
            f"INTERN agent has confidence {confidence}, expected [0.5, 0.7)"
    elif expected_maturity == "SUPERVISED":
        assert 0.7 <= confidence < 0.9, \
            f"SUPERVISED agent has confidence {confidence}, expected [0.7, 0.9)"
    elif expected_maturity == "AUTONOMOUS":
        assert confidence >= 0.9, \
            f"AUTONOMOUS agent has confidence {confidence}, expected >= 0.9"


def assert_governance_blocked(
    agent_id: str,
    action: str,
    reason: Optional[str] = None
) -> None:
    """
    Assert action was blocked by governance.

    Args:
        agent_id: Agent ID
        action: Action that was blocked
        reason: Expected reason for blocking (optional)

    Raises:
        AssertionError: If action wasn't blocked or reason doesn't match

    Usage:
        assert_governance_blocked("student-agent-id", "delete_user")
        assert_governance_blocked("student-agent-id", "delete_user", reason="maturity")
    """
    # Check governance cache for blocked decision
    decision = governance_cache.check(agent_id, action)
    assert decision.allowed is False, \
        f"Action {action} was not blocked for agent {agent_id}"

    if reason:
        assert reason in decision.reason.lower(), \
            f"Blocking reason '{decision.reason}' doesn't contain '{reason}'"


def assert_episode_created(
    db_session: Session,
    agent_id: str,
    min_segments: int = 1
) -> Episode:
    """
    Assert episode was created for agent with minimum segments.

    Args:
        db_session: Database session
        agent_id: Agent ID
        min_segments: Minimum expected segment count

    Returns:
        The created Episode

    Raises:
        AssertionError: If no episode found or segment count too low

    Usage:
        episode = assert_episode_created(db_session, "agent-id", min_segments=3)
    """
    episode = db_session.query(Episode).filter(
        Episode.agent_id == agent_id
    ).first()

    assert episode is not None, \
        f"No episode found for agent {agent_id}"

    assert episode.segment_count >= min_segments, \
        f"Episode has {episode.segment_count} segments, expected >= {min_segments}"

    return episode


def assert_canvas_presented(
    db_session: Session,
    agent_id: str,
    canvas_type: Optional[str] = None
) -> CanvasAudit:
    """
    Assert canvas was presented by agent.

    Args:
        db_session: Database session
        agent_id: Agent ID
        canvas_type: Expected canvas type (optional)

    Returns:
        The CanvasAudit record

    Raises:
        AssertionError: If no canvas audit found

    Usage:
        canvas = assert_canvas_presented(db_session, "agent-id", canvas_type="sheets")
        canvas = assert_canvas_presented(db_session, "agent-id")  # Any type
    """
    query = db_session.query(CanvasAudit).filter(
        CanvasAudit.agent_id == agent_id,
        CanvasAudit.action == "present"
    )

    if canvas_type:
        query = query.filter(CanvasAudit.canvas_type == canvas_type)

    canvas = query.first()

    assert canvas is not None, \
        f"No canvas presentation found for agent {agent_id}" + \
        (f" of type {canvas_type}" if canvas_type else "")

    return canvas


def assert_coverage_threshold(
    coverage_data: dict,
    module: str,
    min_coverage: float
) -> None:
    """
    Assert module meets coverage threshold.

    Args:
        coverage_data: Coverage data from coverage.json
        module: Module name to check
        min_coverage: Minimum required coverage (0-100)

    Raises:
        AssertionError: If coverage below threshold

    Usage:
        assert_coverage_threshold(coverage_data, "governance_cache", 80.0)
    """
    # Find module in coverage data
    module_coverage = 0.0
    for file_path, metrics in coverage_data.get('files', {}).items():
        if module in file_path:
            pct = metrics.get('summary', {}).get('percent_covered', 0)
            module_coverage = max(module_coverage, pct)

    assert module_coverage >= min_coverage, \
        f"Module {module} has {module_coverage:.1f}% coverage, " \
        f"expected >= {min_coverage:.1f}%"


def assert_performance_baseline(
    duration: float,
    max_duration: float,
    operation: str
) -> None:
    """
    Assert operation completes within performance baseline.

    Args:
        duration: Actual operation duration (seconds)
        max_duration: Maximum allowed duration (seconds)
        operation: Operation name for error message

    Raises:
        AssertionError: If duration exceeds baseline

    Usage:
        start = time.time()
        result = execute_operation()
        duration = time.time() - start
        assert_performance_baseline(duration, 1.0, "database query")
    """
    assert duration <= max_duration, \
        f"{operation} took {duration:.2f}s, expected <= {max_duration:.2f}s"
