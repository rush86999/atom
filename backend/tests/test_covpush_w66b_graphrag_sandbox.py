"""
Coverage wave 66b — agent_graphrag_service, sandbox_transaction,
enterprise_endpoints, storage (TDD, standalone, zero LLM spend, no network,
no real DB).

Each module is driven to >=95% statement coverage by THIS file alone:

- AgentGraphRAGService: init, local/global context retrieval, fail-fast
  validation branches, entity-relationship validation (both node-missing and
  edge-missing errors, type-filtered query), hybrid context with/without a
  recalled POMDP trajectory and with memory-manager failure, context
  formatting (global, local with ids, fallback raw ids, empty relationships).
- SandboxTransaction: start on existing/non-existing targets, snapshot
  skipping of .sandbox_snapshots, context-manager commit/rollback, rollback
  on exception, rollback+re-raise on resource-cap breach, timeout and disk
  cap breaches, inactive guards on check_resource_limits/commit/rollback,
  cleanup of snapshot dirs, nested dir/file restore.
- enterprise_endpoints: every route on /api/enterprise incl. the compliance
  not-found 404 path.
- storage: lazy boto3 import (both branches), client construction with and
  without endpoint, env credential/bucket precedence, upload/download/
  check/delete/list happy + error paths, singleton service factory.

No real S3 or network access: boto3 client is always a Mock; the
ImportError branch is forced via sys.modules poisoning.
"""

import os
import sys
import shutil
import tempfile
import time
from io import BytesIO
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from core.agent_graphrag_service import AgentGraphRAGService
from core.enterprise_endpoints import enterprise_data, router
from core.sandbox_transaction import SandboxTransaction
from core.storage import _import_boto3, StorageService, get_storage_service


# ============================================================================
# Shared helpers
# ============================================================================


def _local_result():
    return {
        "mode": "local",
        "entities": [
            {"id": "e1", "name": "Alpha", "type": "org", "description": "d1"},
            {"id": "e2", "name": "Beta", "type": "person", "description": "d2"},
        ],
        "relationships": [
            {"from": "e1", "to": "e2", "type": "works_at", "description": "x"},
            {"from": "e2", "to": "e1", "type": "manages"},
        ],
    }


def _make_graphrag_service(engine=None):
    service = AgentGraphRAGService.__new__(AgentGraphRAGService)
    service.db = Mock()
    service.workspace_id = "ws-1"
    service.agent_id = "agent-1"
    service.graphrag = engine or Mock()
    return service


def _graph_db(nodes=(None, None), edge=None):
    """Mock session whose query() returns a node query then an edge query."""
    from core.models import GraphEdge, GraphNode

    db = Mock()
    node_query = Mock()
    node_query.filter.return_value = node_query
    node_query.first.side_effect = list(nodes)
    edge_query = Mock()
    edge_query.filter.return_value = edge_query
    edge_query.first.return_value = edge
    db.query = Mock(
        side_effect=lambda model: node_query if model is GraphNode else edge_query
    )
    return db


def _make_edge(**overrides):
    props = {
        "relationship_type": "works_at",
        "weight": 1.5,
        "properties": {"description": "desc"},
    }
    props.update(overrides)
    return Mock(**props)


def _workspace(tmp_path):
    ws = tmp_path / "workspace"
    ws.mkdir()
    (ws / "file1.txt").write_text("hello")
    (ws / "dir1").mkdir()
    (ws / "dir1" / "file2.txt").write_text("world")
    return ws


@pytest.fixture
def enterprise_client():
    app = FastAPI()
    app.include_router(router)
    with TestClient(app) as c:
        yield c


@pytest.fixture(autouse=True)
def _clear_storage_singleton():
    StorageService._instance = None
    yield
    StorageService._instance = None


# ============================================================================
# AgentGraphRAGService
# ============================================================================


class TestAgentGraphRAGInit:
    def test_init_creates_engine(self):
        with patch("core.agent_graphrag_service.GraphRAGEngine") as engine_cls:
            service = AgentGraphRAGService(Mock(), "ws-1", "agent-1")
        assert service.db is not None
        assert service.workspace_id == "ws-1"
        assert service.agent_id == "agent-1"
        engine_cls.assert_called_once()


