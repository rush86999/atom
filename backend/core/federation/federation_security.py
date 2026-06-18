"""
Federation Security Service

Implements advanced security features for federation:
- Mutual TLS (mTLS) authentication
- Credential rotation and lifecycle management
- Anomaly detection for traffic patterns
- Federation security monitoring

Based on 2025-2026 research:
- Zero-Trust Identity Framework (arXiv:2505.19301v2)
- Multi-Tenant AI Systems Guide
"""

import hashlib
import json
import logging
import os
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Set, Tuple, Deque
from collections import defaultdict, deque
from statistics import mean, stdev

logger = logging.getLogger(__name__)


# ============================================================================
# Enums and Configuration
# ============================================================================

class TLSVersion(Enum):
    """Supported TLS versions"""
    TLS_1_2 = "TLSv1.2"
    TLS_1_3 = "TLSv1.3"


class AnomalyType(Enum):
    """Types of anomalies"""
    TRAFFIC_SPIKE = "traffic_spike"
    UNUSUAL_SOURCE = "unusual_source"
    FAILED_AUTH_RATE = "failed_auth_rate"
    LATENCY_SPIKE = "latency_spike"
    LARGE_REQUEST = "large_request"
    RATE_EXCEEDED = "rate_exceeded"
    GEOPHYSICALLY_IMPROBABLE = "geophysically_improbable"


class CredentialStatus(Enum):
    """Status of credentials"""
    ACTIVE = "active"
    ROTATING = "rotating"
    EXPIRED = "expired"
    REVOKED = "revoked"
    COMPROMISED = "compromised"


@dataclass
class MutualTLSConfig:
    """Configuration for mutual TLS"""
    # Certificates
    cert_path: str = ""
    key_path: str = ""
    ca_path: str = ""
    cert_chain_path: str = ""

    # TLS settings
    min_version: TLSVersion = TLSVersion.TLS_1_2
    max_version: TLSVersion = TLSVersion.TLS_1_3
    cipher_suites: List[str] = field(default_factory=lambda: [
        "TLS_AES_128_GCM_SHA256",
        "TLS_AES_256_GCM_SHA384",
        "TLS_CHACHA20_POLY1305_SHA256"
    ])

    # Verification
    verify_client: bool = True
    verify_depth: int = 3
    check_hostname: bool = True

    # Session
    session_timeout: int = 3600  # seconds
    session_tickets: bool = True


@dataclass
class CredentialRotationConfig:
    """Configuration for credential rotation"""
    # Rotation schedule
    auto_rotate: bool = True
    rotation_interval_days: int = 90
    warning_days: int = 30

    # Grace period
    grace_period_days: int = 7

    # Emergency rotation
    force_rotation_on_compromise: bool = True


@dataclass
class AnomalyDetectionConfig:
    """Configuration for anomaly detection"""
    # Detection thresholds
    enable_traffic_analysis: bool = True
    enable_rate_analysis: bool = True
    enable_latency_analysis: bool = True
    enable_geographic_analysis: bool = True

    # Thresholds
    traffic_spike_multiplier: float = 3.0  # x times normal
    failed_auth_threshold: float = 0.1  # 10% failure rate
    latency_spike_multiplier: float = 2.0
    max_request_size_mb: float = 100.0

    # Learning
    learning_window_minutes: int = 60
    min_samples_for_baseline: int = 100

    # Response
    auto_block_on_anomaly: bool = False
    alert_on_anomaly: bool = True


# ============================================================================
# Data Classes
# ============================================================================

@dataclass
class TLSConnection:
    """Record of a TLS connection"""
    connection_id: str = ""
    source_instance: str = ""
    source_ip: str = ""
    cipher_suite: str = ""
    protocol_version: str = ""
    established_at: datetime = field(default_factory=datetime.now)
    last_activity: datetime = field(default_factory=datetime.now)
    bytes_sent: int = 0
    bytes_received: int = 0
    is_active: bool = True


@dataclass
class CredentialRecord:
    """Record of a credential"""
    credential_id: str = ""
    credential_type: str = ""  # federation_key, api_token, certificate
    instance_id: str = ""

    # Lifecycle
    created_at: datetime = field(default_factory=datetime.now)
    expires_at: Optional[datetime] = None
    rotated_at: Optional[datetime] = None
    status: CredentialStatus = CredentialStatus.ACTIVE

    # Rotation
    rotation_count: int = 0
    next_rotation: Optional[datetime] = None

    # Security
    compromised_at: Optional[datetime] = None
    compromise_reason: Optional[str] = None


