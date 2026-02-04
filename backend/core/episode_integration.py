"""
Episode auto-creation helper for agent endpoints
"""

import logging
import asyncio
from typing import Optional

logger = logging.getLogger(__name__)


async def _create_episode_after_execution(
    session_id: str,
    agent_id: str,
    title: Optional[str] = None
):
    """
    Background task to create episode after execution.

    Args:
        session_id: Chat session ID
        agent_id: Agent ID
        title: Optional title for episode
    """
    try:
        from core.episode_segmentation_service import EpisodeSegmentationService
        from core.database import get_db_session

        with get_db_session() as db:
            service = EpisodeSegmentationService(db)
            episode = await service.create_episode_from_session(
                session_id=session_id,
                agent_id=agent_id,
                title=title,
                force_create=False  # Only create if meaningful content
            )
            if episode:
                logger.info(f"Created episode {episode.id} after session {session_id}")
    except Exception as e:
        logger.error(f"Failed to create episode: {e}")


def trigger_episode_creation(session_id: str, agent_id: str, title: Optional[str] = None):
    """
    Non-blocking trigger for episode creation.

    Call this after agent execution completes.
    """
    asyncio.create_task(_create_episode_after_execution(session_id, agent_id, title))
