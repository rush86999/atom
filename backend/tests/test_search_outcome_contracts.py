"""Search outcome contracts: per-leg coverage, constraint preservation, bounded
inference.

Every test here is written against the DEFECT the work order names, not against
the implementation, so an implementation that quietly reverts fails rather than
passes. The recurring theme is one question: can a caller still tell "I looked
and found nothing" from "I could not look"?
"""
from __future__ import annotations

import asyncio
import time
from datetime import datetime, timezone
from typing import Any, Dict, List

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool


@pytest.fixture
def db(monkeypatch):
    """Scratch in-memory SQLite with the FTS5 sidecars the lexical leg needs.

    Hermetic by construction: the conversations leg reads the real shared
    LanceDB comms store, so it is switched off here — these tests are about
    documents-leg coverage, and an unreadable shared store is exactly the kind
    of ambient dependency that turns a contract test into a flaky one.
    """
    monkeypatch.setenv("MEMORY_CONVERSATIONS_LEG", "false")
    from core.models import Base, IngestedDocument, KnowledgeDocument

    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    session.add_all([
        IngestedDocument(
            id="doc_a", workspace_id="default", tenant_id="default",
            file_name="revenue_report.pdf",
            file_path="/reports/revenue_report.pdf", file_type="pdf",
            integration_id="google_drive", file_size_bytes=100,
            content_preview="Quarterly revenue grew twenty percent on enterprise growth.",
            external_id="e1", ingested_at=datetime.now(timezone.utc),
        ),
        KnowledgeDocument(
            id="kd_a", workspace_id="default", tenant_id="default",
            title="Growth strategy",
            content="Revenue growth strategy for the enterprise market segment.",
        ),
    ])
    session.commit()
    session.execute(text(
        "CREATE VIRTUAL TABLE ingested_documents_fts USING fts5("
        "file_name, content_preview, content='ingested_documents', content_rowid='rowid')"
    ))
    session.execute(text(
        "CREATE VIRTUAL TABLE knowledge_documents_fts USING fts5("
        "title, content, content='knowledge_documents', content_rowid='rowid')"
    ))
    session.execute(text(
        "INSERT INTO ingested_documents_fts(rowid, file_name, content_preview) "
        "SELECT rowid, COALESCE(file_name,''), COALESCE(content_preview,'') "
        "FROM ingested_documents"
    ))
    session.execute(text(
        "INSERT INTO knowledge_documents_fts(rowid, title, content) "
        "SELECT rowid, COALESCE(title,''), COALESCE(content,'') "
        "FROM knowledge_documents"
    ))
    session.commit()
    yield session
    session.close()


# --------------------------------------------------------------------------- #
# Phase B — a failed search must never look like a successful zero-match search
# --------------------------------------------------------------------------- #


class _FakeVectorStore:
    def __init__(self, rows=None, raises: Exception | None = None):
        self._rows = rows
        self._raises = raises

    def search(self, table, query, limit=10):
        if self._raises:
            raise self._raises
        return list(self._rows or [])


def _svc(db, vector=None):
    from core.hybrid_search.documents_hybrid import DocumentsHybridSearch

    return DocumentsHybridSearch(db=db, lancedb=vector)


@pytest.mark.asyncio
async def test_raising_vector_leg_is_partial_not_silently_lexical_only(db):
    """The vector leg used to swallow its own exception and return [], which is
    byte-identical to 'the vector store has nothing'. A caller reading
    `hybrid == "lexical_only"` could not tell them apart, so 'the semantic
    index was never read' was reported as 'the corpus contains no semantic
    matches'."""
    svc = _svc(db, _FakeVectorStore(raises=RuntimeError("index gone")))

    res = await svc.search("revenue growth")

    assert res["status"] == "partial", res
    assert res["legs"]["vector"]["status"] == "failed"
    assert res["legs"]["vector"]["error_category"], "a failure must name a category"
    assert res["legs"]["lexical"]["status"] == "ok"
    assert res["results"], "a healthy sibling leg must stay usable"
    assert res["absence_claimable"] is False


