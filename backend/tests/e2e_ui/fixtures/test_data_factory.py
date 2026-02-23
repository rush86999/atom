"""
Test Data Factory Module for E2E UI Testing

This module provides reusable factory functions for generating test data across
different domains: users, agents, skills, projects, episodes, canvas, and chat.

All factories use unique_test_id (from worker_id + uuid4) for parallel execution safety.
Factories return dictionaries suitable for API requests or database initialization.

Key Design Principles:
- unique_test_id prevents parallel execution collisions
- Realistic default values (not "test1", "foo" placeholders)
- **kwargs support for field overrides
- Function-based (not class-based) for simplicity
- API-first design (dictionaries, not ORM instances)

Usage:
    from backend.tests.e2e_ui.fixtures.test_data_factory import user_factory, agent_factory

    # In a test with worker_id fixture
    user_data = user_factory(worker_id)
    agent_data = agent_factory(worker_id, maturity_level="AUTONOMOUS")
"""

from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List


# =============================================================================
# Factory Functions
# =============================================================================

def user_factory(unique_test_id: str, **kwargs) -> Dict[str, Any]:
    """
    Create user test data.

    Default values include realistic email, username, and display names based on
    unique_test_id to prevent collisions in parallel test execution.

    Args:
        unique_test_id: Unique identifier from worker_id + uuid4 (e.g., "gw0_abc123")
        **kwargs: Field overrides (email, username, display_name, password, etc.)

    Returns:
        Dictionary with user fields suitable for API requests or database insertion

    Example:
        user = user_factory("gw0_abc123")
        # Returns: {
        #     "email": "test.user.gw0_abc123@example.com",
        #     "username": "testuser_gw0_abc123",
        #     "display_name": "Test User gw0_abc1",
        #     "password": "SecureTestPassword123!",
        #     "first_name": "Test",
        #     "last_name": "User",
        #     "role": "MEMBER",
        #     "specialty": "Quality Assurance"
        # }
    """
    # Extract short ID for display (first 8 chars)
    short_id = unique_test_id[:8]

    user_data = {
        "email": f"test.user.{unique_test_id}@example.com",
        "username": f"testuser_{unique_test_id}",
        "display_name": f"Test User {short_id}",
        "password": "SecureTestPassword123!",  # Consistent password for tests
        "first_name": "Test",
        "last_name": f"User {short_id}",
        "role": "MEMBER",
        "specialty": "Quality Assurance",
        "status": "ACTIVE",
        "email_verified": True,
        "onboarding_completed": True,
        "capacity_hours": 40.0,
        "hourly_cost_rate": 75.0,
        "preferences": {
            "theme": "light",
            "notifications_enabled": True
        }
    }

    # Apply any custom overrides
    user_data.update(kwargs)
    return user_data


def agent_factory(unique_test_id: str, **kwargs) -> Dict[str, Any]:
    """
    Create agent test data.

    Default values include realistic agent names, descriptions, and capabilities.
    Maturity level defaults to "INTERN" but can be overridden for different
    governance scenarios.

    Args:
        unique_test_id: Unique identifier from worker_id + uuid4
        **kwargs: Field overrides (name, category, maturity_level, capabilities, etc.)

    Returns:
        Dictionary with agent fields

    Example:
        agent = agent_factory("gw0_abc123", maturity_level="AUTONOMOUS")
        # Returns: {
        #     "name": "Test Agent gw0_abc1",
        #     "category": "testing",
        #     "maturity_level": "AUTONOMOUS",
        #     "description": "Test agent created by gw0_abc123",
        #     "capabilities": ["markdown", "charts"],
        #     "confidence_score": 0.95
        # }
    """
    short_id = unique_test_id[:8]

    agent_data = {
        "name": f"Test Agent {short_id}",
        "category": "testing",
        "maturity_level": "INTERN",
        "description": f"Test agent created by {unique_test_id}",
        "capabilities": ["markdown", "charts"],
        "confidence_score": 0.6,
        "module_path": "test.module",
        "class_name": "TestClass",
        "configuration": {
            "timeout": 30,
            "max_retries": 3
        },
        "version": "1.0.0",
        "status": "ACTIVE"
    }

    # Adjust confidence_score based on maturity_level if not overridden
    if "maturity_level" in kwargs and "confidence_score" not in kwargs:
        maturity = kwargs["maturity_level"].upper()
        confidence_map = {
            "STUDENT": 0.4,
            "INTERN": 0.6,
            "SUPERVISED": 0.8,
            "AUTONOMOUS": 0.95
        }
        agent_data["confidence_score"] = confidence_map.get(maturity, 0.6)

    # Apply any custom overrides
    agent_data.update(kwargs)
    return agent_data