class TestGetAgentContext:
    async def test_local_mode_truncates_entities_and_relationships(self):
        service = _make_graphrag_service()
        service.graphrag.query = AsyncMock(return_value=_local_result())
        result = await service.get_agent_context(
            "who is alpha", max_entities=1, max_relationships=1
        )
        assert result["agent_id"] == "agent-1"
        assert result["has_results"] is True
        assert len(result["entities"]) == 1
        assert len(result["relationships"]) == 1
        assert "Found 1 relevant entities" in result["context"]

    async def test_local_mode_empty_raises_value_error(self):
        service = _make_graphrag_service()
        service.graphrag.query = AsyncMock(
            return_value={"mode": "local", "entities": [], "relationships": []}
        )
        with pytest.raises(ValueError, match="No entities found"):
            await service.get_agent_context("query")

    async def test_local_mode_only_relationships_is_valid(self):
        service = _make_graphrag_service()
        service.graphrag.query = AsyncMock(
            return_value={"mode": "local", "entities": [], "relationships": [{"from": "a", "to": "b"}]}
        )
        result = await service.get_agent_context("query")
        assert result["has_results"] is True

    async def test_global_mode_uses_answer(self):
        service = _make_graphrag_service()
        service.graphrag.query = AsyncMock(
            return_value={"mode": "global", "answer": "Community summary"}
        )
        result = await service.get_agent_context("overview", mode="global")
        assert result["context"] == "Global Context: Community summary"
        assert result["has_results"] is True

    async def test_global_mode_empty_answer_raises(self):
        service = _make_graphrag_service()
        service.graphrag.query = AsyncMock(
            return_value={"mode": "global", "answer": "   "}
        )
        with pytest.raises(ValueError, match="global search failed"):
            await service.get_agent_context("overview", mode="global")

    async def test_query_passes_workspace_and_mode(self):
        service = _make_graphrag_service()
        service.graphrag.query = AsyncMock(return_value=_local_result())
        await service.get_agent_context("q", mode="auto")
        service.graphrag.query.assert_awaited_once_with(
            workspace_id="ws-1", query="q", mode="auto"
        )

    def test_format_context_local_includes_entities_and_rels(self):
        service = _make_graphrag_service()
        ctx = service._format_context(_local_result())
        assert "Found 2 relevant entities" in ctx
        assert "- Alpha (org): d1" in ctx
        assert "Alpha -> Beta (works_at)" in ctx

    def test_format_context_global(self):
        service = _make_graphrag_service()
        assert service._format_context({"mode": "global", "answer": "summary"}) == (
            "Global Context: summary"
        )

    def test_format_context_falls_back_to_raw_ids(self):
        service = _make_graphrag_service()
        result = _local_result()
        result["relationships"] = [{"from": "unknown-id", "to": "e2", "type": "t"}]
        ctx = service._format_context(result)
        assert "unknown-id -> Beta (t)" in ctx

    def test_format_context_relationship_without_type(self):
        service = _make_graphrag_service()
        result = _local_result()
        result["relationships"] = [{"from": "e1", "to": "e2"}]
        ctx = service._format_context(result)
        assert "Alpha -> Beta (related)" in ctx

    def test_format_context_empty_relationships(self):
        service = _make_graphrag_service()
        result = _local_result()
        result["relationships"] = []
        ctx = service._format_context(result)
        assert "0 relationships" in ctx


class TestValidateEntityRelationship:
    async def test_relationship_found_returns_metadata(self):
        service = _make_graphrag_service()
        service.db = _graph_db(
            nodes=(Mock(id="n1"), Mock(id="n2")), edge=_make_edge()
        )
        result = await service.validate_entity_relationship("Alpha", "Beta")
        assert result == {
            "exists": True,
            "relationship_type": "works_at",
            "description": "desc",
            "weight": 1.5,
            "metadata": {"description": "desc"},
        }

    async def test_relationship_type_filter_applied(self):
        from core.models import GraphEdge, GraphNode

        service = _make_graphrag_service()
        edge = _make_edge(properties={})
        node_a, node_b = Mock(id="n1"), Mock(id="n2")
        node_query = Mock()
        node_query.filter.return_value = node_query
        node_query.first.side_effect = [node_a, node_b]
        edge_query = Mock()
        edge_query.filter.return_value = edge_query
        edge_query.first.return_value = edge
        db = Mock()
        db.query = Mock(
            side_effect=lambda model: node_query if model is GraphNode else edge_query
        )
        service.db = db
        await service.validate_entity_relationship("Alpha", "Beta", "works_at")
        assert edge_query.filter.call_count == 2

    async def test_relationship_without_description_uses_default(self):
        service = _make_graphrag_service()
        edge = _make_edge(properties={})
        service.db = _graph_db(nodes=(Mock(id="n1"), Mock(id="n2")), edge=edge)
        result = await service.validate_entity_relationship("Alpha", "Beta")
        assert result["description"] == "Alpha -> Beta"

    async def test_missing_node_a_raises(self):
        service = _make_graphrag_service()
        service.db = _graph_db(nodes=(None, Mock(id="n2")), edge=None)
        with pytest.raises(ValueError, match="Entities not found"):
            await service.validate_entity_relationship("Alpha", "Beta")

    async def test_missing_node_b_raises(self):
        service = _make_graphrag_service()
        service.db = _graph_db(nodes=(Mock(id="n1"), None), edge=None)
        with pytest.raises(ValueError, match="Entities not found"):
            await service.validate_entity_relationship("Alpha", "Beta")

    async def test_missing_edge_raises(self):
        service = _make_graphrag_service()
        service.db = _graph_db(nodes=(Mock(id="n1"), Mock(id="n2")), edge=None)
        with pytest.raises(ValueError, match="No relationship found"):
            await service.validate_entity_relationship("Alpha", "Beta")


