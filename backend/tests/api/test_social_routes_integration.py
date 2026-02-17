"""
API Integration Tests for Social Routes

Tests cover:
- GET /feed - Retrieve social feed
- POST /posts - Create new post
- GET /channels - List channels
- GET /channels/{id}/feed - Channel-specific feed
- POST /channels/{id}/posts - Post to channel
- Pagination with cursor
- Filter by topic
"""
import pytest
from datetime import datetime, timedelta
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from main_api_app import app
from core.models import AgentRegistry, AgentPost, Channel
from tests.factories import AgentFactory


class TestSocialRoutesAPI:
    """Test social routes API endpoints."""

    @pytest.fixture
    def client(self):
        """Create test client."""
        return TestClient(app)

    @pytest.fixture
    def agent(self, db_session):
        """Create test agent."""
        agent = AgentFactory(
            name="TestAgent",
            status="INTERN",
            class_name="TestAgent",
            module_path="tests.api.test_social_routes_integration"
        )
        db_session.add(agent)
        db_session.commit()
        return agent

    @pytest.fixture
    def channel(self, db_session):
        """Create test channel."""
        channel = Channel(
            id="test-channel",
            name="test",
            display_name="Test Channel",
            description="Test channel",
            channel_type="general",
            is_public=True
        )
        db_session.add(channel)
        db_session.commit()
        return channel

    def test_get_feed(self, client, agent, channel, db_session):
        """Test GET /api/social/feed endpoint."""
        # Create posts
        now = datetime.utcnow()
        for i in range(5):
            post = AgentPost(
                sender_type="agent",
                sender_id=agent.id,
                sender_name=agent.name,
                sender_maturity=agent.status,
                sender_category=agent.category,
                post_type="status",
                content=f"Post {i}",
                channel_id=channel.id,
                channel_name=channel.name,
                is_public=True,
                created_at=now + timedelta(seconds=i)
            )
            db_session.add(post)
        db_session.commit()

        # Get feed
        response = client.get(f"/api/social/feed?sender_id={agent.id}&channel_id={channel.id}&limit=10")

        assert response.status_code == 200
        data = response.json()
        assert "posts" in data
        assert len(data["posts"]) == 5

    def test_create_post(self, client, agent, channel):
        """Test POST /api/social/posts endpoint."""
        response = client.post(
            "/api/social/posts",
            json={
                "sender_type": "agent",
                "sender_id": agent.id,
                "sender_name": agent.name,
                "sender_maturity": agent.status,
                "sender_category": agent.category,
                "post_type": "status",
                "content": "Test post #automation",
                "is_public": True,
                "channel_id": channel.id,
                "channel_name": channel.name
            }
        )

        assert response.status_code == 200
        data = response.json()
        assert data["content"] == "Test post #automation"
        assert data["sender_id"] == agent.id
        assert data["channel_id"] == channel.id

    def test_create_post_student_forbidden(self, client, db_session):
        """Test POST /api/social/posts with STUDENT agent (should fail)."""
        # Create STUDENT agent
        student_agent = AgentFactory(
            name="StudentAgent",
            status="STUDENT",
            class_name="TestAgent",
            module_path="tests.api.test_social_routes_integration"
        )
        db_session.add(student_agent)
        db_session.commit()

        response = client.post(
            "/api/social/posts",
            json={
                "sender_type": "agent",
                "sender_id": student_agent.id,
                "sender_name": student_agent.name,
                "sender_maturity": student_agent.status,
                "sender_category": student_agent.category,
                "post_type": "status",
                "content": "Should not be allowed",
                "is_public": True
            }
        )

        # STUDENT agents should get 403 Forbidden
        assert response.status_code == 403
        assert "STUDENT agents cannot post" in response.json()["detail"]

    def test_get_channels(self, client, db_session):
        """Test GET /api/social/channels endpoint."""
        # Create channels
        for i in range(3):
            channel = Channel(
                id=f"channel-{i}",
                name=f"channel-{i}",
                display_name=f"Channel {i}",
                description=f"Channel {i}",
                channel_type="general",
                is_public=True
            )
            db_session.add(channel)
        db_session.commit()

        # Get channels
        response = client.get("/api/social/channels")

        assert response.status_code == 200
        data = response.json()
        assert "channels" in data
        assert len(data["channels"]) >= 3

    def test_create_channel(self, client):
        """Test POST /api/social/channels endpoint."""
        response = client.post(
            "/api/social/channels",
            json={
                "channel_id": "new-channel",
                "channel_name": "new-channel",
                "creator_id": "user-123",
                "display_name": "New Channel",
                "description": "A new channel",
                "channel_type": "general",
                "is_public": True
            }
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["channel"]["id"] == "new-channel"

    def test_get_channel_feed(self, client, agent, channel, db_session):
        """Test GET /api/social/feed with channel_id filter."""
        # Create posts in channel
        now = datetime.utcnow()
        for i in range(5):
            post = AgentPost(
                sender_type="agent",
                sender_id=agent.id,
                sender_name=agent.name,
                sender_maturity=agent.status,
                sender_category=agent.category,
                post_type="status",
                content=f"Post {i}",
                channel_id=channel.id,
                channel_name=channel.name,
                is_public=True,
                created_at=now + timedelta(seconds=i)
            )
            db_session.add(post)
        db_session.commit()

        # Get channel feed
        response = client.get(f"/api/social/feed?sender_id={agent.id}&channel_id={channel.id}")

        assert response.status_code == 200
        data = response.json()
        assert len(data["posts"]) == 5

    def test_pagination_with_offset(self, client, agent, channel, db_session):
        """Test pagination with limit and offset parameters."""
        # Create 50 posts
        now = datetime.utcnow()
        for i in range(50):
            post = AgentPost(
                sender_type="agent",
                sender_id=agent.id,
                sender_name=agent.name,
                sender_maturity=agent.status,
                sender_category=agent.category,
                post_type="status",
                content=f"Post {i}",
                channel_id=channel.id,
                channel_name=channel.name,
                is_public=True,
                created_at=now + timedelta(seconds=i)
            )
            db_session.add(post)
        db_session.commit()

        # Get first page
        response1 = client.get(f"/api/social/feed?sender_id={agent.id}&channel_id={channel.id}&limit=20&offset=0")
        assert response1.status_code == 200
        data1 = response1.json()

        # Get second page
        response2 = client.get(f"/api/social/feed?sender_id={agent.id}&channel_id={channel.id}&limit=20&offset=20")
        assert response2.status_code == 200
        data2 = response2.json()

        # Should have different posts (no duplicates)
        ids1 = {p["id"] for p in data1["posts"]}
        ids2 = {p["id"] for p in data2["posts"]}
        assert len(ids1 & ids2) == 0  # No duplicates

    def test_pagination_with_cursor(self, client, agent, channel, db_session):
        """Test pagination with cursor parameter."""
        # Create 50 posts
        now = datetime.utcnow()
        for i in range(50):
            post = AgentPost(
                sender_type="agent",
                sender_id=agent.id,
                sender_name=agent.name,
                sender_maturity=agent.status,
                sender_category=agent.category,
                post_type="status",
                content=f"Post {i}",
                channel_id=channel.id,
                channel_name=channel.name,
                is_public=True,
                created_at=now + timedelta(milliseconds=i*10)
            )
            db_session.add(post)
        db_session.commit()

        # Get first page
        response1 = client.get(f"/api/social/feed/cursor?sender_id={agent.id}&channel_id={channel.id}&limit=20")
        assert response1.status_code == 200
        data1 = response1.json()
        cursor1 = data1.get("next_cursor")

        # Get second page with cursor
        response2 = client.get(f"/api/social/feed/cursor?sender_id={agent.id}&channel_id={channel.id}&cursor={cursor1}&limit=20")
        assert response2.status_code == 200
        data2 = response2.json()

        # Should have different posts
        ids1 = {p["id"] for p in data1["posts"]}
        ids2 = {p["id"] for p in data2["posts"]}
        assert len(ids1 & ids2) == 0  # No duplicates

    def test_filter_feed_by_post_type(self, client, agent, channel, db_session):
        """Test filtering feed by post type."""
        # Create posts with different types
        now = datetime.utcnow()
        post_types = ["status", "insight", "question", "alert"]
        for i, post_type in enumerate(post_types * 2):
            post = AgentPost(
                sender_type="agent",
                sender_id=agent.id,
                sender_name=agent.name,
                sender_maturity=agent.status,
                sender_category=agent.category,
                post_type=post_type,
                content=f"{post_type} post {i}",
                channel_id=channel.id,
                channel_name=channel.name,
                is_public=True,
                created_at=now + timedelta(seconds=i)
            )
            db_session.add(post)
        db_session.commit()

        # Filter by question type
        response = client.get(f"/api/social/feed?sender_id={agent.id}&channel_id={channel.id}&post_type=question")

        assert response.status_code == 200
        data = response.json()

        # Should only have question posts
        assert all(p["post_type"] == "question" for p in data["posts"])
        assert len(data["posts"]) == 2

    def test_filter_feed_by_sender(self, client, agent, channel, db_session):
        """Test filtering feed by specific sender."""
        # Create another agent
        agent2 = AgentFactory(
            name="Agent2",
            status="INTERN",
            class_name="TestAgent",
            module_path="tests.api.test_social_routes_integration"
        )
        db_session.add(agent2)

        # Create posts from both agents
        now = datetime.utcnow()
        for i in range(3):
            post1 = AgentPost(
                sender_type="agent",
                sender_id=agent.id,
                sender_name=agent.name,
                sender_maturity=agent.status,
                sender_category=agent.category,
                post_type="status",
                content=f"Agent1 post {i}",
                channel_id=channel.id,
                channel_name=channel.name,
                is_public=True,
                created_at=now + timedelta(seconds=i*2)
            )
            db_session.add(post1)

            post2 = AgentPost(
                sender_type="agent",
                sender_id=agent2.id,
                sender_name=agent2.name,
                sender_maturity=agent2.status,
                sender_category=agent2.category,
                post_type="status",
                content=f"Agent2 post {i}",
                channel_id=channel.id,
                channel_name=channel.name,
                is_public=True,
                created_at=now + timedelta(seconds=i*2+1)
            )
            db_session.add(post2)
        db_session.commit()

        # Filter by agent1
        response = client.get(f"/api/social/feed?sender_id={agent.id}&channel_id={channel.id}&sender_filter={agent.id}")

        assert response.status_code == 200
        data = response.json()

        # Should only have agent1's posts
        assert all(p["sender_id"] == agent.id for p in data["posts"])
        assert len(data["posts"]) == 3

    def test_create_reply(self, client, agent, channel, db_session):
        """Test POST /api/social/posts/{post_id}/replies endpoint."""
        # Create parent post
        now = datetime.utcnow()
        parent = AgentPost(
            sender_type="agent",
            sender_id=agent.id,
            sender_name=agent.name,
            sender_maturity=agent.status,
            sender_category=agent.category,
            post_type="question",
            content="Parent post",
            channel_id=channel.id,
            channel_name=channel.name,
            is_public=True,
            created_at=now
        )
        db_session.add(parent)
        db_session.commit()

        # Create reply
        response = client.post(
            f"/api/social/posts/{parent.id}/replies",
            json={
                "sender_type": "agent",
                "sender_id": agent.id,
                "sender_name": agent.name,
                "sender_maturity": agent.status,
                "sender_category": agent.category,
                "content": "Reply to parent"
            }
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["reply"]["content"] == "Reply to parent"
        assert data["reply"]["post_type"] == "response"

    def test_get_replies(self, client, agent, channel, db_session):
        """Test GET /api/social/posts/{post_id}/replies endpoint."""
        # Create parent post
        now = datetime.utcnow()
        parent = AgentPost(
            sender_type="agent",
            sender_id=agent.id,
            sender_name=agent.name,
            sender_maturity=agent.status,
            sender_category=agent.category,
            post_type="question",
            content="Parent post",
            channel_id=channel.id,
            channel_name=channel.name,
            is_public=True,
            reply_count=3,
            created_at=now
        )
        db_session.add(parent)
        db_session.commit()

        # Create replies
        for i in range(3):
            reply = AgentPost(
                sender_type="agent",
                sender_id=agent.id,
                sender_name=agent.name,
                sender_maturity=agent.status,
                sender_category=agent.category,
                post_type="response",
                content=f"Reply {i}",
                reply_to_id=parent.id,
                created_at=now + timedelta(seconds=i+1)
            )
            db_session.add(reply)
        db_session.commit()

        # Get replies
        response = client.get(f"/api/social/posts/{parent.id}/replies?limit=50")

        assert response.status_code == 200
        data = response.json()
        assert "replies" in data
        assert len(data["replies"]) == 3
        assert data["total"] == 3

    def test_add_reaction(self, client, agent, channel, db_session):
        """Test POST /api/social/posts/{post_id}/reactions endpoint."""
        # Create post
        now = datetime.utcnow()
        post = AgentPost(
            sender_type="agent",
            sender_id=agent.id,
            sender_name=agent.name,
            sender_maturity=agent.status,
            sender_category=agent.category,
            post_type="status",
            content="Test post",
            channel_id=channel.id,
            channel_name=channel.name,
            is_public=True,
            reactions={},
            created_at=now
        )
        db_session.add(post)
        db_session.commit()

        # Add reaction
        response = client.post(
            f"/api/social/posts/{post.id}/reactions?sender_id={agent.id}&emoji=%F0%9F%91%8D"
        )

        assert response.status_code == 200
        data = response.json()
        assert "reactions" in data
        assert data["reactions"].get("👍", 0) == 1

    def test_get_trending(self, client, agent, channel, db_session):
        """Test GET /api/social/trending endpoint."""
        # Create posts with mentions
        now = datetime.utcnow()
        post = AgentPost(
            sender_type="agent",
            sender_id=agent.id,
            sender_name=agent.name,
            sender_maturity=agent.status,
            sender_category=agent.category,
            post_type="status",
            content="Mentioning agent-123 and episode-456",
            mentioned_agent_ids=["agent-123", "agent-456"],
            mentioned_episode_ids=["episode-456"],
            channel_id=channel.id,
            channel_name=channel.name,
            is_public=True,
            created_at=now
        )
        db_session.add(post)
        db_session.commit()

        # Get trending
        response = client.get("/api/social/trending?hours=24")

        assert response.status_code == 200
        data = response.json()
        assert "trending" in data

    def test_public_vs_private_feed(self, client, agent, channel, db_session):
        """Test filtering by public/private posts."""
        # Create public post
        now = datetime.utcnow()
        public_post = AgentPost(
            sender_type="agent",
            sender_id=agent.id,
            sender_name=agent.name,
            sender_maturity=agent.status,
            sender_category=agent.category,
            post_type="status",
            content="Public post",
            is_public=True,
            created_at=now
        )
        db_session.add(public_post)

        # Create private post
        private_post = AgentPost(
            sender_type="agent",
            sender_id=agent.id,
            sender_name=agent.name,
            sender_maturity=agent.status,
            sender_category=agent.category,
            post_type="command",
            content="Private post",
            is_public=False,
            recipient_type="agent",
            recipient_id=agent.id,
            created_at=now + timedelta(seconds=1)
        )
        db_session.add(private_post)
        db_session.commit()

        # Get public feed
        response = client.get(f"/api/social/feed?sender_id={agent.id}&is_public=true")
        assert response.status_code == 200
        data = response.json()
        assert all(p["is_public"] for p in data["posts"])

        # Get private feed
        response = client.get(f"/api/social/feed?sender_id={agent.id}&is_public=false")
        assert response.status_code == 200
        data = response.json()
        assert all(not p["is_public"] for p in data["posts"])

    def test_empty_feed(self, client, agent, channel):
        """Test GET /feed with no posts."""
        response = client.get(f"/api/social/feed?sender_id={agent.id}&channel_id={channel.id}")

        assert response.status_code == 200
        data = response.json()
        assert data["posts"] == []
        assert data["total"] == 0

    def test_invalid_post_type(self, client, agent):
        """Test POST /posts with invalid post type."""
        response = client.post(
            "/api/social/posts",
            json={
                "sender_type": "agent",
                "sender_id": agent.id,
                "sender_name": agent.name,
                "sender_maturity": agent.status,
                "sender_category": agent.category,
                "post_type": "invalid_type",
                "content": "Should fail",
                "is_public": True
            }
        )

        assert response.status_code == 400
        assert "Invalid post_type" in response.json()["detail"]
