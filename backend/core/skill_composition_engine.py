"""
Skill Composition Engine - Multi-skill workflow execution with DAG validation.

Chains multiple skills into workflows with:
- DAG validation (no circular dependencies)
- Topological execution order
- Data passing between steps
- Conditional execution
- Rollback on failure

Reference: Phase 60 RESEARCH.md Pattern 2 "Skill Composition with DAG Workflow Engine"
"""

import logging
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import networkx as nx
from sqlalchemy.orm import Session

from core.models import SkillCompositionExecution
from core.skill_registry_service import SkillRegistryService

logger = logging.getLogger(__name__)


@dataclass
class SkillStep:
    """Single step in skill composition workflow."""
    step_id: str
    skill_id: str
    inputs: Dict[str, Any]
    dependencies: List[str]  # List of step_ids this step depends on
    condition: Optional[str] = None  # Conditional execution logic
    retry_policy: Optional[Dict[str, Any]] = None  # max_retries, backoff
    timeout_seconds: int = 30


class SkillCompositionEngine:
    """
    Execute skill composition workflows with DAG validation and rollback.

    Example workflow:
        [
            SkillStep("fetch", "http_get", {"url": "api.example.com"}, []),
            SkillStep("process", "analyze", {"algorithm": "sentiment"}, ["fetch"]),
            SkillStep("notify", "send_email", {"template": "results"}, ["process"])
        ]
    """

    def __init__(self, db: Session):
        """
        Initialize composition engine.

        Args:
            db: SQLAlchemy database session
        """
        self.db = db
        self.skill_registry = SkillRegistryService(db)

    def validate_workflow(self, steps: List[SkillStep]) -> Dict[str, Any]:
        """
        Validate workflow is a DAG (no cycles).

        Args:
            steps: List of workflow steps

        Returns:
            Dict with validation result
        """
        try:
            graph = nx.DiGraph()

            # Build dependency graph
            for step in steps:
                graph.add_node(step.step_id)
                for dep in step.dependencies:
                    graph.add_edge(dep, step.step_id)

            # Check for cycles
            if not nx.is_directed_acyclic_graph(graph):
                cycles = list(nx.simple_cycles(graph))
                return {
                    "valid": False,
                    "error": "Workflow contains cycles",
                    "cycles": cycles
                }

            # Check for missing dependencies
            step_ids = {s.step_id for s in steps}
            missing_deps = []
            for step in steps:
                for dep in step.dependencies:
                    if dep not in step_ids:
                        missing_deps.append(f"Step '{step.step_id}' depends on non-existent '{dep}'")

            if missing_deps:
                return {
                    "valid": False,
                    "error": "Missing dependencies",
                    "missing": missing_deps
                }

            logger.info("Workflow validated as DAG")
            return {
                "valid": True,
                "node_count": len(graph.nodes),
                "edge_count": len(graph.edges),
                "execution_order": list(nx.topological_sort(graph))
            }

        except Exception as e:
            logger.error(f"Workflow validation failed: {e}")
            return {
                "valid": False,
                "error": str(e)
            }

    async def execute_workflow(
        self,
        workflow_id: str,
        steps: List[SkillStep],
        agent_id: str
    ) -> Dict[str, Any]:
        """
        Execute skill composition workflow with transaction rollback.

        Args:
            workflow_id: Unique workflow identifier
            steps: List of workflow steps
            agent_id: Agent ID executing the workflow

        Returns:
            Dict with execution result
        """
        # Create workflow execution record
        execution_id = str(uuid.uuid4())
        workflow_exec = SkillCompositionExecution(
            id=execution_id,
            workflow_id=workflow_id,
            agent_id=agent_id,
            workspace_id="default",
            workflow_definition=[self._step_to_dict(s) for s in steps],
            validation_status="pending",
            status="pending",
            started_at=datetime.now(timezone.utc)
        )
        self.db.add(workflow_exec)
        self.db.commit()

        try:
            # Step 1: Validate workflow
            validation = self.validate_workflow(steps)
            workflow_exec.validation_status = "valid" if validation["valid"] else "invalid"

            if not validation["valid"]:
                workflow_exec.status = "failed"
                workflow_exec.error_message = validation.get("error", "Validation failed")
                self.db.commit()
                return {
                    "success": False,
                    "error": validation["error"],
                    "workflow_id": workflow_id,
                    "execution_id": execution_id
                }

            # Step 2: Get execution order
            graph = nx.DiGraph()
            for step in steps:
                graph.add_node(step.step_id)
                for dep in step.dependencies:
                    graph.add_edge(dep, step.step_id)

            execution_order = list(nx.topological_sort(graph))

            # Step 3: Execute steps in order
            workflow_exec.status = "running"
            self.db.commit()

            results = {}
            executed_steps = []

            for step_id in execution_order:
                step = next(s for s in steps if s.step_id == step_id)
                workflow_exec.current_step = step_id

                # Resolve inputs from dependency outputs
                resolved_inputs = self._resolve_inputs(step, results)

                # Check condition
                if step.condition and not self._evaluate_condition(step.condition, results):
                    logger.info(f"Skipping step {step_id} (condition not met)")
                    continue

                # Execute skill
                logger.info(f"Executing step {step_id} with skill {step.skill_id}")
                result = await self.skill_registry.execute_skill(
                    skill_id=step.skill_id,
                    inputs=resolved_inputs,
                    agent_id=agent_id
                )

                if not result["success"]:
                    # Rollback executed steps
                    logger.error(f"Step {step_id} failed, rolling back workflow")
                    await self._rollback_workflow(executed_steps, agent_id, workflow_exec)
                    return {
                        "success": False,
                        "error": f"Step {step_id} failed: {result.get('error')}",
                        "workflow_id": workflow_id,
                        "execution_id": execution_id,
                        "rolled_back": True
                    }

                results[step_id] = result.get("result", result)
                executed_steps.append(step_id)
                workflow_exec.completed_steps = executed_steps
                workflow_exec.execution_results = results
                self.db.commit()

            # Step 4: Complete workflow
            workflow_exec.status = "completed"
            completed_at = datetime.now(timezone.utc)
            workflow_exec.completed_at = completed_at
            # Ensure started_at is timezone-aware for subtraction
            started_at = workflow_exec.started_at
            if started_at.tzinfo is None:
                started_at = started_at.replace(tzinfo=timezone.utc)
            workflow_exec.duration_seconds = (
                completed_at - started_at
            ).total_seconds()
            workflow_exec.final_output = results
            self.db.commit()

            return {
                "success": True,
                "workflow_id": workflow_id,
                "execution_id": execution_id,
                "results": results,
                "duration_seconds": workflow_exec.duration_seconds
            }

        except Exception as e:
            logger.error(f"Workflow execution failed: {e}")
            workflow_exec.status = "failed"
            workflow_exec.error_message = str(e)
            workflow_exec.completed_at = datetime.now(timezone.utc)
            self.db.commit()

            return {
                "success": False,
                "error": str(e),
                "workflow_id": workflow_id,
                "execution_id": execution_id
            }

    def _resolve_inputs(
        self,
        step: SkillStep,
        results: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Resolve step inputs from dependency outputs.

        Merges dependency outputs into step inputs.
        """
        resolved = step.inputs.copy()

        for dep_id in step.dependencies:
            if dep_id in results:
                dep_output = results[dep_id]
                # Merge output into inputs
                if isinstance(dep_output, dict):
                    resolved.update(dep_output)
                else:
                    resolved[f"{dep_id}_output"] = dep_output

        return resolved

    def _evaluate_condition(
        self,
        condition: str,
        results: Dict[str, Any]
    ) -> bool:
        """
        Evaluate conditional execution logic.

        Simple conditions like "fetch.success == true" or "process.count > 0".
        """
        try:
            # Create safe evaluation context
            context = {}
            for step_id, result in results.items():
                context[step_id] = result

            # Evaluate condition (simplified - in production use safer eval)
            return eval(condition, {"__builtins__": {}}, context)
        except Exception as e:
            logger.warning(f"Condition evaluation failed: {e}")
            return False

    async def _rollback_workflow(
        self,
        executed_steps: List[str],
        agent_id: str,
        workflow_exec: SkillCompositionExecution
    ):
        """
        Rollback executed steps (compensation transactions).

        For now, logs rollback. In production, could call skill undo methods.
        """
        logger.warning(f"Rolling back {len(executed_steps)} executed steps")

        workflow_exec.rollback_performed = True
        workflow_exec.rollback_steps = list(reversed(executed_steps))

        # TODO: Implement skill-specific rollback handlers
        # For now, mark workflow as rolled back
        workflow_exec.status = "rolled_back"
        completed_at = datetime.now(timezone.utc)
        workflow_exec.completed_at = completed_at
        # Ensure started_at is timezone-aware for subtraction
        started_at = workflow_exec.started_at
        if started_at.tzinfo is None:
            started_at = started_at.replace(tzinfo=timezone.utc)
        workflow_exec.duration_seconds = (
            completed_at - started_at
        ).total_seconds()
        self.db.commit()

    def _step_to_dict(self, step: SkillStep) -> Dict[str, Any]:
        """Convert SkillStep to dict for storage."""
        return {
            "step_id": step.step_id,
            "skill_id": step.skill_id,
            "inputs": step.inputs,
            "dependencies": step.dependencies,
            "condition": step.condition,
            "retry_policy": step.retry_policy,
            "timeout_seconds": step.timeout_seconds
        }