class TestGetHybridContext:
    async def test_with_recalled_trajectory_merges_episodic_context(self):
        service = _make_graphrag_service()
        service.graphrag.query = AsyncMock(
            return_value={"mode": "global", "answer": "ans"}
        )
        manager = Mock()
        manager.recall_hypothesis_trajectory = Mock(
            return_value={
                "winning_trajectory": [{"step": 1}],
                "pruned_failure_branches": [{"branch": 2}],
            }
        )
        with patch(
            "core.memory.pomdp_memory_framework.get_memory_manager",
            return_value=manager,
        ):
            result = await service.get_hybrid_context("query")
        assert "Recalled Experiential Context" in result["context"]
        assert '{"step": 1}' in result["context"]
        assert result["recalled_trajectory"] is not None

    async def test_without_trajectory_keeps_context(self):
        service = _make_graphrag_service()
        service.graphrag.query = AsyncMock(
            return_value={"mode": "global", "answer": "ans"}
        )
        manager = Mock()
        manager.recall_hypothesis_trajectory = Mock(return_value=None)
        with patch(
            "core.memory.pomdp_memory_framework.get_memory_manager",
            return_value=manager,
        ):
            result = await service.get_hybrid_context("query")
        assert result["recalled_trajectory"] is None
        assert "Recalled Experiential Context" not in result["context"]

    async def test_memory_manager_failure_is_swallowed(self):
        service = _make_graphrag_service()
        service.graphrag.query = AsyncMock(
            return_value={"mode": "global", "answer": "ans"}
        )
        with patch(
            "core.memory.pomdp_memory_framework.get_memory_manager",
            side_effect=RuntimeError("mem down"),
        ):
            result = await service.get_hybrid_context("query")
        assert result["recalled_trajectory"] is None
        assert "ans" in result["context"]

    async def test_forwards_mode_and_limits(self):
        service = _make_graphrag_service()
        service.graphrag.query = AsyncMock(return_value=_local_result())
        await service.get_hybrid_context("q", "local", 3, 5)
        service.graphrag.query.assert_awaited_once_with(
            workspace_id="ws-1", query="q", mode="local"
        )


# ============================================================================
# SandboxTransaction
# ============================================================================


class TestSandboxTransactionStart:
    def test_start_creates_missing_target_dir(self, tmp_path):
        target = tmp_path / "brand_new"
        tx = SandboxTransaction(target)
        tx.start()
        assert target.exists()
        assert tx.snapshot_dir is not None and tx.snapshot_dir.exists()
        assert tx.start_time is not None
        tx._cleanup_snapshot()

    def test_start_snapshots_files_and_dirs(self, tmp_path):
        ws = _workspace(tmp_path)
        tx = SandboxTransaction(ws)
        tx.start()
        assert (tx.snapshot_dir / "file1.txt").exists()
        assert (tx.snapshot_dir / "dir1" / "file2.txt").exists()
        tx._cleanup_snapshot()

    def test_start_skips_snapshot_dir_inside_target(self, tmp_path):
        ws = _workspace(tmp_path)
        (ws / ".sandbox_snapshots").mkdir()
        (ws / ".sandbox_snapshots" / "junk.bin").write_bytes(b"junk")
        tx = SandboxTransaction(ws)
        tx.start()
        assert not (tx.snapshot_dir / ".sandbox_snapshots").exists()
        tx._cleanup_snapshot()

    def test_start_marks_active(self, tmp_path):
        tx = SandboxTransaction(_workspace(tmp_path))
        assert tx._active is False
        tx.start()
        assert tx._active is True
        tx._cleanup_snapshot()

    def test_enter_returns_self_and_starts(self, tmp_path):
        ws = _workspace(tmp_path)
        tx = SandboxTransaction(ws)
        entered = tx.__enter__()
        assert entered is tx
        assert tx._active is True
        tx.__exit__(None, None, None)


