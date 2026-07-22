"""Domain-aware verification cascade for Swarm Coordination.

Public surface — what callers (the Conductor, tests) should import:

    from core.orchestration.verification import (
        TaskDomain,
        VerificationStrategy,
        VerificationResult,
        VerificationOrchestrator,
        infer_domain,
        resolve_domain,
        resolve_strategy,
        DOMAIN_STRATEGY_MAP,
    )

Design overview: see :mod:`core.orchestration.verification.base` and
the architecture doc ``docs/architecture/SWARM_COORDINATION.md`` §4.
"""
from core.orchestration.verification.base import (
    VerificationResult,
    VerificationStrategy,
    Verifier,
    serialise,
)
from core.orchestration.verification.code_pipeline import CodePipelineVerifier
from core.orchestration.verification.domain import (
    DOMAIN_STRATEGY_MAP,
    TaskDomain,
    infer_domain,
    resolve_domain,
    resolve_strategy,
)
from core.orchestration.verification.dispatcher import VerificationOrchestrator
from core.orchestration.verification.execution import ExecutionVerifier
from core.orchestration.verification.formal import FormalVerifier
from core.orchestration.verification.grounded import GroundedVerifier
from core.orchestration.verification.judge import JudgeVerifier
from core.orchestration.verification.schema_verifier import SchemaVerifier
from core.orchestration.verification.voting import VotingVerifier

__all__ = [
    # Enums + dataclasses
    "TaskDomain",
    "VerificationStrategy",
    "VerificationResult",
    "DOMAIN_STRATEGY_MAP",
    # Orchestrator + verifiers
    "VerificationOrchestrator",
    "Verifier",
    "VotingVerifier",
    "SchemaVerifier",
    "ExecutionVerifier",
    "FormalVerifier",
    "GroundedVerifier",
    "JudgeVerifier",
    "CodePipelineVerifier",
    # Resolution helpers
    "infer_domain",
    "resolve_domain",
    "resolve_strategy",
    "serialise",
]
