"""
Social Post Generator - GPT-4.1 mini integration for natural language post generation.

Converts AgentOperationTracker metadata into engaging social posts using GPT-4.1 mini.
Falls back to template-based generation if LLM unavailable.
"""

import os
import asyncio
import logging
from typing import Optional
from datetime import datetime, timedelta

try:
    import openai
    from openai import AsyncOpenAI
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False

from sqlalchemy.orm import Session
from core.models import AgentOperationTracker, AgentRegistry


logger = logging.getLogger(__name__)


class SocialPostGenerator:
    """
    Generate social posts from agent operations using GPT-4.1 mini.

    Features:
    - GPT-4.1 mini integration ($0.15/1M input, $0.60/1M output tokens)
    - 5-second timeout with fallback to templates
    - Significant operation detection
    - Template-based fallback generation
    - PII-aware generation (external redaction required)
    """

    # Significant operation types that warrant social posts
    SIGNIFICANT_OPERATIONS = {
        "workflow_execute",
        "integration_connect",
        "browser_automate",
        "report_generate",
        "human_feedback_received",
        "approval_requested",
        "agent_to_agent_call"
    }

    # Template fallbacks for when LLM unavailable
    TEMPLATES = {
        "completed": "Just finished {operation_type}! {what_explanation} #automation",
        "working": "Working on {operation_type}: {next_steps}",
        "default": "{agent_name} completed {operation_type} - {why_explanation}"
    }

    def __init__(self):
        self.llm_enabled = os.getenv("SOCIAL_POST_LLM_ENABLED", "true").lower() == "true"
        self.rate_limit_minutes = int(os.getenv("SOCIAL_POST_RATE_LIMIT_MINUTES", "5"))

        # Rate limiting tracker: {agent_id: last_post_timestamp}
        self._rate_limit_tracker = {}  # type: Dict[str, datetime]

        # Initialize OpenAI client if available
        self._openai_client = None
        if OPENAI_AVAILABLE and os.getenv("OPENAI_API_KEY"):
            try:
                self._openai_client = AsyncOpenAI(
                    api_key=os.getenv("OPENAI_API_KEY"),
                    timeout=5.0  # 5-second timeout
                )
                logger.info("SocialPostGenerator: GPT-4.1 mini client initialized")
            except Exception as e:
                logger.warning(f"SocialPostGenerator: Failed to initialize OpenAI client: {e}")
                self._openai_client = None
        else:
            logger.warning("SocialPostGenerator: OPENAI_API_KEY not set, using templates only")

    def is_significant_operation(self, tracker: AgentOperationTracker) -> bool:
        """
        Determine if operation warrants a social post.

        Args:
            tracker: AgentOperationTracker instance

        Returns:
            True if operation is significant enough for social post
        """
        # Check if operation type is significant
        if tracker.operation_type not in self.SIGNIFICANT_OPERATIONS:
            return False

        # Check if status indicates completion
        if tracker.status == "completed":
            return True

        # Check if approval requested (always significant)
        if tracker.operation_type == "approval_requested":
            return True

        # Check if agent-to-agent call (always significant)
        if tracker.operation_type == "agent_to_agent_call":
            return True

        return False

    def is_rate_limited(self, agent_id: str) -> bool:
        """
        Check if agent is rate limited for posting.

        Args:
            agent_id: Agent ID to check

        Returns:
            True if agent should be rate limited
        """
        if agent_id not in self._rate_limit_tracker:
            return False

        last_post = self._rate_limit_tracker[agent_id]
        time_since_last = datetime.utcnow() - last_post

        if time_since_last < timedelta(minutes=self.rate_limit_minutes):
            return True

        return False

    def update_rate_limit(self, agent_id: str) -> None:
        """
        Update rate limit tracker for agent.

        Args:
            agent_id: Agent ID to update
        """
        self._rate_limit_tracker[agent_id] = datetime.utcnow()

        # Cleanup old entries (older than 1 hour)
        cutoff = datetime.utcnow() - timedelta(hours=1)
        self._rate_limit_tracker = {
            k: v for k, v in self._rate_limit_tracker.items()
            if v > cutoff
        }

    async def generate_from_operation(
        self,
        tracker: AgentOperationTracker,
        agent: AgentRegistry
    ) -> str:
        """
        Generate natural language post from operation metadata using GPT-4.1 mini.

        Args:
            tracker: AgentOperationTracker instance
            agent: AgentRegistry instance

        Returns:
            Generated social post content

        Raises:
            ValueError: If required fields missing
        """
        # Validate required fields
        if not tracker.what_explanation:
            raise ValueError("what_explanation is required for post generation")

        # Try GPT-4.1 mini if enabled and available
        if self.llm_enabled and self._openai_client:
            try:
                return await self._generate_with_llm(tracker, agent)
            except asyncio.TimeoutError:
                logger.warning("SocialPostGenerator: LLM timeout, using template fallback")
            except Exception as e:
                logger.warning(f"SocialPostGenerator: LLM generation failed: {e}, using template")

        # Fallback to template-based generation
        return self.generate_with_template(tracker.operation_type, {
            "agent_name": agent.name,
            "operation_type": tracker.operation_type,
            "what_explanation": tracker.what_explanation,
            "why_explanation": tracker.why_explanation or "",
            "next_steps": tracker.next_steps or "",
            "status": tracker.status
        })

    async def _generate_with_llm(
        self,
        tracker: AgentOperationTracker,
        agent: AgentRegistry
    ) -> str:
        """
        Generate post using GPT-4.1 mini.

        Args:
            tracker: AgentOperationTracker instance
            agent: AgentRegistry instance

        Returns:
            Generated social post content

        Raises:
            asyncio.TimeoutError: If generation takes >5 seconds
        """
        if not self._openai_client:
            raise ValueError("OpenAI client not initialized")

        # Build prompt
        system_prompt = """You are an AI agent posting to a team social feed. Your posts should:
- Be casual and friendly (like a helpful teammate)
- Use emoji if appropriate (max 2 per post)
- Be under 280 characters
- Avoid technical jargon
- Focus on value delivered to the team"""

        user_prompt = f"""Generate a social post for this operation:

Agent: {agent.name}
Operation: {tracker.operation_type}
What I did: {tracker.what_explanation}
Why: {tracker.why_explanation or 'N/A'}
Next steps: {tracker.next_steps or 'N/A'}

Make it engaging and team-focused. Keep it under 280 characters."""

        try:
            # Call GPT-4.1 mini with timeout
            response = await asyncio.wait_for(
                self._openai_client.chat.completions.create(
                    model="gpt-4.1-mini",  # $0.15/1M input, $0.60/1M output
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt}
                    ],
                    max_tokens=100,
                    temperature=0.7  # Creative but consistent
                ),
                timeout=5.0  # 5-second timeout
            )

            content = response.choices[0].message.content.strip()

            # Validate length
            if len(content) > 280:
                logger.warning(f"Generated post too long ({len(content)} chars), truncating")
                content = content[:277] + "..."

            return content

        except asyncio.TimeoutError:
            raise
        except openai.APIError as e:
            logger.error(f"OpenAI API error: {e}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error during LLM generation: {e}")
            raise

    def generate_with_template(
        self,
        operation_type: str,
        metadata: dict
    ) -> str:
        """
        Generate post using template fallback.

        Args:
            operation_type: Type of operation
            metadata: Operation metadata dict

        Returns:
            Generated social post content
        """
        status = metadata.get("status", "running")

        # Select template based on status
        if status == "completed":
            template = self.TEMPLATES["completed"]
        elif status == "running":
            template = self.TEMPLATES["working"]
        else:
            template = self.TEMPLATES["default"]

        # Fill template with metadata
        try:
            post = template.format(**metadata)

            # Ensure length limit
            if len(post) > 280:
                post = post[:277] + "..."

            return post

        except KeyError as e:
            logger.warning(f"Template missing key {e}, using default")
            return f"{metadata.get('agent_name', 'Agent')} working on {operation_type}"


# Global service instance
social_post_generator = SocialPostGenerator()
