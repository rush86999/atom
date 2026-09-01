"""Cross-canvas learning recall for the canvas co-editor (multi-channel,
human-style memory: the parts of a hire's experience beyond the canvas in
front of them).

Channels pinned here:
- EPISODIC — corrections from OTHER canvases of the same kind, ranked by
  relevance × recency (Generative Agents-style retrieval), same-type only.
- DISTILLED — recurring supervisor preference patterns aggregated across ALL
  corrections (ExpeL-style cross-task insights), e.g. "filled the empty
  'to' field in 3/4 corrections".

Live context: the supervisor's corrections lived per-canvas; an agent drafting
a first-contact email for dealer B never saw what the supervisor taught it on
dealer A's identical draft.
"""
from datetime import datetime, timezone, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from core.models import Base, CanvasContext
from services.canvas_context_service import (
    CanvasContextService,
    profile_similarity,
)


@pytest.fixture
def db_session():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    Sess = sessionmaker(bind=engine)
    with Sess() as s:
        yield s, engine
    engine.dispose()


NOW = datetime(2026, 9, 1, 12, 0, 0, tzinfo=timezone.utc)

DEALER_A_CORRECTION = {
    "original": {"type": "canvas_edit", "content": {
        "to": "", "cc": "",
        "subject": "Draft — first contact",
        "body": "Hello, I am reaching out about your inquiry. Best regards"}},
    "corrected": {"type": "canvas_edit", "content": {
        "to": "buyer@acme.com", "cc": "sales@brennan.ca",
        "subject": "Brennan Machinery | Your Equipment Inquiry",
        "body": "Hi Dave,\n\nChandrakant here from Brennan Machinery…"}},
    "timestamp": "2026-08-30T10:00:00+00:00",
}

UNRELATED_CORRECTION = {
    "original": {"type": "canvas_edit", "content": {"rows": [["a", 1]]}},
    "corrected": {"type": "canvas_edit", "content": {"rows": [["a", 2]]}},
    "timestamp": "2026-08-30T11:00:00+00:00",
}


def _seed(s, canvas_id, corrections, canvas_type="email", agent_id=None,
          state=None, activity=None):
    s.add(CanvasContext(
        canvas_id=canvas_id, tenant_id="default", canvas_type=canvas_type,
        user_id="u-1", agent_id=agent_id,
        user_corrections=corrections, current_state=state or {},
        last_activity_at=activity or NOW,
    ))
    s.commit()


def _current_profile():
    return (
        "email Draft — first contact dealer Jacob Schulz jschulz@blumetric.ca "
        "Brennan Machinery inquiry equipment quote Chandrakant"
    )


# ───────────────────────── similarity scorer ─────────────────────────

def test_similarity_high_for_same_kind_of_task():
    a = "email first contact dealer BluMetric Brennan Machinery inquiry equipment quote"
    b = "email first contact dealer Acme Corp Brennan Machinery equipment quote inquiry"
    assert profile_similarity(a, b) >= 0.4


def test_similarity_low_for_unrelated_tasks():
    a = "email first contact dealer Brennan Machinery inquiry equipment"
    b = "sheet quarterly revenue rows pivot totals quarterly revenue report"
    assert profile_similarity(a, b) < 0.15


def test_similarity_handles_empty_profiles():
    assert profile_similarity("", "anything at all") == 0.0
    assert profile_similarity("word", "") == 0.0


# ───────────────────────── episodic channel ─────────────────────────

def test_similar_canvas_corrections_ranks_semantically_similar_first(db_session):
    s, engine = db_session
    _seed(s, "c-current", [UNRELATED_CORRECTION], canvas_type="email")
    _seed(s, "c-dealer-a", [DEALER_A_CORRECTION], canvas_type="email",
          state={"title": "first contact — Acme Corp (Dave Bell)"},
          activity=NOW - timedelta(days=1))
    _seed(s, "c-unrelated", [UNRELATED_CORRECTION], canvas_type="sheet",
          activity=NOW - timedelta(hours=1))

    with patch("core.database.get_db_session", side_effect=lambda: s):
        svc = CanvasContextService(s, tenant_id="default")
        results = svc.get_similar_canvas_corrections(
            "c-current", "u-1", _current_profile(), current_canvas_type="email",
            now=NOW,
        )

    assert results, "the similar dealer draft must be recalled"
    assert results[0]["canvas_id"] == "c-dealer-a"
    assert results[0]["corrections"][-1]["corrected"]["content"]["to"] == "buyer@acme.com"
    # the same-type filter kept the sheet canvas out entirely
    assert all(e["canvas_type"] == "email" for e in results)


