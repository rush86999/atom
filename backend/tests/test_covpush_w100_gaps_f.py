# -*- coding: utf-8 -*-
"""Coverage wave 100 — verified gaps batch F.

Verified real gaps (all other wave-100 modules measured >=80% already):
1. core/federation/federation_security.py            (74% -> target 80+)
2. core/auto_dev/alpha_evolver_engine.py             (44% -> target 80+)

Plain pytest + unittest.mock, no network / no real LLM / no real sandbox.
"""
from __future__ import annotations

import asyncio
import sys
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace as NS
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest

# ---------------------------------------------------------------------------
# Federation security
# ---------------------------------------------------------------------------
from core.federation.federation_security import (
    AnomalyDetectionConfig,
    AnomalyDetector,
    AnomalyType,
    CredentialRotationConfig,
    CredentialRotationManager,
    CredentialStatus,
    FederationSecurityService,
    MutualTLSManager,
    get_federation_security,
)


def run(coro):
    return asyncio.get_event_loop().run_until_complete(coro) if False else asyncio.run(coro)


class TestMutualTLSManagerGap:
    def test_get_active_connections_filters_by_instance(self):
        mgr = MutualTLSManager()
        mgr.create_connection("inst-a", "10.0.0.1", "TLS_AES", "TLSv1.3")
        mgr.create_connection("inst-b", "10.0.0.2", "TLS_AES", "TLSv1.3")
        only_a = mgr.get_active_connections("inst-a")
        assert len(only_a) == 1 and only_a[0].source_instance == "inst-a"
        assert len(mgr.get_active_connections()) == 2

    def test_close_connection_hit_and_miss(self):
        mgr = MutualTLSManager()
        conn = mgr.create_connection("i", "ip", "c", "v")
        assert mgr.close_connection(conn.connection_id) is True
        assert conn.is_active is False
        assert mgr.close_connection("nope") is False

    def test_handshake_failures(self):
        mgr = MutualTLSManager()
        mgr.record_handshake_failure("1.2.3.4")
        mgr.record_handshake_failure("1.2.3.4")
        assert mgr.get_handshake_failures("1.2.3.4") == {"1.2.3.4": 2}
        assert mgr.get_handshake_failures() == {"1.2.3.4": 2}
        assert mgr.get_handshake_failures("9.9.9.9") == {"9.9.9.9": 0}

    def test_cleanup_stale_connections(self):
        mgr = MutualTLSManager()
        fresh = mgr.create_connection("i", "ip", "c", "v")
        stale = mgr.create_connection("i2", "ip2", "c", "v")
        stale.last_activity = datetime.now() - timedelta(seconds=7200)
        cleaned = mgr.cleanup_stale_connections(timeout_seconds=3600)
        assert cleaned == 1
        assert stale.is_active is False
        assert fresh.is_active is True
        assert mgr.cleanup_stale_connections(timeout_seconds=3600) == 0


class TestCredentialRotationManagerGap:
    def test_register_without_expiry_and_no_autorotate(self):
        mgr = CredentialRotationManager(CredentialRotationConfig(auto_rotate=False))
        rec = mgr.register_credential("c1", "federation_key", "i1")
        assert rec.expires_at is None
        assert rec.next_rotation is None
        assert mgr.check_rotation_needed("missing") is False

    def test_rotation_needed_compromised_and_schedule_and_expiry(self):
        mgr = CredentialRotationManager(CredentialRotationConfig(
            auto_rotate=False, warning_days=30))
        rec = mgr.register_credential("c1", "api_token", "i1", expiry_days=90)
        assert mgr.check_rotation_needed("c1") is False
        rec.status = CredentialStatus.COMPROMISED
        assert mgr.check_rotation_needed("c1") is True
        rec.status = CredentialStatus.ACTIVE
        rec.next_rotation = datetime.now() - timedelta(days=1)
        assert mgr.check_rotation_needed("c1") is True
        rec.next_rotation = None
        rec.expires_at = datetime.now() + timedelta(days=5)  # inside warning window
        assert mgr.check_rotation_needed("c1") is True

    def test_rotate_credential(self):
        mgr = CredentialRotationManager()
        mgr.register_credential("old", "certificate", "i1", expiry_days=90)
        new_rec = mgr.rotate_credential("old", "new")
        assert new_rec.rotation_count == 1
        assert new_rec.status == CredentialStatus.ACTIVE
        assert mgr._credentials["old"].status == CredentialStatus.ROTATING
        with pytest.raises(ValueError):
            mgr.rotate_credential("ghost", "x")

    def test_rotate_without_expiry_no_autorotate(self):
        mgr = CredentialRotationManager(CredentialRotationConfig(auto_rotate=False))
        mgr.register_credential("a", "api_token", "i")
        rec = mgr.rotate_credential("a", "b")
        assert rec.expires_at is None and rec.next_rotation is None

    def test_revoke_credential(self):
        mgr = CredentialRotationManager()
        mgr.register_credential("c", "api_token", "i")
        assert mgr.revoke_credential("c", reason="leak") is True
        assert mgr._credentials["c"].status == CredentialStatus.REVOKED
        assert mgr._credentials["c"].compromised_reason == "leak"
        assert mgr.revoke_credential("ghost") is False

    def test_due_for_rotation_and_statistics(self):
        mgr = CredentialRotationManager()
        mgr.register_credential("ok", "api_token", "i")
        bad = mgr.register_credential("due", "api_token", "i")
        bad.next_rotation = datetime.now() - timedelta(days=1)
        assert mgr.get_credentials_due_for_rotation() == ["due"]
        stats = mgr.get_statistics()
        assert stats["total_credentials"] == 2
        assert stats["due_for_rotation"] == 1
        assert stats["status_counts"]["active"] == 2


