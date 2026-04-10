"""
Atom Auto-Dev Module

Self-evolving agent capabilities for the open-source Atom platform.
Provides two complementary learning loops:

1. **Memento-Skills** (MementoEngine): Generates new skills from failed episodes.
   - Triggered when agents fail tasks repeatedly
   - Creates SkillCandidate proposals for user review
   - Requires INTERN maturity level

2. **AlphaEvolver** (AlphaEvolverEngine): Optimizes existing skills via mutation.
   - Iterative mutation → sandbox → fitness comparison loop
   - Requires SUPERVISED maturity level

Activation is gated by:
- Workspace settings (`Workspace.configuration.auto_dev.enabled`)
- Agent maturity level via the graduation framework (AutoDevCapabilityService)

Users are notified when agents graduate into new Auto-Dev capabilities.
Explicit triggers are the default; background evolution requires AUTONOMOUS level.
"""

from core.auto_dev.base_engine import BaseLearningEngine, SandboxProtocol
from core.auto_dev.memento_engine import MementoEngine
from core.auto_dev.alpha_evolver_engine import AlphaEvolverEngine
from core.auto_dev.fitness_service import FitnessService
from core.auto_dev.advisor_service import AdvisorService
from core.auto_dev.capability_gate import AutoDevCapabilityService

__all__ = [
    "BaseLearningEngine",
    "SandboxProtocol",
    "MementoEngine",
    "AlphaEvolverEngine",
    "FitnessService",
    "AdvisorService",
    "AutoDevCapabilityService",
]