@pytest.mark.asyncio
async def test_error_category_never_leaks_the_raw_message(db):
    """The category is rendered into model-visible and user-visible text. A
    connection string or file path in that slot is a data leak, and the old code
    put `str(e)` straight into the log line the assistant reads."""
    svc = _svc(db, _FakeVectorStore(
        raises=RuntimeError("postgres://user:hunter2@10.0.0.5/atom refused")))

    res = await svc.search("revenue growth")

    blob = repr(res)
    assert "hunter2" not in blob and "10.0.0.5" not in blob, blob
    assert res["legs"]["vector"]["error_category"] == "unknown"


@pytest.mark.asyncio
async def test_both_legs_failing_is_failed_and_forbids_absence(db, monkeypatch):
    """With no usable evidence from any required leg, the envelope must be
    `failed`, and `absence_claimable` must be False so a planner cannot turn a
    broken store into 'these items do not exist'."""
    from core.hybrid_search import documents_hybrid as mod

    def _boom(*a, **k):
        raise RuntimeError("lexical index unavailable")

    monkeypatch.setattr(mod.DocumentsHybridSearch, "_lexical_leg", _boom)
    monkeypatch.setattr(mod, "_vector_leg_enabled", lambda: True)
    svc = _svc(db, _FakeVectorStore(raises=RuntimeError("vector gone")))

    res = await svc.search("revenue growth")

    assert res["status"] == "failed", res
    assert res["success"] is False
    assert res["results"] == []
    assert res["absence_claimable"] is False
    assert set(res["error"]["legs"]) == {"lexical", "vector"}


@pytest.mark.asyncio
async def test_legitimate_zero_matches_is_success_and_absence_claimable(db):
    """The control for the failure cases. A corpus that really has no match is
    the ONE situation where 'not present within this coverage' is a true
    statement, so it must not be degraded into `partial` — otherwise the
    honest case starts abstaining and the distinction stops meaning anything."""
    svc = _svc(db, _FakeVectorStore([]))

    res = await svc.search("zzz qqq zzz")

    assert res["status"] == "success", res
    assert res["legs"]["lexical"]["status"] == "ok"
    assert res["legs"]["vector"]["status"] == "ok"
    assert res["results"] == []
    assert res["absence_claimable"] is True


@pytest.mark.asyncio
async def test_kill_switched_leg_is_skipped_never_failed(db, monkeypatch):
    """An optional leg disabled by configuration is `skipped`. Reporting it as
    `failed` would make every deliberately lexical-only deployment look broken
    and would train callers to ignore the coverage field."""
    from core.hybrid_search import documents_hybrid as mod

    monkeypatch.setattr(mod, "_vector_leg_enabled", lambda: False)
    svc = _svc(db, _FakeVectorStore(raises=AssertionError("must not be called")))

    res = await svc.search("revenue growth")

    assert res["legs"]["vector"]["status"] == "skipped"
    assert res["legs"]["vector"]["skip_reason"] == "vector_leg_disabled"
    assert res["status"] == "success", res
    assert "vector" not in res["coverage"]["unavailable"]
    assert "vector" in res["coverage"]["skipped"]


@pytest.mark.asyncio
async def test_hydration_failure_is_recorded_because_it_costs_source_identity(db):
    """A failed PG identity lookup used to relabel every vector hit
    `source:"vector", bridged:false` and still claim semantic coverage, so a
    broken read was indistinguishable from a corpus of genuinely unbridged
    rows. The hits stay (they are real candidates) but the loss of identity
    resolution must be visible in the coverage."""
    svc = _svc(db, _FakeVectorStore([{"id": "d1", "_distance": 0.1,
                                     "metadata": {"file_name": "a.pdf"}}]))

    original = svc._get_db

    class _Broken:
        def __enter__(self):
            raise RuntimeError("pg unavailable")

        def __exit__(self, *a):
            return False

    svc._get_db = lambda: _Broken()  # type: ignore[method-assign]
    try:
        res = await svc.search("revenue growth")
    finally:
        svc._get_db = original  # type: ignore[method-assign]

    assert res["legs"]["hydration"]["status"] == "failed"
    assert "hydration" in res["coverage"]["unavailable"]
    assert res["status"] in ("partial", "failed"), res


