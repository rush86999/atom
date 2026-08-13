# -*- coding: utf-8 -*-
"""Coverage wave 74 — core/webhook_metrics.py (standalone, zero LLM spend,
no network, no real DB/Redis).

Covers: delivery recording (success/signature_error, sample trimming >1000),
delivery counts/percentiles (empty + populated), signature failure counts,
processing success/error recording (error-type breakdown, duration-only-if>0,
sample trimming), processing counts/percentiles/entities, delivery &
processing success rates (with-data + empty), total deliveries across tenants,
full Prometheus export (all metric families incl. duration percentiles and
error types), persist_to_redis (no client / success / failure), singleton
get_instance, module-level convenience functions, get_webhook_metrics.
"""
import json
from unittest.mock import MagicMock

import pytest

from core.webhook_metrics import (
    WebhookMetrics,
    get_webhook_metrics,
    record_webhook_delivery,
    record_webhook_processing_error,
    record_webhook_processing_success,
)


@pytest.fixture()
def metrics():
    return WebhookMetrics()


class TestDelivery:
    def test_record_success(self, metrics):
        metrics.record_delivery("slack", "tenant-12345678", 45.0, signature_valid=True)
        assert metrics.get_delivery_count("slack", "tenant-12345678") == 1
        assert metrics.get_signature_failure_count("slack", "tenant-12345678") == 0
        assert metrics.get_delivery_rate("slack", "tenant-12345678") == 100.0

    def test_record_signature_error(self, metrics):
        metrics.record_delivery("slack", "tenant-12345678", 45.0, signature_valid=False)
        assert metrics.get_delivery_count("slack", "tenant-12345678") == 1
        assert metrics.get_signature_failure_count("slack", "tenant-12345678") == 1
        assert metrics.get_delivery_rate("slack", "tenant-12345678") == 0.0

    def test_mixed_rate(self, metrics):
        metrics.record_delivery("slack", "tenant-12345678", 10.0, True)
        metrics.record_delivery("slack", "tenant-12345678", 10.0, True)
        metrics.record_delivery("slack", "tenant-12345678", 10.0, False)
        assert metrics.get_delivery_count("slack", "tenant-12345678") == 3
        assert metrics.get_delivery_rate("slack", "tenant-12345678") == pytest.approx(66.666, rel=1e-2)

    def test_short_tenant_key(self, metrics):
        metrics.record_delivery("gh", "t1", 5.0, True)
        assert metrics.get_delivery_count("gh", "t1") == 1

    def test_unknown_tenant_defaults(self, metrics):
        metrics.record_delivery("slack", "", 5.0, True)
        assert metrics.get_delivery_count("slack", "") == 1
        assert metrics.get_delivery_count("slack", "other") == 0

    def test_rate_with_no_data_returns_100(self, metrics):
        assert metrics.get_delivery_rate("slack", "tenant-x") == 100.0

    def test_percentiles_empty(self, metrics):
        p = metrics.get_delivery_percentiles("slack", "tenant-x")
        assert p == {"p50": 0, "p95": 0, "p99": 0}

    def test_percentiles_populated(self, metrics):
        for i in range(1, 101):
            metrics.record_delivery("slack", "tenant-x", float(i), True)
        p = metrics.get_delivery_percentiles("slack", "tenant-x")
        # index = int(n * frac) with 0-based indexing
        assert p["p50"] == 51
        assert p["p95"] == 96
        assert p["p99"] == 100

    def test_sample_trimming(self, metrics):
        for i in range(1001):
            metrics.record_delivery("slack", "tenant-x", float(i), True)
        key = metrics._make_duration_key("slack", "tenant-x")
        assert len(metrics._delivery_duration_samples[key]) == 1000
        assert metrics._delivery_duration_samples[key][0] == 1.0

    def test_total_deliveries_across_tenants(self, metrics):
        metrics.record_delivery("slack", "tenant-aaaa", 1.0, True)
        metrics.record_delivery("slack", "tenant-bbbb", 1.0, True)
        metrics.record_delivery("slack", "tenant-bbbb", 1.0, False)
        metrics.record_delivery("teams", "tenant-cccc", 1.0, True)
        assert metrics.get_total_deliveries("slack") == 3
        assert metrics.get_total_deliveries("teams") == 1


class TestProcessing:
    def test_success_recording(self, metrics):
        metrics.record_processing_success("hubspot", "tenant-1", 150.0, entities_count=5)
        assert metrics.get_processing_success_count("hubspot", "tenant-1") == 1
        assert metrics.get_entities_extracted_count("hubspot", "tenant-1") == 5
        assert metrics.get_processing_success_rate("hubspot", "tenant-1") == 100.0

    def test_error_recording(self, metrics):
        metrics.record_processing_error("hubspot", "tenant-1", "transformation_error", 50.0)
        metrics.record_processing_error("hubspot", "tenant-1", "llm_error")
        assert metrics.get_processing_error_count("hubspot", "tenant-1") == 2
        errors = metrics.get_processing_errors_by_type("hubspot", "tenant-1")
        assert errors == {"transformation_error": 1, "llm_error": 1}

    def test_rate_with_mixed(self, metrics):
        metrics.record_processing_success("hubspot", "tenant-1", 10.0)
        metrics.record_processing_error("hubspot", "tenant-1", "llm_error")
        assert metrics.get_processing_success_rate("hubspot", "tenant-1") == 50.0

    def test_rate_no_data(self, metrics):
        assert metrics.get_processing_success_rate("hubspot", "tenant-1") == 100.0

    def test_error_with_zero_duration_skips_samples(self, metrics):
        metrics.record_processing_error("hubspot", "tenant-1", "x", 0)
        assert metrics.get_processing_percentiles("hubspot", "tenant-1") == {"p50": 0, "p95": 0, "p99": 0}

    def test_processing_percentiles(self, metrics):
        for i in range(1, 101):
            metrics.record_processing_success("hubspot", "tenant-1", float(i))
        p = metrics.get_processing_percentiles("hubspot", "tenant-1")
        assert p["p50"] == 51
        assert p["p95"] == 96
        assert p["p99"] == 100

    def test_processing_sample_trimming(self, metrics):
        for i in range(1001):
            metrics.record_processing_success("hubspot", "tenant-1", float(i))
        key = metrics._make_duration_key("hubspot", "tenant-1")
        assert len(metrics._processing_duration_samples[key]) == 1000

    def test_errors_by_type_unknown(self, metrics):
        assert metrics.get_processing_errors_by_type("hubspot", "nope") == {}
        assert metrics.get_processing_success_count("hubspot", "nope") == 0
        assert metrics.get_processing_error_count("hubspot", "nope") == 0
        assert metrics.get_entities_extracted_count("hubspot", "nope") == 0


