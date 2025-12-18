#!/usr/bin/env python3
"""
OAuth Configuration Assistant
Interactive helper for setting up OAuth credentials
"""

import os
from pathlib import Path
from typing import Dict, List
from dotenv import load_dotenv

# Load environment variables from .env file
env_path = Path(__file__).parent / ".env"
load_dotenv(env_path)

def check_env_var(var_name: str) -> bool:
    """Check if environment variable is set and not a placeholder"""
    value = os.getenv(var_name)
    if not value:
        return False
    # Check for common placeholder patterns
    lower_val = value.lower()
    if "your_" in lower_val and "_here" in lower_val:
        return False
    return True

def get_oauth_status() -> Dict[str, Dict]:
    """Get OAuth configuration status for all integrations"""
    
    integrations = {
        "Google (Gmail, Calendar, Drive)": {
            "priority": 1,
            "business_value": "$220K/year",
            "time": "30-45 min",
            "vars": ["GOOGLE_CLIENT_ID", "GOOGLE_CLIENT_SECRET", "GOOGLE_REDIRECT_URI"],
            "guide_section": "1. Google Workspace"
        },
        "Salesforce": {
            "priority": 2,
            "business_value": "$100K/year",
            "time": "20-30 min",
            "vars": ["SALESFORCE_CLIENT_ID", "SALESFORCE_CLIENT_SECRET", "SALESFORCE_REDIRECT_URI"],
            "guide_section": "2. Salesforce"
        },
        "Microsoft (Outlook, OneDrive, Teams)": {
            "priority": 3,
            "business_value": "$120K/year",
            "time": "30-45 min",
            "vars": ["MICROSOFT_CLIENT_ID", "MICROSOFT_CLIENT_SECRET", "MICROSOFT_REDIRECT_URI"],
            "guide_section": "6. Microsoft"
        },
        "Slack": {
            "priority": 4,
            "business_value": "$68K/year",
            "time": "15-20 min",
            "vars": ["SLACK_CLIENT_ID", "SLACK_CLIENT_SECRET", "SLACK_REDIRECT_URI"],
            "guide_section": "3. Slack"
        },
        "GitHub": {
            "priority": 5,
            "business_value": "$32K/year",
            "time": "10-15 min",
            "vars": ["GITHUB_CLIENT_ID", "GITHUB_CLIENT_SECRET", "GITHUB_REDIRECT_URI"],
            "guide_section": "4. GitHub"
        },
    }
    
    for name, config in integrations.items():
        configured_vars = sum(1 for var in config["vars"] if check_env_var(var))
        total_vars = len(config["vars"])
        config["configured"] = configured_vars == total_vars
        config["partial"] = 0 < configured_vars < total_vars
        config["status"] = "✅ Ready" if config["configured"] else ("⚠️ Partial" if config["partial"] else "❌ Not Configured")
    
    return integrations

def print_status_report():
    """Print OAuth configuration status"""
    integrations = get_oauth_status()
    
    print("\n" + "="*80)
    print("OAUTH CONFIGURATION STATUS")
    print("="*80)
    print()
    
    configured = sum(1 for i in integrations.values() if i["configured"])
    total = len(integrations)
    
    print(f"Progress: {configured}/{total} integrations configured ({configured/total*100:.0f}%)")
    print()
    
    # Calculate business value
    total_value = 0
    configured_value = 0
    
    for name, config in sorted(integrations.items(), key=lambda x: x[1]["priority"]):
        value_str = config["business_value"].replace("$", "").replace("K/year", "")
        value = int(value_str) * 1000
        total_value += value
        
        if config["configured"]:
            configured_value += value
        
        print(f"{config['priority']}. {name}")
        print(f"   {config['status']}")
        print(f"   💰 Business Value: {config['business_value']}")
        print(f"   ⏱️  Est. Time: {config['time']}")
        print(f"   📖 Guide: See oauth_setup_guide.md - Section {config['guide_section']}")
        print()
    
    print("="*80)
    print("BUSINESS VALUE SUMMARY")
    print("="*80)
    print(f"✅ Configured: ${configured_value/1000:.0f}K/year")
    print(f"❌ Remaining: ${(total_value-configured_value)/1000:.0f}K/year")
    print(f"📊 Total Potential: ${total_value/1000:.0f}K/year")
    print()
    
    if configured < total:
        next_integration = next(
            (name for name, config in sorted(integrations.items(), key=lambda x: x[1]["priority"]) 
             if not config["configured"]), 
            None
        )
        if next_integration:
            config = integrations[next_integration]
            print("="*80)
            print("NEXT STEP")
            print("="*80)
            print(f"Configure: {next_integration}")
            print(f"Value: {config['business_value']}")
            print(f"Time: {config['time']}")
            print(f"Guide: oauth_setup_guide.md - Section {config['guide_section']}")
            print()
            print("Steps:")
            print(f"1. Open oauth_setup_guide.md")
            print(f"2. Follow Section {config['guide_section']}")
            print(f"3. Copy credentials to .env file")
            print(f"4. Run this script again to verify")
            print()

def check_oauth_health():
    """Check OAuth health via API"""
    import httpx
    import asyncio
    
    async def check():
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get("http://localhost:8001/api/auth/health", timeout=5.0)
                if response.status_code == 200:
                    data = response.json()
                    print("\n" + "="*80)
                    print("API OAUTH HEALTH CHECK")
                    print("="*80)
                    print()
                    for provider, configured in data.get("oauth_configured", {}).items():
                        status = "✅ Configured" if configured else "❌ Not Configured"
                        print(f"{provider.capitalize()}: {status}")
                    print()
                else:
                    print(f"\n❌ Health check failed: HTTP {response.status_code}")
        except httpx.ConnectError:
            print("\n⚠️  Backend not running. Start with: python -m uvicorn main_api_app:app --port 8001")
        except Exception as e:
            print(f"\n❌ Health check error: {e}")
    
    asyncio.run(check())

def generate_env_template():
    """Generate .env template with instructions"""
    template_path = Path(".env.oauth.template")
    env_path = Path(".env")
    
    if not env_path.exists():
        print(f"\n📝 Creating .env file from template...")
        if template_path.exists():
            import shutil
            shutil.copy(template_path, env_path)
            print(f"✅ Created .env file")
            print(f"📝 Edit .env and replace placeholder values with your actual OAuth credentials")
        else:
            print(f"❌ Template not found: {template_path}")
    else:
        print(f"\n✅ .env file already exists")

def main():
    print("\n🔐 ATOM OAuth Configuration Assistant")
    print_status_report()
    check_oauth_health()
    generate_env_template()
    
    print("\n" + "="*80)
    print("QUICK START")
    print("="*80)
    print("1. Open: oauth_setup_guide.md")
    print("2. Start with Google (highest value)")
    print("3. Follow step-by-step instructions")
    print("4. Update .env with credentials")
    print("5. Run this script to verify")
    print()
    print("For detailed help: cat oauth_setup_guide.md")
    print()

if __name__ == "__main__":
    main()