@pytest.mark.asyncio
async def test_ranking_degradation_is_not_coverage(db, monkeypatch):
    """A reranker fallback means the candidates were retrieved and merely
    ordered differently. Folding it into coverage produced 'evidence was fully
    searched' claims over a degraded ranking."""
    from core.hybrid_search import documents_hybrid as mod

    monkeypatch.setattr(mod, "_vector_leg_enabled", lambda: True)
    svc = _svc(db, _FakeVectorStore([]))

    res = await svc.search("revenue growth")
    res["ranking"] = {"status": "degraded", "reason": "rerank_timeout"}

    assert res["status"] == "success"
    assert res["ranking"]["status"] == "degraded"
    assert res["absence_claimable"] is True


@pytest.mark.asyncio
async def test_backward_compatible_fields_survive(db):
    """Four in-repo consumers read `results`; action_registry.documents.search
    returns this envelope verbatim as the agent-facing tool result."""
    svc = _svc(db, _FakeVectorStore([]))

    res = await svc.search("revenue growth")

    for key in ("success", "query", "results", "hybrid", "stats"):
        assert key in res, f"{key} removed from the envelope"
    assert isinstance(res["results"], list)
    assert isinstance(res["hybrid"], str)
    assert isinstance(res["stats"], dict)


# --------------------------------------------------------------------------- #
# Phase C — constraints must survive every query transformation
# --------------------------------------------------------------------------- #


def test_identifiers_keep_requested_order_and_original_spelling():
    from core.identifier_search import exact_identifiers

    ids = exact_identifiers("price for 381, U-22, SLE24-16 and GSL48-16 please")
    assert ids.index("U-22") < ids.index("SLE24-16") < ids.index("GSL48-16")
    assert "U-22" in ids, "hyphen spelling must not be normalised away"


def test_hyphen_compound_is_one_identifier_not_its_halves():
    """'SLE24-16' searched as 'SLE24' and '16' is a decomposition the user never
    asked for, and it matches different records."""
    from core.identifier_search import exact_identifiers

    ids = [t.lower() for t in exact_identifiers("only SLE24-16 please")]
    assert "sle24-16" in ids
    assert "sle24" not in ids and "16" not in ids


def test_bounded_variants_cover_every_identifier_a_head_cut_would_drop():
    """The regression: `query[:200]` searched the head and reported a confident
    zero-match answer for the tail. The replacement must transmit every
    identifier, and the check must be able to DETECT a drop, not merely avoid
    one."""
    from core.identifier_search import bounded_query_variants, query_coverage

    query = (
        "Find the price for these 8 machines: 381, U-22, No. 622, "
        "TK Manual Flanger, SLE24-16, TK 1624, TK Multi Wheel Gang Slitter, "
        "and GSL48-16 in CAD only; owner is the linmac account and the "
        "as-of date must be after the last revision"
    )
    assert len(query) > 200, "fixture must exceed the old cap to be a regression"

    variants = bounded_query_variants(query, max_chars=200, max_variants=8)
    coverage = query_coverage(query, variants)

    assert coverage["complete"], coverage["dropped_identifiers"]
    assert all(len(v) <= 200 for v in variants), "a variant may not exceed the cap"
    assert len(variants) > 1, "a long query must actually be decomposed"


def test_identifier_straddling_a_window_boundary_survives():
    """Without overlap, an identifier split across two windows is lost by both
    halves — the one failure a naive chunker cannot see from the pieces alone."""
    from core.identifier_search import bounded_query_variants, query_coverage

    query = "please find " + ("x" * 190) + " ITEM-9999 and report it"
    variants = bounded_query_variants(query, max_chars=100, max_variants=8)

    assert query_coverage(query, variants)["complete"]
    assert any("ITEM-9999" in v for v in variants)


def test_over_cap_reports_what_it_did_not_reach_instead_of_pretending():
    """Bounded means bounded. When the text cannot be covered within the call
    budget the honest answer names the gap; silently returning a head-only
    search is the defect being fixed."""
    from core.identifier_search import bounded_query_variants, query_coverage

    query = " ".join("CODE-%04d" % i for i in range(80))
    variants = bounded_query_variants(query, max_chars=120, max_variants=3)
    coverage = query_coverage(query, variants)

    assert len(variants) <= 3
    assert coverage["complete"] is False
    assert coverage["dropped_identifiers"], "the gap must be reported, not hidden"


def test_query_coverage_detects_a_head_cut():
    """If the detector cannot see the old defect, a regression to `query[:N]`
    would pass every other test in this file."""
    from core.identifier_search import query_coverage

    query = "price of 381 and U-22 and SLE24-16 and GSL48-16"
    coverage = query_coverage(query, query[:20])

    assert coverage["complete"] is False
    assert "U-22" in coverage["dropped_identifiers"]


