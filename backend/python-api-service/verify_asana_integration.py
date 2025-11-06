#!/usr/bin/env python3
"""
Asana Integration Verification Script
Verifies that all Asana integration components are properly implemented
without requiring the API server to be running.
"""

import os
import sys
import importlib.util
import logging
from typing import List, Dict, Any, Tuple

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


class AsanaIntegrationVerifier:
    """Verifies Asana integration implementation"""

    def __init__(self):
        self.base_path = os.path.dirname(os.path.abspath(__file__))
        self.results = {}

    def verify_file_exists(self, filename: str) -> bool:
        """Verify that a file exists"""
        filepath = os.path.join(self.base_path, filename)
        exists = os.path.exists(filepath)
        status = "✅" if exists else "❌"
        logger.info(f"{status} {filename}: {'Found' if exists else 'Missing'}")
        return exists

    def verify_module_import(self, module_name: str, filename: str) -> bool:
        """Verify that a module can be imported"""
        try:
            filepath = os.path.join(self.base_path, filename)
            spec = importlib.util.spec_from_file_location(module_name, filepath)
            if spec and spec.loader:
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)
                logger.info(f"✅ {module_name}: Import successful")
                return True
        except Exception as e:
            logger.error(f"❌ {module_name}: Import failed - {e}")
            return False

    def verify_class_exists(self, filename: str, class_name: str) -> bool:
        """Verify that a specific class exists in a file"""
        try:
            filepath = os.path.join(self.base_path, filename)
            spec = importlib.util.spec_from_file_location("temp_module", filepath)
            if spec and spec.loader:
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)

                if hasattr(module, class_name):
                    logger.info(f"✅ {class_name}: Class found in {filename}")
                    return True
                else:
                    logger.error(f"❌ {class_name}: Class not found in {filename}")
                    return False
        except Exception as e:
            logger.error(f"❌ {class_name}: Verification failed - {e}")
            return False

    def verify_function_exists(self, filename: str, function_name: str) -> bool:
        """Verify that a specific function exists in a file"""
        try:
            filepath = os.path.join(self.base_path, filename)
            spec = importlib.util.spec_from_file_location("temp_module", filepath)
            if spec and spec.loader:
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)

                if hasattr(module, function_name):
                    logger.info(f"✅ {function_name}: Function found in {filename}")
                    return True
                else:
                    logger.error(
                        f"❌ {function_name}: Function not found in {filename}"
                    )
                    return False
        except Exception as e:
            logger.error(f"❌ {function_name}: Verification failed - {e}")
            return False

    def verify_blueprint_exists(self, filename: str, blueprint_name: str) -> bool:
        """Verify that a Flask blueprint exists"""
        return self.verify_variable_exists(filename, blueprint_name)

    def verify_variable_exists(self, filename: str, variable_name: str) -> bool:
        """Verify that a specific variable exists in a file"""
        try:
            filepath = os.path.join(self.base_path, filename)
            spec = importlib.util.spec_from_file_location("temp_module", filepath)
            if spec and spec.loader:
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)

                if hasattr(module, variable_name):
                    logger.info(f"✅ {variable_name}: Variable found in {filename}")
                    return True
                else:
                    logger.error(
                        f"❌ {variable_name}: Variable not found in {filename}"
                    )
                    return False
        except Exception as e:
            logger.error(f"❌ {variable_name}: Verification failed - {e}")
            return False

    def verify_asana_service(self) -> Dict[str, bool]:
        """Verify Asana service implementation"""
        logger.info("🔍 Verifying Asana Service...")

        results = {}

        # Check files exist
        service_files = [
            "asana_service_real.py",
            "asana_service.py",
            "asana_service_mock.py",
        ]

        for file in service_files:
            results[f"{file}_exists"] = self.verify_file_exists(file)

        # Check module can be imported
        results["module_import"] = self.verify_module_import(
            "asana_service_real", "asana_service_real.py"
        )

        # Check key classes exist
        key_classes = ["AsanaServiceReal"]
        for cls in key_classes:
            results[f"class_{cls}"] = self.verify_class_exists(
                "asana_service_real.py", cls
            )

        # Check key functions exist
        key_functions = ["get_asana_service_real"]
        for func in key_functions:
            results[f"function_{func}"] = self.verify_function_exists(
                "asana_service_real.py", func
            )

        return results

    def verify_asana_handler(self) -> Dict[str, bool]:
        """Verify Asana handler implementation"""
        logger.info("🔍 Verifying Asana Handler...")

        results = {}

        # Check file exists
        results["file_exists"] = self.verify_file_exists("asana_handler.py")

        # Check module can be imported
        results["module_import"] = self.verify_module_import(
            "asana_handler", "asana_handler.py"
        )

        # Check blueprint exists
        results["blueprint_exists"] = self.verify_blueprint_exists(
            "asana_handler.py", "asana_bp"
        )

        # Check key functions exist
        key_functions = [
            "get_asana_client",
            "search_asana_route",
            "list_tasks",
            "create_task",
            "update_task",
            "list_projects",
            "get_sections",
            "list_teams",
            "list_users",
            "get_user_profile",
        ]

        for func in key_functions:
            results[f"function_{func}"] = self.verify_function_exists(
                "asana_handler.py", func
            )

        return results

    def verify_asana_health_handler(self) -> Dict[str, bool]:
        """Verify Asana health handler implementation"""
        logger.info("🔍 Verifying Asana Health Handler...")

        results = {}

        # Check file exists
        results["file_exists"] = self.verify_file_exists("asana_health_handler.py")

        # Check module can be imported
        results["module_import"] = self.verify_module_import(
            "asana_health_handler", "asana_health_handler.py"
        )

        # Check blueprint exists
        results["blueprint_exists"] = self.verify_blueprint_exists(
            "asana_health_handler.py", "asana_health_bp"
        )

        # Check key functions exist
        key_functions = [
            "asana_health",
            "asana_token_health",
            "asana_connection_health",
            "asana_health_summary",
        ]

        for func in key_functions:
            results[f"function_{func}"] = self.verify_function_exists(
                "asana_health_handler.py", func
            )

        return results

    def verify_asana_enhanced_api(self) -> Dict[str, bool]:
        """Verify Asana enhanced API implementation"""
        logger.info("🔍 Verifying Asana Enhanced API...")

        results = {}

        # Check file exists
        results["file_exists"] = self.verify_file_exists("asana_enhanced_api.py")

        # Check module can be imported
        results["module_import"] = self.verify_module_import(
            "asana_enhanced_api", "asana_enhanced_api.py"
        )

        # Check blueprint exists
        results["blueprint_exists"] = self.verify_blueprint_exists(
            "asana_enhanced_api.py", "asana_enhanced_bp"
        )

        return results

    def verify_main_app_integration(self) -> Dict[str, bool]:
        """Verify Asana integration in main app"""
        logger.info("🔍 Verifying Main App Integration...")

        results = {}

        # Check main app file exists
        results["main_app_exists"] = self.verify_file_exists("main_api_app.py")

        # Check for Asana imports and registration
        try:
            with open(os.path.join(self.base_path, "main_api_app.py"), "r") as f:
                content = f.read()

            # Check for Asana imports
            imports_to_check = [
                "from asana_health_handler import",
                "from asana_handler import",
                "from asana_enhanced_api import",
            ]

            for import_stmt in imports_to_check:
                if import_stmt in content:
                    logger.info(f"✅ {import_stmt}: Found in main app")
                    results[f"import_{import_stmt.split()[-1]}"] = True
                else:
                    logger.error(f"❌ {import_stmt}: Not found in main app")
                    results[f"import_{import_stmt.split()[-1]}"] = False

            # Check for blueprint registration
            registrations_to_check = [
                "asana_health_bp",
                "asana_bp",
                "asana_enhanced_bp",
            ]

            for blueprint in registrations_to_check:
                # Check for both conditional and direct registration patterns
                registration_patterns = [
                    f"app.register_blueprint({blueprint}",
                    f"register_blueprint({blueprint}",
                    f"{blueprint}, url_prefix=",
                    f'name="{blueprint.replace("_bp", "")}"',
                ]

                blueprint_registered = any(
                    pattern in content for pattern in registration_patterns
                )

                if blueprint_registered:
                    logger.info(f"✅ {blueprint}: Registered in main app")
                    results[f"registered_{blueprint}"] = True
                else:
                    logger.error(f"❌ {blueprint}: Not registered in main app")
                    results[f"registered_{blueprint}"] = False

        except Exception as e:
            logger.error(f"❌ Main app verification failed: {e}")
            results["main_app_verification"] = False

        return results

    def verify_service_registry_integration(self) -> Dict[str, bool]:
        """Verify Asana integration in service registry"""
        logger.info("🔍 Verifying Service Registry Integration...")

        results = {}

        # Check service registry file exists
        results["service_registry_exists"] = self.verify_file_exists(
            "service_registry_routes.py"
        )

        # Check for Asana service entries
        try:
            with open(
                os.path.join(self.base_path, "service_registry_routes.py"), "r"
            ) as f:
                content = f.read()

            # Check for Asana service imports
            if "from asana_service_real import" in content:
                logger.info("✅ Asana service: Imported in service registry")
                results["service_import"] = True
            else:
                logger.error("❌ Asana service: Not imported in service registry")
                results["service_import"] = False

            # Check for Asana service entries
            service_entries = ["asana_service"]

            for service in service_entries:
                if f'"{service}":' in content:
                    logger.info(f"✅ {service}: Found in service registry")
                    results[f"service_{service}"] = True
                else:
                    logger.error(f"❌ {service}: Not found in service registry")
                    results[f"service_{service}"] = False

        except Exception as e:
            logger.error(f"❌ Service registry verification failed: {e}")
            results["service_registry_verification"] = False

        return results

    def run_all_verifications(self) -> Dict[str, Dict[str, bool]]:
        """Run all verification checks"""
        logger.info("🚀 Starting Asana Integration Verification")
        logger.info("=" * 60)

        self.results = {
            "asana_service": self.verify_asana_service(),
            "asana_handler": self.verify_asana_handler(),
            "asana_health_handler": self.verify_asana_health_handler(),
            "asana_enhanced_api": self.verify_asana_enhanced_api(),
            "main_app_integration": self.verify_main_app_integration(),
            "service_registry_integration": self.verify_service_registry_integration(),
        }

        return self.results

    def generate_summary(self) -> Tuple[int, int]:
        """Generate verification summary"""
        logger.info("=" * 60)
        logger.info("📊 Asana Integration Verification Summary")
        logger.info("=" * 60)

        total_checks = 0
        passed_checks = 0

        for category, checks in self.results.items():
            category_passed = sum(checks.values())
            category_total = len(checks)

            total_checks += category_total
            passed_checks += category_passed

            status = "✅ PASS" if category_passed == category_total else "⚠️ PARTIAL"
            logger.info(f"{status} {category}: {category_passed}/{category_total}")

            # Show failed checks for this category
            if category_passed < category_total:
                for check_name, check_result in checks.items():
                    if not check_result:
                        logger.info(f"   ❌ Failed: {check_name}")

        # Overall summary
        logger.info("=" * 60)
        if passed_checks == total_checks:
            logger.info(f"🎉 ALL CHECKS PASSED: {passed_checks}/{total_checks}")
            logger.info("✅ Asana integration is fully implemented!")
        else:
            logger.info(f"📊 OVERALL: {passed_checks}/{total_checks} checks passed")
            logger.info("⚠️ Some integration components need attention")

        return passed_checks, total_checks


def main():
    """Main verification function"""
    verifier = AsanaIntegrationVerifier()
    verifier.run_all_verifications()
    passed, total = verifier.generate_summary()

    # Return appropriate exit code
    return 0 if passed == total else 1


if __name__ == "__main__":
    exit(main())
