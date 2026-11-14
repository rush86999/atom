"""Goal 13 — structured-response signature contract for the fleet paths.

Both fleet entry points name the acting user on their structured LLM call
(``RecruitmentIntelligenceService.analyze_goal_domains`` and
``FleetAdmiral.analyze_task_requirements``). ``LLMService`` consumes
``user_id`` for personalization, but ``BYOKHandler.generate_structured_response``
has no ``user_id`` parameter, so forwarding it raised::

    BYOKHandler.generate_structured_response() got an unexpected keyword
    argument 'user_id'

for every call. Both call sites swallow the exception into a fallback, so
the only visible symptom was degraded output — observed live on Goal 13::

    reasoning: "LLM analysis failed, using default assessment. Error:
                BYOKHandler.generate_structured_response() got an
                unexpected keyword argument 'user_id'"
    goal_analysis: "Keyword-based analysis (LLM fallback)"

These regressions deliberately do **not** mock
``LLMService.generate_structured_response``. An ``AsyncMock`` accepts any
keyword and is exactly what hid this bug. Instead they drive the REAL
forwarding method into a handler double whose accepted keywords are bound
to the REAL ``BYOKHandler.generate_structured_response`` signature, so an
unsupported keyword raises the same ``TypeError`` production raised.

User/workspace attribution must survive the fix through the mechanisms the
product supports:

* ``user_id``  -> LLMService personalization (and the voter's audit row),
  never a handler keyword;
* ``workspace_id`` / ``tenant_id`` -> handler selection scope;
* ``agent_id`` / ``chain_id`` -> handler routing/cost attribution.
"""
from __future__ import annotations

import inspect
import threading

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from core.database import Base
from core.fleet_admiral import FleetAdmiral, TaskAnalysis
from core.llm.byok_handler import BYOKHandler
from core.llm_service import LLMService
from core.recruitment_intelligence_service import (
    RecruitmentIntelligenceService,
    RecruitmentPlan,
)

TENANT = "tenant-g13"
WORKSPACE = "workspace-g13"
USER = "user-g13"

# The real contract this regression is pinned to. If the handler ever grows
# a ``user_id`` parameter the first test tells us to revisit the wrapper.
_REAL_STRUCTURED_SIGNATURE = inspect.signature(
    BYOKHandler.generate_structured_response)


class _RealSignatureStructuredHandler:
    """Handler double that speaks BYOKHandler's ACTUAL structured signature.

    ``inspect.Signature.bind`` performs the same keyword validation CPython
    performs on a real call: an unknown keyword such as ``user_id`` raises
    ``TypeError: ... got an unexpected keyword argument 'user_id'``. A
    ``**kwargs`` mock cannot, which is what made the production bug invisible
    to the existing suite.
    """

    def __init__(self, responder):
        self._responder = responder
        self.calls = []

    async def generate_structured_response(self, *args, **kwargs):
        _REAL_STRUCTURED_SIGNATURE.bind(self, *args, **kwargs)
        self.calls.append(dict(kwargs))
        return self._responder(**kwargs)


def _service_with_handler(handler, workspace_id=WORKSPACE, tenant_id=TENANT):
    """Real ``LLMService`` forwarding over a supplied handler.

    ``__new__`` avoids constructing a network-capable ``BYOKHandler``; every
    attribute the structured forwarding path reads is set explicitly, so the
    method under test (``generate_structured_response``) is the production
    code, not a mock.
    """
    service = object.__new__(LLMService)
    service._db = None
    service._tenant_id = tenant_id or "default"
    service._workspace_id = workspace_id or "default"
    service._workspace_from_tenant_resolution = False
    service._scope_unresolved_reason = None
    service._handler = handler
    service._scoped_handlers = {}
    service._scope_lock = threading.RLock()
    service.continuous_learning = None
    return service


def _plan() -> RecruitmentPlan:
    return RecruitmentPlan(
        goal_analysis="LLM-derived revenue shortfall analysis",
        required_domains=["sales"],
        domain_rationale={"sales": "Goal mentions lead"},
        complexity_estimate="medium",
        estimated_parallelizable=True,
        suggested_specialist_count=1,
    )


@pytest.fixture()
def scratch_db(tmp_path):
    """Per-test scratch SQLite (never the live dev DB)."""
    engine = create_engine(
        f"sqlite:///{tmp_path / 'g13.db'}",
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, expire_on_commit=False)
    with Session() as db:
        yield db


# ---------------------------------------------------------------------------
# 1. The double can actually fail — otherwise the regression is vacuous.
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_signature_double_rejects_user_id_like_the_real_handler():
    handler = _RealSignatureStructuredHandler(lambda **_kw: _plan())

    with pytest.raises(TypeError, match="unexpected keyword argument 'user_id'"):
        await handler.generate_structured_response(
            prompt="p", system_instruction="s", response_model=RecruitmentPlan,
            user_id=USER,
        )

    # And it accepts everything the real handler accepts.
    result = await handler.generate_structured_response(
        prompt="p", system_instruction="s", response_model=RecruitmentPlan,
        temperature=0.3, agent_id="spec-sales", chain_id="chain-1",
        cascade=False, stage_decision_id="decision-1",
        capability_profile="balanced", capability_preference="balanced",
    )
    assert isinstance(result, RecruitmentPlan)
    assert handler.calls[-1]["agent_id"] == "spec-sales"


