"""
Blast Radius Controls for Chaos Engineering

Ensures failure injection is scoped to test environment only.
Prevents production impact through environment validation.
"""

import os
import subprocess


def assert_blast_radius():
    """
    Ensure failure is scoped to test environment only.

    Raises:
        AssertionError: If blast radius checks fail (unsafe to proceed)

    Safety checks:
    - Environment is test or development (not production)
    - Database URL contains test/dev/chaos (not production)
    - No known production endpoints in configuration
    - Hostname does not contain "prod"
    """
    # Check 1: Environment
    environment = os.getenv("ENVIRONMENT", "development")
    assert environment in ["test", "development"], \
        f"Unsafe: Environment is {environment}, not test/development"

    # Check 2: Database URL
    db_url = os.getenv("DATABASE_URL", "")
    assert "test" in db_url or "dev" in db_url, \
        f"Unsafe: Database URL appears to be production: {db_url}"

    # Check 3: No production endpoints
    production_endpoints = [
        "api.production.com",
        "prod-db.example.com",
        "production.example.com"
    ]
    for endpoint in production_endpoints:
        assert endpoint not in db_url, \
            f"Unsafe: Production endpoint in URL: {endpoint}"

    # Check 4: Network isolation (verify we're not in production network)
    hostname = subprocess.check_output(["hostname"]).decode().strip()
    assert "prod" not in hostname.lower(), \
        f"Unsafe: Running on production host: {hostname}"

    print("✓ Blast radius checks passed")


def assert_test_database_only():
    """
    Verify we're using a test database only.

    Raises:
        AssertionError: If database URL is not a test database
    """
    db_url = os.getenv("DATABASE_URL", "")
    assert "test" in db_url or "dev" in db_url or "chaos" in db_url, \
        f"Unsafe: Database URL must contain 'test', 'dev', or 'chaos': {db_url}"


def assert_environment_safe():
    """
    Verify we're in a safe environment for chaos testing.

    Raises:
        AssertionError: If environment is production or not approved for chaos testing
    """
    environment = os.getenv("ENVIRONMENT", "development")
    assert environment != "production", \
        "Unsafe: Chaos tests cannot run in production"
    assert environment in ["test", "development"], \
        f"Unsafe: Environment {environment} not approved for chaos testing"
