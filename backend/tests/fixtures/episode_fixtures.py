"""
Episode test data factories.

Provides factory functions for creating test episode data with minimal boilerplate.
"""

from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List
from sqlalchemy.orm import Session

from core.models import Episode, EpisodeSegment


def create_test_episode(
    db_session: Session,
    agent_id: str = "test_agent",
    title: str = "Test Episode",
    **kwargs
) -> Episode:
    """Factory function to create test episodes with defaults.

    Args:
        db_session: Database session
        agent_id: Agent ID associated with episode
        title: Episode title
        **kwargs: Additional Episode fields

    Returns:
        Created Episode instance

    Example:
        episode = create_test_episode(db_session, title="My Episode")
    """
    now = datetime.utcnow()
    episode = Episode(
        agent_id=agent_id,
        title=title,
        summary=kwargs.get("summary", f"Test episode: {title}"),
        start_time=kwargs.get("start_time", now - timedelta(hours=1)),
        end_time=kwargs.get("end_time", now),
        maturity_level=kwargs.get("maturity_level", "INTERN"),
        intervention_count=kwargs.get("intervention_count", 0),
        created_at=kwargs.get("created_at", now),
        **{k: v for k, v in kwargs.items() if k not in [
            "summary", "start_time", "end_time", "maturity_level",
            "intervention_count", "created_at"
        ]}
    )
    db_session.add(episode)
    db_session.commit()
    db_session.refresh(episode)
    return episode


def create_episode_segment(
    db_session: Session,
    episode_id: str,
    segment_type: str = "action",
    content: str = "Test content",
    **kwargs
) -> EpisodeSegment:
    """Factory function to create test episode segments.

    Args:
        db_session: Database session
        episode_id: Parent episode ID
        segment_type: Segment type (action, observation, result)
        content: Segment content
        **kwargs: Additional EpisodeSegment fields

    Returns:
        Created EpisodeSegment instance
    """
    segment = EpisodeSegment(
        episode_id=episode_id,
        segment_type=segment_type,
        content=content,
        timestamp=kwargs.get("timestamp", datetime.utcnow()),
        metadata=kwargs.get("metadata", {}),
        **{k: v for k, v in kwargs.items() if k not in ["timestamp", "metadata"]}
    )
    db_session.add(segment)
    db_session.commit()
    db_session.refresh(segment)
    return segment


def create_episode_with_segments(
    db_session: Session,
    agent_id: str = "test_agent",
    segment_count: int = 5
) -> tuple[Episode, List[EpisodeSegment]]:
    """Create a complete episode with multiple segments.

    Args:
        db_session: Database session
        agent_id: Agent ID associated with episode
        segment_count: Number of segments to create

    Returns:
        Tuple of (episode, segments)
    """
    episode = create_test_episode(db_session, agent_id=agent_id)

    segments = []
    segment_types = ["action", "observation", "result"]
    for i in range(segment_count):
        segment = create_episode_segment(
            db_session,
            episode_id=episode.id,
            segment_type=segment_types[i % len(segment_types)],
            content=f"Segment {i+1} content"
        )
        segments.append(segment)

    return episode, segments


def create_intervention_episode(
    db_session: Session,
    agent_id: str = "test_agent",
    intervention_count: int = 2
) -> Episode:
    """Create an episode with interventions for testing graduation logic.

    Args:
        db_session: Database session
        agent_id: Agent ID associated with episode
        intervention_count: Number of interventions

    Returns:
        Created Episode with intervention_count set
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
) -> List[Episode]:
    """Create multiple episodes spread across time for retrieval testing.

    Args:
        db_session: Database session
        agent_id: Agent ID associated with episodes
        count: Number of episodes to create
        days_back: Spread episodes across this many days

    Returns:
        List of created Episode instances
    """
    episodes = []
    now = datetime.utcnow()

    for i in range(count):
        days_ago = (i * days_back) // count
        start_time = now - timedelta(days=days_ago, hours=i % 24)
        end_time = start_time + timedelta(hours=1)

        episode = Episode(
            agent_id=agent_id,
            title=f"Episode {i+1}",
            summary=f"Test episode {i+1} from {days_ago} days ago",
            start_time=start_time,
            end_time=end_time,
            maturity_level="INTERN",
            intervention_count=0,
            created_at=end_time
        )
        db_session.add(episode)
        episodes.append(episode)

    db_session.commit()
    return episodes
