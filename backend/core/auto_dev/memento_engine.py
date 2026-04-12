"""
Memento Engine

Generates new skills from failed episodes. When an agent hits the same
failure pattern repeatedly, MementoEngine:

1. Analyzes the failure — extracts task description, error trace, tool calls
2. Proposes a skill — uses LLM to generate Python code that addresses the gap
3. Validates the skill — runs in sandbox against test inputs from the failure
4. Promotes the skill — registers via SkillBuilderService on user approval

This is the "Feature Expansion" phase — it creates NEW capabilities rather
than optimizing existing ones (which is AlphaEvolver's role).
"""

import logging
import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from core.auto_dev.base_engine import BaseLearningEngine, SandboxProtocol
from core.auto_dev.models import SkillCandidate

logger = logging.getLogger(__name__)


class MementoEngine(BaseLearningEngine):
    """
    Generates new skills from failed episodes.

    Lifecycle:
    1. analyze_episode() — extract failure pattern
    2. propose_code_change() — generate skill code via LLM
    3. validate_change() — test in sandbox
    4. promote_skill() — register via SkillBuilderService
    """

    def __init__(
        self,
        db: Session,
        llm_service: Any | None = None,
        sandbox: SandboxProtocol | None = None,
    ):
        super().__init__(db=db, llm_service=llm_service, sandbox=sandbox)

    async def analyze_episode(self, episode_id: str, **kwargs) -> dict[str, Any]:
        """
        Analyze a failed episode to extract the failure pattern.

        Returns:
            {
                "episode_id": str,
                "task_description": str,
                "error_trace": str,
                "tool_calls_attempted": list,
                "failure_summary": str,
                "suggested_skill_name": str,
            }
        """
        try:
            from core.models import AgentEpisode, EpisodeSegment

            episode = (
                self.db.query(AgentEpisode).filter(AgentEpisode.id == episode_id).first()
            )
            if not episode:
                return {"error": f"Episode {episode_id} not found"}

            segments = (
                self.db.query(EpisodeSegment)
                .filter(EpisodeSegment.episode_id == episode_id)
                .all()
            )

            # Extract failure information
            error_segments = [
                s
                for s in segments
                if getattr(s, "segment_type", "") in ("error", "failure", "skill_failure")
            ]

            error_trace = ""
            tool_calls = []
            for seg in segments:
                meta = getattr(seg, "metadata", {}) or {}
                if meta.get("error"):
                    error_trace += f"{meta['error']}\n"
                if meta.get("tool_name"):
                    tool_calls.append(
                        {
                            "tool_name": meta["tool_name"],
                            "status": meta.get("status", "unknown"),
                        }
                    )

            task_desc = episode.task_description or ""

            # Generate a suggested skill name from the task
            suggested_name = self._suggest_skill_name(task_desc, error_trace)

            return {
                "episode_id": episode_id,
                "agent_id": str(episode.agent_id) if episode.agent_id else None,
                "tenant_id": str(episode.user_id) if hasattr(episode, "user_id") else None,
                "task_description": task_desc,
                "error_trace": error_trace.strip(),
                "tool_calls_attempted": tool_calls,
                "error_segments_count": len(error_segments),
                "failure_summary": f"Failed: {task_desc[:100]}. Errors: {error_trace[:200]}",
                "suggested_skill_name": suggested_name,
            }
        except ImportError:
            logger.warning("Episode models not available")
            return {"episode_id": episode_id, "error": "Episode models not available"}

    async def propose_code_change(
        self, context: dict[str, Any], **kwargs
    ) -> str:
        """
        Generate a new skill script via LLM to address a failure pattern.

        Args:
            context: Analysis output from analyze_episode()

        Returns:
            Generated Python skill code
        """
        llm = self._get_llm_service()
        if not llm:
            return "# Skill generation skipped: LLM unavailable"

        task_desc = context.get("task_description", "Unknown task")
        error_trace = context.get("error_trace", "")
        tool_calls = context.get("tool_calls_attempted", [])

        system_prompt = (
            "You are the Memento Skill Generator. Your goal is to create a new "
            "Python utility function that addresses a gap in the agent's capabilities. "
            "The agent failed a task because it lacked the right tool. "
            "Create a self-contained Python function that accomplishes the task. "
            "Include clear docstrings and type hints. "
            "Respond ONLY with the Python code."
        )

        tool_context = ""
        if tool_calls:
            tool_list = ", ".join(t["tool_name"] for t in tool_calls)
            tool_context = f"\nTools attempted (all failed or insufficient): {tool_list}"

        user_prompt = (
            f"Task the agent failed at:\n{task_desc}\n\n"
            f"Error trace:\n{error_trace[:500]}\n"
            f"{tool_context}\n\n"
            "Generate a Python skill function that would let the agent "
            "succeed at this task. Include:\n"
            "- A clear function name\n"
            "- Input parameters with type hints\n"
            "- Error handling\n"
            "- A docstring explaining what it does\n\n"
            "Provide the code now:"
        )

        try:
            response = await llm.generate_completion(
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                model="auto",
                task_type="code",
            )
            return self._strip_markdown_fences(response.get("content", ""))
        except Exception as e:
            logger.error(f"Skill generation failed: {e}")
            return f"# Skill generation failed: {e}"

    async def validate_change(
        self,
        code: str,
        test_inputs: list[dict[str, Any]],
        tenant_id: str,
        **kwargs,
    ) -> dict[str, Any]:
        """Execute generated skill in sandbox and verify it works."""
        sandbox = self._get_sandbox()
        if not sandbox:
            return {"passed": False, "error": "Sandbox unavailable"}

        results = []
        all_passed = True

        for i, inputs in enumerate(test_inputs or [{}]):
            result = await sandbox.execute_raw_python(
                tenant_id=tenant_id,
                code=code,
                input_params=inputs,
            )
            passed = result.get("status") == "success"
            if not passed:
                all_passed = False
            results.append(
                {
                    "test_index": i,
                    "passed": passed,
                    "output": result.get("output", ""),
                    "execution_seconds": result.get("execution_seconds", 0),
                }
            )

        return {
            "passed": all_passed,
            "test_results": results,
        }

    # --- Memento-specific methods ---

    async def generate_skill_candidate(
        self,
        tenant_id: str,
        agent_id: str | None,
        episode_id: str,
        failure_analysis: dict[str, Any] | None = None,
    ) -> SkillCandidate:
        """
        Full pipeline: analyze episode → generate skill → store candidate.

        Returns a SkillCandidate with validation_status='pending'.
        """
        # Step 1: Analyze the episode if no analysis provided
        if failure_analysis is None:
            failure_analysis = await self.analyze_episode(episode_id)

        if "error" in failure_analysis:
            raise ValueError(f"Episode analysis failed: {failure_analysis['error']}")

        # Step 2: Generate skill code
        generated_code = await self.propose_code_change(failure_analysis)

        # Step 3: Create candidate record
        skill_name = failure_analysis.get(
            "suggested_skill_name", f"auto_skill_{uuid.uuid4().hex[:8]}"
        )

        candidate = SkillCandidate(
            tenant_id=tenant_id,
            agent_id=agent_id,
            source_episode_id=episode_id,
            skill_name=skill_name,
            skill_description=failure_analysis.get("failure_summary", ""),
            generated_code=generated_code,
            failure_pattern=failure_analysis,
            validation_status="pending",
        )
        self.db.add(candidate)
        self.db.commit()
        self.db.refresh(candidate)

        logger.info(
            f"Generated skill candidate '{skill_name}' from episode {episode_id}"
        )
        return candidate

    async def validate_candidate(
        self,
        candidate_id: str,
        tenant_id: str,
        test_inputs: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        """
        Validate a pending skill candidate in the sandbox.

        Updates the candidate's validation_status to 'validated' or 'failed'.
        """
        candidate = (
            self.db.query(SkillCandidate)
            .filter(
                SkillCandidate.id == candidate_id,
                SkillCandidate.tenant_id == tenant_id,
            )
            .first()
        )

        if not candidate:
            return {"error": f"Candidate {candidate_id} not found"}

        result = await self.validate_change(
            code=candidate.generated_code,
            test_inputs=test_inputs or [{}],
            tenant_id=tenant_id,
        )

        candidate.validation_status = "validated" if result["passed"] else "failed"
        candidate.validation_result = result
        candidate.validated_at = datetime.now(timezone.utc)

        if result["passed"]:
            candidate.fitness_score = 1.0

        self.db.commit()

        return {
            "candidate_id": candidate_id,
            "passed": result["passed"],
            "validation_result": result,
        }

    async def promote_skill(
        self, candidate_id: str, tenant_id: str
    ) -> dict[str, Any]:
        """
        Promote a validated candidate to the active skill registry.

        Uses SkillBuilderService to create a proper skill package.
        """
        candidate = (
            self.db.query(SkillCandidate)
            .filter(
                SkillCandidate.id == candidate_id,
                SkillCandidate.tenant_id == tenant_id,
                SkillCandidate.validation_status == "validated",
            )
            .first()
        )

        if not candidate:
            return {"error": "Candidate not found or not validated"}

        try:
            from core.skill_builder_service import SkillBuilderService, SkillMetadata

            builder = SkillBuilderService()
            metadata = SkillMetadata(
                name=candidate.skill_name,
                description=candidate.skill_description or "Auto-generated skill",
                version="1.0.0",
                author="Memento-Skills",
                capabilities=[],
                instructions=(
                    f"Generated from failed episode {candidate.source_episode_id}."
                ),
            )

            result = builder.create_skill_package(
                tenant_id=tenant_id,
                metadata=metadata,
                scripts={f"{candidate.skill_name}.py": candidate.generated_code},
            )

            if result.get("success"):
                candidate.validation_status = "promoted"
                candidate.promoted_at = datetime.now(timezone.utc)
                self.db.commit()

            return result
        except ImportError:
            logger.warning("SkillBuilderService not available")
            return {"error": "SkillBuilderService not available"}

    # --- Internal helpers ---

    @staticmethod
    def _suggest_skill_name(task_description: str, error_trace: str) -> str:
        """Generate a suggested skill name from the task description."""
        # Simple heuristic: extract key verbs/nouns from task
        words = task_description.lower().split()
        action_words = [
            w
            for w in words
            if len(w) > 3 and w not in ("the", "and", "for", "with", "that", "this")
        ]
        if action_words:
            name = "_".join(action_words[:3])
            # Sanitize for use as a Python identifier
            name = "".join(c for c in name if c.isalnum() or c == "_")
            return f"auto_{name}"
        return f"auto_skill_{uuid.uuid4().hex[:6]}"