@dataclass
class AnomalyAlert:
    """An anomaly detection alert"""
    alert_id: str = ""
    anomaly_type: AnomalyType = AnomalyType.TRAFFIC_SPIKE
    severity: str = "medium"  # low, medium, high, critical
    description: str = ""

    # Context
    source_instance: str = ""
    source_ip: str = ""
    metric_value: float = 0.0
    baseline_value: float = 0.0
    deviation: float = 0.0  # standard deviations

    # Timestamps
    detected_at: datetime = field(default_factory=datetime.now)
    resolved_at: Optional[datetime] = None

    # Actions
    actions_taken: List[str] = field(default_factory=list)
    is_resolved: bool = False


@dataclass
class TrafficMetrics:
    """Traffic metrics for anomaly detection"""
    timestamp: datetime = field(default_factory=datetime.now)
    request_count: int = 0
    failed_auth_count: int = 0
    avg_latency_ms: float = 0.0
    total_bytes: int = 0
    unique_sources: int = 0
    error_rate: float = 0.0


# ============================================================================
# Mutual TLS Manager
# ============================================================================

class MutualTLSManager:
    """Manages mutual TLS authentication for federation"""

    def __init__(self, config: Optional[MutualTLSConfig] = None):
        self.config = config or MutualTLSConfig()
        self._connections: Dict[str, TLSConnection] = {}
        self._handshake_failures: Dict[str, int] = defaultdict(int)

    def create_connection(
        self,
        source_instance: str,
        source_ip: str,
        cipher_suite: str,
        protocol_version: str
    ) -> TLSConnection:
        """Record a new TLS connection"""
        conn_id = hashlib.sha256(f"{source_instance}:{datetime.now().isoformat()}".encode()).hexdigest()[:16]

        conn = TLSConnection(
            connection_id=conn_id,
            source_instance=source_instance,
            source_ip=source_ip,
            cipher_suite=cipher_suite,
            protocol_version=protocol_version
        )

        self._connections[conn_id] = conn
        logger.debug(f"Created TLS connection: {conn_id} for {source_instance}")
        return conn

    def get_active_connections(self, instance_id: Optional[str] = None) -> List[TLSConnection]:
        """Get active TLS connections"""
        connections = [c for c in self._connections.values() if c.is_active]
        if instance_id:
            connections = [c for c in connections if c.source_instance == instance_id]
        return connections

    def close_connection(self, connection_id: str) -> bool:
        """Close a TLS connection"""
        if connection_id in self._connections:
            self._connections[connection_id].is_active = False
            logger.debug(f"Closed TLS connection: {connection_id}")
            return True
        return False

    def record_handshake_failure(self, source_ip: str) -> None:
        """Record a TLS handshake failure"""
        self._handshake_failures[source_ip] += 1
        logger.warning(f"TLS handshake failure from {source_ip} (count: {self._handshake_failures[source_ip]})")

    def get_handshake_failures(self, source_ip: Optional[str] = None) -> Dict[str, int]:
        """Get handshake failure counts"""
        if source_ip:
            return {source_ip: self._handshake_failures.get(source_ip, 0)}
        return dict(self._handshake_failures)

    def cleanup_stale_connections(self, timeout_seconds: int = 3600) -> int:
        """Clean up stale connections"""
        cutoff = datetime.now() - timedelta(seconds=timeout_seconds)
        cleaned = 0

        for conn_id, conn in self._connections.items():
            if conn.is_active and conn.last_activity < cutoff:
                conn.is_active = False
                cleaned += 1

        if cleaned > 0:
            logger.info(f"Cleaned up {cleaned} stale TLS connections")

        return cleaned


# ============================================================================
# Credential Rotation Manager
# ============================================================================

