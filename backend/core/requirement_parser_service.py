"""
Requirement Parser Service for Autonomous Coding Agents

Converts natural language feature requests into structured requirements with:
- User stories (role/action/value format)
- Acceptance criteria (Gherkin format: Given/When/Then)
- Dependency identification
- Integration point detection
- Complexity estimation

Integration:
- Uses BYOK handler for LLM provider routing
- Stores parsed requirements in AutonomousWorkflow model
- Follows INVEST principles for user story validation

Performance targets:
- Requirements parsing: <5 minutes
- Acceptance criteria extraction: Gherkin format
- Complexity estimation: simple/moderate/complex/advanced
"""

import asyncio
import json
import logging
import re
from datetime import datetime
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from core.llm.byok_handler import BYOKHandler
from core.models import AutonomousWorkflow

logger = logging.getLogger(__name__)


# System prompt for requirements parsing
REQUIREMENT_PARSER_SYSTEM_PROMPT = """
You are a requirements analyst specializing in software development. Your task is to parse natural language feature requests into structured requirements.

Output format (JSON):
{
  "user_stories": [
    {
      "id": "US-001",
      "title": "Brief title",
      "role": "user|admin|developer",
      "action": "action the user wants to perform",
      "value": "business value or benefit",
      "acceptance_criteria": [
        "Given precondition",
        "When action is taken",
        "Then expected outcome"
      ],
      "priority": "high|medium|low",
      "complexity": "simple|moderate|complex|advanced"
    }
  ],
  "dependencies": [
    "External dependency or service needed"
  ],
  "integration_points": [
    "API endpoint or system to integrate with"
  ],
  "estimated_complexity": "simple|moderate|complex|advanced",
  "estimated_time": "Time estimate (e.g., '4-6 hours')"
}

Guidelines:
1. Follow INVEST principles (Independent, Negotiable, Valuable, Estimable, Small, Testable)
2. Use Gherkin format for acceptance criteria (Given/When/Then)
3. Identify dependencies (OAuth credentials, database tables, external services)
4. List integration points (API endpoints, database models, frontend components)
5. Estimate complexity based on feature scope and dependencies
6. Be specific and actionable

Complexity levels:
- simple: <50 tokens, 1-2 dependencies, 1-2 hours
- moderate: 50-150 tokens, 3-5 dependencies, 4-6 hours
- complex: 150-300 tokens, 5-10 dependencies, 1-2 days
- advanced: 300+ tokens, 10+ dependencies, 2+ days
"""


