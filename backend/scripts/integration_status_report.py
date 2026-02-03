#!/usr/bin/env python3
"""
Integration Status Report Generator
Analyzes all integrations and generates a comprehensive status report
"""

import os
import sys
from pathlib import Path

# Add project root to path
sys.path.append(str(Path(__file__).parent.parent.parent))

from dotenv import load_dotenv

load_dotenv()

def check_integration_files(integration_name):
    """Check if integration has routes and service files"""
    base_path = Path(__file__).parent.parent / "integrations"
    
    routes_file = base_path / f"{integration_name}_routes.py"
    service_file = base_path / f"{integration_name}_service.py"
    
    return {
        "has_routes": routes_file.exists(),
        "has_service": service_file.exists(),
        "routes_path": str(routes_file) if routes_file.exists() else None,
        "service_path": str(service_file) if service_file.exists() else None
    }

def check_env_vars(integration_name, required_vars):
    """Check if required environment variables are set"""
    missing = []
    present = []
    
    for var in required_vars:
        if os.getenv(var):
            present.append(var)
        else:
            missing.append(var)
    
    return {
        "present": present,
        "missing": missing,
        "complete": len(missing) == 0
    }

# Define integrations and their required environment variables
INTEGRATIONS = {
    # CRM & Sales
    "salesforce": ["SALESFORCE_CLIENT_ID", "SALESFORCE_CLIENT_SECRET"],
    "hubspot": ["HUBSPOT_CLIENT_ID", "HUBSPOT_CLIENT_SECRET"],
    
    # Project Management
    "asana": ["ASANA_CLIENT_ID", "ASANA_CLIENT_SECRET"],
    "jira": ["JIRA_CLIENT_ID", "JIRA_CLIENT_SECRET"],
    "linear": ["LINEAR_CLIENT_ID", "LINEAR_CLIENT_SECRET"],
    "monday": ["MONDAY_CLIENT_ID", "MONDAY_CLIENT_SECRET"],
    
    # Communication
    "slack": ["SLACK_CLIENT_ID", "SLACK_CLIENT_SECRET"],
    "teams": ["TEAMS_CLIENT_ID", "TEAMS_CLIENT_SECRET"],
    "discord": ["DISCORD_CLIENT_ID", "DISCORD_CLIENT_SECRET"],
    "zoom": ["ZOOM_CLIENT_ID", "ZOOM_CLIENT_SECRET"],
    "twilio": ["TWILIO_ACCOUNT_SID", "TWILIO_AUTH_TOKEN"],
    
    # Email & Calendar
    "gmail": ["GMAIL_CLIENT_ID", "GMAIL_CLIENT_SECRET"],
    "outlook": ["OUTLOOK_CLIENT_ID", "OUTLOOK_CLIENT_SECRET"],
    "google_calendar": ["GOOGLE_CALENDAR_CLIENT_ID", "GOOGLE_CALENDAR_CLIENT_SECRET"],
    "calendly": ["CALENDLY_CLIENT_ID", "CALENDLY_CLIENT_SECRET"],
    
    # Development
    "github": ["GITHUB_CLIENT_ID", "GITHUB_CLIENT_SECRET"],
    "gitlab": ["GITLAB_CLIENT_ID", "GITLAB_CLIENT_SECRET"],
    "bitbucket": ["BITBUCKET_CLIENT_ID", "BITBUCKET_CLIENT_SECRET"],
    
    # Storage
    "dropbox": ["DROPBOX_CLIENT_ID", "DROPBOX_CLIENT_SECRET"],
    "google_drive": ["GOOGLE_DRIVE_CLIENT_ID", "GOOGLE_DRIVE_CLIENT_SECRET"],
    "onedrive": ["ONEDRIVE_CLIENT_ID", "ONEDRIVE_CLIENT_SECRET"],
    "box": ["BOX_CLIENT_ID", "BOX_CLIENT_SECRET"],
    
    # Finance & Payments
    "stripe": ["STRIPE_CLIENT_ID", "STRIPE_CLIENT_SECRET"],
    "quickbooks": ["QUICKBOOKS_CLIENT_ID", "QUICKBOOKS_CLIENT_SECRET"],
    "plaid": ["PLAID_CLIENT_ID", "PLAID_SECRET"],
    "xero": ["XERO_CLIENT_ID", "XERO_CLIENT_SECRET"],
    
    # E-commerce & Marketing
    "shopify": ["SHOPIFY_API_KEY", "SHOPIFY_API_SECRET"],
    "mailchimp": ["MAILCHIMP_CLIENT_ID", "MAILCHIMP_CLIENT_SECRET"],
    
    # Customer Support
    "zendesk": ["ZENDESK_CLIENT_ID", "ZENDESK_CLIENT_SECRET"],
    "intercom": ["INTERCOM_CLIENT_ID", "INTERCOM_CLIENT_SECRET"],
    "freshdesk": ["FRESHDESK_API_KEY"],
    
    # Productivity
    "notion": ["NOTION_CLIENT_ID", "NOTION_CLIENT_SECRET"],
    "airtable": ["AIRTABLE_API_KEY"],
    "figma": ["FIGMA_CLIENT_ID", "FIGMA_CLIENT_SECRET"],
    
    # Analytics & Data
    "tableau": ["TABLEAU_CLIENT_ID", "TABLEAU_CLIENT_SECRET"],
    
    # AI & Media
    "deepgram": ["DEEPGRAM_API_KEY"],
}