def test_user_id_is_a_service_level_kwarg_not_a_handler_parameter():
    """Pins the reason the wrapper must consume ``user_id``."""
    assert "user_id" not in _REAL_STRUCTURED_SIGNATURE.parameters
    assert "agent_id" in _REAL_STRUCTURED_SIGNATURE.parameters


# ---------------------------------------------------------------------------
# 2. LLMService: consume user attribution, forward only supported keywords.
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_structured_response_consumes_user_id_for_personalization(
        monkeypatch):
    handler = _RealSignatureStructuredHandler(lambda **_kw: _plan())
    service = _service_with_handler(handler)

    personalization = []
    service.continuous_learning = type(
        "Learning", (), {
            "get_personalized_parameters": lambda self, **kw: (
                personalization.append(kw) or {})
        })()

    # Record the scope the wrapper hands to handler selection.
    selected = {}
    real_get_handler = service._get_handler

    def _spy_get_handler(workspace_id=None, tenant_id=None):
        selected["workspace_id"] = workspace_id
        selected["tenant_id"] = tenant_id
        return real_get_handler(workspace_id=workspace_id, tenant_id=tenant_id)

    monkeypatch.setattr(service, "_get_handler", _spy_get_handler)

    result = await service.generate_structured_response(
        prompt="Analyze the revenue shortfall",
        response_model=RecruitmentPlan,
        user_id=USER,
        agent_id="spec-sales",
        chain_id="chain-g13",
        workspace_id=WORKSPACE,
        tenant_id=TENANT,
    )

    assert isinstance(result, RecruitmentPlan)

    # user attribution preserved through the supported mechanism ...
    assert personalization == [{
        "tenant_id": WORKSPACE,
        "agent_id": "spec-sales",
        "user_id": USER,
    }]
    # ... workspace attribution reached handler selection ...
    assert selected == {"workspace_id": WORKSPACE, "tenant_id": TENANT}
    # ... and only handler-supported keywords were forwarded.
    forwarded = handler.calls[-1]
    assert "user_id" not in forwarded
    assert forwarded["agent_id"] == "spec-sales"
    assert forwarded["chain_id"] == "chain-g13"


# ---------------------------------------------------------------------------
# 3. Recruitment: real LLM dispatch, not the keyword fallback.
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_recruitment_structured_call_is_dispatched_with_scope(
        scratch_db, monkeypatch):
    handler = _RealSignatureStructuredHandler(lambda **_kw: _plan())
    llm = _service_with_handler(handler)

    recorded = {}
    real_structured = LLMService.generate_structured_response

    async def _recording(self, **kwargs):
        recorded.update(kwargs)
        return await real_structured(self, **kwargs)

    monkeypatch.setattr(
        LLMService, "generate_structured_response", _recording)

    matcher = type("Matcher", (), {
        "get_all_available_domains": lambda self, user_id, workspace_id=None: [
            "sales"],
    })()

    svc = RecruitmentIntelligenceService(
        db=scratch_db,
        llm=llm,
        specialist_matcher=matcher,
        analytics=type("A", (), {})(),
        fleet_service=type("F", (), {})(),
        optimizer=type("O", (), {})(),
        governance=type("G", (), {})(),
        workspace_id=WORKSPACE,
        tenant_id=TENANT,
    )

    plan = await svc.analyze_goal_domains(
        goal="Diagnose the quarterly revenue shortfall", user_id=USER)

    # The LLM result, not ``_fallback_domain_analysis``.
    assert plan.goal_analysis == "LLM-derived revenue shortfall analysis"
    assert handler.calls, "structured dispatch never reached the handler"

    # Caller forwarded the authenticated scope through supported params.
    assert recorded["workspace_id"] == WORKSPACE
    assert recorded["tenant_id"] == TENANT
    assert recorded["user_id"] == USER
    assert "user_id" not in handler.calls[-1]


# ---------------------------------------------------------------------------
# 4. Fleet Admiral: task analysis is LLM-backed, with scope attribution.
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_fleet_admiral_task_analysis_is_not_the_default_fallback(
        scratch_db, monkeypatch):
    def _analysis(**_kw):
        return TaskAnalysis(
            complexity="high",
            required_capabilities=["sales", "marketing"],
            estimated_duration="2-3 hours",
            specialist_count=2,
            reasoning="Revenue diagnosis needs sales and marketing specialists",
        )

    handler = _RealSignatureStructuredHandler(_analysis)
    llm = _service_with_handler(handler)
    admiral = FleetAdmiral(scratch_db, llm)

    recorded = {}
    real_structured = LLMService.generate_structured_response

    async def _recording(self, **kwargs):
        recorded.update(kwargs)
        return await real_structured(self, **kwargs)

    monkeypatch.setattr(
        LLMService, "generate_structured_response", _recording)

    analysis = await admiral.analyze_task_requirements(
        task="Diagnose the quarterly revenue shortfall",
        user_id=USER,
        workspace_id=WORKSPACE,
        tenant_id=TENANT,
    )

    assert analysis["reasoning"] != (
        "LLM analysis failed, using default assessment.")
    assert analysis["complexity"] == "high"
    assert analysis["specialist_count"] == 2
    assert recorded["workspace_id"] == WORKSPACE
    assert recorded["tenant_id"] == TENANT
    assert recorded["user_id"] == USER
    assert "user_id" not in handler.calls[-1]
