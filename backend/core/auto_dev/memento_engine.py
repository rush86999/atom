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
                # Extract from content field (EpisodeSegment has content, not metadata_json)
                content = seg.content or ""

                # Parse error information from content
                if "error" in content.lower() or "failed" in content.lower():
                    error_trace += f"{content}\n"

                # Parse tool calls from content
                # Format: "Tool call: <tool_name> - <status>"
                if "tool call:" in content.lower():
                    parts = content.split(":")
                    if len(parts) >= 2:
                        tool_info = parts[1].strip()
                        tool_name = tool_info.split("-")[0].strip()
                        status = "unknown"
                        if "-" in tool_info:
                            status = tool_info.split("-")[1].strip().lower()
                            if "failed" in status:
                                status = "failed"
                            elif "success" in status:
                                status = "success"

                        tool_calls.append(
                            {
                                "tool_name": tool_name,
                                "status": status,
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

        # WikiSkill W1+W2: show the proposer the skill-impact ledger (so a
        # previously rejected intervention is not re-proposed) and the wiki
        # pattern index (root causes + workarounds distilled from traces).
        history_block = ""
        index_block = ""
        tenant_id = context.get("tenant_id")
        if tenant_id and self.db is not None:
            try:
                from core.auto_dev.skill_impact_ledger import proposer_history_block
                history_block = proposer_history_block(
                    self.db, str(tenant_id),
                    agent_id=context.get("agent_id"),
                )
            except Exception:
                history_block = ""
            try:
                from core.knowledge_pattern_service import pattern_index
                index_block = pattern_index(
                    self.db, str(tenant_id), consumer="evolver")
            except Exception:
                index_block = ""

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

        history_context = f"\n\n{history_block}\n" if history_block else ""
        index_context = f"\n\n{index_block}\n" if index_block else ""

        user_prompt = (
            f"Task the agent failed at:\n{task_desc}\n\n"
            f"Error trace:\n{error_trace[:500]}\n"
            f"{tool_context}"
            f"{history_context}"
            f"{index_context}\n\n"
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
            try:
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
            except Exception as e:
                # Handle sandbox errors gracefully
                all_passed = False
                results.append(
                    {
                        "test_index": i,
                        "passed": False,
                        "output": f"Sandbox error: {str(e)}",
                        "execution_seconds": 0,
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

        # The proposer prompt reads the skill-impact ledger (W1); make sure
        # the scoping keys survive an externally-supplied analysis dict.
        failure_analysis = dict(failure_analysis)
        failure_analysis.setdefault("tenant_id", tenant_id)
        failure_analysis.setdefault("agent_id", agent_id)

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

    # --- /learn workflow→skill distillation (R72 Workstream B) ---

    async def analyze_execution(
        self, execution_id: str, **kwargs
    ) -> dict[str, Any]:
        """
        Analyze a completed agent execution into a success/step trace.

        Unlike ``analyze_episode`` (which assumes a failed episode), this
        handles ANY outcome (success or failure): it pulls the
        ``AgentExecution`` row plus its ordered ``AgentReasoningStep`` rows
        into a structured trace that the LLM can distill a skill from.

        Returns:
            {
                "execution_id": str,
                "agent_id": str | None,
                "tenant_id": str | None,
                "status": str,
                "task_description": str,
                "result_summary": str | None,
                "error_trace": str,
                "steps": list[dict],   # ordered reasoning steps
                "step_count": int,
                "tool_calls_attempted": list,
                "failure_summary": str,
                "suggested_skill_name": str,
            }
        """
        try:
            from core.models import AgentExecution, AgentReasoningStep

            execution = (
                self.db.query(AgentExecution)
                .filter(AgentExecution.id == execution_id)
                .first()
            )
            if not execution:
                return {"error": f"Execution {execution_id} not found"}

            steps = (
                self.db.query(AgentReasoningStep)
                .filter(AgentReasoningStep.execution_id == execution_id)
                .order_by(AgentReasoningStep.step_number.asc())
                .all()
            )

            step_trace = [
                {
                    "step_number": s.step_number,
                    "step_type": s.step_type,
                    "thought": s.thought,
                    "action": s.action,
                    "observation": s.observation,
                    "verified": s.verified,
                }
                for s in steps
            ]

            task_desc = execution.input_summary or ""
            outcome = execution.status or ""
            error_trace = execution.error_message or ""

            return {
                "execution_id": execution_id,
                "agent_id": str(execution.agent_id) if execution.agent_id else None,
                "tenant_id": str(execution.tenant_id) if execution.tenant_id else None,
                "status": outcome,
                "task_description": task_desc,
                "result_summary": execution.result_summary,
                "error_trace": error_trace,
                "steps": step_trace,
                "step_count": len(step_trace),
                "tool_calls_attempted": [
                    s["action"] for s in step_trace if s.get("action")
                ],
                "failure_summary": (
                    f"{outcome}: {task_desc[:100]}. Errors: {error_trace[:200]}"
                    if error_trace
                    else f"{outcome}: {task_desc[:100]}"
                ),
                "suggested_skill_name": self._suggest_skill_name(
                    task_desc, error_trace
                ),
            }
        except ImportError:
            logger.warning("Execution models not available")
            return {
                "execution_id": execution_id,
                "error": "Execution models not available",
            }

    async def learn_from_execution(
        self,
        tenant_id: str,
        agent_id: str | None,
        execution_id: str,
        skill_name: str | None = None,
        description: str | None = None,
    ) -> dict[str, Any]:
        """
        Distill a completed agent execution into a reusable Python skill.

        Pipeline:
            1. analyze_execution(execution_id) — success/step trace
            2. propose_code_change(trace) — LLM generates the skill script
            3. validate_change(code) — execute in the sandbox
            4. SkillBuilderService.create_skill_package — write disk package
            5. SkillRegistryService.import_skill — register/discoverable

        Returns a dict with ``success`` plus the package + registry results.
        """
        analysis = await self.analyze_execution(execution_id)
        if "error" in analysis:
            return {"success": False, "error": analysis["error"]}

        code = await self.propose_code_change(analysis)
        if code.startswith("# Skill generation failed"):
            return {
                "success": False,
                "error": "Skill generation failed — LLM unavailable",
            }

        validation = await self.validate_change(
            code=code, test_inputs=[{}], tenant_id=tenant_id
        )
        if not validation.get("passed"):
            return {
                "success": False,
                "error": "Skill validation failed in sandbox",
                "validation": validation,
            }

        name = (
            skill_name
            or analysis.get("suggested_skill_name")
            or f"auto_skill_{uuid.uuid4().hex[:6]}"
        )
        safe_name = "".join(c for c in name if c.isalnum() or c in ("-", "_")).lower()
        if not safe_name:
            return {"success": False, "error": "Invalid skill name"}

        desc = (
            description
            or analysis.get("failure_summary")
            or f"Skill distilled from execution {execution_id}"
        )

        # 1. Write a disk package via SkillBuilderService
        from core.skill_builder_service import SkillBuilderService, SkillMetadata

        builder = SkillBuilderService()
        package_result = builder.create_skill_package(
            tenant_id=tenant_id,
            metadata=SkillMetadata(
                name=name,
                description=desc,
                version="1.0.0",
                author="Memento-Learn",
                capabilities=[],
                instructions=f"Generated from execution {execution_id}.",
            ),
            scripts={f"{safe_name}.py": code},
        )
        if not package_result.get("success"):
            return {
                "success": False,
                "error": package_result.get("message", "Package creation failed"),
            }

        # 2. Register in the skill registry so it is discoverable/executable
        skill_md_content = (
            f"---\n"
            f"name: {name}\n"
            f"description: {desc}\n"
            f"version: 1.0.0\n"
            f"author: Memento-Learn\n"
            f"---\n\n"
            f"# {name}\n\n"
            f"{desc}\n\n"
            f"## Instructions\n"
            f"Generated from execution {execution_id}.\n\n"
            f"```python\n{code}\n```\n"
        )
        from core.skill_registry_service import SkillRegistryService

        registry = SkillRegistryService(self.db)
        import_result = await registry.import_skill(
            source="raw_content",
            content=skill_md_content,
            metadata={"imported_by": "learn_endpoint"},
        )

        return {
            "success": True,
            "execution_id": execution_id,
            "skill_name": name,
            "package": package_result,
            "registry": import_result,
        }

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