class TestAnomalyDetectorGap:
    def test_baseline_updates_after_min_samples(self):
        cfg = AnomalyDetectionConfig(min_samples_for_baseline=5)
        det = AnomalyDetector(cfg)
        for _ in range(5):
            det.record_traffic("src", "1.1.1.1", request_count=10, latency_ms=50)
        assert det._baseline_samples == 5
        assert det._baselines["request_count"] == pytest.approx(10.0)

    def test_anomaly_detection_paths(self):
        cfg = AnomalyDetectionConfig(
            min_samples_for_baseline=3,
            traffic_spike_multiplier=2.0,
            failed_auth_threshold=0.5,
            latency_spike_multiplier=1.5,
            max_request_size_mb=0.0005,  # ~524 bytes triggers LARGE_REQUEST
        )
        det = AnomalyDetector(cfg)
        for _ in range(3):
            det.record_traffic("src", "1.1.1.1", request_count=10,
                               failed_auth=1, latency_ms=10, bytes_sent=10, bytes_received=10)
        # Spike everything at once: traffic, failed auth, latency, bytes
        det.record_traffic("src", "1.1.1.1", request_count=100,
                           failed_auth=100, latency_ms=100,
                           bytes_sent=1024 * 1024, bytes_received=0)
        types = {a.anomaly_type for a in det._alerts}
        assert AnomalyType.TRAFFIC_SPIKE in types
        assert AnomalyType.FAILED_AUTH_RATE in types
        assert AnomalyType.LATENCY_SPIKE in types
        assert AnomalyType.LARGE_REQUEST in types

    def test_check_anomalies_disabled_analyses(self):
        cfg = AnomalyDetectionConfig(
            min_samples_for_baseline=2,
            enable_traffic_analysis=False,
            enable_rate_analysis=False,
            enable_latency_analysis=False,
            max_request_size_mb=10_000.0,
        )
        det = AnomalyDetector(cfg)
        for _ in range(2):
            det.record_traffic("s", "ip", request_count=5, latency_ms=5)
        det.record_traffic("s", "ip", request_count=500, failed_auth=50, latency_ms=500)
        assert det._alerts == []  # everything disabled / thresholds not met

    def test_create_alert_zero_baseline(self):
        det = AnomalyDetector()
        alert = det._create_alert(AnomalyType.RATE_EXCEEDED, "src", 5.0, 0.0, "high")
        assert alert.deviation == 0.0
        assert "Rate Exceeded" in alert.description

    def test_alert_resolution_and_query(self):
        det = AnomalyDetector()
        det._alerts.append(NS(alert_id="a1", is_resolved=False,
                              detected_at=datetime.now(), resolved_at=None))
        det._alerts.append(NS(alert_id="a2", is_resolved=False,
                              detected_at=datetime(2020, 1, 1), resolved_at=None))
        # old alert filtered out by `since`
        assert len(det.get_recent_alerts(since=datetime.now() - timedelta(hours=1))) == 1
        assert det.resolve_alert("a1") is True
        assert det.resolve_alert("a1") is False  # already resolved
        assert det.resolve_alert("zzz") is False
        stats = det.get_statistics()
        assert stats["total_alerts"] == 2

    def test_record_traffic_zero_requests(self):
        det = AnomalyDetector()
        m = det.record_traffic("s", "ip", request_count=0, failed_auth=0)
        assert m.error_rate == 0