def test_short_query_is_a_single_unchanged_variant():
    from core.identifier_search import bounded_query_variants

    assert bounded_query_variants("U-22 price", max_chars=200) == ["U-22 price"]
    assert bounded_query_variants("", max_chars=200) == []


@pytest.mark.asyncio
async def test_planner_adapter_never_drops_a_tail_identifier(db):
    """End-to-end through the shared adapter the planner uses: two windows, both
    searched, merged, and the reported coverage proves the tail arrived."""
    from core.chat_tool_planner import _hybrid_search_preserving_constraints
    from core.hybrid_search.documents_hybrid import DocumentsHybridSearch

    sent: List[str] = []

    class _Recording(DocumentsHybridSearch):
        async def search(self, query, limit=10, since=None, source=None,
                         author=None, owner_user_id=None):
            sent.append(query)
            return {
                "success": True, "status": "success", "query": query,
                "results": [], "hybrid": "no_results", "stats": {},
                "legs": {"lexical": {"status": "ok", "required": True,
                                     "error_category": None, "hit_count": 0,
                                     "duration_ms": 0.0}},
                "coverage": {"searched": ["lexical"], "unavailable": [],
                             "skipped": []},
                "ranking": {"status": "as_fused", "reason": None},
                "absence_claimable": True,
            }

    query = "prices for " + ("detail " * 40) + "U-22 SLE24-16 GSL48-16"
    res = await _hybrid_search_preserving_constraints(
        _Recording(db=db), query, limit=8, max_chars=120, max_variants=6)

    assert len(sent) > 1, "the long query was not decomposed"
    assert res["coverage"]["query_coverage"]["complete"], res["coverage"]
    for token in ("U-22", "SLE24-16", "GSL48-16"):
        assert any(token in piece for piece in sent), token


@pytest.mark.asyncio
async def test_planner_adapter_reports_the_worst_window_status(db):
    """The union is only as covered as its weakest part: one failing window
    makes the merged search partial, so a caller cannot read a half-answered
    decomposition as a complete one."""
    from core.chat_tool_planner import _hybrid_search_preserving_constraints
    from core.hybrid_search.documents_hybrid import DocumentsHybridSearch

    class _FlakySecond(DocumentsHybridSearch):
        async def search(self, query, limit=10, since=None, source=None,
                         author=None, owner_user_id=None):
            ok = "U-22" not in query
            return {
                "success": ok, "status": "success" if ok else "failed",
                "query": query,
                "results": ([{"id": "doc_a", "source": "ingested"}] if ok else []),
                "hybrid": "lexical_only", "stats": {},
                "legs": {"lexical": {
                    "status": "ok" if ok else "failed", "required": True,
                    "error_category": None if ok else "source_unavailable",
                    "hit_count": 1 if ok else 0, "duration_ms": 0.0}},
                "coverage": {"searched": ["lexical"] if ok else [],
                             "unavailable": [] if ok else ["lexical"], "skipped": []},
                "ranking": {"status": "as_fused", "reason": None},
                "absence_claimable": ok,
            }

    query = "prices for " + ("detail " * 40) + "U-22"
    res = await _hybrid_search_preserving_constraints(
        _FlakySecond(db=db), query, limit=8, max_chars=120, max_variants=6)

    assert res["status"] == "partial", res
    assert res["absence_claimable"] is False
    assert res["results"], "the window that worked must stay usable"


@pytest.mark.asyncio
async def test_planner_adapter_merges_and_dedupes_across_windows(db):
    from core.chat_tool_planner import _hybrid_search_preserving_constraints
    from core.hybrid_search.documents_hybrid import DocumentsHybridSearch

    class _SameHits(DocumentsHybridSearch):
        async def search(self, query, limit=10, since=None, source=None,
                         author=None, owner_user_id=None):
            return {
                "success": True, "status": "success", "query": query,
                "results": [{"id": "doc_a", "source": "ingested"},
                            {"id": "doc_b", "source": "ingested"}],
                "hybrid": "bm25_vector_rrf",
                "stats": {"lexical_hits": 2, "vector_hits": 0},
                "legs": {"lexical": {"status": "ok", "required": True,
                                     "error_category": None, "hit_count": 2,
                                     "duration_ms": 0.0}},
                "coverage": {"searched": ["lexical"], "unavailable": [], "skipped": []},
                "ranking": {"status": "as_fused", "reason": None},
                "absence_claimable": True,
            }

    query = "prices for " + ("detail " * 40) + "U-22"
    res = await _hybrid_search_preserving_constraints(
        _SameHits(db=db), query, limit=8, max_chars=120, max_variants=6)

    ids = [r["id"] for r in res["results"]]
    assert ids == ["doc_a", "doc_b"], ids


