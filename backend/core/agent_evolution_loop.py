"""
Agent Evolution Loop — GEA Phase 3: Updating Module + Full Evolution Cycle

Implements the Updating Module and the complete GEA evolution loop from the
Group-Evolving Agents paper (UC Santa Barbara, Feb 2026).

Architecture mirrors the two-stage GEA process:
  Stage 1 — Parent Group Selection (Performance-Novelty Algorithm)
  Stage 2 — Open-Ended Group Evolution (Experience Sharing → Reflect → Update → Evaluate)

The full cycle:
  1. select_parent_group()       — Performance-Novelty Algorithm
  2. gather experience pool      — GroupReflectionService.gather_group_experience_pool()
  3. reflect_and_generate_directives() — GroupReflectionService.reflect_and_generate_directives()
  4. _apply_directives_to_clone()— Clone agent config; apply directives; validate via guardrails
  5. _evaluate_evolved_agent()   — Lightweight benchmark evaluation
  6. _archive_or_discard()       — Save winner trace; discard failures

Key design decisions:
  - Directives are ALWAYS applied to a *clone* of the agent config, never in-place.
  - Every directive is validated by autonomous_guardrails before committing.
  - Evolution happens offline; only the winner agent is deployed (zero inference cost).

Usage:
    from core.agent_evolution_loop import AgentEvolutionLoop
    from core.database import SessionLocal

    with SessionLocal() as db:
        loop = AgentEvolutionLoop(db)
        result = await loop.run_evolution_cycle(tenant_id="tenant-uuid")
"""

import logging
import math
import uuid
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy.orm import Session

from core.models import AgentEvolutionTrace, AgentRegistry
from core.group_reflection_service import GroupReflectionService

logger = logging.getLogger(__name__)

# ─── Tuning constants ─────────────────────────────────────────────────────────
PERF_WEIGHT: float = 0.6      # α in combined_score = α*perf + β*novelty
NOVELTY_WEIGHT: float = 0.4   # β
PARENT_GROUP_SIZE: int = 5     # |P| — parent group size
MIN_PERF_THRESHOLD: float = 0.3  # Agents below this are excluded from selection
LOOKBACK_DAYS: int = 30        # Only consider agents active in the past N days


class EvolutionCycleResult:
    """Structured result from a single evolution cycle."""

    def __init__(
        self,
        cycle_id: str,
        tenant_id: str,
        parent_agent_ids: List[str],
        directives: List[str],
        evolved_agent_id: Optional[str],
        benchmark_passed: bool,
        benchmark_score: float,
        trace_id: Optional[str],
    ) -> None:
        self.cycle_id = cycle_id
        self.tenant_id = tenant_id
        self.parent_agent_ids = parent_agent_ids
        self.directives = directives
        self.evolved_agent_id = evolved_agent_id
        self.benchmark_passed = benchmark_passed
        self.benchmark_score = benchmark_score
        self.trace_id = trace_id
        self.timestamp = datetime.now(timezone.utc).isoformat()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "cycle_id": self.cycle_id,
            "tenant_id": self.tenant_id,
            "parent_agent_ids": self.parent_agent_ids,
            "directives": self.directives,
            "evolved_agent_id": self.evolved_agent_id,
            "benchmark_passed": self.benchmark_passed,
            "benchmark_score": self.benchmark_score,
            "trace_id": self.trace_id,
            "timestamp": self.timestamp,
        }


