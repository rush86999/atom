"""Feedback-loop journey (data-journey trace, final leg).

The learning loop documented across the codebase:

    agent run → AgentExperience(metadata.agent_execution_id=…) → user feedback
    (POST /api/feedback) → experience updated (confidence/feedback_score) →
    next recall surfaces feedback-aware experiences → graduation inputs

Traced gaps:

F1. **Linkage never written**: ``GenericAgent._record_execution`` built the
    AgentExperience WITHOUT ``agent_execution_id`` — even though the same
    value is the AgentExecution row id AND what the feedback API submits.
    No experience could ever be matched to a run.
F2. **No reader wiring**: ``WorldModelService.update_experience_feedback``
    / ``boost_experience_confidence`` had ZERO production callers — user
    ratings/corrections landed in an SQL AgentFeedback row and stopped
    there; stored experiences kept their pre-feedback confidence forever.

Fixes: F1 stamps the linkage at write time. F2 adds
``WorldModelService.apply_feedback_for_execution(agent_id, execution_id,
thumbs/rating, notes)`` — finds the experience by a metadata-needle filter
(same JSON-LIKE trick as role recall), maps the signal numerically
(rating → [-1, 1]; thumbs → ±1.0; comment-only → no numeric update), and
routes it through update_experience_feedback's aligned replace. The feedback
route calls it best-effort — a broken vector store must never fail a
submission.
"""
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


class FakeExperienceStore:
    def __init__(self, rows):
        self.rows = rows  # top-level id -> {"text", "metadata"}

    def get_document_by_id(self, table_name, doc_id):
        row = self.rows.get(doc_id)
        return dict(row, id=doc_id) if row else None

    def delete_documents_by_id(self, table_name, doc_id):
        self.rows.pop(doc_id, None)
        return True

    def add_document(self, table_name=None, text="", source="", metadata=None,
                     user_id="t", doc_id=None, **k):
        self.rows[doc_id] = {"text": text, "metadata": metadata or {}}
        return True

    def get_table(self, table_name):
        return _FakeTable(self.rows)


class _FakeTable:
    def __init__(self, rows):
        self._rows = rows
        self._expr = None

    def search(self):
        return self

    def where(self, expr):
        self._expr = expr
        return self

    def limit(self, n):
        return self

    def to_pandas(self):
        import pandas as pd

        needle = self._expr or ""
        recs = []
        for rid, row in self._rows.items():
            exec_id = row["metadata"].get("agent_execution_id")
            if exec_id and f'"{exec_id}"' in needle:
                recs.append(dict(row, id=rid))
        return pd.DataFrame(recs)


def _seed_experience(store, exp_id="exp-1", exec_id="exec-77", confidence=0.5):
    store.rows[exp_id] = {
        "text": "Task: reconciliation\nInput: do thing\nOutcome: Success\nLearnings: ok",
        "metadata": {
            "agent_execution_id": exec_id,
            "confidence_score": confidence,
            "outcome": "Success",
        },
    }


@pytest.fixture
def world_model():
    from core.agent_world_model import WorldModelService

    svc = WorldModelService(workspace_id="ws-fb")
    svc.db = FakeExperienceStore({})
    return svc


# ---------------------------------------------------------------------------
# F2a. apply_feedback_for_execution — mapping + lookup + aligned replace
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_rating_routes_into_experience(world_model):
    _seed_experience(world_model.db)

    ok = await world_model.apply_feedback_for_execution(
        agent_id="a1", execution_id="exec-77", rating=5,
    )

    assert ok is True
    meta = world_model.db.rows["exp-1"]["metadata"]
    assert meta["feedback_score"] == 1.0, "rating 5 must map to +1.0"
    assert meta["confidence_score"] == pytest.approx(0.7), (
        "0.5*0.6 + 1.0*0.4 = 0.7 — feedback must move confidence"
    )


@pytest.mark.asyncio
async def test_thumbs_down_negative_signal(world_model):
    _seed_experience(world_model.db, confidence=0.8)

    ok = await world_model.apply_feedback_for_execution(
        agent_id="a1", execution_id="exec-77", thumbs_up_down=False,
    )

    assert ok is True
    meta = world_model.db.rows["exp-1"]["metadata"]
    assert meta["feedback_score"] == -1.0
    # Blend: old*0.6 + ((score+1)/2)*0.4 → 0.8*0.6 + 0*0.4 = 0.48
    assert meta["confidence_score"] == pytest.approx(0.48)


@pytest.mark.asyncio
async def test_comment_only_is_no_numeric_update(world_model):
    _seed_experience(world_model.db)
    before = dict(world_model.db.rows["exp-1"]["metadata"])

    ok = await world_model.apply_feedback_for_execution(
        agent_id="a1", execution_id="exec-77", notes="meh",
    )

    assert ok is False
    assert world_model.db.rows["exp-1"]["metadata"] == before


@pytest.mark.asyncio
async def test_no_matching_execution_returns_false(world_model):
    _seed_experience(world_model.db, exec_id="other-run")

    ok = await world_model.apply_feedback_for_execution(
        agent_id="a1", execution_id="exec-77", rating=4,
    )
    assert ok is False