class TestFederationSecurityServiceGap:
    def test_health_status_levels(self):
        svc = FederationSecurityService()
        assert svc.get_health_status()["status"] == "healthy"
        # degraded
        for i in range(11):
            svc.anomaly._alerts.append(NS(alert_id=str(i), is_resolved=False,
                                          detected_at=datetime.now(), resolved_at=None))
        assert svc.get_health_status()["status"] == "degraded"
        for i in range(100, 160):
            svc.anomaly._alerts.append(NS(alert_id=str(i), is_resolved=False,
                                          detected_at=datetime.now(), resolved_at=None))
        assert svc.get_health_status()["status"] == "unhealthy"

    def test_get_statistics(self):
        svc = FederationSecurityService()
        svc.tls.record_handshake_failure("1.1.1.1")
        svc.tls.record_handshake_failure("1.1.1.1")
        svc.tls.record_handshake_failure("2.2.2.2")
        stats = svc.get_statistics()
        assert stats["tls"]["handshake_failures"] == 3  # BUG-094: sum of counts
        assert "rotation" in stats and "anomaly" in stats

    def test_factory_singleton(self):
        import core.federation.federation_security as fs
        fs._federation_security_instance = None
        first = get_federation_security()
        second = get_federation_security()
        assert first is second
        fs._federation_security_instance = None  # restore


# ---------------------------------------------------------------------------
# AlphaEvolver engine
# ---------------------------------------------------------------------------
from core.auto_dev.alpha_evolver_engine import AlphaEvolverEngine


def make_db():
    """MagicMock DB session; add() records objects so query().first() can return them."""
    db = MagicMock()
    added = []

    def _add(obj):
        added.append(obj)

    def _first():
        return added[-1] if added else None

    db.add.side_effect = _add
    db.query.return_value.filter.return_value.first.side_effect = _first
    db.added = added
    return db


def make_engine(llm=None, sandbox=None):
    db = make_db()
    return AlphaEvolverEngine(db=db, llm_service=llm, sandbox=sandbox), db


def llm_returning(content, fail=False):
    llm = MagicMock()
    if fail:
        llm.generate_completion = AsyncMock(side_effect=RuntimeError("boom"))
    else:
        llm.generate_completion = AsyncMock(return_value={"content": content})
    return llm


class TestAnalyzeEpisodeGap:
    def test_episode_not_found(self):
        eng, db = make_engine()
        db.query.return_value.filter.return_value.first.side_effect = lambda: None
        result = run(eng.analyze_episode("ep-404"))
        assert result == {"error": "Episode ep-404 not found"}

    def test_episode_models_unavailable(self, monkeypatch):
        eng, _ = make_engine()
        monkeypatch.setitem(sys.modules, "core.models", NS())  # no AgentEpisode attr
        result = run(eng.analyze_episode("ep-1"))
        assert result["error"] == "Episode models not available"

    def test_optimization_targets_identified(self, monkeypatch):
        eng, db = make_engine()
        episode = NS(task_description="t", success=True, metadata_json={"a": 1})
        segs = [
            NS(id="s1", canvas_context={"execution_seconds": 9.0}),
            NS(id="s2", canvas_context={"retry_count": 2}),
            NS(id="s3", canvas_context={}),
            NS(id="s4", canvas_context=None),
        ]
        db.query.return_value.filter.return_value.first.side_effect = lambda: episode
        db.query.return_value.filter.return_value.all.side_effect = lambda: segs
        result = run(eng.analyze_episode("ep-1"))
        assert result["total_segments"] == 4
        reasons = {t["reason"] for t in result["optimization_targets"]}
        assert reasons == {"high_latency", "retries"}