@pytest.mark.asyncio
async def test_empty_query_is_failed_not_a_successful_zero(db):
    from core.chat_tool_planner import _hybrid_search_preserving_constraints
    from core.hybrid_search.documents_hybrid import DocumentsHybridSearch

    res = await _hybrid_search_preserving_constraints(
        DocumentsHybridSearch(db=db), "   ", limit=8)

    assert res["status"] == "failed"
    assert res["absence_claimable"] is False


# --------------------------------------------------------------------------- #
# Phase D — the reranker must be a trained reranker, and must not block the loop
# --------------------------------------------------------------------------- #


def test_embedding_checkpoint_is_rejected_as_a_reranker(monkeypatch):
    """`CrossEncoder("BAAI/bge-large-en-v1.5")` is a bi-encoder: its logits are
    cosine geometry, not a trained relevance judgement. Min-max normalising them
    into [0,1] is what made a ranking artefact look like a relevance score."""
    from core import hybrid_retrieval_service as svc

    class _EncoderConfig:
        num_labels = 1
        architectures = ["BertModel"]

    monkeypatch.setattr(
        svc, "_classify_checkpoint",
        lambda model_id: {
            "model_id": model_id, "trained_reranker": False,
            "reason": "single_logit_encoder_without_classification_head",
        },
    )

    class _CrossEncoder:
        def __init__(self, *a, **k):
            raise AssertionError("an embedding checkpoint must never be loaded")

    import sys
    fake = type(sys)("sentence_transformers")
    fake.CrossEncoder = _CrossEncoder
    monkeypatch.setitem(sys.modules, "sentence_transformers", fake)

    service = svc.HybridRetrievalService.__new__(svc.HybridRetrievalService)
    service._reranker_model = None
    service._reranker_verdict = None
    service._reranker_probe_done = False

    async def _go():
        return await service._get_reranker_model()

    assert asyncio.run(_go()) is False
    assert service.reranker_verdict()["trained_reranker"] is False


def test_no_model_download_at_request_time(monkeypatch):
    """The work order forbids a download during a request, so the loader is
    local-files-only unless an operator opts out explicitly."""
    from core import hybrid_retrieval_service as svc

    seen: Dict[str, Any] = {}

    class _CrossEncoder:
        def __init__(self, model_id, device=None, local_files_only=None):
            seen["model_id"] = model_id
            seen["local_files_only"] = local_files_only

    import sys
    fake = type(sys)("sentence_transformers")
    fake.CrossEncoder = _CrossEncoder
    monkeypatch.setitem(sys.modules, "sentence_transformers", fake)
    monkeypatch.setattr(
        svc, "_classify_checkpoint",
        lambda m: {"model_id": m, "trained_reranker": True, "reason": "ok"},
    )
    monkeypatch.setattr(svc, "_RERANK_LOCAL_ONLY", True)

    service = svc.HybridRetrievalService.__new__(svc.HybridRetrievalService)
    service._reranker_model = None
    service._reranker_verdict = None
    service._reranker_probe_done = False

    assert asyncio.run(service._get_reranker_model()) is not False
    assert seen["local_files_only"] is True
    assert "bge-large-en-v1.5" not in seen["model_id"], (
        "the embedding checkpoint must not be the default reranker")


def test_default_reranker_is_a_trained_cross_encoder():
    from core.hybrid_retrieval_service import DEFAULT_RERANK_MODEL

    assert "bge-large-en-v1.5" not in DEFAULT_RERANK_MODEL
    assert "reranker" in DEFAULT_RERANK_MODEL.lower()