class TestSandboxTransactionCommit:
    def test_commit_discards_snapshot_and_keeps_changes(self, tmp_path):
        ws = _workspace(tmp_path)
        with SandboxTransaction(ws) as tx:
            (ws / "file1.txt").write_text("modified")
            (ws / "new_file.txt").write_text("added")
            shutil.rmtree(ws / "dir1")
        assert (ws / "file1.txt").read_text() == "modified"
        assert (ws / "new_file.txt").read_text() == "added"
        assert not (ws / "dir1").exists()
        assert tx.snapshot_dir is None
        assert tx._active is False

    def test_commit_when_not_active_is_noop(self, tmp_path):
        ws = _workspace(tmp_path)
        tx = SandboxTransaction(ws)
        tx.commit()
        assert tx.snapshot_dir is None
        assert tx._active is False

    def test_exit_without_exception_commits(self, tmp_path):
        ws = _workspace(tmp_path)
        tx = SandboxTransaction(ws)
        tx.__enter__()
        (ws / "file1.txt").write_text("v2")
        assert tx.__exit__(None, None, None) is None
        assert (ws / "file1.txt").read_text() == "v2"


class TestSandboxTransactionRollback:
    def test_exit_with_exception_rolls_back(self, tmp_path):
        ws = _workspace(tmp_path)
        try:
            with SandboxTransaction(ws) as tx:
                (ws / "file1.txt").write_text("modified")
                (ws / "new_file.txt").write_text("added")
                raise ValueError("abort")
        except ValueError:
            pass
        assert (ws / "file1.txt").read_text() == "hello"
        assert not (ws / "new_file.txt").exists()
        assert (ws / "dir1" / "file2.txt").read_text() == "world"
        assert tx._active is False
        assert tx.snapshot_dir is None

    def test_rollback_restores_deleted_subdir(self, tmp_path):
        ws = _workspace(tmp_path)
        tx = SandboxTransaction(ws)
        tx.start()
        shutil.rmtree(ws / "dir1")
        tx.rollback()
        assert (ws / "dir1" / "file2.txt").read_text() == "world"

    def test_rollback_when_not_active_is_noop(self, tmp_path):
        tx = SandboxTransaction(_workspace(tmp_path))
        tx.rollback()
        assert tx._active is False

    def test_rollback_when_snapshot_missing_is_noop(self, tmp_path):
        ws = _workspace(tmp_path)
        tx = SandboxTransaction(ws)
        tx.start()
        tx._active = False
        tx.rollback()
        assert (ws / "file1.txt").exists()

    def test_rollback_skips_sandbox_snapshots_dir(self, tmp_path):
        ws = _workspace(tmp_path)
        tx = SandboxTransaction(ws)
        tx.start()
        (ws / ".sandbox_snapshots").mkdir()
        (ws / ".sandbox_snapshots" / "keep.bin").write_bytes(b"keep")
        tx.rollback()
        assert (ws / ".sandbox_snapshots" / "keep.bin").exists()
        assert (ws / "file1.txt").read_text() == "hello"

    def test_rollback_after_target_fully_cleared(self, tmp_path):
        ws = _workspace(tmp_path)
        tx = SandboxTransaction(ws)
        tx.start()
        for item in list(ws.iterdir()):
            if item.is_dir():
                shutil.rmtree(item)
            else:
                item.unlink()
        tx.rollback()
        assert (ws / "file1.txt").read_text() == "hello"
        assert (ws / "dir1" / "file2.txt").read_text() == "world"


