"""
Tests for Document Freshness & Supersession Service.

Covers:
- Pure freshness math: compute_freshness_status, derive_status_from_hash,
  detect_removed_upstream, jaccard, cosine.
- Supersession detection: semantic near-duplicate, entity overlap, and the
  "newer must be genuinely newer" heuristic. Also covers the
  two-docs-same-topic case (a newer doc in a different location obsoleting an
  older one).
- DB round-trips: mark_on_ingest, mark_stale, mark_superseded,
  reevaluate_workspace (age-out + removed-upstream), non_fresh_doc_ids.
- Postgres GraphRAG cascade: cascade_graph_supersession stamps
  properties.superseded_by onto graph_nodes/edges derived from a doc; and
  entity_set_for_doc reads a doc's entities back for the comparison signal.
"""

import uuid
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import text
from sqlalchemy.orm import Session

from core.models import (
    GraphEdge,
    GraphNode,
    IngestedDocument as IngestedDocumentModel,
)
from core.doc_freshness_service import (
    NON_FRESH_STATUSES,
    SupersessionCandidate,
    compute_freshness_status,
    detect_removed_upstream,
    detect_supersession,
    derive_status_from_hash,
    hash_text,
    jaccard,
    DocFreshnessService,
)
from core.doc_freshness_service import _cosine


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def db(worker_database):
    """Isolated in-memory DB session (mirrors test_user_activity.py)."""
    SessionLocal = worker_database
    session = SessionLocal()
    try:
        yield session
    finally:
        session.rollback()
        session.close()


@pytest.fixture
def ws_id() -> str:
    return f"ws_{uuid.uuid4().hex[:8]}"


def _make_doc(
    db: Session,
    ws_id: str,
    *,
    external_id: str,
    freshness_status: str = "fresh",
    last_verified_at: datetime | None = None,
    external_modified_at: datetime | None = None,
    source_modified_at: datetime | None = None,
    source_content_hash: str | None = None,
) -> IngestedDocumentModel:
    doc = IngestedDocumentModel(
        id=f"doc_{uuid.uuid4().hex[:8]}",
        workspace_id=ws_id,
        file_name=f"{external_id}.md",
        file_path=f"/{external_id}.md",
        file_type="md",
        integration_id="notion",
        file_size_bytes=100,
        content_preview="preview",
        external_id=external_id,
        external_modified_at=external_modified_at,
        last_verified_at=last_verified_at,
        source_modified_at=source_modified_at,
        source_content_hash=source_content_hash,
        freshness_status=freshness_status,
    )
    db.add(doc)
    db.commit()
    db.refresh(doc)
    return doc


# ============================================================================
# Pure-function freshness math
# ============================================================================