@pytest.mark.asyncio
async def test_broken_store_never_raises(world_model):
    world_model.db.get_table = MagicMock(side_effect=RuntimeError("lance down"))

    ok = await world_model.apply_feedback_for_execution(
        agent_id="a1", execution_id="e1", rating=3,
    )
    assert ok is False


# ---------------------------------------------------------------------------
# F2b. The feedback route actually invokes the loop
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_submit_feedback_calls_apply_feedback_for_execution(monkeypatch):
    from core.database import Base
    from core.models import AgentFeedback, AgentRegistry, User
    import backend.api.feedback_enhanced as fb
    import sqlalchemy

    engine = sqlalchemy.create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=sqlalchemy.pool.StaticPool,
    )
    Base.metadata.create_all(engine)
    session = sqlalchemy.orm.sessionmaker(bind=engine)()
    session.add(AgentRegistry(
        id="agent-fb-1", name="FB", type="assistant",
        module_path="agents.x", class_name="X", category="general",
        configuration={},
    ))
    session.commit()

    captured = {}

    class FakeWM:
        async def apply_feedback_for_execution(self, **kwargs):
            captured.update(kwargs)
            return True

    monkeypatch.setattr(
        "core.agent_world_model.WorldModelService", lambda workspace_id=None: FakeWM()
    )

    class FakeUser:
        id = "u9"

    req = fb.FeedbackSubmitRequest(
        agent_id="agent-fb-1",
        agent_execution_id="exec-42",
        user_id="u9",
        thumbs_up_down=False,
        input_context="task",
        original_output="wrong answer",
    )
    resp = await fb.submit_enhanced_feedback(request=req, current_user=FakeUser(), db=session)

    assert resp is not None
    assert captured.get("execution_id") == "exec-42"
    assert captured.get("thumbs_up_down") is False
    assert captured.get("rating") is None
    row = session.query(AgentFeedback).filter(
        AgentFeedback.agent_execution_id == "exec-42"
    ).first()
    assert row is not None, "SQL audit row still persisted"
    session.close()


# ---------------------------------------------------------------------------
# F1. The experience carries the execution linkage at write time
# ---------------------------------------------------------------------------
def _harness_patches():
    mock_world_model = AsyncMock()
    mock_world_model.recall_experiences.return_value = {}
    mock_reflection = AsyncMock()
    mock_reflection.generate_critique = AsyncMock(return_value=None)
    mock_reflection.get_relevant_critiques = AsyncMock(return_value=[])

    async def mock_generate(*args, **kwargs):
        resp = MagicMock()
        resp.thought = "thinking"
        resp.action = None
        resp.final_answer = "all done"
        return resp

    mock_llm = AsyncMock()
    mock_llm.generate_structured = mock_generate
    handler = MagicMock()
    handler.analyze_query_complexity.return_value = MagicMock(value="simple")
    mock_llm._get_handler = MagicMock(return_value=handler)
    mock_mcp = AsyncMock()
    mock_mcp.get_all_tools.return_value = []
    return mock_world_model, mock_reflection, mock_llm, mock_mcp


@pytest.mark.asyncio
async def test_record_execution_stamps_agent_execution_id():
    """A completed run's experience MUST carry the execution id — it is the
    join key the feedback loop uses to find the row later."""
    from core.generic_agent import GenericAgent
    from core.models import AgentRegistry

    mw, mr, ml, mmcp = _harness_patches()
    recorded = []

    async def fake_record(experience):
        recorded.append(experience)
        return True

    mw.record_experience = fake_record
    mw.recall_experiences = AsyncMock(return_value={})

    budget_patch = patch.object(
        GenericAgent,
        "_check_budget_before_react",
        new=AsyncMock(return_value={"allowed": True, "reason": "ok"}),
    )
    extractor = MagicMock()
    extractor.extract_from_turn = AsyncMock(return_value=None)

    with patch("core.generic_agent.WorldModelService", return_value=mw), \
         patch("core.generic_agent.ReflectionService", return_value=mr), \
         patch("core.generic_agent.CanvasSummaryService"), \
         patch("core.generic_agent.mcp_service", mmcp), \
         patch("core.generic_agent.LLMService", return_value=ml), \
         patch("core.generic_agent.get_db_session"), \
         patch("core.generic_agent.AgentGovernanceService"), \
         budget_patch, \
         patch("core.turn_fact_extractor.TURN_FACT_EXTRACTION_ENABLED", True), \
         patch(
             "core.turn_fact_extractor.get_turn_fact_extractor",
             return_value=extractor,
         ):
        agent = GenericAgent(AgentRegistry(
            id="agent-link-1", name="L", type="assistant",
            module_path="agents.x", class_name="X", category="general",
            configuration={"max_steps": 2},
        ))
        result = await agent.execute(
            "linkage task", context={"execution_id": "exec-link-9"}
        )
        assert result["status"] == "success"

    assert recorded, "experience must be recorded"
    assert recorded[0].agent_execution_id == "exec-link-9", (
        "experience.agent_execution_id is the feedback loop's join key"
    )