class TestSandboxTransactionResourceLimits:
    def test_check_limits_when_not_active_returns(self, tmp_path):
        tx = SandboxTransaction(_workspace(tmp_path))
        tx.check_resource_limits()

    def test_timeout_without_start_time_skips(self, tmp_path):
        tx = SandboxTransaction(_workspace(tmp_path), timeout_seconds=1.0)
        tx._active = True
        tx.check_resource_limits()

    def test_timeout_breach_raises(self, tmp_path):
        tx = SandboxTransaction(_workspace(tmp_path), timeout_seconds=1.0)
        tx._active = True
        tx.start_time = time.time() - 5
        with pytest.raises(TimeoutError, match="timed out"):
            tx.check_resource_limits()

    def test_no_timeout_limit_skips(self, tmp_path):
        tx = SandboxTransaction(_workspace(tmp_path))
        tx._active = True
        tx.start_time = time.time() - 9999
        tx.check_resource_limits()

    def test_max_bytes_without_target_skips(self, tmp_path):
        tx = SandboxTransaction(tmp_path / "missing_target", max_bytes=10)
        tx._active = True
        tx.check_resource_limits()

    def test_disk_cap_breach_raises(self, tmp_path):
        ws = _workspace(tmp_path)
        tx = SandboxTransaction(ws, max_bytes=8)
        tx._active = True
        with pytest.raises(MemoryError, match="exceeded disk size cap"):
            tx.check_resource_limits()

    def test_disk_size_within_cap_passes(self, tmp_path):
        ws = _workspace(tmp_path)
        tx = SandboxTransaction(ws, max_bytes=10_000_000)
        tx._active = True
        tx.check_resource_limits()

    def test_exit_rolls_back_and_reraises_on_cap_breach(self, tmp_path):
        ws = _workspace(tmp_path)
        tx = SandboxTransaction(ws, timeout_seconds=1.0)
        tx.__enter__()
        tx.start_time = time.time() - 5
        with pytest.raises(TimeoutError, match="timed out"):
            tx.__exit__(None, None, None)
        assert tx._active is False
        assert tx.snapshot_dir is None


class TestSandboxTransactionCleanup:
    def test_cleanup_without_snapshot_is_noop(self, tmp_path):
        tx = SandboxTransaction(_workspace(tmp_path))
        tx._cleanup_snapshot()
        assert tx.snapshot_dir is None

    def test_cleanup_removes_snapshot_dir(self, tmp_path):
        tx = SandboxTransaction(_workspace(tmp_path))
        tx.start()
        snapshot = tx.snapshot_dir
        assert snapshot.exists()
        tx._cleanup_snapshot()
        assert not snapshot.exists()
        assert tx.snapshot_dir is None


# ============================================================================
# enterprise_endpoints
# ============================================================================


class TestEnterpriseSecurity:
    def test_security_status(self, enterprise_client):
        resp = enterprise_client.get("/api/enterprise/security/status")
        assert resp.status_code == 200
        body = resp.json()
        assert body["overall_status"] == "secure"
        assert body["features_enabled"] == 8
        assert body["total_features"] == 8
        assert body["security_metrics"]["encryption_strength"] == "AES-256"
        assert body["validation_evidence"]["certifications"] == [
            "SOC 2 Type II", "ISO 27001:2022", "GDPR Compliance",
            "HIPAA Compliance", "PCI DSS Level 1", "FedRAMP Authorized",
        ]

    def test_security_features(self, enterprise_client):
        resp = enterprise_client.get("/api/enterprise/security/features")
        assert resp.status_code == 200
        features = resp.json()
        assert len(features) == 8
        assert all(f["enabled"] is True for f in features)
        assert features[0]["compliance_level"] == "AES-256"


class TestEnterpriseUptime:
    def test_uptime_metrics(self, enterprise_client):
        resp = enterprise_client.get("/api/enterprise/uptime")
        assert resp.status_code == 200
        body = resp.json()
        assert set(body) == {
            "current_uptime_percentage", "uptime_last_30_days", "uptime_last_90_days",
            "uptime_last_year", "total_downtime_minutes", "sla_compliance",
        }
        assert 90.0 <= body["current_uptime_percentage"] <= 100.0
        assert body["total_downtime_minutes"] == 42

    def test_uptime_keeps_value_within_bounds_over_calls(self, enterprise_client):
        for _ in range(3):
            enterprise_client.get("/api/enterprise/uptime")
        value = enterprise_data["uptime"]["current_uptime_percentage"]
        assert 90.0 <= value <= 100.0


class TestEnterpriseReliability:
    def test_reliability_metrics(self, enterprise_client):
        resp = enterprise_client.get("/api/enterprise/reliability/metrics")
        assert resp.status_code == 200
        metrics = resp.json()
        assert len(metrics) == 6
        names = {m["metric_name"] for m in metrics}
        assert {"api_availability", "error_rate", "data_backup_success"} <= names
        for m in metrics:
            base = enterprise_data["reliability_metrics"][m["metric_name"]]["value"]
            assert 0.0 <= m["value"] <= round(base * 1.02, 2)
            assert m["status"] in ("exceeding", "met", "failing")
            assert m["trend"] in ("stable", "improving", "decreasing", "increasing")


