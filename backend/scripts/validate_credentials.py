#!/usr/bin/env python3
"""
Credential Validator for ATOM Application
Checks which environment variables are configured and generates a status report.
"""

import os
from pathlib import Path
from typing import Dict, List, Tuple
from dotenv import load_dotenv

# Load environment variables
env_path = Path(__file__).parent.parent / ".env"
load_dotenv(env_path)

# Define required vs optional credentials
REQUIRED_VARS = {
    "NEXTAUTH_SECRET": "Required for session encryption",
    "NEXTAUTH_URL": "Required for NextAuth routing",
    "ATOM_ENCRYPTION_KEY": "Required for OAuth token encryption",
    "BYOK_ENCRYPTION_KEY": "Required for AI key encryption",
}

OPTIONAL_CATEGORIES = {
    "Core": ["NODE_ENV", "NEXT_PUBLIC_API_BASE_URL", "LOG_LEVEL"],
    "Database": ["LANCEDB_PATH", "SQLITE_PATH", "DATABASE_URL"],
    "AI Services": [
        "OPENAI_API_KEY", "ANTHROPIC_API_KEY", "DEEPSEEK_API_KEY",
        "GOOGLE_GENERATIVE_AI_API_KEY", "GLM_API_KEY"
    ],
    "Communication": [
        "SLACK_CLIENT_ID", "SLACK_CLIENT_SECRET", "ZOOM_CLIENT_ID",
        "TEAMS_CLIENT_ID", "TWILIO_ACCOUNT_SID", "SENDGRID_API_KEY"
    ],
    "Google Services": [
        "GOOGLE_CLIENT_ID", "GOOGLE_CLIENT_SECRET"
    ],
    "Project Management": [
        "ASANA_CLIENT_ID", "JIRA_CLIENT_ID", "LINEAR_CLIENT_ID",
        "NOTION_CLIENT_ID", "MONDAY_CLIENT_ID", "TRELLO_API_KEY",
        "CLICKUP_CLIENT_ID", "AIRTABLE_API_KEY"
    ],
    "CRM": [
        "SALESFORCE_CLIENT_ID", "HUBSPOT_CLIENT_ID", "ZENDESK_CLIENT_ID",
        "INTERCOM_ACCESS_TOKEN", "FRESHDESK_API_KEY"
    ],
    "Development": [
        "GITHUB_CLIENT_ID", "GITLAB_CLIENT_ID", "BITBUCKET_CLIENT_ID",
        "FIGMA_ACCESS_TOKEN"
    ],
    "Finance": [
        "STRIPE_SECRET_KEY", "QUICKBOOKS_CLIENT_ID", "XERO_CLIENT_ID",
        "PLAID_CLIENT_ID"
    ],
    "Cloud Storage": [
        "DROPBOX_CLIENT_ID", "BOX_CLIENT_ID"
    ],
    "Marketing": [
        "MAILCHIMP_API_KEY", "LINKEDIN_CLIENT_ID", "SHOPIFY_API_KEY"
    ],
    "Audio/Video": [
        "DEEPGRAM_API_KEY", "ELEVENLABS_API_KEY"
    ],
}


def check_var(var_name: str) -> bool:
    """Check if an environment variable is set and not empty."""
    value = os.getenv(var_name)
    return value is not None and value.strip() != ""


def validate_credentials() -> Dict[str, List[Tuple[str, bool]]]:
    """Validate all credentials and return status."""
    results = {
        "Required": [],
        **{category: [] for category in OPTIONAL_CATEGORIES.keys()}
    }
    
    # Check required vars
    for var, description in REQUIRED_VARS.items():
        is_set = check_var(var)
        results["Required"].append((var, is_set))
    
    # Check optional vars by category
    for category, vars_list in OPTIONAL_CATEGORIES.items():
        for var in vars_list:
            is_set = check_var(var)
            results[category].append((var, is_set))
    
    return results


def print_report(results: Dict[str, List[Tuple[str, bool]]]):
    """Print a formatted credential validation report."""
    print("=" * 80)
    print("ATOM CREDENTIAL VALIDATION REPORT")
    print("=" * 80)
    print()
    
    # Required credentials first
    print("🔒 REQUIRED CREDENTIALS")
    print("-" * 80)
    required_results = results["Required"]
    for var, is_set in required_results:
        status = "✅" if is_set else "❌"
        print(f"{status} {var:<30} {REQUIRED_VARS[var]}")
    
    all_required_set = all(is_set for _, is_set in required_results)
    if not all_required_set:
        print("\n⚠️  WARNING: Missing required credentials! Application may not function.")
    print()
    
    # Optional credentials by category
    print("🔧 OPTIONAL INTEGRATIONS")
    print("-" * 80)
    
    for category in OPTIONAL_CATEGORIES.keys():
        category_results = results[category]
        configured_count = sum(1 for _, is_set in category_results if is_set)
        total_count = len(category_results)
        
        if configured_count > 0:
            print(f"\n{category} ({configured_count}/{total_count} configured):")
            for var, is_set in category_results:
                if is_set:
                    print(f"  ✅ {var}")
            # Show unconfigured with dimmed symbol
            unconfigured = [var for var, is_set in category_results if not is_set]
            if unconfigured:
                print(f"  ⚪ {len(unconfigured)} not configured")
    
    # Summary
    print()
    print("=" * 80)
    total_configured = sum(
        sum(1 for _, is_set in results[cat] if is_set)
        for cat in results.keys()
    )
    total_vars = sum(len(results[cat]) for cat in results.keys())
    print(f"SUMMARY: {total_configured}/{total_vars} credentials configured")
    print("=" * 80)
    print()
    print("💡 Tip: Copy .env.example to .env and fill in your credentials")
    print("📖 Guide: docs/missing_credentials_guide.md")


def main():
    """Main entry point."""
    if not env_path.exists():
        print("⚠️  No .env file found!")
        print("Run: cp .env.example .env")
        print()
        return
    
    results = validate_credentials()
    print_report(results)


if __name__ == "__main__":
    main()