class TestFreshnessMath:
    def test_unverified_is_outdated(self):
        assert compute_freshness_status(None) == "outdated"

    def test_recently_verified_is_fresh(self):
        now = datetime.now(timezone.utc)
        assert compute_freshness_status(now) == "fresh"

    def test_beyond_ttl_is_outdated(self):
        now = datetime.now(timezone.utc)
        assert compute_freshness_status(now - timedelta(hours=25)) == "outdated"

    def test_within_ttl_is_fresh(self):
        now = datetime.now(timezone.utc)
        assert compute_freshness_status(now - timedelta(hours=2)) == "fresh"

    def test_ttl_boundary_is_fresh(self):
        # Just under the 24h TTL should still be fresh.
        now = datetime.now(timezone.utc)
        assert compute_freshness_status(now - timedelta(hours=23, minutes=59)) == "fresh"

    def test_source_modified_drift_is_stale(self):
        now = datetime.now(timezone.utc)
        old = now - timedelta(days=5)
        assert (
            compute_freshness_status(
                last_verified_at=now,
                source_modified_at_now=now,
                last_verified_modified=old,
            )
            == "stale"
        )

    def test_source_modified_aligned_is_fresh(self):
        now = datetime.now(timezone.utc)
        assert (
            compute_freshness_status(
                last_verified_at=now,
                source_modified_at_now=now,
                last_verified_modified=now,
            )
            == "fresh"
        )

    def test_outdated_takes_precedence_over_stale(self):
        """A doc both old AND with drifted source should be outdated."""
        now = datetime.now(timezone.utc)
        old = now - timedelta(days=5)
        assert (
            compute_freshness_status(
                last_verified_at=old,  # > TTL → outdated
                source_modified_at_now=now,
                last_verified_modified=old,  # also drifted
            )
            == "outdated"
        )

    def test_naive_datetimes_are_coerced_to_aware(self):
        naive_now = datetime.utcnow()  # no tz
        # Should not raise; treated as UTC
        assert compute_freshness_status(naive_now) == "fresh"

    def test_naive_now_with_aware_last_verified_does_not_crash(self):
        """A tz-naive ``now`` passed by a caller (e.g. from a SQLite cell or a
        naive datetime.now()) must be coerced before subtraction against a
        tz-aware ``last_verified_at``.

        Postgres stores ``last_verified_at`` as ``DateTime(timezone=True)``
        (aware); if a caller passes a naive ``now``, the subtraction
        ``now - _aware(last_verified_at)`` mixes offset-naive and offset-aware
        datetimes and raises ``TypeError`` — crashing the whole freshness
        re-evaluation sweep. ``now`` must be normalized just like
        ``last_verified_at``.
        """
        aware_last_verified = datetime.now(timezone.utc) - timedelta(hours=1)
        naive_now = datetime.utcnow()  # tzinfo=None

        # Must not raise TypeError; should resolve to "fresh".
        result = compute_freshness_status(
            last_verified_at=aware_last_verified,
            now=naive_now,
        )
        assert result == "fresh"

    def test_aware_now_with_naive_last_verified_does_not_crash(self):
        """Symmetric case: aware ``now`` with naive ``last_verified_at``."""
        naive_last_verified = datetime.utcnow() - timedelta(hours=1)
        aware_now = datetime.now(timezone.utc)

        result = compute_freshness_status(
            last_verified_at=naive_last_verified,
            now=aware_now,
        )
        assert result == "fresh"


class TestHashDerivation:
    def test_no_prior_hash_is_fresh(self):
        assert derive_status_from_hash(None, "abc") == "fresh"

    def test_matching_hash_is_fresh(self):
        assert derive_status_from_hash("abc", "abc") == "fresh"

    def test_differing_hash_is_stale(self):
        assert derive_status_from_hash("abc", "def") == "stale"

    def test_hash_text_is_sha256(self):
        h = hash_text("hello")
        assert len(h) == 64
        assert h == hash_text("hello")
        assert h != hash_text("world")


class TestRemovedDetection:
    def test_present_is_not_removed(self):
        assert detect_removed_upstream("a", {"a", "b"}) is False

    def test_absent_is_removed(self):
        assert detect_removed_upstream("c", {"a", "b"}) is True

    def test_empty_seen_set_treats_all_as_removed(self):
        # NOTE: the age-only background pass passes set() but the service
        # disables removal detection when seen is empty. This pure fn still
        # answers True; the gating lives in reevaluate_workspace.
        assert detect_removed_upstream("a", set()) is True


class TestJaccardAndCosine:
    def test_jaccard_empty_is_zero(self):
        assert jaccard([], []) == 0.0

    def test_jaccard_identical_is_one(self):
        assert jaccard(["a", "b"], ["a", "b"]) == 1.0

    def test_jaccard_partial(self):
        assert jaccard(["a", "b"], ["b", "c"]) == pytest.approx(1 / 3)

    def test_cosine_identical_is_one(self):
        assert _cosine([1.0, 0.0], [1.0, 0.0]) == pytest.approx(1.0)

    def test_cosine_orthogonal_is_zero(self):
        assert _cosine([1.0, 0.0], [0.0, 1.0]) == pytest.approx(0.0)

    def test_cosine_mismatched_length_is_zero(self):
        assert _cosine([1.0, 0.0], [1.0]) == 0.0

    def test_cosine_empty_is_zero(self):
        assert _cosine([], []) == 0.0


# ============================================================================
# Supersession detection (incl. two-docs-same-topic case)
# ============================================================================