def skill_factory(unique_test_id: str, **kwargs) -> Dict[str, Any]:
    """
    Create skill test data.

    Default values include realistic skill names, descriptions, and categories.
    Permissions are set to basic read/write for testing.

    Args:
        unique_test_id: Unique identifier from worker_id + uuid4
        **kwargs: Field overrides (name, display_name, description, category, etc.)

    Returns:
        Dictionary with skill fields

    Example:
        skill = skill_factory("gw0_abc123", category="automation")
        # Returns: {
        #     "name": "test-skill-gw0_abc1",
        #     "display_name": "Test Skill gw0_abc1",
        #     "description": "A test skill for gw0_abc123",
        #     "category": "automation",
        #     "permissions": ["read:basic", "write:basic"],
        #     "version": "1.0.0"
        # }
    """
    short_id = unique_test_id[:8]

    skill_data = {
        "name": f"test-skill-{short_id}",
        "display_name": f"Test Skill {short_id}",
        "description": f"A test skill for {unique_test_id}",
        "category": "productivity",
        "permissions": ["read:basic", "write:basic"],
        "version": "1.0.0",
        "author": f"testuser_{unique_test_id}",
        "tags": ["e2e", "test", short_id],
        "documentation_url": f"https://docs.example.com/skills/{short_id}",
        "repository_url": f"https://github.com/test/skill-{short_id}",
        "status": "PUBLISHED"
    }

    # Apply any custom overrides
    skill_data.update(kwargs)
    return skill_data


def project_factory(unique_test_id: str, **kwargs) -> Dict[str, Any]:
    """
    Create project test data.

    Default values include realistic project names and descriptions.
    Owner ID is generated from unique_test_id if not provided.

    Args:
        unique_test_id: Unique identifier from worker_id + uuid4
        **kwargs: Field overrides (name, description, owner_id, status, etc.)

    Returns:
        Dictionary with project fields

    Example:
        project = project_factory("gw0_abc123")
        # Returns: {
        #     "name": "Test Project gw0_abc1",
        #     "description": "Test project description gw0_abc123",
        #     "owner_id": "user_gw0_abc1",
        #     "status": "ACTIVE",
        #     "type": "automation"
        # }
    """
    short_id = unique_test_id[:8]

    project_data = {
        "name": f"Test Project {short_id}",
        "description": f"Test project description {unique_test_id}",
        "owner_id": f"user_{short_id}",
        "status": "ACTIVE",
        "type": "automation",
        "priority": "medium",
        "start_date": datetime.utcnow().isoformat(),
        "end_date": (datetime.utcnow() + timedelta(days=30)).isoformat(),
        "budget": 10000.00,
        "currency": "USD",
        "team_size": 5,
        "tags": ["e2e", "test", short_id]
    }

    # Apply any custom overrides
    project_data.update(kwargs)
    return project_data


def episode_factory(unique_test_id: str, **kwargs) -> Dict[str, Any]:
    """
    Create episode test data.

    Default values include realistic episode titles, summaries, and tags.
    Episodes are the core unit of episodic memory for agents.

    Args:
        unique_test_id: Unique identifier from worker_id + uuid4
        **kwargs: Field overrides (title, summary, episode_type, tags, etc.)

    Returns:
        Dictionary with episode fields

    Example:
        episode = episode_factory("gw0_abc123")
        # Returns: {
        #     "title": "Test Episode gw0_abc1",
        #     "summary": "Test episode summary gw0_abc123",
        #     "episode_type": "testing",
        #     "tags": ["e2e", "test", "gw0_abc1"],
        #     "status": "completed"
        # }
    """
    short_id = unique_test_id[:8]

    episode_data = {
        "title": f"Test Episode {short_id}",
        "description": f"Test episode description for {unique_test_id}",
        "summary": f"Test episode summary {unique_test_id}",
        "episode_type": "testing",
        "tags": ["e2e", "test", short_id],
        "status": "completed",
        "maturity_at_time": "INTERN",
        "importance_score": 0.7,
        "constitutional_score": 0.85,
        "human_intervention_count": 1,
        "canvas_action_count": 3,
        "started_at": (datetime.utcnow() - timedelta(hours=2)).isoformat(),
        "ended_at": datetime.utcnow().isoformat(),
        "topics": ["testing", "quality assurance"],
        "entities": [f"agent_{short_id}", f"user_{short_id}"]
    }

    # Apply any custom overrides
    episode_data.update(kwargs)
    return episode_data


def canvas_factory(unique_test_id: str, **kwargs) -> Dict[str, Any]:
    """
    Create canvas presentation test data.

    Default values include form canvas type with text and button components.
    Canvas presentations are used for agent-to-user communication.

    Args:
        unique_test_id: Unique identifier from worker_id + uuid4
        **kwargs: Field overrides (canvas_id, type, title, components, etc.)

    Returns:
        Dictionary with canvas fields

    Example:
        canvas = canvas_factory("gw0_abc123", type="chart")
        # Returns: {
        #     "canvas_id": "canvas_gw0_abc123",
        #     "type": "chart",
        #     "title": "Test Canvas gw0_abc1",
        #     "components": [...]
        # }
    """
    short_id = unique_test_id[:8]

    canvas_data = {
        "canvas_id": f"canvas_{unique_test_id}",
        "type": "form",
        "title": f"Test Canvas {short_id}",
        "description": f"Test canvas description for {unique_test_id}",
        "components": [
            {
                "type": "text",
                "content": f"Test content for {short_id}",
                "style": {"fontSize": 16}
            },
            {
                "type": "button",
                "label": "Submit",
                "action": "submit",
                "style": {"primary": True}
            }
        ],
        "layout": {
            "type": "vertical",
            "spacing": "medium"
        },
        "metadata": {
            "created_by": f"agent_{short_id}",
            "created_at": datetime.utcnow().isoformat(),
            "version": "1.0.0"
        }
    }

    # Apply any custom overrides
    canvas_data.update(kwargs)
    return canvas_data


