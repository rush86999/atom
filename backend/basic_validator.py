#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import json
from datetime import datetime
from glob import glob

def run_validation():
    """Run basic code validation"""
    print("Starting Basic Code Validation")
    print("=" * 40)

    issues = []
    recommendations = []

    # Check integrations directory
    integrations_dir = "integrations"
    if os.path.exists(integrations_dir):
        integration_files = glob(os.path.join(integrations_dir, "*.py"))
        print("Found {} integration files".format(len(integration_files)))

        # Check each integration file
        for file_path in integration_files:
            file_name = os.path.basename(file_path)
            try:
                with open(file_path, 'r') as f:
                    content = f.read()

                # Basic checks
                if 'APIRouter' not in content and 'routes' in file_name:
                    issues.append("{} missing APIRouter".format(file_name))

                if 'logger' not in content:
                    issues.append("{} missing logging".format(file_name))

            except Exception as e:
                issues.append("Error reading {}: {}".format(file_name, str(e)))
    else:
        issues.append("Integrations directory not found")

    # Check core directory
    core_dir = "core"
    if os.path.exists(core_dir):
        core_files = glob(os.path.join(core_dir, "*.py"))
        print("Found {} core files".format(len(core_files)))

        critical_files = ["config.py", "integration_loader.py"]
        for critical_file in critical_files:
            if not os.path.exists(os.path.join(core_dir, critical_file)):
                issues.append("Missing critical core file: {}".format(critical_file))
    else:
        issues.append("Core directory not found")

    # Check main API file
    main_api_file = "main_api_app.py"
    if os.path.exists(main_api_file):
        try:
            with open(main_api_file, 'r') as f:
                content = f.read()

            if "integration_loader" not in content:
                issues.append("Main API doesn't use integration_loader")

            print("Main API file analyzed")
        except Exception as e:
            issues.append("Error analyzing main API: {}".format(str(e)))
    else:
        issues.append("Main API file not found")

    # Print results
    print("\nRESULTS:")
    print("Total Issues: {}".format(len(issues)))

    if issues:
        print("\nISSUES FOUND:")
        for i, issue in enumerate(issues[:10], 1):
            print("{}. {}".format(i, issue))

        if len(issues) > 10:
            print("... and {} more issues".format(len(issues) - 10))

    # Generate recommendations
    if len(issues) > 5:
        recommendations.append("Address multiple code quality issues")
    if "missing" in " ".join(issues).lower():
        recommendations.append("Add missing logging and error handling")
    if not issues:
        recommendations.append("Code quality looks good!")

    print("\nRECOMMENDATIONS:")
    for i, rec in enumerate(recommendations, 1):
        print("{}. {}".format(i, rec))

    # Calculate health score
    health_score = max(0, 100 - (len(issues) * 5))
    print("\nHEALTH SCORE: {}/100".format(health_score))

    if health_score > 80:
        print("Status: HEALTHY")
    elif health_score > 60:
        print("Status: NEEDS IMPROVEMENT")
    else:
        print("Status: CRITICAL")

    # Save report
    report = {
        "timestamp": datetime.now().isoformat(),
        "total_issues": len(issues),
        "issues": issues,
        "recommendations": recommendations,
        "health_score": health_score
    }

    report_file = "validation_report_{}.json".format(datetime.now().strftime('%Y%m%d_%H%M%S'))
    with open(report_file, 'w') as f:
        json.dump(report, f, indent=2)

    print("\nReport saved to: {}".format(report_file))
    print("=" * 40)

    return report

if __name__ == "__main__":
    run_validation()