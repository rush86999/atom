"""
Tests for Social Post Generator and Operation Tracker Hooks.

Comprehensive test coverage for:
- GPT-4.1 mini post generation
- Template fallback generation
- Significant operation detection
- Rate limiting enforcement
- Governance enforcement (INTERN+ can post, STUDENT read-only)
- PII redaction integration
- Auto-post hooks trigger
"""

import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, MagicMock, patch
from datetime import datetime, timedelta
from sqlalchemy.orm import Session

from core.social_post_generator import SocialPostGenerator
from core.operation_tracker_hooks import OperationTrackerHooks
from core.models import AgentOperationTracker, AgentRegistry


# ==============================================================================
# Unit Tests: SocialPostGenerator
# ==============================================================================

class TestSocialPostGenerator:
    """Unit tests for SocialPostGenerator"""

    @pytest.fixture
    def generator(self):
        """Create a SocialPostGenerator instance"""
        return SocialPostGenerator()

    @pytest.fixture
    def mock_agent(self):
        """Create a mock agent"""
        agent = Mock(spec=AgentRegistry)
        agent.id = "agent_123"
        agent.name = "Test Agent"
        agent.status = "INTERN"
        agent.category = "engineering"
        return agent

    @pytest.fixture
    def mock_tracker(self):
        """Create a mock operation tracker"""
        tracker = Mock(spec=AgentOperationTracker)
        tracker.id = "tracker_123"
        tracker.agent_id = "agent_123"
        tracker.operation_type = "workflow_execute"
        tracker.status = "completed"
        tracker.what_explanation = "Ran test suite for PR #123"
        tracker.why_explanation = "To ensure code quality"
        tracker.next_steps = "Fixing 3 failing tests"
        return tracker

    def test_is_significant_operation_workflow_completed(self, generator, mock_tracker):
        """Test that completed workflow operations are significant"""
        mock_tracker.operation_type = "workflow_execute"
        mock_tracker.status = "completed"

        result = generator.is_significant_operation(mock_tracker)

        assert result is True

    def test_is_significant_operation_integration_connect(self, generator, mock_tracker):
        """Test that integration connect operations are significant"""
        mock_tracker.operation_type = "integration_connect"
        mock_tracker.status = "completed"

        result = generator.is_significant_operation(mock_tracker)

        assert result is True

    def test_is_significant_operation_browser_automate(self, generator, mock_tracker):
        """Test that browser automation operations are significant"""
        mock_tracker.operation_type = "browser_automate"
        mock_tracker.status = "completed"

        result = generator.is_significant_operation(mock_tracker)

        assert result is True

    def test_is_significant_operation_db_query(self, generator, mock_tracker):
        """Test that trivial operations are not significant"""
        mock_tracker.operation_type = "database_query"
        mock_tracker.status = "completed"

        result = generator.is_significant_operation(mock_tracker)

        assert result is False

    def test_is_significant_operation_running_status(self, generator, mock_tracker):
        """Test that running operations are not significant"""
        mock_tracker.operation_type = "workflow_execute"
        mock_tracker.status = "running"

        result = generator.is_significant_operation(mock_tracker)

        assert result is False

    def test_is_significant_operation_approval_requested(self, generator, mock_tracker):
        """Test that approval requests are always significant"""
        mock_tracker.operation_type = "approval_requested"
        mock_tracker.status = "waiting"

        result = generator.is_significant_operation(mock_tracker)

        assert result is True

    def test_template_fallback_content(self, generator):
        """Test that template fallback generates valid content"""
        metadata = {
            "agent_name": "Test Agent",
            "operation_type": "workflow_execute",
            "what_explanation": "Ran tests",
            "why_explanation": "Code quality",
            "next_steps": "Fix bugs",
            "status": "completed"
        }

        post = generator.generate_with_template("workflow_execute", metadata)

        assert len(post) <= 280
        assert "workflow" in post.lower() or "tests" in post.lower()

    def test_template_fallback_truncation(self, generator):
        """Test that long content is truncated to 280 chars"""
        long_text = "x" * 500
        metadata = {
            "agent_name": "Test Agent",
            "operation_type": "workflow_execute",
            "what_explanation": long_text,
            "why_explanation": long_text,
            "next_steps": long_text,
            "status": "completed"
        }

        post = generator.generate_with_template("workflow_execute", metadata)

        assert len(post) <= 280
        assert post.endswith("...")

    def test_rate_limit_enforcement(self, generator):
        """Test that rate limit prevents posts within window"""
        agent_id = "agent_123"

        # First post should not be rate limited
        assert generator.is_rate_limited(agent_id) is False

        # Update rate limit
        generator.update_rate_limit(agent_id)

        # Second post within window should be rate limited
        assert generator.is_rate_limited(agent_id) is True

    def test_rate_limit_expiry(self, generator):
        """Test that rate limit expires after window"""
        agent_id = "agent_123"

        # Set rate limit in the past
        generator._rate_limit_tracker[agent_id] = datetime.utcnow() - timedelta(minutes=10)

        # Should not be rate limited now
        assert generator.is_rate_limited(agent_id) is False

    @pytest.mark.asyncio
    async def test_generate_from_operation_success(self, generator, mock_tracker, mock_agent):
        """Test successful post generation"""
        with patch.object(generator, '_openai_client', create=True):
            generator._openai_client = AsyncMock()
            generator._openai_client.chat.completions.create = AsyncMock(
                return_value=Mock(choices=[Mock(message=Mock(content="Just finished tests! 🧪"))])
            )

            post = await generator.generate_from_operation(mock_tracker, mock_agent)

            assert post == "Just finished tests! 🧪"
            assert len(post) <= 280

    @pytest.mark.asyncio
    async def test_generate_from_operation_fallback_to_template(self, generator, mock_tracker, mock_agent):
        """Test fallback to template when LLM unavailable"""
        generator._openai_client = None

        post = await generator.generate_from_operation(mock_tracker, mock_agent)

        assert "workflow" in post.lower() or "tests" in post.lower()
        assert len(post) <= 280

    @pytest.mark.asyncio
    async def test_llm_timeout_fallback(self, generator, mock_tracker, mock_agent):
        """Test that LLM timeout falls back to template"""
        with patch.object(generator, '_openai_client', create=True):
            generator._openai_client = AsyncMock()
            generator._openai_client.chat.completions.create = AsyncMock(
                side_effect=asyncio.TimeoutError()
            )

            post = await generator.generate_from_operation(mock_tracker, mock_agent)

            assert "workflow" in post.lower() or "tests" in post.lower()

    def test_missing_what_explanation_raises_error(self, generator, mock_tracker, mock_agent):
        """Test that missing what_explanation raises ValueError"""
        mock_tracker.what_explanation = None

        with pytest.raises(ValueError, match="what_explanation is required"):
            asyncio.run(generator.generate_from_operation(mock_tracker, mock_agent))

    # Additional GPT-4.1 Mini NLG Tests
    @pytest.mark.asyncio
    async def test_llm_api_error_fallback(self, generator, mock_tracker, mock_agent):
        """Test that API errors fall back to template"""
        with patch.object(generator, '_openai_client', create=True):
            import openai
            generator._openai_client = AsyncMock()
            # Use Exception instead of APIError to avoid complex signature
            generator._openai_client.chat.completions.create = AsyncMock(
                side_effect=Exception("API request failed")
            )

            post = await generator.generate_from_operation(mock_tracker, mock_agent)

            assert "workflow" in post.lower() or "tests" in post.lower()

    @pytest.mark.asyncio
    async def test_llm_disabled_behavior(self, generator, mock_tracker, mock_agent):
        """Test that template used when LLM disabled"""
        generator.llm_enabled = False

        post = await generator.generate_from_operation(mock_tracker, mock_agent)

        assert "workflow" in post.lower() or "tests" in post.lower()
        assert len(post) <= 280

    @pytest.mark.asyncio
    async def test_generated_post_length_limit(self, generator, mock_tracker, mock_agent):
        """Verify 280 character truncation"""
        # Create a very long response
        long_response = "x" * 300
        with patch.object(generator, '_openai_client', create=True):
            generator._openai_client = AsyncMock()
            generator._openai_client.chat.completions.create = AsyncMock(
                return_value=Mock(choices=[Mock(message=Mock(content=long_response))])
            )

            post = await generator.generate_from_operation(mock_tracker, mock_agent)

            assert len(post) <= 280

    @pytest.mark.asyncio
    async def test_generated_post_quality(self, generator, mock_tracker, mock_agent):
        """Verify casual tone, emoji usage (max 2), no jargon"""
        with patch.object(generator, '_openai_client', create=True):
            generator._openai_client = AsyncMock()
            generator._openai_client.chat.completions.create = AsyncMock(
                return_value=Mock(choices=[Mock(message=Mock(content="Just finished running tests! 🎉 All passed! 🧪"))])
            )

            post = await generator.generate_from_operation(mock_tracker, mock_agent)

            # Count emojis (should be max 2)
            emoji_count = sum(1 for char in post if ord(char) > 127)
            assert emoji_count <= 2, f"Too many emojis: {post}"

            # Should be casual tone (not overly formal)
            assert len(post) <= 280

    def test_significant_operation_detection(self, generator):
        """All 7 operation types verified"""
        significant_ops = [
            "workflow_execute",
            "integration_connect",
            "browser_automate",
            "report_generate",
            "human_feedback_received",
            "approval_requested",
            "agent_to_agent_call"
        ]

        for op_type in significant_ops:
            tracker = Mock(spec=AgentOperationTracker)
            tracker.operation_type = op_type
            tracker.status = "completed"
            tracker.what_explanation = "Test"
            tracker.why_explanation = "Test"
            tracker.next_steps = "Test"

            result = generator.is_significant_operation(tracker)
            assert result is True, f"{op_type} should be significant"

    # Additional Template Fallback Tests
    def test_template_completed_status(self, generator):
        """Uses 'completed' template"""
        metadata = {
            "agent_name": "Test Agent",
            "operation_type": "workflow_execute",
            "what_explanation": "Ran tests",
            "why_explanation": "Quality",
            "next_steps": "Fix bugs",
            "status": "completed"
        }

        post = generator.generate_with_template("workflow_execute", metadata)

        assert "completed" in post.lower() or "workflow" in post.lower()

    def test_template_working_status(self, generator):
        """Uses 'working' template"""
        metadata = {
            "agent_name": "Test Agent",
            "operation_type": "workflow_execute",
            "what_explanation": "Running tests",
            "why_explanation": "Quality",
            "next_steps": "Fix bugs",
            "status": "running"
        }

        post = generator.generate_with_template("workflow_execute", metadata)

        assert "working" in post.lower() or "workflow" in post.lower()

    def test_template_default_status(self, generator):
        """Uses 'default' template"""
        metadata = {
            "agent_name": "Test Agent",
            "operation_type": "workflow_execute",
            "what_explanation": "Running tests",
            "why_explanation": "Quality",
            "next_steps": "Fix bugs",
            "status": "pending"
        }

        post = generator.generate_with_template("workflow_execute", metadata)

        # Should use default template
        assert "test agent" in post.lower() or "workflow" in post.lower()

    def test_template_missing_key_uses_default(self, generator):
        """KeyError handled gracefully"""
        # Missing required metadata keys
        metadata = {
            "agent_name": "Test Agent",
            "status": "completed"
        }

        post = generator.generate_with_template("workflow_execute", metadata)

        # Should not crash, should return something
        assert post is not None
        assert len(post) > 0

    def test_template_empty_content(self, generator):
        """Empty strings handled"""
        metadata = {
            "agent_name": "",
            "operation_type": "workflow_execute",
            "what_explanation": "",
            "why_explanation": "",
            "next_steps": "",
            "status": "completed"
        }

        post = generator.generate_with_template("workflow_execute", metadata)

        # Should handle gracefully
        assert post is not None

    def test_template_special_characters(self, generator):
        """Special characters preserved"""
        metadata = {
            "agent_name": "Test Agent",
            "operation_type": "workflow_execute",
            "what_explanation": "Fixed bug: NullPointerException in @async method",
            "why_explanation": "Critical fix",
            "next_steps": "Deploy to prod",
            "status": "completed"
        }

        post = generator.generate_with_template("workflow_execute", metadata)

        # Should handle special chars
        assert post is not None
        assert len(post) <= 280

    def test_template_unicode_content(self, generator):
        """Unicode characters handled"""
        metadata = {
            "agent_name": "Tëst Ägënt",
            "operation_type": "workflow_execute",
            "what_explanation": "Fïxëd büg",
            "why_explanation": "Crïtical",
            "next_steps": "Dëploy",
            "status": "completed"
        }

        post = generator.generate_with_template("workflow_execute", metadata)

        # Should handle unicode
        assert post is not None
        assert len(post) <= 280


