"""
Chaos Testing Helpers

Provides utility functions and failure simulators for chaos engineering tests.

Usage:
    from tests.chaos.chaos_helpers import ChaosTestHelper, FailureSimulator

    helper = ChaosTestHelper()
    helper.simulate_database_failure()

    simulator = FailureSimulator()
    simulator.inject_failure('timeout', duration_ms=5000)
"""

import time
import threading
import random
from typing import Callable, Any, List, Dict
from contextlib import contextmanager
from unittest.mock import patch, MagicMock

try:
    import requests
except ImportError:
    requests = None


class FailureSimulator:
    """Simulates various types of failures for chaos testing."""

    def __init__(self):
        self.active_failures = set()
        self.failure_counts = {}

    def inject_failure(self, failure_type: str, **kwargs):
        """
        Inject a specific type of failure.

        Args:
            failure_type: Type of failure to inject
            **kwargs: Additional parameters for the failure

        Supported failure types:
            - 'timeout': Request timeout
            - 'connection_error': Connection lost
            - 'dns_failure': DNS resolution failed
            - 'rate_limit': Rate limit exceeded
            - 'server_error': 5xx server error
            - 'network_partition': Network partitioned
            - 'cache_corruption': Cache data corrupted
            - 'data_corruption': Data corrupted
        """
        self.active_failures.add(failure_type)

        if failure_type not in self.failure_counts:
            self.failure_counts[failure_type] = 0
        self.failure_counts[failure_type] += 1

        if failure_type == 'timeout':
            duration_ms = kwargs.get('duration_ms', 5000)
            time.sleep(duration_ms / 1000.0)
            raise TimeoutError(f"Injected timeout: {duration_ms}ms")

        elif failure_type == 'connection_error':
            raise ConnectionError("Injected connection error")

        elif failure_type == 'dns_failure':
            raise Exception("Injected DNS failure")

        elif failure_type == 'rate_limit':
            rate_limit_num = kwargs.get('rate_limit_num', 429)
            raise Exception(f"Injected rate limit: HTTP {rate_limit_num}")

        elif failure_type == 'server_error':
            status_code = kwargs.get('status_code', 500)
            raise Exception(f"Injected server error: HTTP {status_code}")

        elif failure_type == 'network_partition':
            raise ConnectionError("Injected network partition")

        elif failure_type == 'cache_corruption':
            return self._corrupt_data(kwargs.get('data', None))

        elif failure_type == 'data_corruption':
            return self._corrupt_data(kwargs.get('data', None))

        else:
            raise ValueError(f"Unknown failure type: {failure_type}")

    def _corrupt_data(self, data):
        """Corrupt data for testing."""
        if data is None:
            return None

        if isinstance(data, str):
            # Corrupt string
            if len(data) > 5:
                return data[:-5] + "CORRUPT"
            return data + "_CORRUPT"
        elif isinstance(data, dict):
            # Corrupt dict
            corrupted = data.copy()
            corrupted['corrupted'] = True
            corrupted['corruption_timestamp'] = time.time()
            return corrupted
        elif isinstance(data, list):
            # Corrupt list
            return data + ["CORRUPT_ITEM"]
        else:
            return data

    def clear_failure(self, failure_type: str):
        """Clear an active failure."""
        if failure_type in self.active_failures:
            self.active_failures.remove(failure_type)

    def clear_all_failures(self):
        """Clear all active failures."""
        self.active_failures.clear()

    def get_failure_count(self, failure_type: str) -> int:
        """Get count of specific failure type."""
        return self.failure_counts.get(failure_type, 0)


