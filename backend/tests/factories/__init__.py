"""
Test data factories for Atom platform.

Uses factory_boy for dynamic, isolated test data generation.
All factories inherit from BaseFactory which manages SQLAlchemy sessions.
"""

from tests.factories.base import BaseFactory
from tests.factories.agent_factory import (
    AgentFactory,
    StudentAgentFactory,
    InternAgentFactory,
    SupervisedAgentFactory,
    AutonomousAgentFactory,
)
from tests.factories.user_factory import UserFactory, AdminUserFactory, MemberUserFactory
from tests.factories.episode_factory import EpisodeFactory, EpisodeSegmentFactory
from tests.factories.execution_factory import AgentExecutionFactory
from tests.factories.canvas_factory import CanvasAuditFactory
from tests.factories.chat_session_factory import ChatSessionFactory

__all__ = [
    'BaseFactory',
    'AgentFactory',
    'StudentAgentFactory',
    'InternAgentFactory',
    'SupervisedAgentFactory',
    'AutonomousAgentFactory',
    'UserFactory',
    'AdminUserFactory',
    'MemberUserFactory',
    'EpisodeFactory',
    'EpisodeSegmentFactory',
    'AgentExecutionFactory',
    'CanvasAuditFactory',
    'ChatSessionFactory',
]
