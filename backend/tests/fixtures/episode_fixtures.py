"""
Episode test data factories.

Provides factory functions for creating test episode data with minimal boilerplate.

Note: These are placeholder factories. Actual model imports depend on episode models
being defined in core.models.py. Use these as templates for your specific episode models.
"""

from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List
from sqlalchemy.orm import Session


def create_test_episode(
    db_session: Session,
    agent_id: str = "test_agent",
    title: str = "Test Episode",
    **kwargs
) -> Any:
    """Factory function to create test episodes with defaults.

    Note: This is a template. Implement based on your actual Episode model.

    Args:
        db_session: Database session
        agent_id: Agent ID associated with episode
        title: Episode title
        **kwargs: Additional episode fields

    Returns:
        Created episode instance

    Example:
        episode = create_test_episode(db_session, title="My Episode")
    """
    # TODO: Implement with actual Episode model
    now = datetime.utcnow()
    return {
        "id": "test_episode",
        "agent_id": agent_id,
        "title": title,
        "start_time": kwargs.get("start_time", now - timedelta(hours=1)),
        "end_time": kwargs.get("end_time", now),
    }


def create_episode_segment(
    db_session: Session,
    episode_id: str,
    segment_type: str = "action",
    content: str = "Test content",
    **kwargs
) -> Any:
    """Factory function to create test episode segments.

    Note: This is a template. Implement based on your actual EpisodeSegment model.

    Args:
        db_session: Database session
        episode_id: Parent episode ID
        segment_type: Segment type (action, observation, result)
        content: Segment content
        **kwargs: Additional segment fields

    Returns:
        Created episode segment instance
    """
    # TODO: Implement with actual EpisodeSegment model
    return {
        "id": "test_segment",
        "episode_id": episode_id,
        "segment_type": segment_type,
        "content": content,
        "timestamp": kwargs.get("timestamp", datetime.utcnow()),
    }


def create_episode_with_segments(
    db_session: Session,
    agent_id: str = "test_agent",
    segment_count: int = 5
) -> tuple:
    """Create a complete episode with multiple segments.

    Note: This is a template. Implement based on your actual episode models.

    Args:
        db_session: Database session
        agent_id: Agent ID associated with episode
        segment_count: Number of segments to create

    Returns:
        Tuple of (episode, segments)
    """
    episode = create_test_episode(db_session, agent_id=agent_id)
    segments = [
        create_episode_segment(
            db_session,
            episode_id=episode["id"],
            segment_type=["action", "observation", "result"][i % 3],
            content=f"Segment {i+1} content"
        )
        for i in range(segment_count)
    ]
    return episode, segments


def create_intervention_episode(
    db_session: Session,
    agent_id: str = "test_agent",
    intervention_count: int = 2
) -> Any:
    """Create an episode with interventions for testing graduation logic.

    Note: This is a template. Implement based on your actual Episode model.

    Args:
        db_session: Database session
        agent_id: Agent ID associated with episode
        intervention_count: Number of interventions

    Returns:
        Created episode with intervention_count set
    """
    return create_test_episode(
        db_session,
        agent_id=agent_id,
        title="Intervention Episode",
        intervention_count=intervention_count
    )


def create_episode_batch(
    db_session: Session,
    agent_id: str,
    count: int = 10,
    days_back: int = 30
) -> List:
    """Create multiple episodes spread across time for retrieval testing.

    Note: This is a template. Implement based on your actual Episode model.

    Args:
        db_session: Database session
        agent_id: Agent ID associated with episodes
        count: Number of episodes to create
        days_back: Spread episodes across this many days

    Returns:
        List of created episode instances
    """
    episodes = []
    now = datetime.utcnow()

    for i in range(count):
        days_ago = (i * days_back) // count
        start_time = now - timedelta(days=days_ago, hours=i % 24)
        end_time = start_time + timedelta(hours=1)

        episode = {
            "id": f"episode_{i}",
            "agent_id": agent_id,
            "title": f"Episode {i+1}",
            "start_time": start_time,
            "end_time": end_time,
        }
        episodes.append(episode)

    return episodes