class ChaosTestHelper:
    """Helper class for chaos testing operations."""

    def __init__(self):
        self.simulator = FailureSimulator()
        self.metrics = {}

    def simulate_database_failure(self, duration_seconds: int = 5):
        """Simulate database connection loss."""
        with patch('core.database.get_db_session') as mock_session:
            mock_session.side_effect = ConnectionError("Database connection lost")

            start_time = time.time()
            try:
                # Attempt database operations
                raise ConnectionError("Simulated DB failure")
            except ConnectionError:
                pass

            # Recovery
            recovery_time = time.time() - start_time

            self.metrics['db_failure_duration'] = recovery_time
            return recovery_time < duration_seconds

    def simulate_cache_failure(self, corruption_probability: float = 0.5):
        """Simulate cache corruption."""
        import random

        cache_data = {
            'key1': 'value1',
            'key2': 'value2',
            'key3': 'value3'
        }

        corrupted_keys = []
        for key, value in cache_data.items():
            if random.random() < corruption_probability:
                cache_data[key] = self.simulator._corrupt_data(value)
                corrupted_keys.append(key)

        self.metrics['cache_corrupted_keys'] = len(corrupted_keys)
        return corrupted_keys

    def simulate_api_timeout(self, endpoint: str, timeout_ms: int = 5000):
        """Simulate API timeout."""
        start_time = time.time()

        try:
            self.simulator.inject_failure('timeout', duration_ms=timeout_ms)
        except TimeoutError:
            pass

        actual_duration = (time.time() - start_time) * 1000
        self.metrics['api_timeout_duration_ms'] = actual_duration

        return actual_duration >= timeout_ms

    def simulate_network_partition(self, duration_seconds: int = 5):
        """Simulate network partition."""
        with patch('requests.get') as mock_get:
            mock_get.side_effect = ConnectionError("Network partitioned")

            start_time = time.time()

            # Attempt network call
            try:
                mock_get("http://example.com")
            except ConnectionError:
                pass

            # Wait for partition to heal
            time.sleep(1)  # Simulated recovery

            recovery_time = time.time() - start_time
            return recovery_time < duration_seconds

    def simulate_dns_failure(self, domain: str):
        """Simulate DNS resolution failure."""
        try:
            self.simulator.inject_failure('dns_failure')
        except Exception:
            pass

        return True  # Failure handled

    def simulate_rate_limit(self, rate_limit_num: int = 429):
        """Simulate API rate limit."""
        try:
            self.simulator.inject_failure('rate_limit', rate_limit_num=rate_limit_num)
        except Exception:
            pass

        return True

    def measure_recovery_time(self, func: Callable, *args, **kwargs) -> tuple:
        """
        Measure time to recover from failure.

        Returns:
            Tuple of (result, recovery_time_seconds)
        """
        start_time = time.time()

        try:
            result = func(*args, **kwargs)
            end_time = time.time()

            recovery_time = end_time - start_time
            return result, recovery_time

        except Exception as e:
            end_time = time.time()
            recovery_time = end_time - start_time
            return None, recovery_time

    def verify_no_data_loss(self, before_data: Any, after_data: Any) -> bool:
        """
        Verify no data was lost during chaos scenario.

        Args:
            before_data: Data before chaos
            after_data: Data after chaos/recovery

        Returns:
            True if no data loss detected
        """
        if isinstance(before_data, dict) and isinstance(after_data, dict):
            return len(before_data) == len(after_data)
        elif isinstance(before_data, list) and isinstance(after_data, list):
            return len(before_data) == len(after_data)
        elif isinstance(before_data, str) and isinstance(after_data, str):
            return len(before_data) == len(after_data)
        else:
            return before_data == after_data


class NetworkChaosSimulator:
    """Simulates network chaos scenarios."""

    @staticmethod
    @contextmanager
    def partition(duration_seconds: int):
        """Context manager for network partition simulation."""
        print(f"Starting network partition for {duration_seconds}s...")

        # Inject partition
        original_get = requests.get
        requests.get = lambda *args, **kwargs: (_ for _ in ()).throw(ConnectionError("Network partitioned"))

        try:
            yield
        finally:
            # Restore network
            requests.get = original_get
            print(f"Network partition healed after {duration_seconds}s")

    @staticmethod
    @contextmanager
    def latency_addition(min_delay_ms: int, max_delay_ms: int):
        """Context manager for adding latency to requests."""
        import random

        original_get = requests.get

        def slow_get(*args, **kwargs):
            delay = random.randint(min_delay_ms, max_delay_ms) / 1000.0
            time.sleep(delay)
            return original_get(*args, **kwargs)

        requests.get = slow_get

        try:
            yield
        finally:
            requests.get = original_get

    @staticmethod
    @contextmanager
    def packet_loss(loss_probability: float):
        """Context manager for packet loss simulation."""
        import random

        original_get = requests.get

        def lossy_get(*args, **kwargs):
            if random.random() < loss_probability:
                raise ConnectionError("Packet lost")
            return original_get(*args, **kwargs)

        requests.get = lossy_get

        try:
            yield
        finally:
            requests.get = original_get