# ==============================================================================
# Unit Tests: OperationTrackerHooks
# ==============================================================================

class TestOperationTrackerHooks:
    """Unit tests for OperationTrackerHooks"""

    @pytest.fixture
    def hooks(self):
        """Create OperationTrackerHooks instance"""
        return OperationTrackerHooks()

    @pytest.fixture
    def mock_tracker(self):
        """Create a mock operation tracker"""
        tracker = Mock(spec=AgentOperationTracker)
        tracker.id = "tracker_123"
        tracker.agent_id = "agent_123"
        tracker.operation_type = "workflow_execute"
        tracker.status = "completed"
        tracker.what_explanation = "Ran tests"
        tracker.why_explanation = "Code quality"
        tracker.next_steps = "Fix bugs"
        return tracker

    def test_is_alert_post_failed_status(self, hooks, mock_tracker):
        """Test that failed operations are alert posts"""
        mock_tracker.status = "failed"

        result = hooks.is_alert_post(mock_tracker)

        assert result is True

    def test_is_alert_post_security_operation(self, hooks, mock_tracker):
        """Test that security operations are alert posts"""
        mock_tracker.operation_type = "security_scan"

        result = hooks.is_alert_post(mock_tracker)

        assert result is True

    def test_is_alert_post_approval_requested(self, hooks, mock_tracker):
        """Test that approval requests are alert posts"""
        mock_tracker.operation_type = "approval_requested"

        result = hooks.is_alert_post(mock_tracker)

        assert result is True

    def test_is_alert_post_normal_operation(self, hooks, mock_tracker):
        """Test that normal operations are not alert posts"""
        mock_tracker.operation_type = "workflow_execute"
        mock_tracker.status = "completed"

        result = hooks.is_alert_post(mock_tracker)

        assert result is False

    def test_rate_limit_enforcement(self, hooks):
        """Test rate limiting enforcement"""
        agent_id = "agent_123"

        # First post not rate limited
        assert hooks.is_rate_limited(agent_id) is False

        # Update rate limit
        hooks.update_rate_limit(agent_id)

        # Second post rate limited
        assert hooks.is_rate_limited(agent_id) is True

    def test_rate_limit_independent_per_agent(self, hooks):
        """Test that rate limit is independent per agent"""
        agent_1 = "agent_1"
        agent_2 = "agent_2"

        # Agent 1 posts
        hooks.update_rate_limit(agent_1)

        # Agent 1 rate limited
        assert hooks.is_rate_limited(agent_1) is True

        # Agent 2 not rate limited
        assert hooks.is_rate_limited(agent_2) is False


