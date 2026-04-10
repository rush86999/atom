"""
AlphaEvolver Engine

Core mutation and optimization logic for the evolutionary learning loop.
Produces code mutations via LLM, executes them in a sandbox, and tracks
fitness signals — allowing agents to iteratively improve their tools.

This is the upstream equivalent of the SaaS AlphaEvolveOrchestrator,
designed to work with any sandbox implementing SandboxProtocol.
"""

import logging
import uuid
from typing import Any

from sqlalchemy.orm import Session

from core.auto_dev.base_engine import BaseLearningEngine, SandboxProtocol
from core.auto_dev.models import ToolMutation, WorkflowVariant

logger = logging.getLogger(__name__)


class AlphaEvolverEngine(BaseLearningEngine):
    """
    Skill optimization via iterative code mutation.

    Lifecycle:
    1. analyze_episode() — extract performance signals from successful episodes
    2. generate_tool_mutation() — LLM generates a code mutation
    3. sandbox_execute_mutation() — run in sandbox, collect fitness signals
    4. spawn_workflow_variant() — track variant for population comparison
    5. run_research_experiment() — iterative mutate→sandbox→compare loop
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
        Analyze a successful episode to identify optimization opportunities.

        Extracts:
        - Execution latency and token usage
        - Tool calls and their performance
        - Edge case signals (retries, partial failures)
        """
        try:
            from core.models import Episode, EpisodeSegment

            episode = (
                self.db.query(Episode).filter(Episode.id == episode_id).first()
            )
            if not episode:
                return {"error": f"Episode {episode_id} not found"}

            segments = (
                self.db.query(EpisodeSegment)
                .filter(EpisodeSegment.episode_id == episode_id)
                .all()
            )

            return {
                "episode_id": episode_id,
                "task_description": episode.task_description or "",
                "success": episode.success,
                "total_segments": len(segments),
                "metadata": episode.metadata_json or {},
                "optimization_targets": self._identify_optimization_targets(segments),
            }
        except ImportError:
            logger.warning("Episode models not available")
            return {"episode_id": episode_id, "error": "Episode models not available"}

    async def propose_code_change(
        self, context: dict[str, Any], **kwargs
    ) -> str:
        """Generate a code mutation via LLM."""
        base_code = context.get("base_code", "")
        mutation_prompt = context.get("mutation_prompt", "Optimize this code")

        llm = self._get_llm_service()
        if not llm:
            return base_code + "\n# Mutation skipped: LLM unavailable"

        system_prompt = (
            "You are the AlphaEvolve Code Mutator. Your goal is to refine and "
            "evolve Python tool code to better achieve a specific objective. "
            "Respond ONLY with the mutated Python code. "
            "Maintain the same function signatures and expected return types."
        )
        user_prompt = (
            f"Objective: {mutation_prompt}\n\n"
            f"Original Python Tool Code:\n```python\n{base_code}\n```\n\n"
            "Provide the mutated code now:"
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
            return self._strip_markdown_fences(response.get("content", base_code))
        except Exception as e:
            logger.error(f"LLM mutation failed: {e}")
            return base_code + f"\n# Mutation failed: {e}"

    async def validate_change(
        self,
        code: str,
        test_inputs: list[dict[str, Any]],
        tenant_id: str,
        **kwargs,
    ) -> dict[str, Any]:
        """Execute mutated code in sandbox and assess fitness."""
        sandbox = self._get_sandbox()
        if not sandbox:
            return {"passed": False, "error": "Sandbox unavailable"}

        results = []
        all_passed = True

        for i, inputs in enumerate(test_inputs):
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
            "proxy_signals": self._compute_proxy_signals(results),
        }

    # --- AlphaEvolve-specific methods ---

    async def generate_tool_mutation(
        self,
        tenant_id: str,
        tool_name: str,
        parent_tool_id: str | None,
        base_code: str,
        mutation_prompt: str,
    ) -> ToolMutation:
        """
        Produce a new variation of a Python tool via LLM mutation.

        The mutated code is persisted as a ToolMutation record with
        sandbox_status='pending' until validated.
        """
        mutated_code = await self.propose_code_change(
            context={
                "base_code": base_code,
                "mutation_prompt": mutation_prompt,
            }
        )

        mutation = ToolMutation(
            tenant_id=tenant_id,
            parent_tool_id=parent_tool_id,
            tool_name=tool_name,
            mutated_code=mutated_code.strip(),
            sandbox_status="pending",
        )
        self.db.add(mutation)
        self.db.commit()
        self.db.refresh(mutation)

        return mutation

    async def sandbox_execute_mutation(
        self, mutation_id: str, tenant_id: str, inputs: dict[str, Any]
    ) -> dict[str, Any]:
        """
        Execute a mutation in the sandbox and record results.

        Returns proxy fitness signals for downstream evaluation.
        """
        mutation = (
            self.db.query(ToolMutation)
            .filter(
                ToolMutation.id == mutation_id,
                ToolMutation.tenant_id == tenant_id,
            )
            .first()
        )

        if not mutation:
            msg = f"Mutation {mutation_id} not found or unauthorized for tenant {tenant_id}"
            logger.error(msg)
            return {"error": msg}

        sandbox = self._get_sandbox()
        if not sandbox:
            return {"error": "Sandbox unavailable"}

        result = await sandbox.execute_raw_python(
            tenant_id=mutation.tenant_id,
            code=mutation.mutated_code,
            input_params=inputs,
        )

        execution_success = result.get("status") == "success"

        # Update mutation record
        mutation.sandbox_status = "passed" if execution_success else "failed"
        if not execution_success:
            mutation.execution_error = result.get("output", "Unknown error")

        self.db.commit()

        # Generate proxy signals
        proxy_signals = {
            "syntax_error": (
                not execution_success
                and "SyntaxError" in (mutation.execution_error or "")
            ),
            "execution_success": execution_success,
            "execution_latency_ms": result.get("execution_seconds", 0) * 1000.0,
            "environment": result.get("environment", "unknown"),
        }

        return {
            "success": execution_success,
            "output": result.get("output"),
            "proxy_signals": proxy_signals,
        }

    def spawn_workflow_variant(
        self,
        tenant_id: str,
        agent_id: str,
        workflow_def: dict[str, Any],
        parent_variant_id: str | None = None,
    ) -> WorkflowVariant:
        """Create a new workflow variant for population-based comparison."""
        variant = WorkflowVariant(
            tenant_id=tenant_id,
            parent_variant_id=parent_variant_id,
            agent_id=agent_id,
            workflow_definition=workflow_def,
            evaluation_status="pending",
        )
        self.db.add(variant)
        self.db.commit()
        self.db.refresh(variant)
        return variant

    def check_auto_synthesis_readiness(
        self, tenant_id: str, tool_name: str, threshold: int = 5
    ) -> bool:
        """Check if enough mutations passed to trigger automatic synthesis."""
        passed_count = (
            self.db.query(ToolMutation)
            .filter(
                ToolMutation.tenant_id == tenant_id,
                ToolMutation.tool_name == tool_name,
                ToolMutation.sandbox_status == "passed",
            )
            .count()
        )
        return passed_count >= threshold

    async def run_research_experiment(
        self,
        tenant_id: str,
        base_code: str,
        research_goal: str,
        iterations: int = 3,
        inputs: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        """
        Iterative research experiment: mutate → sandbox → compare → keep winner.
        """
        results = []
        current_code = base_code

        for i in range(iterations):
            logger.info(
                f"Research experiment iteration {i + 1}/{iterations} for tenant {tenant_id}"
            )

            mutation = await self.generate_tool_mutation(
                tenant_id=tenant_id,
                tool_name=f"research_exp_{uuid.uuid4().hex[:8]}",
                parent_tool_id=None,
                base_code=current_code,
                mutation_prompt=research_goal,
            )

            exec_result = await self.sandbox_execute_mutation(
                mutation_id=mutation.id,
                tenant_id=tenant_id,
                inputs=inputs or {},
            )

            results.append(
                {
                    "iteration": i + 1,
                    "mutation_id": mutation.id,
                    "success": exec_result.get("success", False),
                    "output": exec_result.get("output"),
                    "code_preview": mutation.mutated_code[:200] + "...",
                }
            )

            # Progressive evolution: use winning code as next base
            if exec_result.get("success"):
                current_code = mutation.mutated_code

        return results

    # --- Internal helpers ---

    def _identify_optimization_targets(self, segments: list) -> list[dict[str, Any]]:
        """Identify segments with room for optimization."""
        targets = []
        for seg in segments:
            meta = getattr(seg, "metadata", {}) or {}
            if meta.get("execution_seconds", 0) > 5.0:
                targets.append(
                    {
                        "segment_id": str(seg.id),
                        "reason": "high_latency",
                        "value": meta.get("execution_seconds"),
                    }
                )
            if meta.get("retry_count", 0) > 0:
                targets.append(
                    {
                        "segment_id": str(seg.id),
                        "reason": "retries",
                        "value": meta.get("retry_count"),
                    }
                )
        return targets

    @staticmethod
    def _compute_proxy_signals(test_results: list[dict]) -> dict[str, Any]:
        """Compute aggregate fitness proxy signals from test results."""
        total = len(test_results)
        passed = sum(1 for r in test_results if r["passed"])
        avg_latency = (
            sum(r.get("execution_seconds", 0) for r in test_results) / total
            if total > 0
            else 0
        )

        return {
            "execution_success": passed == total,
            "pass_rate": passed / total if total > 0 else 0,
            "avg_execution_seconds": round(avg_latency, 3),
            "syntax_error": any(
                "SyntaxError" in r.get("output", "") for r in test_results
            ),
        }
