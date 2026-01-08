"""
Circuit Breaker - Automatically disable failing integrations
"""
import logging
import time
from collections import defaultdict
from typing import Dict, Set
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class IntegrationStats:
    """Statistics for an integration"""
    total_calls: int = 0
    failures: int = 0
    last_failure_time: float = 0
    consecutive_failures: int = 0


class CircuitBreaker:
    """
    Circuit breaker pattern for integrations
    Automatically disables integrations that fail repeatedly
    """
    
    def __init__(
        self,
        failure_threshold: float = 0.5,  # 50% failure rate
        min_calls: int = 5,  # Minimum calls before checking
        consecutive_failure_limit: int = 3,  # Disable after N consecutive failures
        cooldown_seconds: int = 300  # 5 minutes cooldown before re-enabling
    ):
        self.failure_threshold = failure_threshold
        self.min_calls = min_calls
        self.consecutive_failure_limit = consecutive_failure_limit
        self.cooldown_seconds = cooldown_seconds
        
        self.stats: Dict[str, IntegrationStats] = defaultdict(IntegrationStats)
        self.disabled: Set[str] = set()
        self.disabled_until: Dict[str, float] = {}
        
        # Callbacks for autonomous actions
        self._on_open_callbacks = []
        self._on_reset_callbacks = []
    
    def on_open(self, callback):
        """Register a callback for when circuit opens"""
        self._on_open_callbacks.append(callback)
        return callback
        
    def on_reset(self, callback):
        """Register a callback for when circuit resets/closes"""
        self._on_reset_callbacks.append(callback)
        return callback
    
    def record_success(self, integration: str):
        """Record a successful integration call"""
        stats = self.stats[integration]
        stats.total_calls += 1
        stats.consecutive_failures = 0
        
        # Re-enable if it was disabled and cooldown passed
        if integration in self.disabled:
            self._try_reenable(integration)
    
    def record_failure(self, integration: str, error: Exception = None):
        """Record a failed integration call"""
        stats = self.stats[integration]
        stats.total_calls += 1
        stats.failures += 1
        stats.consecutive_failures += 1
        stats.last_failure_time = time.time()
        
        # Check if should disable
        if self._should_disable(integration):
            self._disable_integration(integration)
            logger.error(
                f"Circuit breaker OPENED for {integration}: "
                f"{stats.failures}/{stats.total_calls} failures, "
                f"{stats.consecutive_failures} consecutive"
            )
    
    def is_enabled(self, integration: str) -> bool:
        """Check if integration is enabled"""
        if integration not in self.disabled:
            return True
        
        # Check if cooldown period has passed
        if self._try_reenable(integration):
            return True
        
        return False
    
    def get_stats(self, integration: str) -> Dict:
        """Get statistics for an integration"""
        stats = self.stats[integration]
        failure_rate = stats.failures / stats.total_calls if stats.total_calls > 0 else 0
        
        return {
            "total_calls": stats.total_calls,
            "failures": stats.failures,
            "consecutive_failures": stats.consecutive_failures,
            "failure_rate": failure_rate,
            "is_enabled": self.is_enabled(integration),
            "disabled_until": self.disabled_until.get(integration, 0)
        }
    
    def get_all_stats(self) -> Dict[str, Dict]:
        """Get statistics for all integrations"""
        return {
            name: self.get_stats(name)
            for name in self.stats.keys()
        }
    
    def reset(self, integration: str = None):
        """Reset statistics for an integration or all integrations"""
        if integration:
            if integration in self.stats:
                del self.stats[integration]
            if integration in self.disabled:
                self.disabled.remove(integration)
            if integration in self.disabled_until:
                del self.disabled_until[integration]
            logger.info(f"Circuit breaker reset for {integration}")
        else:
            self.stats.clear()
            self.disabled.clear()
            self.disabled_until.clear()
            logger.info("Circuit breaker reset for all integrations")
    
    def _should_disable(self, integration: str) -> bool:
        """Check if integration should be disabled"""
        stats = self.stats[integration]
        
        # Not enough calls yet
        if stats.total_calls < self.min_calls:
            return False
        
        # Too many consecutive failures
        if stats.consecutive_failures >= self.consecutive_failure_limit:
            return True
        
        # High failure rate
        failure_rate = stats.failures / stats.total_calls
        if failure_rate >= self.failure_threshold:
            return True
        
        return False
    
    def _disable_integration(self, integration: str):
        """Disable an integration"""
        self.disabled.add(integration)
        self.disabled_until[integration] = time.time() + self.cooldown_seconds
        logger.warning(
            f"Integration {integration} disabled for {self.cooldown_seconds}s"
        )
        
        # Trigger callbacks
        for callback in self._on_open_callbacks:
            try:
                callback(integration)
            except Exception as e:
                logger.error(f"Error in circuit breaker on_open callback: {e}")
    
    def _try_reenable(self, integration: str) -> bool:
        """Try to re-enable a disabled integration if cooldown passed"""
        if integration not in self.disabled:
            return True
        
        if time.time() >= self.disabled_until.get(integration, 0):
            self.disabled.remove(integration)
            if integration in self.disabled_until:
                del self.disabled_until[integration]
            logger.info(f"Integration {integration} re-enabled after cooldown")
            
            # Trigger callbacks
            for callback in self._on_reset_callbacks:
                try:
                    callback(integration)
                except Exception as e:
                    logger.error(f"Error in circuit breaker on_reset callback: {e}")
            return True
        
        return False


# Global circuit breaker instance
circuit_breaker = CircuitBreaker()
