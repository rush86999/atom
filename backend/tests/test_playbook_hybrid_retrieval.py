"""Hybrid playbook retrieval: dense (embedding) recall + trigger keywords
as a boost, not a gate.

Regression context (Sep 8, 2026): get_relevant gated keyworded playbooks on
a literal keyword hit, so any paraphrased request silently skipped an
approved process — "chase the supplier about the unpaid one" never hit the
keyword "invoice", the playbook didn't render, and nothing looked broken
(the agent just did unguided work). Also: the chat-surface memory leg never
passed canvas_type, so keyword-less playbooks could only trigger on the
canvas-edit path. These tests pin the new recall rule (keyword hit OR
canvas-type match OR strong dense similarity), the ranking order
(keyword ≥ weak dense < strong dense), and graceful degradation when the
embedder is unavailable or failing.
"""
import asyncio

import pytest

from core.models import Base
from core.playbook_service import PlaybookService, _playbook_document
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker


@pytest.fixture
def db():
    eng = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=eng)
    Sess = sessionmaker(bind=eng, expire_on_commit=False)
    s = Sess()
    try:
        yield s
    finally:
        s.close()
    eng.dispose()


class DomainBackend:
    """2-D toy embedder for recall tests: dimension 0 = invoice-ness,
    dimension 1 = bandsaw-ness. Counts domain words, so docs and messages
    in the same domain land close together regardless of wording."""

    model = "domain-toy"
    available = True

    def embed(self, texts):
        out = []
        for t in texts:
            v = [0.0, 0.0]
            for word in str(t).lower().split():
                if any(w in word for w in ("invoice", "payment", "unpaid")):
                    v[0] += 1
                if any(w in word for w in ("bandsaw", "blade")):
                    v[1] += 1
            out.append(v)
        return out


class StaticBackend:
    """Embeds from an exact-text → vector table (texts not listed get
    ``default``). Used for ranking calibration, where the test needs to
    control precise cosine values."""

    model = "static-test-model"
    available = True

    def __init__(self, vectors, default=None):
        self.vectors = vectors
        self.default = default or [0.0, 0.0]

    def embed(self, texts):
        return [list(self.vectors.get(t, self.default)) for t in texts]


class BrokenBackend:
    """Mimics an embedder failure mid-turn (model load crash, ONNX error)."""

    model = "broken-model"
    available = True

    def embed(self, texts):
        raise RuntimeError("embedder exploded")


class UnavailableBackend:
    """Mimics a deploy without fastembed / with a cloud provider: the
    service must treat it as a no-op, never an error."""

    model = None
    available = False

    def embed(self, texts):
        raise RuntimeError("not available")


def _make(db, *, name, keywords=None, canvas_type=None, steps=None,
          questions=None, description=""):
    """Approved playbook row, created with embeddings unavailable (so no
    vectors are stored) — ranking tests attach exact vectors afterwards via
    a StaticBackend keyed on _playbook_document(row)."""
    svc = PlaybookService(db, tenant_id="default",
                          embedding_backend=UnavailableBackend())
    return svc.create(
        name=name,
        description=description,
        trigger_canvas_type=canvas_type,
        trigger_keywords=keywords or [],
        steps=steps or [],
        template_questions=questions or [],
        source="authored",
        approval_state="approved",
    )


def _static_service(db, rows, message_vec, doc_vecs):
    """A service whose backend knows each row's document vector (keyed by
    the exact text _playbook_document produces). The caller adds the
    message vector: backend.vectors[message] = message_vec."""
    backend = StaticBackend(dict(doc_vecs))
    return PlaybookService(db, tenant_id="default",
                           embedding_backend=backend), backend


def test_paraphrase_recalled_without_keyword_hit(db):
    """THE bug this change fixes: zero literal keyword overlap, but the
    request is semantically the playbook's domain → still recalled."""
    row = _make(db, name="Invoice follow-up",
                description="Chase unpaid supplier invoices.",
                keywords=["invoice", "po number"],
                steps=["Check the PO number before chasing."])
    _make(db, name="Bandsaw quoting", keywords=["bandsaw"],
          steps=["Ask for material and dimensions."])

    # No "invoice"/"po number" anywhere — the OLD gate skipped the playbook.
    svc = PlaybookService(db, tenant_id="default",
                          embedding_backend=DomainBackend())
    got = svc.get_relevant("please chase the supplier about the unpaid one")
    assert [p["name"] for p in got] == ["Invoice follow-up"]
    assert row.id == got[0]["id"]


def test_no_semantic_match_returns_empty(db):
    _make(db, name="Invoice follow-up", keywords=["invoice"],
          steps=["Check the PO number."])
    _make(db, name="Bandsaw quoting", keywords=["bandsaw"],
          steps=["Ask for material and dimensions."])

    svc = PlaybookService(db, tenant_id="default",
                          embedding_backend=DomainBackend())
    assert svc.get_relevant("tell me a joke about penguins") == []


def test_keywordless_playbook_recalled_by_similarity(db):
    """Keyword-less playbooks used to fire on canvas-type match alone; a
    semantically on-domain message now recalls them with no canvas at all."""
    _make(db, name="Bandsaw quoting", keywords=[],
          steps=["Ask for material and dimensions before quoting."])

    svc = PlaybookService(db, tenant_id="default",
                          embedding_backend=DomainBackend())
    got = svc.get_relevant("customer asked what to check before a bandsaw "
                           "blade quote")
    assert [p["name"] for p in got] == ["Bandsaw quoting"]


