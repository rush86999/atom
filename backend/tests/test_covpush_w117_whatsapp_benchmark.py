"""Wave 117 coverage: integrations.whatsapp_performance_benchmark.

Covers the benchmark harness executable logic (result parsing, formatting,
thresholds) with fully mocked requests/time — zero network. Also locks in the
RED->GREEN fix for the undefined-``logger`` NameError on the request-exception
path (the method must return False, not crash).
"""

import logging
import time
from unittest import mock

import pytest

from integrations.whatsapp_performance_benchmark import WhatsAppPerformanceBenchmark

pytestmark = pytest.mark.usefixtures("_silence_benchmark_logs")


@pytest.fixture
def _silence_benchmark_logs():
    logging.getLogger("integrations.whatsapp_performance_benchmark").setLevel(logging.CRITICAL)


def _fake_response(status_code):
    return mock.Mock(status_code=status_code)


class TestInitAndGetter:
    def test_init_results_structure(self):
        bench = WhatsAppPerformanceBenchmark()
        assert bench.base_url == "http://127.0.0.1:5058"
        assert set(bench.results) == {"timestamp", "api_endpoints", "overall_metrics", "performance_grade"}
        assert bench.results["api_endpoints"] == {}
        assert bench.results["overall_metrics"] == {}
        assert bench.results["performance_grade"] == "UNKNOWN"
        assert "T" in bench.results["timestamp"]  # ISO datetime

    def test_get_benchmark_results_returns_internal_dict(self):
        bench = WhatsAppPerformanceBenchmark()
        bench.results["api_endpoints"]["x"] = {"y": 1}
        assert bench.get_benchmark_results() is bench.results


class TestPerformanceGrade:
    @pytest.mark.parametrize(
        ("avg", "expected"),
        [
            (0.0, "A+ (Excellent)"),
            (99.99, "A+ (Excellent)"),
            (100.0, "A (Good)"),
            (199.99, "A (Good)"),
            (200.0, "B (Fair)"),
            (499.99, "B (Fair)"),
            (500.0, "C (Poor)"),
            (5000.0, "C (Poor)"),
        ],
    )
    def test_grade_boundaries(self, avg, expected):
        assert WhatsAppPerformanceBenchmark().get_performance_grade(avg) == expected


class TestBenchmarkApiEndpoint:
    def test_success_path_records_metrics(self):
        bench = WhatsAppPerformanceBenchmark()
        deltas = [100.0, 100.05, 100.10, 100.12]  # 50ms, 20ms
        with (
            mock.patch("time.time", side_effect=deltas),
            mock.patch("requests.get", return_value=_fake_response(200)),
        ):
            assert bench.benchmark_api_endpoint("/api/whatsapp/health", "WhatsApp Health", iterations=2) is True

        entry = bench.results["api_endpoints"]["WhatsApp Health"]
        assert entry["average_response_time_ms"] == 35.0
        assert entry["min_response_time_ms"] == 20.0
        assert entry["max_response_time_ms"] == 50.0
        assert entry["median_response_time_ms"] == 35.0
        assert entry["success_rate"] == "100.0%"
        assert entry["iterations"] == 2
        assert entry["grade"] == "A+ (Excellent)"

    def test_mixed_status_codes_compute_partial_success_rate(self):
        bench = WhatsAppPerformanceBenchmark()
        deltas = [10.0, 10.02, 10.03, 10.05, 10.06, 10.07]  # 3 attempts, 2 with 200
        responses = [_fake_response(200), _fake_response(500), _fake_response(200)]
        with (
            mock.patch("time.time", side_effect=deltas),
            mock.patch("requests.get", side_effect=responses),
        ):
            assert bench.benchmark_api_endpoint("/x", "Mixed", iterations=3) is True

        entry = bench.results["api_endpoints"]["Mixed"]
        assert entry["success_rate"] == "66.7%"
        assert entry["average_response_time_ms"] == 15.0
        assert entry["min_response_time_ms"] == 10.0
        assert entry["max_response_time_ms"] == 20.0

    def test_all_failures_return_false_and_no_entry(self):
        bench = WhatsAppPerformanceBenchmark()
        with mock.patch("requests.get", return_value=_fake_response(503)):
            assert bench.benchmark_api_endpoint("/x", "Down", iterations=3) is False
        assert "Down" not in bench.results["api_endpoints"]

    def test_request_exception_returns_false(self):
        """RED for wave-117 bug: undefined `logger` NameError crashed this path."""
        bench = WhatsAppPerformanceBenchmark()
        with mock.patch("requests.get", side_effect=RuntimeError("connection refused")):
            assert bench.benchmark_api_endpoint("/x", "Err", iterations=3) is False
        assert "Err" not in bench.results["api_endpoints"]

    def test_metric_computation_failure_returns_false(self):
        """Outer try/except: stats failure after successful requests must return False."""
        bench = WhatsAppPerformanceBenchmark()
        with (
            mock.patch("time.time", side_effect=[1.0, 1.01]),
            mock.patch("requests.get", return_value=_fake_response(200)),
            mock.patch("statistics.mean", side_effect=ValueError("degenerate sample")),
        ):
            assert bench.benchmark_api_endpoint("/x", "Degenerate", iterations=1) is False
        assert "Degenerate" not in bench.results["api_endpoints"]

    def test_requests_called_with_base_url_timeout(self):
        bench = WhatsAppPerformanceBenchmark()
        with (
            mock.patch("time.time", side_effect=[1.0, 1.01]),
            mock.patch("requests.get", return_value=_fake_response(200)) as mock_get,
        ):
            bench.benchmark_api_endpoint("/api/whatsapp/health", "H", iterations=1)
        mock_get.assert_called_once_with("http://127.0.0.1:5058/api/whatsapp/health", timeout=5)