class TestEnterpriseCompliance:
    def test_all_reports(self, enterprise_client):
        resp = enterprise_client.get("/api/enterprise/compliance/reports")
        assert resp.status_code == 200
        reports = resp.json()
        assert len(reports) == 4
        assert {r["compliance_standard"] for r in reports} == {
            "SOC 2 Type II", "ISO 27001", "GDPR", "HIPAA",
        }
        assert all(r["score"] >= 95.0 for r in reports)

    def test_single_report_case_insensitive(self, enterprise_client):
        resp = enterprise_client.get("/api/enterprise/compliance/gdpr")
        assert resp.status_code == 200
        assert resp.json()["compliance_standard"] == "GDPR"

    def test_unknown_standard_404(self, enterprise_client):
        resp = enterprise_client.get("/api/enterprise/compliance/iso-9001")
        assert resp.status_code == 404
        assert "not found" in resp.json()["detail"]


class TestEnterpriseSla:
    def test_sla_status(self, enterprise_client):
        resp = enterprise_client.get("/api/enterprise/sla/status")
        assert resp.status_code == 200
        body = resp.json()
        assert body["sla_status"] == "exceeding"
        assert body["current_sla_achievement"] == 99.97
        assert len(body["monitored_services"]) == 4
        assert body["validation_evidence"]["enterprise_sla_compliance"] is True


class TestEnterpriseBackup:
    def test_backup_status(self, enterprise_client):
        resp = enterprise_client.get("/api/enterprise/backup/status")
        assert resp.status_code == 200
        body = resp.json()
        assert body["backup_system"] == "operational"
        assert body["backup_frequency"] == "hourly"
        assert body["backup_retention_days"] == 365
        assert body["drill_success_rate"] == 100.0
        assert body["validation_evidence"]["rto_rpo_met"] is True


class TestEnterpriseMonitoring:
    def test_monitoring_status(self, enterprise_client):
        resp = enterprise_client.get("/api/enterprise/monitoring/status")
        assert resp.status_code == 200
        body = resp.json()
        assert body["active_monitors"] == 156
        assert "PagerDuty" in body["alert_channels"]
        assert body["uptime_monitoring"]["external_monitors"] == 12
        assert body["validation_evidence"]["24x7_monitoring"] is True


class TestEnterpriseStatus:
    def test_enterprise_status(self, enterprise_client):
        resp = enterprise_client.get("/api/enterprise/status")
        assert resp.status_code == 200
        body = resp.json()
        assert body["enterprise_status"] == "operational"
        assert body["enterprise_grade"] is True
        assert all(body["critical_capabilities"].values())
        assert body["validation_evidence"]["sla_metrics_exceeding"] is True


# ============================================================================
# storage
# ============================================================================


class TestImportBoto3:
    def test_imports_boto3_and_config(self):
        boto3, config_cls = _import_boto3()
        assert boto3 is not None
        assert config_cls is not None

    def test_import_failure_returns_none_none(self):
        with patch.dict(sys.modules, {"boto3": None}):
            boto3, config_cls = _import_boto3()
        assert boto3 is None
        assert config_cls is None


class _FakeConfig:
    def __init__(self, **kwargs):
        self.kwargs = kwargs


