"""Wave 117 coverage: integrations.whatsapp_database_optimization_final.

Covers the optimizer's executable parts: DDL generation (create_performance_indexes),
idempotency-style result bookkeeping, success/failure branching of the composite
run, and result accessor. Pure in-memory object — no DB, no network.
"""

import logging
from unittest import mock

import pytest

from integrations.whatsapp_database_optimization_final import WhatsAppDatabaseOptimizer

pytestmark = pytest.mark.usefixtures("_silence_optimizer_logs")


@pytest.fixture
def _silence_optimizer_logs():
    logging.getLogger("integrations.whatsapp_database_optimization_final").setLevel(logging.CRITICAL)


class TestOptimizationSteps:
    def test_create_performance_indexes(self):
        optimizer = WhatsAppDatabaseOptimizer()
        assert optimizer.create_performance_indexes() is True
        results = optimizer.get_optimization_results()
        assert "Database indexes created" in results["optimizations_applied"]
        assert results["performance_improvements"]["query_speed"] == "50% faster"

    def test_implement_query_caching(self):
        optimizer = WhatsAppDatabaseOptimizer()
        assert optimizer.implement_query_caching() is True
        results = optimizer.get_optimization_results()
        assert "Query caching implemented" in results["optimizations_applied"]
        assert results["performance_improvements"]["api_response"] == "40% faster"

    def test_optimize_connection_pooling(self):
        optimizer = WhatsAppDatabaseOptimizer()
        assert optimizer.optimize_connection_pooling() is True
        results = optimizer.get_optimization_results()
        assert "Connection pooling optimized" in results["optimizations_applied"]
        assert results["performance_improvements"]["connection_time"] == "30% faster"

    @pytest.mark.parametrize(
        "method_name",
        ["create_performance_indexes", "implement_query_caching", "optimize_connection_pooling"],
    )
    def test_step_exception_returns_false(self, method_name):
        optimizer = WhatsAppDatabaseOptimizer()
        optimizer.optimization_results = None  # AttributeError inside -> except path
        assert getattr(optimizer, method_name)() is False


class TestCompleteOptimization:
    def test_all_steps_success(self):
        optimizer = WhatsAppDatabaseOptimizer()
        assert optimizer.run_complete_optimization() is True
        results = optimizer.get_optimization_results()
        assert results["success"] is True
        assert results["overall_improvement"] == "50% faster"
        assert len(results["optimizations_applied"]) == 3

    def test_partial_failure_marks_unsuccessful(self):
        optimizer = WhatsAppDatabaseOptimizer()
        with mock.patch.object(optimizer, "create_performance_indexes", return_value=False):
            assert optimizer.run_complete_optimization() is False
        results = optimizer.get_optimization_results()
        assert results["success"] is False
        assert "overall_improvement" not in results
        # the remaining steps still ran
        assert len(results["optimizations_applied"]) == 2

    def test_cascading_failures_tracked(self):
        optimizer = WhatsAppDatabaseOptimizer()
        with (
            mock.patch.object(optimizer, "create_performance_indexes", return_value=False),
            mock.patch.object(optimizer, "implement_query_caching", return_value=False),
        ):
            assert optimizer.run_complete_optimization() is False
        results = optimizer.get_optimization_results()
        assert results["success"] is False
        assert len(results["optimizations_applied"]) == 1  # only pooling appended

    def test_pooling_failure_branch(self):
        optimizer = WhatsAppDatabaseOptimizer()
        with mock.patch.object(optimizer, "optimize_connection_pooling", return_value=False):
            assert optimizer.run_complete_optimization() is False
        results = optimizer.get_optimization_results()
        assert results["success"] is False
        assert len(results["optimizations_applied"]) == 2  # indexes + caching appended

    def test_exception_returns_false(self):
        optimizer = WhatsAppDatabaseOptimizer()
        with mock.patch.object(optimizer, "create_performance_indexes", side_effect=RuntimeError("boom")):
            assert optimizer.run_complete_optimization() is False


class TestResults:
    def test_initial_state(self):
        results = WhatsAppDatabaseOptimizer().get_optimization_results()
        assert results["optimizations_applied"] == []
        assert results["performance_improvements"] == {}
        assert results["success"] is False
        assert "T" in results["timestamp"]

    def test_get_optimization_results_returns_internal_dict(self):
        optimizer = WhatsAppDatabaseOptimizer()
        assert optimizer.get_optimization_results() is optimizer.optimization_results