def test_short_score_vector_cannot_reorder_records(monkeypatch):
    """The scores were mapped back to candidates by position, so a vector
    shorter than the candidate list produced a confident ordering over the
    WRONG records. Cardinality is now checked before anything is reordered."""
    from core.hybrid_retrieval_service import HybridRetrievalService, RerankUnavailable

    class _Model:
        def predict(self, pairs):
            return [0.9]  # one score for three pairs

    class _Episode:
        def __init__(self, eid):
            self.id = eid
            self.task_description = f"text for {eid}"

    class _Query:
        def query(self, *a, **k):
            return self

        def filter(self, *a, **k):
            return self

        def all(self):
            return [_Episode("e1"), _Episode("e2"), _Episode("e3")]

    service = HybridRetrievalService.__new__(HybridRetrievalService)
    service.db = _Query()
    candidates = [("e1", 0.5), ("e2", 0.4), ("e3", 0.3)]

    async def _go():
        return await service._predict_bounded(
            _Model(), "q", candidates, "agent", timeout=5.0)

    with pytest.raises(RerankUnavailable) as exc:
        asyncio.run(_go())
    assert "score_cardinality_mismatch" in str(exc.value)


def test_non_finite_scores_cannot_reorder_records(monkeypatch):
    from core.hybrid_retrieval_service import HybridRetrievalService, RerankUnavailable

    class _Model:
        def predict(self, pairs):
            return [float("nan"), 0.2, 0.3]

    class _Episode:
        def __init__(self, eid):
            self.id = eid
            self.task_description = f"text {eid}"

    class _Query:
        def query(self, *a, **k):
            return self

        def filter(self, *a, **k):
            return self

        def all(self):
            return [_Episode("e1"), _Episode("e2"), _Episode("e3")]

    service = HybridRetrievalService.__new__(HybridRetrievalService)
    service.db = _Query()

    async def _go():
        return await service._predict_bounded(
            _Model(), "q", [("e1", 0.5), ("e2", 0.4), ("e3", 0.3)], "a", timeout=5.0)

    with pytest.raises(RerankUnavailable) as exc:
        asyncio.run(_go())
    assert "non_finite" in str(exc.value)


def test_scores_stay_on_the_model_scale_and_are_not_normalised(monkeypatch):
    """Min-max normalisation per query turned an arbitrary logit into a
    confident 0..1. A pairwise ranking score is not a calibrated correctness
    probability and the raw value is what keeps it that way."""
    from core.hybrid_retrieval_service import HybridRetrievalService

    class _Model:
        def predict(self, pairs):
            return [-8.0, 4.0, 0.0]

    class _Episode:
        def __init__(self, eid):
            self.id = eid
            self.task_description = f"text {eid}"

    class _Query:
        def query(self, *a, **k):
            return self

        def filter(self, *a, **k):
            return self

        def all(self):
            return [_Episode("e1"), _Episode("e2"), _Episode("e3")]

    service = HybridRetrievalService.__new__(HybridRetrievalService)
    service.db = _Query()

    async def _go():
        return await service._predict_bounded(
            _Model(), "q", [("e1", 0.5), ("e2", 0.4), ("e3", 0.3)], "a", timeout=5.0)

    out = asyncio.run(_go())
    assert [eid for eid, _ in out] == ["e2", "e3", "e1"]
    assert min(score for _, score in out) < 0.0, (
        "a negative raw logit was normalised away into a positive 0..1 score")


def test_blocking_inference_does_not_block_the_event_loop(monkeypatch):
    """`model.predict` was called synchronously inside a coroutine, so a slow
    CPU pass stalled every concurrent request in the process — and the
    surrounding `wait_for` could not preempt it, because the coroutine it was
    waiting on never got to run."""
    from core.hybrid_retrieval_service import HybridRetrievalService

    class _SlowModel:
        def predict(self, pairs):
            time.sleep(0.35)
            return [0.1] * len(pairs)

    class _Episode:
        def __init__(self, eid):
            self.id = eid
            self.task_description = f"text {eid}"

    class _Query:
        def query(self, *a, **k):
            return self

        def filter(self, *a, **k):
            return self

        def all(self):
            return [_Episode("e1")]

    service = HybridRetrievalService.__new__(HybridRetrievalService)
    service.db = _Query()

    async def _go():
        ticks = 0

        async def _heartbeat():
            nonlocal ticks
            while True:
                ticks += 1
                await asyncio.sleep(0.01)

        beat = asyncio.create_task(_heartbeat())
        try:
            await service._predict_bounded(
                _SlowModel(), "q", [("e1", 0.5)], "a", timeout=5.0)
        finally:
            beat.cancel()
        return ticks

    ticks = asyncio.run(_go())
    assert ticks >= 5, (
        f"the event loop only ticked {ticks} times during a 350ms inference — "
        "inference is still running on the loop thread")


