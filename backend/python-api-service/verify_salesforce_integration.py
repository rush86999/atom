#!/usr/bin/env python3
"""
Salesforce Integration Verification Script
Verifies that all Salesforce integration components are properly implemented
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


class SalesforceIntegrationVerifier:
    """Verifies Salesforce integration implementation"""

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

    def verify_salesforce_service(self) -> Dict[str, bool]:
        """Verify Salesforce service implementation"""
        logger.info("🔍 Verifying Salesforce Service...")

        results = {}

        # Check file exists
        results["file_exists"] = self.verify_file_exists("salesforce_service.py")

        # Check module can be imported
        results["module_import"] = self.verify_module_import(
            "salesforce_service", "salesforce_service.py"
        )

        # Check key functions exist
        key_functions = [
            "get_salesforce_client",
            "list_contacts",
            "list_accounts",
            "list_opportunities",
            "create_contact",
            "create_account",
            "create_opportunity",
            "update_opportunity",
            "get_opportunity",
            "create_lead",
            "get_user_info",
            "execute_soql_query",
        ]

        for func in key_functions:
            results[f"function_{func}"] = self.verify_function_exists(
                "salesforce_service.py", func
            )

        return results

    def verify_oauth_handler(self) -> Dict[str, bool]:
        """Verify Salesforce OAuth handler implementation"""
        logger.info("🔍 Verifying Salesforce OAuth Handler...")

        results = {}

        # Check file exists
        results["file_exists"] = self.verify_file_exists("auth_handler_salesforce.py")

        # Check module can be imported
        results["module_import"] = self.verify_module_import(
            "auth_handler_salesforce", "auth_handler_salesforce.py"
        )

        # Check key classes exist
        key_classes = [
            "SalesforceOAuthHandler",
            "SalesforceOAuthConfig",
            "SalesforceTokenInfo",
        ]
        for cls in key_classes:
            results[f"class_{cls}"] = self.verify_class_exists(
                "auth_handler_salesforce.py", cls
            )

        # Check blueprint exists
        results["blueprint_exists"] = self.verify_blueprint_exists(
            "auth_handler_salesforce.py", "salesforce_auth_bp"
        )

        # Check key functions exist
        key_functions = [
            "salesforce_authorize",
            "salesforce_callback",
            "salesforce_refresh",
            "salesforce_revoke",
            "salesforce_health",
        ]

        for func in key_functions:
            results[f"function_{func}"] = self.verify_function_exists(
                "auth_handler_salesforce.py", func
            )

        return results

    def verify_database_handler(self) -> Dict[str, bool]:
        """Verify Salesforce database handler implementation"""
        logger.info("🔍 Verifying Salesforce Database Handler...")

        results = {}

        # Check file exists
        results["file_exists"] = self.verify_file_exists("db_oauth_salesforce.py")

        # Check module can be imported
        results["module_import"] = self.verify_module_import(
            "db_oauth_salesforce", "db_oauth_salesforce.py"
        )

        # Check key functions exist
        key_functions = [
            "init_salesforce_oauth_table",
            "store_salesforce_tokens",
            "get_user_salesforce_tokens",
            "refresh_user_salesforce_tokens",
            "revoke_user_salesforce_tokens",
            "list_user_salesforce_integrations",
            "cleanup_expired_tokens",
        ]

        for func in key_functions:
            results[f"function_{func}"] = self.verify_function_exists(
                "db_oauth_salesforce.py", func
            )

        return results

    def verify_api_handlers(self) -> Dict[str, bool]:
        """Verify Salesforce API handlers implementation"""
        logger.info("🔍 Verifying Salesforce API Handlers...")

        results = {}

        # Check handler files exist
        handler_files = [
            "salesforce_handler.py",
            "salesforce_health_handler.py",
            "salesforce_enhanced_api.py",
        ]

        for file in handler_files:
            results[f"{file}_exists"] = self.verify_file_exists(file)

        # Check blueprints exist
        blueprints = [
            ("salesforce_handler.py", "salesforce_bp"),
            ("salesforce_health_handler.py", "salesforce_health_bp"),
            ("salesforce_enhanced_api.py", "salesforce_enhanced_bp"),
        ]

        for file, blueprint in blueprints:
            results[f"{blueprint}_exists"] = self.verify_blueprint_exists(
                file, blueprint
            )

        return results

    def verify_main_app_integration(self) -> Dict[str, bool]:
        """Verify Salesforce integration in main app"""
        logger.info("🔍 Verifying Main App Integration...")

        results = {}

        # Check main app file exists
        results["main_app_exists"] = self.verify_file_exists("main_api_app.py")

        # Check for Salesforce imports and registration
        try:
            with open(os.path.join(self.base_path, "main_api_app.py"), "r") as f:
                content = f.read()

            # Check for Salesforce imports
            imports_to_check = [
                "from auth_handler_salesforce import",
                "from salesforce_handler import",
                "from salesforce_health_handler import",
                "from salesforce_enhanced_api import",
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
                "salesforce_auth_bp",
                "salesforce_bp",
                "salesforce_health_bp",
                "salesforce_enhanced_bp",
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
        """Verify Salesforce integration in service registry"""
        logger.info("🔍 Verifying Service Registry Integration...")

        results = {}

        # Check service registry file exists
        results["service_registry_exists"] = self.verify_file_exists(
            "service_registry_routes.py"
        )

        # Check for Salesforce service entries
        try:
            with open(
                os.path.join(self.base_path, "service_registry_routes.py"), "r"
            ) as f:
                content = f.read()

            # Check for Salesforce service imports
            if "from salesforce_service import" in content:
                logger.info("✅ Salesforce service: Imported in service registry")
                results["service_import"] = True
            else:
                logger.error("❌ Salesforce service: Not imported in service registry")
                results["service_import"] = False

            # Check for Salesforce service entries
            service_entries = [
                "salesforce_service",
                "auth_handler_salesforce",
                "salesforce_enhanced_api",
                "salesforce_handler",
            ]

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

    def verify_comprehensive_integration(self) -> Dict[str, bool]:
        """Verify Salesforce integration in comprehensive API"""
        logger.info("🔍 Verifying Comprehensive Integration API...")

        results = {}

        # Check comprehensive API file exists
        results["comprehensive_api_exists"] = self.verify_file_exists(
            "comprehensive_integration_api.py"
        )

        # Check for Salesforce integration
        try:
            with open(
                os.path.join(self.base_path, "comprehensive_integration_api.py"), "r"
            ) as f:
                content = f.read()

            # Check for Salesforce imports
            if "from salesforce_service import" in content:
                logger.info("✅ Salesforce service: Imported in comprehensive API")
                results["comprehensive_import"] = True
            else:
                logger.error("❌ Salesforce service: Not imported in comprehensive API")
                results["comprehensive_import"] = False

            # Check for Salesforce endpoints
            endpoints_to_check = [
                "/api/integrations/salesforce/add",
                "/api/integrations/salesforce/status",
                "/api/integrations/salesforce/sync",
                "/api/integrations/salesforce/search",
            ]

            for endpoint in endpoints_to_check:
                if endpoint in content:
                    logger.info(f"✅ {endpoint}: Found in comprehensive API")
                    results[f"endpoint_{endpoint.split('/')[-1]}"] = True
                else:
                    logger.error(f"❌ {endpoint}: Not found in comprehensive API")
                    results[f"endpoint_{endpoint.split('/')[-1]}"] = False

        except Exception as e:
            logger.error(f"❌ Comprehensive API verification failed: {e}")
            results["comprehensive_verification"] = False

        return results

    def run_all_verifications(self) -> Dict[str, Dict[str, bool]]:
        """Run all verification checks"""
        logger.info("🚀 Starting Salesforce Integration Verification")
        logger.info("=" * 60)

        self.results = {
            "salesforce_service": self.verify_salesforce_service(),
            "oauth_handler": self.verify_oauth_handler(),
            "database_handler": self.verify_database_handler(),
            "api_handlers": self.verify_api_handlers(),
            "main_app_integration": self.verify_main_app_integration(),
            "service_registry_integration": self.verify_service_registry_integration(),
            "comprehensive_integration": self.verify_comprehensive_integration(),
        }

        return self.results

    def generate_summary(self) -> Tuple[int, int]:
        """Generate verification summary"""
        logger.info("=" * 60)
        logger.info("📊 Salesforce Integration Verification Summary")
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
            logger.info("✅ Salesforce integration is fully implemented!")
        else:
            logger.info(f"📊 OVERALL: {passed_checks}/{total_checks} checks passed")
            logger.info("⚠️ Some integration components need attention")

        return passed_checks, total_checks


def main():
    """Main verification function"""
    verifier = SalesforceIntegrationVerifier()
    verifier.run_all_verifications()
    passed, total = verifier.generate_summary()

    # Return appropriate exit code
    return 0 if passed == total else 1


if __name__ == "__main__":
    exit(main())
