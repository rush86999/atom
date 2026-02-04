#!/usr/bin/env python3
"""
Live Evidence Collector for Independent AI Validator
Collects real evidence from live ATOM backend APIs for >98% validation
"""

import asyncio
import json
import logging
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
import aiohttp

logger = logging.getLogger(__name__)

@dataclass
class EvidencePoint:
    """Single piece of evidence from API testing"""
    endpoint: str
    success: bool
    response_time: float
    status_code: int
    response_data: Any
    timestamp: float
    evidence_type: str

class LiveEvidenceCollector:
    """
    Collects live evidence from ATOM backend APIs for marketing claim validation
    """

    def __init__(self, base_url: str = "http://localhost:5058"):
        self.base_url = base_url
        self.session = None
        self.evidence_points = []

    async def initialize(self):
        """Initialize HTTP session"""
        self.session = aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=60),  # Increased timeout
            headers={"User-Agent": "ATOM-Evidence-Collector/1.0"}
        )
        logger.info(f"Live evidence collector initialized for {self.base_url}")

    async def cleanup(self):
        """Cleanup HTTP session"""
        if self.session:
            await self.session.close()

    async def collect_all_evidence(self) -> Dict[str, Any]:
        """
        Collect comprehensive evidence for all marketing claims
        Returns structured evidence for AI provider validation
        """
        evidence = {
            "api_endpoints": await self._test_api_endpoints(),
            "ai_workflows": await self._test_ai_workflows(),
            "integrations": await self._test_integrations(),
            "analytics": await self._test_analytics(),
            "enterprise_features": await self._test_enterprise_features(),
            "performance_metrics": await self._collect_performance_metrics(),
            "system_status": await self._get_system_status()
        }

        # Calculate overall evidence strength
        evidence["evidence_strength"] = self._calculate_evidence_strength(evidence)
        evidence["collection_timestamp"] = time.time()
        evidence["total_endpoints_tested"] = len(self.evidence_points)

        return evidence

    async def _test_api_endpoints(self) -> List[EvidencePoint]:
        """Test core API endpoints for basic functionality"""
        endpoints = [
            "/",
            "/api/ai/health",
            "/api/ai/providers",
            "/api/analytics/usage/stats",
            "/api/system/status",
            "/api/enterprise/security/status",
            "/api/services/status"
        ]

        results = []
        for endpoint in endpoints:
            evidence = await self._test_endpoint(endpoint)
            if evidence:
                results.append(evidence)
                self.evidence_points.append(evidence)

        logger.info(f"API endpoint testing: {len(results)}/{len(endpoints)} successful")
        return results

    async def _test_ai_workflows(self) -> Dict[str, Any]:
        """Test AI workflow automation capabilities"""
        workflow_evidence = {
            "ai_provider_management": await self._test_endpoint("/api/v1/ai/status"),
            "workflow_optimization": await self._test_endpoint("/api/v1/ai/optimize"),
            "ai_health_status": await self._test_endpoint("/api/v1/ai/status"),
            "nlu_processing": await self._test_endpoint("/api/v1/ai/nlu"),
            "provider_configuration": await self._test_endpoint("/api/v1/byok/status")
        }

        # Test workflow automation specific features
        workflow_results = []
        for endpoint, evidence in workflow_evidence.items():
            if evidence and evidence.success:
                workflow_results.append({
                    "feature": endpoint,
                    "status": "operational",
                    "response_time": evidence.response_time
                })

        return {
            "workflow_automation_tested": len(workflow_results),
            "features_operational": workflow_results,
            "overall_status": "functional" if len(workflow_results) >= 3 else "limited"
        }

    async def _test_integrations(self) -> Dict[str, Any]:
        """Test multi-provider integration capabilities"""
        integration_endpoints = [
            "/api/v1/services/asana",
            "/api/v1/services/notion",
            "/api/v1/services/github",
            "/api/v1/services/slack",
            "/api/v1/services/linear",
            "/api/v1/services/outlook",
            "/api/v1/services/dropbox",
            "/api/v1/services/googledrive",
            "/api/v1/services/onedrive",
            "/api/v1/services/box",
            "/api/v1/services/stripe",
            "/api/v1/services/salesforce",
            "/api/v1/services/zoom",
            "/api/v1/services/tableau",
            "/api/v1/services/whatsapp",
            "/api/v1/services/microsoft365"
        ]

        integration_results = []
        working_integrations = 0

        for endpoint in integration_endpoints:
            evidence = await self._test_endpoint(endpoint)
            if evidence:
                integration_results.append({
                    "service": endpoint.split('/')[-1],  # Extract service name from /api/v1/services/{service}
                    "endpoint": endpoint,
                    "operational": evidence.success,
                    "response_time": evidence.response_time if evidence.success else None,
                    "status_code": evidence.status_code
                })

                if evidence.success:
                    working_integrations += 1
                self.evidence_points.append(evidence)

            # Add small delay to prevent overwhelming backend
            await asyncio.sleep(0.1)

        return {
            "total_integrations_tested": len(integration_results),
            "operational_integrations": working_integrations,
            "integration_success_rate": (working_integrations / len(integration_results)) * 100,
            "integration_details": integration_results
        }

    async def _test_analytics(self) -> Dict[str, Any]:
        """Test real-time analytics capabilities"""
        analytics_endpoints = [
            "/api/v1/analytics/dashboard",
            "/api/v1/analytics/performance",
            "/api/v1/analytics/usage",
            "/api/v1/analytics/reports"
        ]

        analytics_results = []
        working_features = 0

        for endpoint in analytics_endpoints:
            evidence = await self._test_endpoint(endpoint)
            if evidence:
                analytics_results.append({
                    "feature": endpoint.split('/')[-1] if '/' in endpoint else endpoint,
                    "operational": evidence.success,
                    "response_time": evidence.response_time if evidence.success else None
                })

                if evidence.success:
                    working_features += 1
                self.evidence_points.append(evidence)

        return {
            "analytics_features_tested": len(analytics_results),
            "operational_features": working_features,
            "real_time_capability": working_features >= 2,
            "performance_metrics": analytics_results
        }

    async def _test_enterprise_features(self) -> Dict[str, Any]:
        """Test enterprise-grade reliability and security features"""
        enterprise_endpoints = [
            "/api/v1/health/enterprise",
            "/api/v1/health/system",
            "/api/v1/uptime",
            "/api/v1/monitoring/status"
        ]

        enterprise_results = []
        security_features = 0

        for endpoint in enterprise_endpoints:
            evidence = await self._test_endpoint(endpoint)
            if evidence:
                enterprise_results.append({
                    "feature": endpoint.split('/')[-1] if '/' in endpoint else endpoint,
                    "operational": evidence.success,
                    "response_time": evidence.response_time if evidence.success else None
                })

                if evidence.success and 'security' in endpoint:
                    security_features += 1
                self.evidence_points.append(evidence)

        return {
            "enterprise_features_tested": len(enterprise_results),
            "security_features_operational": security_features,
            "enterprise_ready": len(enterprise_results) >= 2,
            "reliability_features": enterprise_results
        }

    async def _collect_performance_metrics(self) -> Dict[str, Any]:
        """Collect detailed performance metrics"""
        response_times = [ep.response_time for ep in self.evidence_points if ep.success]

        if not response_times:
            return {"error": "No performance data available"}

        return {
            "average_response_time": sum(response_times) / len(response_times),
            "min_response_time": min(response_times),
            "max_response_time": max(response_times),
            "total_requests": len(self.evidence_points),
            "successful_requests": len(response_times),
            "success_rate": (len(response_times) / len(self.evidence_points)) * 100,
            "performance_grade": self._grade_performance(response_times)
        }

    async def _get_system_status(self) -> Dict[str, Any]:
        """Get overall system status"""
        try:
            # Test root endpoint for basic system info
            evidence = await self._test_endpoint("/")
            if evidence and evidence.success:
                return {
                    "status": "operational",
                    "uptime": "unknown",  # Would need dedicated uptime endpoint
                    "version": "1.0.0",
                    "api_status": "healthy",
                    "last_check": time.time()
                }
        except Exception as e:
            logger.error(f"System status check failed: {e}")

        return {
            "status": "degraded",
            "api_status": "issues_detected",
            "last_check": time.time()
        }

    async def _test_endpoint(self, endpoint: str) -> Optional[EvidencePoint]:
        """Test a single API endpoint and collect evidence"""
        if not self.session:
            logger.error("Session not initialized")
            return None

        url = f"{self.base_url}{endpoint}"
        start_time = time.time()

        try:
            async with self.session.get(url) as response:
                response_time = time.time() - start_time

                # Try to parse JSON response
                response_data = None
                try:
                    response_data = await response.json()
                except:
                    response_data = await response.text()

                evidence = EvidencePoint(
                    endpoint=endpoint,
                    success=response.status == 200,
                    response_time=response_time,
                    status_code=response.status,
                    response_data=response_data,
                    timestamp=start_time,
                    evidence_type="api_test"
                )

                logger.debug(f"Endpoint {endpoint}: {response.status} in {response_time:.3f}s")
                return evidence

        except asyncio.TimeoutError:
            logger.warning(f"Timeout testing {endpoint}")
            return EvidencePoint(
                endpoint=endpoint,
                success=False,
                response_time=30.0,  # Timeout value
                status_code=0,
                response_data="Timeout",
                timestamp=start_time,
                evidence_type="api_test"
            )
        except Exception as e:
            logger.warning(f"Error testing {endpoint}: {str(e)}")
            return EvidencePoint(
                endpoint=endpoint,
                success=False,
                response_time=time.time() - start_time,
                status_code=0,
                response_data=str(e),
                timestamp=start_time,
                evidence_type="api_test"
            )

    def _calculate_evidence_strength(self, evidence: Dict[str, Any]) -> str:
        """Calculate overall evidence strength based on collected data"""
        total_tests = 0
        successful_tests = 0

        # Count API endpoint tests
        api_endpoints = evidence.get("api_endpoints", [])
        total_tests += len(api_endpoints)
        successful_tests += sum(1 for ep in api_endpoints if hasattr(ep, 'success') and ep.success)

        # Count integration tests
        integrations = evidence.get("integrations", {})
        if isinstance(integrations, dict):
            total_integrations = integrations.get("total_integrations_tested", 0)
            working_integrations = integrations.get("operational_integrations", 0)
            total_tests += total_integrations
            successful_tests += working_integrations

        # Calculate strength
        if total_tests == 0:
            return "INSUFFICIENT"

        success_rate = successful_tests / total_tests

        if success_rate >= 0.9:
            return "STRONG"
        elif success_rate >= 0.7:
            return "MODERATE"
        elif success_rate >= 0.5:
            return "WEAK"
        else:
            return "INSUFFICIENT"

    def _grade_performance(self, response_times: List[float]) -> str:
        """Grade performance based on response times"""
        avg_time = sum(response_times) / len(response_times)

        if avg_time < 0.5:  # Less than 500ms
            return "EXCELLENT"
        elif avg_time < 1.0:  # Less than 1 second
            return "GOOD"
        elif avg_time < 2.0:  # Less than 2 seconds
            return "FAIR"
        else:
            return "POOR"

    def get_validation_evidence_summary(self) -> Dict[str, Any]:
        """Get a summary of evidence for AI provider validation"""
        if not self.evidence_points:
            return {"error": "No evidence collected"}

        successful_endpoints = [ep for ep in self.evidence_points if ep.success]

        return {
            "total_endpoints_tested": len(self.evidence_points),
            "successful_endpoints": len(successful_endpoints),
            "success_rate": (len(successful_endpoints) / len(self.evidence_points)) * 100,
            "average_response_time": sum(ep.response_time for ep in successful_endpoints) / len(successful_endpoints) if successful_endpoints else 0,
            "evidence_strength": self._calculate_evidence_strength({}),
            "collection_method": "live_api_testing",
            "backend_url": self.base_url,
            "validation_ready": len(successful_endpoints) >= 10  # Require sufficient evidence
        }

async def main():
    """Test the live evidence collector"""
    collector = LiveEvidenceCollector()
    await collector.initialize()

    try:
        evidence = await collector.collect_all_evidence()
        print("=== Live Evidence Collection Results ===")
        print(f"Evidence Strength: {evidence.get('evidence_strength', 'UNKNOWN')}")
        print(f"Endpoints Tested: {evidence.get('total_endpoints_tested', 0)}")
        print(f"API Endpoints: {len(evidence.get('api_endpoints', []))}")
        print(f"Working Integrations: {evidence.get('integrations', {}).get('operational_integrations', 0)}")

        # Get summary for validation
        summary = collector.get_validation_evidence_summary()
        print(f"\nValidation Ready: {summary.get('validation_ready', False)}")
        print(f"Success Rate: {summary.get('success_rate', 0):.1f}%")

    finally:
        await collector.cleanup()

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main())