class TestSupersessionDetection:
    def test_semantic_near_duplicate_supersedes_older(self):
        """Two docs, same topic (near-identical content), newer obsoletes older."""
        now = datetime.now(timezone.utc)
        old_ts = now - timedelta(days=10)
        emb = [1.0, 0.0, 0.0]
        older_docs = [
            {
                "doc_id": "old1",
                "text": "Quarterly report v1",
                "external_modified_at": old_ts,
                "freshness_status": "fresh",
            }
        ]
        cands = detect_supersession(
            newer_doc_id="new1",
            newer_text="Quarterly report v1",
            newer_embedding=emb,
            newer_entities=set(),
            newer_ts=now,
            older_docs=older_docs,
            older_embeddings={"old1": emb},
            sim_threshold=0.86,
        )
        assert len(cands) == 1
        assert cands[0].doc_id == "old1"
        assert cands[0].status == "superseded"
        assert "new1" in cands[0].reason

    def test_entity_overlap_supersedes_without_embedding(self):
        """Same subject matter (shared entities) even without embeddings."""
        now = datetime.now(timezone.utc)
        older_docs = [
            {
                "doc_id": "old1",
                "text": "x",
                "external_modified_at": now - timedelta(days=3),
                "freshness_status": "fresh",
            }
        ]
        cands = detect_supersession(
            newer_doc_id="new1",
            newer_text="y",
            newer_embedding=None,
            newer_entities={"Acme", "Invoice", "Q3"},
            newer_ts=now,
            older_docs=older_docs,
            older_entity_sets={"old1": {"Acme", "Invoice", "Q3", "Extra"}},
            entity_overlap_threshold=0.5,
        )
        assert len(cands) == 1
        assert cands[0].entity_overlap >= 0.5

    def test_different_topic_not_superseded(self):
        """Low similarity AND low overlap → no supersession."""
        now = datetime.now(timezone.utc)
        older_docs = [
            {
                "doc_id": "old1",
                "text": "x",
                "external_modified_at": now - timedelta(days=3),
                "freshness_status": "fresh",
            }
        ]
        cands = detect_supersession(
            newer_doc_id="new1",
            newer_text="y",
            newer_embedding=[1.0, 0.0],
            newer_entities={"Alpha"},
            newer_ts=now,
            older_docs=older_docs,
            older_embeddings={"old1": [0.0, 1.0]},  # orthogonal
            older_entity_sets={"old1": {"Beta"}},  # disjoint
        )
        assert cands == []

    def test_older_newer_not_superseded_when_newer_is_actually_older(self):
        """Heuristic confirm: if the 'newer' doc is older, don't supersede."""
        now = datetime.now(timezone.utc)
        emb = [1.0, 0.0]
        older_docs = [
            {
                "doc_id": "old1",
                "text": "x",
                "external_modified_at": now,  # candidate is NEWER than new1
                "freshness_status": "fresh",
            }
        ]
        cands = detect_supersession(
            newer_doc_id="new1",
            newer_text="x",
            newer_embedding=emb,
            newer_entities=set(),
            newer_ts=now - timedelta(days=5),  # new1 is actually older
            older_docs=older_docs,
            older_embeddings={"old1": emb},
            sim_threshold=0.86,
        )
        assert cands == []

    def test_already_superseded_or_removed_are_skipped(self):
        now = datetime.now(timezone.utc)
        emb = [1.0, 0.0]
        older_docs = [
            {
                "doc_id": "old1",
                "text": "x",
                "external_modified_at": now - timedelta(days=3),
                "freshness_status": "superseded",
            },
            {
                "doc_id": "old2",
                "text": "x",
                "external_modified_at": now - timedelta(days=3),
                "freshness_status": "removed",
            },
        ]
        cands = detect_supersession(
            newer_doc_id="new1",
            newer_text="x",
            newer_embedding=emb,
            newer_entities=set(),
            newer_ts=now,
            older_docs=older_docs,
            older_embeddings={"old1": emb, "old2": emb},
            sim_threshold=0.86,
        )
        assert cands == []

    def test_two_docs_same_topic_different_locations(self):
        """The user's clarified case: two distinct docs, same topic, one newer.

        Different external_ids / locations but near-duplicate content. The
        newer one (wherever it lives) supersedes the older one.
        """
        now = datetime.now(timezone.utc)
        emb = [0.9, 0.1, 0.0]
        # Old doc lives in Notion, new doc came in from Google Drive — same
        # content, different location.
        older_docs = [
            {
                "doc_id": "notion_old",
                "text": "Onboarding guide",
                "external_modified_at": now - timedelta(days=30),
                "freshness_status": "fresh",
            }
        ]
        cands = detect_supersession(
            newer_doc_id="gdrive_new",
            newer_text="Onboarding guide",
            newer_embedding=emb,
            newer_entities=set(),
            newer_ts=now,
            older_docs=older_docs,
            older_embeddings={"notion_old": emb},
            sim_threshold=0.86,
        )
        assert len(cands) == 1
        assert cands[0].doc_id == "notion_old"


