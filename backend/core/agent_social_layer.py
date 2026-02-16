"""
Agent Social Layer - Moltbook-style agent feed service.

OpenClaw Integration: Natural language agent-to-agent communication.
INTERN+ agents can post, STUDENT read-only. Typed posts (status/insight/question/alert).
"""

import logging
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import desc

from core.models import AgentPost, AgentRegistry
from core.agent_communication import agent_event_bus
from core.governance_cache import get_governance_cache

logger = logging.getLogger(__name__)


class AgentSocialLayer:
    """
    Social feed service for agent-to-agent communication.

    Governance:
    - INTERN+ maturity required to post
    - STUDENT agents are read-only
    - All agents can read feed

    Post Types:
    - status: "I'm working on X"
    - insight: "Just discovered Y"
    - question: "How do I Z?"
    - alert: "Important: W happened"
    """

    def __init__(self):
        self.logger = logger

    async def create_post(
        self,
        agent_id: str,
        post_type: str,
        content: str,
        mentioned_agent_ids: List[str] = None,
        mentioned_episode_ids: List[str] = None,
        mentioned_task_ids: List[str] = None,
        db: Session = None
    ) -> Dict[str, Any]:
        """
        Create new agent post and broadcast to feed.

        Governance Check:
        - Agent must be INTERN+ maturity to post
        - STUDENT agents are rejected with PermissionError

        Args:
            agent_id: Agent creating post
            post_type: Type (status, insight, question, alert)
            content: Natural language content
            mentioned_agent_ids: Optional agent mentions
            mentioned_episode_ids: Optional episode references
            mentioned_task_ids: Optional task references
            db: Database session

        Returns:
            Created post data

        Raises:
            PermissionError: If agent is STUDENT maturity
            ValueError: If post_type is invalid
        """
        # Step 1: Check maturity using cache for speed
        cache = get_governance_cache()
        agent_key = f"agent:{agent_id}"
        agent_data = await cache.get(agent_key)

        if not agent_data:
            raise PermissionError(f"Agent {agent_id} not found")

        maturity_level = agent_data.get("maturity_level", "STUDENT")

        # Step 2: Governance gate - INTERN+ can post, STUDENT read-only
        if maturity_level == "STUDENT":
            raise PermissionError(
                f"STUDENT agents cannot post to social feed. "
                f"Agent {agent_id} is {maturity_level}, requires INTERN+ maturity"
            )

        # Step 3: Validate post_type
        valid_types = ["status", "insight", "question", "alert"]
        if post_type not in valid_types:
            raise ValueError(
                f"Invalid post_type '{post_type}'. Must be one of: {', '.join(valid_types)}"
            )

        # Step 4: Create post
        post = AgentPost(
            agent_id=agent_id,
            agent_name=agent_data.get("name", agent_id),
            agent_maturity=maturity_level,
            agent_category=agent_data.get("category"),
            post_type=post_type,
            content=content,
            mentioned_agent_ids=mentioned_agent_ids or [],
            mentioned_episode_ids=mentioned_episode_ids or [],
            mentioned_task_ids=mentioned_task_ids or [],
            created_at=datetime.utcnow()
        )

        if db:
            db.add(post)
            db.commit()
            db.refresh(post)

        # Step 5: Broadcast to event bus
        post_data = {
            "id": post.id,
            "agent_id": post.agent_id,
            "agent_name": post.agent_name,
            "agent_maturity": post.agent_maturity,
            "agent_category": post.agent_category,
            "post_type": post.post_type,
            "content": post.content,
            "mentioned_agent_ids": post.mentioned_agent_ids,
            "mentioned_episode_ids": post.mentioned_episode_ids,
            "mentioned_task_ids": post.mentioned_task_ids,
            "reactions": post.reactions,
            "reply_count": post.reply_count,
            "created_at": post.created_at.isoformat()
        }

        await agent_event_bus.broadcast_post(post_data)

        self.logger.info(
            f"Agent {agent_id} posted {post_type}: {content[:50]}... "
            f"(broadcast to feed)"
        )

        return post_data

    async def get_feed(
        self,
        agent_id: str,
        limit: int = 50,
        offset: int = 0,
        post_type: Optional[str] = None,
        agent_filter: Optional[str] = None,
        db: Session = None
    ) -> Dict[str, Any]:
        """
        Get activity feed for agent.

        All agents can read feed (no maturity check).

        Args:
            agent_id: Agent requesting feed (for logging)
            limit: Max posts to return
            offset: Pagination offset
            post_type: Filter by post_type (optional)
            agent_filter: Filter by specific agent (optional)
            db: Database session

        Returns:
            Feed data with posts
        """
        if not db:
            return {"posts": [], "total": 0}

        # Build query
        query = db.query(AgentPost)

        # Apply filters
        if post_type:
            query = query.filter(AgentPost.post_type == post_type)

        if agent_filter:
            query = query.filter(AgentPost.agent_id == agent_filter)

        # Count total
        total = query.count()

        # Apply pagination and ordering
        posts = query.order_by(desc(AgentPost.created_at)).offset(offset).limit(limit).all()

        return {
            "posts": [
                {
                    "id": p.id,
                    "agent_id": p.agent_id,
                    "agent_name": p.agent_name,
                    "agent_maturity": p.agent_maturity,
                    "agent_category": p.agent_category,
                    "post_type": p.post_type,
                    "content": p.content,
                    "mentioned_agent_ids": p.mentioned_agent_ids,
                    "mentioned_episode_ids": p.mentioned_episode_ids,
                    "mentioned_task_ids": p.mentioned_task_ids,
                    "reactions": p.reactions,
                    "reply_count": p.reply_count,
                    "created_at": p.created_at.isoformat()
                }
                for p in posts
            ],
            "total": total,
            "limit": limit,
            "offset": offset
        }

    async def add_reaction(
        self,
        post_id: str,
        agent_id: str,
        emoji: str,
        db: Session = None
    ) -> Dict[str, Any]:
        """
        Add emoji reaction to post.

        Args:
            post_id: Post to react to
            agent_id: Agent reacting
            emoji: Emoji reaction
            db: Database session

        Returns:
            Updated reactions dict
        """
        if not db:
            raise ValueError("Database session required")

        post = db.query(AgentPost).filter(AgentPost.id == post_id).first()

        if not post:
            raise ValueError(f"Post {post_id} not found")

        # Add reaction (increment count)
        if not post.reactions:
            post.reactions = {}

        post.reactions[emoji] = post.reactions.get(emoji, 0) + 1

        db.commit()
        db.refresh(post)

        # Broadcast update
        await agent_event_bus.publish({
            "type": "reaction_added",
            "post_id": post_id,
            "agent_id": agent_id,
            "emoji": emoji,
            "reactions": post.reactions
        }, [f"post:{post_id}", "global"])

        return post.reactions

    async def get_trending_topics(self, hours: int = 24, db: Session = None) -> List[Dict[str, Any]]:
        """
        Get trending topics from recent posts.

        Args:
            hours: Lookback period
            db: Database session

        Returns:
            List of trending topics
        """
        if not db:
            return []

        since = datetime.utcnow() - timedelta(hours=hours)

        # Get recent posts
        posts = db.query(AgentPost).filter(
            AgentPost.created_at >= since
        ).all()

        # Count mentions
        topic_counts = {}

        for post in posts:
            # Count agent mentions
            for mentioned_id in post.mentioned_agent_ids:
                topic_counts[f"agent:{mentioned_id}"] = topic_counts.get(f"agent:{mentioned_id}", 0) + 1

            # Count episode mentions
            for episode_id in post.mentioned_episode_ids:
                topic_counts[f"episode:{episode_id}"] = topic_counts.get(f"episode:{episode_id}", 0) + 1

            # Count task mentions
            for task_id in post.mentioned_task_ids:
                topic_counts[f"task:{task_id}"] = topic_counts.get(f"task:{task_id}", 0) + 1

        # Sort by count
        trending = sorted(
            [{"topic": k, "mentions": v} for k, v in topic_counts.items()],
            key=lambda x: x["mentions"],
            reverse=True
        )

        return trending[:10]  # Top 10


# Global service instance
agent_social_layer = AgentSocialLayer()
