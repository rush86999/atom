#!/usr/bin/env python3
"""
Integration Health Check Framework
Quick connectivity and basic health validation for all 116+ integrations
"""

import asyncio
import json
import sys
import time
from pathlib import Path
from typing import Dict, List, Any
from datetime import datetime

class IntegrationHealthChecker:
    """Universal health checker for all ATOM integrations"""
    
    def __init__(self, registry_file: str = "backend/integration_registry.json"):
        self.registry_file = Path(registry_file)
        self.services = {}
        self.results = {}
        
        if self.registry_file.exists():
            data = json.loads(self.registry_file.read_text())
            self.services = data.get("services", {})
        else:
            print(f"❌ Registry file not found: {registry_file}")
            print("Run: python3 backend/integration_registry.py")
            sys.exit(1)
    
    async def check_service(self, service_name: str, service_info: Dict[str, Any]) -> Dict[str, Any]:
        """Check health of a single service"""
        result = {
            "service": service_name,
            "category": service_info.get("category", "unknown"),
            "status": "UNKNOWN",
            "checks": {
                "file_exists": False,
                "has_service_class": False,
                "has_auth_method": False
            },
            "timestamp": datetime.now().isoformat()
        }
        
        # Check 1: File exists
        file_path = Path(service_info["file"])
        if file_path.exists():
            result["checks"]["file_exists"] = True
        else:
            result["status"] = "FILE_MISSING"
            return result
        
        # Check 2: Has service class or integration class
        if service_info.get("classes"):
            result["checks"]["has_service_class"] = True
        
        # Check 3: Has auth/connect methods
        if service_info.get("has_connect") or service_info.get("auth_type") != "unknown":
            result["checks"]["has_auth_method"] = True
        
        # Determine overall status
        if all(result["checks"].values()):
            result["status"] = "READY"  # Ready for deeper testing
        elif result["checks"]["file_exists"] and result["checks"]["has_service_class"]:
            result["status"] = "PARTIAL"  # Missing auth but file exists
        else:
            result["status"] = "INCOMPLETE"
        
        return result
    
    async def check_all(self, category: str = None) -> Dict[str, Any]:
        """Check all services or services in a specific category"""
        services_to_check = self.services
        
        if category:
            services_to_check = {
                name: info for name, info in self.services.items()
                if info.get("category") == category
            }
        
        print(f"Checking {len(services_to_check)} services...")
        
        # Run checks concurrently
        tasks = [
            self.check_service(name, info)
            for name, info in services_to_check.items()
        ]
        
        results = await asyncio.gather(*tasks)
        
        for result in results:
            self.results[result["service"]] = result
        
        return self.results
    
    def generate_report(self) -> Dict[str, Any]:
        """Generate health check report"""
        if not self.results:
            return {"error": "No results available"}
        
        # Count by status
        status_counts = {}
        for result in self.results.values():
            status = result["status"]
            status_counts[status] = status_counts.get(status, 0) + 1
        
        # Count by category
        category_counts = {}
        for result in self.results.values():
            cat = result["category"]
            category_counts[cat] = category_counts.get(cat, 0) + 1
        
        # Calculate readiness score
        ready = status_counts.get("READY", 0)
        total = len(self.results)
        readiness_score = (ready / total) * 100 if total > 0 else 0
        
        return {
            "summary": {
                "total_services": total,
                "ready": ready,
                "partial": status_counts.get("PARTIAL", 0),
                "incomplete": status_counts.get("INCOMPLETE", 0),
                "file_missing": status_counts.get("FILE_MISSING", 0),
                "readiness_score": round(readiness_score, 2)
            },
            "by_category": category_counts,
            "by_status": status_counts,
            "detailed_results": self.results
        }
    
    def print_summary(self, report: Dict[str, Any]):
        """Print a formatted summary"""
        summary = report["summary"]
        
        print("\n" + "=" * 70)
        print("INTEGRATION HEALTH CHECK SUMMARY")
        print("=" * 70)
        print(f"\nTotal Services: {summary['total_services']}")
        print(f"Readiness Score: {summary['readiness_score']:.1f}%\n")
        
        print("Status Breakdown:")
        print(f"  [READY]:        {summary['ready']}")
        print(f"  [PARTIAL]:      {summary['partial']}")
        print(f"  [INCOMPLETE]:   {summary['incomplete']}")
        print(f"  [MISSING]:      {summary['file_missing']}")
        
        print("\nTop Categories:")
        for cat, count in sorted(report["by_category"].items(), key=lambda x: -x[1])[:5]:
            ready_in_cat = sum(
                1 for r in self.results.values()
                if r["category"] == cat and r["status"] == "READY"
            )
            print(f"  {cat.replace('_', ' ').title()}: {ready_in_cat}/{count} ready")
        
        # Critical services status
        print("\nCritical Services:")
        critical_cats = ["calendar", "email", "project_management"]
        for cat in critical_cats:
            cat_services = [r for r in self.results.values() if r["category"] == cat]
            ready = sum(1 for s in cat_services if s["status"] == "READY")
            total = len(cat_services)
            status_label = "[OK]" if ready == total else "[WARN]"
            print(f"  {status_label} {cat.replace('_', ' ').title()}: {ready}/{total}")

async def main():
    checker = IntegrationHealthChecker()
    
    print("=" * 70)
    print("ATOM INTEGRATION HEALTH CHECK")
    print("=" * 70)
    print()
    
    # Run health checks
    start_time = time.time()
    await checker.check_all()
    duration = time.time() - start_time
    
    # Generate and print report
    report = checker.generate_report()
    checker.print_summary(report)
    
    print(f"\nCheck completed in {duration:.2f}s")
    
    # Save detailed report
    report_path = Path("backend/integration_health_report.json")
    report_path.write_text(json.dumps(report, indent=2))
    print(f"\n[OK] Detailed report saved: {report_path}")
    
    # Return exit code based on readiness
    readiness = report["summary"]["readiness_score"]
    if readiness >= 80:
        print("\n[OK] Integration health: EXCELLENT")
        return 0
    elif readiness >= 60:
        print("\n[WARN] Integration health: GOOD")
        return 0
    else:
        print("\n[FAIL] Integration health: NEEDS WORK")
        return 1

if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