# ============================================================================
# DB round-trips via DocFreshnessService
# ============================================================================

class TestDocFreshnessServiceDB:
    def test_mark_on_ingest_sets_fresh_fields(self, db, ws_id):
        doc = _make_doc(db, ws_id, external_id="ext1")
        svc = DocFreshnessService(db, workspace_id=ws_id)
        now = datetime.now(timezone.utc)
        svc.mark_on_ingest(
            doc,
            source_url="https://notion.so/x",
            content_hash=hash_text("hi"),
            source_modified_at=now,
        )
        db.refresh(doc)
        assert doc.freshness_status == "fresh"
        assert doc.source_url == "https://notion.so/x"
        assert doc.source_content_hash == hash_text("hi")
        # SQLite may round-trip the datetime without tzinfo; compare naive
        # values to stay portable across the hybrid dev DB.
        stored = doc.source_modified_at
        assert stored is not None
        assert stored.replace(tzinfo=None) == now.replace(tzinfo=None)
        assert doc.last_verified_at is not None
        assert doc.superseded_by is None

    def test_mark_stale_does_not_resurrect_removed(self, db, ws_id):
        doc = _make_doc(db, ws_id, external_id="ext1", freshness_status="removed")
        svc = DocFreshnessService(db, workspace_id=ws_id)
        svc.mark_stale(doc, reason="changed")
        db.refresh(doc)
        assert doc.freshness_status == "removed"  # unchanged

    def test_mark_stale_on_fresh_doc(self, db, ws_id):
        doc = _make_doc(db, ws_id, external_id="ext1", freshness_status="fresh")
        svc = DocFreshnessService(db, workspace_id=ws_id)
        svc.mark_stale(doc, reason="source_changed")
        db.refresh(doc)
        assert doc.freshness_status == "stale"

    def test_mark_superseded_links_newer(self, db, ws_id):
        doc = _make_doc(db, ws_id, external_id="ext1")
        svc = DocFreshnessService(db, workspace_id=ws_id)
        result = svc.mark_superseded(doc.id, "new_doc_id", "superseded by new_doc_id")
        assert result is not None
        db.refresh(doc)
        assert doc.freshness_status == "superseded"
        assert doc.superseded_by == "new_doc_id"

    def test_reevaluate_age_out_to_outdated(self, db, ws_id):
        old = datetime.now(timezone.utc) - timedelta(hours=48)
        doc = _make_doc(
            db, ws_id, external_id="ext1", last_verified_at=old, freshness_status="fresh"
        )
        svc = DocFreshnessService(db, workspace_id=ws_id)
        # Empty seen set → age-out only (no removal detection).
        summary = svc.reevaluate_workspace(ws_id, set())
        db.refresh(doc)
        assert doc.freshness_status == "outdated"
        assert summary.marked_outdated >= 1

    def test_reevaluate_removed_upstream(self, db, ws_id):
        doc = _make_doc(
            db,
            ws_id,
            external_id="ext1",
            last_verified_at=datetime.now(timezone.utc),
            freshness_status="fresh",
        )
        svc = DocFreshnessService(db, workspace_id=ws_id)
        # ext1 NOT in seen set → removed
        summary = svc.reevaluate_workspace(ws_id, {"some_other_id"})
        db.refresh(doc)
        assert doc.freshness_status == "removed"
        assert summary.marked_removed >= 1

    def test_reevaluate_keeps_fresh_when_present_and_recent(self, db, ws_id):
        doc = _make_doc(
            db,
            ws_id,
            external_id="ext1",
            last_verified_at=datetime.now(timezone.utc),
            source_modified_at=datetime.now(timezone.utc),
            external_modified_at=datetime.now(timezone.utc),
            freshness_status="fresh",
        )
        svc = DocFreshnessService(db, workspace_id=ws_id)
        summary = svc.reevaluate_workspace(ws_id, {"ext1"})
        db.refresh(doc)
        assert doc.freshness_status == "fresh"
        assert summary.unchanged >= 1

    def test_reevaluate_skips_already_removed_and_superseded(self, db, ws_id):
        _make_doc(db, ws_id, external_id="r1", freshness_status="removed")
        _make_doc(db, ws_id, external_id="s1", freshness_status="superseded")
        svc = DocFreshnessService(db, workspace_id=ws_id)
        summary = svc.reevaluate_workspace(ws_id, set())
        # They should be counted as unchanged, not re-aged.
        assert summary.unchanged >= 2

    def test_non_fresh_doc_ids(self, db, ws_id):
        _make_doc(db, ws_id, external_id="f1", freshness_status="fresh")
        _make_doc(db, ws_id, external_id="s1", freshness_status="stale")
        _make_doc(db, ws_id, external_id="o1", freshness_status="outdated")
        _make_doc(db, ws_id, external_id="r1", freshness_status="removed")
        _make_doc(db, ws_id, external_id="su1", freshness_status="superseded")
        svc = DocFreshnessService(db, workspace_id=ws_id)
        non_fresh = svc.non_fresh_doc_ids(ws_id)
        assert len(non_fresh) == 4  # stale, outdated, removed, superseded