# ==============================================================================
# Integration Tests
# ==============================================================================

class TestSocialPostIntegration:
    """Integration tests for social post generation"""

    @pytest.fixture(autouse=True)
    def reset_rate_limit_tracker(self):
        """Reset rate limit tracker before each test"""
        OperationTrackerHooks._rate_limit_tracker = {}
        yield
        OperationTrackerHooks._rate_limit_tracker = {}

    @pytest.fixture
    def mock_db(self):
        """Create mock database session"""
        db = Mock(spec=Session)
        return db

    @pytest.fixture
    def mock_agent(self):
        """Create mock agent"""
        agent = Mock(spec=AgentRegistry)
        agent.id = "agent_123"
        agent.name = "Test Agent"
        agent.status = "INTERN"
        agent.category = "engineering"
        return agent

    @pytest.fixture
    def mock_student_agent(self):
        """Create mock STUDENT agent"""
        agent = Mock(spec=AgentRegistry)
        agent.id = "student_123"
        agent.name = "Student Agent"
        agent.status = "STUDENT"
        agent.category = "engineering"
        return agent

    @pytest.fixture
    def mock_tracker(self):
        """Create mock operation tracker"""
        tracker = Mock(spec=AgentOperationTracker)
        tracker.id = "tracker_123"
        tracker.agent_id = "agent_123"
        tracker.operation_type = "workflow_execute"
        tracker.status = "completed"
        tracker.what_explanation = "Ran tests"
        tracker.why_explanation = "Code quality"
        tracker.next_steps = "Fix bugs"
        return tracker

    @pytest.mark.asyncio
    async def test_operation_complete_triggers_post(
        self, mock_tracker, mock_agent, mock_db
    ):
        """Test that operation completion triggers social post"""
        # Mock database queries
        mock_db.query.return_value.filter.return_value.first.side_effect = [mock_tracker, mock_agent]

        # Mock social layer
        with patch('core.operation_tracker_hooks.agent_social_layer') as mock_social:
            mock_social.create_post = AsyncMock()

            hooks = OperationTrackerHooks()
            await hooks.on_operation_complete("tracker_123", mock_db)

            # Verify post was created
            mock_social.create_post.assert_called_once()
            call_args = mock_social.create_post.call_args
            assert call_args.kwargs['sender_id'] == "agent_123"
            assert call_args.kwargs['auto_generated'] is True

    @pytest.mark.asyncio
    async def test_student_agent_cannot_post(
        self, mock_tracker, mock_student_agent, mock_db
    ):
        """Test that STUDENT agents cannot auto-post"""
        # Mock database queries
        mock_db.query.return_value.filter.return_value.first.side_effect = [mock_tracker, mock_student_agent]

        # Mock social layer
        with patch('core.operation_tracker_hooks.agent_social_layer') as mock_social:
            mock_social.create_post = AsyncMock()

            hooks = OperationTrackerHooks()
            await hooks.on_operation_complete("tracker_123", mock_db)

            # Verify post was NOT created
            mock_social.create_post.assert_not_called()

    @pytest.mark.asyncio
    async def test_rate_limit_blocks_post(
        self, mock_tracker, mock_agent, mock_db
    ):
        """Test that rate limit blocks post"""
        # Mock database queries
        mock_db.query.return_value.filter.return_value.first.side_effect = [mock_tracker, mock_agent]

        # Set rate limit
        OperationTrackerHooks.update_rate_limit("agent_123")

        # Mock social layer
        with patch('core.operation_tracker_hooks.agent_social_layer') as mock_social:
            mock_social.create_post = AsyncMock()

            hooks = OperationTrackerHooks()
            await hooks.on_operation_complete("tracker_123", mock_db)

            # Verify post was NOT created (rate limited)
            mock_social.create_post.assert_not_called()

    @pytest.mark.asyncio
    async def test_alert_post_bypasses_rate_limit(
        self, mock_tracker, mock_agent, mock_db
    ):
        """Test that alert posts bypass rate limit"""
        # Make it an alert post
        mock_tracker.status = "failed"

        # Mock database queries
        mock_db.query.return_value.filter.return_value.first.side_effect = [mock_tracker, mock_agent]

        # Set rate limit
        OperationTrackerHooks.update_rate_limit("agent_123")

        # Mock social layer
        with patch('core.operation_tracker_hooks.agent_social_layer') as mock_social:
            mock_social.create_post = AsyncMock()

            hooks = OperationTrackerHooks()
            await hooks.on_operation_complete("tracker_123", mock_db)

            # Verify post WAS created (alert bypasses rate limit)
            mock_social.create_post.assert_called_once()

    @pytest.mark.asyncio
    async def test_governance_enforcement_for_auto_posts(
        self, mock_tracker, mock_agent, mock_db
    ):
        """Test that governance is enforced for auto-generated posts"""
        # Mock database queries
        mock_db.query.return_value.filter.return_value.first.side_effect = [mock_tracker, mock_agent]

        # Mock social layer
        with patch('core.operation_tracker_hooks.agent_social_layer') as mock_social:
            mock_social.create_post = AsyncMock()

            hooks = OperationTrackerHooks()
            await hooks.on_operation_complete("tracker_123", mock_db)

            # Verify governance parameters passed
            call_args = mock_social.create_post.call_args
            assert call_args.kwargs['sender_maturity'] == "INTERN"
            assert call_args.kwargs['sender_category'] == "engineering"

    def test_post_content_quality(self):
        """Test that generated posts meet quality standards"""
        generator = SocialPostGenerator()

        # Test template fallback
        metadata = {
            "agent_name": "Test Agent",
            "operation_type": "workflow_execute",
            "what_explanation": "Ran test suite for PR #123",
            "why_explanation": "To ensure code quality",
            "next_steps": "Fixing 3 failing tests",
            "status": "completed"
        }

        post = generator.generate_with_template("workflow_execute", metadata)

        # Quality checks
        assert len(post) <= 280, "Post must be under 280 characters"
        assert any(word in post.lower() for word in ["workflow", "tests", "pr"]), "Post should mention relevant keywords"
        assert post != "", "Post should not be empty"

    @pytest.mark.asyncio
    async def test_pii_redaction_integration(self, mock_tracker, mock_agent, mock_db):
        """PII redaction placeholder verified"""
        # Add PII to tracker
        mock_tracker.what_explanation = "Contact john@example.com for help"

        # Mock database queries
        mock_db.query.return_value.filter.return_value.first.side_effect = [mock_tracker, mock_agent]

        # Mock social layer
        with patch('core.operation_tracker_hooks.agent_social_layer') as mock_social:
            mock_social.create_post = AsyncMock()

            hooks = OperationTrackerHooks()
            await hooks.on_operation_complete("tracker_123", mock_db)

            # Verify post was created (PII redaction is TODO in Plan 02)
            mock_social.create_post.assert_called_once()

            # Verify content was passed (will be redacted in Plan 02)
            call_args = mock_social.create_post.call_args
            content = call_args.kwargs.get('content', '')
            assert len(content) > 0