def test_keyword_hit_outranks_weak_dense_match(db):
    """A literal keyword hit (user said the word) must rank above a
    moderate semantic match; both still render (recall-first)."""
    invoice = _make(db, name="Invoice follow-up", keywords=["refund"],
                    steps=["Refund goes back to the original payment method."])
    bandsaw = _make(db, name="Bandsaw quoting", keywords=[],
                    steps=["Ask for material and dimensions."])
    message = "the customer wants a refund"
    # invoice doc: weak 0.2 cosine; bandsaw doc: moderate 0.6 cosine.
    svc, backend = _static_service(db, [invoice, bandsaw], message, {
        _playbook_document(invoice): [0.2, 0.98],
        _playbook_document(bandsaw): [0.6, 0.8],
    })
    backend.vectors[message] = [1.0, 0.0]

    got = svc.get_relevant(message)
    # invoice: 1.0 keyword + 1.5*0.2 = 1.3  >  bandsaw: 1.5*0.6 = 0.9
    assert [p["name"] for p in got] == ["Invoice follow-up", "Bandsaw quoting"]


def test_keyworded_playbook_admitted_by_canvas_match_alone(db):
    """Behavior change, pinned deliberately: a keyworded playbook with zero
    keyword hits used to be excluded even on a matching canvas; now canvas
    match alone admits it (advisory leg, ranked, capped at 2)."""
    _make(db, name="Quarterly review", keywords=["zebra-unlikely-word"],
          canvas_type="email", steps=["Pull the quarterly numbers."])

    svc = PlaybookService(db, tenant_id="default",
                          embedding_backend=DomainBackend())
    got = svc.get_relevant("draft an email about the quarterly numbers",
                           canvas_type="email")
    assert [p["name"] for p in got] == ["Quarterly review"]


def test_canvas_match_boosts_rank_over_dense_only(db):
    """Equal keyword situation: the canvas-matching playbook ranks first."""
    a = _make(db, name="A email process", canvas_type="email",
              steps=["Step one."])
    b = _make(db, name="B sheet process", canvas_type="sheet",
              steps=["Step one."])
    message = "do the thing"
    doc_vecs = {
        _playbook_document(a): [0.99, 0.141],   # cos 0.99 vs message
        _playbook_document(b): [0.6, 0.8],      # cos 0.6 vs message
    }
    svc, backend = _static_service(db, [a, b], [1.0, 0.0], doc_vecs)
    backend.vectors[message] = [1.0, 0.0]
    got = svc.get_relevant(message, canvas_type="sheet")
    # B: canvas +2.0 + 1.5*0.6 = 2.9  >  A: 1.5*0.99 = 1.485
    assert [p["name"] for p in got] == ["B sheet process", "A email process"]


def test_stale_embedding_model_backfills(db):
    """Vectors from a DIFFERENT embedder model must not be scored
    cross-model — the read path re-embeds and persists the new model name."""
    row = _make(db, name="Invoice follow-up", keywords=["invoice"],
                steps=["Check the PO number."])
    row.embedding = [1.0, 0.0]
    row.embedding_model = "ancient-model"
    db.commit()

    message = "chase the unpaid invoice"
    backend = StaticBackend({
        _playbook_document(row): [2.0, 0.0],
        message: [1.0, 0.0],
    })
    got = PlaybookService(db, tenant_id="default",
                          embedding_backend=backend).get_relevant(message)
    db.refresh(row)
    assert row.embedding_model == StaticBackend.model
    assert [p["name"] for p in got] == ["Invoice follow-up"]


def test_embedder_failure_degrades_to_keywords(db):
    """An embedder crash mid-turn must never fail retrieval: keyword/canvas
    scoring still runs."""
    _make(db, name="Invoice follow-up", keywords=["invoice"],
          steps=["Check the PO number."])

    svc = PlaybookService(db, tenant_id="default",
                          embedding_backend=BrokenBackend())
    got = svc.get_relevant("process the invoice")
    assert [p["name"] for p in got] == ["Invoice follow-up"]
    assert svc.get_relevant("nothing related here") == []


def test_create_and_update_store_embeddings(db):
    """Write-time embedding: create computes and stores the document vector
    + model; update (draft editing) refreshes it."""
    backend = DomainBackend()
    svc = PlaybookService(db, tenant_id="default", embedding_backend=backend)
    row = svc.create(name="Bandsaw quoting",
                     description="Quote process.",
                     steps=["Ask for material."],
                     source="authored", approval_state="approved")
    expected = backend.embed([_playbook_document(row)])[0]
    assert row.embedding == expected
    assert row.embedding_model == DomainBackend.model

    svc.update(row.id, steps=["Ask for material and blade width."])
    db.refresh(row)
    assert row.embedding == backend.embed([_playbook_document(row)])[0]


def test_mode_off_short_circuits(db, monkeypatch):
    _make(db, name="Invoice follow-up", keywords=["invoice"])
    monkeypatch.setattr("core.playbook_service.playbook_mode", lambda: "off")
    svc = PlaybookService(db, tenant_id="default",
                          embedding_backend=DomainBackend())
    assert svc.get_relevant("invoice") == []


def test_playbooks_leg_threads_canvas_type(monkeypatch):
    """The chat-surface memory leg must pass canvas_type through — dropping
    it silently disabled keyword-less playbooks on that surface."""
    from core.memory_context_assembler import _playbooks_leg

    captured = {}

    def fake_get_relevant(self, message, canvas_type=None, limit=2):
        captured["canvas_type"] = canvas_type
        return []

    monkeypatch.setattr(PlaybookService, "get_relevant", fake_get_relevant)

    class _DummyDB:
        def close(self):
            pass

    monkeypatch.setattr("core.database.SessionLocal", lambda: _DummyDB())

    asyncio.run(_playbooks_leg("msg", "ws", "tenant", canvas_type="email"))
    assert captured["canvas_type"] == "email"
