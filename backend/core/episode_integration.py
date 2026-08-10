"""
Episode auto-creation helper for agent endpoints
"""

import asyncio
import logging
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
        from core.database import get_db_session
        from core.episode_segmentation_service import EpisodeSegmentationService

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


def trigger_episode_creation(
    session_id: str,
    agent_id: str,
    title: Optional[str] = None,
    user_id: Optional[str] = None,
    workspace_id: Optional[str] = None,
):
    """
    Non-blocking trigger for episode creation.

    Call this after agent execution completes. Safe from both async callers
    (schedules on the running loop) and sync callers (runs the coroutine to
    completion via ``asyncio.run``) — never raises.

    ``user_id``/``workspace_id`` are accepted for call-site compatibility
    (``core/agent_execution_service`` passes them); the segmentation service
    derives identity from the session.
    """
    coro = _create_episode_after_execution(session_id, agent_id, title)
    try:
        asyncio.create_task(coro)
    except RuntimeError:
        # No running loop (sync caller) — run inline so the episode is still
        # created rather than silently dropped.
        try:
            asyncio.run(coro)
        except Exception as e:  # pragma: no cover - defensive
            logger.error(f"Failed to create episode: {e}")
