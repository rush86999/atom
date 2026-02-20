"""
Agent test data factories.

Provides factory functions for creating test agent data with minimal boilerplate.
All factory functions create fresh instances to ensure test independence.
"""

from datetime import datetime
from typing import Optional, Dict, Any
from sqlalchemy.orm import Session

from core.models import AgentRegistry, AgentStatus, AgentMaturity


def create_test_agent(
    db_session: Session,
    name: str = "TestAgent",
    category: str = "test",
    maturity: str = "INTERN",
    confidence_score: float = 0.6,
    **kwargs
) -> AgentRegistry:
    """Factory function to create test agents with defaults.

    Args:
        db_session: Database session
        name: Agent name
        category: Agent category
        maturity: Agent maturity level (STUDENT, INTERN, SUPERVISED, AUTONOMOUS)
        confidence_score: Agent confidence score (0.0-1.0)
        **kwargs: Additional AgentRegistry fields

    Returns:
        Created AgentRegistry instance

    Example:
        agent = create_test_agent(db_session, name="MyAgent", maturity="AUTONOMOUS")
    """
    agent = AgentRegistry(
        name=name,
        category=category,
        module_path=kwargs.get("module_path", "test.module"),
        class_name=kwargs.get("class_name", "TestClass"),
        status=maturity,
        confidence_score=confidence_score,
        description=kwargs.get("description", f"Test agent {name}"),
        version=kwargs.get("version", "1.0.0"),
        created_at=kwargs.get("created_at", datetime.utcnow()),
        **{k: v for k, v in kwargs.items() if k not in ["module_path", "class_name", "description", "version", "created_at"]}
    )
    db_session.add(agent)
    db_session.commit()
    db_session.refresh(agent)
    return agent


def create_student_agent(db_session: Session, **kwargs) -> AgentRegistry:
    """Create a STUDENT maturity test agent."""
    return create_test_agent(
        db_session,
        maturity=AgentStatus.STUDENT.value,
        confidence_score=0.3,
        **kwargs
    )


def create_intern_agent(db_session: Session, **kwargs) -> AgentRegistry:
    """Create an INTERN maturity test agent."""
    return create_test_agent(
        db_session,
        maturity=AgentStatus.INTERN.value,
        confidence_score=0.6,
        **kwargs
    )


def create_supervised_agent(db_session: Session, **kwargs) -> AgentRegistry:
    """Create a SUPERVISED maturity test agent."""
    return create_test_agent(
        db_session,
        maturity=AgentStatus.SUPERVISED.value,
        confidence_score=0.8,
        **kwargs
    )


def create_autonomous_agent(db_session: Session, **kwargs) -> AgentRegistry:
    """Create an AUTONOMOUS maturity test agent."""
    return create_test_agent(
        db_session,
        maturity=AgentStatus.AUTONOMOUS.value,
        confidence_score=0.95,
        **kwargs
    )


def create_agent_batch(
    db_session: Session,
    count: int = 5,
    maturity: str = "INTERN",
    category: str = "test"
) -> list[AgentRegistry]:
    """Create multiple test agents with default settings.

    Args:
        db_session: Database session
        count: Number of agents to create
        maturity: Agent maturity level
        category: Agent category

    Returns:
        List of created AgentRegistry instances
    """
    agents = []
    for i in range(count):
        agent = create_test_agent(
            db_session,
            name=f"{category.title()}Agent{i+1}",
            category=category,
            maturity=maturity
        )
        agents.append(agent)
    return agents