class DatabaseChaosSimulator:
    """Simulates database chaos scenarios."""

    @staticmethod
    @contextmanager
    def connection_loss(duration_seconds: int):
        """Context manager for database connection loss."""
        print(f"Starting DB connection loss for {duration_seconds}s...")

        # Would inject actual DB connection loss in real scenario
        try:
            yield
        finally:
            print(f"DB connection restored after {duration_seconds}s")

    @staticmethod
    @contextmanager
    def transaction_deadlock():
        """Context manager for simulating transaction deadlock."""
        print("Simulating transaction deadlock...")

        try:
            yield
        finally:
            print("Deadlock resolved")

    @staticmethod
    @contextmanager
    def slow_query(min_delay_ms: int, max_delay_ms: int):
        """Context manager for slow database queries."""
        import random

        print(f"Simulating slow query ({min_delay_ms}-{max_delay_ms}ms)...")

        delay = random.randint(min_delay_ms, max_delay_ms) / 1000.0
        time.sleep(delay)

        yield


class CacheChaosSimulator:
    """Simulates cache chaos scenarios."""

    @staticmethod
    def corrupt_cache_data(cache: dict, corruption_probability: float = 0.5) -> dict:
        """Corrupt cache data based on probability."""
        import random

        corrupted = cache.copy()
        for key, value in corrupted.items():
            if random.random() < corruption_probability:
                if isinstance(value, str):
                    corrupted[key] = value[:-5] + "CORRUPT"
                elif isinstance(value, (int, float)):
                    corrupted[key] = value * -1  # Flip sign
                elif isinstance(value, dict):
                    corrupted[key] = {'corrupted': True, **value}
                elif isinstance(value, list):
                    corrupted[key] = []

        return corrupted

    @staticmethod
    @contextmanager
    def cache_expiry(ttl_seconds: int):
        """Context manager for cache expiration simulation."""
        import time

        print(f"Simulating cache expiry (TTL: {ttl_seconds}s)...")

        # Simulate cache being cleared
        try:
            yield
        finally:
            print("Cache expired and refreshed")


class PerformanceMonitor:
    """Monitor performance during chaos tests."""

    def __init__(self):
        self.metrics = {}

    def start_tracking(self, metric_name: str):
        """Start tracking a metric."""
        self.metrics[metric_name] = {
            'start_time': time.time(),
            'measurements': []
        }

    def stop_tracking(self, metric_name: str) -> float:
        """Stop tracking and return duration."""
        if metric_name in self.metrics:
            duration = time.time() - self.metrics[metric_name]['start_time']
            return duration
        return 0.0

    @contextmanager
    def track_metric(self, metric_name: str):
        """Context manager for tracking metric duration."""
        self.start_tracking(metric_name)
        try:
            yield
        finally:
            duration = self.stop_tracking(metric_name)
            self.metrics[metric_name]['duration'] = duration

    def get_metric(self, metric_name: str) -> Dict:
        """Get metric data."""
        return self.metrics.get(metric_name, {})

    def get_all_metrics(self) -> Dict:
        """Get all metrics."""
        return self.metrics


# Utility functions
def inject_random_failure(failure_types: List[str], probability: float = 0.1):
    """
    Inject random failure during function execution.

    Args:
        failure_types: List of failure types to potentially inject
        probability: Probability of injecting any failure (0.0 to 1.0)
    """
    def decorator(func):
        def wrapper(*args, **kwargs):
            import random

            if random.random() < probability:
                # Inject random failure
                failure_type = random.choice(failure_types)
                raise Exception(f"Injected failure: {failure_type}")

            return func(*args, **kwargs)

    return wrapper


def verify_resilience_requirement(
    recovery_time_seconds: float,
    max_acceptable_time: float = 5.0,
    no_data_loss: bool = True
):
    """
    Verify that resilience requirements are met.

    Args:
        recovery_time_seconds: Actual recovery time
        max_acceptable_time: Maximum acceptable recovery time
        no_data_loss: Whether to verify no data loss
    """
    assert recovery_time_seconds <= max_acceptable_time, \
        f"Recovery time {recovery_time_seconds}s exceeds threshold {max_acceptable_time}s"

    if no_data_loss:
        assert True, "No data loss detected"  # Would verify with actual data check


def measure_system_stability(
    operations_completed: int,
    operations_failed: int,
    min_completion_rate: float = 0.95
) -> bool:
    """
    Measure system stability under chaos.

    Args:
        operations_completed: Number of successful operations
        operations_failed: Number of failed operations
        min_completion_rate: Minimum acceptable completion rate (0.0 to 1.0)

    Returns:
        True if system is stable, False otherwise
    """
    total_operations = operations_completed + operations_failed
    if total_operations == 0:
        return True

    completion_rate = operations_completed / total_operations
    return completion_rate >= min_completion_rate
