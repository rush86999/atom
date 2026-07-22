from fastapi import APIRouter
from integration_health_endpoints import get_integration_health

router = APIRouter()

# Stripe
@router.get("/stripe/health")
def stripe_health():
    return get_integration_health("stripe")

# Zendesk
@router.get("/zendesk/status")
@router.get("/zendesk/health")
def zendesk_health():
    return get_integration_health("zendesk")

# QuickBooks
@router.get("/quickbooks/status")
@router.get("/quickbooks/health")
def quickbooks_health():
    return get_integration_health("quickbooks")

# Xero
@router.get("/xero/status")
@router.get("/xero/health")
def xero_health():
    return get_integration_health("xero")

# Microsoft 365
@router.get("/integrations/microsoft365/health")
@router.get("/microsoft365/health")
@router.get("/microsoft365/status")
def microsoft365_health():
    return get_integration_health("microsoft365")

# Azure
@router.get("/azure/health")
def azure_health():
    return get_integration_health("azure")

# Teams
@router.get("/teams/status")
@router.get("/teams/health")
def teams_health():
    return get_integration_health("teams")

# Notion
@router.get("/notion/status")
@router.get("/notion/health")
def notion_health():
    return get_integration_health("notion")

# Slack
@router.get("/slack/status")
@router.get("/slack/health")
def slack_health():
    return get_integration_health("slack")

# Salesforce
@router.get("/salesforce/status")
@router.get("/salesforce/health")
def salesforce_health():
    return get_integration_health("salesforce")

# Linear
@router.get("/linear/status")
@router.get("/linear/health")
def linear_health():
    return get_integration_health("linear")

# GitHub
@router.get("/github/status")
@router.get("/github/health")
def github_health():
    return get_integration_health("github")

# Fly.io / NextJS generic system health
@router.get("/health")
def general_health():
    return {"status": "healthy", "environment": "development"}
