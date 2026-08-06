"""
Round 22 TDD bug hunt — BUG-094: federation security misreports handshake-failure volume.

`FederationSecurityService.get_statistics()` reports `tls.handshake_failures`
as `len(get_handshake_failures())`, which is the number of DISTINCT source IPs,
not the total failure count. Five failed handshakes from the same attacker IP
report as "1" — undercounting the real security signal in a monitoring module
whose whole job is anomaly detection.

TDD: assertion below fails against current code (reports distinct-IP count),
then passes once the metric sums the per-IP failure counts.
"""
from core.federation.federation_security import FederationSecurityService


class TestHandshakeFailureMetric:
    def test_metric_counts_total_failures_not_distinct_ips(self):
        svc = FederationSecurityService()
        # Five failures from a single source IP.
        for _ in range(5):
            svc.tls.record_handshake_failure("203.0.113.1")

        stats = svc.get_statistics()
        assert stats["tls"]["handshake_failures"] == 5

    def test_metric_accumulates_across_ips(self):
        svc = FederationSecurityService()
        svc.tls.record_handshake_failure("203.0.113.1")
        svc.tls.record_handshake_failure("203.0.113.1")
        svc.tls.record_handshake_failure("198.51.100.7")

        stats = svc.get_statistics()
        assert stats["tls"]["handshake_failures"] == 3

    def test_metric_zero_when_no_failures(self):
        svc = FederationSecurityService()
        stats = svc.get_statistics()
        assert stats["tls"]["handshake_failures"] == 0
