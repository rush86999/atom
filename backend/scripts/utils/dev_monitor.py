#!/usr/bin/env python3
"""
ATOM PLATFORM - DEVELOPMENT MONITORING DASHBOARD
Real-time monitoring for development environment
"""

import json
import threading
import time
from collections import deque
from datetime import datetime
from typing import Any, Dict, List
import requests


class DevMonitor:
    """Development monitoring dashboard for ATOM platform"""

    def __init__(self):
        self.base_urls = {
            "frontend": "http://localhost:3000",
            "backend": "http://localhost:8000",
            "oauth": "http://localhost:5058",
        }

        # Monitoring data storage
        self.metrics = {
            "service_health": {},
            "api_endpoints": {},
            "performance": deque(maxlen=100),
            "errors": deque(maxlen=50),
            "development_progress": {},
        }

        # Development progress tracking
        self.progress_metrics = {
            "core_endpoints": {
                "total": 15,
                "completed": 0,
                "endpoints": [
                    "/health",
                    "/api/services/registry",
                    "/api/ai/providers",
                    "/api/workflows/templates",
                    "/api/auth/oauth-status",
                    "/docs",
                    "/api/system/status",
                    "/api/workflows/execute",
                    "/api/ai/optimize-cost",
                    "/api/services/{service_id}",
                    "/api/workflows/templates/{template_id}",
                    "/api/ai/providers/{provider_id}",
                    "/api/auth/services",
                    "/healthz",
                    "/api/health",
                ],
            },
            "service_integrations": {"total": 33, "connected": 0, "services": []},
            "byok_system": {
                "providers_configured": 0,
                "total_providers": 5,
                "cost_optimization": False,
            },
            "workflow_system": {
                "templates_available": 0,
                "workflows_executed": 0,
                "automation_ready": False,
            },
        }

    def check_service_health(self) -> Dict[str, Any]:
        """Check health of all services"""
        health_data = {}

        for service, url in self.base_urls.items():
            try:
                if service == "oauth":
                    health_url = f"{url}/healthz"
                elif service == "frontend":
                    health_url = f"{url}/api/health"
                else:
                    health_url = f"{url}/health"

                start_time = time.time()
                response = requests.get(health_url, timeout=5)
                response_time = time.time() - start_time

                health_data[service] = {
                    "status": "healthy" if response.status_code == 200 else "unhealthy",
                    "response_time": response_time,
                    "status_code": response.status_code,
                    "last_check": datetime.now().isoformat(),
                }

                # Log performance metric
                self.metrics["performance"].append(
                    {
                        "service": service,
                        "response_time": response_time,
                        "timestamp": datetime.now().isoformat(),
                    }
                )

            except Exception as e:
                health_data[service] = {
                    "status": "unhealthy",
                    "error": str(e),
                    "last_check": datetime.now().isoformat(),
                }

                # Log error
                self.metrics["errors"].append(
                    {
                        "service": service,
                        "error": str(e),
                        "timestamp": datetime.now().isoformat(),
                        "type": "health_check_failed",
                    }
                )

        self.metrics["service_health"] = health_data
        return health_data

    def check_api_endpoints(self) -> Dict[str, Any]:
        """Check core API endpoints"""
        endpoints_to_check = [
            ("Service Registry", "/api/services/registry", "backend"),
            ("BYOK Providers", "/api/ai/providers", "backend"),
            ("Workflow Templates", "/api/workflows/templates", "backend"),
            ("OAuth Status", "/api/auth/oauth-status", "oauth"),
            ("API Documentation", "/docs", "backend"),
            ("System Status", "/api/system/status", "backend"),
        ]

        endpoint_data = {}
        working_endpoints = 0

        for name, endpoint, service in endpoints_to_check:
            try:
                url = f"{self.base_urls[service]}{endpoint}"
                response = requests.get(url, timeout=5)

                endpoint_data[name] = {
                    "status": "working"
                    if response.status_code in [200, 405]
                    else "broken",
                    "status_code": response.status_code,
                    "url": url,
                    "last_check": datetime.now().isoformat(),
                }

                if response.status_code in [200, 405]:
                    working_endpoints += 1

            except Exception as e:
                endpoint_data[name] = {
                    "status": "broken",
                    "error": str(e),
                    "url": url,
                    "last_check": datetime.now().isoformat(),
                }

        # Update development progress
        self.progress_metrics["core_endpoints"]["completed"] = working_endpoints
        self.metrics["api_endpoints"] = endpoint_data

        return endpoint_data

    def update_development_progress(self):
        """Update development progress metrics"""
        # Check service integrations
        try:
            response = requests.get(
                f"{self.base_urls['backend']}/api/services/registry", timeout=5
            )
            if response.status_code == 200:
                data = response.json()
                services = data.get("services", [])
                self.progress_metrics["service_integrations"]["connected"] = len(
                    services
                )
                self.progress_metrics["service_integrations"]["services"] = [
                    s["id"] for s in services if s.get("status") == "available"
                ]
        except:
            pass

        # Check BYOK system
        try:
            response = requests.get(
                f"{self.base_urls['backend']}/api/ai/providers", timeout=5
            )
            if response.status_code == 200:
                data = response.json()
                self.progress_metrics["byok_system"]["providers_configured"] = len(
                    data.get("providers", [])
                )
                self.progress_metrics["byok_system"]["cost_optimization"] = True
        except:
            pass

        # Check workflow system
        try:
            response = requests.get(
                f"{self.base_urls['backend']}/api/workflows/templates", timeout=5
            )
            if response.status_code == 200:
                data = response.json()
                self.progress_metrics["workflow_system"]["templates_available"] = len(
                    data.get("templates", [])
                )
                self.progress_metrics["workflow_system"]["automation_ready"] = True
        except:
            pass

        self.metrics["development_progress"] = self.progress_metrics

    def calculate_development_score(self) -> float:
        """Calculate overall development progress score"""
        total_score = 0
        max_score = 0

        # Core endpoints (40% weight)
        endpoints = self.progress_metrics["core_endpoints"]
        endpoint_score = (endpoints["completed"] / endpoints["total"]) * 40
        total_score += endpoint_score
        max_score += 40

        # Service integrations (30% weight)
        integrations = self.progress_metrics["service_integrations"]
        integration_score = (integrations["connected"] / integrations["total"]) * 30
        total_score += integration_score
        max_score += 30

        # BYOK system (20% weight)
        byok = self.progress_metrics["byok_system"]
        byok_score = (byok["providers_configured"] / byok["total_providers"]) * 20
        if byok["cost_optimization"]:
            byok_score += 5  # Bonus for cost optimization
        total_score += byok_score
        max_score += 25

        # Workflow system (10% weight)
        workflow = self.progress_metrics["workflow_system"]
        workflow_score = (
            workflow["templates_available"] / 10
        ) * 10  # Assuming 10 templates max
        if workflow["automation_ready"]:
            workflow_score += 5  # Bonus for automation readiness
        total_score += workflow_score
        max_score += 15

        return (total_score / max_score) * 100

    def generate_dashboard(self):
        """Generate development dashboard"""
        # Update all metrics
        service_health = self.check_service_health()
        api_endpoints = self.check_api_endpoints()
        self.update_development_progress()
        dev_score = self.calculate_development_score()

        print("🚀 ATOM PLATFORM - DEVELOPMENT MONITORING DASHBOARD")
        print("=" * 70)
        print(f"📊 Development Score: {dev_score:.1f}%")
        print(f"🕐 Last Updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print()

        # Service Health Section
        print("🔍 SERVICE HEALTH")
        print("-" * 40)
        for service, health in service_health.items():
            status_icon = "✅" if health["status"] == "healthy" else "❌"
            response_time = (
                f"{health.get('response_time', 0):.3f}s"
                if "response_time" in health
                else "N/A"
            )
            print(
                f"   {status_icon} {service.upper():<15} {health['status']:<10} {response_time}"
            )
        print()

        # API Endpoints Section
        print("🔧 API ENDPOINTS")
        print("-" * 40)
        working_count = sum(
            1 for ep in api_endpoints.values() if ep["status"] == "working"
        )
        print(f"   📈 Working: {working_count}/{len(api_endpoints)} endpoints")
        for name, endpoint in api_endpoints.items():
            status_icon = "✅" if endpoint["status"] == "working" else "❌"
            print(f"   {status_icon} {name}")
        print()

        # Development Progress Section
        print("📈 DEVELOPMENT PROGRESS")
        print("-" * 40)

        # Core endpoints
        endpoints = self.progress_metrics["core_endpoints"]
        endpoint_pct = (endpoints["completed"] / endpoints["total"]) * 100
        print(
            f"   🔌 Core Endpoints: {endpoints['completed']}/{endpoints['total']} ({endpoint_pct:.1f}%)"
        )

        # Service integrations
        integrations = self.progress_metrics["service_integrations"]
        integration_pct = (integrations["connected"] / integrations["total"]) * 100
        print(
            f"   🔗 Service Integrations: {integrations['connected']}/{integrations['total']} ({integration_pct:.1f}%)"
        )

        # BYOK system
        byok = self.progress_metrics["byok_system"]
        byok_pct = (byok["providers_configured"] / byok["total_providers"]) * 100
        cost_opt = "✅" if byok["cost_optimization"] else "❌"
        print(
            f"   🤖 BYOK System: {byok['providers_configured']}/{byok['total_providers']} providers ({byok_pct:.1f}%)"
        )
        print(f"      Cost Optimization: {cost_opt}")

        # Workflow system
        workflow = self.progress_metrics["workflow_system"]
        automation = "✅" if workflow["automation_ready"] else "❌"
        print(f"   🔄 Workflow System: {workflow['templates_available']} templates")
        print(f"      Automation Ready: {automation}")
        print()

        # Performance Metrics
        print("⚡ PERFORMANCE METRICS")
        print("-" * 40)
        if self.metrics["performance"]:
            recent_perf = list(self.metrics["performance"])[-5:]  # Last 5 metrics
            avg_response_time = sum(p["response_time"] for p in recent_perf) / len(
                recent_perf
            )
            print(f"   📊 Avg Response Time: {avg_response_time:.3f}s")
            print(f"   📈 Recent Samples: {len(recent_perf)}")
        else:
            print("   📊 No performance data collected yet")
        print()

        # Error Tracking
        print("🚨 ERROR TRACKING")
        print("-" * 40)
        error_count = len(self.metrics["errors"])
        if error_count > 0:
            recent_errors = list(self.metrics["errors"])[-3:]  # Last 3 errors
            print(f"   ❌ Total Errors: {error_count}")
            for error in recent_errors:
                print(f"      • {error['service']}: {error['error']}")
        else:
            print("   ✅ No recent errors")
        print()

        # Recommendations
        print("💡 DEVELOPMENT RECOMMENDATIONS")
        print("-" * 40)
        recommendations = []

        if dev_score < 50:
            recommendations.append(
                "🔴 Focus on core functionality before advanced features"
            )
        if service_health.get("frontend", {}).get("status") != "healthy":
            recommendations.append("🔴 Fix frontend service health")
        if working_count < len(api_endpoints):
            recommendations.append("🟡 Complete missing API endpoints")
        if integrations["connected"] < 5:
            recommendations.append("🟡 Connect at least 5 core services")
        if byok["providers_configured"] < 3:
            recommendations.append("🟡 Configure at least 3 AI providers")
        if workflow["templates_available"] < 3:
            recommendations.append("🟡 Create more workflow templates")

        if not recommendations:
            recommendations.append(
                "✅ Great progress! Continue with feature development"
            )

        for rec in recommendations:
            print(f"   {rec}")

        print()
        print("=" * 70)

        # Save metrics to file
        self.save_metrics()

    def save_metrics(self):
        """Save metrics to JSON file for historical tracking"""
        metrics_data = {
            "timestamp": datetime.now().isoformat(),
            "development_score": self.calculate_development_score(),
            "service_health": self.metrics["service_health"],
            "api_endpoints": self.metrics["api_endpoints"],
            "development_progress": self.metrics["development_progress"],
            "recent_errors": list(self.metrics["errors"])[-10:],  # Last 10 errors
            "performance_samples": list(self.metrics["performance"])[
                -20:
            ],  # Last 20 samples
        }

        filename = f"dev_metrics_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(filename, "w") as f:
            json.dump(metrics_data, f, indent=2)

    def start_monitoring(self, interval_seconds=30):
        """Start continuous monitoring"""
        print(f"🚀 Starting development monitoring (interval: {interval_seconds}s)")
        print("Press Ctrl+C to stop monitoring")
        print()

        try:
            while True:
                self.generate_dashboard()
                print(f"⏰ Next update in {interval_seconds} seconds...")
                print()
                time.sleep(interval_seconds)
        except KeyboardInterrupt:
            print("\n🛑 Monitoring stopped")


def main():
    """Main execution function"""
    monitor = DevMonitor()

    # Single dashboard generation
    monitor.generate_dashboard()

    # Ask if user wants continuous monitoring
    response = input("\nStart continuous monitoring? (y/N): ").strip().lower()
    if response in ["y", "yes"]:
        monitor.start_monitoring(interval_seconds=30)


if __name__ == "__main__":
    main()
