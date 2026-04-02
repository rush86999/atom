"""
Task Decomposition Service

Intelligent task decomposition using LLM analysis with rule-based fallback.
Breaks complex tasks into parallelizable subtasks with dependency tracking.

Pattern: Follows RecruitmentIntelligenceService structure
- LLM-based analysis with structured Pydantic output
- Rule-based fallback templates from SwarmOrchestrator
- Token estimation and domain requirements
"""

import logging
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from core.llm.byok_handler import BYOKHandler

logger = logging.getLogger(__name__)

# Pydantic models for structured LLM output
class SubTask(BaseModel):
    """Individual subtask from decomposition."""
    id: str = Field(description="Unique subtask identifier (e.g., 'task-1', 'task-2')")
    description: str = Field(description="What this subtask does")
    required_domain: str = Field(description="Domain specialist needed (e.g., 'finance', 'sales')")
    estimated_tokens: int = Field(description="Expected token usage for this subtask", ge=0, le=100000)
    depends_on: List[str] = Field(
        description="List of subtask IDs this depends on",
        default_factory=list
    )
    can_parallelize: bool = Field(description="Can this subtask run in parallel with siblings")

class TaskDecomposition(BaseModel):
    """Complete task decomposition result."""
    subtasks: List[SubTask] = Field(description="List of subtasks")
    complexity_score: float = Field(
        description="0-1 complexity estimate (0=simple, 1=very complex)",
        ge=0,
        le=1
    )
    estimated_duration_seconds: int = Field(description="Expected completion time in seconds")
    suggested_fleet_size: int = Field(
        description="Recommended specialist count",
        ge=1,
        le=25
    )
    decomposition_rationale: str = Field(description="Why decomposed this way")