class TestExportPrometheus:
    def test_empty_export_has_base_lines(self, metrics):
        out = metrics.export_prometheus()
        assert "webhook_" not in out  # no webhook metrics yet

    def test_full_export(self, metrics):
        metrics.record_delivery("slack", "tenant-12345678", 10.0, True)
        metrics.record_delivery("slack", "tenant-12345678", 30.0, True)
        metrics.record_delivery("slack", "tenant-12345678", 5.0, False)
        metrics.record_processing_success("hubspot", "tenant-87654321", 20.0, entities_count=3)
        metrics.record_processing_error("hubspot", "tenant-87654321", "transformation_error", 4.0)

        out = metrics.export_prometheus()
        assert 'webhook_delivery_count{connector_id="slack",tenant_id="tenant-1",status="success"} 2' in out
        assert 'webhook_delivery_count{connector_id="slack",tenant_id="tenant-1",status="signature_error"} 1' in out
        assert 'webhook_delivery_duration_ms{connector_id="slack",tenant_id="tenant-1",p="50"}' in out
        assert 'webhook_delivery_duration_ms{connector_id="slack",tenant_id="tenant-1",p="95"}' in out
        assert 'webhook_delivery_duration_ms{connector_id="slack",tenant_id="tenant-1",p="99"}' in out
        assert 'webhook_signature_verification_failures{connector_id="slack",tenant_id="tenant-1"} 1' in out
        assert 'webhook_processing_count{connector_id="hubspot",tenant_id="tenant-8",status="success"} 1' in out
        assert 'webhook_processing_count{connector_id="hubspot",tenant_id="tenant-8",status="error"} 1' in out
        assert 'webhook_processing_duration_ms{connector_id="hubspot",tenant_id="tenant-8",p="50"}' in out
        assert 'webhook_entities_extracted{connector_id="hubspot",tenant_id="tenant-8"} 3' in out
        assert 'webhook_transformation_errors{connector_id="hubspot",tenant_id="tenant-8",error_type="transformation_error"} 1' in out

    def test_export_skips_empty_duration_samples(self, metrics):
        metrics._delivery_duration_samples["slack:ten:duration"] = []
        metrics._processing_duration_samples["hubspot:ten:duration"] = []
        out = metrics.export_prometheus()
        assert "webhook_delivery_duration_ms" not in out
        assert "webhook_processing_duration_ms" not in out


class TestPersistence:
    def test_no_redis_client_returns(self, metrics):
        assert metrics.persist_to_redis(None) is None

    def test_persist_success(self, metrics):
        metrics.record_delivery("slack", "tenant-1", 5.0, True)
        metrics.record_processing_error("slack", "tenant-1", "llm_error")
        client = MagicMock()
        metrics.persist_to_redis(client)
        client.setex.assert_called_once()
        key, ttl, payload = client.setex.call_args[0]
        assert key == "webhook:metrics:current"
        assert ttl == 3600
        data = json.loads(payload)
        assert "delivery_counts" in data
        assert "processing_error_counts" in data

    def test_persist_failure_logged(self, metrics):
        client = MagicMock()
        client.setex.side_effect = RuntimeError("redis down")
        metrics.persist_to_redis(client)  # must not raise


class TestSingletonAndModuleFunctions:
    def test_get_instance_singleton(self):
        a = WebhookMetrics.get_instance()
        b = WebhookMetrics.get_instance()
        assert a is b

    def test_module_level_delivery(self):
        metrics = WebhookMetrics()
        record_webhook_delivery("slack", "tenant-1", 5.0, True)
        assert metrics.get_delivery_count("slack", "tenant-1") == 0  # separate instance

    def test_module_functions_use_singleton(self):
        record_webhook_processing_success("slack", "tenant-1", 5.0, entities_count=2)
        record_webhook_processing_error("slack", "tenant-1", "llm_error")
        singleton = WebhookMetrics.get_instance()
        assert singleton.get_processing_success_count("slack", "tenant-1") == 1
        assert singleton.get_processing_error_count("slack", "tenant-1") == 1

    def test_get_webhook_metrics_returns_instance(self):
        # module-level singleton is distinct from the class-level one
        assert isinstance(get_webhook_metrics(), WebhookMetrics)
        assert get_webhook_metrics() is get_webhook_metrics()
