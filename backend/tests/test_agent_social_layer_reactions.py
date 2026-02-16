"""
Tests for AgentSocialLayer reactions - separate file to avoid dict mocking issues.
"""

import pytest
from unittest.mock import Mock, AsyncMock, patch

from core.agent_social_layer import agent_social_layer
from core.agent_communication import agent_event_bus


class TestReactions:
    """Test emoji reactions on posts."""

    @pytest.mark.asyncio
    async def test_add_reaction(self):
        """Agents and humans can add emoji reactions to posts."""
        # Use a real dict, not a Mock
        reactions_dict = {}
        
        mock_post = Mock()
        mock_post.reactions = reactions_dict

        mock_db = Mock()
        mock_db.query = Mock(return_value=Mock(first=Mock(return_value=mock_post)))
        mock_db.commit = Mock()
        mock_db.refresh = Mock()

        reactions = await agent_social_layer.add_reaction(
            post_id="post-123",
            sender_id="agent-456",
            emoji="👍",
            db=mock_db
        )

        assert reactions["👍"] == 1

    @pytest.mark.asyncio
    async def test_multiple_reactions(self):
        """Multiple reactions of same emoji increment count."""
        # Use a real dict, not a Mock
        reactions_dict = {"👍": 2}
        
        mock_post = Mock()
        mock_post.reactions = reactions_dict

        mock_db = Mock()
        mock_db.query = Mock(return_value=Mock(first=Mock(return_value=mock_post)))
        mock_db.commit = Mock()
        mock_db.refresh = Mock()

        reactions = await agent_social_layer.add_reaction(
            post_id="post-123",
            sender_id="agent-789",
            emoji="👍",
            db=mock_db
        )

        assert reactions["👍"] == 3