class TaskDecompositionService:
    """
    Service for intelligent task decomposition using LLM analysis.

    Uses LLM to break complex tasks into subtasks with:
    - Explicit dependencies
    - Token estimates
    - Domain requirements
    - Parallelization flags

    Falls back to rule-based templates if LLM fails.
    """

    # Available domains (should match SwarmOrchestrator domains)
    AVAILABLE_DOMAINS = [
        "finance", "sales", "marketing", "operations", "legal",
        "engineering", "hr", "procurement", "communications", "intelligence",
        "research", "analyst", "coordinator", "executor", "reporter"
    ]

    def __init__(
        self,
        db: Session,
        llm_service: BYOKHandler,
        swarm_orchestrator=None
    ):
        """
        Initialize TaskDecompositionService.

        Args:
            db: Database session
            llm_service: BYOKHandler for LLM calls
            swarm_orchestrator: Optional SwarmOrchestrator for fallback patterns
        """
        self.db = db
        self.llm = llm_service
        self.swarm_orchestrator = swarm_orchestrator

    async def decompose_task(
        self,
        task_description: str,
        
        context: Dict[str, Any],
        max_subtasks: int = 10
    ) -> TaskDecomposition:
        """
        Decompose a complex task into subtasks using LLM analysis.

        Args:
            task_description: The task to decompose
            tenant_id: Any ID for LLM routing
            context: Additional context (available domains, constraints, etc.)
            max_subtasks: Maximum number of subtasks to generate

        Returns:
            TaskDecomposition with subtasks, complexity, and recommendations
        """
        # Build domain catalog for LLM
        available_domains_info = self._build_domain_catalog(tenant_id)

        prompt = f"""You are an expert at multi-agent task decomposition and dependency analysis.

TASK: {task_description}

AVAILABLE SPECIALIST DOMAINS:
{available_domains_info}

CONTEXT: {context}

DECOMPOSITION RULES:
1. Break into 3-10 subtasks (not too granular, not too coarse)
2. Identify dependencies: which subtasks must finish before others start
3. Estimate token usage for each subtask (0-100000 range)
4. Mark which subtasks can run in parallel
5. Assign required domain from available domains
6. Assess overall complexity (0.0-1.0 scale)
7. Suggest fleet size (1-25 agents)

DEPENDENCY EXAMPLES:
- If task-2 requires output from task-1, set task-2.depends_on = ["task-1"]
- Independent tasks can run in parallel (can_parallelize = true)
- Sequential tasks set can_parallelize = false

Return JSON matching the TaskDecomposition schema."""

        try:
            result = await self.llm.generate_structured_response(
                prompt=prompt,
                system_instruction="You are an expert at multi-agent task decomposition and dependency analysis.",
                response_model=TaskDecomposition,
                temperature=0.3,  # Low temperature for deterministic decomposition
                tenant_id=tenant_id
            )

            # Validate subtask count
            if len(result.subtasks) > max_subtasks:
                logger.warning(
                    f"[TaskDecomposition] LLM returned {len(result.subtasks)} subtasks, "
                    f"limiting to {max_subtasks}"
                )
                result.subtasks = result.subtasks[:max_subtasks]

            # Validate domains are available
            for subtask in result.subtasks:
                if subtask.required_domain not in self.AVAILABLE_DOMAINS:
                    logger.warning(
                        f"[TaskDecomposition] Unknown domain '{subtask.required_domain}', "
                        f"defaulting to 'analyst'"
                    )
                    subtask.required_domain = "analyst"

            # Validate dependencies reference valid subtask IDs
            valid_ids = {s.id for s in result.subtasks}
            for subtask in result.subtasks:
                invalid_deps = [dep for dep in subtask.depends_on if dep not in valid_ids]
                if invalid_deps:
                    logger.warning(
                        f"[TaskDecomposition] Invalid dependencies {invalid_deps} in {subtask.id}, "
                        f"removing them"
                    )
                    subtask.depends_on = [dep for dep in subtask.depends_on if dep in valid_ids]

            logger.info(
                f"[TaskDecomposition] Decomposed '{task_description[:50]}...' into "
                f"{len(result.subtasks)} subtasks (complexity: {result.complexity_score}, "
                f"fleet size: {result.suggested_fleet_size})"
            )

            return result

        except Exception as e:
            logger.error(f"[TaskDecomposition] LLM decomposition failed: {e}")
            # Fallback to rule-based templates
            return self._fallback_decomposition(task_description, tenant_id, max_subtasks)

    def _build_domain_catalog(self) -> str:
        """Build formatted catalog of available domains for LLM."""
        # For now, return static list
        # In future enhancement, could query AgentRegistry for actual agent counts
        catalog_lines = []
        for domain in self.AVAILABLE_DOMAINS:
            catalog_lines.append(f"- {domain.title()}: Available")

        return "\n".join(catalog_lines)

    def _fallback_decomposition(
        self,
        task_description: str,
        
        max_subtasks: int
    ) -> TaskDecomposition:
        """
        Fallback decomposition using rule-based templates when LLM fails.

        Uses patterns from SwarmOrchestrator (_decompose_generic, _decompose_data_analysis).

        Args:
            task_description: The task to decompose
            tenant_id: Any ID
            max_subtasks: Maximum subtasks

        Returns:
            Simple TaskDecomposition with sequential subtasks
        """
        logger.info(f"[TaskDecomposition] Using fallback decomposition for: {task_description[:50]}...")

        # Simple keyword-based task type detection
        task_lower = task_description.lower()

        # Detect task type
        if any(keyword in task_lower for keyword in ["analyze", "analysis", "report", "data"]):
            subtasks = self._fallback_data_analysis(task_description)
        elif any(keyword in task_lower for keyword in ["search", "research", "find"]):
            subtasks = self._fallback_research(task_description)
        elif any(keyword in task_lower for keyword in ["correlate", "cross", "multiple system"]):
            subtasks = self._fallback_correlation(task_description)
        else:
            subtasks = self._fallback_generic(task_description)

        # Limit to max_subtasks
        subtasks = subtasks[:max_subtasks]

        # Calculate simple metrics
        total_tokens = sum(s.estimated_tokens for s in subtasks)
        complexity = min(1.0, len(subtasks) / 10.0)  # More subtasks = more complex
        duration = total_tokens / 100  # Assume 100 tokens/second
        fleet_size = min(len(subtasks), 5)  # Conservative fleet size

        return TaskDecomposition(
            subtasks=subtasks,
            complexity_score=complexity,
            estimated_duration_seconds=duration,
            suggested_fleet_size=fleet_size,
            decomposition_rationale="Rule-based decomposition (LLM fallback)"
        )

    def _fallback_data_analysis(self, task_description: str) -> List[SubTask]:
        """Fallback: Data analysis task decomposition."""
        return [
            SubTask(
                id="task-1",
                description=f"Gather data for: {task_description}",
                required_domain="analyst",
                estimated_tokens=2000,
                depends_on=[],
                can_parallelize=False
            ),
            SubTask(
                id="task-2",
                description=f"Analyze data for: {task_description}",
                required_domain="analyst",
                estimated_tokens=5000,
                depends_on=["task-1"],
                can_parallelize=False
            ),
            SubTask(
                id="task-3",
                description=f"Generate report for: {task_description}",
                required_domain="reporter",
                estimated_tokens=3000,
                depends_on=["task-2"],
                can_parallelize=False
            )
        ]

    def _fallback_research(self, task_description: str) -> List[SubTask]:
        """Fallback: Research task decomposition."""
        return [
            SubTask(
                id="task-1",
                description=f"Search for information: {task_description}",
                required_domain="research",
                estimated_tokens=2000,
                depends_on=[],
                can_parallelize=False
            ),
            SubTask(
                id="task-2",
                description=f"Extract relevant information: {task_description}",
                required_domain="analyst",
                estimated_tokens=4000,
                depends_on=["task-1"],
                can_parallelize=False
            ),
            SubTask(
                id="task-3",
                description=f"Synthesize findings: {task_description}",
                required_domain="analyst",
                estimated_tokens=3000,
                depends_on=["task-2"],
                can_parallelize=False
            )
        ]

    def _fallback_correlation(self, task_description: str) -> List[SubTask]:
        """Fallback: Multi-system correlation task decomposition."""
        return [
            SubTask(
                id="task-1",
                description=f"Query CRM system: {task_description}",
                required_domain="analyst",
                estimated_tokens=2000,
                depends_on=[],
                can_parallelize=True
            ),
            SubTask(
                id="task-2",
                description=f"Query communication system: {task_description}",
                required_domain="analyst",
                estimated_tokens=2000,
                depends_on=[],
                can_parallelize=True
            ),
            SubTask(
                id="task-3",
                description=f"Query calendar system: {task_description}",
                required_domain="analyst",
                estimated_tokens=2000,
                depends_on=[],
                can_parallelize=True
            ),
            SubTask(
                id="task-4",
                description=f"Correlate results: {task_description}",
                required_domain="coordinator",
                estimated_tokens=4000,
                depends_on=["task-1", "task-2", "task-3"],
                can_parallelize=False
            )
        ]

    def _fallback_generic(self, task_description: str) -> List[SubTask]:
        """Fallback: Generic task decomposition."""
        return [
            SubTask(
                id="task-1",
                description=f"Execute task: {task_description}",
                required_domain="executor",
                estimated_tokens=5000,
                depends_on=[],
                can_parallelize=False
            )
        ]