def test_similar_recall_prefers_recent_over_stale_at_equal_relevance(db_session):
    s, engine = db_session
    _seed(s, "c-current", [], canvas_type="email")
    _seed(s, "c-old", [DEALER_A_CORRECTION], canvas_type="email",
          activity=NOW - timedelta(days=120))  # ~6 half-lives back
    fresh = dict(DEALER_A_CORRECTION, timestamp="2026-08-31T10:00:00+00:00")
    _seed(s, "c-new", [fresh], canvas_type="email",
          activity=NOW - timedelta(days=1))

    svc = CanvasContextService(s, tenant_id="default")
    results = svc.get_similar_canvas_corrections(
        "c-current", "u-1", _current_profile(), current_canvas_type="email",
        now=NOW,
    )
    assert [e["canvas_id"] for e in results][0] == "c-new"


def test_similar_recall_empty_when_nothing_matches(db_session):
    s, engine = db_session
    _seed(s, "c-current", [], canvas_type="email")
    _seed(s, "c-sheet", [UNRELATED_CORRECTION], canvas_type="sheet")

    svc = CanvasContextService(s, tenant_id="default")
    assert svc.get_similar_canvas_corrections(
        "c-current", "u-1", _current_profile(), current_canvas_type="email",
        now=NOW,
    ) == []


# ───────────────────────── distilled channel ─────────────────────────

def test_correction_patterns_aggregate_across_canvases(db_session):
    s, engine = db_session
    # the SAME supervisor behavior on two different canvases
    _seed(s, "c-a", [DEALER_A_CORRECTION], canvas_type="email", agent_id="agent-1")
    second = {
        "original": {"type": "canvas_edit", "content": {
            "to": "", "cc": "", "subject": "Draft — follow up", "body": "Hi there"}},
        "corrected": {"type": "canvas_edit", "content": {
            "to": "dave@acme.com", "cc": "", "subject": "Brennan | Follow up",
            "body": "Hi Dave,\n\nChandrakant from Brennan Machinery here."}},
        "timestamp": "2026-08-31T10:00:00+00:00",
    }
    _seed(s, "c-b", [second], canvas_type="email", agent_id="agent-1")

    svc = CanvasContextService(s, tenant_id="default")
    patterns = svc.get_correction_patterns("u-1", agent_id="agent-1")

    filled_to = next(p for p in patterns if "'to'" in p["pattern"])
    assert filled_to["count"] == 2 and filled_to["total"] == 2
    # single-occurrence behaviors are noise, not patterns
    assert all(p["count"] >= 2 for p in patterns)


def test_correction_patterns_empty_without_repetition(db_session):
    s, engine = db_session
    _seed(s, "c-a", [DEALER_A_CORRECTION], canvas_type="email", agent_id="agent-1")
    svc = CanvasContextService(s, tenant_id="default")
    assert svc.get_correction_patterns("u-1", agent_id="agent-1") == []


# ───────────────────────── prompt rendering + wiring ─────────────────────────

def test_similar_lessons_section_renders_both_channels():
    from core.chat_canvas_editor import _similar_lessons_section

    section = _similar_lessons_section(
        [{
            "canvas_id": "c-a", "canvas_type": "email", "relevance": 0.61,
            "corrections": [DEALER_A_CORRECTION],
        }],
        [{"pattern": "filled the empty 'to' field", "count": 3, "total": 4}],
    )
    assert "LEARNINGS FROM SIMILAR PAST CANVASES" in section
    assert "relevance 0.61" in section
    assert "buyer@acme.com" in section
    assert "RECURRING SUPERVISOR PREFERENCES" in section
    assert "filled the empty 'to' field (3/4 corrections)" in section
    assert "outrank them" in section  # explicit precedence


def test_similar_lessons_section_empty_when_no_channels():
    from core.chat_canvas_editor import _similar_lessons_section
    assert _similar_lessons_section([], []) == ""


@pytest.mark.asyncio
async def test_plan_prompt_includes_cross_canvas_channels():
    from core.chat_canvas_editor import plan_canvas_edit

    llm = MagicMock()
    llm._get_handler.return_value.clients = {}
    llm.generate_structured_response = AsyncMock(
        return_value=MagicMock(wants_edit=False))
    await plan_canvas_edit(
        "decide on the draft", [], {"canvas_id": "c-1", "canvas_type": "email",
                                    "content": {"to": "", "subject": "", "body": "x"}},
        llm,
        similar_corrections=[{"canvas_id": "c-a", "canvas_type": "email",
                              "relevance": 0.5, "corrections": [DEALER_A_CORRECTION]}],
        correction_patterns=[{"pattern": "filled the empty 'to' field",
                              "count": 2, "total": 2}],
    )
    prompt = llm.generate_structured_response.call_args.kwargs["prompt"]
    assert "LEARNINGS FROM SIMILAR PAST CANVASES" in prompt
    assert "RECURRING SUPERVISOR PREFERENCES" in prompt