class CredentialRotationManager:
    """Manages credential lifecycle and rotation"""

    def __init__(self, config: Optional[CredentialRotationConfig] = None):
        self.config = config or CredentialRotationConfig()
        self._credentials: Dict[str, CredentialRecord] = {}

    def register_credential(
        self,
        credential_id: str,
        credential_type: str,
        instance_id: str,
        expiry_days: Optional[int] = None
    ) -> CredentialRecord:
        """Register a new credential"""
        # Calculate expiration
        if expiry_days:
            expires_at = datetime.now() + timedelta(days=expiry_days)
        else:
            expires_at = None

        # Calculate next rotation
        if self.config.auto_rotate:
            next_rotation = datetime.now() + timedelta(days=self.config.rotation_interval_days)
        else:
            next_rotation = None

        record = CredentialRecord(
            credential_id=credential_id,
            credential_type=credential_type,
            instance_id=instance_id,
            expires_at=expires_at,
            next_rotation=next_rotation
        )

        self._credentials[credential_id] = record
        logger.info(f"Registered credential: {credential_id} for {instance_id}")
        return record

    def check_rotation_needed(self, credential_id: str) -> bool:
        """Check if credential needs rotation"""
        if credential_id not in self._credentials:
            return False

        record = self._credentials[credential_id]

        # Check compromise
        if record.status == CredentialStatus.COMPROMISED:
            return True

        # Check rotation schedule
        if record.next_rotation and datetime.now() >= record.next_rotation:
            return True

        # Check expiration warning
        if record.expires_at:
            warning_date = record.expires_at - timedelta(days=self.config.warning_days)
            if datetime.now() >= warning_date:
                return True

        return False

    def rotate_credential(
        self,
        credential_id: str,
        new_credential_id: str
    ) -> CredentialRecord:
        """Rotate a credential"""
        if credential_id not in self._credentials:
            raise ValueError(f"Credential not found: {credential_id}")

        old_record = self._credentials[credential_id]

        # Create new record
        new_record = CredentialRecord(
            credential_id=new_credential_id,
            credential_type=old_record.credential_type,
            instance_id=old_record.instance_id,
            expires_at=datetime.now() + timedelta(days=self.config.rotation_interval_days) if old_record.expires_at else None,
            rotated_at=datetime.now(),
            status=CredentialStatus.ACTIVE,
            rotation_count=old_record.rotation_count + 1,
            next_rotation=datetime.now() + timedelta(days=self.config.rotation_interval_days) if self.config.auto_rotate else None
        )

        # Mark old as rotating
        old_record.status = CredentialStatus.ROTATING

        self._credentials[new_credential_id] = new_record
        logger.info(f"Rotated credential: {credential_id} -> {new_credential_id}")
        return new_record

    def revoke_credential(
        self,
        credential_id: str,
        reason: Optional[str] = None
    ) -> bool:
        """Revoke a credential"""
        if credential_id not in self._credentials:
            return False

        record = self._credentials[credential_id]
        record.status = CredentialStatus.REVOKED
        record.compromised_at = datetime.now()
        record.compromised_reason = reason

        logger.warning(f"Revoked credential: {credential_id} - {reason}")
        return True

    def get_credentials_due_for_rotation(self) -> List[str]:
        """Get list of credentials that need rotation"""
        return [
            cred_id for cred_id in self._credentials
            if self.check_rotation_needed(cred_id)
        ]

    def get_statistics(self) -> Dict[str, Any]:
        """Get credential statistics"""
        status_counts = defaultdict(int)
        for record in self._credentials.values():
            status_counts[record.status.value] += 1

        return {
            "total_credentials": len(self._credentials),
            "status_counts": dict(status_counts),
            "due_for_rotation": len(self.get_credentials_due_for_rotation()),
            "auto_rotate_enabled": self.config.auto_rotate,
            "rotation_interval_days": self.config.rotation_interval_days
        }


# ============================================================================
# Anomaly Detector
# ============================================================================