class RequirementParserService:
    """
    Service for parsing natural language feature requests into structured requirements.

    Uses LLM (via BYOK handler) to extract:
    - User stories with role/action/value format
    - Acceptance criteria in Gherkin format
    - Dependencies and integration points
    - Complexity estimation

    Attributes:
        db: SQLAlchemy database session
        byok_handler: BYOK handler for LLM provider routing

    Example:
        ```python
        parser = RequirementParserService(db, byok_handler)
        result = await parser.parse_requirements(
            feature_request="Add OAuth2 login with Google",
            workspace_id="default"
        )
        ```
    """

    def __init__(self, db: Session, byok_handler: BYOKHandler):
        """
        Initialize RequirementParserService.

        Args:
            db: SQLAlchemy database session
            byok_handler: BYOK handler for LLM provider routing
        """
        self.db = db
        self.byok_handler = byok_handler

    async def parse_requirements(
        self,
        feature_request: str,
        workspace_id: str,
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Parse natural language feature request into structured requirements.

        Uses LLM to extract user stories, acceptance criteria, dependencies,
        and integration points. Follows INVEST principles for validation.

        Args:
            feature_request: Natural language feature request (e.g., "Add OAuth2 login")
            workspace_id: Workspace identifier for multi-tenancy
            context: Optional additional context (priority, deadline, constraints)

        Returns:
            Dictionary with parsed requirements:
            {
                "user_stories": [...],
                "dependencies": [...],
                "integration_points": [...],
                "estimated_complexity": "moderate",
                "estimated_time": "4-6 hours"
            }

        Raises:
            ValueError: If feature_request is empty or invalid
            Exception: If LLM parsing fails
        """
        if not feature_request or not feature_request.strip():
            raise ValueError("Feature request cannot be empty")

        logger.info(f"Parsing requirements for: {feature_request[:100]}...")

        # Prepare prompt with context
        user_prompt = self._build_prompt(feature_request, context)

        try:
            # Call LLM via BYOK handler (prefer Anthropic for intent understanding)
            llm_response = await self._call_llm(user_prompt)

            # Parse LLM response into structured requirements
            requirements = self._parse_llm_response(llm_response)

            # Validate and enhance requirements
            requirements = self._validate_requirements(requirements, feature_request)

            # Estimate complexity if not provided
            if "estimated_complexity" not in requirements:
                requirements["estimated_complexity"] = self._estimate_complexity(
                    requirements.get("user_stories", [])
                )

            logger.info(
                f"Successfully parsed {len(requirements.get('user_stories', []))} user stories, "
                f"complexity: {requirements.get('estimated_complexity')}"
            )

            return requirements

        except Exception as e:
            logger.error(f"Failed to parse requirements: {e}")
            raise

    def _build_prompt(
        self,
        feature_request: str,
        context: Optional[Dict[str, Any]]
    ) -> str:
        """
        Build LLM prompt with feature request and context.

        Args:
            feature_request: Natural language feature request
            context: Optional additional context

        Returns:
            Formatted prompt string
        """
        prompt = f"""Feature Request: {feature_request}"""

        if context:
            prompt += "\n\nAdditional Context:"
            for key, value in context.items():
                prompt += f"\n- {key}: {value}"

        prompt += "\n\nParse this into structured requirements following the specified format."

        return prompt

    async def _call_llm(self, user_prompt: str) -> str:
        """
        Call LLM via BYOK handler for requirement parsing.

        Prefers Anthropic Claude for intent understanding.
        Falls back to other providers if unavailable.

        Args:
            user_prompt: User prompt to send to LLM

        Returns:
            LLM response text

        Raises:
            Exception: If LLM call fails
        """
        try:
            # Prefer Anthropic for parsing (best intent understanding)
            # Use chat completion interface
            response = await self.byok_handler.acomplete(
                prompt=user_prompt,
                system_prompt=REQUIREMENT_PARSER_SYSTEM_PROMPT,
                provider_id="anthropic",  # Prefer Anthropic
                model="claude-3-5-sonnet-20241022",  # Sonnet for good balance of speed/quality
                temperature=0.0,  # Deterministic output
                max_tokens=2000
            )

            return response

        except Exception as e:
            logger.warning(f"Anthropic call failed, trying fallback: {e}")
            # Fallback to OpenAI
            try:
                response = await self.byok_handler.acomplete(
                    prompt=user_prompt,
                    system_prompt=REQUIREMENT_PARSER_SYSTEM_PROMPT,
                    provider_id="openai",
                    model="gpt-4o-mini",
                    temperature=0.0,
                    max_tokens=2000
                )
                return response
            except Exception as e2:
                logger.error(f"LLM call failed completely: {e2}")
                raise Exception(f"Failed to get LLM response: {e2}")

    def _parse_llm_response(self, llm_response: str) -> Dict[str, Any]:
        """
        Parse LLM response into structured requirements.

        Extracts JSON from LLM response, handling various formats.

        Args:
            llm_response: Raw LLM response text

        Returns:
            Parsed requirements dictionary

        Raises:
            ValueError: If JSON parsing fails
        """
        # Try to extract JSON from response
        # LLM may wrap JSON in markdown code blocks
        json_match = re.search(r'```json\s*(.*?)\s*```', llm_response, re.DOTALL)
        if json_match:
            llm_response = json_match.group(1)

        # Try without language specifier
        json_match = re.search(r'```\s*(.*?)\s*```', llm_response, re.DOTALL)
        if json_match:
            llm_response = json_match.group(1)

        try:
            requirements = json.loads(llm_response)
            return requirements
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON from LLM response: {e}")
            logger.debug(f"LLM response: {llm_response[:500]}...")
            raise ValueError(f"Invalid JSON in LLM response: {e}")

    def _validate_requirements(
        self,
        requirements: Dict[str, Any],
        original_request: str
    ) -> Dict[str, Any]:
        """
        Validate and enhance parsed requirements.

        Ensures required fields exist, validates formats,
        and adds missing metadata.

        Args:
            requirements: Parsed requirements dictionary
            original_request: Original feature request for reference

        Returns:
            Validated requirements dictionary
        """
        # Ensure required top-level fields exist
        if "user_stories" not in requirements:
            requirements["user_stories"] = []
        if "dependencies" not in requirements:
            requirements["dependencies"] = []
        if "integration_points" not in requirements:
            requirements["integration_points"] = []

        # Validate user stories
        for i, story in enumerate(requirements.get("user_stories", [])):
            # Ensure required fields
            if "id" not in story:
                story["id"] = f"US-{i+1:03d}"
            if "title" not in story:
                story["title"] = original_request[:50]
            if "role" not in story:
                story["role"] = "user"
            if "priority" not in story:
                story["priority"] = "medium"
            if "complexity" not in story:
                story["complexity"] = "moderate"
            if "acceptance_criteria" not in story:
                story["acceptance_criteria"] = []

        return requirements

    def _estimate_complexity(self, user_stories: List[Dict[str, Any]]) -> str:
        """
        Estimate complexity based on user stories and dependencies.

        Factors:
        - Number of user stories
        - Total dependencies across all stories
        - Average complexity per story

        Args:
            user_stories: List of user story dictionaries

        Returns:
            Complexity level: simple, moderate, complex, or advanced
        """
        if not user_stories:
            return "simple"

        story_count = len(user_stories)
        total_complexity = 0

        for story in user_stories:
            complexity = story.get("complexity", "moderate")
            # Map complexity to numeric score
            complexity_scores = {
                "simple": 1,
                "moderate": 2,
                "complex": 3,
                "advanced": 4
            }
            total_complexity += complexity_scores.get(complexity, 2)

        average_complexity = total_complexity / story_count

        # Determine overall complexity
        if story_count <= 2 and average_complexity <= 1.5:
            return "simple"
        elif story_count <= 5 and average_complexity <= 2.5:
            return "moderate"
        elif story_count <= 10 and average_complexity <= 3.5:
            return "complex"
        else:
            return "advanced"

    def _extract_user_stories(self, llm_response: str) -> List[Dict[str, Any]]:
        """
        Parse LLM response into structured user stories.

        Legacy method - use _parse_llm_response instead.

        Args:
            llm_response: LLM response text

        Returns:
            List of user story dictionaries
        """
        requirements = self._parse_llm_response(llm_response)
        return requirements.get("user_stories", [])

    def _extract_acceptance_criteria(self, llm_response: str) -> List[str]:
        """
        Extract Gherkin-style scenarios from LLM response.

        Legacy method - use _parse_llm_response instead.

        Args:
            llm_response: LLM response text

        Returns:
            List of Gherkin scenario strings
        """
        requirements = self._parse_llm_response(llm_response)
        criteria = []
        for story in requirements.get("user_stories", []):
            criteria.extend(story.get("acceptance_criteria", []))
        return criteria

    async def create_workflow(
        self,
        feature_request: str,
        workspace_id: str,
        parsed_requirements: Dict[str, Any]
    ) -> AutonomousWorkflow:
        """
        Create AutonomousWorkflow record with parsed requirements.

        Persists parsed requirements to database for tracking.

        Args:
            feature_request: Original feature request
            workspace_id: Workspace identifier
            parsed_requirements: Parsed requirements from parse_requirements()

        Returns:
            Created AutonomousWorkflow instance

        Raises:
            Exception: If database operation fails
        """
        try:
            workflow = AutonomousWorkflow(
                workspace_id=workspace_id,
                feature_request=feature_request,
                status="pending",
                requirements=parsed_requirements.get("requirements"),
                user_stories=parsed_requirements.get("user_stories"),
                acceptance_criteria=parsed_requirements.get("acceptance_criteria"),
                estimated_duration_seconds=self._estimate_duration(
                    parsed_requirements.get("estimated_time")
                ),
                started_at=datetime.utcnow()
            )

            self.db.add(workflow)
            self.db.commit()
            self.db.refresh(workflow)

            logger.info(f"Created AutonomousWorkflow {workflow.id} for feature request")

            return workflow

        except Exception as e:
            logger.error(f"Failed to create workflow: {e}")
            self.db.rollback()
            raise

    def _estimate_duration(self, estimated_time: Optional[str]) -> Optional[int]:
        """
        Parse time estimate string into seconds.

        Args:
            estimated_time: Time estimate string (e.g., "4-6 hours", "2 days")

        Returns:
            Duration in seconds, or None if not parseable
        """
        if not estimated_time:
            return None

        # Extract numbers and units
        # Pattern: "4-6 hours" -> [4, 6], "hours"
        match = re.search(r'(\d+)(?:-(\d+))?\s*(hour|hours|day|days|minute|minutes)', estimated_time, re.IGNORECASE)
        if not match:
            return None

        min_value = int(match.group(1))
        max_value = int(match.group(2)) if match.group(2) else min_value
        unit = match.group(3).lower()

        # Average value in seconds
        avg_value = (min_value + max_value) / 2

        # Convert to seconds
        multipliers = {
            "minute": 60,
            "minutes": 60,
            "hour": 3600,
            "hours": 3600,
            "day": 86400,
            "days": 86400
        }

        return int(avg_value * multipliers.get(unit, 3600))
