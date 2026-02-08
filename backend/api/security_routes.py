"""
Security Routes
Provides security health checks and configuration validation.
"""

import logging
import os
from typing import List
from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from core.base_routes import BaseAPIRouter
from core.database import get_db
from core.config import get_config
from core.app_secrets import get_secret_manager

router = BaseAPIRouter(prefix="/api/security", tags=["security"])
logger = logging.getLogger(__name__)


# Response Models
class SecurityIssue(BaseModel):
    """Security issue found during validation"""
    severity: str = Field(..., description="Severity level: critical, warning, info")
    issue: str = Field(..., description="Issue identifier")
    message: str = Field(..., description="Human-readable description")
    recommendation: str = Field(..., description="Recommended fix")


class SecurityConfigurationResponse(BaseModel):
    """Security configuration check response"""
    status: str = Field(..., description="Overall status: healthy, warning, critical")
    issues: List[SecurityIssue] = Field(default_factory=list)
    config: dict = Field(default_factory=dict)


class SecretsSecurityResponse(BaseModel):
    """Secrets storage security status"""
    encryption_enabled: bool
    storage_type: str
    secrets_count: int
    environment: str


class WebhookSecurityStatus(BaseModel):
    """Webhook security configuration status"""
    slack_configured: bool
    teams_configured: bool
    gmail_configured: bool
    environment: str
    warnings: List[str] = Field(default_factory=list)


@router.get("/configuration", response_model=SecurityConfigurationResponse)
async def security_configuration_check():
    """
    Check security configuration status.

    Returns:
        - status: Overall security status (healthy, warning, critical)
        - issues: List of security issues found
        - config: Current security configuration
    """
    from sqlalchemy.orm import Session
    from core.database import SessionLocal

    config = get_config()
    issues = []
    environment = os.getenv('ENVIRONMENT', 'development')

    # Check SECRET_KEY
    if config.security.secret_key == "atom-secret-key-change-in-production":
        if environment == 'production':
            issues.append(SecurityIssue(
                severity="critical",
                issue="default_secret_key",
                message="Using default SECRET_KEY in production",
                recommendation="Set SECRET_KEY environment variable to a secure random value"
            ))
        else:
            issues.append(SecurityIssue(
                severity="warning",
                issue="default_secret_key",
                message="Using default SECRET_KEY in development",
                recommendation="Set SECRET_KEY environment variable for better security"
            ))

    # Check ENCRYPTION_KEY
    if not config.security.encryption_key:
        if environment == 'production':
            issues.append(SecurityIssue(
                severity="warning",
                issue="missing_encryption_key",
                message="ENCRYPTION_KEY not set in production",
                recommendation="Set ENCRYPTION_KEY to enable secrets encryption at rest"
            ))

    # Check ALLOW_DEV_TEMP_USERS
    if config.security.allow_dev_temp_users:
        if environment == 'production':
            issues.append(SecurityIssue(
                severity="critical",
                issue="dev_temp_users_enabled",
                message="ALLOW_DEV_TEMP_USERS is TRUE in production",
                recommendation="Set ALLOW_DEV_TEMP_USERS=false in production immediately"
            ))
        else:
            issues.append(SecurityIssue(
                severity="info",
                issue="dev_temp_users_enabled",
                message="Development temporary users enabled",
                recommendation="This is acceptable for development but must be disabled in production"
            ))

    # Check webhook secrets
    slack_secret = os.getenv('SLACK_SIGNING_SECRET')
    if not slack_secret:
        if environment == 'production':
            issues.append(SecurityIssue(
                severity="warning",
                issue="missing_slack_secret",
                message="SLACK_SIGNING_SECRET not configured",
                recommendation="Set SLACK_SIGNING_SECRET for webhook signature verification"
            ))

    # Determine overall status
    if any(issue.severity == "critical" for issue in issues):
        status = "critical"
    elif any(issue.severity == "warning" for issue in issues):
        status = "warning"
    else:
        status = "healthy"

    # Log security check
    logger.info(f"Security configuration check: {status} ({len(issues)} issues)")

    return SecurityConfigurationResponse(
        status=status,
        issues=issues,
        config={
            "environment": environment,
            "cors_origins": config.security.cors_origins,
            "jwt_expiration": config.security.jwt_expiration,
            "allow_dev_temp_users": config.security.allow_dev_temp_users
        }
    )


@router.get("/secrets", response_model=SecretsSecurityResponse)
async def secrets_security_status():
    """
    Get security status of secrets storage.

    Returns:
        - encryption_enabled: Whether encryption is active
        - storage_type: Type of storage (encrypted or plaintext)
        - secrets_count: Number of secrets in storage
        - environment: Current environment
    """
    secret_manager = get_secret_manager()
    status = secret_manager.get_security_status()

    return SecretsSecurityResponse(**status)


@router.get("/webhooks", response_model=WebhookSecurityStatus)
async def webhook_security_status():
    """
    Check webhook security configuration.

    Returns:
        - slack_configured: Whether Slack signing secret is set
        - teams_configured: Whether Teams auth is configured
        - gmail_configured: Whether Gmail verification is configured
        - environment: Current environment
        - warnings: List of security warnings
    """
    environment = os.getenv('ENVIRONMENT', 'development')
    warnings = []

    slack_configured = bool(os.getenv('SLACK_SIGNING_SECRET'))
    teams_configured = bool(os.getenv('TEAMS_APP_ID'))
    gmail_configured = bool(os.getenv('GMAIL_API_KEY'))

    # Generate warnings based on environment
    if environment == 'production':
        if not slack_configured:
            warnings.append("Slack webhook signature verification disabled in production")
        if not teams_configured:
            warnings.append("Teams webhook authentication not configured in production")
        if not gmail_configured:
            warnings.append("Gmail webhook verification not configured in production")
    else:
        if not slack_configured:
            warnings.append("Slack webhook signature verification disabled (development mode)")
        if not teams_configured:
            warnings.append("Teams webhook authentication not configured (development mode)")
        if not gmail_configured:
            warnings.append("Gmail webhook verification not configured (development mode)")

    return WebhookSecurityStatus(
        slack_configured=slack_configured,
        teams_configured=teams_configured,
        gmail_configured=gmail_configured,
        environment=environment,
        warnings=warnings
    )


@router.get("/health")
async def security_health_check():
    """
    Quick health check for security systems.

    Returns overall security system health status.
    """
    config = get_config()
    secret_manager = get_secret_manager()
    environment = os.getenv('ENVIRONMENT', 'development')

    # Determine health
    is_healthy = True

    if environment == 'production':
        # Production has stricter requirements
        if config.security.secret_key == "atom-secret-key-change-in-production":
            is_healthy = False
        if config.security.allow_dev_temp_users:
            is_healthy = False

    return {
        "status": "healthy" if is_healthy else "unhealthy",
        "environment": environment,
        "encryption_enabled": secret_manager.get_security_status()['encryption_enabled']
    }
