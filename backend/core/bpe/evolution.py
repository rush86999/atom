"""AlphaEvolve-lite: offline population search over BPE harness bounds.

The paper-lineage idea (AlphaEvolve → self-evolving harnesses): treat the
harness configuration as an evolvable genome and search over it offline,
guided by an evaluator, instead of hand-tuning. Scope here is deliberately
narrow — the four tunable workspace bounds in
``core.bpe.workspace.GENE_BOUNDS`` (subgoal cap, recall top-K, Experience
capacity, render budget) — never prompts, never weights.

Loop (all offline, supervisor-gated to apply):

1. ``propose(family)`` — mutate a random elite (or sample a random genome
   when the population is cold). MAP-elites-lite: duplicate genomes are
   rejected so the population keeps diversity.
2. Trial the candidate by running agents under those bounds; score with
   ``fitness_from_signals`` (consult-policy value EMA, penalized when the
   harness-call rate strays from the paper's ~1-consult-per-episode
   annealing target).
3. ``report(family, genome, fitness)`` — keep the top :data:`POPULATION_SIZE`
   distinct genomes.
4. ``apply_best(family)`` — with ``ATOM_BPE_EVOLUTION_ENABLED`` set, write
   the winner via ``workspace.set_active_bounds``. Flag off → returns None
   (proposals only; a human/automation flips the flag to deploy).
"""
from __future__ import annotations

import logging
import os
import random
import time
from typing import Any, Dict, List, Optional, Tuple

from core.bpe.workspace import GENE_BOUNDS, set_active_bounds

logger = logging.getLogger(__name__)

POPULATION_SIZE = 8
EVOLUTION_FLAG = "ATOM_BPE_EVOLUTION_ENABLED"
# Fitness shaping: target harness-call rate (paper annealing target) and the
# penalty weight for straying from it.
TARGET_CALL_RATE = 1.0
CALL_RATE_PENALTY = 0.25


def evolution_enabled() -> bool:
    return os.getenv(EVOLUTION_FLAG, "false").strip().lower() in ("1", "true", "yes")


def _explicit_apply_override() -> Optional[bool]:
    """Explicit ATOM_BPE_EVOLUTION_ENABLED resolution: env first, then a
    UI-persisted runtime-settings override, else None (automation decides).
    'auto' (the catalog default) also resolves to None."""
    raw = os.getenv(EVOLUTION_FLAG)
    if raw is not None:
        text = raw.strip().lower()
        if text in ("1", "true", "yes"):
            return True
        if text in ("0", "false", "no", "off"):
            return False
        return None
    try:
        from core.runtime_settings import resolve_setting

        res = resolve_setting(EVOLUTION_FLAG)
        if res.source == "db":
            text = str(res.value).strip().lower()
            if text in ("1", "true", "yes"):
                return True
            if text in ("0", "false", "no", "off"):
                return False
    except Exception:
        pass
    return None


def clamp_genome(genome: Dict[str, Any]) -> Dict[str, Any]:
    """Clamp/validate a genome against GENE_BOUNDS (invalid genes dropped)."""
    out: Dict[str, Any] = {}
    for gene, (lo, hi) in GENE_BOUNDS.items():
        raw = genome.get(gene)
        if raw is None:
            continue
        try:
            out[gene] = max(lo, min(hi, type(lo)(raw)))
        except (TypeError, ValueError):
            continue
    return out


def random_genome(rng: random.Random) -> Dict[str, Any]:
    genome: Dict[str, Any] = {}
    for gene, (lo, hi) in GENE_BOUNDS.items():
        if isinstance(lo, int):
            genome[gene] = rng.randint(lo, hi)
        else:
            genome[gene] = round(rng.uniform(lo, hi), 3)
    return genome


def mutate(genome: Dict[str, Any], rng: random.Random) -> Dict[str, Any]:
    """Perturb ONE gene by ±10% of its range (clamped). Single-step search."""
    genes = sorted(GENE_BOUNDS.keys())
    gene = rng.choice(genes)
    lo, hi = GENE_BOUNDS[gene]
    child = dict(genome)
    step = (hi - lo) * 0.1
    delta = rng.uniform(-step, step)
    base = child.get(gene, lo)
    try:
        child[gene] = max(lo, min(hi, type(lo)(base + delta)))
    except (TypeError, ValueError):
        child[gene] = lo
    if isinstance(lo, int):
        child[gene] = int(round(child[gene]))
        child[gene] = max(lo, min(hi, child[gene]))
    else:
        child[gene] = round(float(child[gene]), 3)
    return child


