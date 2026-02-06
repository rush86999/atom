#!/usr/bin/env python
"""
Configuration Validation Script

Validates production deployment configuration and identifies security issues.
Run this before deploying to production to catch configuration errors early.
"""

import os
import sys


def validate_config():
    """Check configuration and print warnings/errors"""
    environment = os.getenv('ENVIRONMENT', 'development')
    issues = []

    # Check SECRET_KEY
    secret_key = os.getenv('SECRET_KEY', 'atom-secret-key-change-in-production')
    if secret_key == 'atom-secret-key-change-in-production':
        if environment == 'production':
            issues.append(("CRITICAL", "Using default SECRET_KEY in production",
                          "Set SECRET_KEY environment variable to a secure random value"))
        else:
            issues.append(("WARNING", "Using default SECRET_KEY in development",
                          "Set SECRET_KEY for better security (generate with: python -c 'import secrets; print(secrets.token_urlsafe(32))')"))

    # Check ENCRYPTION_KEY
    if not os.getenv('ENCRYPTION_KEY'):
        if environment == 'production':
            issues.append(("WARNING", "ENCRYPTION_KEY not set",
                          "Secrets will be stored in plaintext. Set ENCRYPTION_KEY to enable encryption at rest"))

    # Check ALLOW_DEV_TEMP_USERS
    if os.getenv('ALLOW_DEV_TEMP_USERS', 'false').lower() == 'true':
        if environment == 'production':
            issues.append(("CRITICAL", "ALLOW_DEV_TEMP_USERS is TRUE in production",
                          "Set ALLOW_DEV_TEMP_USERS=false immediately in production"))

    # Check webhook secrets
    if not os.getenv('SLACK_SIGNING_SECRET'):
        if environment == 'production':
            issues.append(("WARNING", "SLACK_SIGNING_SECRET not configured",
                          "Webhook signature verification disabled for Slack"))

    if not os.getenv('TEAMS_APP_ID'):
        if environment == 'production':
            issues.append(("WARNING", "TEAMS_APP_ID not configured",
                          "Webhook authentication disabled for Teams"))

    # Check database URL
    database_url = os.getenv('DATABASE_URL', 'sqlite:///atom_data.db')
    if environment == 'production' and database_url.startswith('sqlite:///'):
        issues.append(("WARNING", "Using SQLite in production",
                      "Consider using PostgreSQL for production deployments"))

    # Check Redis configuration
    redis_url = os.getenv('REDIS_URL')
    if not redis_url:
        if environment == 'production':
            issues.append(("INFO", "REDIS_URL not configured",
                          "Background task queue and caching will be disabled"))

    # Check LLM API keys
    if not os.getenv('OPENAI_API_KEY') and not os.getenv('ANTHROPIC_API_KEY'):
        issues.append(("WARNING", "No LLM API keys configured",
                      "AI features will not work. Set OPENAI_API_KEY or ANTHROPIC_API_KEY"))

    # Print results
    if not issues:
        print("✓ All configuration checks passed!")
        return 0

    print(f"\n{'='*70}")
    print(f"Configuration Validation ({environment} environment)")
    print(f"{'='*70}\n")

    for severity, issue, recommendation in issues:
        if severity == "CRITICAL":
            print(f"🚨 {severity}: {issue}")
        elif severity == "WARNING":
            print(f"⚠️  {severity}: {issue}")
        else:
            print(f"ℹ️  {severity}: {issue}")
        print(f"  → {recommendation}\n")

    # Exit with error code if critical issues in production
    if environment == 'production' and any(severity == "CRITICAL" for severity, _, _ in issues):
        print("🚨 CRITICAL issues detected in production! Deployment not recommended.\n")
        return 1

    return 0


if __name__ == '__main__':
    sys.exit(validate_config())