def chat_message_factory(unique_test_id: str, **kwargs) -> Dict[str, Any]:
    """
    Create chat message test data.

    Default values include realistic message content and metadata.
    Messages represent user-agent conversations.

    Args:
        unique_test_id: Unique identifier from worker_id + uuid4
        **kwargs: Field overrides (content, role, agent_id, etc.)

    Returns:
        Dictionary with chat message fields

    Example:
        message = chat_message_factory("gw0_abc123", role="assistant")
        # Returns: {
        #     "content": "Test message gw0_abc123",
        #     "role": "assistant",
        #     "agent_id": "agent_gw0_abc1",
        #     "timestamp": "2026-02-23T16:35:00Z"
        # }
    """
    short_id = unique_test_id[:8]

    message_data = {
        "content": f"Test message {unique_test_id}",
        "role": "user",
        "agent_id": f"agent_{short_id}",
        "session_id": f"session_{unique_test_id}",
        "timestamp": datetime.utcnow().isoformat(),
        "status": "sent",
        "metadata": {
            "test_id": unique_test_id,
            "worker": short_id
        }
    }

    # Apply any custom overrides
    message_data.update(kwargs)
    return message_data


# =============================================================================
# Helper Functions
# =============================================================================

def random_email(unique_test_id: str) -> str:
    """
    Generate unique email based on unique_test_id.

    Args:
        unique_test_id: Unique identifier from worker_id + uuid4

    Returns:
        Unique email address

    Example:
        email = random_email("gw0_abc123")
        # Returns: "test.user.gw0_abc123@example.com"
    """
    return f"test.user.{unique_test_id}@example.com"


def random_username(unique_test_id: str) -> str:
    """
    Generate unique username based on unique_test_id.

    Args:
        unique_test_id: Unique identifier from worker_id + uuid4

    Returns:
        Unique username

    Example:
        username = random_username("gw0_abc123")
        # Returns: "testuser_gw0_abc123"
    """
    return f"testuser_{unique_test_id}"


def random_password() -> str:
    """
    Return consistent test password.

    Uses a consistent password across all tests for simplicity.
    Password meets security requirements (uppercase, lowercase, numbers, special chars).

    Returns:
        Test password string

    Example:
        password = random_password()
        # Returns: "SecureTestPassword123!"
    """
    return "SecureTestPassword123!"


def random_project_name(unique_test_id: str) -> str:
    """
    Generate unique project name based on unique_test_id.

    Args:
        unique_test_id: Unique identifier from worker_id + uuid4

    Returns:
        Unique project name

    Example:
        name = random_project_name("gw0_abc123")
        # Returns: "Test Project gw0_abc1"
    """
    short_id = unique_test_id[:8]
    return f"Test Project {short_id}"


# =============================================================================
# Batch Creation Helpers
# =============================================================================

def create_user_batch(unique_test_id: str, count: int, **kwargs) -> List[Dict[str, Any]]:
    """
    Create multiple users with sequential unique_test_id suffixes.

    Args:
        unique_test_id: Base unique identifier
        count: Number of users to create
        **kwargs: Field overrides applied to all users

    Returns:
        List of user data dictionaries

    Example:
        users = create_user_batch("gw0_abc", 3)
        # Returns: [user_data_1, user_data_2, user_data_3]
    """
    return [
        user_factory(f"{unique_test_id}_{i}", **kwargs)
        for i in range(count)
    ]


def create_agent_batch(unique_test_id: str, count: int, **kwargs) -> List[Dict[str, Any]]:
    """
    Create multiple agents with sequential unique_test_id suffixes.

    Args:
        unique_test_id: Base unique identifier
        count: Number of agents to create
        **kwargs: Field overrides applied to all agents

    Returns:
        List of agent data dictionaries
    """
    return [
        agent_factory(f"{unique_test_id}_{i}", **kwargs)
        for i in range(count)
    ]


def create_skill_batch(unique_test_id: str, count: int, **kwargs) -> List[Dict[str, Any]]:
    """
    Create multiple skills with sequential unique_test_id suffixes.

    Args:
        unique_test_id: Base unique identifier
        count: Number of skills to create
        **kwargs: Field overrides applied to all skills

    Returns:
        List of skill data dictionaries
    """
    return [
        skill_factory(f"{unique_test_id}_{i}", **kwargs)
        for i in range(count)
    ]