class AnomalyDetector:
    """Detects anomalies in federation traffic patterns"""

    def __init__(self, config: Optional[AnomalyDetectionConfig] = None):
        self.config = config or AnomalyDetectionConfig()

        # Metrics history
        self._metrics_history: Deque[TrafficMetrics] = deque(maxlen=10000)
        self._metrics_by_source: Dict[str, Deque[TrafficMetrics]] = defaultdict(lambda: deque(maxlen=1000))

        # Baselines
        self._baselines: Dict[str, float] = {}
        self._baseline_samples: int = 0

        # Alerts
        self._alerts: List[AnomalyAlert] = []

        # Geographic data (simplified - in production use GeoIP)
        self._geo_db: Dict[str, str] = {}  # IP -> country

    def record_traffic(
        self,
        source_instance: str,
        source_ip: str,
        request_count: int = 1,
        failed_auth: int = 0,
        latency_ms: float = 0.0,
        bytes_sent: int = 0,
        bytes_received: int = 0
    ) -> TrafficMetrics:
        """Record traffic metrics"""
        metrics = TrafficMetrics(
            request_count=request_count,
            failed_auth_count=failed_auth,
            avg_latency_ms=latency_ms,
            total_bytes=bytes_sent + bytes_received,
            error_rate=failed_auth / request_count if request_count > 0 else 0
        )

        self._metrics_history.append(metrics)
        self._metrics_by_source[source_instance].append(metrics)

        # Update baseline if we have enough samples
        self._update_baseline()

        # Check for anomalies
        if self._baseline_samples >= self.config.min_samples_for_baseline:
            self._check_anomalies(source_instance, source_ip, metrics)

        return metrics

    def _update_baseline(self) -> None:
        """Update baseline metrics"""
        window_end = datetime.now()
        window_start = window_end - timedelta(minutes=self.config.learning_window_minutes)

        # Get recent metrics
        recent = [
            m for m in self._metrics_history
            if m.timestamp >= window_start
        ]

        if len(recent) < self.config.min_samples_for_baseline:
            return

        # Calculate baselines
        self._baselines = {
            "request_count": mean(m.request_count for m in recent),
            "failed_auth_count": mean(m.failed_auth_count for m in recent),
            "avg_latency_ms": mean(m.avg_latency_ms for m in recent),
            "total_bytes": mean(m.total_bytes for m in recent),
            "error_rate": mean(m.error_rate for m in recent)
        }
        self._baseline_samples = len(recent)

    def _check_anomalies(
        self,
        source_instance: str,
        source_ip: str,
        metrics: TrafficMetrics
    ) -> List[AnomalyAlert]:
        """Check for anomalies in current metrics"""
        alerts = []

        # Traffic spike check
        if self.config.enable_traffic_analysis:
            baseline_count = self._baselines.get("request_count", 0)
            if baseline_count > 0 and metrics.request_count > baseline_count * self.config.traffic_spike_multiplier:
                alert = self._create_alert(
                    AnomalyType.TRAFFIC_SPIKE,
                    source_instance,
                    metrics.request_count,
                    baseline_count,
                    "high"
                )
                alerts.append(alert)

        # Failed auth rate check
        if self.config.enable_rate_analysis:
            baseline_error = self._baselines.get("error_rate", 0)
            if metrics.error_rate > max(self.config.failed_auth_threshold, baseline_error * 2):
                alert = self._create_alert(
                    AnomalyType.FAILED_AUTH_RATE,
                    source_instance,
                    metrics.error_rate,
                    baseline_error,
                    "medium"
                )
                alerts.append(alert)

        # Latency spike check
        if self.config.enable_latency_analysis and metrics.avg_latency_ms > 0:
            baseline_latency = self._baselines.get("avg_latency_ms", 0)
            if baseline_latency > 0 and metrics.avg_latency_ms > baseline_latency * self.config.latency_spike_multiplier:
                alert = self._create_alert(
                    AnomalyType.LATENCY_SPIKE,
                    source_instance,
                    metrics.avg_latency_ms,
                    baseline_latency,
                    "medium"
                )
                alerts.append(alert)

        # Large request check
        if metrics.total_bytes > self.config.max_request_size_mb * 1024 * 1024:
            alert = self._create_alert(
                AnomalyType.LARGE_REQUEST,
                source_instance,
                metrics.total_bytes / (1024 * 1024),
                self.config.max_request_size_mb,
                "medium"
            )
            alerts.append(alert)

        # Store alerts
        for alert in alerts:
            self._alerts.append(alert)
            logger.warning(f"Anomaly detected: {alert.anomaly_type.value} from {source_instance}")

        return alerts

    def _create_alert(
        self,
        anomaly_type: AnomalyType,
        source_instance: str,
        metric_value: float,
        baseline_value: float,
        severity: str
    ) -> AnomalyAlert:
        """Create an anomaly alert"""
        alert_id = hashlib.sha256(f"{anomaly_type.value}:{source_instance}:{datetime.now().isoformat()}".encode()).hexdigest()[:16]

        # Calculate deviation (standard deviations from baseline)
        if baseline_value > 0:
            deviation = abs((metric_value - baseline_value) / baseline_value)
        else:
            deviation = 0.0

        return AnomalyAlert(
            alert_id=alert_id,
            anomaly_type=anomaly_type,
            severity=severity,
            description=f"{anomaly_type.value.replace('_', ' ').title()}: {metric_value:.2f} vs baseline {baseline_value:.2f}",
            source_instance=source_instance,
            metric_value=metric_value,
            baseline_value=baseline_value,
            deviation=deviation
        )

    def get_recent_alerts(
        self,
        since: Optional[datetime] = None,
        limit: int = 100
    ) -> List[AnomalyAlert]:
        """Get recent anomaly alerts"""
        if since:
            return [a for a in self._alerts if a.detected_at >= since][:limit]
        return self._alerts[-limit:]

    def resolve_alert(self, alert_id: str) -> bool:
        """Mark an alert as resolved"""
        for alert in self._alerts:
            if alert.alert_id == alert_id and not alert.is_resolved:
                alert.is_resolved = True
                alert.resolved_at = datetime.now()
                logger.info(f"Resolved anomaly alert: {alert_id}")
                return True
        return False

    def get_statistics(self) -> Dict[str, Any]:
        """Get anomaly detection statistics"""
        unresolved = [a for a in self._alerts if not a.is_resolved]

        return {
            "total_alerts": len(self._alerts),
            "unresolved_alerts": len(unresolved),
            "baseline_samples": self._baseline_samples,
            "baselines": self._baselines,
            "config": {
                "traffic_spike_multiplier": self.config.traffic_spike_multiplier,
                "failed_auth_threshold": self.config.failed_auth_threshold,
                "latency_spike_multiplier": self.config.latency_spike_multiplier,
                "auto_block_on_anomaly": self.config.auto_block_on_anomaly
            }
        }


