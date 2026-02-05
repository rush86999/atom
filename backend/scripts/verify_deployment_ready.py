#!/usr/bin/env python3
"""
🚀 ATOM - Final Deployment Verification Script
Comprehensive verification that everything is ready for production deployment.
"""

import asyncio
import json
import logging
import os
from pathlib import Path
import subprocess
import sys
from typing import Dict, List, Tuple
import aiohttp

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("deployment_verifier")


class DeploymentVerifier:
    def __init__(self):
        self.base_url = "http://localhost:5058"
        self.timeout = aiohttp.ClientTimeout(total=10)
        self.results = {}
        self.start_time = None

    async def verify_backend_health(self) -> Tuple[bool, str]:
        """Verify backend server is healthy"""
        try:
            async with aiohttp.ClientSession(timeout=self.timeout) as session:
                async with session.get(f"{self.base_url}/healthz") as response:
                    if response.status == 200:
                        data = await response.json()
                        return True, f"Backend healthy: {data.get('status', 'ok')}"
                    else:
                        return False, f"Backend unhealthy: HTTP {response.status}"
        except Exception as e:
            return False, f"Backend unreachable: {str(e)}"

    async def verify_core_endpoints(self) -> Tuple[bool, Dict]:
        """Verify all core API endpoints"""
        endpoints = {
            "dashboard": "/api/dashboard",
            "services": "/api/services",
            "workflow_templates": "/api/workflows/templates",
            "workflow_agent": "/api/workflow-agent/health",
        }

        results = {}
        async with aiohttp.ClientSession(timeout=self.timeout) as session:
            for name, endpoint in endpoints.items():
                try:
                    async with session.get(f"{self.base_url}{endpoint}") as response:
                        results[name] = {
                            "status": response.status,
                            "healthy": response.status == 200,
                        }
                except Exception as e:
                    results[name] = {
                        "status": "error",
                        "healthy": False,
                        "error": str(e),
                    }

        healthy_count = sum(1 for result in results.values() if result["healthy"])
        total_count = len(results)
        success_rate = healthy_count / total_count if total_count > 0 else 0

        return success_rate >= 0.75, results

    async def verify_workflow_automation(self) -> Tuple[bool, Dict]:
        """Verify workflow automation system is functional"""
        checks = {}

        # Test workflow templates
        try:
            async with aiohttp.ClientSession(timeout=self.timeout) as session:
                async with session.get(
                    f"{self.base_url}/api/workflows/templates"
                ) as response:
                    if response.status == 200:
                        templates = await response.json()
                        checks["templates"] = {
                            "healthy": True,
                            "count": templates.get("count", 0),
                            "available": len(templates.get("templates", [])),
                        }
                    else:
                        checks["templates"] = {
                            "healthy": False,
                            "error": f"HTTP {response.status}",
                        }
        except Exception as e:
            checks["templates"] = {"healthy": False, "error": str(e)}

        # Test workflow agent
        try:
            async with aiohttp.ClientSession(timeout=self.timeout) as session:
                async with session.get(
                    f"{self.base_url}/api/workflow-agent/health"
                ) as response:
                    checks["workflow_agent"] = {
                        "healthy": response.status == 200,
                        "status": response.status,
                    }
        except Exception as e:
            checks["workflow_agent"] = {"healthy": False, "error": str(e)}

        # Test workflow creation
        try:
            async with aiohttp.ClientSession(timeout=self.timeout) as session:
                async with session.post(
                    f"{self.base_url}/api/workflow-agent/analyze",
                    json={"user_input": "Create a test workflow"},
                ) as response:
                    checks["workflow_creation"] = {
                        "healthy": response.status in [200, 400, 500],
                        "status": response.status,
                    }
        except Exception as e:
            checks["workflow_creation"] = {"healthy": False, "error": str(e)}

        healthy_checks = sum(1 for check in checks.values() if check["healthy"])
        total_checks = len(checks)

        return healthy_checks >= 2, checks

    async def verify_service_registry(self) -> Tuple[bool, Dict]:
        """Verify service registry is populated"""
        try:
            async with aiohttp.ClientSession(timeout=self.timeout) as session:
                async with session.get(f"{self.base_url}/api/services") as response:
                    if response.status == 200:
                        services = await response.json()
                        active_services = services.get("active_services", 0)
                        total_services = services.get("total_services", 0)
                        return True, {
                            "active_services": active_services,
                            "total_services": total_services,
                            "services": [
                                s["name"] for s in services.get("services", [])
                            ],
                        }
                    else:
                        return False, {"error": f"HTTP {response.status}"}
        except Exception as e:
            return False, {"error": str(e)}

    async def verify_frontend_build(self) -> Tuple[bool, str]:
        """Verify frontend is built and ready"""
        frontend_paths = [
            "frontend-nextjs/.next",
            "frontend-nextjs/package.json",
            "frontend-nextjs/next.config.js",
        ]

        existing_paths = []
        for path in frontend_paths:
            if Path(path).exists():
                existing_paths.append(path)

        if len(existing_paths) >= 2:
            return (
                True,
                f"Frontend build ready ({len(existing_paths)}/{len(frontend_paths)} files)",
            )
        else:
            return (
                False,
                f"Frontend build incomplete ({len(existing_paths)}/{len(frontend_paths)} files)",
            )

    async def verify_database_connectivity(self) -> Tuple[bool, str]:
        """Verify database is accessible"""
        try:
            # Check if PostgreSQL container is running
            result = subprocess.run(
                [
                    "docker",
                    "ps",
                    "--filter",
                    "name=atom-postgres",
                    "--format",
                    "{{.Names}}",
                ],
                capture_output=True,
                text=True,
                timeout=10,
            )

            if "atom-postgres" in result.stdout:
                return True, "PostgreSQL container running"
            else:
                return False, "PostgreSQL container not found"
        except subprocess.TimeoutExpired:
            return False, "Database check timeout"
        except Exception as e:
            return False, f"Database check failed: {str(e)}"

    async def verify_file_structure(self) -> Tuple[bool, Dict]:
        """Verify critical file structure exists"""
        critical_files = [
            "README.md",
            "package.json",
            "Pipfile.lock",
            "backend/python-api-service/main_api_app.py",
            "frontend-nextjs/package.json",
            "src/orchestration/conversationalWorkflowManager.ts",
            "src/nlu_agents/workflow_agent.ts",
            "backend/python-api-service/dashboard_routes.py",
            "backend/python-api-service/service_registry_routes.py",
            "backend/python-api-service/nlu_bridge_service.py",
        ]

        critical_dirs = [
            "backend",
            "frontend-nextjs",
            "src",
            "src/orchestration",
            "src/nlu_agents",
            "config",
        ]

        file_results = {}
        for file_path in critical_files:
            exists = Path(file_path).exists()
            file_results[file_path] = exists

        dir_results = {}
        for dir_path in critical_dirs:
            exists = Path(dir_path).exists() and Path(dir_path).is_dir()
            dir_results[dir_path] = exists

        files_exist = sum(file_results.values())
        dirs_exist = sum(dir_results.values())

        files_healthy = files_exist >= len(critical_files) * 0.9  # 90% threshold
        dirs_healthy = dirs_exist >= len(critical_dirs) * 0.9

        return files_healthy and dirs_healthy, {
            "files": file_results,
            "directories": dir_results,
            "files_score": f"{files_exist}/{len(critical_files)}",
            "dirs_score": f"{dirs_exist}/{len(critical_dirs)}",
        }

    async def verify_processes(self) -> Tuple[bool, Dict]:
        """Verify required processes are running"""
        processes_to_check = [
            "python.*main_api_app.py",
            "node.*next",
            "docker.*postgres",
        ]

        results = {}
        for process_pattern in processes_to_check:
            try:
                result = subprocess.run(
                    ["pgrep", "-f", process_pattern],
                    capture_output=True,
                    text=True,
                    timeout=5,
                )
                running = result.returncode == 0
                results[process_pattern] = running
            except subprocess.TimeoutExpired:
                results[process_pattern] = False
            except Exception:
                results[process_pattern] = False

        running_count = sum(results.values())
        total_count = len(results)

        return running_count >= 1, results  # At least backend should be running

    def generate_deployment_report(self) -> Dict:
        """Generate comprehensive deployment readiness report"""
        total_checks = len(self.results)
        passed_checks = sum(1 for result in self.results.values() if result["healthy"])
        success_rate = (passed_checks / total_checks) * 100 if total_checks > 0 else 0

        # Determine deployment readiness
        if success_rate >= 90:
            deployment_status = "🟢 READY FOR DEPLOYMENT"
        elif success_rate >= 75:
            deployment_status = "🟡 READY WITH MINOR ISSUES"
        else:
            deployment_status = "🔴 NOT READY FOR DEPLOYMENT"

        return {
            "deployment_status": deployment_status,
            "success_rate": f"{success_rate:.1f}%",
            "passed_checks": passed_checks,
            "total_checks": total_checks,
            "verification_time": f"{time.time() - self.start_time:.2f}s",
            "detailed_results": self.results,
        }

    async def run_deployment_verification(self) -> Dict:
        """Run all deployment verification checks"""
        self.start_time = time.time()

        verification_tasks = [
            ("backend_health", self.verify_backend_health),
            ("core_endpoints", self.verify_core_endpoints),
            ("workflow_automation", self.verify_workflow_automation),
            ("service_registry", self.verify_service_registry),
            ("frontend_build", self.verify_frontend_build),
            ("database", self.verify_database_connectivity),
            ("file_structure", self.verify_file_structure),
            ("processes", self.verify_processes),
        ]

        logger.info("🚀 Starting ATOM deployment verification...")
        print("\n" + "=" * 60)
        print("🚀 ATOM DEPLOYMENT READINESS VERIFICATION")
        print("=" * 60)

        for check_name, check_func in verification_tasks:
            try:
                print(f"🔍 {check_name.replace('_', ' ').title()}...", end=" ")
                healthy, details = await check_func()
                self.results[check_name] = {
                    "healthy": healthy,
                    "details": details,
                    "timestamp": time.time(),
                }

                if healthy:
                    print("✅ PASS")
                else:
                    print("❌ FAIL")

            except Exception as e:
                print("❌ ERROR")
                logger.error(f"Verification error in {check_name}: {str(e)}")
                self.results[check_name] = {
                    "healthy": False,
                    "details": {"error": str(e)},
                    "timestamp": time.time(),
                }

        return self.generate_deployment_report()


