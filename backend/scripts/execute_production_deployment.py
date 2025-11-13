#!/usr/bin/env python3
"""
Production Deployment Execution Script for Atom AI Assistant

This script executes the complete production deployment process for the
Atom AI Assistant platform, including OAuth authentication system validation,
production environment configuration, and deployment verification.

Usage:
    python execute_production_deployment.py
"""

import os
import sys
import json
import time
import subprocess
import requests
from datetime import datetime
from typing import Dict, List, Any, Tuple


class ProductionDeployment:
    """Production deployment execution class"""

    def __init__(self):
        self.base_url = "http://localhost:5058"
        self.deployment_log = []
        self.start_time = datetime.now()
        self.deployment_status = {
            "overall": "pending",
            "steps": {},
            "timestamp": self.start_time.isoformat(),
        }

    def log_step(self, step_name: str, status: str, message: str = ""):
        """Log deployment step with timestamp"""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        log_entry = {
            "timestamp": timestamp,
            "step": step_name,
            "status": status,
            "message": message,
        }
        self.deployment_log.append(log_entry)
        self.deployment_status["steps"][step_name] = {
            "status": status,
            "message": message,
            "timestamp": timestamp,
        }

        # Print to console
        status_icon = (
            "✅" if status == "success" else "❌" if status == "failed" else "⚠️"
        )
        print(f"{status_icon} [{timestamp}] {step_name}: {message}")

    def validate_environment(self) -> bool:
        """Validate production environment prerequisites"""
        self.log_step(
            "environment_validation", "running", "Checking environment prerequisites"
        )

        checks = {
            "python_version": sys.version_info >= (3, 8),
            "required_directories": all(
                os.path.exists(dir_path)
                for dir_path in [
                    "backend",
                    "frontend-nextjs",
                    "desktop",
                    "config",
                ]
            ),
            "environment_file": os.path.exists(".env.production")
            or os.path.exists(".env"),
            "deployment_scripts": all(
                os.path.exists(script)
                for script in [
                    "production_deployment_config.py",
                    "deploy_production.sh",
                ]
            ),
        }

        all_passed = all(checks.values())

        if all_passed:
            self.log_step(
                "environment_validation", "success", "All environment prerequisites met"
            )
        else:
            failed_checks = [check for check, passed in checks.items() if not passed]
            self.log_step(
                "environment_validation",
                "failed",
                f"Failed checks: {', '.join(failed_checks)}",
            )

        return all_passed

    def start_backend_server(self) -> bool:
        """Start the backend server with production configuration"""
        self.log_step("backend_startup", "running", "Starting backend server")

        try:
            # Check if server is already running
            response = requests.get(f"{self.base_url}/healthz", timeout=5)
            if response.status_code == 200:
                self.log_step(
                    "backend_startup", "success", "Backend server already running"
                )
                return True
        except:
            pass  # Server not running, continue with startup

        try:
            # Start the server in background
            process = subprocess.Popen(
                ["python", "start_oauth_status_server.py"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                cwd=os.getcwd(),
            )

            # Wait for server to start
            time.sleep(5)

            # Verify server is running
            for attempt in range(3):
                try:
                    response = requests.get(f"{self.base_url}/healthz", timeout=5)
                    if response.status_code == 200:
                        self.log_step(
                            "backend_startup",
                            "success",
                            "Backend server started successfully",
                        )
                        return True
                except:
                    time.sleep(2)

            self.log_step("backend_startup", "failed", "Backend server failed to start")
            return False

        except Exception as e:
            self.log_step(
                "backend_startup", "failed", f"Backend startup error: {str(e)}"
            )
            return False

    def validate_oauth_system(self) -> bool:
        """Validate OAuth authentication system status"""
        self.log_step(
            "oauth_validation", "running", "Validating OAuth authentication system"
        )

        try:
            # Test comprehensive OAuth status
            response = requests.get(
                f"{self.base_url}/api/auth/oauth-status?user_id=production_test",
                timeout=10,
            )

            if response.status_code == 200:
                oauth_data = response.json()
                connected_services = oauth_data.get("connected_services", 0)
                total_services = oauth_data.get("total_services", 0)
                success_rate = (
                    connected_services / total_services if total_services > 0 else 0
                )

                if success_rate >= 0.7:  # 70% success rate required
                    self.log_step(
                        "oauth_validation",
                        "success",
                        f"OAuth system operational: {connected_services}/{total_services} services connected ({success_rate:.1%})",
                    )
                    return True
                else:
                    self.log_step(
                        "oauth_validation",
                        "failed",
                        f"OAuth system below threshold: {connected_services}/{total_services} services connected ({success_rate:.1%})",
                    )
                    return False
            else:
                self.log_step(
                    "oauth_validation",
                    "failed",
                    f"OAuth status endpoint returned HTTP {response.status_code}",
                )
                return False

        except Exception as e:
            self.log_step(
                "oauth_validation", "failed", f"OAuth validation error: {str(e)}"
            )
            return False

    def test_service_endpoints(self) -> bool:
        """Test critical service endpoints"""
        self.log_step(
            "service_endpoints", "running", "Testing critical service endpoints"
        )

        endpoints_to_test = [
            "/healthz",
            "/api/services/status",
            "/api/auth/oauth-status",
        ]

        successful_tests = 0

        for endpoint in endpoints_to_test:
            try:
                response = requests.get(f"{self.base_url}{endpoint}", timeout=10)
                if response.status_code == 200:
                    successful_tests += 1
                    self.log_step(
                        f"endpoint_{endpoint.replace('/', '_')}",
                        "success",
                        f"Endpoint {endpoint} responding correctly",
                    )
                else:
                    self.log_step(
                        f"endpoint_{endpoint.replace('/', '_')}",
                        "failed",
                        f"Endpoint {endpoint} returned HTTP {response.status_code}",
                    )
            except Exception as e:
                self.log_step(
                    f"endpoint_{endpoint.replace('/', '_')}",
                    "failed",
                    f"Endpoint {endpoint} error: {str(e)}",
                )

        success_rate = successful_tests / len(endpoints_to_test)

        if success_rate >= 0.8:  # 80% success rate required
            self.log_step(
                "service_endpoints",
                "success",
                f"Service endpoints operational: {successful_tests}/{len(endpoints_to_test)} endpoints working",
            )
            return True
        else:
            self.log_step(
                "service_endpoints",
                "failed",
                f"Service endpoints below threshold: {successful_tests}/{len(endpoints_to_test)} endpoints working",
            )
            return False

    def configure_production_environment(self) -> bool:
        """Configure production environment settings"""
        self.log_step(
            "production_config", "running", "Configuring production environment"
        )

        try:
            # Import production configuration
            sys.path.append(os.getcwd())
            from production_deployment_config import ProductionConfig

            # Validate production configuration
            validation = ProductionConfig.validate_configuration()

            if validation["valid"]:
                self.log_step(
                    "production_config",
                    "success",
                    "Production configuration validated successfully",
                )

                # Log configuration details
                config_details = []
                for component, result in validation["details"].items():
                    config_details.append(f"{component}: {result['message']}")

                self.log_step(
                    "production_config_details",
                    "info",
                    f"Configuration: {', '.join(config_details)}",
                )
                return True
            else:
                self.log_step(
                    "production_config",
                    "failed",
                    "Production configuration validation failed",
                )
                return False

        except Exception as e:
            self.log_step(
                "production_config", "failed", f"Configuration error: {str(e)}"
            )
            return False

    def generate_deployment_report(self) -> Dict[str, Any]:
        """Generate comprehensive deployment report"""
        end_time = datetime.now()
        duration = (end_time - self.start_time).total_seconds()

        # Count successful steps
        successful_steps = sum(
            1
            for step in self.deployment_status["steps"].values()
            if step["status"] == "success"
        )
        total_steps = len(self.deployment_status["steps"])
        success_rate = successful_steps / total_steps if total_steps > 0 else 0

        # Determine overall status
        if success_rate >= 0.8:
            overall_status = "success"
        elif success_rate >= 0.5:
            overall_status = "partial"
        else:
            overall_status = "failed"

        report = {
            "deployment_id": f"atom_deployment_{self.start_time.strftime('%Y%m%d_%H%M%S')}",
            "overall_status": overall_status,
            "success_rate": f"{success_rate:.1%}",
            "start_time": self.start_time.isoformat(),
            "end_time": end_time.isoformat(),
            "duration_seconds": duration,
            "total_steps": total_steps,
            "successful_steps": successful_steps,
            "failed_steps": total_steps - successful_steps,
            "steps": self.deployment_status["steps"],
            "log": self.deployment_log,
            "recommendations": self._generate_recommendations(),
        }

        return report

    def _generate_recommendations(self) -> List[str]:
        """Generate deployment recommendations based on results"""
        recommendations = []

        # Check for specific issues and provide recommendations
        steps = self.deployment_status["steps"]

        if steps.get("environment_validation", {}).get("status") == "failed":
            recommendations.append("Fix environment prerequisites before deployment")

        if steps.get("oauth_validation", {}).get("status") == "failed":
            recommendations.append(
                "Complete OAuth service configuration for remaining services"
            )

        if steps.get("service_endpoints", {}).get("status") == "failed":
            recommendations.append(
                "Ensure all critical service endpoints are operational"
            )

        if steps.get("production_config", {}).get("status") == "failed":
            recommendations.append("Review and fix production configuration settings")

        # Add general recommendations
        if not recommendations:
            recommendations.extend(
                [
                    "Deployment ready for production environment",
                    "Monitor system performance and error rates",
                    "Set up automated backups and monitoring",
                    "Configure SSL/TLS certificates for production",
                    "Implement rate limiting and security headers",
                ]
            )
        else:
            recommendations.append("Address above issues before production deployment")

        return recommendations

    def save_deployment_report(self, report: Dict[str, Any]):
        """Save deployment report to file"""
        filename = f"deployment_report_{self.start_time.strftime('%Y%m%d_%H%M%S')}.json"

        with open(filename, "w") as f:
            json.dump(report, f, indent=2)

        self.log_step(
            "report_generation", "success", f"Deployment report saved to {filename}"
        )
        return filename

    def execute_deployment(self) -> bool:
        """Execute complete production deployment process"""
        print("🚀 Starting Atom AI Assistant Production Deployment")
        print("=" * 60)
        print(f"Start Time: {self.start_time.strftime('%Y-%m-%d %H:%M:%S')}")
        print("=" * 60)

        # Execute deployment steps
        steps = [
            ("Environment Validation", self.validate_environment),
            ("Backend Server Startup", self.start_backend_server),
            ("OAuth System Validation", self.validate_oauth_system),
            ("Service Endpoint Testing", self.test_service_endpoints),
            ("Production Configuration", self.configure_production_environment),
        ]

        all_steps_successful = True

        for step_name, step_function in steps:
            print(f"\n🔧 Executing: {step_name}")
            print("-" * 40)

            success = step_function()
            if not success:
                all_steps_successful = False
                # Continue with other steps to get complete picture

        # Generate final report
        print(f"\n📊 Generating Deployment Report")
        print("-" * 40)
        report = self.generate_deployment_report()
        report_filename = self.save_deployment_report(report)

        # Print summary
        print(f"\n🎯 DEPLOYMENT SUMMARY")
        print("=" * 60)
        print(f"Overall Status: {report['overall_status'].upper()}")
        print(f"Success Rate: {report['success_rate']}")
        print(f"Duration: {report['duration_seconds']:.1f} seconds")
        print(f"Steps Completed: {report['successful_steps']}/{report['total_steps']}")
        print(f"Report: {report_filename}")

        # Print recommendations
        print(f"\n💡 RECOMMENDATIONS:")
        for recommendation in report["recommendations"]:
            print(f"  • {recommendation}")

        print("=" * 60)

        return all_steps_successful and report["overall_status"] == "success"


def main():
    """Main execution function"""
    try:
        deployment = ProductionDeployment()
        success = deployment.execute_deployment()

        if success:
            print("\n🎉 PRODUCTION DEPLOYMENT COMPLETED SUCCESSFULLY!")
            exit(0)
        else:
            print("\n⚠️  PRODUCTION DEPLOYMENT COMPLETED WITH ISSUES")
            print("    Review the deployment report and address recommendations")
            exit(1)

    except KeyboardInterrupt:
        print("\n🛑 Deployment interrupted by user")
        exit(1)
    except Exception as e:
        print(f"\n❌ Deployment failed with error: {e}")
        exit(1)


if __name__ == "__main__":
    main()