def test_timed_out_inference_is_bounded_not_accumulated(monkeypatch):
    """Cancelling the await does not stop the thread, so repeated timeouts used
    to accumulate orphaned inferences that keep burning CPU. Admission is
    bounded and saturation is refused rather than queued."""
    from core import hybrid_retrieval_service as svc

    started = 0
    lock = __import__("threading").Lock()

    class _Stuck:
        def predict(self, pairs):
            nonlocal started
            with lock:
                started += 1
            time.sleep(0.6)
            return [0.1] * len(pairs)

    monkeypatch.setattr(svc, "_RERANK_WORKERS", 1)
    monkeypatch.setattr(svc, "_RERANK_MAX_QUEUE", 1)
    svc._rerank_executor = None
    svc._rerank_slots = None

    class _Episode:
        def __init__(self, eid):
            self.id = eid
            self.task_description = "text"

    class _Query:
        def query(self, *a, **k):
            return self

        def filter(self, *a, **k):
            return self

        def all(self):
            return [_Episode("e1")]

    service = svc.HybridRetrievalService.__new__(svc.HybridRetrievalService)
    service.db = _Query()

    async def _go():
        refused = 0
        for _ in range(6):
            try:
                await service._predict_bounded(
                    _Stuck(), "q", [("e1", 0.5)], "a", timeout=0.05)
            except asyncio.TimeoutError:
                pass
            except svc.RerankUnavailable as exc:
                if exc.reason == "queue_saturated":
                    refused += 1
        return refused

    refused = asyncio.run(_go())
    assert refused >= 1, "an unbounded pool would queue all six instead of refusing"
    assert started <= 2, (
        f"{started} inferences were admitted concurrently; the bound is workers+queue")


def test_ranking_degradation_is_observable_and_not_a_retrieval_failure(monkeypatch):
    """A reranker fallback means the candidates were retrieved and merely
    ordered differently. Reporting it as a retrieval failure produced
    'evidence was not fully searched' claims over a degraded ranking."""
    from core import hybrid_retrieval_service as svc

    class _Embedder:
        async def coarse_search_fastembed(self, **k):
            return [("e1", 0.9), ("e2", 0.8)]

    class _NoModel:
        pass

    monkeypatch.setattr(
        svc.HybridRetrievalService, "_get_reranker_model",
        lambda self: _async_false(),
    )

    service = svc.HybridRetrievalService.__new__(svc.HybridRetrievalService)
    service.db = object()
    service.embedding_service = _Embedder()
    service._reranker_model = False
    service._reranker_verdict = {"reason": "checkpoint_not_local"}
    service._reranker_probe_done = True
    service.last_ranking_status = {}

    async def _go():
        return await service.retrieve_semantic_hybrid("agent", "query")

    out = asyncio.run(_go())
    assert [stage for _, _, stage in out] == ["coarse_only", "coarse_only"]
    assert service.last_ranking_status["status"] == "degraded"
    assert service.last_ranking_status["reason"] == "checkpoint_not_local"


async def _async_false():
    return False


def test_rerank_timing_reports_measurements_not_targets():
    from core.hybrid_retrieval_service import rerank_timing

    timing = rerank_timing()
    for key in ("calls", "timed_out", "saturated", "failed", "mean_ms", "max_ms"):
        assert key in timing, f"{key} missing — a target is not a measurement"
    assert timing["workers"] >= 1


def test_module_no_longer_advertises_unmeasured_targets():
    """The old header claimed <20ms/<150ms/<200ms and >15% relevance improvement.
    Those were design targets written before any measurement existed, and
    repeating them is how a docstring becomes a false performance claim."""
    import pathlib

    text = pathlib.Path("core/hybrid_retrieval_service.py").read_text()
    for claim in ("<200ms", ">15%", "Recall@10: >90%", "NDCG@10: >0.85"):
        assert claim not in text, f"unmeasured claim still advertised: {claim}"