class TestProposeCodeChangeGap:
    def test_llm_unavailable_returns_skip_marker(self):
        eng = AlphaEvolverEngine(db=MagicMock(), llm_service=None)
        with patch.object(eng, "_get_llm_service", return_value=None):
            out = run(eng.propose_code_change({"base_code": "x = 1"}))
        assert out.startswith("x = 1") and "Mutation skipped" in out

    def test_llm_failure_returns_failure_marker(self):
        eng, _ = make_engine(llm=llm_returning("", fail=True))
        out = run(eng.propose_code_change({"base_code": "x = 1"}))
        assert "Mutation failed: boom" in out

    def test_strips_fences(self):
        eng, _ = make_engine(llm=llm_returning("```python\ny = 2\n```"))
        out = run(eng.propose_code_change({"base_code": "x = 1"}))
        assert out.strip() == "y = 2"


class TestValidateChangeGap:
    def test_sandbox_unavailable(self):
        eng = AlphaEvolverEngine(db=MagicMock(), llm_service=None, sandbox=None)
        with patch.object(eng, "_get_sandbox", return_value=None):
            result = run(eng.validate_change("code", [{"x": 1}], "t1"))
        assert result == {"passed": False, "error": "Sandbox unavailable"}

    def _sandbox(self, statuses):
        sandbox = MagicMock()
        responses = [{"status": s, "output": "out", "execution_seconds": 1.0}
                     for s in statuses]
        sandbox.execute_raw_python = AsyncMock(side_effect=responses)
        return sandbox

    def test_failing_test_rejects_without_regression(self):
        sandbox = self._sandbox(["success", "failed"])
        eng, _ = make_engine(sandbox=sandbox)
        result = run(eng.validate_change("code", [{"a": 1}, {"a": 2}], "t1"))
        assert result["passed"] is False
        assert result["proxy_signals"]["pass_rate"] == 0.5
        assert result["proxy_signals"]["avg_execution_seconds"] == 1.0

    def test_pass_with_parent_regression_ok(self):
        sandbox = self._sandbox(["success", "success"])
        eng, _ = make_engine(sandbox=sandbox)
        validator = MagicMock()
        validator.validate_regression = AsyncMock(
            return_value=NS(passed=True, mismatches=[], total_tests=2,
                            to_dict=lambda: {"passed": True}))
        with patch("core.auto_dev.regression_validator.RegressionValidator",
                   return_value=validator):
            result = run(eng.validate_change("code2", [{"a": 1}], "t1", parent_code="code1"))
        assert result["passed"] is True

    def test_regression_failure_rejects(self):
        sandbox = self._sandbox(["success"])
        eng, _ = make_engine(sandbox=sandbox)
        validator = MagicMock()
        validator.validate_regression = AsyncMock(
            return_value=NS(passed=False, mismatches=[1], total_tests=2,
                            to_dict=lambda: {"passed": False}))
        with patch("core.auto_dev.regression_validator.RegressionValidator",
                   return_value=validator):
            result = run(eng.validate_change("code2", [{"a": 1}], "t1", parent_code="code1"))
        assert result["passed"] is False
        assert result["regression_result"]["passed"] is False

    def test_regression_import_error_is_tolerated(self):
        sandbox = self._sandbox(["success"])
        eng, _ = make_engine(sandbox=sandbox)
        with patch("core.auto_dev.regression_validator.RegressionValidator",
                   side_effect=ImportError("nope")):
            result = run(eng.validate_change("code2", [{"a": 1}], "t1", parent_code="code1"))
        assert result["passed"] is True  # validator unavailable → continue

    def test_compute_proxy_signals_empty(self):
        assert AlphaEvolverEngine._compute_proxy_signals([]) == {
            "execution_success": True, "pass_rate": 0,
            "avg_execution_seconds": 0, "syntax_error": False,
        }


class TestSandboxExecuteMutationGap:
    def test_mutation_not_found(self):
        eng, db = make_engine()
        db.query.return_value.filter.return_value.first.side_effect = lambda: None
        result = run(eng.sandbox_execute_mutation("m1", "t1", {}))
        assert "not found" in result["error"]

    def test_sandbox_unavailable(self):
        eng = AlphaEvolverEngine(db=MagicMock(), sandbox=None)
        with patch.object(eng, "_get_sandbox", return_value=None):
            result = run(eng.sandbox_execute_mutation("m1", "t1", {}))
        assert result == {"error": "Sandbox unavailable"}

    def test_failed_execution_records_syntax_error_signal(self):
        sandbox = MagicMock()
        sandbox.execute_raw_python = AsyncMock(return_value={
            "status": "failed", "output": "SyntaxError: invalid syntax",
            "execution_seconds": 0.5, "environment": "docker",
        })
        eng, db = make_engine(sandbox=sandbox)
        mutation = NS(tenant_id="t1", mutated_code="bad(", sandbox_status="pending",
                      execution_error=None)
        db.query.return_value.filter.return_value.first.side_effect = lambda: mutation
        result = run(eng.sandbox_execute_mutation("m1", "t1", {}))
        db.commit.assert_called()
        assert result["success"] is False
        assert result["proxy_signals"]["syntax_error"] is True
        assert result["proxy_signals"]["execution_latency_ms"] == 500.0
        assert mutation.sandbox_status == "failed"
        assert "SyntaxError" in mutation.execution_error