class TestGetS3Client:
    def test_returns_none_when_boto3_missing(self):
        with patch("core.storage._import_boto3", return_value=(None, None)):
            service = StorageService.__new__(StorageService)
            assert service._get_s3_client() is None

    def test_client_with_default_endpoint_and_region(self):
        fake_boto3 = Mock()
        fake_boto3.client.return_value = "s3-client"
        with patch("core.storage._import_boto3", return_value=(fake_boto3, _FakeConfig)):
            service = StorageService.__new__(StorageService)
            client = service._get_s3_client()
        assert client == "s3-client"
        kwargs = fake_boto3.client.call_args[1]
        assert kwargs["region_name"] == "us-east-1"
        assert "endpoint_url" not in kwargs
        assert "config" not in kwargs

    def test_client_with_endpoint_url_and_path_style(self, monkeypatch):
        fake_boto3 = Mock()
        fake_boto3.client.return_value = "s3-client"
        monkeypatch.setenv("S3_ENDPOINT", "https://r2.example.com")
        monkeypatch.setenv("STORAGE_AWS_ACCESS_KEY_ID", "ak")
        monkeypatch.setenv("STORAGE_AWS_SECRET_ACCESS_KEY", "sk")
        monkeypatch.setenv("STORAGE_AWS_REGION", "auto")
        with patch("core.storage._import_boto3", return_value=(fake_boto3, _FakeConfig)):
            service = StorageService.__new__(StorageService)
            client = service._get_s3_client()
        assert client == "s3-client"
        kwargs = fake_boto3.client.call_args[1]
        assert kwargs["endpoint_url"] == "https://r2.example.com"
        assert kwargs["region_name"] == "auto"
        assert kwargs["config"].kwargs["s3"]["addressing_style"] == "path"

    def test_client_falls_back_to_aws_env_vars(self, monkeypatch):
        fake_boto3 = Mock()
        fake_boto3.client.return_value = "s3-client"
        monkeypatch.setenv("AWS_ENDPOINT_URL", "https://custom.endpoint")
        monkeypatch.setenv("AWS_ACCESS_KEY_ID", "aws-ak")
        monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "aws-sk")
        monkeypatch.delenv("AWS_REGION", raising=False)
        with patch("core.storage._import_boto3", return_value=(fake_boto3, _FakeConfig)):
            service = StorageService.__new__(StorageService)
            client = service._get_s3_client()
        kwargs = fake_boto3.client.call_args[1]
        assert kwargs["endpoint_url"] == "https://custom.endpoint"
        assert kwargs["aws_access_key_id"] == "aws-ak"
        assert kwargs["aws_secret_access_key"] == "aws-sk"
        assert kwargs["region_name"] == "us-east-1"

    def test_r2_precedence_over_aws_keys(self, monkeypatch):
        fake_boto3 = Mock()
        fake_boto3.client.return_value = "s3-client"
        monkeypatch.setenv("R2_ACCESS_KEY_ID", "r2-ak")
        monkeypatch.setenv("AWS_ACCESS_KEY_ID", "aws-ak")
        with patch("core.storage._import_boto3", return_value=(fake_boto3, _FakeConfig)):
            service = StorageService.__new__(StorageService)
            service._get_s3_client()
        kwargs = fake_boto3.client.call_args[1]
        assert kwargs["aws_access_key_id"] == "r2-ak"


class TestStorageServiceInit:
    def test_default_bucket_name(self):
        fake_boto3 = Mock()
        fake_boto3.client.return_value = "s3-client"
        with patch.dict(os.environ, {}, clear=True), patch(
            "core.storage._import_boto3", return_value=(fake_boto3, _FakeConfig)
        ):
            service = StorageService()
        assert service.bucket == "atom-saas"

    def test_bucket_env_precedence(self, monkeypatch):
        fake_boto3 = Mock()
        fake_boto3.client.return_value = "s3-client"
        monkeypatch.setenv("AWS_S3_BUCKET", "first")
        monkeypatch.setenv("AWS_S3_BUCKET_NAME", "second")
        with patch("core.storage._import_boto3", return_value=(fake_boto3, _FakeConfig)):
            service = StorageService()
        assert service.bucket == "first"

    def test_bucket_name_fallback_env(self, monkeypatch):
        fake_boto3 = Mock()
        fake_boto3.client.return_value = "s3-client"
        monkeypatch.delenv("AWS_S3_BUCKET", raising=False)
        monkeypatch.setenv("AWS_S3_BUCKET_NAME", "second")
        with patch("core.storage._import_boto3", return_value=(fake_boto3, _FakeConfig)):
            service = StorageService()
        assert service.bucket == "second"

    def test_init_sets_s3_and_bucket(self, monkeypatch):
        fake_boto3 = Mock()
        fake_boto3.client.return_value = "s3-client"
        monkeypatch.setenv("AWS_S3_BUCKET", "env-bucket")
        with patch("core.storage._import_boto3", return_value=(fake_boto3, _FakeConfig)):
            service = StorageService()
        assert service.s3 == "s3-client"
        assert service.bucket == "env-bucket"

    def test_init_without_boto3_sets_s3_none(self):
        with patch("core.storage._import_boto3", return_value=(None, None)):
            service = StorageService()
        assert service.s3 is None
        assert service.bucket == "atom-saas"


