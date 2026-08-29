"""BPE automation — everything flips itself when healthy.

Follows the repo's consent-gated automation pattern (see org-politics
automation): env kill-switch > automatic decision from recorded evidence >
default. No operator flip is ever required for the BPE subsystem:

- **Consult gating** (``ATOM_BPE_CONSULT_POLICY``): unset → AUTO (the value
  gate is active and self-regulating — it only ever SUPPRESSES the workspace
  block when an agent's own episodes prove consultation hurts, and rendering
  resumes automatically when episodes recover). ``true`` forces gating on
  regardless of evidence; ``false`` is the kill-switch (shadow recording
  only, never gates).
- **Evolution apply** (``ATOM_BPE_EVOLUTION``): unset → AUTO (the best
  evaluated genome applies once the population has enough evidence: ≥
  ``MIN_EVALUATED_GENOMES`` distinct genomes and best fitness ≥
  ``EVOLUTION_APPLY_FITNESS``). ``false`` = proposal-only kill-switch;
  ``true`` = force-apply as soon as any genome exists.

Every automatic flip logs an INFO line and records a ``bpe.automation`` span
so the flips are observable (the org-politics pattern: automation must be
auditable, and revocation/rollback is always possible via the env
kill-switch, which resolves first).
"""
from __future__ import annotations

import logging
import os
import time
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

AUTOMATION_FLAG = "ATOM_BPE_AUTOMATION"       # off | auto (default auto)
CONSULT_FLAG = "ATOM_BPE_CONSULT_POLICY"      # true | false | unset→auto
EVOLUTION_FLAG = "ATOM_BPE_EVOLUTION"         # true | false | unset→auto

# Evidence thresholds for automatic evolution application.
MIN_EVALUATED_GENOMES = 3
EVOLUTION_APPLY_FITNESS = 0.25


def _env(name: str) -> Optional[str]:
    raw = os.getenv(name)
    return raw.strip().lower() if raw and raw.strip() else None


def _flag(name: str) -> Optional[bool]:
    """Tri-state env resolution: True/False when explicitly set, else None."""
    raw = _env(name)
    if raw is None:
        return None
    if raw in ("1", "true", "yes", "on"):
        return True
    if raw in ("0", "false", "no", "off"):
        return False
    return None


def automation_enabled() -> bool:
    """Automation mode: default ON ("everything should be automated").
    ``ATOM_BPE_AUTOMATION=off`` is the master kill-switch for all
    automatic flips (consult gating AND evolution application)."""
    return _flag(AUTOMATION_FLAG) is not False


def consult_gating_active() -> bool:
    """Whether the consult value-gate may suppress workspace rendering.

    Resolution order: explicit ``ATOM_BPE_CONSULT_POLICY`` (true/false)
    wins; unset → AUTO (gating active, self-regulating by evidence).
    """
    explicit = _flag(CONSULT_FLAG)
    if explicit is not None:
        return explicit
    return automation_enabled()


def evolution_apply_enabled() -> bool:
    """Whether genome application is permitted at all (kill-switch only —
    the evidence gate lives in :func:`evolution_apply_ready`)."""
    explicit = _flag(EVOLUTION_FLAG)
    if explicit is not None:
        return explicit
    return automation_enabled()


def evolution_apply_ready(population_snapshot: Dict[str, Any],
                          min_evaluated: int = MIN_EVALUATED_GENOMES,
                          min_fitness: float = EVOLUTION_APPLY_FITNESS) -> bool:
    """Evidence gate for automatic genome application.

    Ready when any agent family has ≥ ``min_evaluated`` distinct evaluated
    genomes whose best fitness clears ``min_fitness`` — i.e. the search has
    actually explored enough for the winner to mean something.
    """
    for family, individuals in (population_snapshot or {}).items():
        if len(individuals) >= min_evaluated:
            best = max((i.get("fitness") or 0.0) for i in individuals)
            if best >= min_fitness:
                return True
    return False


def maybe_automation_flip(name: str, detail: Dict[str, Any]) -> None:
    """Audit an automatic flip: INFO log + observability span. Never raises."""
    logger.info(f"[BPE Automation] {name}: {detail}")
    try:
        from core.bpe.telemetry import record_bpe_span

        record_bpe_span(
            action="automation_flip",
            extra={"flip": name, **detail},
        )
    except Exception:
        pass