# ============================================================================
# Postgres GraphRAG cascade
# ============================================================================

class TestGraphCascade:
    def _add_graph_node(self, db, ws_id, name, doc_id):
        node = GraphNode(
            workspace_id=ws_id,
            name=name,
            type="document",
            description="",
            properties={"doc_id": doc_id},
        )
        db.add(node)
        db.commit()
        db.refresh(node)
        return node

    def test_cascade_stamps_superseded_by_on_nodes(self, db, ws_id):
        node = self._add_graph_node(db, ws_id, "Entity1", "doc_old")
        svc = DocFreshnessService(db, workspace_id=ws_id)
        count = svc.cascade_graph_supersession("doc_old", "doc_new")
        assert count >= 1
        db.refresh(node)
        assert node.properties.get("superseded_by") == "doc_new"

    def test_cascade_does_not_touch_other_docs_nodes(self, db, ws_id):
        node_a = self._add_graph_node(db, ws_id, "A", "doc_a")
        node_b = self._add_graph_node(db, ws_id, "B", "doc_b")
        svc = DocFreshnessService(db, workspace_id=ws_id)
        svc.cascade_graph_supersession("doc_a", "doc_new")
        db.refresh(node_a)
        db.refresh(node_b)
        assert node_a.properties.get("superseded_by") == "doc_new"
        assert "superseded_by" not in (node_b.properties or {})

    def test_entity_set_for_doc(self, db, ws_id):
        self._add_graph_node(db, ws_id, "Alpha", "doc1")
        self._add_graph_node(db, ws_id, "Beta", "doc1")
        self._add_graph_node(db, ws_id, "Gamma", "doc2")
        svc = DocFreshnessService(db, workspace_id=ws_id)
        ents = svc.entity_set_for_doc("doc1")
        assert ents == {"Alpha", "Beta"}

    def test_apply_supersession_cascades_via_callback(self, db, ws_id):
        """End-to-end: apply_supersession marks the doc AND cascades to graph."""
        old_doc = _make_doc(db, ws_id, external_id="ext_old")
        node = self._add_graph_node(db, ws_id, "Entity", old_doc.id)

        svc = DocFreshnessService(db, workspace_id=ws_id)
        cand = SupersessionCandidate(
            doc_id=old_doc.id,
            status="superseded",
            reason="test",
            similarity=0.99,
            entity_overlap=0.0,
        )
        summary = svc.apply_supersession(
            [cand], "new_doc_id", cascade_to_graph=svc.cascade_graph_supersession
        )
        db.refresh(old_doc)
        db.refresh(node)
        assert summary.marked_superseded == 1
        assert summary.edges_superseded >= 1
        assert old_doc.freshness_status == "superseded"
        assert old_doc.superseded_by == "new_doc_id"
        assert node.properties.get("superseded_by") == "new_doc_id"
