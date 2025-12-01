"""
Comprehensive Integration Status Report Generator
Creates a detailed status report for all configured OAuth integrations
"""

import os
from dotenv import load_dotenv
import json
from datetime import datetime

# Load environment variables
load_dotenv()

def check_oauth_integration(name, client_id_var, client_secret_var, value):
    """Check if an OAuth integration is properly configured"""
    client_id = os.getenv(client_id_var, "")
    client_secret = os.getenv(client_secret_var, "")
    
    # Check if credentials are real (not placeholders)
    id_configured = client_id and not client_id.startswith("your-") and len(client_id) > 10
    secret_configured = client_secret and not client_secret.startswith("your-") and len(client_secret) > 10
    
    return {
        "name": name,
        "value": value,
        "status": "CONFIGURED" if (id_configured and secret_configured) else "MISSING",
        "client_id_set": id_configured,
        "client_secret_set": secret_configured
    }

def generate_integration_report():
    """Generate comprehensive integration status report"""
    
    # High-value OAuth integrations (from Phase 31)
    oauth_integrations = [
        ("Salesforce", "SALESFORCE_CLIENT_ID", "SALESFORCE_CLIENT_SECRET", 100),
        ("HubSpot", "HUBSPOT_CLIENT_ID", "HUBSPOT_CLIENT_SECRET", 88),
        ("Zoom", "ZOOM_CLIENT_ID", "ZOOM_CLIENT_SECRET", 32),
        ("QuickBooks", "QUICKBOOKS_CLIENT_ID", "QUICKBOOKS_CLIENT_SECRET", 35),
        ("Google", "GMAIL_CLIENT_ID", "GMAIL_CLIENT_SECRET", 220),
        ("Microsoft/Azure", "OUTLOOK_CLIENT_ID", "OUTLOOK_CLIENT_SECRET", 120),
        ("Slack", "SLACK_CLIENT_ID", "SLACK_CLIENT_SECRET", 50),
        ("GitHub", "GITHUB_CLIENT_ID", "GITHUB_CLIENT_SECRET", 40),
        ("Notion", "NOTION_CLIENT_ID", "NOTION_CLIENT_SECRET", 60),
        ("Asana", "ASANA_CLIENT_ID", "ASANA_CLIENT_SECRET", 45),
        ("Dropbox", "DROPBOX_CLIENT_ID", "DROPBOX_CLIENT_SECRET", 30),
        ("Box", "BOX_CLIENT_ID", "BOX_CLIENT_SECRET", 25),
        ("Jira", "JIRA_CLIENT_ID", "JIRA_CLIENT_SECRET", 50),
    ]
    
    results = []
    total_value = 0
    configured_count = 0
    
    print("="*80)
    print("COMPREHENSIVE INTEGRATION STATUS REPORT")
    print(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*80)
    print()
    
    for name, id_var, secret_var, value in oauth_integrations:
        result = check_oauth_integration(name, id_var, secret_var, value)
        results.append(result)
        
        status_icon = "✅" if result["status"] == "CONFIGURED" else "❌"
        print(f"{status_icon} {name:20} ${value}K/year  - {result['status']}")
        
        if result["status"] == "CONFIGURED":
            configured_count += 1
            total_value += value
    
    print()
    print("="*80)
    print(f"SUMMARY")
    print("="*80)
    print(f"Total Integrations Checked: {len(oauth_integrations)}")
    print(f"Configured: {configured_count}/{len(oauth_integrations)}")
    print(f"Business Value Unlocked: ${total_value}K/year")
    print(f"Configuration Rate: {(configured_count/len(oauth_integrations)*100):.1f}%")
    print()
    
    # API Keys (non-OAuth)
    api_keys = [
        ("OpenAI", "OPENAI_API_KEY"),
        ("DeepSeek", "DEEPSEEK_API_KEY"),
        ("Anthropic", "ANTHROPIC_API_KEY"),
        ("Google AI", "GOOGLE_API_KEY"),
        ("Linear", "LINEAR_API_KEY"),
        ("Monday", "MONDAY_API_KEY"),
        ("Trello", "TRELLO_API_KEY"),
        ("Deepgram", "DEEPGRAM_API_KEY"),
        ("Discord", "DISCORD_BOT_TOKEN"),
    ]
    
    print("API KEY STATUS (Non-OAuth)")
    print("-"*80)
    
    api_configured = 0
    for name, var in api_keys:
        value = os.getenv(var, "")
        configured = value and not value.startswith("your-") and len(value) > 10
        status_icon = "✅" if configured else "❌"
        print(f"{status_icon} {name:20} - {'CONFIGURED' if configured else 'MISSING'}")
        if configured:
            api_configured += 1
    
    print()
    print(f"API Keys Configured: {api_configured}/{len(api_keys)}")
    print()
    
    # Export JSON report
    report = {
        "generated_at": datetime.now().isoformat(),
        "oauth_integrations": results,
        "summary": {
            "total_oauth": len(oauth_integrations),
            "configured_oauth": configured_count,
            "business_value": f"${total_value}K/year",
            "configuration_rate": f"{(configured_count/len(oauth_integrations)*100):.1f}%"
        },
        "api_keys": {
            "total": len(api_keys),
            "configured": api_configured
        }
    }
    
    with open("backend/integration_status_report.json", "w") as f:
        json.dump(report, f, indent=2)
    
    print("="*80)
    print("Report saved to: backend/integration_status_report.json")
    print("="*80)
    
    return report

if __name__ == "__main__":
    generate_integration_report()
