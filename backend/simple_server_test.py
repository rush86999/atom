#!/usr/bin/env python3
"""
Simple Server Test
Test API endpoints without backend server startup
"""

import os
import sys
import json
import sqlite3
from datetime import datetime, timedelta
from typing import Dict, Any, List

class SimpleServerTest:
    """Simple server testing without backend startup"""

    def __init__(self):
        self.project_root = os.path.dirname(os.path.abspath(__file__))
        self.results = {
            "timestamp": datetime.now().isoformat(),
            "tests": {},
            "summary": {"total": 0, "passed": 0, "failed": 0, "success_rate": 0.0},
        }

    def log_test(self, test_name: str, success: bool, details: Dict[str, Any] = None):
        """Log test result"""
        self.results["summary"]["total"] += 1
        if success:
            self.results["summary"]["passed"] += 1
            status = "✅ PASSED"
        else:
            self.results["summary"]["failed"] += 1
            status = "❌ FAILED"

        self.results["tests"][test_name] = {
            "status": "passed" if success else "failed",
            "timestamp": datetime.now().isoformat(),
            "details": details or {},
        }

        print(f"{status} {test_name}")
        if details:
            for key, value in details.items():
                print(f"   {key}: {value}")

    def test_database_connectivity(self):
        """Test database connectivity and data"""
        try:
            db_path = os.path.join(self.project_root, "backend/python-api-service/atom.db")
            if os.path.exists(db_path):
                with sqlite3.connect(db_path) as conn:
                    cursor = conn.cursor()
                    cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
                    tables = [row[0] for row in cursor.fetchall()]
                    
                    # Test user data
                    cursor.execute("SELECT COUNT(*) FROM users")
                    user_count = cursor.fetchone()[0]
                    
                    # Test integration data
                    cursor.execute("SELECT COUNT(*) FROM integrations")
                    integration_count = cursor.fetchone()[0]
                    
                    self.log_test(
                        "Database Connectivity",
                        True,
                        {
                            "tables": tables,
                            "user_count": user_count,
                            "integration_count": integration_count,
                            "file_size": os.path.getsize(db_path)
                        }
                    )
            else:
                self.log_test("Database Connectivity", False, "Database file not found")
        except Exception as e:
            self.log_test("Database Connectivity", False, str(e))

    def test_oauth_database_connectivity(self):
        """Test OAuth database connectivity"""
        try:
            db_path = os.path.join(self.project_root, "backend/python-api-service/integrations.db")
            if os.path.exists(db_path):
                with sqlite3.connect(db_path) as conn:
                    cursor = conn.cursor()
                    cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
                    tables = [row[0] for row in cursor.fetchall()]
                    
                    # Test service configs
                    cursor.execute("SELECT COUNT(*) FROM service_configs")
                    service_count = cursor.fetchone()[0]
                    
                    self.log_test(
                        "OAuth Database Connectivity",
                        True,
                        {
                            "tables": tables,
                            "service_count": service_count,
                            "file_size": os.path.getsize(db_path)
                        }
                    )
            else:
                self.log_test("OAuth Database Connectivity", False, "OAuth database file not found")
        except Exception as e:
            self.log_test("OAuth Database Connectivity", False, str(e))

    def test_environment_file(self):
        """Test environment file structure"""
        try:
            env_path = os.path.join(self.project_root, ".env")
            if os.path.exists(env_path):
                with open(env_path, 'r') as f:
                    lines = f.readlines()
                
                # Count service configurations
                service_configs = {}
                for line in lines:
                    line = line.strip()
                    if '=' in line and not line.startswith('#'):
                        key, value = line.split('=', 1)
                        if '_CLIENT_ID' in key:
                            service = key.split('_CLIENT_ID')[0].lower()
                            service_configs[service] = value[:20] + '...' if len(value) > 20 else value
                
                self.log_test(
                    "Environment File",
                    True,
                    {
                        "total_lines": len(lines),
                        "service_configs": service_configs,
                        "file_size": os.path.getsize(env_path)
                    }
                )
            else:
                self.log_test("Environment File", False, "Environment file not found")
        except Exception as e:
            self.log_test("Environment File", False, str(e))

    def test_api_file_structure(self):
        """Test API file structure and endpoints"""
        try:
            api_path = os.path.join(self.project_root, "backend/python-api-service/minimal_api_app.py")
            if os.path.exists(api_path):
                with open(api_path, 'r') as f:
                    content = f.read()
                
                # Count API endpoints
                endpoints = []
                for line in content.split('\n'):
                    if '@app.route(' in line:
                        route = line.split('@app.route(')[1].split(')')[0].strip()
                        endpoints.append(route)
                
                # Count imported modules
                imports = []
                for line in content.split('\n'):
                    if line.strip().startswith('import '):
                        imports.append(line.strip().split(' ')[1])
                
                self.log_test(
                    "API File Structure",
                    True,
                    {
                        "endpoints_count": len(endpoints),
                        "endpoints": endpoints[:5],  # Show first 5
                        "imports_count": len(imports),
                        "file_size": os.path.getsize(api_path)
                    }
                )
            else:
                self.log_test("API File Structure", False, "API file not found")
        except Exception as e:
            self.log_test("API File Structure", False, str(e))

    def test_service_dashboard(self):
        """Test service dashboard creation"""
        try:
            dashboard_path = os.path.join(self.project_root, "frontend-nextjs/public/integration-status.html")
            if os.path.exists(dashboard_path):
                with open(dashboard_path, 'r') as f:
                    content = f.read()
                
                # Check for service cards
                service_cards = content.count('class="service-card"')
                status_indicators = content.count('status status-')
                
                self.log_test(
                    "Service Dashboard",
                    True,
                    {
                        "dashboard_exists": True,
                        "service_cards": service_cards,
                        "status_indicators": status_indicators,
                        "file_size": os.path.getsize(dashboard_path)
                    }
                )
            else:
                self.log_test("Service Dashboard", False, "Dashboard file not found")
        except Exception as e:
            self.log_test("Service Dashboard", False, str(e))

    def test_integration_files(self):
        """Test integration file availability"""
        integration_files = [
            "backend/python-api-service/google_enhanced_api.py",
            "backend/python-api-service/asana_enhanced_api.py", 
            "backend/python-api-service/slack_enhanced_api.py",
            "backend/python-api-service/notion_enhanced_api.py",
            "backend/python-api-service/teams_enhanced_api.py",
            "backend/python-api-service/github_enhanced_api.py"
        ]
        
        available_files = []
        for file_path in integration_files:
            full_path = os.path.join(self.project_root, file_path)
            if os.path.exists(full_path):
                service = file_path.split('/')[-1].replace('_enhanced_api.py', '')
                size = os.path.getsize(full_path)
                available_files.append(f"{service}: {size} bytes")
        
        if len(available_files) == len(integration_files):
            self.log_test(
                "Integration Files",
                True,
                {
                    "available_count": len(available_files),
                    "total_count": len(integration_files),
                    "files": available_files
                }
            )
        else:
            self.log_test(
                "Integration Files",
                False,
                {
                    "available_count": len(available_files),
                    "total_count": len(integration_files),
                    "missing_count": len(integration_files) - len(available_files),
                    "files": available_files
                }
            )

    def run_all_tests(self):
        """Run all simple server tests"""
        print("🚀 Starting Simple Server Tests")
        print("=" * 50)
        
        self.test_database_connectivity()
        self.test_oauth_database_connectivity()
        self.test_environment_file()
        self.test_api_file_structure()
        self.test_service_dashboard()
        self.test_integration_files()
        
        # Calculate summary
        total = self.results["summary"]["total"]
        passed = self.results["summary"]["passed"]
        success_rate = (passed / total * 100) if total > 0 else 0

        self.results["summary"]["success_rate"] = success_rate

        # Print summary
        print("\n" + "=" * 50)
        print("📊 Test Summary")
        print(f"Total Tests: {total}")
        print(f"Passed: {passed}")
        print(f"Failed: {self.results['summary']['failed']}")
        print(f"Success Rate: {success_rate:.1f}%")

        if success_rate >= 90:
            print("\n🎉 Platform Status: EXCELLENT")
        elif success_rate >= 75:
            print("\n✅ Platform Status: VERY GOOD")
        elif success_rate >= 60:
            print("\n👍 Platform Status: GOOD")
        else:
            print("\n⚠️  Platform Status: NEEDS IMPROVEMENT")

        return self.results

    def save_results(self, filename: str = "simple_server_test_results.json"):
        """Save test results to file"""
        with open(filename, "w") as f:
            json.dump(self.results, f, indent=2)
        print(f"\n📄 Results saved to: {filename}")


def main():
    """Main execution function"""
    tester = SimpleServerTest()
    results = tester.run_all_tests()
    tester.save_results()


if __name__ == "__main__":
    main()