def generate_report():
    """Generate comprehensive integration status report"""
    print("=" * 80)
    print("ATOM PLATFORM - INTEGRATION STATUS REPORT")
    print("=" * 80)
    print()
    
    categories = {
        "CRM & Sales": ["salesforce", "hubspot"],
        "Project Management": ["asana", "jira", "linear", "monday"],
        "Communication": ["slack", "teams", "discord", "zoom", "twilio"],
        "Email & Calendar": ["gmail", "outlook", "google_calendar", "calendly"],
        "Development": ["github", "gitlab", "bitbucket"],
        "Storage": ["dropbox", "google_drive", "onedrive", "box"],
        "Finance & Payments": ["stripe", "quickbooks", "plaid", "xero"],
        "E-commerce & Marketing": ["shopify", "mailchimp"],
        "Customer Support": ["zendesk", "intercom", "freshdesk"],
        "Productivity": ["notion", "airtable", "figma"],
        "Analytics & Data": ["tableau"],
        "AI & Media": ["deepgram"],
    }
    
    stats = {
        "total": 0,
        "with_service": 0,
        "with_routes": 0,
        "env_complete": 0,
        "ready": 0
    }
    
    for category, integrations in categories.items():
        print(f"\n{'─' * 80}")
        print(f"📁 {category}")
        print(f"{'─' * 80}")
        
        for integration in integrations:
            if integration not in INTEGRATIONS:
                continue
                
            stats["total"] += 1
            
            # Check files
            files = check_integration_files(integration)
            
            # Check env vars
            env_status = check_env_vars(integration, INTEGRATIONS[integration])
            
            # Determine status
            has_service = files["has_service"]
            has_routes = files["has_routes"]
            env_complete = env_status["complete"]
            
            if has_service:
                stats["with_service"] += 1
            if has_routes:
                stats["with_routes"] += 1
            if env_complete:
                stats["env_complete"] += 1
            
            # Overall readiness
            is_ready = has_service and has_routes and env_complete
            if is_ready:
                stats["ready"] += 1
                status_icon = "✅"
                status_text = "READY"
            elif has_service and has_routes:
                status_icon = "⚠️"
                status_text = "PARTIAL (Missing Env)"
            elif has_routes:
                status_icon = "🔶"
                status_text = "ROUTES ONLY"
            else:
                status_icon = "❌"
                status_text = "NOT IMPLEMENTED"
            
            print(f"\n  {status_icon} {integration.upper()}")
            print(f"     Status: {status_text}")
            
            if has_service:
                print(f"     Service: ✓")
            else:
                print(f"     Service: ✗")
                
            if has_routes:
                print(f"     Routes: ✓")
            else:
                print(f"     Routes: ✗")
            
            if env_complete:
                print(f"     Env Vars: ✓ ({len(env_status['present'])}/{len(INTEGRATIONS[integration])})")
            else:
                print(f"     Env Vars: ✗ ({len(env_status['present'])}/{len(INTEGRATIONS[integration])})")
                if env_status["missing"]:
                    print(f"     Missing: {', '.join(env_status['missing'][:3])}")
                    if len(env_status["missing"]) > 3:
                        print(f"              ... and {len(env_status['missing']) - 3} more")
    
    # Summary
    print(f"\n{'=' * 80}")
    print("📊 SUMMARY")
    print(f"{'=' * 80}")
    print(f"\nTotal Integrations: {stats['total']}")
    print(f"  ✅ Fully Ready:    {stats['ready']} ({stats['ready']/stats['total']*100:.1f}%)")
    print(f"  📦 With Service:   {stats['with_service']} ({stats['with_service']/stats['total']*100:.1f}%)")
    print(f"  🛣️  With Routes:    {stats['with_routes']} ({stats['with_routes']/stats['total']*100:.1f}%)")
    print(f"  🔑 Env Complete:   {stats['env_complete']} ({stats['env_complete']/stats['total']*100:.1f}%)")
    
    print(f"\n📈 Readiness Score: {stats['ready']/stats['total']*100:.1f}%")
    
    print(f"\n{'=' * 80}\n")

if __name__ == "__main__":
    generate_report()