def fitness_from_signals(value_ema: float, harness_call_rate: float) -> float:
    """Evaluator: consult value, penalized for call-rate drift from target.

    Positive value_ema means consults correlate with success; a harness-call
    rate far from ~1/episode means the workspace is noisy or ignored — the
    same efficiency signal the paper's R_eff rewards.
    """
    drift = abs(float(harness_call_rate or 0.0) - TARGET_CALL_RATE)
    return round(float(value_ema) - CALL_RATE_PENALTY * drift, 4)


class Individual:
    __slots__ = ("genome", "fitness", "updated_at")

    def __init__(self, genome: Dict[str, Any], fitness: float) -> None:
        self.genome = genome
        self.fitness = fitness
        self.updated_at = time.time()

    def key(self) -> Tuple:
        return tuple(sorted(self.genome.items()))


class Population:
    """Bounded, diversity-keeping elite pool per agent family. In-memory."""

    def __init__(self, size: int = POPULATION_SIZE,
                 rng: Optional[random.Random] = None) -> None:
        self.size = size
        self.rng = rng or random.Random()
        self._individuals: Dict[str, List[Individual]] = {}

    def _family(self, family: str) -> List[Individual]:
        return self._individuals.setdefault(str(family), [])

    def report(self, family: str, genome: Dict[str, Any], fitness: float) -> bool:
        """Insert/update one evaluated genome. Returns True if accepted."""
        clean = clamp_genome(genome)
        if len(clean) != len(GENE_BOUNDS):
            return False
        fam = self._family(family)
        ind = Individual(clean, float(fitness))
        for existing in fam:
            if existing.key() == ind.key():
                if fitness > existing.fitness:  # re-evaluation: keep the best
                    existing.fitness = ind.fitness
                    existing.updated_at = ind.updated_at
                return False
        fam.append(ind)
        fam.sort(key=lambda i: (-i.fitness, i.updated_at))
        del fam[self.size:]
        return True

    def propose(self, family: str) -> Dict[str, Any]:
        """Next candidate: mutate a random elite, or sample fresh when cold."""
        fam = self._family(family)
        if not fam:
            return random_genome(self.rng)
        parent = self.rng.choice(fam)
        return mutate(parent.genome, self.rng)

    def elites(self, family: str, k: int = 3) -> List[Dict[str, Any]]:
        return [i.genome for i in self._family(family)[:max(0, int(k))]]

    def best(self, family: str) -> Optional[Dict[str, Any]]:
        fam = self._family(family)
        return fam[0].genome if fam else None

    def snapshot(self) -> Dict[str, List[Dict[str, Any]]]:
        return {
            family: [{"genome": i.genome, "fitness": i.fitness} for i in fam]
            for family, fam in self._individuals.items()
        }


# Module-level singleton (in-process, like the workspace registry).
population = Population()


def get_population() -> Population:
    return population


def apply_best(family: str) -> Optional[Dict[str, Any]]:
    """Deploy the family's best genome to new workspaces.

    Automation (default): auto-applies once the population has enough
    evaluated evidence (>= MIN_EVALUATED_GENOMES distinct genomes, best
    fitness >= EVOLUTION_APPLY_FITNESS) — no operator flip required. The
    explicit env overrides automation: ATOM_BPE_EVOLUTION=false is the
    proposal-only kill-switch; true force-applies as soon as any genome
    exists. Applications are announced via maybe_automation_flip.
    """
    from core.bpe.automation import (
        EVOLUTION_APPLY_FITNESS,
        evolution_apply_enabled,
        maybe_automation_flip,
    )

    genome = population.best(family)
    if genome is None:
        return None

    snap = population.snapshot().get(str(family), [])
    explicit_flag = _explicit_apply_override()
    if explicit_flag is False:
        logger.debug("bpe evolution: best genome held (kill-switch false)")
        return None

    from core.bpe.trust_bridge import evolution_veto, mark_applied

    vetoed, veto_reason = evolution_veto()
    if vetoed and explicit_flag is not True:
        # Adjudicated corrections landed since the last apply: the fitness
        # landscape is stale by the trusted channel's lights. Hold and let
        # automation retry after fresh trials (human signal = veto, self
        # fitness = throttle). An explicit operator override bypasses.
        logger.info("bpe evolution: best genome held (%s)", veto_reason)
        return None

    evidence_ready = len(snap) >= 3 and max(
        (i.get("fitness") or 0.0) for i in snap
    ) >= EVOLUTION_APPLY_FITNESS
    if explicit_flag is not True and not (evolution_apply_enabled() and evidence_ready):
        logger.debug("bpe evolution: best genome held (evidence pending)")
        return None

    applied = set_active_bounds(genome)
    mark_applied()
    maybe_automation_flip(
        "evolution_apply",
        {"family": family, "genome": genome,
         "fitness": max(i["fitness"] for i in snap)},
    )
    return applied
