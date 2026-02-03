"""
Audit Report Generator for All Integrations
Analyzes the codebase and configuration to generate a comprehensive audit report.
"""

import asyncio
import json
import logging
import os
from datetime import datetime
from typing import Any, Dict, List
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Import Integration Registry (ensure path is correct)
import sys

sys.path.append(os.getcwd())
from backend.integration_registry import IntegrationRegistry

# Import Universal Integration Service
try:
    from backend.integrations.universal_integration_service import (
        NATIVE_INTEGRATIONS,
        UniversalIntegrationService,
    )
except ImportError:
    # Fallback if import fails due to path issues
    sys.path.append(os.path.join(os.getcwd(), 'backend'))
    from integrations.universal_integration_service import (
        NATIVE_INTEGRATIONS,
        UniversalIntegrationService,
    )

async def audit_integrations():
    """Generates an audit report for all integrations."""

    registry = IntegrationRegistry(integrations_dir="backend/integrations")
    discovered_services = registry.discover_integrations()

    # Initialize Universal Integration Service to get supported integrations list
    universal_service = UniversalIntegrationService()

    # Define integrations to audit (combining NATIVE_INTEGRATIONS and discovered ones)
    integrations_to_audit = set(NATIVE_INTEGRATIONS)
    for service_name in discovered_services:
        # Extract potential integration name from service file name (e.g., 'slack_service' -> 'slack')
        name_part = service_name.replace('_service', '').replace('_integration', '')
        if name_part:
            integrations_to_audit.add(name_part)

    report = {
        "generated_at": datetime.now().isoformat(),
        "total_integrations_audited": len(integrations_to_audit),
        "integrations": {},
        "summary": {
            "compliant": 0,
            "partially_compliant": 0,
            "non_compliant": 0,
            "missing_credentials": 0,
            "active": 0
        }
    }

    print(f"Auditing {len(integrations_to_audit)} integrations...")

    for integration in sorted(list(integrations_to_audit)):
        status = {
            "name": integration,
            "in_universal_registry": integration in NATIVE_INTEGRATIONS,
            "has_service_file": False,
            "service_file_path": None,
            "credentials_configured": False,
            "async_support": "unknown", # Placeholder
            "compliance_status": "non_compliant"
        }

        # Check for service file existence
        # We look for {integration}_service.py or {integration}_integration.py or similar
        potential_files = [
            f"{integration}_service",
            f"{integration}_integration",
            f"atom_{integration}_integration",
            f"{integration}_enhanced_service"
        ]

        found_service = None
        for service_key, service_data in discovered_services.items():
            if service_key in potential_files or service_key == integration:
                found_service = service_data
                break

        if found_service:
            status["has_service_file"] = True
            status["service_file_path"] = found_service["file"]

            # Basic async check (very naive, reading file content for 'async def')
            try:
                with open(found_service["file"], 'r') as f:
                    content = f.read()
                    if "async def" in content:
                        status["async_support"] = "likely"
                    else:
                        status["async_support"] = "unlikely"
            except:
                status["async_support"] = "error_reading_file"

        # Check for credentials (naive check for typical env vars)
        env_vars = [
            f"{integration.upper()}_API_KEY",
            f"{integration.upper()}_ACCESS_TOKEN",
            f"{integration.upper()}_CLIENT_ID",
            f"{integration.upper()}_CLIENT_SECRET",
            f"{integration.upper()}_TOKEN",
            f"{integration.upper()}_WEBHOOK_URL"
        ]

        configured_vars = [var for var in env_vars if os.getenv(var)]
        if configured_vars:
            status["credentials_configured"] = True
            status["configured_vars"] = configured_vars

        # Determine Compliance Status
        if status["in_universal_registry"] and status["has_service_file"]:
            status["compliance_status"] = "compliant"
            report["summary"]["compliant"] += 1
        elif status["in_universal_registry"] or status["has_service_file"]:
            status["compliance_status"] = "partially_compliant"
            report["summary"]["partially_compliant"] += 1
        else:
            report["summary"]["non_compliant"] += 1

        if not status["credentials_configured"]:
            report["summary"]["missing_credentials"] += 1
        else:
            report["summary"]["active"] += 1

        report["integrations"][integration] = status

    # Output Report
    output_file = "backend/integration_audit_report.json"
    with open(output_file, "w") as f:
        json.dump(report, f, indent=2)

    print(f"\nAudit Complete. Report saved to {output_file}")

    # Print Summary to Console
    print("\n" + "="*40)
    print("INTEGRATION AUDIT SUMMARY")
    print("="*40)
    print(f"Total Integrations: {report['total_integrations_audited']}")
    print(f"Compliant (Registry + Code): {report['summary']['compliant']}")
    print(f"Partially Compliant: {report['summary']['partially_compliant']}")
    print(f"Non-Compliant: {report['summary']['non_compliant']}")
    print(f"Active (Configured): {report['summary']['active']}")
    print(f"Missing Credentials: {report['summary']['missing_credentials']}")
    print("="*40)

if __name__ == "__main__":
    asyncio.run(audit_integrations())
