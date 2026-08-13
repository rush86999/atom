"""Coverage wave 64d — core/doc_freshness_service.py (TDD, mocked session,
no DB, no network).

Standalone coverage of the whole module: config constants, hash_text,
derive_status_from_hash, compute_freshness_status (tz-aware/naive mixes,
TTL boundary, precedence, sub-second tolerance), detect_removed_upstream,
jaccard, _cosine, SupersessionCandidate/ReevaluateSummary dataclasses,
doc_ts, _aware, _is_genuinely_newer, detect_supersession (all hybrid
signals, embed-fn lazy path + failure, timestamp heuristics, reason
composition), DocFreshnessService (mark_on_ingest, mark_stale terminal
guards, mark_superseded, reevaluate_workspace transitions + commit
failure, apply_supersession cascade + exception, cascade_graph_supersession
with/without workspace + commit failure, entity_set_for_doc, non_fresh_
doc_ids, _get), and extra_columns_for_ingest.
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
    derive_status_from_hash,
    doc_ts,
    extra_columns_for_ingest,
    hash_text,
    jaccard,
)


# ---------------------------------------------------------------------------
# Fakes (mirror the codebase's mocked-session pattern)
# ---------------------------------------------------------------------------


class _FakeQuery:
    def __init__(self, rows=None):
        self._rows = rows if rows is not None else []

    def filter(self, *a, **k):
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

    def with_entities(self, *a):
        return self

    def __iter__(self):
        return iter(self._rows)


class FakeSession:
    def __init__(self):
        self.committed = 0
        self.rolled_back = 0
        self.tables: Dict[Any, List[Any]] = {}
        self._commit_raises = False

    def _resolve(self, model):
        parent = getattr(model, "class_", None) or getattr(
            getattr(model, "parent", None), "class_", None
        )
        return parent if parent is not None else model

    def query(self, model):
        return _FakeQuery(self.tables.get(self._resolve(model), []))

    def commit(self):
        self.committed += 1
        if self._commit_raises:
            raise RuntimeError("commit boom")

    def rollback(self):
        self.rolled_back += 1


def _doc(**kw) -> MagicMock:
    doc = MagicMock(spec=[
        "id", "workspace_id", "external_id", "external_modified_at",
        "source_url", "source_content_hash", "last_verified_at",
        "source_modified_at", "freshness_status", "superseded_by",
        "properties", "name",
    ])
    defaults = dict(
        id="doc-1", workspace_id="ws-1", external_id="ext-1",
        external_modified_at=None, source_url=None, source_content_hash=None,
        last_verified_at=None, source_modified_at=None,
        freshness_status="fresh", superseded_by=None, properties=None, name=None,
    )
    defaults.update(kw)
    for k, v in defaults.items():
        setattr(doc, k, v)
    return doc


# ===========================================================================
# Config / pure helpers
# ===========================================================================


class TestModuleConfig:
    def test_env_defaults(self):
        assert isinstance(dfs.FRESHNESS_TTL_HOURS, float)
        assert dfs.FRESHNESS_TTL_HOURS == 24.0
        assert isinstance(dfs.SUPERSESSION_SIM_THRESHOLD, float)
        assert isinstance(dfs.SUPERSESSION_ENTITY_OVERLAP, float)
        assert dfs.FRESHNESS_FILTER_ENABLED in (True, False)
        assert NON_FRESH_STATUSES == frozenset(
            {"stale", "outdated", "removed", "superseded"}
        )


class TestHashText:
    def test_known_sha256(self):
        assert hash_text("hello") == (
            "2cf24dba5fb0a30e26e83b2ac5b9e29e1b161e5c1fa7425e73043362938b9824"
        )

    def test_empty_string(self):
        assert hash_text("") == (
            "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
        )

    def test_deterministic_and_utf8(self):
        a = hash_text("héllo → world")
        assert a == hash_text("héllo → world")
        assert a != hash_text("hello")
        assert len(a) == 64


class TestDeriveStatusFromHash:
    @pytest.mark.parametrize("old_hash,new_hash,expected", [
        (None, "abc", "fresh"),
        ("", "abc", "fresh"),
        ("abc", "abc", "fresh"),
        ("abc", "xyz", "stale"),
    ])
    def test_matrix(self, old_hash, new_hash, expected):
        assert derive_status_from_hash(old_hash, new_hash) == expected


class TestComputeFreshnessStatus:
    NOW = datetime(2026, 8, 12, 12, 0, 0, tzinfo=timezone.utc)

    def test_never_verified_outdated(self):
        assert compute_freshness_status(None, now=self.NOW) == "outdated"

    def test_recent_fresh(self):
        assert compute_freshness_status(self.NOW - timedelta(hours=1), now=self.NOW) == "fresh"

    def test_aged_outdated(self):
        assert compute_freshness_status(self.NOW - timedelta(hours=25), now=self.NOW) == "outdated"

    def test_exact_ttl_boundary_fresh(self):
        lv = self.NOW - timedelta(hours=24)
        assert compute_freshness_status(lv, now=self.NOW) == "fresh"

    def test_zero_ttl_outdated(self):
        lv = self.NOW - timedelta(seconds=1)
        assert compute_freshness_status(lv, now=self.NOW, ttl_hours=0) == "outdated"

    def test_source_drift_stale(self):
        assert compute_freshness_status(
            self.NOW - timedelta(hours=1),
            source_modified_at_now=self.NOW,
            last_verified_modified=self.NOW - timedelta(hours=2),
            now=self.NOW,
        ) == "stale"

    def test_source_aligned_fresh(self):
        t = self.NOW - timedelta(hours=2)
        assert compute_freshness_status(
            self.NOW - timedelta(hours=1), source_modified_at_now=t,
            last_verified_modified=t, now=self.NOW,
        ) == "fresh"

    def test_subsecond_delta_tolerated(self):
        rec = self.NOW - timedelta(hours=2)
        cur = rec + timedelta(milliseconds=900)
        assert compute_freshness_status(
            self.NOW - timedelta(hours=1), source_modified_at_now=cur,
            last_verified_modified=rec, now=self.NOW,
        ) == "fresh"

    def test_outdated_wins_over_stale(self):
        assert compute_freshness_status(
            self.NOW - timedelta(hours=100), source_modified_at_now=self.NOW,
            last_verified_modified=self.NOW - timedelta(days=5), now=self.NOW,
        ) == "outdated"

    def test_one_sided_signals_fresh(self):
        assert compute_freshness_status(
            self.NOW - timedelta(hours=1), source_modified_at_now=self.NOW,
            last_verified_modified=None, now=self.NOW,
        ) == "fresh"
        assert compute_freshness_status(
            self.NOW - timedelta(hours=1), source_modified_at_now=None,
            last_verified_modified=self.NOW, now=self.NOW,
        ) == "fresh"

    def test_naive_last_verified_coerced(self):
        naive = datetime(2026, 8, 12, 11, 0, 0)
        assert compute_freshness_status(naive, now=self.NOW) == "fresh"

    def test_naive_now_coerced(self):
        naive_now = datetime(2026, 8, 12, 12, 0, 0)
        lv = self.NOW - timedelta(hours=1)
        assert compute_freshness_status(lv, now=naive_now) == "fresh"

    def test_naive_source_signals_coerced(self):
        rec = datetime(2026, 8, 12, 10, 0, 0)  # naive
        cur = datetime(2026, 8, 12, 11, 0, 0)  # naive
        assert compute_freshness_status(
            self.NOW - timedelta(hours=1), source_modified_at_now=cur,
            last_verified_modified=rec, now=self.NOW,
        ) == "stale"

    def test_now_defaults_to_utc(self):
        lv = datetime.now(timezone.utc) - timedelta(seconds=5)
        assert compute_freshness_status(lv) == "fresh"


class TestDetectRemovedUpstream:
    @pytest.mark.parametrize("ext,seen,expected", [
        ("a", {"a", "b"}, False),
        ("c", {"a", "b"}, True),
        ("a", set(), True),
        ("a", [], True),
    ])
    def test_matrix(self, ext, seen, expected):
        assert detect_removed_upstream(ext, seen) is expected

    def test_generator_input(self):
        assert detect_removed_upstream("b", (x for x in ["a", "b"])) is False


class TestJaccard:
    def test_full_overlap(self):
        assert jaccard({"a", "b"}, {"a", "b"}) == 1.0

    def test_disjoint(self):
        assert jaccard({"a"}, {"b"}) == 0.0

    def test_empty_side(self):
        assert jaccard(set(), {"a"}) == 0.0
        assert jaccard({"a"}, set()) == 0.0
        assert jaccard(set(), set()) == 0.0

    def test_partial(self):
        assert jaccard({"a", "b"}, {"b", "c"}) == pytest.approx(1 / 3)

    def test_duplicates_deduped(self):
        assert jaccard(["a", "a", "b"], ["a", "b"]) == 1.0


class TestCosine:
    def test_identical(self):
        assert _cosine([1.0, 2.0, 3.0], [1.0, 2.0, 3.0]) == pytest.approx(1.0)

    def test_orthogonal(self):
        assert _cosine([1.0, 0.0], [0.0, 1.0]) == pytest.approx(0.0)

    def test_negative(self):
        assert _cosine([1.0, 0.0], [-1.0, 0.0]) == pytest.approx(-1.0)

    @pytest.mark.parametrize("a,b", [
        ([], [1.0]), ([1.0], []), ([1.0, 2.0], [1.0]),
    ])
    def test_invalid_shapes(self, a, b):
        assert _cosine(a, b) == 0.0

    def test_zero_magnitude(self):
        assert _cosine([0.0, 0.0], [1.0, 1.0]) == 0.0

    def test_proportional(self):
        assert _cosine([1.0, 2.0], [2.0, 4.0]) == pytest.approx(1.0)


class TestAware:
    def test_naive_gets_utc(self):
        out = _aware(datetime(2026, 1, 1))
        assert out.tzinfo == timezone.utc

    def test_aware_unchanged(self):
        d = datetime(2026, 1, 1, tzinfo=timezone.utc)
        assert _aware(d) is d


class TestDocTs:
    def test_none(self):
        assert doc_ts(None) is None

    def test_empty(self):
        assert doc_ts({}) is None

    def test_prefers_external_modified_at(self):
        ext = datetime(2026, 1, 2, tzinfo=timezone.utc)
        ing = datetime(2026, 1, 3, tzinfo=timezone.utc)
        assert doc_ts({"external_modified_at": ext, "ingested_at": ing}) == ext

    def test_falls_back_to_ingested_at(self):
        ing = datetime(2026, 1, 3, tzinfo=timezone.utc)
        assert doc_ts({"ingested_at": ing}) == ing

    def test_non_datetime_ignored(self):
        assert doc_ts({"external_modified_at": "2026-01-01"}) is None
        assert doc_ts({"ingested_at": 5}) is None


class TestIsGenuinelyNewer:
    def test_no_timestamps_conservative_true(self):
        assert _is_genuinely_newer({}, None) is True
        assert _is_genuinely_newer({}, datetime(2026, 1, 1, tzinfo=timezone.utc)) is True
        older = {"ingested_at": datetime(2026, 1, 1, tzinfo=timezone.utc)}
        assert _is_genuinely_newer(older, None) is True

    def test_strictly_newer(self):
        older = {"ingested_at": datetime(2026, 1, 1, tzinfo=timezone.utc)}
        assert _is_genuinely_newer(older, datetime(2026, 1, 2, tzinfo=timezone.utc)) is True

    def test_equal_not_newer(self):
        ts = datetime(2026, 1, 1, tzinfo=timezone.utc)
        assert _is_genuinely_newer({"ingested_at": ts}, ts) is False

    def test_older_not_newer(self):
        older = {"ingested_at": datetime(2026, 1, 5, tzinfo=timezone.utc)}
        assert _is_genuinely_newer(older, datetime(2026, 1, 1, tzinfo=timezone.utc)) is False

    def test_naive_ts_coerced(self):
        older = {"ingested_at": datetime(2026, 1, 1)}
        assert _is_genuinely_newer(older, datetime(2026, 1, 2)) is True


# ===========================================================================
# Dataclasses
# ===========================================================================


class TestDataclasses:
    def test_candidate_defaults(self):
        c = SupersessionCandidate(doc_id="x", status="superseded", reason="r")
        assert (c.similarity, c.entity_overlap) == (0.0, 0.0)

    def test_summary_as_dict_full(self):
        s = ReevaluateSummary(
            checked=1, marked_fresh=2, marked_stale=3, marked_outdated=4,
            marked_removed=5, marked_superseded=6, edges_superseded=7,
            unchanged=8,
        )
        assert s.as_dict() == {
            "checked": 1, "fresh": 2, "stale": 3, "outdated": 4,
            "removed": 5, "superseded": 6, "edges_superseded": 7,
            "unchanged": 8,
        }

    def test_summary_defaults(self):
        s = ReevaluateSummary()
        assert s.as_dict()["checked"] == 0


# ===========================================================================
# detect_supersession
# ===========================================================================


class TestDetectSupersession:
    NEWER_ID = "doc-new"
    NEWER_TS = datetime(2026, 6, 1, tzinfo=timezone.utc)

    def _older(self, **kw) -> Dict[str, Any]:
        base = dict(
            doc_id="doc-old", text="old text",
            ingested_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
            external_modified_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
            freshness_status="fresh",
        )
        base.update(kw)
        return base

    def _detect(self, older_docs, **kw):
        defaults = dict(
            newer_doc_id=self.NEWER_ID, newer_text="new text",
            newer_embedding=[1.0, 0.0], newer_entities={"acme"},
            newer_ts=self.NEWER_TS, older_docs=older_docs,
        )
        defaults.update(kw)
        return detect_supersession(**defaults)

    def test_empty_newer_id(self):
        assert self._detect([self._older()], newer_doc_id="") == []

    def test_self_and_missing_ids_skipped(self):
        out = self._detect([self._older(doc_id=self.NEWER_ID), self._older(doc_id="")])
        assert out == []

    @pytest.mark.parametrize("status", ["removed", "superseded"])
    def test_terminal_docs_skipped(self, status):
        assert self._detect([self._older(freshness_status=status)]) == []

    def test_similarity_candidate_with_reason(self):
        emb = [1.0, 0.0]
        out = self._detect(
            [self._older()], older_embeddings={"doc-old": emb}, sim_threshold=0.86,
            entity_overlap_threshold=0.99,
        )
        assert len(out) == 1
        assert out[0].doc_id == "doc-old"
        assert out[0].status == "superseded"
        assert "superseded by doc-new" in out[0].reason
        assert "sim=" in out[0].reason and "entity_overlap=" not in out[0].reason
        assert out[0].similarity == pytest.approx(1.0)

    def test_entity_overlap_candidate(self):
        out = self._detect(
            [self._older()],
            newer_embedding=None,  # no embedding signal at all
            older_entity_sets={"doc-old": {"acme", "invoice"}},
            entity_overlap_threshold=0.5, sim_threshold=0.99,
        )
        assert len(out) == 1
        assert "entity_overlap=" in out[0].reason
        assert out[0].entity_overlap == pytest.approx(0.5)

    def test_both_signals_in_reason(self):
        emb = [1.0, 0.0]
        out = self._detect(
            [self._older()],
            older_embeddings={"doc-old": emb},
            older_entity_sets={"doc-old": {"acme"}},
            sim_threshold=0.86, entity_overlap_threshold=0.5,
        )
        assert "sim=" in out[0].reason and "entity_overlap=" in out[0].reason

    def test_embed_fn_lazy(self):
        calls = []

        def embed(text):
            calls.append(text)
            return [1.0, 0.0]

        out = self._detect(
            [self._older(text="custom")], newer_embedding=[1.0, 0.0],
            newer_entities=set(), embed_fn=embed,
        )
        assert calls == ["custom"]
        assert len(out) == 1

    def test_embed_fn_returns_none(self):
        out = self._detect(
            [self._older()], newer_embedding=[1.0, 0.0], newer_entities=set(),
            embed_fn=lambda t: None, entity_overlap_threshold=0.99,
        )
        assert out == []

    def test_embed_fn_raises(self):
        def embed(text):
            raise RuntimeError("boom")

        out = self._detect(
            [self._older()], newer_embedding=[1.0, 0.0], newer_entities=set(),
            embed_fn=embed, entity_overlap_threshold=0.99,
        )
        assert out == []

    def test_no_newer_embedding_and_no_overlap(self):
        out = self._detect(
            [self._older()], newer_embedding=None, newer_entities=set(),
            older_embeddings={"doc-old": [1.0, 0.0]},
        )
        assert out == []

    def test_below_thresholds(self):
        out = self._detect(
            [self._older()], newer_embedding=[1.0, 0.0], newer_entities={"x"},
            older_embeddings={"doc-old": [0.0, 1.0]},
            older_entity_sets={"doc-old": {"y"}},
        )
        assert out == []

    def test_not_genuinely_newer_skipped(self):
        newer = self._older(  # candidate, but NEWER than the newer doc
            ingested_at=datetime(2026, 12, 1, tzinfo=timezone.utc),
            external_modified_at=datetime(2026, 12, 1, tzinfo=timezone.utc),
        )
        out = self._detect([newer], older_embeddings={"doc-old": [1.0, 0.0]})
        assert out == []

    def test_multiple_candidates(self):
        emb = [1.0, 0.0]
        out = self._detect(
            [self._older(doc_id="a"), self._older(doc_id="b")],
            older_embeddings={"a": emb, "b": emb},
        )
        assert [c.doc_id for c in out] == ["a", "b"]


# ===========================================================================
# DocFreshnessService
# ===========================================================================


class TestMarkOnIngest:
    def test_sets_fields_and_commits(self):
        sess = FakeSession()
        svc = DocFreshnessService(sess, workspace_id="ws-1")
        doc = _doc()
        svc.mark_on_ingest(
            doc, source_url="http://x", content_hash="h",
            source_modified_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        )
        assert doc.source_url == "http://x"
        assert doc.source_content_hash == "h"
        assert doc.freshness_status == "fresh"
        assert doc.superseded_by is None
        assert doc.last_verified_at is not None
        assert sess.committed == 1

    def test_commit_failure_rolls_back(self):
        sess = FakeSession()
        sess._commit_raises = True
        svc = DocFreshnessService(sess)
        svc.mark_on_ingest(_doc(), source_url=None, content_hash="h",
                           source_modified_at=None)
        assert sess.rolled_back == 1


class TestMarkStale:
    def test_fresh_becomes_stale(self):
        sess = FakeSession()
        doc = _doc(freshness_status="fresh")
        DocFreshnessService(sess).mark_stale(doc)
        assert doc.freshness_status == "stale"
        assert sess.committed == 1

    @pytest.mark.parametrize("status", ["removed", "superseded"])
    def test_terminal_docs_not_resurrected(self, status):
        sess = FakeSession()
        doc = _doc(freshness_status=status, superseded_by="new")
        DocFreshnessService(sess).mark_stale(doc)
        assert doc.freshness_status == status
        assert sess.committed == 0

    def test_commit_failure_rolls_back(self):
        sess = FakeSession()
        sess._commit_raises = True
        doc = _doc(freshness_status="fresh")
        DocFreshnessService(sess).mark_stale(doc)
        assert doc.freshness_status == "stale"  # in-memory mutation survives
        assert sess.rolled_back == 1


class TestMarkSuperseded:
    def test_marks_and_links(self):
        sess = FakeSession()
        doc = _doc(id="old", workspace_id="ws-1")
        sess.tables[dfs.IngestedDocument] = [doc]
        out = DocFreshnessService(sess, workspace_id="ws-1").mark_superseded("old", "new", "r")
        assert out is doc
        assert doc.freshness_status == "superseded"
        assert doc.superseded_by == "new"
        assert sess.committed == 1

    def test_missing_returns_none(self):
        sess = FakeSession()
        sess.tables[dfs.IngestedDocument] = []
        assert DocFreshnessService(sess).mark_superseded("nope", "new", "r") is None

    def test_commit_failure_rolls_back(self):
        sess = FakeSession()
        doc = _doc(id="old")
        sess.tables[dfs.IngestedDocument] = [doc]
        sess._commit_raises = True
        out = DocFreshnessService(sess).mark_superseded("old", "new", "r")
        assert out is doc
        assert sess.rolled_back == 1


class TestReevaluateWorkspace:
    NOW = datetime(2026, 8, 12, 12, 0, 0, tzinfo=timezone.utc)

    def _svc(self, docs, commit_raises=False):
        sess = FakeSession()
        sess.tables[dfs.IngestedDocument] = docs
        sess._commit_raises = commit_raises
        return DocFreshnessService(sess), sess

    def test_empty_workspace(self):
        svc, _ = self._svc([])
        s = svc.reevaluate_workspace("ws-1", seen_external_ids=set(), now=self.NOW)
        assert s.checked == 0

    def test_marked_removed(self):
        doc = _doc(external_id="gone", freshness_status="fresh",
                   last_verified_at=self.NOW - timedelta(hours=1))
        svc, sess = self._svc([doc])
        s = svc.reevaluate_workspace("ws-1", seen_external_ids={"other"}, now=self.NOW)
        assert doc.freshness_status == "removed"
        assert s.marked_removed == 1
        assert sess.committed == 1

    def test_already_removed_unchanged(self):
        doc = _doc(external_id="gone", freshness_status="removed")
        svc, _ = self._svc([doc])
        s = svc.reevaluate_workspace("ws-1", seen_external_ids={"other"}, now=self.NOW)
        assert s.unchanged == 1
        assert s.marked_removed == 0

    def test_removed_wins_over_superseded(self):
        # external_id absent from listing beats the terminal-doc guard
        doc = _doc(external_id="gone", freshness_status="superseded")
        svc, _ = self._svc([doc])
        s = svc.reevaluate_workspace("ws-1", seen_external_ids={"other"}, now=self.NOW)
        assert doc.freshness_status == "removed"
        assert s.marked_removed == 1

    def test_superseded_left_alone_when_seen(self):
        doc = _doc(external_id="x", freshness_status="superseded", last_verified_at=None)
        svc, _ = self._svc([doc])
        s = svc.reevaluate_workspace("ws-1", seen_external_ids={"x"}, now=self.NOW)
        assert doc.freshness_status == "superseded"
        assert s.unchanged == 1

    def test_aging_to_outdated(self):
        doc = _doc(external_id="x", freshness_status="fresh",
                   last_verified_at=self.NOW - timedelta(hours=100))
        svc, _ = self._svc([doc])
        s = svc.reevaluate_workspace("ws-1", seen_external_ids={"x"}, now=self.NOW)
        assert doc.freshness_status == "outdated"
        assert s.marked_outdated == 1
        assert doc.last_verified_at == self.NOW

    def test_source_drift_to_stale(self):
        doc = _doc(external_id="x", freshness_status="fresh",
                   last_verified_at=self.NOW - timedelta(hours=1),
                   external_modified_at=self.NOW,
                   source_modified_at=self.NOW - timedelta(hours=2))
        svc, _ = self._svc([doc])
        s = svc.reevaluate_workspace("ws-1", seen_external_ids={"x"}, now=self.NOW)
        assert doc.freshness_status == "stale"
        assert s.marked_stale == 1

    def test_stale_recovers_to_fresh(self):
        t = self.NOW - timedelta(hours=2)
        doc = _doc(external_id="x", freshness_status="stale",
                   last_verified_at=self.NOW - timedelta(hours=1),
                   external_modified_at=t, source_modified_at=t)
        svc, _ = self._svc([doc])
        s = svc.reevaluate_workspace("ws-1", seen_external_ids={"x"}, now=self.NOW)
        assert doc.freshness_status == "fresh"
        assert s.marked_fresh == 1
        assert doc.last_verified_at == self.NOW

    def test_still_fresh_unchanged(self):
        doc = _doc(external_id="x", freshness_status="fresh",
                   last_verified_at=self.NOW - timedelta(hours=1))
        svc, _ = self._svc([doc])
        s = svc.reevaluate_workspace("ws-1", seen_external_ids={"x"}, now=self.NOW)
        assert doc.freshness_status == "fresh"
        assert s.unchanged == 1

    def test_no_external_id_skips_removal_detection(self):
        doc = _doc(external_id=None, freshness_status="fresh",
                   last_verified_at=self.NOW - timedelta(hours=1))
        svc, _ = self._svc([doc])
        s = svc.reevaluate_workspace("ws-1", seen_external_ids={"other"}, now=self.NOW)
        assert doc.freshness_status == "fresh"
        assert s.unchanged == 1

    def test_commit_failure_rolls_back(self):
        doc = _doc(external_id="x", freshness_status="fresh",
                   last_verified_at=self.NOW - timedelta(hours=100))
        svc, sess = self._svc([doc], commit_raises=True)
        svc.reevaluate_workspace("ws-1", seen_external_ids={"x"}, now=self.NOW)
        assert sess.rolled_back == 1


class TestApplySupersession:
    def _svc_with_doc(self):
        sess = FakeSession()
        doc = _doc(id="old", workspace_id="ws-1")
        sess.tables[dfs.IngestedDocument] = [doc]
        return DocFreshnessService(sess, workspace_id="ws-1"), doc

    def test_applies_and_counts(self):
        svc, doc = self._svc_with_doc()
        s = svc.apply_supersession(
            [SupersessionCandidate(doc_id="old", status="superseded", reason="r")],
            newer_doc_id="new",
        )
        assert s.marked_superseded == 1
        assert doc.freshness_status == "superseded"

    def test_missing_doc_skipped(self):
        sess = FakeSession()
        sess.tables[dfs.IngestedDocument] = []
        svc = DocFreshnessService(sess, workspace_id="ws-1")
        s = svc.apply_supersession(
            [SupersessionCandidate(doc_id="nope", status="superseded", reason="r")],
            newer_doc_id="new",
        )
        assert s.marked_superseded == 0

    def test_cascade_invoked(self):
        svc, _ = self._svc_with_doc()
        s = svc.apply_supersession(
            [SupersessionCandidate(doc_id="old", status="superseded", reason="r")],
            newer_doc_id="new", cascade_to_graph=lambda src, by: 7,
        )
        assert s.edges_superseded == 7

    def test_cascade_exception_swallowed(self):
        svc, _ = self._svc_with_doc()

        def boom(src, by):
            raise RuntimeError("graph down")

        s = svc.apply_supersession(
            [SupersessionCandidate(doc_id="old", status="superseded", reason="r")],
            newer_doc_id="new", cascade_to_graph=boom,
        )
        assert s.marked_superseded == 1
        assert s.edges_superseded == 0


class TestCascadeGraphSupersession:
    def test_no_workspace_returns_zero(self):
        assert DocFreshnessService(FakeSession()).cascade_graph_supersession("o", "n") == 0

    def test_stamps_matching_rows(self):
        from core import models as models_mod
        sess = FakeSession()
        node = MagicMock(id="n1", workspace_id="ws-1", properties={"doc_id": "old"})
        node_other = MagicMock(id="n2", workspace_id="ws-1", properties={"doc_id": "x"})
        edge = MagicMock(id="e1", workspace_id="ws-1", properties={"doc_id": "old"})
        sess.tables[models_mod.GraphNode] = [node, node_other]
        sess.tables[models_mod.GraphEdge] = [edge]
        svc = DocFreshnessService(sess, workspace_id="ws-1")
        assert svc.cascade_graph_supersession("old", "new") == 2
        assert node.properties["superseded_by"] == "new"
        assert edge.properties["superseded_by"] == "new"
        assert "superseded_by" not in node_other.properties
        assert sess.committed == 1

    def test_none_properties_tolerated(self):
        from core import models as models_mod
        sess = FakeSession()
        node = MagicMock(id="n1", workspace_id="ws-1", properties=None)
        sess.tables[models_mod.GraphNode] = [node]
        sess.tables[models_mod.GraphEdge] = []
        svc = DocFreshnessService(sess, workspace_id="ws-1")
        assert svc.cascade_graph_supersession("old", "new") == 0

    def test_commit_failure_rolls_back(self):
        from core import models as models_mod
        sess = FakeSession()
        node = MagicMock(id="n1", workspace_id="ws-1", properties={"doc_id": "old"})
        sess.tables[models_mod.GraphNode] = [node]
        sess.tables[models_mod.GraphEdge] = []
        sess._commit_raises = True
        svc = DocFreshnessService(sess, workspace_id="ws-1")
        assert svc.cascade_graph_supersession("old", "new") == 1
        assert sess.rolled_back == 1


class TestEntitySetForDoc:
    def test_no_workspace_empty(self):
        assert DocFreshnessService(FakeSession()).entity_set_for_doc("x") == set()

    def test_matching_names_collected(self):
        from core import models as models_mod
        sess = FakeSession()
        n1 = MagicMock()
        n1.name = "Acme"
        n1.properties = {"doc_id": "x"}
        n2 = MagicMock()
        n2.name = "Beta"
        n2.properties = {"doc_id": "other"}
        n3 = MagicMock()
        n3.name = None
        n3.properties = {"doc_id": "x"}
        sess.tables[models_mod.GraphNode] = [n1, n2, n3]
        svc = DocFreshnessService(sess, workspace_id="ws-1")
        assert svc.entity_set_for_doc("x") == {"Acme"}

    def test_exception_returns_empty(self):
        sess = FakeSession()
        sess.query = MagicMock(side_effect=RuntimeError("boom"))
        assert DocFreshnessService(sess, workspace_id="ws-1").entity_set_for_doc("x") == set()


class TestNonFreshDocIds:
    def test_returns_ids(self):
        sess = FakeSession()
        sess.tables[dfs.IngestedDocument] = [("d1",), ("d2",)]
        assert DocFreshnessService(sess).non_fresh_doc_ids("ws-1") == {"d1", "d2"}

    def test_empty(self):
        sess = FakeSession()
        sess.tables[dfs.IngestedDocument] = []
        assert DocFreshnessService(sess).non_fresh_doc_ids("ws-1") == set()


class TestGet:
    def test_with_workspace(self):
        sess = FakeSession()
        doc = _doc(id="x", workspace_id="ws-1")
        sess.tables[dfs.IngestedDocument] = [doc]
        assert DocFreshnessService(sess, workspace_id="ws-1")._get("x") is doc

    def test_without_workspace(self):
        sess = FakeSession()
        doc = _doc(id="x")
        sess.tables[dfs.IngestedDocument] = [doc]
        assert DocFreshnessService(sess)._get("x") is doc

    def test_missing(self):
        sess = FakeSession()
        sess.tables[dfs.IngestedDocument] = []
        assert DocFreshnessService(sess)._get("nope") is None


class TestExtraColumns:
    def test_with_datetime(self):
        dt = datetime(2026, 1, 1, tzinfo=timezone.utc)
        out = extra_columns_for_ingest(
            freshness_status="fresh", source_modified_at=dt, source_url="http://x",
        )
        assert out == {
            "freshness_status": "fresh",
            "source_modified_at": dt.isoformat(),
            "source_url": "http://x",
        }

    def test_with_none(self):
        out = extra_columns_for_ingest(
            freshness_status="stale", source_modified_at=None, source_url=None,
        )
        assert out["source_modified_at"] == ""
        assert out["source_url"] == ""