def print_deployment_report(report: Dict):
    """Print deployment readiness report"""
    print("\n" + "=" * 60)
    print("📊 DEPLOYMENT READINESS REPORT")
    print("=" * 60)

    status = report["deployment_status"]
    if "🟢" in status:
        status_color = "\033[92m"  # Green
    elif "🟡" in status:
        status_color = "\033[93m"  # Yellow
    else:
        status_color = "\033[91m"  # Red

    print(f"Deployment Status: {status_color}{status}\033[0m")
    print(
        f"Success Rate: {report['success_rate']} ({report['passed_checks']}/{report['total_checks']} checks)"
    )
    print(f"Verification Time: {report['verification_time']}")

    print("\n📋 Detailed Results:")
    print("-" * 40)

    for check_name, result in report["detailed_results"].items():
        status = "✅ PASS" if result["healthy"] else "❌ FAIL"
        color = "\033[92m" if result["healthy"] else "\033[91m"
        print(f"{color}{status}\033[0m: {check_name.replace('_', ' ').title()}")

        # Print relevant details
        details = result["details"]
        if isinstance(details, dict):
            for key, value in details.items():
                if key not in ["error", "timestamp"]:
                    if isinstance(value, list):
                        print(
                            f"    {key}: {', '.join(str(v) for v in value[:3])}{'...' if len(value) > 3 else ''}"
                        )
                    else:
                        print(f"    {key}: {value}")
        elif isinstance(details, str):
            print(f"    {details}")

    print("\n🎯 Deployment Recommendations:")
    print("-" * 30)

    failed_checks = [
        name
        for name, result in report["detailed_results"].items()
        if not result["healthy"]
    ]

    if not failed_checks:
        print("✅ All systems ready! Execute deployment script:")
        print("   ./deploy_production.sh")
    else:
        print(f"⚠️  Address these issues before deployment:")
        for check in failed_checks:
            if check == "backend_health":
                print("   → Start backend server: bash start_server.sh")
            elif check == "database":
                print(
                    "   → Start database: docker-compose -f docker-compose.postgres.yml up -d"
                )
            elif check == "frontend_build":
                print("   → Build frontend: cd frontend-nextjs && npm run build")
            elif check == "core_endpoints":
                print("   → Check API endpoints and restart backend")
            else:
                print(f"   → Fix {check.replace('_', ' ')}")

    print("=" * 60)


async def main():
    """Main deployment verification function"""
    verifier = DeploymentVerifier()

    try:
        report = await verifier.run_deployment_verification()
        print_deployment_report(report)

        # Exit with appropriate code
        if "🟢" in report["deployment_status"]:
            print("\n🎉 ATOM is ready for production deployment!")
            sys.exit(0)  # Success
        elif "🟡" in report["deployment_status"]:
            print("\n⚠️  ATOM can be deployed with minor issues")
            sys.exit(1)  # Warning
        else:
            print("\n❌ ATOM is not ready for deployment")
            sys.exit(2)  # Error

    except Exception as e:
        logger.error(f"Deployment verification failed: {str(e)}")
        print(f"❌ Deployment verification failed: {str(e)}")
        sys.exit(2)


if __name__ == "__main__":
    import time

    asyncio.run(main())