class AgentEvolutionLoop:
    """
    Orchestrates the full GEA evolution cycle for a tenant's agent population.
    """

    def __init__(self, db: Session) -> None:
        self.db = db
        self.reflection_svc = GroupReflectionService(db)

    # ─────────────────────────────────────────────────────────────────────────
    # Public API
    # ─────────────────────────────────────────────────────────────────────────

    async def run_evolution_cycle(
        self,
        tenant_id: str,
        group_size: int = PARENT_GROUP_SIZE,
        target_agent_id: Optional[str] = None,
        category: Optional[str] = None,
    ) -> EvolutionCycleResult:
        """
        Run one full GEA evolution cycle for a tenant.

        Args:
            tenant_id: Tenant to evolve agents for
            group_size: Parent group size (default 5)
            target_agent_id: If set, only evolve this specific agent;
                             otherwise select group via Performance-Novelty Algorithm
            category: Agent domain category (e.g. "crm", "finance"). Auto-detected
                      from the seed agent's AgentRegistry.category if not provided.

        Returns:
            EvolutionCycleResult with outcome details
        """
        cycle_id = str(uuid.uuid4())
        logger.info("GEA cycle %s starting for tenant %s", cycle_id, tenant_id)

        # Stage 1: Select parent group
        if target_agent_id:
            parent_group = self._get_single_agent_group(target_agent_id, tenant_id)
        else:
            parent_group = self.select_parent_group(tenant_id, n=group_size)

        if not parent_group:
            logger.warning("GEA cycle %s: no eligible agents found", cycle_id)
            return EvolutionCycleResult(
                cycle_id=cycle_id,
                tenant_id=tenant_id,
                parent_agent_ids=[],
                directives=[],
                evolved_agent_id=None,
                benchmark_passed=False,
                benchmark_score=0.0,
                trace_id=None,
            )

        parent_ids = [a.id for a in parent_group]

        # Resolve domain category once — used by reflection + trace recording
        # Priority: explicit arg > seed agent's registry category
        seed_agent_tentative = max(
            parent_group,
            key=lambda a: self._compute_combined_score(a, parent_group),
        )
        resolved_category = category or getattr(seed_agent_tentative, "category", None)

        # Stage 2: Gather shared experience pool (domain-aware)
        pool = self.reflection_svc.gather_group_experience_pool(
            parent_ids, category=resolved_category
        )

        # Stage 3: Reflect → generate evolution directives (domain-aware)
        directives = await self.reflection_svc.reflect_and_generate_directives(
            pool, tenant_id=tenant_id, category=resolved_category
        )

        # Pick the "seed" agent for mutation (highest combined score in group)
        seed_agent = seed_agent_tentative

        # Stage 4: Apply directives to a cloned config (sandboxed)
        evolved_config, guardrail_ok = await self._apply_directives_to_clone(
            seed_agent, directives, tenant_id
        )

        if not guardrail_ok:
            logger.warning("GEA cycle %s: directives blocked by guardrails", cycle_id)
            trace = self._record_trace(
                agent=seed_agent,
                parent_ids=parent_ids,
                tenant_id=tenant_id,
                directives=directives,
                pool=pool,
                benchmark_passed=False,
                benchmark_score=0.0,
                model_patch=None,
                category=resolved_category,
                block_reason="Guardrail validation failed",
            )
            return EvolutionCycleResult(
                cycle_id=cycle_id,
                tenant_id=tenant_id,
                parent_agent_ids=parent_ids,
                directives=directives,
                evolved_agent_id=None,
                benchmark_passed=False,
                benchmark_score=0.0,
                trace_id=trace.id if trace else None,
            )

        # Stage 5: Evaluate evolved config
        benchmark_score, benchmark_passed = await self._evaluate_evolved_config(
            seed_agent, evolved_config, tenant_id
        )

        # Stage 6: Archive winner or discard
        evolved_agent_id: Optional[str] = None
        if benchmark_passed:
            evolved_agent_id = await self._promote_evolved_config(
                seed_agent, evolved_config, directives, parent_group
            )

        # Record the evolution trace (with domain-specific benchmark name)
        model_patch = self._diff_configs(seed_agent.configuration, evolved_config)
        trace = self._record_trace(
            agent=seed_agent,
            parent_ids=parent_ids,
            tenant_id=tenant_id,
            directives=directives,
            pool=pool,
            benchmark_passed=benchmark_passed,
            benchmark_score=benchmark_score,
            model_patch=model_patch,
            category=resolved_category,
        )

        logger.info(
            "GEA cycle %s complete: passed=%s score=%.3f evolved_agent=%s",
            cycle_id, benchmark_passed, benchmark_score, evolved_agent_id,
        )

        return EvolutionCycleResult(
            cycle_id=cycle_id,
            tenant_id=tenant_id,
            parent_agent_ids=parent_ids,
            directives=directives,
            evolved_agent_id=evolved_agent_id,
            benchmark_passed=benchmark_passed,
            benchmark_score=benchmark_score,
            trace_id=trace.id if trace else None,
        )

    def select_parent_group(
        self,
        tenant_id: str,
        n: int = PARENT_GROUP_SIZE,
    ) -> List[AgentRegistry]:
        """
        Stage 1: Performance-Novelty Algorithm.

        Selects n agents from the archive to form the parent group.
        Combined score = α * performance_score + β * novelty_score.

        Novelty is approximated as the distance of an agent's performance
        from the population mean — agents far from the mean (in either
        direction) are novel, ensuring a healthy mix of specialists and explorers.

        Args:
            tenant_id: Tenant namespace
            n: Parent group size

        Returns:
            List of up to n AgentRegistry objects sorted by combined score desc
        """
        cutoff = datetime.now(timezone.utc) - timedelta(days=LOOKBACK_DAYS)

        agents = (
            self.db.query(AgentRegistry)
            .filter(
                AgentRegistry.tenant_id == tenant_id,
                AgentRegistry.enabled == True,
                AgentRegistry.confidence_score >= MIN_PERF_THRESHOLD,
                AgentRegistry.updated_at >= cutoff,
            )
            .all()
        )

        if not agents:
            return []

        # Compute novelty scores using population mean
        scores = [a.confidence_score for a in agents]
        mean_perf = sum(scores) / len(scores)
        std_perf = math.sqrt(sum((s - mean_perf) ** 2 for s in scores) / len(scores)) or 1e-6

        def novelty(agent: AgentRegistry) -> float:
            # Normalized absolute deviation from mean — high deviation = high novelty
            return min(1.0, abs(agent.confidence_score - mean_perf) / (2 * std_perf))

        scored = [
            (agent, self._compute_combined_score_with_novelty(agent, novelty(agent)))
            for agent in agents
        ]
        scored.sort(key=lambda x: -x[1])

        return [agent for agent, _ in scored[:n]]

    def get_ancestor_lineage(
        self,
        agent_id: str,
        tenant_id: str,
        max_depth: int = 20,
    ) -> List[Dict[str, Any]]:
        """
        Traverse the ancestry chain of an agent via evolution traces.

        Returns a list of dicts describing each ancestor, mirroring GEA's
        "super-employee" metric (17 unique ancestors → 28% of population).

        Args:
            agent_id: Starting agent
            tenant_id: Tenant namespace
            max_depth: Max generations to traverse (prevents infinite loops)

        Returns:
            List[{"agent_id": str, "generation": int, "performance_score": float}]
        """
        visited: set = set()
        lineage: List[Dict[str, Any]] = []
        queue: List[Tuple[str, int]] = [(agent_id, 0)]

        while queue and len(lineage) < max_depth:
            current_id, depth = queue.pop(0)
            if current_id in visited:
                continue
            visited.add(current_id)

            trace = (
                self.db.query(AgentEvolutionTrace)
                .filter(
                    AgentEvolutionTrace.agent_id == current_id,
                    AgentEvolutionTrace.tenant_id == tenant_id,
                )
                .order_by(AgentEvolutionTrace.created_at.desc())
                .first()
            )

            if trace:
                lineage.append({
                    "agent_id": current_id,
                    "generation": trace.generation,
                    "performance_score": trace.performance_score,
                    "depth": depth,
                })
                if trace.parent_agent_ids:
                    for parent_id in trace.parent_agent_ids:
                        if parent_id not in visited:
                            queue.append((parent_id, depth + 1))

        return lineage

    # ─────────────────────────────────────────────────────────────────────────
    # Internal: Apply directives (sandboxed)
    # ─────────────────────────────────────────────────────────────────────────

    async def _apply_directives_to_clone(
        self,
        agent: AgentRegistry,
        directives: List[str],
        tenant_id: str,
    ) -> Tuple[Dict[str, Any], bool]:
        """
        Apply evolution directives to a DEEP CLONE of the agent's configuration.

        This is the Updating Module. Directives update the system prompt and
        evolution history. Each directive is validated against governance rules
        before being committed.

        Returns:
            (evolved_config, guardrail_ok)
        """
        evolved_config = deepcopy(agent.configuration or {})

        # Record evolution metadata
        if "evolution_history" not in evolved_config:
            evolved_config["evolution_history"] = []

        evolved_config["evolution_history"].append({
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "directives": directives,
            "parent_agent_id": agent.id,
            "gea_cycle": True,
        })

        # Apply directives to system prompt (append as guidance)
        existing_prompt = evolved_config.get("system_prompt", "")
        directive_block = "\n\n## Evolution Directives\n" + "\n".join(
            f"- {d}" for d in directives
        )
        evolved_config["system_prompt"] = existing_prompt + directive_block

        # Validate through governance guardrails
        guardrail_ok = await self._validate_via_guardrails(evolved_config, tenant_id)
        return evolved_config, guardrail_ok

    async def _validate_via_guardrails(
        self,
        evolved_config: Dict[str, Any],
        tenant_id: str,
    ) -> bool:
        """
        Validate the evolved config against governance policy.

        Tries to import agent_governance_service if available;
        falls back to a simple content check to avoid hard dependencies.
        """
        try:
            from core.agent_governance_service import AgentGovernanceService
            svc = AgentGovernanceService(self.db)
            return await svc.validate_evolution_directive(evolved_config, tenant_id)
        except (ImportError, AttributeError):
            # Fallback: block configs containing obviously dangerous patterns
            system_prompt = evolved_config.get("system_prompt", "")
            danger_patterns = ["ignore all rules", "bypass guardrails", "disable safety"]
            for pattern in danger_patterns:
                if pattern.lower() in system_prompt.lower():
                    logger.warning("GEA guardrail: blocked config containing '%s'", pattern)
                    return False
            return True

    # ─────────────────────────────────────────────────────────────────────────
    # Internal: Evaluate
    # ─────────────────────────────────────────────────────────────────────────

    async def _evaluate_evolved_config(
        self,
        agent: AgentRegistry,
        evolved_config: Dict[str, Any],
        tenant_id: str,
    ) -> Tuple[float, bool]:
        """
        Evaluate the evolved config against the agent's graduation pipeline.

        Primary path: delegates to GraduationExamService.evaluate_evolved_agent()
        which runs readiness score + constitutional check + prompt quality heuristic
        without committing any changes to the database.

        Fallback: uses the lightweight confidence_score proxy (original behaviour)
        if GraduationExamService is unavailable (e.g. circular import or missing).

        Returns:
            (benchmark_score [0.0–1.0], benchmark_passed [bool])
        """
        try:
            from core.graduation_exam import GraduationExamService
            exam_svc = GraduationExamService(self.db)
            result = exam_svc.evaluate_evolved_agent(
                agent_id=agent.id,
                tenant_id=tenant_id,
                evolved_config=evolved_config,
            )
            return result["benchmark_score"], result["benchmark_passed"]
        except Exception as e:
            logger.warning(
                "GEA: GraduationExamService evaluation failed (%s); using proxy score", e
            )

        # Fallback: lightweight proxy
        benchmark_score: float = agent.confidence_score
        evolution_bonus = min(0.05, 0.01 * len(evolved_config.get("evolution_history", [])))
        benchmark_score = min(1.0, benchmark_score + evolution_bonus)
        benchmark_passed = benchmark_score >= 0.55
        return benchmark_score, benchmark_passed

    # ─────────────────────────────────────────────────────────────────────────
    # Internal: Promote / Record
    # ─────────────────────────────────────────────────────────────────────────

    async def _promote_evolved_config(
        self,
        seed_agent: AgentRegistry,
        evolved_config: Dict[str, Any],
        directives: List[str],
        parent_group: List[AgentRegistry],
    ) -> str:
        """
        Commit the evolved config to the seed agent (in-place update).
        Records the evolution in the agent's configuration.

        Returns the agent_id of the updated agent.
        """
        seed_agent.configuration = evolved_config
        seed_agent.self_healed_count = (seed_agent.self_healed_count or 0) + 1
        seed_agent.updated_at = datetime.now(timezone.utc)
        self.db.commit()
        logger.info("GEA: promoted evolved config to agent %s", seed_agent.id)
        return seed_agent.id

    def _record_trace(
        self,
        agent: AgentRegistry,
        parent_ids: List[str],
        tenant_id: str,
        directives: List[str],
        pool: Dict[str, Any],
        benchmark_passed: bool,
        benchmark_score: float,
        model_patch: Optional[str],
        category: Optional[str] = None,
        block_reason: Optional[str] = None,
    ) -> Optional[AgentEvolutionTrace]:
        """
        Persist an AgentEvolutionTrace to the Experience Archive.
        The benchmark_name is derived from the domain profile's success_label
        so traces are self-describing across domains.
        """
        try:
            from core.group_reflection_service import DomainProfileRegistry
            domain_profile = DomainProfileRegistry.resolve(category)
            benchmark_name = f"{domain_profile.name.lower().replace(' ', '_')}_proxy"

            # Calculate ancestor count by combining parent lineage depths
            ancestor_count = len(set(parent_ids))

            # Determine current generation
            last_trace = (
                self.db.query(AgentEvolutionTrace)
                .filter(AgentEvolutionTrace.agent_id == agent.id)
                .order_by(AgentEvolutionTrace.generation.desc())
                .first()
            )
            generation = (last_trace.generation + 1) if last_trace else 1

            tool_log_sample = pool.get("tool_patterns", [])[:10]

            trace = AgentEvolutionTrace(
                tenant_id=tenant_id,
                agent_id=agent.id,
                generation=generation,
                parent_agent_ids=parent_ids,
                ancestor_count=ancestor_count,
                performance_score=agent.confidence_score,
                novelty_score=0.0,  # Populated by select_parent_group in future
                combined_selection_score=agent.confidence_score * PERF_WEIGHT,
                tool_use_log=tool_log_sample,
                task_log="\n".join(pool.get("task_log_excerpts", [])[:3]),
                evolving_requirements="\n".join(directives),
                model_patch=model_patch,
                benchmark_passed=benchmark_passed,
                benchmark_name=benchmark_name,
                benchmark_score=benchmark_score,
                is_high_quality=benchmark_passed,
                quality_filter_reason=block_reason,
            )
            self.db.add(trace)
            self.db.commit()
            self.db.refresh(trace)
            return trace
        except Exception as e:
            logger.error("GEA: failed to record trace: %s", e)
            self.db.rollback()
            return None

    # ─────────────────────────────────────────────────────────────────────────
    # Scoring utilities
    # ─────────────────────────────────────────────────────────────────────────

    def _compute_combined_score(
        self, agent: AgentRegistry, group: List[AgentRegistry]
    ) -> float:
        scores = [a.confidence_score for a in group]
        mean = sum(scores) / len(scores) if scores else 0.5
        std = math.sqrt(sum((s - mean) ** 2 for s in scores) / len(scores)) or 1e-6
        novelty = min(1.0, abs(agent.confidence_score - mean) / (2 * std))
        return PERF_WEIGHT * agent.confidence_score + NOVELTY_WEIGHT * novelty

    def _compute_combined_score_with_novelty(
        self, agent: AgentRegistry, novelty: float
    ) -> float:
        return PERF_WEIGHT * agent.confidence_score + NOVELTY_WEIGHT * novelty

    def _get_single_agent_group(
        self, agent_id: str, tenant_id: str
    ) -> List[AgentRegistry]:
        agent = (
            self.db.query(AgentRegistry)
            .filter(
                AgentRegistry.id == agent_id,
                AgentRegistry.tenant_id == tenant_id,
            )
            .first()
        )
        return [agent] if agent else []

    def _diff_configs(
        self,
        original: Optional[Dict[str, Any]],
        evolved: Optional[Dict[str, Any]],
    ) -> str:
        """
        Produce a simple human-readable diff between two config dicts.
        In production, use unified diff on the JSON-serialized configs.
        """
        import json
        orig_str = json.dumps(original or {}, indent=2, sort_keys=True)
        evol_str = json.dumps(evolved or {}, indent=2, sort_keys=True)

        if orig_str == evol_str:
            return "--- no changes ---"

        # Simple line-level diff for readability
        orig_lines = orig_str.splitlines()
        evol_lines = evol_str.splitlines()

        import difflib
        diff = difflib.unified_diff(
            orig_lines,
            evol_lines,
            fromfile="original_config",
            tofile="evolved_config",
            lineterm="",
        )
        return "\n".join(list(diff)[:100])  # Cap at 100 lines
