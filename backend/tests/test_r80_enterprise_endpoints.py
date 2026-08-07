# -*- coding: utf-8 -*-
"""Round 80 — zero-coverage gap: core/enterprise_endpoints.py.

Exercises every route on the ``/api/enterprise`` router (uptime, security,
reliability, compliance, SLA, backup, monitoring, status) via TestClient so
the Pydantic response models are validated too.
"""
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from core.enterprise_endpoints import router, enterprise_data


@pytest.fixture()
def client():
    app = FastAPI()
    app.include_router(router)
    with TestClient(app) as c:
        yield c


class TestSecurity:
    def test_security_status(self, client):
        resp = client.get("/api/enterprise/security/status")
        assert resp.status_code == 200
        body = resp.json()
        assert body["overall_status"] == "secure"
        assert body["features_enabled"] == 8
        assert body["total_features"] == 8
        assert body["validation_evidence"]["enterprise_security_verified"] is True

    def test_security_features_list(self, client):
        resp = client.get("/api/enterprise/security/features")
        assert resp.status_code == 200
        features = resp.json()
        assert len(features) == 8
        names = {f["feature_name"] for f in features}
        assert {"Data Encryption", "Multi-Factor Authentication", "Audit Logging"} <= names
        assert all(f["enabled"] is True for f in features)
        assert all(f["status"] == "compliant" for f in features)


class TestUptime:
    def test_uptime_metrics_model(self, client):
        resp = client.get("/api/enterprise/uptime")
        assert resp.status_code == 200
        body = resp.json()
        assert 90.0 <= body["current_uptime_percentage"] <= 100.0
        assert body["uptime_last_30_days"] == 99.95
        assert body["sla_compliance"] is True
        assert body["total_downtime_minutes"] == 42
        # NOTE: validation_evidence is computed in the handler but filtered out
        # by the UptimeMetrics response model — assert the model's fields only.
        assert set(body) == {
            "current_uptime_percentage", "uptime_last_30_days", "uptime_last_90_days",
            "uptime_last_year", "total_downtime_minutes", "sla_compliance",
        }

    def test_uptime_mutates_state_within_bounds(self, client):
        client.get("/api/enterprise/uptime")
        client.get("/api/enterprise/uptime")
        assert 90.0 <= enterprise_data["uptime"]["current_uptime_percentage"] <= 100.0


class TestReliability:
    def test_reliability_metrics(self, client):
        resp = client.get("/api/enterprise/reliability/metrics")
        assert resp.status_code == 200
        metrics = resp.json()
        assert len(metrics) == 6
        names = {m["metric_name"] for m in metrics}
        assert {"api_availability", "error_rate", "response_time_p99"} <= names
        for m in metrics:
            base = enterprise_data["reliability_metrics"][m["metric_name"]]["value"]
            assert 0.0 <= m["value"] <= round(base * 1.02, 2)
            assert m["status"] in ("exceeding", "met", "failing")
            assert m["trend"] in ("stable", "improving", "decreasing", "increasing")


class TestCompliance:
    def test_all_reports(self, client):
        resp = client.get("/api/enterprise/compliance/reports")
        assert resp.status_code == 200
        reports = resp.json()
        assert len(reports) == 4
        standards = {r["compliance_standard"] for r in reports}
        assert standards == {"SOC 2 Type II", "ISO 27001", "GDPR", "HIPAA"}
        assert all(r["score"] >= 95.0 for r in reports)
        assert all(r["status"] == "compliant" for r in reports)

    def test_single_report_case_insensitive(self, client):
        resp = client.get("/api/enterprise/compliance/hipaa")
        assert resp.status_code == 200
        assert resp.json()["compliance_standard"] == "HIPAA"

    def test_unknown_standard_404(self, client):
        resp = client.get("/api/enterprise/compliance/iso-9001")
        assert resp.status_code == 404


class TestSla:
    def test_sla_status(self, client):
        resp = client.get("/api/enterprise/sla/status")
        assert resp.status_code == 200
        body = resp.json()
        assert body["sla_status"] == "exceeding"
        assert body["current_sla_achievement"] >= body["sla_target"]
        assert len(body["monitored_services"]) == 4
        assert all(s["status"] == "compliant" for s in body["monitored_services"])
        assert body["validation_evidence"]["uptime_99_9_verified"] is True


class TestBackup:
    def test_backup_status(self, client):
        resp = client.get("/api/enterprise/backup/status")
        assert resp.status_code == 200
        body = resp.json()
        assert body["backup_system"] == "operational"
        assert body["backup_frequency"] == "hourly"
        assert len(body["backup_locations"]) == 3
        assert body["validation_evidence"]["disaster_recovery_ready"] is True


class TestMonitoring:
    def test_monitoring_status(self, client):
        resp = client.get("/api/enterprise/monitoring/status")
        assert resp.status_code == 200
        body = resp.json()
        assert body["monitoring_system"] == "operational"
        assert body["active_monitors"] == 156
        assert "PagerDuty" in body["alert_channels"]
        assert body["validation_evidence"]["24x7_monitoring"] is True


class TestOverallStatus:
    def test_enterprise_status(self, client):
        resp = client.get("/api/enterprise/status")
        assert resp.status_code == 200
        body = resp.json()
        assert body["enterprise_status"] == "operational"
        assert body["enterprise_grade"] is True
        assert all(body["critical_capabilities"].values())
        assert body["validation_evidence"]["enterprise_99_9_uptime_verified"] is True