# ───────────────── semantic (LanceDB/FastEmbed) ranking path ─────────────────

@pytest.mark.asyncio
async def test_semantic_ranking_orders_by_embedding_cosine():
    """When FastEmbed vectors are available, ordering follows SEMANTIC
    similarity even where lexical overlap disagrees — that is the entire
    point of enabling LanceDB embeddings for the recall."""
    import services.canvas_context_service as ccs
    from datetime import datetime, timezone

    now = datetime(2026, 9, 1, 12, 0, 0, tzinfo=timezone.utc)
    candidates = [
        # lexically CLOSER to the current profile (shares many tokens)...
        {"canvas_id": "c-lexical", "canvas_type": "email",
         "profile_text": "email dealer inquiry equipment quote form submission",
         "corrections": [{"original": {}, "corrected": {}}],
         "latest_ts": now},
        # ...but semantically the SAME job (vectors built to say so)
        {"canvas_id": "c-semantic", "canvas_type": "email",
         "profile_text": "email unrelated words entirely different surface",
         "corrections": [{"original": {}, "corrected": {}}],
         "latest_ts": now},
    ]
    vectors = {
        "current": [1.0, 0.0],
        "email dealer inquiry equipment quote form submission": [0.55, 0.835],  # cos ≈ 0.55
        "email unrelated words entirely different surface": [0.999, 0.045],    # cos ≈ 0.999
    }

    async def fake_embed(text):
        if text == "current profile":
            return vectors["current"]
        return vectors.get(text)

    with patch.object(ccs, "_embed_text_cached", side_effect=fake_embed):
        ranked = await ccs.rank_similar_canvas_candidates(
            "current profile", candidates, now=now, min_score=0.1, limit=2,
        )
    assert ranked[0]["canvas_id"] == "c-semantic"
    assert ranked[0]["relevance"] > ranked[1]["relevance"]


@pytest.mark.asyncio
async def test_semantic_ranking_falls_back_to_lexical_without_embeddings():
    import services.canvas_context_service as ccs
    from datetime import datetime, timezone

    now = datetime(2026, 9, 1, 12, 0, 0, tzinfo=timezone.utc)
    candidates = [
        {"canvas_id": "c-similar", "canvas_type": "email",
         "profile_text": "email first contact dealer Brennan Machinery inquiry equipment",
         "corrections": [], "latest_ts": now},
        {"canvas_id": "c-other", "canvas_type": "email",
         "profile_text": "sheet pivot quarterly revenue totals",
         "corrections": [], "latest_ts": now},
    ]

    async def no_embeddings(text):
        return None

    with patch.object(ccs, "_embed_text_cached", side_effect=no_embeddings):
        ranked = await ccs.rank_similar_canvas_candidates(
            "email first contact dealer Brennan Machinery equipment inquiry",
            candidates, now=now, min_score=0.25, limit=2,
        )
    assert [e["canvas_id"] for e in ranked] == ["c-similar"]
    # the lexical fallback matches the sync path's verdict exactly
    svc = ccs.CanvasContextService(MagicMock(), tenant_id="default")
    lexical = svc.get_similar_canvas_corrections(
        "c-current", "u", "email first contact dealer Brennan Machinery equipment inquiry",
        current_canvas_type="email",
    )
    assert lexical == []


# ───────────────── /logic empty default (right-panel tab fix) ─────────────────

@pytest.mark.asyncio
async def test_logic_get_returns_empty_default_when_nothing_saved():
    """A fresh canvas must serve the Logic tab an EMPTY default (200), not a
    404 — the tab read-fires on every open and the error made it look dead."""
    from datetime import datetime as _dt
    from unittest.mock import Mock
    import contextlib

    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from api.canvas_routes import router
    from core.auth import get_current_user
    from core.database import get_db as _get_db
    from core.models import Canvas

    engine = create_engine(
        "sqlite:///:memory:", connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    Sess = sessionmaker(bind=engine)
    with Sess() as s:
        s.add(Canvas(id="c-logic", tenant_id="default", canvas_type="email",
                     name="Logic test canvas", created_by="owner-1",
                     is_collaborative=False, created_at=_dt.now()))
        s.commit()

    @contextlib.contextmanager
    def db_session():
        with Sess() as sess:
            yield sess

    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_current_user] = lambda: Mock(
        id="owner-1", tenant_id="default", status="active")

    def _override_db():
        with Sess() as sess:
            yield sess

    app.dependency_overrides[_get_db] = _override_db
    client = TestClient(app)

    with patch("core.database.get_db_session", side_effect=lambda: db_session()):
        resp = client.get("/api/canvas/c-logic/logic")
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["source"] == "" and data["language"] == "python"
    assert data["canvas_id"] == "c-logic"
    engine.dispose()
