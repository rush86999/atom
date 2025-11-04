#!/usr/bin/env python3
"""
🚀 ATOM - Comprehensive System Verification Script
This script verifies all ATOM components are working properly without getting stuck.
It includes timeouts, health checks, and comprehensive status reporting.
"""

import asyncio
import aiohttp
import time
import json
import sys
import os
import subprocess
from pathlib import Path
from typing import Dict, List, Tuple
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("atom_verifier")


class AtomSystemVerifier:
    def __init__(self):
        self.base_url = "http://localhost:5058"
        self.timeout = aiohttp.ClientTimeout(total=10)
        self.results = {}
        self.start_time = time.time()

    async def check_backend_health(self) -> Tuple[bool, str]:
        """Check if backend server is running and healthy"""
        try:
            async with aiohttp.ClientSession(timeout=self.timeout) as session:
                async with session.get(f"{self.base_url}/healthz") as response:
                    if response.status == 200:
                        data = await response.json()
                        return True, f"Backend healthy: {data.get('status', 'unknown')}"
                    else:
                        return False, f"Backend unhealthy: HTTP {response.status}"
        except Exception as e:
            return False, f"Backend unreachable: {str(e)}"

    async def check_api_endpoints(self) -> Tuple[bool, Dict]:
        """Check critical API endpoints"""
        endpoints = {
            "dashboard": "/api/dashboard",
            "workflows": "/api/workflows",
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

        return success_rate >= 0.8, results

    async def check_database_connectivity(self) -> Tuple[bool, str]:
        """Check if database is accessible"""
        try:
            # Try to check if PostgreSQL container is running
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

    async def check_frontend_availability(self) -> Tuple[bool, str]:
        """Check if frontend build exists and is accessible"""
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
                f"Frontend build exists ({len(existing_paths)}/{len(frontend_paths)} files)",
            )
        else:
            return (
                False,
                f"Frontend build incomplete ({len(existing_paths)}/{len(frontend_paths)} files)",
            )

    async def check_service_registry(self) -> Tuple[bool, Dict]:
        """Check service registry and integrations"""
        try:
            async with aiohttp.ClientSession(timeout=self.timeout) as session:
                async with session.get(f"{self.base_url}/api/services") as response:
                    if response.status == 200:
                        services = await response.json()
                        active_services = [
                            s for s in services if s.get("status") == "active"
                        ]
                        return True, {
                            "total_services": len(services),
                            "active_services": len(active_services),
                            "services": services,
                        }
                    else:
                        return False, {"error": f"HTTP {response.status}"}
        except Exception as e:
            return False, {"error": str(e)}

    async def check_workflow_automation(self) -> Tuple[bool, Dict]:
        """Check workflow automation system"""
        checks = {}

        # Check workflow templates
        try:
            async with aiohttp.ClientSession(timeout=self.timeout) as session:
                async with session.get(
                    f"{self.base_url}/api/workflows/templates"
                ) as response:
                    if response.status == 200:
                        templates = await response.json()
                        checks["templates"] = {"healthy": True, "count": len(templates)}
                    else:
                        checks["templates"] = {
                            "healthy": False,
                            "error": f"HTTP {response.status}",
                        }
        except Exception as e:
            checks["templates"] = {"healthy": False, "error": str(e)}

        # Check workflow agent
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

        healthy_checks = sum(1 for check in checks.values() if check["healthy"])
        total_checks = len(checks)

        return healthy_checks >= 1, checks

    async def check_file_structure(self) -> Tuple[bool, Dict]:
        """Verify critical file structure exists"""
        critical_files = [
            "README.md",
            "package.json",
            "Pipfile.lock",
            "backend/python-api-service/main_api_app.py",
            "frontend-nextjs/package.json",
            "src/orchestration/conversationalWorkflowManager.ts",
            "src/nlu_agents/workflow_agent.ts",
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

        files_healthy = files_exist >= len(critical_files) * 0.8  # 80% threshold
        dirs_healthy = dirs_exist >= len(critical_dirs) * 0.8

        return files_healthy and dirs_healthy, {
            "files": file_results,
            "directories": dir_results,
            "files_score": f"{files_exist}/{len(critical_files)}",
            "dirs_score": f"{dirs_exist}/{len(critical_dirs)}",
        }

    async def check_processes(self) -> Tuple[bool, Dict]:
        """Check if required processes are running"""
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

    def generate_report(self) -> Dict:
        """Generate comprehensive verification report"""
        total_checks = len(self.results)
        passed_checks = sum(1 for result in self.results.values() if result["healthy"])
        success_rate = (passed_checks / total_checks) * 100 if total_checks > 0 else 0

        # Determine overall status
        if success_rate >= 80:
            overall_status = "🟢 HEALTHY"
        elif success_rate >= 60:
            overall_status = "🟡 DEGRADED"
        else:
            overall_status = "🔴 UNHEALTHY"

        return {
            "overall_status": overall_status,
            "success_rate": f"{success_rate:.1f}%",
            "passed_checks": passed_checks,
            "total_checks": total_checks,
            "verification_time": f"{time.time() - self.start_time:.2f}s",
            "detailed_results": self.results,
        }

    async def run_comprehensive_verification(self) -> Dict:
        """Run all verification checks"""
        verification_tasks = [
            ("backend_health", self.check_backend_health),
            ("api_endpoints", self.check_api_endpoints),
            ("database", self.check_database_connectivity),
            ("frontend", self.check_frontend_availability),
            ("services", self.check_service_registry),
            ("workflow_automation", self.check_workflow_automation),
            ("file_structure", self.check_file_structure),
            ("processes", self.check_processes),
        ]

        logger.info("🚀 Starting comprehensive ATOM system verification...")

        for check_name, check_func in verification_tasks:
            try:
                logger.info(f"🔍 Checking: {check_name.replace('_', ' ').title()}...")
                healthy, details = await check_func()
                self.results[check_name] = {
                    "healthy": healthy,
                    "details": details,
                    "timestamp": time.time(),
                }

                status_emoji = "✅" if healthy else "❌"
                logger.info(
                    f"   {status_emoji} {check_name}: {'HEALTHY' if healthy else 'UNHEALTHY'}"
                )

            except Exception as e:
                logger.error(f"   ❌ {check_name}: ERROR - {str(e)}")
                self.results[check_name] = {
                    "healthy": False,
                    "details": {"error": str(e)},
                    "timestamp": time.time(),
                }

        return self.generate_report()


def print_colored_report(report: Dict):
    """Print a colored, human-readable report"""
    print("\n" + "=" * 80)
    print("🚀 ATOM SYSTEM VERIFICATION REPORT")
    print("=" * 80)

    status = report["overall_status"]
    if "🟢" in status:
        status_color = "\033[92m"  # Green
    elif "🟡" in status:
        status_color = "\033[93m"  # Yellow
    else:
        status_color = "\033[91m"  # Red

    print(f"Overall Status: {status_color}{status}\033[0m")
    print(
        f"Success Rate: {report['success_rate']} ({report['passed_checks']}/{report['total_checks']} checks)"
    )
    print(f"Verification Time: {report['verification_time']}")

    print("\n📊 Detailed Results:")
    print("-" * 40)

    for check_name, result in report["detailed_results"].items():
        status = "✅ HEALTHY" if result["healthy"] else "❌ UNHEALTHY"
        color = "\033[92m" if result["healthy"] else "\033[91m"
        print(f"{color}{status}\033[0m: {check_name.replace('_', ' ').title()}")

        # Print relevant details
        details = result["details"]
        if isinstance(details, dict):
            for key, value in details.items():
                if key not in ["error", "timestamp"]:
                    print(f"    {key}: {value}")
        elif isinstance(details, str):
            print(f"    {details}")

    print("\n🎯 Recommendations:")
    print("-" * 20)

    failed_checks = [
        name
        for name, result in report["detailed_results"].items()
        if not result["healthy"]
    ]
    if not failed_checks:
        print("✅ All systems operational! Ready for deployment.")
    else:
        print(f"⚠️  Issues detected in: {', '.join(failed_checks)}")
        if "backend_health" in failed_checks:
            print("   → Start backend server: bash start_server.sh")
        if "database" in failed_checks:
            print(
                "   → Start database: docker-compose -f docker-compose.postgres.yml up -d"
            )
        if "frontend" in failed_checks:
            print("   → Build frontend: cd frontend-nextjs && npm run build")

    print("=" * 80)


async def main():
    """Main verification function"""
    verifier = AtomSystemVerifier()

    try:
        report = await verifier.run_comprehensive_verification()
        print_colored_report(report)

        # Exit with appropriate code
        if "🟢" in report["overall_status"]:
            sys.exit(0)  # Success
        elif "🟡" in report["overall_status"]:
            sys.exit(1)  # Warning
        else:
            sys.exit(2)  # Error

    except Exception as e:
        logger.error(f"Verification failed: {str(e)}")
        print(f"❌ Verification failed: {str(e)}")
        sys.exit(2)


if __name__ == "__main__":
    asyncio.run(main())
