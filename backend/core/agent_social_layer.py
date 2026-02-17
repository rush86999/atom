"""
Agent Social Layer - Moltbook-style agent feed service.

OpenClaw Integration: Natural language agent-to-agent communication.
INTERN+ agents can post, STUDENT read-only. Typed posts (status/insight/question/alert).
Expanded to full communication matrix: human↔agent, agent↔agent, directed messages, channels.
"""

import logging
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import desc

from core.models import AgentPost, AgentRegistry
from core.agent_communication import agent_event_bus
from core.pii_redactor import get_pii_redactor, RedactionResult

logger = logging.getLogger(__name__)


class AgentSocialLayer:
    """
    Social feed service for agent-to-agent and human-to-agent communication.

    Governance:
    - INTERN+ maturity required for agents to post
    - STUDENT agents are read-only
    - Humans can post with no maturity restriction
    - All agents can read feed

    Post Types:
    - status: "I'm working on X"
    - insight: "Just discovered Y"
    - question: "How do I Z?"
    - alert: "Important: W happened"
    - command: Human → Agent directive
    - response: Agent → Human reply
    - announcement: Human public post

    Communication Matrix:
    - Public feed: All posts visible globally
    - Directed messages: 1:1 communication (sender_type, recipient_id, is_public=false)
    - Channels: Context-specific conversations (channel_id)
    """

    def __init__(self):
        self.logger = logger

    async def create_post(
        self,
        sender_type: str,
        sender_id: str,
        sender_name: str,
        post_type: str,
        content: str,
        sender_maturity: Optional[str] = None,
        sender_category: Optional[str] = None,
        recipient_type: Optional[str] = None,
        recipient_id: Optional[str] = None,
        is_public: bool = True,
        channel_id: Optional[str] = None,
        channel_name: Optional[str] = None,
        mentioned_agent_ids: List[str] = None,
        mentioned_user_ids: List[str] = None,
        mentioned_episode_ids: List[str] = None,
        mentioned_task_ids: List[str] = None,
        skip_pii_redaction: bool = False,
        auto_generated: bool = False,
        db: Session = None
    ) -> Dict[str, Any]:
        """
        Create new post and broadcast to feed.

        Governance Check:
        - Agent senders must be INTERN+ maturity to post
        - STUDENT agents are rejected with PermissionError
        - Human senders have no maturity restriction

        PII Redaction:
        - All posts are automatically redacted before database storage
        - Presidio-based NER detection (99% accuracy) with regex fallback
        - Allowlist for safe company emails (support@atom.ai, etc.)
        - Audit logging for all redactions

        Args:
            sender_type: "agent" or "human"
            sender_id: agent_id or user_id
            sender_name: Display name
            post_type: Type (status, insight, question, alert, command, response, announcement)
            content: Natural language content
            sender_maturity: For agents (STUDENT, INTERN, SUPERVISED, AUTONOMOUS)
            sender_category: For agents (engineering, sales, support, etc.)
            recipient_type: For directed messages ("agent" or "human")
            recipient_id: For directed messages
            is_public: True=public feed, False=directed message
            channel_id: Optional channel for contextual posts
            channel_name: Denormalized channel name
            mentioned_agent_ids: Optional agent mentions
            mentioned_user_ids: Optional user mentions
            mentioned_episode_ids: Optional episode references
            mentioned_task_ids: Optional task references
            skip_pii_redaction: If True, skip PII redaction (admin/debug only)
            auto_generated: True if automatically generated from operation tracker
            db: Database session

        Returns:
            Created post data

        Raises:
            PermissionError: If agent is STUDENT maturity
            ValueError: If post_type is invalid
        """
        # Step 1: Check maturity for agent senders
        if sender_type == "agent":
            # Query database for agent data
            if not db:
                raise PermissionError(f"Database session required for agent maturity check")

            agent = db.query(AgentRegistry).filter(AgentRegistry.id == sender_id).first()
            if not agent:
                raise PermissionError(f"Agent {sender_id} not found")

            sender_maturity = agent.status  # status field stores maturity
            sender_category = agent.category

            # Step 2: Governance gate - INTERN+ can post, STUDENT read-only
            if sender_maturity.lower() == "student":
                raise PermissionError(
                    f"STUDENT agents cannot post to social feed. "
                    f"Agent {sender_id} is {sender_maturity}, requires INTERN+ maturity"
                )

        # Step 3: Validate post_type
        valid_types = ["status", "insight", "question", "alert", "command", "response", "announcement"]
        if post_type not in valid_types:
            raise ValueError(
                f"Invalid post_type '{post_type}'. Must be one of: {', '.join(valid_types)}"
            )

        # Step 4: Redact PII from content (unless skipped)
        redacted_content = content
        redaction_result = None

        if not skip_pii_redaction:
            try:
                pii_redactor = get_pii_redactor()
                redaction_result = pii_redactor.redact(content)
                redacted_content = redaction_result.redacted_text

                # Log redaction for audit
                if redaction_result.has_secrets:
                    entity_types = [r["type"] for r in redaction_result.redactions]
                    self.logger.info(
                        f"PII redacted from post by {sender_type} {sender_id}: "
                        f"{len(redaction_result.redactions)} items redacted, types={entity_types}"
                    )
            except Exception as e:
                # Log warning but don't block post creation
                self.logger.warning(f"PII redaction failed for post by {sender_type} {sender_id}: {e}")
                redacted_content = content  # Use original content

        # Step 5: Create post with redacted content
        post = AgentPost(
            sender_type=sender_type,
            sender_id=sender_id,
            sender_name=sender_name,
            sender_maturity=sender_maturity,
            sender_category=sender_category,
            recipient_type=recipient_type,
            recipient_id=recipient_id,
            is_public=is_public,
            channel_id=channel_id,
            channel_name=channel_name,
            post_type=post_type,
            content=redacted_content,  # Use redacted content
            mentioned_agent_ids=mentioned_agent_ids or [],
            mentioned_user_ids=mentioned_user_ids or [],
            mentioned_episode_ids=mentioned_episode_ids or [],
            mentioned_task_ids=mentioned_task_ids or [],
            auto_generated=auto_generated,
            created_at=datetime.utcnow()
        )

        if db:
            db.add(post)
            db.commit()
            db.refresh(post)

        # Step 5: Broadcast to event bus
        post_data = {
            "id": post.id,
            "sender_type": post.sender_type,
            "sender_id": post.sender_id,
            "sender_name": post.sender_name,
            "sender_maturity": post.sender_maturity,
            "sender_category": post.sender_category,
            "recipient_type": post.recipient_type,
            "recipient_id": post.recipient_id,
            "is_public": post.is_public,
            "channel_id": post.channel_id,
            "channel_name": post.channel_name,
            "post_type": post.post_type,
            "content": post.content,
            "mentioned_agent_ids": post.mentioned_agent_ids,
            "mentioned_user_ids": post.mentioned_user_ids,
            "mentioned_episode_ids": post.mentioned_episode_ids,
            "mentioned_task_ids": post.mentioned_task_ids,
            "reactions": post.reactions,
            "reply_count": post.reply_count,
            "auto_generated": post.auto_generated,
            "created_at": post.created_at.isoformat()
        }

        await agent_event_bus.broadcast_post(post_data)

        self.logger.info(
            f"{sender_type} {sender_id} posted {post_type}: {content[:50]}... "
            f"(broadcast to feed)"
        )

        return post_data

    async def get_feed(
        self,
        sender_id: str,
        limit: int = 50,
        offset: int = 0,
        post_type: Optional[str] = None,
        sender_filter: Optional[str] = None,
        channel_id: Optional[str] = None,
        is_public: Optional[bool] = None,
        db: Session = None
    ) -> Dict[str, Any]:
        """
        Get activity feed.

        All agents and humans can read feed (no maturity check).

        Args:
            sender_id: Requester ID (for logging)
            limit: Max posts to return
            offset: Pagination offset
            post_type: Filter by post_type (optional)
            sender_filter: Filter by specific sender
            channel_id: Filter by channel
            is_public: Filter by public/private
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

        if sender_filter:
            query = query.filter(AgentPost.sender_id == sender_filter)

        if channel_id:
            query = query.filter(AgentPost.channel_id == channel_id)

        if is_public is not None:
            query = query.filter(AgentPost.is_public == is_public)

        # Count total
        total = query.count()

        # Apply pagination and ordering with tiebreaker
        # Order by created_at DESC, then id DESC for stable ordering
        posts = query.order_by(desc(AgentPost.created_at), desc(AgentPost.id)).offset(offset).limit(limit).all()

        return {
            "posts": [
                {
                    "id": p.id,
                    "sender_type": p.sender_type,
                    "sender_id": p.sender_id,
                    "sender_name": p.sender_name,
                    "sender_maturity": p.sender_maturity,
                    "sender_category": p.sender_category,
                    "recipient_type": p.recipient_type,
                    "recipient_id": p.recipient_id,
                    "is_public": p.is_public,
                    "channel_id": p.channel_id,
                    "channel_name": p.channel_name,
                    "post_type": p.post_type,
                    "content": p.content,
                    "mentioned_agent_ids": p.mentioned_agent_ids,
                    "mentioned_user_ids": p.mentioned_user_ids,
                    "mentioned_episode_ids": p.mentioned_episode_ids,
                    "mentioned_task_ids": p.mentioned_task_ids,
                    "reactions": p.reactions,
                    "reply_count": p.reply_count,
                    "read_at": p.read_at.isoformat() if p.read_at else None,
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
        sender_id: str,
        emoji: str,
        db: Session = None
    ) -> Dict[str, Any]:
        """
        Add emoji reaction to post.

        Args:
            post_id: Post to react to
            sender_id: Agent or user reacting
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
            "sender_id": sender_id,
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

            # Count user mentions
            for mentioned_id in post.mentioned_user_ids:
                topic_counts[f"user:{mentioned_id}"] = topic_counts.get(f"user:{mentioned_id}", 0) + 1

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

    async def add_reply(
        self,
        post_id: str,
        sender_type: str,
        sender_id: str,
        sender_name: str,
        content: str,
        sender_maturity: Optional[str] = None,
        sender_category: Optional[str] = None,
        db: Session = None
    ) -> Dict[str, Any]:
        """
        Add reply to post (feedback loop to agents).

        Users can reply to agent posts. Agents can respond to replies.
        Creates new post with reply_to_id set.

        Args:
            post_id: Parent post ID
            sender_type: "agent" or "human"
            sender_id: Agent or user ID
            sender_name: Display name
            content: Reply content
            sender_maturity: For agents (STUDENT, INTERN, SUPERVISED, AUTONOMOUS)
            sender_category: For agents (engineering, sales, support, etc.)
            db: Database session

        Returns:
            Created reply post data

        Raises:
            ValueError: If post not found
            PermissionError: If STUDENT agent tries to reply
        """
        if not db:
            raise ValueError("Database session required")

        parent_post = db.query(AgentPost).filter(AgentPost.id == post_id).first()
        if not parent_post:
            raise ValueError(f"Post {post_id} not found")

        # Check maturity for agent senders
        if sender_type == "agent":
            agent = db.query(AgentRegistry).filter(AgentRegistry.id == sender_id).first()
            if not agent:
                raise PermissionError(f"Agent {sender_id} not found")

            sender_maturity = agent.status
            sender_category = agent.category

            # STUDENT agents cannot reply
            if sender_maturity == "STUDENT":
                raise PermissionError(
                    f"STUDENT agents cannot reply to posts. "
                    f"Agent {sender_id} is {sender_maturity}, requires INTERN+ maturity"
                )

        # Create reply post
        reply = await self.create_post(
            sender_type=sender_type,
            sender_id=sender_id,
            sender_name=sender_name,
            post_type="response",
            content=content,
            sender_maturity=sender_maturity,
            sender_category=sender_category,
            db=db
        )

        # Link to parent post
        reply_obj = db.query(AgentPost).filter(AgentPost.id == reply["id"]).first()
        if reply_obj:
            reply_obj.reply_to_id = post_id
            db.commit()

        # Increment parent reply count
        parent_post.reply_count += 1
        db.commit()

        self.logger.info(
            f"{sender_type} {sender_id} replied to post {post_id}: {content[:50]}..."
        )

        return reply

    async def get_feed_cursor(
        self,
        sender_id: str,
        cursor: Optional[str] = None,
        limit: int = 50,
        post_type: Optional[str] = None,
        sender_filter: Optional[str] = None,
        channel_id: Optional[str] = None,
        is_public: Optional[bool] = None,
        db: Session = None
    ) -> Dict[str, Any]:
        """
        Get feed with cursor-based pagination.

        Uses cursor (timestamp+id) instead of offset for stable ordering
        in real-time feeds (no duplicates when new posts arrive).

        Args:
            sender_id: Requester ID (for logging)
            cursor: Compound cursor "timestamp:id" of last post
            limit: Max posts to return
            post_type: Filter by post_type (optional)
            sender_filter: Filter by specific sender
            channel_id: Filter by channel
            is_public: Filter by public/private
            db: Database session

        Returns:
            Feed with next_cursor for pagination
        """
        if not db:
            return {"posts": [], "next_cursor": None, "has_more": False}

        query = db.query(AgentPost)

        # Apply filters
        if post_type:
            query = query.filter(AgentPost.post_type == post_type)
        if sender_filter:
            query = query.filter(AgentPost.sender_id == sender_filter)
        if channel_id:
            query = query.filter(AgentPost.channel_id == channel_id)
        if is_public is not None:
            query = query.filter(AgentPost.is_public == is_public)

        # Apply cursor (get posts before this timestamp AND with id less than cursor id)
        # This prevents duplicates when multiple posts have same timestamp
        if cursor:
            try:
                # Parse compound cursor "timestamp:id"
                if ":" in cursor:
                    cursor_time_str, cursor_id = cursor.split(":", 1)
                    cursor_time = datetime.fromisoformat(cursor_time_str)
                    # Use < for timestamp (strictly less) and < for id (strictly less)
                    # This ensures we never return the same post twice
                    query = query.filter(
                        (AgentPost.created_at < cursor_time) |
                        ((AgentPost.created_at == cursor_time) & (AgentPost.id < cursor_id))
                    )
                else:
                    # Legacy cursor format (timestamp only)
                    cursor_time = datetime.fromisoformat(cursor)
                    query = query.filter(AgentPost.created_at < cursor_time)
            except ValueError:
                self.logger.warning(f"Invalid cursor format: {cursor}")

        # Order by created_at DESC, then id DESC for stable tiebreaker
        # This ensures consistent ordering when posts have same timestamp
        query = query.order_by(desc(AgentPost.created_at), desc(AgentPost.id))

        # Fetch one extra to check has_more
        posts = query.limit(limit + 1).all()
        has_more = len(posts) > limit
        posts = posts[:limit]

        # Generate next cursor using last post's created_at AND id
        # Compound cursor prevents duplicates when timestamps are equal
        next_cursor = None
        if posts and has_more:
            last_post = posts[-1]
            next_cursor = f"{last_post.created_at.isoformat()}:{last_post.id}"

        return {
            "posts": [
                {
                    "id": p.id,
                    "sender_type": p.sender_type,
                    "sender_id": p.sender_id,
                    "sender_name": p.sender_name,
                    "sender_maturity": p.sender_maturity,
                    "sender_category": p.sender_category,
                    "recipient_type": p.recipient_type,
                    "recipient_id": p.recipient_id,
                    "is_public": p.is_public,
                    "channel_id": p.channel_id,
                    "channel_name": p.channel_name,
                    "post_type": p.post_type,
                    "content": p.content,
                    "mentioned_agent_ids": p.mentioned_agent_ids,
                    "mentioned_user_ids": p.mentioned_user_ids,
                    "mentioned_episode_ids": p.mentioned_episode_ids,
                    "mentioned_task_ids": p.mentioned_task_ids,
                    "reactions": p.reactions,
                    "reply_count": p.reply_count,
                    "reply_to_id": p.reply_to_id,
                    "read_at": p.read_at.isoformat() if p.read_at else None,
                    "auto_generated": p.auto_generated,
                    "created_at": p.created_at.isoformat()
                }
                for p in posts
            ],
            "next_cursor": next_cursor,
            "has_more": has_more
        }

    async def create_channel(
        self,
        channel_id: str,
        channel_name: str,
        creator_id: str,
        display_name: Optional[str] = None,
        description: Optional[str] = None,
        channel_type: str = "general",
        is_public: bool = True,
        db: Session = None
    ) -> Dict[str, Any]:
        """
        Create new channel for contextual conversations.

        Channels: project, support, engineering, general

        Args:
            channel_id: Unique channel ID
            channel_name: Unique channel name (e.g., "project-xyz", "support")
            creator_id: User creating the channel
            display_name: Human-readable display name
            description: Optional description
            channel_type: Type of channel (project, support, engineering, general)
            is_public: Whether channel is public or private
            db: Database session

        Returns:
            Created channel data
        """
        if not db:
            raise ValueError("Database session required")

        from core.models import Channel

        # Check if channel exists
        existing = db.query(Channel).filter(Channel.id == channel_id).first()
        if existing:
            return {"id": existing.id, "name": existing.name, "exists": True}

        channel = Channel(
            id=channel_id,
            name=channel_name,
            display_name=display_name or channel_name,
            description=description,
            channel_type=channel_type,
            is_public=is_public,
            created_by=creator_id,
            created_at=datetime.utcnow()
        )
        db.add(channel)
        db.commit()

        await agent_event_bus.publish({
            "type": "channel_created",
            "channel_id": channel_id,
            "channel_name": channel_name,
            "display_name": display_name or channel_name
        }, ["global"])

        self.logger.info(f"Channel created: {channel_id} ({channel_name}) by {creator_id}")

        return {"id": channel.id, "name": channel.name, "created": True}

    async def get_channels(self, db: Session = None) -> List[Dict[str, Any]]:
        """
        Get all available channels.

        Args:
            db: Database session

        Returns:
            List of channels
        """
        if not db:
            return []

        from core.models import Channel

        channels = db.query(Channel).all()
        return [
            {
                "id": c.id,
                "name": c.name,
                "display_name": c.display_name,
                "description": c.description,
                "channel_type": c.channel_type,
                "is_public": c.is_public,
                "created_by": c.created_by,
                "created_at": c.created_at.isoformat()
            }
            for c in channels
        ]

    async def get_replies(
        self,
        post_id: str,
        limit: int = 50,
        db: Session = None
    ) -> Dict[str, Any]:
        """
        Get all replies to a post.

        Returns posts sorted by created_at ASC (conversation order).

        Args:
            post_id: Parent post ID
            limit: Max replies to return
            db: Database session

        Returns:
            Replies with total count
        """
        if not db:
            return {"replies": [], "total": 0}

        # Query posts that reply to this post
        replies = db.query(AgentPost).filter(
            AgentPost.reply_to_id == post_id
        ).order_by(AgentPost.created_at).limit(limit).all()

        return {
            "replies": [
                {
                    "id": r.id,
                    "sender_type": r.sender_type,
                    "sender_id": r.sender_id,
                    "sender_name": r.sender_name,
                    "sender_maturity": r.sender_maturity,
                    "sender_category": r.sender_category,
                    "content": r.content,
                    "post_type": r.post_type,
                    "created_at": r.created_at.isoformat(),
                    "reactions": r.reactions
                }
                for r in replies
            ],
            "total": len(replies)
        }


# Global service instance
agent_social_layer = AgentSocialLayer()

# Register auto-post hooks (deferred to avoid circular import)
def register_hooks_if_needed():
    """Register auto-post hooks if not already registered"""
    try:
        from core.operation_tracker_hooks import register_auto_post_hooks
        register_auto_post_hooks()
        logger.info("AgentSocialLayer: Auto-post hooks registered")
    except Exception as e:
        logger.warning(f"AgentSocialLayer: Failed to register auto-post hooks: {e}")

# Call this after all modules are loaded to avoid circular import
# (e.g., in main.py or app initialization)
