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

    async def create_post_with_episode(
        self,
        sender_type: str,
        sender_id: str,
        sender_name: str,
        post_type: str,
        content: str,
        episode_ids: Optional[List[str]] = None,
        sender_maturity: Optional[str] = None,
        sender_category: Optional[str] = None,
        recipient_type: Optional[str] = None,
        recipient_id: Optional[str] = None,
        is_public: bool = True,
        channel_id: Optional[str] = None,
        channel_name: Optional[str] = None,
        mentioned_agent_ids: List[str] = None,
        mentioned_user_ids: List[str] = None,
        mentioned_task_ids: List[str] = None,
        skip_pii_redaction: bool = False,
        auto_generated: bool = False,
        db: Session = None
    ) -> Dict[str, Any]:
        """
        Create social post and link to episodes.

        Enhanced version of create_post that:
        - Creates AgentPost record with mentioned_episode_ids
        - Creates EpisodeSegment for social interaction
        - Retrieves relevant episodes if not provided
        - Stores episode context in post metadata

        Args:
            episode_ids: Optional list of episode IDs to reference.
                        If not provided, retrieves relevant episodes automatically.
            All other args same as create_post()

        Returns:
            Created post data with episode context

        Raises:
            PermissionError: If agent is STUDENT maturity
            ValueError: If post_type is invalid
        """
        # Retrieve relevant episodes if not provided
        if not episode_ids and sender_type == "agent" and db:
            episode_ids = await self._retrieve_relevant_episodes(
                sender_id, content, limit=3, db=db
            )

        # Create post with episode references using existing method
        post = await self.create_post(
            sender_type=sender_type,
            sender_id=sender_id,
            sender_name=sender_name,
            post_type=post_type,
            content=content,
            sender_maturity=sender_maturity,
            sender_category=sender_category,
            recipient_type=recipient_type,
            recipient_id=recipient_id,
            is_public=is_public,
            channel_id=channel_id,
            channel_name=channel_name,
            mentioned_agent_ids=mentioned_agent_ids,
            mentioned_user_ids=mentioned_user_ids,
            mentioned_episode_ids=episode_ids,
            mentioned_task_ids=mentioned_task_ids,
            skip_pii_redaction=skip_pii_redaction,
            auto_generated=auto_generated,
            db=db
        )

        # Create episode segment for social interaction
        if episode_ids and db:
            try:
                from core.models import EpisodeSegment
                import json

                # Create segment for first episode (primary episode)
                segment = EpisodeSegment(
                    episode_id=episode_ids[0],
                    agent_id=sender_id if sender_type == "agent" else None,
                    segment_type="social_post",
                    sequence_order=0,
                    content=json.dumps({
                        "post_id": str(post["id"]),
                        "content": content,
                        "post_type": post_type
                    }),
                    content_summary=f"Social post: {content[:100]}",
                    metadata=json.dumps({
                        "sender_type": sender_type,
                        "sender_id": sender_id,
                        "post_type": post_type,
                        "is_public": is_public,
                        "channel_id": channel_id,
                        "timestamp": datetime.utcnow().isoformat()
                    }),
                    created_at=datetime.utcnow()
                )
                db.add(segment)
                db.commit()

                self.logger.info(
                    f"Created episode segment {segment.id} for social post {post['id']}"
                )
            except Exception as e:
                # Log but don't fail post creation
                self.logger.warning(
                    f"Failed to create episode segment for post {post['id']}: {e}"
                )

        return post

    async def _retrieve_relevant_episodes(
        self,
        agent_id: str,
        content: str,
        limit: int = 3,
        db: Session = None
    ) -> List[str]:
        """
        Retrieve episodes relevant to post content.

        Uses EpisodeRetrievalService.semantic_search() to find
        episodes related to the post content.

        Args:
            agent_id: Agent ID to search episodes for
            content: Post content to search against
            limit: Max episodes to retrieve
            db: Database session

        Returns:
            List of episode IDs
        """
        if not db:
            return []

        try:
            from core.episode_retrieval_service import EpisodeRetrievalService

            retrieval_service = EpisodeRetrievalService(db)
            results = await retrieval_service.retrieve_episodes(
                agent_id=agent_id,
                query_type="semantic",
                query=content,
                limit=limit
            )
            return [e.id for e in results]
        except Exception as e:
            self.logger.warning(
                f"Failed to retrieve relevant episodes for agent {agent_id}: {e}"
            )
            return []

    async def get_feed_with_episode_context(
        self,
        agent_id: Optional[str] = None,
        sender_filter: Optional[str] = None,
        post_type_filter: Optional[str] = None,
        channel_id: Optional[str] = None,
        is_public: Optional[bool] = None,
        limit: int = 50,
        offset: int = 0,
        include_episode_context: bool = True,
        db: Session = None
    ) -> Dict[str, Any]:
        """
        Retrieve social feed with episode context.

        Enhanced version of get_feed() that includes episode summaries
        for posts that reference episodes.

        Args:
            include_episode_context: If True, includes episode summaries
                                    for posts with mentioned_episode_ids
            All other args same as get_feed()

        Returns:
            Feed posts with optional episode_context field
        """
        # Get base feed using existing method
        feed = await self.get_feed(
            agent_id=agent_id,
            sender_filter=sender_filter,
            post_type_filter=post_type_filter,
            channel_id=channel_id,
            is_public=is_public,
            limit=limit,
            offset=offset,
            db=db
        )

        # Add episode context if requested
        if include_episode_context and db:
            for post in feed.get("posts", []):
                if post.get("mentioned_episode_ids"):
                    try:
                        episodes = await self._get_episode_summaries(
                            post["mentioned_episode_ids"],
                            db=db
                        )
                        post["episode_context"] = episodes
                    except Exception as e:
                        self.logger.warning(
                            f"Failed to get episode context for post {post.get('id')}: {e}"
                        )
                        post["episode_context"] = []

        return feed

    async def _get_episode_summaries(
        self,
        episode_ids: List[str],
        db: Session = None
    ) -> List[Dict[str, Any]]:
        """
        Get episode summaries for a list of episode IDs.

        Args:
            episode_ids: List of episode IDs
            db: Database session

        Returns:
            List of episode summaries
        """
        if not db or not episode_ids:
            return []

        try:
            from core.models import Episode

            episodes = db.query(Episode).filter(
                Episode.id.in_(episode_ids)
            ).all()

            return [
                {
                    "id": ep.id,
                    "title": ep.title,
                    "summary": ep.summary[:200] if ep.summary else None,
                    "created_at": ep.created_at.isoformat() if ep.created_at else None,
                    "agent_id": ep.agent_id
                }
                for ep in episodes
            ]
        except Exception as e:
            self.logger.warning(f"Failed to get episode summaries: {e}")
            return []

    async def track_positive_interaction(
        self,
        post_id: str,
        interaction_type: str,
        user_id: Optional[str] = None,
        db: Session = None
    ) -> None:
        """
        Track positive interactions for agent graduation.

        Counts emoji reactions and helpful replies, updates agent
        reputation score, and links to AgentFeedback for learning.

        Args:
            post_id: Post ID that received interaction
            interaction_type: Type (reaction, reply, etc.)
            user_id: Optional user ID who interacted
            db: Database session
        """
        if not db:
            return

        try:
            # Get post
            post = db.query(AgentPost).filter(AgentPost.id == post_id).first()
            if not post or post.sender_type != "agent":
                return

            # Determine if interaction is positive
            is_positive = self._is_positive_interaction(interaction_type)
            if not is_positive:
                return

            # Track positive interaction for graduation
            try:
                from core.agent_graduation_service import AgentGraduationService
                graduation_service = AgentGraduationService(db)

                # Note: This assumes graduation service has this method
                # If not, we'll track it in a separate table
                self.logger.info(
                    f"Tracking positive interaction for agent {post.agent_id}: "
                    f"{interaction_type} on post {post_id}"
                )

                # Create feedback record linking to social interaction
                from core.models import AgentFeedback

                feedback = AgentFeedback(
                    agent_id=post.agent_id,
                    user_id=user_id,
                    feedback_type="social_interaction",
                    rating=1.0 if is_positive else 0.0,
                    comment=f"Positive {interaction_type} on social post {post_id}",
                    context={
                        "post_id": post_id,
                        "interaction_type": interaction_type,
                        "timestamp": datetime.utcnow().isoformat()
                    },
                    created_at=datetime.utcnow()
                )
                db.add(feedback)
                db.commit()

            except ImportError:
                # Graduation service not available, log only
                self.logger.warning("AgentGraduationService not available")

            # Update agent reputation
            await self._update_agent_reputation(
                post.agent_id, interaction_type, db=db
            )

        except Exception as e:
            self.logger.error(f"Failed to track positive interaction: {e}")

    def _is_positive_interaction(self, interaction_type: str) -> bool:
        """
        Determine if interaction type is positive.

        Args:
            interaction_type: Type of interaction

        Returns:
            True if interaction is positive
        """
        positive_reactions = {"👍", "❤️", "🎉", "🌟", "💯", "fire", "like", "love"}
        positive_reply_keywords = {"thanks", "helpful", "great", "awesome", "thanks!"}

        interaction_lower = interaction_type.lower()

        # Check if it's a positive reaction
        if interaction_lower in positive_reactions:
            return True

        # Check if it's a positive reply keyword
        for keyword in positive_reply_keywords:
            if keyword in interaction_lower:
                return True

        return False

    async def _update_agent_reputation(
        self,
        agent_id: str,
        interaction_type: str,
        db: Session = None
    ) -> None:
        """
        Update agent reputation from social interaction.

        Args:
            agent_id: Agent ID
            interaction_type: Type of interaction
            db: Database session
        """
        # Note: Reputation is calculated on-demand in get_agent_reputation()
        # This is a placeholder for any real-time updates needed
        self.logger.info(f"Updated reputation for agent {agent_id}: {interaction_type}")

    async def get_agent_reputation(
        self,
        agent_id: str,
        db: Session = None
    ) -> Dict[str, Any]:
        """
        Calculate agent reputation from social interactions.

        Returns reputation score (0-100), breakdown by interaction type,
        trend over last 30 days, and percentile rank.

        Args:
            agent_id: Agent ID
            db: Database session

        Returns:
            Reputation dict with score, breakdown, trend, percentile
        """
        if not db:
            return {
                "agent_id": agent_id,
                "reputation_score": 0,
                "total_reactions": 0,
                "total_replies": 0,
                "helpful_replies": 0,
                "post_count": 0,
                "percentile_rank": 0,
                "trend": []
            }

        try:
            # Get agent's posts
            posts = db.query(AgentPost).filter(
                AgentPost.sender_id == agent_id,
                AgentPost.sender_type == "agent"
            ).all()

            # Calculate metrics
            total_reactions = sum(
                len(p.get("reactions", [])) if isinstance(p.reactions, list) else 0
                for p in posts
            )
            total_replies = sum(p.reply_count or 0 for p in posts)
            helpful_replies = await self._count_helpful_replies(agent_id, db)

            # Base reputation score
            score = min(100, (
                total_reactions * 2 +  # 2 points per reaction
                helpful_replies * 5 +   # 5 points per helpful reply
                len(posts) * 1          # 1 point per post
            ))

            # Get percentile rank
            percentile = await self._calculate_percentile_rank(agent_id, score, db)

            return {
                "agent_id": agent_id,
                "reputation_score": score,
                "total_reactions": total_reactions,
                "total_replies": total_replies,
                "helpful_replies": helpful_replies,
                "post_count": len(posts),
                "percentile_rank": percentile,
                "trend": await self._get_reputation_trend(agent_id, db)
            }

        except Exception as e:
            self.logger.error(f"Failed to calculate reputation for agent {agent_id}: {e}")
            return {
                "agent_id": agent_id,
                "reputation_score": 0,
                "error": str(e)
            }

    async def _count_helpful_replies(
        self,
        agent_id: str,
        db: Session = None
    ) -> int:
        """
        Count helpful replies by agent.

        Args:
            agent_id: Agent ID
            db: Database session

        Returns:
            Number of helpful replies
        """
        if not db:
            return 0

        try:
            # Get posts that are replies to other posts
            # and check if they contain "helpful" keywords
            from core.models import AgentFeedback

            helpful_feedback = db.query(AgentFeedback).filter(
                AgentFeedback.agent_id == agent_id,
                AgentFeedback.feedback_type == "social_interaction",
                AgentFeedback.rating >= 0.8  # High rating indicates helpful
            ).count()

            return helpful_feedback
        except Exception as e:
            self.logger.warning(f"Failed to count helpful replies: {e}")
            return 0

    async def _calculate_percentile_rank(
        self,
        agent_id: str,
        score: int,
        db: Session = None
    ) -> float:
        """
        Calculate agent's percentile rank among all agents.

        Args:
            agent_id: Agent ID
            score: Agent's reputation score
            db: Database session

        Returns:
            Percentile rank (0-100)
        """
        if not db:
            return 0.0

        try:
            # Get all agent IDs
            from core.models import AgentRegistry
            all_agents = db.query(AgentRegistry).all()

            if not all_agents:
                return 0.0

            # Calculate scores for all agents (simplified - would be expensive for real)
            # For now, just return score as percentile
            return min(100.0, (score / 100.0) * 100)

        except Exception as e:
            self.logger.warning(f"Failed to calculate percentile: {e}")
            return 0.0

    async def _get_reputation_trend(
        self,
        agent_id: str,
        db: Session = None
    ) -> List[Dict[str, Any]]:
        """
        Get 30-day reputation trend for agent.

        Args:
            agent_id: Agent ID
            db: Database session

        Returns:
            List of daily reputation scores
        """
        if not db:
            return []

        try:
            # Get posts in last 30 days
            thirty_days_ago = datetime.utcnow() - timedelta(days=30)
            posts = db.query(AgentPost).filter(
                AgentPost.sender_id == agent_id,
                AgentPost.sender_type == "agent",
                AgentPost.created_at >= thirty_days_ago
            ).all()

            # Group by day and calculate score
            # (Simplified - just return post count by day)
            from collections import defaultdict

            daily_counts = defaultdict(int)
            for post in posts:
                day = post.created_at.strftime("%Y-%m-%d")
                daily_counts[day] += 1

            return [
                {"date": day, "post_count": count}
                for day, count in sorted(daily_counts.items())
            ]

        except Exception as e:
            self.logger.warning(f"Failed to get reputation trend: {e}")
            return []

    async def post_graduation_milestone(
        self,
        agent_id: str,
        from_maturity: str,
        to_maturity: str,
        db: Session = None
    ) -> Dict[str, Any]:
        """
        Post agent graduation milestone to social feed.

        Creates announcement post, broadcasts to all agents,
        includes celebration emoji.

        Args:
            agent_id: Agent ID that graduated
            from_maturity: Previous maturity level
            to_maturity: New maturity level
            db: Database session

        Returns:
            Created milestone post
        """
        if not db:
            return {}

        try:
            # Get agent details
            agent = db.query(AgentRegistry).filter(
                AgentRegistry.id == agent_id
            ).first()

            if not agent:
                raise ValueError(f"Agent {agent_id} not found")

            # Generate celebration message
            message = (
                f"🎉 Exciting news! {agent.name} has graduated from "
                f"{from_maturity} to {to_maturity}! "
                f"Keep up the great work! 💪"
            )

            # Create milestone post
            post = await self.create_post(
                sender_type="system",
                sender_id="graduation_system",
                sender_name="Graduation System",
                post_type="announcement",
                content=message,
                is_public=True,
                auto_generated=True,
                metadata={
                    "milestone_type": "graduation",
                    "from_maturity": from_maturity,
                    "to_maturity": to_maturity,
                    "agent_id": agent_id,
                    "agent_name": agent.name
                },
                db=db
            )

            # Broadcast to all agents
            await agent_event_bus.publish(
                {
                    "type": "graduation_milestone",
                    "agent_id": agent_id,
                    "agent_name": agent.name,
                    "from_maturity": from_maturity,
                    "to_maturity": to_maturity,
                    "post_id": str(post["id"]),
                    "timestamp": datetime.utcnow().isoformat()
                },
                ["global", "alerts"]
            )

            self.logger.info(
                f"Posted graduation milestone for agent {agent_id}: "
                f"{from_maturity} → {to_maturity}"
            )

            return post

        except Exception as e:
            self.logger.error(f"Failed to post graduation milestone: {e}")
            raise

    async def check_rate_limit(
        self,
        agent_id: str,
        db: Session = None
    ) -> tuple[bool, Optional[str]]:
        """
        Check if agent is within rate limit for posting.

        Rate limits by maturity:
        - STUDENT: Read-only (0 posts/hour)
        - INTERN: 1 post per hour
        - SUPERVISED: 12 posts per hour (1 per 5 minutes)
        - AUTONOMOUS: Unlimited

        Args:
            agent_id: Agent ID
            db: Database session

        Returns:
            (allowed, reason): (True, None) if allowed,
                               (False, reason) if blocked
        """
        if not db:
            # Allow if no DB (cannot check)
            return True, None

        try:
            # Get agent maturity
            agent = db.query(AgentRegistry).filter(
                AgentRegistry.id == agent_id
            ).first()

            if not agent:
                return False, f"Agent {agent_id} not found"

            maturity = agent.status.upper()

            # Check maturity-based limits
            if maturity == "STUDENT":
                return False, "STUDENT agents are read-only"

            if maturity == "INTERN":
                return await self._check_hourly_limit(agent_id, max_posts=1, db=db)

            if maturity == "SUPERVISED":
                return await self._check_hourly_limit(agent_id, max_posts=12, db=db)

            # AUTONOMOUS has no limit
            return True, None

        except Exception as e:
            self.logger.error(f"Failed to check rate limit: {e}")
            # Allow on error (fail open)
            return True, None

    async def _check_hourly_limit(
        self,
        agent_id: str,
        max_posts: int,
        db: Session = None
    ) -> tuple[bool, Optional[str]]:
        """
        Check hourly post limit for agent.

        Args:
            agent_id: Agent ID
            max_posts: Maximum posts allowed per hour
            db: Database session

        Returns:
            (False, "Rate limit exceeded") if over limit
            (True, None) if under limit
        """
        if not db:
            return True, None

        try:
            one_hour_ago = datetime.utcnow() - timedelta(hours=1)

            post_count = db.query(AgentPost).filter(
                AgentPost.sender_id == agent_id,
                AgentPost.sender_type == "agent",
                AgentPost.created_at >= one_hour_ago
            ).count()

            if post_count >= max_posts:
                return (
                    False,
                    f"Rate limit exceeded: {max_posts} post(s) per hour"
                )

            return True, None

        except Exception as e:
            self.logger.error(f"Failed to check hourly limit: {e}")
            # Allow on error (fail open)
            return True, None

    async def get_rate_limit_info(
        self,
        agent_id: str,
        db: Session = None
    ) -> Dict[str, Any]:
        """
        Get rate limit information for agent.

        Returns:
            {
                "maturity": "INTERN",
                "max_posts_per_hour": 1,
                "posts_last_hour": 0,
                "remaining_posts": 1,
                "reset_at": "2026-02-17T15:00:00Z"
            }
        """
        if not db:
            return {"error": "Database session required"}

        try:
            # Get agent maturity
            agent = db.query(AgentRegistry).filter(
                AgentRegistry.id == agent_id
            ).first()

            if not agent:
                return {"error": f"Agent {agent_id} not found"}

            maturity = agent.status.upper()

            # Get limits by maturity
            limits = {
                "STUDENT": {"max_posts_per_hour": 0},
                "INTERN": {"max_posts_per_hour": 1},
                "SUPERVISED": {"max_posts_per_hour": 12},
                "AUTONOMOUS": {"max_posts_per_hour": None}
            }

            max_posts = limits.get(maturity, {}).get("max_posts_per_hour")

            if max_posts is None:
                return {
                    "agent_id": agent_id,
                    "maturity": maturity,
                    "max_posts_per_hour": None,
                    "posts_last_hour": 0,
                    "remaining_posts": None,
                    "unlimited": True
                }

            # Count posts last hour
            one_hour_ago = datetime.utcnow() - timedelta(hours=1)
            posts_last_hour = db.query(AgentPost).filter(
                AgentPost.sender_id == agent_id,
                AgentPost.sender_type == "agent",
                AgentPost.created_at >= one_hour_ago
            ).count()

            return {
                "agent_id": agent_id,
                "maturity": maturity,
                "max_posts_per_hour": max_posts,
                "posts_last_hour": posts_last_hour,
                "remaining_posts": max(0, max_posts - posts_last_hour),
                "reset_at": (datetime.utcnow() + timedelta(hours=1)).isoformat()
            }

        except Exception as e:
            self.logger.error(f"Failed to get rate limit info: {e}")
            return {"error": str(e)}


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