class TestOverallMetrics:
    def _with_entries(self):
        bench = WhatsAppPerformanceBenchmark()
        bench.results["api_endpoints"] = {
            "fast": {"average_response_time_ms": 50.0, "grade": "A+ (Excellent)"},
            "medium": {"average_response_time_ms": 150.0, "grade": "A (Good)"},
            "slow": {"average_response_time_ms": 400.0, "grade": "B (Fair)"},
        }
        return bench

    def test_computes_overall_metrics(self):
        bench = self._with_entries()
        bench.calculate_overall_metrics()
        metrics = bench.results["overall_metrics"]
        assert metrics["average_response_time_ms"] == 200.0
        assert metrics["fastest_endpoint_ms"] == 50.0
        assert metrics["slowest_endpoint_ms"] == 400.0
        assert metrics["performance_grade"] == "B (Fair)"

    def test_empty_endpoints_is_noop(self):
        bench = WhatsAppPerformanceBenchmark()
        bench.calculate_overall_metrics()
        assert bench.results["overall_metrics"] == {}

    def test_grade_prefix_uses_first_letter(self):
        bench = self._with_entries()
        bench.calculate_overall_metrics()
        assert "B" in bench.results["overall_metrics"]["performance_grade"]


class TestPrintResults:
    def test_prints_endpoint_and_target_met(self, capsys):
        bench = WhatsAppPerformanceBenchmark()
        bench.results["api_endpoints"] = {
            "WhatsApp Health": {
                "average_response_time_ms": 50.0,
                "min_response_time_ms": 40.0,
                "max_response_time_ms": 60.0,
                "median_response_time_ms": 50.0,
                "success_rate": "100.0%",
                "grade": "A+ (Excellent)",
            }
        }
        bench.results["overall_metrics"] = {
            "average_response_time_ms": 50.0,
            "fastest_endpoint_ms": 40.0,
            "slowest_endpoint_ms": 60.0,
            "performance_grade": "A+ (Excellent)",
        }
        bench.print_benchmark_results()
        out = capsys.readouterr().out
        assert "WhatsApp Health:" in out
        assert "Avg Response: 50.0ms" in out
        assert "TARGET MET" in out
        assert "Overall Grade: A+ (Excellent)" in out

    def test_target_not_met_when_over_200(self, capsys):
        bench = WhatsAppPerformanceBenchmark()
        bench.results["overall_metrics"] = {
            "average_response_time_ms": 250.0,
            "fastest_endpoint_ms": 200.0,
            "slowest_endpoint_ms": 300.0,
            "performance_grade": "B (Fair)",
        }
        bench.print_benchmark_results()
        assert "TARGET NOT MET" in capsys.readouterr().out


class TestComprehensive:
    def test_all_endpoints_success_returns_true(self):
        bench = WhatsAppPerformanceBenchmark()
        bench.results["api_endpoints"] = {
            "a": {
                "average_response_time_ms": 50.0,
                "min_response_time_ms": 40.0,
                "max_response_time_ms": 60.0,
                "median_response_time_ms": 50.0,
                "success_rate": "100.0%",
                "grade": "A+ (Excellent)",
            },
            "b": {
                "average_response_time_ms": 60.0,
                "min_response_time_ms": 50.0,
                "max_response_time_ms": 70.0,
                "median_response_time_ms": 60.0,
                "success_rate": "100.0%",
                "grade": "A+ (Excellent)",
            },
            "c": {
                "average_response_time_ms": 70.0,
                "min_response_time_ms": 60.0,
                "max_response_time_ms": 80.0,
                "median_response_time_ms": 70.0,
                "success_rate": "100.0%",
                "grade": "A+ (Excellent)",
            },
            "d": {
                "average_response_time_ms": 80.0,
                "min_response_time_ms": 70.0,
                "max_response_time_ms": 90.0,
                "median_response_time_ms": 80.0,
                "success_rate": "100.0%",
                "grade": "A+ (Excellent)",
            },
        }
        with mock.patch.object(bench, "benchmark_api_endpoint", return_value=True):
            assert bench.run_comprehensive_benchmark() is True
        assert bench.results["overall_metrics"]["average_response_time_ms"] == 65.0

    def test_partial_failure_returns_false(self, capsys):
        bench = WhatsAppPerformanceBenchmark()
        with mock.patch.object(bench, "benchmark_api_endpoint", side_effect=[True, False, True, True]):
            assert bench.run_comprehensive_benchmark() is False
        out = capsys.readouterr().out
        assert "WhatsApp Conversations: FAILED" in out
        assert "WhatsApp Health: COMPLETED" in out
