#!/usr/bin/env python3
"""
Production Setup Script
Environment configuration cleanup and production preparation
"""

import os
import sys
import json
import subprocess
from datetime import datetime
from typing import Dict, List, Any

class ProductionSetup:
    """Production environment setup and configuration"""

    def __init__(self):
        self.project_root = os.path.dirname(os.path.abspath(__file__))
        self.results = {
            "timestamp": datetime.now().isoformat(),
            "setup_steps": {},
            "summary": {"total": 0, "completed": 0, "failed": 0},
        }

    def log_step(self, step_name: str, success: bool, details: str = ""):
        """Log setup step result"""
        self.results["summary"]["total"] += 1
        if success:
            self.results["summary"]["completed"] += 1
            status = "✅ COMPLETED"
        else:
            self.results["summary"]["failed"] += 1
            status = "❌ FAILED"

        self.results["setup_steps"][step_name] = {
            "status": "completed" if success else "failed",
            "timestamp": datetime.now().isoformat(),
            "details": details,
        }

        print(f"{status} {step_name}")
        if details:
            print(f"   {details}")

    def check_environment_file(self):
        """Check and validate .env file"""
        env_file = os.path.join(self.project_root, ".env")
        
        try:
            if os.path.exists(env_file):
                with open(env_file, 'r') as f:
                    lines = f.readlines()
                
                # Check for common issues
                issues = []
                for i, line in enumerate(lines, 1):
                    line = line.strip()
                    if not line or line.startswith('#'):
                        continue
                    if ':' in line and '=' not in line:
                        issues.append(f"Line {i}: Using ':' instead of '='")
                    if 'export ' in line:
                        issues.append(f"Line {i}: Contains 'export' keyword")
                
                if issues:
                    self.log_step("Environment File Check", False, f"Issues found: {'; '.join(issues)}")
                else:
                    self.log_step("Environment File Check", True, f"Valid format ({len(lines)} lines)")
            else:
                self.log_step("Environment File Check", False, "File not found")
        except Exception as e:
            self.log_step("Environment File Check", False, str(e))

    def check_required_packages(self):
        """Check if required packages are installed"""
        required_packages = [
            "flask", "requests", "python-dotenv", "loguru"
        ]
        
        missing_packages = []
        for package in required_packages:
            try:
                __import__(package)
            except ImportError:
                missing_packages.append(package)
        
        if missing_packages:
            self.log_step("Required Packages Check", False, f"Missing: {', '.join(missing_packages)}")
        else:
            self.log_step("Required Packages Check", True, "All required packages installed")

    def check_service_endpoints(self):
        """Check if service endpoints are accessible"""
        endpoints = [
            "http://localhost:5058/health",
            "http://localhost:5058/api/integrations/google/health",
            "http://localhost:5058/api/integrations/asana/health",
            "http://localhost:5058/api/integrations/slack/health",
            "http://localhost:5058/api/integrations/notion/health",
            "http://localhost:5058/api/integrations/teams/health"
        ]
        
        accessible_endpoints = []
        failed_endpoints = []
        
        try:
            import requests
            for endpoint in endpoints:
                try:
                    response = requests.get(endpoint, timeout=5)
                    if response.status_code == 200:
                        accessible_endpoints.append(endpoint)
                    else:
                        failed_endpoints.append(f"{endpoint} (status: {response.status_code})")
                except Exception:
                    failed_endpoints.append(f"{endpoint} (connection failed)")
            
            if len(accessible_endpoints) == len(endpoints):
                self.log_step("Service Endpoints Check", True, f"All {len(endpoints)} endpoints accessible")
            else:
                self.log_step("Service Endpoints Check", False, f"{len(accessible_endpoints)}/{len(endpoints)} accessible")
                for failed in failed_endpoints:
                    print(f"   ❌ {failed}")
        except ImportError:
            self.log_step("Service Endpoints Check", False, "requests package not available")

    def check_database_connections(self):
        """Check database connectivity"""
        db_files = [
            "backend/python-api-service/atom.db",
            "backend/python-api-service/integrations.db"
        ]
        
        available_dbs = []
        for db_file in db_files:
            full_path = os.path.join(self.project_root, db_file)
            if os.path.exists(full_path):
                available_dbs.append(db_file)
        
        if available_dbs:
            self.log_step("Database Connections Check", True, f"Available: {', '.join(available_dbs)}")
        else:
            self.log_step("Database Connections Check", False, "No database files found")

    def check_security_configuration(self):
        """Check security configurations"""
        security_issues = []
        
        # Check for hardcoded secrets
        env_file = os.path.join(self.project_root, ".env")
        if os.path.exists(env_file):
            with open(env_file, 'r') as f:
                content = f.read()
                if "test_key" in content.lower() or "demo_key" in content.lower():
                    security_issues.append("Demo/test keys found in .env")
        
        # Check for exposed endpoints
        try:
            import requests
            response = requests.get("http://localhost:5058/api/auth/debug", timeout=5)
            if response.status_code == 200:
                security_issues.append("Debug endpoint exposed")
        except:
            pass  # Debug endpoint not accessible
        
        if security_issues:
            self.log_step("Security Configuration Check", False, f"Issues: {'; '.join(security_issues)}")
        else:
            self.log_step("Security Configuration Check", True, "No obvious security issues")

    def check_frontend_configuration(self):
        """Check frontend configuration"""
        frontend_dirs = [
            "frontend-nextjs/pages",
            "frontend-nextjs/src",
            "frontend-nextjs/public"
        ]
        
        available_dirs = []
        for frontend_dir in frontend_dirs:
            full_path = os.path.join(self.project_root, frontend_dir)
            if os.path.exists(full_path):
                available_dirs.append(frontend_dir)
        
        # Check package.json
        package_json = os.path.join(self.project_root, "frontend-nextjs/package.json")
        package_exists = os.path.exists(package_json)
        
        if available_dirs and package_exists:
            self.log_step("Frontend Configuration Check", True, f"Available dirs: {len(available_dirs)}, package.json exists")
        else:
            self.log_step("Frontend Configuration Check", False, f"Missing directories or package.json")

    def generate_production_config(self):
        """Generate production configuration recommendations"""
        recommendations = [
            "Set production environment variables",
            "Configure HTTPS/SSL certificates",
            "Enable API rate limiting",
            "Set up monitoring and logging",
            "Configure database backups",
            "Enable security headers",
            "Set up error reporting",
            "Configure load balancing"
        ]
        
        self.log_step("Production Config Generation", True, f"Generated {len(recommendations)} recommendations")
        
        # Save recommendations to file
        config_file = os.path.join(self.project_root, "PRODUCTION_RECOMMENDATIONS.md")
        with open(config_file, 'w') as f:
            f.write("# Production Deployment Recommendations\n\n")
            f.write(f"Generated: {datetime.now().isoformat()}\n\n")
            for i, rec in enumerate(recommendations, 1):
                f.write(f"{i}. {rec}\n")
        
        print(f"   💾 Saved to: PRODUCTION_RECOMMENDATIONS.md")

    def run_setup(self):
        """Run complete production setup"""
        print("🚀 Starting Production Setup")
        print("=" * 50)
        
        self.check_environment_file()
        self.check_required_packages()
        self.check_service_endpoints()
        self.check_database_connections()
        self.check_security_configuration()
        self.check_frontend_configuration()
        self.generate_production_config()
        
        # Print summary
        print("\n" + "=" * 50)
        print("📊 Setup Summary")
        total = self.results["summary"]["total"]
        completed = self.results["summary"]["completed"]
        failed = self.results["summary"]["failed"]
        
        print(f"Total Steps: {total}")
        print(f"Completed: {completed}")
        print(f"Failed: {failed}")
        print(f"Success Rate: {(completed/total*100):.1f}%")
        
        # Save results
        results_file = os.path.join(self.project_root, "production_setup_results.json")
        with open(results_file, 'w') as f:
            json.dump(self.results, f, indent=2)
        print(f"\n📄 Results saved to: production_setup_results.json")
        
        return self.results


def main():
    """Main execution function"""
    setup = ProductionSetup()
    results = setup.run_setup()
    
    if results["summary"]["failed"] == 0:
        print("\n🎉 Production Setup: EXCELLENT - Ready for deployment!")
    elif results["summary"]["failed"] <= 2:
        print("\n✅ Production Setup: GOOD - Minor issues to address")
    else:
        print("\n⚠️  Production Setup: NEEDS ATTENTION - Multiple issues to fix")


if __name__ == "__main__":
    main()