class TestSynthesisAndResearchGap:
    def test_check_auto_synthesis_readiness(self):
        eng, db = make_engine()
        db.query.return_value.filter.return_value.count.return_value = 5
        assert eng.check_auto_synthesis_readiness("t1", "tool") is True
        db.query.return_value.filter.return_value.count.return_value = 4
        assert eng.check_auto_synthesis_readiness("t1", "tool") is False

    def test_run_research_experiment_promotes_and_skips(self):
        eng, db = make_engine()
        good = NS(id="m1", mutated_code="def f():\n    return 2\n")
        noop = NS(id="m2", mutated_code="# just a comment\n")
        mutations = [good, noop]
        exec_results = [
            {"success": True, "output": "2"},
            {"success": True, "output": ""},  # no useful output → not promoted
        ]
        with patch.object(eng, "generate_tool_mutation",
                          AsyncMock(side_effect=mutations)), \
             patch.object(eng, "sandbox_execute_mutation",
                          AsyncMock(side_effect=exec_results)):
            results = run(eng.run_research_experiment("t1", "base", "goal", iterations=2))
        assert len(results) == 2
        assert results[0]["success"] is True
        # noop mutation (only comments) must not be promoted — code stays at base
        assert results[1]["code_preview"].startswith("# just a comment")

    def test_run_research_experiment_failed_iteration(self):
        eng, _ = make_engine()
        mutation = NS(id="m1", mutated_code="x = 1")
        with patch.object(eng, "generate_tool_mutation",
                          AsyncMock(return_value=mutation)), \
             patch.object(eng, "sandbox_execute_mutation",
                          AsyncMock(return_value={"success": False, "output": None})):
            results = run(eng.run_research_experiment("t1", "base", "goal", iterations=1))
        assert results[0]["success"] is False


class TestArborExperimentGap:
    def test_arbor_success_and_test_failed_paths(self):
        eng, db = make_engine()
        codes = [
            "def f():\n    return 1\n",   # iteration 1: success
            "def f(:\n    return 2\n",    # iteration 2: syntax error → lint prune
            "def f():\n    return 3\n",   # iteration 3: sandbox failure → test prune
        ]
        llm = MagicMock()
        llm.generate_completion = AsyncMock(
            side_effect=[{"content": c} for c in codes])
        eng.llm = llm

        sandbox = MagicMock()
        sandbox.execute_raw_python = AsyncMock(side_effect=[
            {"status": "success", "output": "1", "execution_seconds": 0.1},
            {"status": "failed", "output": "err", "execution_seconds": 0.1},
        ])
        eng.sandbox = sandbox

        result = run(eng.run_arbor_experiment("t1", "x = 0", "goal", iterations=3))

        assert result["winning_node_id"] is not None
        iters = result["iterations"]
        assert len(iters) == 3
        assert iters[0]["success"] is True and iters[0]["pruned"] is False
        assert iters[1]["pruned"] is True and iters[1]["prune_reason"] == "lint_failed"
        assert iters[2]["pruned"] is True and iters[2]["prune_reason"] == "test_failed"
        assert result["tree"]["winning_path"]
        assert db.commit.called

    def test_arbor_budget_exhausted(self):
        eng, db = make_engine()
        llm = MagicMock()
        llm.generate_completion = AsyncMock(return_value={"content": "x = 1\n"})
        eng.llm = llm
        eng.sandbox = MagicMock()
        eng.sandbox.execute_raw_python = AsyncMock(return_value={
            "status": "success", "output": "1", "execution_seconds": 0.1})
        # 'free' tier has the smallest node budget
        result = run(eng.run_arbor_experiment("t1", "x = 0", "goal",
                                              iterations=10_000, tier="free"))
        assert len(result["iterations"]) <= 50
        assert result["iterations"][0]["success"] is True
