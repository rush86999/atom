"""
Coverage + bug-hunt tests for core/doc_freshness_service.py.

These tests exercise the pure functions (hash, staleness math, jaccard,
cosine, supersession detection) and the DB-backed DocFreshnessService
methods with a mocked SQLAlchemy session. No network, no real DB.

Bug-hunt tests are marked with a leading ``BUG:`` docstring; each one was
verified to FAIL against the original source before the fix was applied.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Set
from unittest.mock import MagicMock

import pytest

import core.doc_freshness_service as dfs
from core.doc_freshness_service import (
    NON_FRESH_STATUSES,
    DocFreshnessService,
    ReevaluateSummary,
    SupersessionCandidate,
    _aware,
    _cosine,
    _is_genuinely_newer,
    compute_freshness_status,
    detect_removed_upstream,
    detect_supersession,
    doc_ts,
    extra_columns_for_ingest,
    derive_status_from_hash,
    hash_text,
    jaccard,
)


# ---------------------------------------------------------------------------
# Fake SQLAlchemy session + query helpers (mirror tests/core/ingestion pattern)
# ---------------------------------------------------------------------------


class _FakeQuery:
    """Minimal chainable query that returns rows seeded per test."""

    def __init__(self, rows: Optional[List[Any]] = None):
        self._rows = rows if rows is not None else []
        self._filters: List[Any] = []

    def filter(self, *a, **k):
        self._filters.append((a, k))
        return self

    def filter_by(self, **k):
        return self

    def order_by(self, *a):
        return self

    def limit(self, n):
        return self

    def all(self):
        return list(self._rows)

    def first(self):
        return self._rows[0] if self._rows else None

    # Support `.id` projection used by non_fresh_doc_ids
    def with_entities(self, *a):
        return self

    def __iter__(self):
        return iter(self._rows)


class FakeSession:
    """Tracks commits/rollbacks and serves seeded query results.

    The ``tables`` dict is keyed by the *argument* passed to ``query()``.
    Because SQLAlchemy callers sometimes pass a model class and sometimes
    a column entity (e.g. ``IngestedDocument.id``), we resolve via a small
    lookup that maps both forms to the same seed list. Tests register
    seeds under the model class; the ``_resolve`` helper normalizes
    column entities back to their parent class.
    """

    def __init__(self):
        self.committed = 0
        self.rolled_back = 0
        # Map model class -> list of rows
        self.tables: Dict[Any, List[Any]] = {}
        self.added: List[Any] = []

    def _resolve(self, model):
        # Column entity (InstrumentedAttribute) → parent class
        parent = getattr(model, "class_", None) or getattr(
            getattr(model, "parent", None), "class_", None
        )
        if parent is not None:
            return parent
        return model

    def query(self, model):
        return _FakeQuery(self.tables.get(self._resolve(model), []))

    def add(self, obj):
        self.added.append(obj)

    def commit(self):
        self.committed += 1
        # Some tests raise to exercise rollback paths
        if getattr(self, "_commit_raises", False):
            raise RuntimeError("commit boom")

    def rollback(self):
        self.rolled_back += 1

    def close(self):
        pass

    def execute(self, *a, **k):
        return MagicMock()


def _make_doc(**kw) -> MagicMock:
    """Build a doc-like object with freshness fields."""
    doc = MagicMock(spec=[
        "id", "workspace_id", "external_id", "external_modified_at",
        "source_url", "source_content_hash", "last_verified_at",
        "source_modified_at", "freshness_status", "superseded_by",
        "properties", "name",
    ])
    defaults = dict(
        id="doc-1",
        workspace_id="ws-1",
        external_id="ext-1",
        external_modified_at=None,
        source_url=None,
        source_content_hash=None,
        last_verified_at=None,
        source_modified_at=None,
        freshness_status="fresh",
        superseded_by=None,
        properties=None,
        name=None,
    )
    defaults.update(kw)
    for k, v in defaults.items():
        setattr(doc, k, v)
    return doc


# ===========================================================================
# Pure function tests
# ===========================================================================


class TestHashText:
    def test_hash_text_deterministic(self):
        assert hash_text("hello") == hash_text("hello")

    def test_hash_text_differs(self):
        assert hash_text("hello") != hash_text("world")

    def test_hash_text_unicode(self):
        # Should not raise on non-ascii
        out = hash_text("héllo → world")
        assert isinstance(out, str) and len(out) == 64


class TestDeriveStatusFromHash:
    def test_no_prior_hash_is_fresh(self):
        assert derive_status_from_hash(None, "abc") == "fresh"

    def test_empty_prior_hash_is_fresh(self):
        assert derive_status_from_hash("", "abc") == "fresh"

    def test_matching_hashes_fresh(self):
        assert derive_status_from_hash("abc", "abc") == "fresh"

    def test_differing_hashes_stale(self):
        assert derive_status_from_hash("abc", "xyz") == "stale"


class TestComputeFreshnessStatus:
    NOW = datetime(2026, 8, 7, 12, 0, 0, tzinfo=timezone.utc)

    def test_never_verified_is_outdated(self):
        assert compute_freshness_status(None, now=self.NOW) == "outdated"

    def test_recently_verified_is_fresh(self):
        lv = self.NOW - timedelta(hours=1)
        assert compute_freshness_status(lv, now=self.NOW) == "fresh"

    def test_older_than_ttl_is_outdated(self):
        lv = self.NOW - timedelta(hours=25)
        assert compute_freshness_status(lv, now=self.NOW, ttl_hours=24) == "outdated"

    def test_exactly_at_ttl_is_fresh_boundary(self):
        # age == ttl exactly → strict > → fresh (documented boundary)
        lv = self.NOW - timedelta(hours=24)
        assert compute_freshness_status(lv, now=self.NOW, ttl_hours=24) == "fresh"

    def test_source_modified_changed_is_stale(self):
        lv = self.NOW - timedelta(hours=1)
        src_now = self.NOW - timedelta(minutes=10)
        src_recorded = self.NOW - timedelta(hours=2)
        assert compute_freshness_status(
            lv, source_modified_at_now=src_now,
            last_verified_modified=src_recorded, now=self.NOW,
        ) == "stale"

    def test_source_modified_unchanged_is_fresh(self):
        lv = self.NOW - timedelta(hours=1)
        t = self.NOW - timedelta(hours=2)
        assert compute_freshness_status(
            lv, source_modified_at_now=t, last_verified_modified=t, now=self.NOW,
        ) == "fresh"

    def test_stale_within_subsecond_tolerance_is_fresh(self):
        # <1s difference → treated as unchanged
        lv = self.NOW - timedelta(hours=1)
        src_recorded = self.NOW - timedelta(hours=2)
        src_now = src_recorded + timedelta(milliseconds=500)
        assert compute_freshness_status(
            lv, source_modified_at_now=src_now,
            last_verified_modified=src_recorded, now=self.NOW,
        ) == "fresh"

    def test_outdated_takes_precedence_over_stale(self):
        # Verified long ago AND source changed → outdated wins
        lv = self.NOW - timedelta(hours=100)
        assert compute_freshness_status(
            lv,
            source_modified_at_now=self.NOW,
            last_verified_modified=self.NOW - timedelta(days=5),
            now=self.NOW, ttl_hours=24,
        ) == "outdated"

    def test_only_one_modified_signal_present_is_fresh(self):
        lv = self.NOW - timedelta(hours=1)
        # source_modified_at_now present but last_verified_modified None → fresh
        assert compute_freshness_status(
            lv, source_modified_at_now=self.NOW, last_verified_modified=None,
            now=self.NOW,
        ) == "fresh"
        # and vice-versa
        assert compute_freshness_status(
            lv, source_modified_at_now=None,
            last_verified_modified=self.NOW, now=self.NOW,
        ) == "fresh"

    def test_naive_datetimes_are_treated_as_utc(self):
        # Mixing tz-naive last_verified with tz-aware now must not crash
        naive_lv = datetime(2026, 8, 7, 11, 0, 0)  # 1h before NOW, naive
        assert compute_freshness_status(naive_lv, now=self.NOW) == "fresh"

    def test_naive_now_is_coerced(self):
        lv = self.NOW - timedelta(hours=1)
        naive_now = datetime(2026, 8, 7, 12, 0, 0)
        assert compute_freshness_status(lv, now=naive_now) == "fresh"

    def test_custom_ttl_zero(self):
        # ttl_hours=0 → anything with non-None last_verified older than 0 is outdated
        lv = self.NOW - timedelta(seconds=1)
        assert compute_freshness_status(lv, now=self.NOW, ttl_hours=0) == "outdated"

    def test_now_defaults_to_utc_when_none(self):
        lv = datetime.now(timezone.utc) - timedelta(seconds=1)
        # Should not raise; status fresh
        assert compute_freshness_status(lv) == "fresh"


class TestDetectRemovedUpstream:
    def test_present_not_removed(self):
        assert detect_removed_upstream("a", {"a", "b"}) is False

    def test_absent_is_removed(self):
        assert detect_removed_upstream("c", {"a", "b"}) is True

    def test_empty_listing_removes(self):
        assert detect_removed_upstream("a", set()) is True

    def test_iterable_input(self):
        # Lists (not just sets) should work
        assert detect_removed_upstream("a", ["a", "b"]) is False
        assert detect_removed_upstream("c", ["a", "b"]) is True


class TestJaccard:
    def test_identical_sets_one(self):
        assert jaccard({"a", "b"}, {"a", "b"}) == 1.0

    def test_disjoint_zero(self):
        assert jaccard({"a"}, {"b"}) == 0.0

    def test_empty_returns_zero(self):
        assert jaccard(set(), {"a"}) == 0.0
        assert jaccard({"a"}, set()) == 0.0
        assert jaccard(set(), set()) == 0.0

    def test_partial_overlap(self):
        assert jaccard({"a", "b"}, {"b", "c"}) == pytest.approx(1 / 3)

    def test_iterable_inputs(self):
        assert jaccard(["a", "a"], ["a"]) == 1.0  # dedup via set


class TestCosine:
    def test_identical_vectors_one(self):
        assert _cosine([1.0, 2.0, 3.0], [1.0, 2.0, 3.0]) == pytest.approx(1.0)

    def test_orthogonal_zero(self):
        assert _cosine([1.0, 0.0], [0.0, 1.0]) == pytest.approx(0.0)

    def test_empty_returns_zero(self):
        assert _cosine([], [1.0]) == 0.0
        assert _cosine([1.0], []) == 0.0

    def test_mismatched_length_returns_zero(self):
        assert _cosine([1.0, 2.0], [1.0]) == 0.0

    def test_zero_magnitude_returns_zero(self):
        assert _cosine([0.0, 0.0], [1.0, 1.0]) == 0.0

    def test_negative_correlation(self):
        assert _cosine([1.0, 0.0], [-1.0, 0.0]) == pytest.approx(-1.0)


class TestAware:
    def test_naive_gets_utc(self):
        d = datetime(2026, 1, 1, 0, 0, 0)
        out = _aware(d)
        assert out.tzinfo is not None

    def test_aware_unchanged(self):
        d = datetime(2026, 1, 1, tzinfo=timezone.utc)
        assert _aware(d) is d


class TestDocTs:
    def test_none_returns_none(self):
        assert doc_ts(None) is None

    def test_empty_dict_returns_none(self):
        assert doc_ts({}) is None

    def test_prefers_external_modified_at(self):
        ext = datetime(2026, 1, 2, tzinfo=timezone.utc)
        ing = datetime(2026, 1, 3, tzinfo=timezone.utc)
        assert doc_ts({"external_modified_at": ext, "ingested_at": ing}) == ext

    def test_falls_back_to_ingested_at(self):
        ing = datetime(2026, 1, 3, tzinfo=timezone.utc)
        assert doc_ts({"ingested_at": ing}) == ing

    def test_non_datetime_values_ignored(self):
        assert doc_ts({"external_modified_at": "not-a-date"}) is None
        assert doc_ts({"external_modified_at": 12345}) is None


class TestIsGenuinelyNewer:
    def test_both_none_returns_true(self):
        assert _is_genuinely_newer({}, None) is True

    def test_newer_none_returns_true(self):
        older = {"ingested_at": datetime(2026, 1, 1, tzinfo=timezone.utc)}
        assert _is_genuinely_newer(older, None) is True

    def test_older_none_returns_true(self):
        newer_ts = datetime(2026, 1, 1, tzinfo=timezone.utc)
        assert _is_genuinely_newer({}, newer_ts) is True

    def test_strictly_newer_true(self):
        older = {"ingested_at": datetime(2026, 1, 1, tzinfo=timezone.utc)}
        newer_ts = datetime(2026, 1, 2, tzinfo=timezone.utc)
        assert _is_genuinely_newer(older, newer_ts) is True

    def test_equal_timestamps_false(self):
        ts = datetime(2026, 1, 1, tzinfo=timezone.utc)
        older = {"ingested_at": ts}
        assert _is_genuinely_newer(older, ts) is False

    def test_older_than_newer_false(self):
        older = {"ingested_at": datetime(2026, 1, 5, tzinfo=timezone.utc)}
        newer_ts = datetime(2026, 1, 1, tzinfo=timezone.utc)
        assert _is_genuinely_newer(older, newer_ts) is False


# ===========================================================================
# detect_supersession — hybrid detection
# ===========================================================================


class TestDetectSupersession:
    NEWER_ID = "doc-new"
    NEWER_TS = datetime(2026, 6, 1, tzinfo=timezone.utc)
    NEWER_ENTS = {"acme", "invoice"}

    def _older(self, **kw) -> Dict[str, Any]:
        base = dict(
            doc_id="doc-old",
            text="old text",
            ingested_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
            external_modified_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
            freshness_status="fresh",
        )
        base.update(kw)
        return base

    def test_empty_newer_id_returns_empty(self):
        out = detect_supersession(
            newer_doc_id="", newer_text="x", newer_embedding=[1.0],
            newer_entities=set(), newer_ts=self.NEWER_TS, older_docs=[self._older()],
        )
        assert out == []

    def test_self_not_candidate(self):
        out = detect_supersession(
            newer_doc_id=self.NEWER_ID, newer_text="x",
            newer_embedding=[1.0], newer_entities=set(),
            newer_ts=self.NEWER_TS,
            older_docs=[self._older(doc_id=self.NEWER_ID)],
        )
        assert out == []

    def test_no_doc_id_skipped(self):
        out = detect_supersession(
            newer_doc_id=self.NEWER_ID, newer_text="x",
            newer_embedding=[1.0], newer_entities=set(),
            newer_ts=self.NEWER_TS,
            older_docs=[self._older(doc_id="")],
        )
        assert out == []

    def test_already_removed_skipped(self):
        out = detect_supersession(
            newer_doc_id=self.NEWER_ID, newer_text="x",
            newer_embedding=[1.0], newer_entities=set(),
            newer_ts=self.NEWER_TS,
            older_docs=[self._older(freshness_status="removed")],
        )
        assert out == []

    def test_already_superseded_skipped(self):
        out = detect_supersession(
            newer_doc_id=self.NEWER_ID, newer_text="x",
            newer_embedding=[1.0], newer_entities=set(),
            newer_ts=self.NEWER_TS,
            older_docs=[self._older(freshness_status="superseded")],
        )
        assert out == []

    def test_semantic_near_duplicate_candidate(self):
        emb = [1.0, 0.0]
        out = detect_supersession(
            newer_doc_id=self.NEWER_ID, newer_text="x",
            newer_embedding=emb, newer_entities=set(),
            newer_ts=self.NEWER_TS,
            older_docs=[self._older()],
            older_embeddings={"doc-old": emb},
            sim_threshold=0.86,
        )
        assert len(out) == 1
        assert out[0].doc_id == "doc-old"
        assert out[0].status == "superseded"
        assert "superseded by doc-new" in out[0].reason
        assert "sim=" in out[0].reason

    def test_entity_overlap_candidate(self):
        out = detect_supersession(
            newer_doc_id=self.NEWER_ID, newer_text="x",
            newer_embedding=[1.0], newer_entities=self.NEWER_ENTS,
            newer_ts=self.NEWER_TS,
            older_docs=[self._older()],
            older_entity_sets={"doc-old": self.NEWER_ENTS},
            entity_overlap_threshold=0.5,
            sim_threshold=0.99,  # above what cosine will give (different vecs)
        )
        assert len(out) == 1
        assert "entity_overlap=" in out[0].reason

    def test_embed_fn_used_when_no_precomputed(self):
        emb = [1.0, 0.0]
        calls = []

        def embed(text):
            calls.append(text)
            return emb

        out = detect_supersession(
            newer_doc_id=self.NEWER_ID, newer_text="x",
            newer_embedding=emb, newer_entities=set(),
            newer_ts=self.NEWER_TS,
            older_docs=[self._older(text="custom text")],
            embed_fn=embed,
        )
        assert len(out) == 1
        assert calls == ["custom text"]

    def test_embed_fn_exception_handled(self):
        def embed(text):
            raise RuntimeError("boom")

        out = detect_supersession(
            newer_doc_id=self.NEWER_ID, newer_text="x",
            newer_embedding=[1.0], newer_entities=set(),
            newer_ts=self.NEWER_TS,
            older_docs=[self._older()],
            embed_fn=embed,
            entity_overlap_threshold=0.99,
        )
        assert out == []  # no signal → no candidate

    def test_not_genuinely_newer_skipped(self):
        emb = [1.0, 0.0]
        # older doc has a LATER timestamp than newer
        older = self._older(
            ingested_at=datetime(2026, 12, 1, tzinfo=timezone.utc),
            external_modified_at=datetime(2026, 12, 1, tzinfo=timezone.utc),
        )
        out = detect_supersession(
            newer_doc_id=self.NEWER_ID, newer_text="x",
            newer_embedding=emb, newer_entities=set(),
            newer_ts=self.NEWER_TS,
            older_docs=[older],
            older_embeddings={"doc-old": emb},
        )
        assert out == []

    def test_below_thresholds_not_candidate(self):
        out = detect_supersession(
            newer_doc_id=self.NEWER_ID, newer_text="x",
            newer_embedding=[1.0, 0.0], newer_entities={"x"},
            newer_ts=self.NEWER_TS,
            older_docs=[self._older()],
            older_embeddings={"doc-old": [0.0, 1.0]},  # orthogonal → sim 0
            older_entity_sets={"doc-old": {"y"}},  # disjoint → overlap 0
            sim_threshold=0.86, entity_overlap_threshold=0.5,
        )
        assert out == []

    def test_reason_includes_both_signals_when_both_match(self):
        emb = [1.0, 0.0]
        out = detect_supersession(
            newer_doc_id=self.NEWER_ID, newer_text="x",
            newer_embedding=emb, newer_entities={"a", "b"},
            newer_ts=self.NEWER_TS,
            older_docs=[self._older()],
            older_embeddings={"doc-old": emb},
            older_entity_sets={"doc-old": {"a", "b"}},
        )
        assert len(out) == 1
        assert "sim=" in out[0].reason and "entity_overlap=" in out[0].reason

    def test_multiple_candidates_returned_in_order(self):
        emb = [1.0, 0.0]
        older_a = self._older(doc_id="a")
        older_b = self._older(doc_id="b")
        out = detect_supersession(
            newer_doc_id=self.NEWER_ID, newer_text="x",
            newer_embedding=emb, newer_entities=set(),
            newer_ts=self.NEWER_TS,
            older_docs=[older_a, older_b],
            older_embeddings={"a": emb, "b": emb},
        )
        assert [c.doc_id for c in out] == ["a", "b"]


# ===========================================================================
# SupersessionCandidate / ReevaluateSummary dataclasses
# ===========================================================================


class TestDataclasses:
    def test_candidate_defaults(self):
        c = SupersessionCandidate(doc_id="x", status="superseded", reason="r")
        assert c.similarity == 0.0
        assert c.entity_overlap == 0.0

    def test_summary_defaults_and_dict(self):
        s = ReevaluateSummary(checked=3, marked_fresh=1, marked_superseded=2)
        d = s.as_dict()
        assert d["checked"] == 3
        assert d["fresh"] == 1
        assert d["superseded"] == 2
        assert d["unchanged"] == 0


# ===========================================================================
# extra_columns_for_ingest
# ===========================================================================


class TestExtraColumns:
    def test_basic(self):
        dt = datetime(2026, 1, 1, tzinfo=timezone.utc)
        out = extra_columns_for_ingest(
            freshness_status="fresh", source_modified_at=dt, source_url="http://x",
        )
        assert out == {
            "freshness_status": "fresh",
            "source_modified_at": dt.isoformat(),
            "source_url": "http://x",
        }

    def test_none_modified_and_url(self):
        out = extra_columns_for_ingest(
            freshness_status="stale", source_modified_at=None, source_url=None,
        )
        assert out["source_modified_at"] == ""
        assert out["source_url"] == ""


# ===========================================================================
# DocFreshnessService — DB-backed methods (mocked session)
# ===========================================================================


class TestMarkOnIngest:
    def test_sets_fields_and_commits(self):
        sess = FakeSession()
        svc = DocFreshnessService(sess, workspace_id="ws-1")
        doc = _make_doc()
        svc.mark_on_ingest(
            doc, source_url="http://x", content_hash="abc",
            source_modified_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        )
        assert doc.source_url == "http://x"
        assert doc.source_content_hash == "abc"
        assert doc.source_modified_at == datetime(2026, 1, 1, tzinfo=timezone.utc)
        assert doc.freshness_status == "fresh"
        assert doc.superseded_by is None
        assert doc.last_verified_at is not None
        assert sess.committed == 1

    def test_commit_failure_rolls_back_and_swallows(self):
        sess = FakeSession()
        sess._commit_raises = True
        svc = DocFreshnessService(sess, workspace_id="ws-1")
        doc = _make_doc()
        # Must not raise
        svc.mark_on_ingest(doc, source_url=None, content_hash="x",
                           source_modified_at=None)
        assert sess.rolled_back == 1


class TestMarkStale:
    def test_marks_stale(self):
        sess = FakeSession()
        svc = DocFreshnessService(sess)
        doc = _make_doc(freshness_status="fresh")
        svc.mark_stale(doc)
        assert doc.freshness_status == "stale"
        assert sess.committed == 1

    def test_removed_doc_not_resurrected(self):
        sess = FakeSession()
        svc = DocFreshnessService(sess)
        doc = _make_doc(freshness_status="removed")
        svc.mark_stale(doc)
        assert doc.freshness_status == "removed"
        assert sess.committed == 0  # early return before commit

    def test_commit_failure_rolls_back(self):
        sess = FakeSession()
        sess._commit_raises = True
        svc = DocFreshnessService(sess)
        doc = _make_doc(freshness_status="fresh")
        svc.mark_stale(doc)
        assert sess.rolled_back == 1

    def test_bug_mark_stale_resurrects_superseded_doc(self):
        """BUG: mark_stale only guards 'removed' but flips a 'superseded'
        doc back to 'stale', destroying the supersession link state.
        Repro: a superseded doc passed to mark_stale becomes stale.
        Expected: superseded docs are terminal (like removed) and must not
        be resurrected to stale."""
        sess = FakeSession()
        svc = DocFreshnessService(sess)
        doc = _make_doc(freshness_status="superseded", superseded_by="doc-new")
        svc.mark_stale(doc)
        assert doc.freshness_status == "superseded", (
            "mark_stale must not resurrect a superseded doc back to 'stale'"
        )


class TestMarkSuperseded:
    def test_marks_superseded(self):
        sess = FakeSession()
        doc = _make_doc(id="old", workspace_id="ws-1")
        sess.tables[dfs.IngestedDocument] = [doc]
        svc = DocFreshnessService(sess, workspace_id="ws-1")
        result = svc.mark_superseded("old", "new", "reason")
        assert result is doc
        assert doc.freshness_status == "superseded"
        assert doc.superseded_by == "new"
        assert sess.committed == 1

    def test_missing_doc_returns_none(self):
        sess = FakeSession()
        sess.tables[dfs.IngestedDocument] = []
        svc = DocFreshnessService(sess, workspace_id="ws-1")
        assert svc.mark_superseded("nope", "new", "r") is None

    def test_commit_failure_rolls_back(self):
        sess = FakeSession()
        doc = _make_doc(id="old", workspace_id="ws-1")
        sess.tables[dfs.IngestedDocument] = [doc]
        sess._commit_raises = True
        svc = DocFreshnessService(sess, workspace_id="ws-1")
        # returns the doc anyway (status mutated in-memory); rollback swallowed
        out = svc.mark_superseded("old", "new", "r")
        assert out is doc
        assert sess.rolled_back == 1


class TestReevaluateWorkspace:
    NOW = datetime(2026, 8, 7, 12, 0, 0, tzinfo=timezone.utc)

    def test_empty_workspace(self):
        sess = FakeSession()
        sess.tables[dfs.IngestedDocument] = []
        svc = DocFreshnessService(sess)
        s = svc.reevaluate_workspace("ws-1", seen_external_ids=set(), now=self.NOW)
        assert s.checked == 0
        assert s.as_dict()["unchanged"] == 0

    def test_removed_detection(self):
        sess = FakeSession()
        doc = _make_doc(
            external_id="gone", freshness_status="fresh",
            last_verified_at=self.NOW - timedelta(hours=1),
        )
        sess.tables[dfs.IngestedDocument] = [doc]
        svc = DocFreshnessService(sess)
        s = svc.reevaluate_workspace("ws-1", seen_external_ids={"other"}, now=self.NOW)
        assert doc.freshness_status == "removed"
        assert s.marked_removed == 1

    def test_already_removed_unchanged(self):
        sess = FakeSession()
        doc = _make_doc(
            external_id="gone", freshness_status="removed",
            last_verified_at=self.NOW,
        )
        sess.tables[dfs.IngestedDocument] = [doc]
        svc = DocFreshnessService(sess)
        s = svc.reevaluate_workspace("ws-1", seen_external_ids={"other"}, now=self.NOW)
        assert doc.freshness_status == "removed"
        assert s.unchanged == 1
        assert s.marked_removed == 0

    def test_superseded_left_alone(self):
        sess = FakeSession()
        doc = _make_doc(
            external_id="x", freshness_status="superseded",
            last_verified_at=None,  # would normally → outdated
        )
        sess.tables[dfs.IngestedDocument] = [doc]
        svc = DocFreshnessService(sess)
        s = svc.reevaluate_workspace("ws-1", seen_external_ids=set(), now=self.NOW)
        assert doc.freshness_status == "superseded"
        assert s.unchanged == 1

    def test_aging_to_outdated(self):
        sess = FakeSession()
        doc = _make_doc(
            external_id="x", freshness_status="fresh",
            last_verified_at=self.NOW - timedelta(hours=100),
        )
        sess.tables[dfs.IngestedDocument] = [doc]
        svc = DocFreshnessService(sess)
        s = svc.reevaluate_workspace("ws-1", seen_external_ids=set(), now=self.NOW)
        assert doc.freshness_status == "outdated"
        assert s.marked_outdated == 1
        assert doc.last_verified_at == self.NOW

    def test_source_changed_to_stale(self):
        sess = FakeSession()
        doc = _make_doc(
            external_id="x", freshness_status="fresh",
            last_verified_at=self.NOW - timedelta(hours=1),
            external_modified_at=self.NOW,
            source_modified_at=self.NOW - timedelta(hours=2),
        )
        sess.tables[dfs.IngestedDocument] = [doc]
        svc = DocFreshnessService(sess)
        s = svc.reevaluate_workspace("ws-1", seen_external_ids={"x"}, now=self.NOW)
        assert doc.freshness_status == "stale"
        assert s.marked_stale == 1

    def test_remains_fresh_unchanged(self):
        sess = FakeSession()
        doc = _make_doc(
            external_id="x", freshness_status="fresh",
            last_verified_at=self.NOW - timedelta(hours=1),
        )
        sess.tables[dfs.IngestedDocument] = [doc]
        svc = DocFreshnessService(sess)
        s = svc.reevaluate_workspace("ws-1", seen_external_ids={"x"}, now=self.NOW)
        assert doc.freshness_status == "fresh"
        assert s.unchanged == 1

    def test_stale_recovers_to_fresh(self):
        # A doc previously marked stale (source_changed) whose source now
        # matches again transitions back to fresh via reevaluate.
        sess = FakeSession()
        t = self.NOW - timedelta(hours=2)
        doc = _make_doc(
            external_id="x", freshness_status="stale",
            last_verified_at=self.NOW - timedelta(hours=1),
            external_modified_at=t, source_modified_at=t,
        )
        sess.tables[dfs.IngestedDocument] = [doc]
        svc = DocFreshnessService(sess)
        s = svc.reevaluate_workspace("ws-1", seen_external_ids={"x"}, now=self.NOW)
        assert doc.freshness_status == "fresh"
        assert s.marked_fresh == 1
        assert doc.last_verified_at == self.NOW

    def test_doc_with_no_external_id_skips_removal(self):
        # external_id None + non-empty seen → falls through to aging recompute
        sess = FakeSession()
        doc = _make_doc(
            external_id=None, freshness_status="fresh",
            last_verified_at=self.NOW - timedelta(hours=1),
        )
        sess.tables[dfs.IngestedDocument] = [doc]
        svc = DocFreshnessService(sess)
        s = svc.reevaluate_workspace("ws-1", seen_external_ids={"other"}, now=self.NOW)
        assert doc.freshness_status == "fresh"
        assert s.unchanged == 1

    def test_commit_failure_rolls_back(self):
        sess = FakeSession()
        doc = _make_doc(
            external_id="x", freshness_status="fresh",
            last_verified_at=self.NOW - timedelta(hours=100),
        )
        sess.tables[dfs.IngestedDocument] = [doc]
        sess._commit_raises = True
        svc = DocFreshnessService(sess)
        svc.reevaluate_workspace("ws-1", seen_external_ids=set(), now=self.NOW)
        assert sess.rolled_back == 1


class TestApplySupersession:
    def test_applies_candidates(self):
        sess = FakeSession()
        doc = _make_doc(id="old", workspace_id="ws-1")
        sess.tables[dfs.IngestedDocument] = [doc]
        svc = DocFreshnessService(sess, workspace_id="ws-1")
        cands = [SupersessionCandidate(doc_id="old", status="superseded", reason="r")]
        s = svc.apply_supersession(cands, newer_doc_id="new")
        assert s.marked_superseded == 1
        assert doc.freshness_status == "superseded"

    def test_missing_doc_skipped(self):
        sess = FakeSession()
        sess.tables[dfs.IngestedDocument] = []
        svc = DocFreshnessService(sess, workspace_id="ws-1")
        cands = [SupersessionCandidate(doc_id="nope", status="superseded", reason="r")]
        s = svc.apply_supersession(cands, newer_doc_id="new")
        assert s.marked_superseded == 0

    def test_cascade_to_graph_invoked(self):
        sess = FakeSession()
        doc = _make_doc(id="old", workspace_id="ws-1")
        sess.tables[dfs.IngestedDocument] = [doc]
        svc = DocFreshnessService(sess, workspace_id="ws-1")

        def cascade(src, by):
            return 7

        cands = [SupersessionCandidate(doc_id="old", status="superseded", reason="r")]
        s = svc.apply_supersession(cands, newer_doc_id="new", cascade_to_graph=cascade)
        assert s.edges_superseded == 7

    def test_cascade_exception_swallowed(self):
        sess = FakeSession()
        doc = _make_doc(id="old", workspace_id="ws-1")
        sess.tables[dfs.IngestedDocument] = [doc]
        svc = DocFreshnessService(sess, workspace_id="ws-1")

        def cascade(src, by):
            raise RuntimeError("graph down")

        cands = [SupersessionCandidate(doc_id="old", status="superseded", reason="r")]
        s = svc.apply_supersession(cands, newer_doc_id="new", cascade_to_graph=cascade)
        assert s.marked_superseded == 1
        assert s.edges_superseded == 0  # not counted on exception


class TestCascadeGraphSupersession:
    def test_no_workspace_returns_zero(self):
        sess = FakeSession()
        svc = DocFreshnessService(sess, workspace_id=None)
        assert svc.cascade_graph_supersession("old", "new") == 0

    def test_stamps_matching_nodes_and_edges(self):
        sess = FakeSession()
        node_match = MagicMock(id="n1", workspace_id="ws-1",
                               name="Acme", properties={"doc_id": "old"})
        node_other = MagicMock(id="n2", workspace_id="ws-1",
                               name="Other", properties={"doc_id": "different"})
        edge_match = MagicMock(id="e1", workspace_id="ws-1",
                               properties={"doc_id": "old"})
        # GraphNode/GraphEdge imported lazily inside the method from core.models
        from core import models as models_mod
        sess.tables[models_mod.GraphNode] = [node_match, node_other]
        sess.tables[models_mod.GraphEdge] = [edge_match]
        svc = DocFreshnessService(sess, workspace_id="ws-1")
        count = svc.cascade_graph_supersession("old", "new")
        assert count == 2  # 1 node + 1 edge
        assert node_match.properties["superseded_by"] == "new"
        assert "superseded_by" not in node_other.properties

    def test_commit_failure_rolls_back(self):
        sess = FakeSession()
        from core import models as models_mod
        node = MagicMock(id="n1", workspace_id="ws-1")
        node.properties = {"doc_id": "old"}
        sess.tables[models_mod.GraphNode] = [node]
        sess.tables[models_mod.GraphEdge] = []
        sess._commit_raises = True
        svc = DocFreshnessService(sess, workspace_id="ws-1")
        # Count reflects stamps attempted before commit raised; rollback runs.
        count = svc.cascade_graph_supersession("old", "new")
        assert count == 1
        assert sess.rolled_back == 1


class TestEntitySetForDoc:
    def test_no_workspace_returns_empty(self):
        sess = FakeSession()
        svc = DocFreshnessService(sess, workspace_id=None)
        assert svc.entity_set_for_doc("x") == set()

    def test_returns_matching_node_names(self):
        sess = FakeSession()
        from core import models as models_mod
        n1 = MagicMock()
        n1.name = "Acme"
        n1.properties = {"doc_id": "x"}
        n2 = MagicMock()
        n2.name = "Beta"
        n2.properties = {"doc_id": "other"}
        n3 = MagicMock()
        n3.name = None  # no name → skipped
        n3.properties = {"doc_id": "x"}
        sess.tables[models_mod.GraphNode] = [n1, n2, n3]
        svc = DocFreshnessService(sess, workspace_id="ws-1")
        out = svc.entity_set_for_doc("x")
        assert out == {"Acme"}

    def test_exception_returns_empty(self):
        sess = FakeSession()
        sess.query = MagicMock(side_effect=RuntimeError("boom"))
        svc = DocFreshnessService(sess, workspace_id="ws-1")
        assert svc.entity_set_for_doc("x") == set()


class TestNonFreshDocIds:
    def test_returns_set_of_ids(self):
        sess = FakeSession()
        # non_fresh_doc_ids uses .id projection; FakeQuery.all returns rows
        r1 = MagicMock()
        r1.id = "d1"
        # The code does {r[0] for r in rows} — emulate tuple rows
        sess.tables[dfs.IngestedDocument] = [("d1",), ("d2",)]
        svc = DocFreshnessService(sess)
        out = svc.non_fresh_doc_ids("ws-1")
        assert out == {"d1", "d2"}

    def test_empty(self):
        sess = FakeSession()
        sess.tables[dfs.IngestedDocument] = []
        svc = DocFreshnessService(sess)
        assert svc.non_fresh_doc_ids("ws-1") == set()


class TestGetWithWorkspace:
    def test_get_returns_first_match(self):
        sess = FakeSession()
        doc = _make_doc(id="x", workspace_id="ws-1")
        sess.tables[dfs.IngestedDocument] = [doc]
        svc = DocFreshnessService(sess, workspace_id="ws-1")
        assert svc._get("x") is doc

    def test_get_no_workspace(self):
        sess = FakeSession()
        doc = _make_doc(id="x")
        sess.tables[dfs.IngestedDocument] = [doc]
        svc = DocFreshnessService(sess, workspace_id=None)
        assert svc._get("x") is doc

    def test_get_missing(self):
        sess = FakeSession()
        sess.tables[dfs.IngestedDocument] = []
        svc = DocFreshnessService(sess, workspace_id="ws-1")
        assert svc._get("nope") is None


class TestModuleConfig:
    def test_non_fresh_statuses_constant(self):
        assert NON_FRESH_STATUSES == frozenset(
            {"stale", "outdated", "removed", "superseded"}
        )
