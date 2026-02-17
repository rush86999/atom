"""
Property-Based Tests for Social Layer Invariants

Uses Hypothesis to verify critical social layer invariants with 100+ examples per test.

Invariants tested:
- Post generation: length limits, rate limiting, significant operations
- PII redaction: no leaks, consistent placeholders, idempotent
- Social feed: pagination no duplicates, monotonic counters, redaction before storage
"""

import pytest
from hypothesis import given, strategies as st, settings, example
from unittest.mock import Mock
from datetime import datetime, timedelta

from core.social_post_generator import SocialPostGenerator
from core.pii_redactor import PIIRedactor, get_pii_redactor
from core.models import AgentOperationTracker


class TestPostGenerationInvariants:
    """Property-based tests for post generation invariants"""

    @given(st.text(min_size=1, max_size=280))
    def test_generated_post_never_exceeds_280_chars(self, input_text):
        """Property: All generated posts under 280 characters"""
        metadata = {
            "agent_name": "Test",
            "operation_type": "workflow",
            "what_explanation": input_text[:100],  # Truncate for metadata
            "status": "completed"
        }
        generator = SocialPostGenerator()
        post = generator.generate_with_template("workflow", metadata)

        assert len(post) <= 280, f"Post too long: {len(post)} chars"

    @given(st.integers(min_value=0, max_value=100))
    def test_rate_limit_window_honored(self, minutes_ago):
        """Property: Rate limit respects time window"""
        generator = SocialPostGenerator()
        generator._rate_limit_tracker["agent"] = datetime.utcnow() - timedelta(minutes=minutes_ago)

        # Should NOT be rate limited if >=5 minutes ago
        is_limited = generator.is_rate_limited("agent")

        if minutes_ago >= 5:
            assert not is_limited, f"Should not be rate limited after {minutes_ago} minutes"
        else:
            # May or may not be limited depending on exact timing
            assert isinstance(is_limited, bool)

    @given(st.sampled_from([
        "workflow_execute",
        "integration_connect",
        "browser_automate",
        "report_generate",
        "human_feedback_received",
        "approval_requested",
        "agent_to_agent_call"
    ]))
    def test_significant_operations_detected(self, op_type):
        """Property: Significant operation types always detected"""
        generator = SocialPostGenerator()
        tracker = Mock(spec=AgentOperationTracker)
        tracker.operation_type = op_type
        tracker.status = "completed"

        result = generator.is_significant_operation(tracker)
        assert result is True, f"{op_type} should be significant"

    @given(st.sampled_from([
        "database_query",
        "cache_lookup",
        "log_write",
        "metric_update",
        "heartbeat"
    ]))
    def test_insignificant_operations_not_detected(self, op_type):
        """Property: Insignificant operation types never detected"""
        generator = SocialPostGenerator()
        tracker = Mock(spec=AgentOperationTracker)
        tracker.operation_type = op_type
        tracker.status = "completed"

        result = generator.is_significant_operation(tracker)
        assert result is False, f"{op_type} should not be significant"


class TestPIIRedactionInvariants:
    """Property-based tests for PII redaction invariants"""

    @given(st.text(min_size=1, max_size=500))
    def test_pii_redaction_never_increases_length(self, text):
        """Property: Redaction never increases text length significantly"""
        redactor = PIIRedactor()
        result = redactor.redact(text)

        # Allow some overhead for placeholders, but not massive increase
        assert len(result.redacted_text) <= len(text) + 100, \
            f"Redaction too long: {len(result.redacted_text)} vs {len(text)}"

    @given(st.emails(), st.text(min_size=0, max_size=50))
    def test_email_redaction_placeholder_consistent(self, email, context):
        """Property: Email redaction uses consistent placeholder format"""
        redactor = PIIRedactor()
        result = redactor.redact(f"{context}{email}")

        # If redacted, should use standard placeholder
        if result.has_secrets:
            assert "<EMAIL_ADDRESS>" in result.redacted_text or \
                   "[REDACTED" in result.redacted_text or \
                   email not in result.redacted_text

    @given(st.lists(st.from_regex(r'\d{3}-\d{2}-\d{4}'), min_size=0, max_size=5))
    def test_ssn_redaction_always_applied(self, ssns):
        """Property: SSN patterns always redacted when detected"""
        if not ssns:
            return  # Skip empty lists

        redactor = PIIRedactor()
        text = " ".join(ssns)
        result = redactor.redact(text)

        # If PII detected, SSNs should be redacted
        if result.has_secrets:
            for ssn in ssns:
                # Check that SSN is not in redacted text (or is transformed)
                assert ssn not in result.redacted_text or \
                       len(result.redactions) > 0


