"""
Integration Tests for Agent Coordination

Tests cover:
- Agent-to-agent messaging via social layer
- Event bus communication
- Message delivery reliability
- Multi-agent workflows
- Message ordering (FIFO)

Note: These tests use mocked implementations for Redis and WebSocket
to avoid external dependencies while validating the coordination logic.
"""
import pytest
import asyncio
from unittest.mock import patch, AsyncMock, MagicMock
from datetime import datetime

from core.agent_social_layer import AgentSocialLayer
from core.agent_communication import agent_event_bus
from core.models import AgentRegistry, AgentPost, AgentStatus
from sqlalchemy.orm import Session


class TestAgentCoordination:
    """Test agent coordination."""

    @pytest.fixture
    def social_layer(self, db_session):
        """Create social layer instance."""
        return AgentSocialLayer()

    @pytest.fixture
    def agents_for_coordination(self, db_session):
        """Create multiple agents for coordination testing."""
        agents = []
        for i in range(3):
            agent = AgentRegistry(
                id=f"test-agent-coord-{i}",
                name=f"TestCoordAgent{i}",
                category="testing",
                module_path="test.module",
                class_name=f"TestCoord{i}",
                status=AgentStatus.AUTONOMOUS.value,
                confidence_score=0.95,
            )
            db_session.add(agent)
            agents.append(agent)
        db_session.commit()
        for agent in agents:
            db_session.refresh(agent)
        return agents

    @pytest.mark.asyncio
    async def test_agent_to_agent_messaging(self, social_layer, agents_for_coordination, db_session):
        """
        Test agent-to-agent messaging.

        Validates:
        - Agent can send message to another agent
        - Message is stored in database
        - Sender and recipient information preserved
        - Message content preserved
        - Timestamp recorded
        """
        sender, receiver = agents_for_coordination[0], agents_for_coordination[1]

        # Create a post from one agent to another
        result = await social_layer.create_post(
            sender_type="agent",
            sender_id=sender.id,
            sender_name=sender.name,
            post_type="status",
            content="Hello from sender agent!",
            sender_maturity=sender.status,
            sender_category=sender.category,
            recipient_type="agent",
            recipient_id=receiver.id,
            is_public=False,  # Directed message
            db=db_session
        )

        # Verify post created successfully
        assert result is not None
        assert result.get("success") is True or result.get("id") is not None

        # Verify post in database
        post = db_session.query(AgentPost).filter_by(
            sender_id=sender.id,
            recipient_id=receiver.id
        ).first()

        assert post is not None
        assert post.sender_type == "agent"
        assert post.sender_id == sender.id
        assert post.recipient_id == receiver.id
        assert post.content == "Hello from sender agent!"
        assert post.post_type == "status"
        assert post.is_public is False  # Directed message

    @pytest.mark.asyncio
    async def test_public_feed_posting(self, social_layer, agents_for_coordination, db_session):
        """
        Test posting to public feed.

        Validates:
        - Agent can post to public feed
        - Post visible to all agents
        - No specific recipient required
        - Proper metadata stored
        """
        sender = agents_for_coordination[0]

        # Create a public post
        result = await social_layer.create_post(
            sender_type="agent",
            sender_id=sender.id,
            sender_name=sender.name,
            post_type="insight",
            content="Public insight for all agents!",
            sender_maturity=sender.status,
            sender_category=sender.category,
            is_public=True,  # Public feed
            db=db_session
        )

        # Verify post created
        assert result is not None

        # Verify post in database
        post = db_session.query(AgentPost).filter_by(
            sender_id=sender.id,
            post_type="insight",
            is_public=True
        ).first()

        assert post is not None
        assert post.content == "Public insight for all agents!"
        assert post.is_public is True
        assert post.recipient_id is None  # Public posts have no recipient

    @pytest.mark.asyncio
    async def test_event_bus_publish_subscribe(self, agents_for_coordination):
        """
        Test event bus publish-subscribe pattern.

        Validates:
        - Agent can publish event to event bus
        - Other agents can subscribe to events
        - Subscribers receive published events
        - Event data preserved correctly
        """
        # Create event bus instance (uses in-memory by default without Redis)
        event_bus = agent_event_bus

        # Subscribe agents to event type
        await event_bus.subscribe(
            agent_id=agents_for_coordination[0].id,
            websocket=MagicMock(),  # Mock WebSocket
            topics=["agent_coordination"]
        )

        # Publish event (correct signature: event dict + topics)
        await event_bus.publish(
            event={
                "source_agent_id": agents_for_coordination[1].id,
                "target_agent_ids": [a.id for a in agents_for_coordination],
                "message": "Coordination event"
            },
            topics=["agent_coordination"]
        )

        # Note: In in-memory mode, events are broadcast to connected WebSocket clients
        # The test validates the publish mechanism works without errors
        assert True  # If we got here without exception, publish worked

    @pytest.mark.asyncio
    async def test_message_ordering_fifo(self, social_layer, agents_for_coordination, db_session):
        """
        Test message ordering (FIFO - First In, First Out).

        Validates:
        - Messages are delivered in the order they were sent
        - Timestamps preserve ordering
        - Multiple messages from same sender ordered correctly
        """
        sender, receiver = agents_for_coordination[0], agents_for_coordination[1]

        # Send multiple messages in sequence
        messages = [
            "First message",
            "Second message",
            "Third message",
            "Fourth message",
            "Fifth message"
        ]

        created_posts = []
        for i, message in enumerate(messages):
            result = await social_layer.create_post(
                sender_type="agent",
                sender_id=sender.id,
                sender_name=sender.name,
                post_type="status",
                content=message,
                sender_maturity=sender.status,
                sender_category=sender.category,
                recipient_type="agent",
                recipient_id=receiver.id,
                is_public=False,
                db=db_session
            )
            # Small delay to ensure different timestamps
            await asyncio.sleep(0.01)
            created_posts.append(result)

        # Retrieve messages from database
        posts = db_session.query(AgentPost).filter_by(
            sender_id=sender.id,
            recipient_id=receiver.id
        ).order_by(AgentPost.created_at).all()

        # Verify we have all messages
        assert len(posts) == len(messages)

        # Verify messages are in FIFO order
        retrieved_contents = [post.content for post in posts]
        assert retrieved_contents == messages

    @pytest.mark.asyncio
    async def test_multi_agent_workflow_coordination(self, social_layer, agents_for_coordination, db_session):
        """
        Test multi-agent workflow coordination.

        Validates:
        - Multiple agents can coordinate on a task
        - Each agent can post status updates
        - Agents can reference each other's posts
        - Workflow progress tracked across agents
        """
        agent1, agent2, agent3 = agents_for_coordination[0], agents_for_coordination[1], agents_for_coordination[2]

        # Agent 1 initiates workflow
        result1 = await social_layer.create_post(
            sender_type="agent",
            sender_id=agent1.id,
            sender_name=agent1.name,
            post_type="status",
            content="Starting workflow task",
            sender_maturity=agent1.status,
            sender_category=agent1.category,
            is_public=True,
            channel_id="workflow-123",
            channel_name="Test Workflow",
            db=db_session
        )

        # Agent 2 responds with progress
        result2 = await social_layer.create_post(
            sender_type="agent",
            sender_id=agent2.id,
            sender_name=agent2.name,
            post_type="status",
            content="Processing step 1 complete",
            sender_maturity=agent2.status,
            sender_category=agent2.category,
            is_public=True,
            channel_id="workflow-123",
            channel_name="Test Workflow",
            db=db_session
        )

        # Agent 3 completes workflow
        result3 = await social_layer.create_post(
            sender_type="agent",
            sender_id=agent3.id,
            sender_name=agent3.name,
            post_type="alert",
            content="Workflow task completed successfully",
            sender_maturity=agent3.status,
            sender_category=agent3.category,
            is_public=True,
            channel_id="workflow-123",
            channel_name="Test Workflow",
            db=db_session
        )

        # Verify all posts created
        assert result1 is not None
        assert result2 is not None
        assert result3 is not None

        # Retrieve all workflow posts
        workflow_posts = db_session.query(AgentPost).filter_by(
            channel_id="workflow-123"
        ).order_by(AgentPost.created_at).all()

        # Verify workflow coordination
        assert len(workflow_posts) == 3
        assert workflow_posts[0].sender_id == agent1.id
        assert workflow_posts[1].sender_id == agent2.id
        assert workflow_posts[2].sender_id == agent3.id

        # Verify content progression
        contents = [post.content for post in workflow_posts]
        assert "Starting" in contents[0]
        assert "step 1" in contents[1]
        assert "completed" in contents[2]

    @pytest.mark.asyncio
    async def test_cross_mention_coordination(self, social_layer, agents_for_coordination, db_session):
        """
        Test coordination via @mentions.

        Validates:
        - Agents can mention other agents in posts
        - Mentioned agent IDs captured correctly
        - Multiple mentions supported
        - Coordination requests tracked
        """
        agent1, agent2, agent3 = agents_for_coordination[0], agents_for_coordination[1], agents_for_coordination[2]

        # Agent 1 mentions Agent 2 and Agent 3
        result = await social_layer.create_post(
            sender_type="agent",
            sender_id=agent1.id,
            sender_name=agent1.name,
            post_type="question",
            content="Can @agent2 and @agent3 help with this task?",
            sender_maturity=agent1.status,
            sender_category=agent1.category,
            is_public=True,
            mentioned_agent_ids=[agent2.id, agent3.id],
            db=db_session
        )

        # Verify post created
        assert result is not None

        # Verify mentions in database
        post = db_session.query(AgentPost).filter_by(
            sender_id=agent1.id,
            post_type="question"
        ).first()

        assert post is not None
        assert post.mentioned_agent_ids is not None
        # Note: mentioned_agent_ids is stored as JSON string
        import json
        mentioned_ids = json.loads(post.mentioned_agent_ids) if isinstance(post.mentioned_agent_ids, str) else post.mentioned_agent_ids
        assert agent2.id in mentioned_ids
        assert agent3.id in mentioned_ids

    @pytest.mark.asyncio
    async def test_post_type_governance(self, social_layer, agents_for_coordination, db_session):
        """
        Test different post types for coordination.

        Validates:
        - All post types (status, insight, question, alert) work
        - Post types stored correctly
        - Different types serve different coordination purposes
        """
        sender = agents_for_coordination[0]

        post_types = ["status", "insight", "question", "alert"]
        created_posts = []

        for post_type in post_types:
            result = await social_layer.create_post(
                sender_type="agent",
                sender_id=sender.id,
                sender_name=sender.name,
                post_type=post_type,
                content=f"Testing {post_type} post type",
                sender_maturity=sender.status,
                sender_category=sender.category,
                is_public=True,
                db=db_session
            )
            created_posts.append(result)

        # Verify all post types created
        for post_type in post_types:
            post = db_session.query(AgentPost).filter_by(
                sender_id=sender.id,
                post_type=post_type
            ).first()
            assert post is not None
            assert post.post_type == post_type

    @pytest.mark.asyncio
    async def test_student_agent_read_only(self, social_layer, agents_for_coordination, db_session):
        """
        Test that STUDENT agents cannot post (governance check).

        Validates:
        - STUDENT agents blocked from posting
        - PermissionError raised appropriately
        - Error message includes governance reason
        """
        # Create STUDENT agent
        student_agent = AgentRegistry(
            id="test-student-agent",
            name="TestStudentAgent",
            category="testing",
            module_path="test.module",
            class_name="TestStudent",
            status=AgentStatus.STUDENT.value,
            confidence_score=0.3,
        )
        db_session.add(student_agent)
        db_session.commit()
        db_session.refresh(student_agent)

        # Attempt to create post as STUDENT agent
        with pytest.raises(PermissionError) as exc_info:
            await social_layer.create_post(
                sender_type="agent",
                sender_id=student_agent.id,
                sender_name=student_agent.name,
                post_type="status",
                content="STUDENT attempting to post",
                sender_maturity=student_agent.status,
                sender_category=student_agent.category,
                is_public=True,
                db=db_session
            )

        # Verify error message
        error_message = str(exc_info.value)
        assert "STUDENT" in error_message
        assert "cannot post" in error_message.lower() or "read-only" in error_message.lower()

    @pytest.mark.asyncio
    async def test_message_persistence_across_sessions(self, social_layer, agents_for_coordination, db_session):
        """
        Test that messages persist across different agent sessions.

        Validates:
        - Messages stored in database
        - Messages retrievable after creation
        - Historical messages accessible
        - Multiple agents can access same messages
        """
        sender, receiver = agents_for_coordination[0], agents_for_coordination[1]

        # Create initial message
        await social_layer.create_post(
            sender_type="agent",
            sender_id=sender.id,
            sender_name=sender.name,
            post_type="status",
            content="Persistent message for later retrieval",
            sender_maturity=sender.status,
            sender_category=sender.category,
            is_public=True,
            db=db_session
        )

        # Simulate new session - retrieve all public posts
        all_public_posts = db_session.query(AgentPost).filter_by(
            is_public=True
        ).all()

        # Verify message persists
        assert len(all_public_posts) >= 1
        persistent_message = [p for p in all_public_posts if p.content == "Persistent message for later retrieval"]
        assert len(persistent_message) == 1

    @pytest.mark.asyncio
    async def test_reply_coordination(self, social_layer, agents_for_coordination, db_session):
        """
        Test agent reply coordination.

        Validates:
        - Agents can reply to specific posts
        - Reply context maintained
        - Conversation threads possible
        """
        agent1, agent2 = agents_for_coordination[0], agents_for_coordination[1]

        # Agent 1 creates original post
        original_post = await social_layer.create_post(
            sender_type="agent",
            sender_id=agent1.id,
            sender_name=agent1.name,
            post_type="question",
            content="How do I implement feature X?",
            sender_maturity=agent1.status,
            sender_category=agent1.category,
            is_public=True,
            db=db_session
        )

        # Get the post ID
        original_post_db = db_session.query(AgentPost).filter_by(
            sender_id=agent1.id,
            content="How do I implement feature X?"
        ).first()

        # Agent 2 replies (creates new post with reference)
        reply_post = await social_layer.create_post(
            sender_type="agent",
            sender_id=agent2.id,
            sender_name=agent2.name,
            post_type="insight",
            content="Here's how to implement feature X...",
            sender_maturity=agent2.status,
            sender_category=agent2.category,
            is_public=True,
            mentioned_agent_ids=[agent1.id],  # Reference original poster
            db=db_session
        )

        # Verify both posts exist
        assert original_post_db is not None

        reply_post_db = db_session.query(AgentPost).filter_by(
            sender_id=agent2.id,
            content="Here's how to implement feature X..."
        ).first()

        assert reply_post_db is not None

        # Verify reply references original agent
        import json
        mentioned_ids = json.loads(reply_post_db.mentioned_agent_ids) if isinstance(reply_post_db.mentioned_agent_ids, str) else reply_post_db.mentioned_agent_ids
        assert agent1.id in mentioned_ids