# ============================================================================
# Federation Security Service
# ============================================================================

class FederationSecurityService:
    """
    Main service for federation security.

    Coordinates:
    - Mutual TLS management
    - Credential rotation
    - Anomaly detection
    """

    def __init__(
        self,
        tls_config: Optional[MutualTLSConfig] = None,
        rotation_config: Optional[CredentialRotationConfig] = None,
        anomaly_config: Optional[AnomalyDetectionConfig] = None
    ):
        self.tls = MutualTLSManager(tls_config)
        self.rotation = CredentialRotationManager(rotation_config)
        self.anomaly = AnomalyDetector(anomaly_config)

    def get_health_status(self) -> Dict[str, Any]:
        """Get overall security health status"""
        active_conns = len(self.tls.get_active_connections())
        due_rotation = len(self.rotation.get_credentials_due_for_rotation())
        recent_alerts = len(self.anomaly.get_recent_alerts(since=datetime.now() - timedelta(hours=1)))

        # Determine health
        health = "healthy"
        if recent_alerts > 10:
            health = "degraded"
        if recent_alerts > 50:
            health = "unhealthy"

        return {
            "status": health,
            "active_tls_connections": active_conns,
            "credentials_due_for_rotation": due_rotation,
            "recent_anomaly_alerts": recent_alerts,
            "services": {
                "tls": "active",
                "rotation": "active",
                "anomaly_detection": "active"
            }
        }

    def get_statistics(self) -> Dict[str, Any]:
        """Get comprehensive statistics"""
        return {
            "tls": {
                "active_connections": len(self.tls.get_active_connections()),
                "handshake_failures": len(self.tls.get_handshake_failures())
            },
            "rotation": self.rotation.get_statistics(),
            "anomaly": self.anomaly.get_statistics()
        }


# ============================================================================
# Factory
# ============================================================================

_federation_security_instance: Optional[FederationSecurityService] = None


def get_federation_security(
    tls_config: Optional[MutualTLSConfig] = None,
    rotation_config: Optional[CredentialRotationConfig] = None,
    anomaly_config: Optional[AnomalyDetectionConfig] = None
) -> FederationSecurityService:
    """Get or create federation security service instance"""
    global _federation_security_instance
    if _federation_security_instance is None:
        _federation_security_instance = FederationSecurityService(
            tls_config, rotation_config, anomaly_config
        )
    return _federation_security_instance