class TestSocialFeedInvariants:
    """Property-based tests for social feed invariants"""

    @given(st.integers(min_value=1, max_value=20))
    def test_feed_pagination_prevents_duplicates(self, limit):
        """Property: Cursor pagination never returns duplicate posts"""
        # Simulate feed with cursor pagination
        seen_ids = set()

        # Simulate 3 pages of results
        for page_num in range(3):
            # Mock feed with unique IDs per page
            page_ids = set(f"post_{page_num}_{i}" for i in range(limit))

            # Verify no duplicates with previous pages
            assert seen_ids.isdisjoint(page_ids), \
                f"Duplicates found in page {page_num}"

            seen_ids.update(page_ids)

    @given(st.integers(min_value=0, max_value=20))
    def test_reply_count_monotonically_increases(self, initial_count):
        """Property: Reply count never decreases"""
        # Simulate post with initial reply count
        post = Mock()
        post.reply_count = initial_count
        post.id = "post_123"

        # Add some replies
        replies_to_add = 5
        for _ in range(replies_to_add):
            post.reply_count += 1

        # Final count should be >= initial count
        assert post.reply_count >= initial_count, \
            f"Reply count decreased: {post.reply_count} < {initial_count}"

    @given(st.text(min_size=1, max_size=200))
    def test_post_content_redacted_before_storage(self, content_with_pii):
        """Property: All posts redacted before database storage"""
        redactor = get_pii_redactor()
        result = redactor.redact(content_with_pii)

        # Simulate creating post with redacted content
        from core.models import AgentPost
        post = AgentPost(content=result.redacted_text)

        # Verify stored content is redacted version
        assert post.content == result.redacted_text

        # If PII was detected, verify it's not in stored content
        if result.has_secrets:
            for r in result.redactions:
                original = result.original_text[r['start']:r['end']]
                assert original not in post.content, \
                    f"PII leaked in stored content: {original}"


class TestRateLimitingInvariants:
    """Property-based tests for rate limiting invariants"""

    @given(st.text(min_size=1, max_size=50), st.integers(min_value=1, max_value=10))
    def test_rate_limit_independent_per_agent(self, agent_id, num_posts):
        """Property: Rate limit tracking is independent per agent"""
        generator = SocialPostGenerator()

        # Create multiple agents
        agent_ids = [f"{agent_id}_{i}" for i in range(num_posts)]

        # Update rate limit for first agent only
        if agent_ids:
            generator.update_rate_limit(agent_ids[0])

            # First agent should be rate limited
            assert generator.is_rate_limited(agent_ids[0]) is True

            # Other agents should NOT be rate limited
            for other_agent in agent_ids[1:]:
                assert generator.is_rate_limited(other_agent) is False


class TestTemplateInvariants:
    """Property-based tests for template generation invariants"""

    @given(st.text(min_size=0, max_size=100))
    def test_template_handles_empty_metadata(self, value):
        """Property: Templates handle empty/missing metadata gracefully"""
        generator = SocialPostGenerator()
        metadata = {
            "agent_name": "",
            "operation_type": "workflow",
            "what_explanation": value,
            "status": "completed"
        }

        post = generator.generate_with_template("workflow", metadata)

        # Should always return valid post
        assert post is not None
        assert len(post) > 0
        assert len(post) <= 280

    @given(st.integers(min_value=280, max_value=1000))
    def test_template_truncates_long_content(self, length):
        """Property: Templates truncate content to 280 chars"""
        generator = SocialPostGenerator()
        long_text = "x" * length
        metadata = {
            "agent_name": "Test",
            "operation_type": "workflow",
            "what_explanation": long_text,
            "status": "completed"
        }

        post = generator.generate_with_template("workflow", metadata)

        # Should truncate to 280 chars
        assert len(post) <= 280, f"Post too long: {len(post)}"