class TestUploadFile:
    def test_upload_success_returns_s3_uri(self):
        service = StorageService.__new__(StorageService)
        service.s3 = Mock()
        service.bucket = "bucket"
        result = service.upload_file(BytesIO(b"data"), "path/file.txt")
        assert result == "s3://bucket/path/file.txt"
        service.s3.upload_fileobj.assert_called_once()

    def test_upload_with_content_type(self):
        service = StorageService.__new__(StorageService)
        service.s3 = Mock()
        service.bucket = "bucket"
        service.upload_file(BytesIO(b"data"), "f.txt", content_type="text/plain")
        kwargs = service.s3.upload_fileobj.call_args[1]
        assert kwargs["ExtraArgs"]["ContentType"] == "text/plain"

    def test_upload_without_content_type_uses_empty_extra_args(self):
        service = StorageService.__new__(StorageService)
        service.s3 = Mock()
        service.bucket = "bucket"
        service.upload_file(BytesIO(b"data"), "f.txt")
        kwargs = service.s3.upload_fileobj.call_args[1]
        assert kwargs["ExtraArgs"] == {}

    def test_upload_failure_logs_and_reraises(self):
        service = StorageService.__new__(StorageService)
        service.s3 = Mock()
        service.bucket = "bucket"
        service.s3.upload_fileobj.side_effect = OSError("conn refused")
        with pytest.raises(OSError, match="conn refused"):
            service.upload_file(BytesIO(b"data"), "f.txt")


class TestCheckExists:
    def test_exists_true(self):
        service = StorageService.__new__(StorageService)
        service.s3 = Mock()
        service.bucket = "bucket"
        service.s3.head_object.return_value = {}
        assert service.check_exists("k") is True
        service.s3.head_object.assert_called_once_with(Bucket="bucket", Key="k")

    def test_missing_false(self):
        service = StorageService.__new__(StorageService)
        service.s3 = Mock()
        service.bucket = "bucket"
        service.s3.head_object.side_effect = Exception("404")
        assert service.check_exists("k") is False


class TestDownloadFile:
    def test_download_returns_body_bytes(self):
        service = StorageService.__new__(StorageService)
        service.s3 = Mock()
        service.bucket = "bucket"
        service.s3.get_object.return_value = {"Body": BytesIO(b"content")}
        assert service.download_file("k") == b"content"
        service.s3.get_object.assert_called_once_with(Bucket="bucket", Key="k")


class TestDeleteObject:
    def test_delete_success(self):
        service = StorageService.__new__(StorageService)
        service.s3 = Mock()
        service.bucket = "bucket"
        assert service.delete_object("k") is True
        service.s3.delete_object.assert_called_once_with(Bucket="bucket", Key="k")

    def test_delete_failure_returns_false(self):
        service = StorageService.__new__(StorageService)
        service.s3 = Mock()
        service.bucket = "bucket"
        service.s3.delete_object.side_effect = Exception("forbidden")
        assert service.delete_object("k") is False


class TestListKeys:
    def test_list_keys_paginated_and_sorted(self):
        service = StorageService.__new__(StorageService)
        service.s3 = Mock()
        service.bucket = "bucket"
        paginator = Mock()
        paginator.paginate.return_value = [
            {"Contents": [{"Key": "b"}, {"Key": "a"}]},
            {"Contents": [{"Key": "c"}]},
        ]
        service.s3.get_paginator.return_value = paginator
        assert service.list_keys("pre") == ["a", "b", "c"]
        paginator.paginate.assert_called_once_with(Bucket="bucket", Prefix="pre")

    def test_list_keys_empty_pages(self):
        service = StorageService.__new__(StorageService)
        service.s3 = Mock()
        service.bucket = "bucket"
        paginator = Mock()
        paginator.paginate.return_value = [{}, {"Contents": []}]
        service.s3.get_paginator.return_value = paginator
        assert service.list_keys() == []

    def test_list_keys_default_prefix(self):
        service = StorageService.__new__(StorageService)
        service.s3 = Mock()
        service.bucket = "bucket"
        paginator = Mock()
        paginator.paginate.return_value = []
        service.s3.get_paginator.return_value = paginator
        assert service.list_keys() == []
        paginator.paginate.assert_called_once_with(Bucket="bucket", Prefix="")


class TestGetStorageService:
    def test_creates_and_caches_singleton(self):
        cls = Mock(return_value="instance")
        cls._instance = None
        with patch("core.storage.StorageService", cls):
            assert get_storage_service() == "instance"
            assert get_storage_service() == "instance"
        assert cls.call_count == 1

    def test_returns_existing_instance_without_recreating(self):
        service = MagicMock()
        cls = Mock()
        cls._instance = service
        with patch("core.storage.StorageService", cls):
            assert get_storage_service() is service
        cls.assert_not_called()
