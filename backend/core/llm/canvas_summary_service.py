"""
Canvas Summary Service

Generates LLM-powered semantic summaries of canvas presentations for
episodic memory enhancement. Replaces Phase 20's metadata extraction
with richer context capture.

Features:
- Canvas-specific prompts for all 7 canvas types
- BYOK integration for multi-provider LLM support
- Caching to avoid redundant generation
- Fallback to metadata extraction if LLM fails
- Cost tracking for per-episode summary generation
"""

import asyncio
import hashlib
import json
import logging
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

# Import at runtime to avoid circular dependencies
BYOKHandler = None


class CanvasSummaryService:
    """
    LLM-powered canvas presentation summary service.

    Generates semantically rich descriptions (50-100 words) that capture:
    - What was presented (canvas type, key elements, data)
    - Why it mattered (business context, decision required, risks)
    - Critical data (metrics, amounts, deadlines, stakeholders)
    - User decision (what the user did)

    Falls back to metadata extraction if LLM fails or times out.
    """

    # Canvas-specific extraction guidance
    _CANVAS_PROMPTS = {
        "generic": (
            "Focus on: Generic canvas content, purpose, key elements.\n"
            "Extract: canvas_title, components, interaction_type, main_purpose."
        ),
        "orchestration": (
            "Focus on: Workflow details, approval amounts, stakeholders, risks, decision context.\n"
            "Extract: workflow_id, approval_amount, approvers, blockers, deadline."
        ),
        "sheets": (
            "Focus on: Data values, calculations, trends, notable entries.\n"
            "Extract: revenue, amounts, key_metrics, data_points."
        ),
        "terminal": (
            "Focus on: Command output, errors, test results, deployment status.\n"
            "Extract: command, exit_code, error_lines, test_counts, blocking_issues."
        ),
        "docs": (
            "Focus on: Document content, sections, key information.\n"
            "Extract: document_title, sections, word_count, key_topics."
        ),
        "email": (
            "Focus on: Email composition, recipients, subject, attachments.\n"
            "Extract: to, cc, subject, attachment_count, draft_status."
        ),
        "coding": (
            "Focus on: Code content, language, syntax elements.\n"
            "Extract: language, line_count, functions, syntax_errors."
        ),
    }

    def __init__(self, byok_handler: Any):
        """
        Initialize canvas summary service.

        Args:
            byok_handler: BYOK handler for LLM generation
        """
        self.byok_handler = byok_handler
        self._summary_cache: Dict[str, str] = {}
        self._cost_tracker: Dict[str, float] = {}

    async def generate_summary(
        self,
        canvas_type: str,
        canvas_state: Dict[str, Any],
        agent_task: Optional[str] = None,
        user_interaction: Optional[str] = None,
        timeout_seconds: int = 2
    ) -> str:
        """
        Generate LLM-powered semantic summary of canvas presentation.

        Args:
            canvas_type: One of 7 canvas types (generic, docs, email, sheets,
                        orchestration, terminal, coding)
            canvas_state: Canvas state from accessibility tree or state API
            agent_task: Optional task description for context
            user_interaction: Optional user action (submit, close, update, execute)
            timeout_seconds: LLM generation timeout (default 2s)

        Returns:
            Semantic summary (50-100 words) or metadata fallback

        Raises:
            ValueError: If canvas_type is not one of 7 supported types
        """
        # Validate canvas type
        valid_types = list(self._CANVAS_PROMPTS.keys())
        if canvas_type not in valid_types:
            raise ValueError(
                f"Invalid canvas_type '{canvas_type}'. "
                f"Must be one of: {', '.join(valid_types)}"
            )

        # Generate cache key from all inputs
        cache_key = hashlib.sha256(
            json.dumps({
                "canvas_type": canvas_type,
                "canvas_state": canvas_state,
                "agent_task": agent_task,
                "user_interaction": user_interaction
            }, sort_keys=True).encode()
        ).hexdigest()[:16]

        # Check cache
        if cache_key in self._summary_cache:
            logger.debug(f"Cache hit for canvas summary: {cache_key}")
            return self._summary_cache[cache_key]

        # Generate summary with LLM
        try:
            prompt = self._build_prompt(canvas_type, canvas_state, agent_task, user_interaction)

            summary = await asyncio.wait_for(
                self.byok_handler.generate_response(
                    prompt=prompt,
                    system_instruction="You are a canvas presentation analyzer. Generate concise semantic summaries (50-100 words).",
                    temperature=0.0,  # Deterministic for consistency
                    task_type="analysis"
                ),
                timeout=timeout_seconds
            )

            # Cache the result
            self._summary_cache[cache_key] = summary

            # Track cost (BYOK handler tracks internally)
            session_key = f"{canvas_type}_{cache_key}"
            self._cost_tracker[session_key] = 0.0  # Updated by BYOK handler

            logger.info(f"Generated LLM summary for {canvas_type} canvas: {cache_key}")
            return summary

        except asyncio.TimeoutError:
            logger.warning(f"LLM summary generation timed out after {timeout_seconds}s")
            return self._fallback_to_metadata(canvas_type, canvas_state)

        except Exception as e:
            logger.error(f"LLM summary generation failed: {e}")
            return self._fallback_to_metadata(canvas_type, canvas_state)

    def _build_prompt(
        self,
        canvas_type: str,
        canvas_state: Dict[str, Any],
        agent_task: Optional[str],
        user_interaction: Optional[str]
    ) -> str:
        """
        Build LLM prompt with canvas context.

        Args:
            canvas_type: Canvas type
            canvas_state: Canvas state dictionary
            agent_task: Optional agent task description
            user_interaction: Optional user interaction

        Returns:
            Complete LLM prompt
        """
        # Get canvas-specific instructions
        canvas_instructions = self._CANVAS_PROMPTS.get(canvas_type, "")

        prompt = f"""You are analyzing a canvas presentation from an AI agent interaction. Generate a concise semantic summary (50-100 words) that captures:

1. **What was presented**: Canvas type, key elements, data shown
2. **Why it mattered**: Business context, decision required, risks highlighted
3. **Critical data**: Key metrics, amounts, deadlines, stakeholders
4. **User decision**: What the user did (if applicable)

**Canvas Type**: {canvas_type}
**Agent Task**: {agent_task or "Not specified"}
**Canvas State**: {json.dumps(canvas_state, indent=2)}
**User Interaction**: {user_interaction or "None"}

{canvas_instructions}

**Summary**:"""

        return prompt

    def _fallback_to_metadata(
        self,
        canvas_type: str,
        canvas_state: Dict[str, Any]
    ) -> str:
        """
        Fallback to metadata extraction if LLM fails.

        Replicates Phase 20 behavior for reliability.

        Args:
            canvas_type: Canvas type
            canvas_state: Canvas state dictionary

        Returns:
            Metadata-based summary (30-50 words)
        """
        # Extract visual elements
        components = canvas_state.get("components", [])
        visual_elements = ", ".join([c.get("type", "element") for c in components[:3]])

        # Extract critical data
        critical_data = []
        if "workflow_id" in canvas_state:
            critical_data.append(f"workflow {canvas_state['workflow_id']}")
        if "revenue" in canvas_state:
            critical_data.append(f"${canvas_state['revenue']}")
        if "amount" in canvas_state:
            critical_data.append(f"${canvas_state['amount']}")
        if "command" in canvas_state:
            critical_data.append(f"command: {canvas_state['command']}")

        # Build summary
        if visual_elements:
            summary = f"Agent presented {visual_elements} on {canvas_type} canvas"
        else:
            summary = f"Agent presented {canvas_type} canvas"

        if critical_data:
            summary += f" with {', '.join(critical_data)}"

        logger.info(f"Used metadata fallback for {canvas_type} canvas")
        return summary
