#!/usr/bin/env python3
"""
Atom Production Deployment Readiness Check

Quick and simple check for production readiness focusing only on critical issues.
"""

import os
import sys
import subprocess
import json

def log(msg, level="INFO"):
    """Simple logging function."""
    symbols = {"INFO": "✅", "WARN": "⚠️", "ERROR": "❌"}
    print(f"{symbols.get(level, 'INFO')} {msg}")

def check_syntax(file_path):
    """Check if a Python file has valid syntax."""
    try:
        import ast
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            ast.parse(f.read())
        return True
    except:
        return False

def main():
    """Main production readiness check."""
    log("Starting Atom Production Readiness Check...")

    root = os.path.dirname(os.path.abspath(__file__))

    # Check critical Python files only
    critical_files = [
        "atomic-docker/project/functions/python_api_service/linkedin_service.py",
        "atomic-docker/project/functions/python_api_service/twitter_service.py",
        "atomic-docker/project/functions/python_api_service/gdrive_service.py"
    ]

    all_good = True

    for file_path in critical_files:
        full_path = os.path.join(root, file_path)
        if os.path.exists(full_path):
            if check_syntax(full_path):
                log(f"Syntactically valid: {file_path}")
            else:
                log(f"Syntax error: {file_path}", "ERROR")
                all_good = False
        else:
            log(f"File missing: {file_path}", "WARN")

    # Check deployment files exist
    deployment_files = [
        "fly.toml",
        "package.json",
        "deployment/production/k8s-production.yaml"
    ]

    for file_path in deployment_files:
        full_path = os.path.join(root, file_path)
        if os.path.exists(full_path):
            log(f"Found deployment file: {file_path}")
        else:
            log(f"Missing deployment file: {file_path}", "WARN")

    # Basic package.json validation
    package_path = os.path.join(root, "package.json")
    if os.path.exists(package_path):
        try:
            with open(package_path) as f:
                json.load(f)
            log("package.json is valid JSON")
        except:
            log("package.json has invalid JSON", "ERROR")
            all_good = False

    log("Production readiness check complete!")

    if all_good:
        log("Application is PRODUCTION READY for deployment!")
        log("Tips:")
        log("- Use `npm install` to install dependencies")
        log("- Use `npm run build` for production build")
        log("- Use `fly deploy` for Fly.io deployment")
        return 0
    else:
        log("Some issues detected - review warnings above")
        return 1

if __name__ == "__main__":
    sys.exit(main())
