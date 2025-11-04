#!/usr/bin/env python3
"""
Simplified Production Deployment Script for Atom AI Assistant

This script creates all necessary configuration files and scripts
for production deployment of the OAuth authentication system.

Usage:
    python deploy_production_simple.py
"""

import os
import json
import secrets
from datetime import datetime


def create_oauth_config():
    """Create OAuth configuration for remaining services"""
    config = {
        "production_domain": "your-production-domain.com",
        "remaining_services": ["outlook", "teams", "github"],
        "oauth_config": {
            "outlook": {
                "client_id": "YOUR_OUTLOOK_CLIENT_ID",
                "client_secret": "YOUR_OUTLOOK_CLIENT_SECRET",
                "redirect_uri": "https://your-production-domain.com/api/auth/outlook/oauth2callback",
                "scopes": [
                    "https://graph.microsoft.com/Mail.Read",
                    "https://graph.microsoft.com/Calendars.Read",
                ],
                "setup_url": "https://portal.azure.com",
            },
            "teams": {
                "client_id": "YOUR_TEAMS_CLIENT_ID",
                "client_secret": "YOUR_TEAMS_CLIENT_SECRET",
                "redirect_uri": "https://your-production-domain.com/api/auth/teams/oauth2callback",
                "scopes": ["https://graph.microsoft.com/Team.ReadBasic.All"],
                "setup_url": "https://portal.azure.com",
            },
            "github": {
                "client_id": "YOUR_GITHUB_CLIENT_ID",
                "client_secret": "YOUR_GITHUB_CLIENT_SECRET",
                "redirect_uri": "https://your-production-domain.com/api/auth/github/oauth2callback",
                "scopes": ["repo", "user", "read:org"],
                "setup_url": "https://github.com/settings/developers",
            },
        },
    }

    with open("oauth_production_config.json", "w") as f:
        json.dump(config, f, indent=2)

    print("✅ Created oauth_production_config.json")


def create_production_env():
    """Create production environment file"""
    env_content = f"""# Production Environment Configuration
# Generated: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}

# Application Settings
FLASK_ENV=production
DEBUG=False
SECRET_KEY={secrets.token_urlsafe(32)}

# Server Configuration
HOST=0.0.0.0
PORT=5058
PRODUCTION_DOMAIN=your-production-domain.com

# Database Configuration
DATABASE_URL=sqlite:///./data/atom_production.db

# Security Configuration
ATOM_OAUTH_ENCRYPTION_KEY={secrets.token_urlsafe(32)}
CSRF_ENABLED=True
SESSION_SECURE=True

# OAuth Services - Update with real credentials
GOOGLE_CLIENT_ID=your_google_client_id
GOOGLE_CLIENT_SECRET=your_google_client_secret
SLACK_CLIENT_ID=your_slack_client_id
SLACK_CLIENT_SECRET=your_slack_client_secret
TRELLO_API_KEY=your_trello_api_key
TRELLO_API_SECRET=your_trello_api_secret
ASANA_CLIENT_ID=your_asana_client_id
ASANA_CLIENT_SECRET=your_asana_client_secret
NOTION_CLIENT_ID=your_notion_client_id
NOTION_CLIENT_SECRET=your_notion_client_secret
DROPBOX_CLIENT_ID=your_dropbox_client_id
DROPBOX_CLIENT_SECRET=your_dropbox_client_secret

# Remaining OAuth Services - TODO: Configure
OUTLOOK_CLIENT_ID=YOUR_OUTLOOK_CLIENT_ID
OUTLOOK_CLIENT_SECRET=YOUR_OUTLOOK_CLIENT_SECRET
TEAMS_CLIENT_ID=YOUR_TEAMS_CLIENT_ID
TEAMS_CLIENT_SECRET=YOUR_TEAMS_CLIENT_SECRET
GITHUB_CLIENT_ID=YOUR_GITHUB_CLIENT_ID
GITHUB_CLIENT_SECRET=YOUR_GITHUB_CLIENT_SECRET

# AI Provider Configuration
OPENAI_API_KEY=your_openai_api_key
ANTHROPIC_API_KEY=your_anthropic_api_key

# Monitoring
ENABLE_METRICS=True
LOG_LEVEL=INFO
HEALTH_CHECK_INTERVAL=30
"""

    with open(".env.production", "w") as f:
        f.write(env_content)

    print("✅ Created .env.production")


def create_setup_script():
    """Create OAuth setup script"""
    script_content = f"""#!/bin/bash
# OAuth Service Setup Script
# Generated: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}

echo "🚀 Setting up OAuth Services for Production"
echo "=========================================="

echo ""
echo "📋 Remaining Services to Configure:"
echo "   - Microsoft Outlook"
echo "   - Microsoft Teams"
echo "   - GitHub"
echo ""

echo "🔧 Setup Instructions:"
echo ""
echo "1. Microsoft Azure (Outlook & Teams):"
echo "   - Go to: https://portal.azure.com"
echo "   - Create app registration"
echo "   - Add redirect URIs:"
echo "     - https://your-production-domain.com/api/auth/outlook/oauth2callback"
echo "     - https://your-production-domain.com/api/auth/teams/oauth2callback"
echo "   - Configure API permissions:"
echo "     - Mail.Read, Calendars.Read, Team.ReadBasic.All"
echo ""

echo "2. GitHub:"
echo "   - Go to: https://github.com/settings/developers"
echo "   - Create OAuth App"
echo "   - Set callback URL:"
echo "     - https://your-production-domain.com/api/auth/github/oauth2callback"
echo "   - Configure scopes: repo, user, read:org"
echo ""

echo "📝 Update .env.production with:"
echo "OUTLOOK_CLIENT_ID=your_microsoft_client_id"
echo "OUTLOOK_CLIENT_SECRET=your_microsoft_client_secret"
echo "TEAMS_CLIENT_ID=your_teams_client_id"
echo "TEAMS_CLIENT_SECRET=your_teams_client_secret"
echo "GITHUB_CLIENT_ID=your_github_client_id"
echo "GITHUB_CLIENT_SECRET=your_github_client_secret"
echo ""

echo "✅ After configuration:"
echo "   - Restart backend server"
echo "   - Run: python test_oauth_validation.py"
echo "   - Verify all 10 services show as connected"
echo ""

echo "🎉 Setup script completed"
"""

    with open("setup_oauth.sh", "w") as f:
        f.write(script_content)

    # Make executable
    os.chmod("setup_oauth.sh", 0o755)
    print("✅ Created setup_oauth.sh")


def create_backup_script():
    """Create database backup script"""
    script_content = f"""#!/bin/bash
# Database Backup Script
# Generated: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}

BACKUP_DIR="./backups"
DATE=$(date +%Y%m%d_%H%M%S)
DB_FILE="./data/atom_production.db"

echo "💾 Starting database backup..."

# Create backup directory
mkdir -p "$BACKUP_DIR"

# Backup SQLite database
if [ -f "$DB_FILE" ]; then
    sqlite3 "$DB_FILE" ".backup $BACKUP_DIR/atom_backup_$DATE.db"
    echo "✅ Database backed up to: $BACKUP_DIR/atom_backup_$DATE.db"
else
    echo "❌ Database file not found: $DB_FILE"
    exit 1
fi

# Backup configuration files
tar -czf "$BACKUP_DIR/config_backup_$DATE.tar.gz" \\
    .env.production \\
    oauth_production_config.json

echo "✅ Configuration files backed up"

# Clean up old backups (keep last 7 days)
find "$BACKUP_DIR" -name "*.db" -mtime +7 -delete
find "$BACKUP_DIR" -name "*.tar.gz" -mtime +7 -delete

echo "🧹 Old backups cleaned up"
echo "🎉 Backup completed successfully"
"""

    with open("backup_database.sh", "w") as f:
        f.write(script_content)

    # Make executable
    os.chmod("backup_database.sh", 0o755)
    print("✅ Created backup_database.sh")


def create_deployment_plan():
    """Create deployment plan"""
    plan = {
        "deployment_id": f"atom_production_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
        "timestamp": datetime.now().isoformat(),
        "status": "configuration_ready",
        "current_state": {
            "oauth_services_connected": 7,
            "oauth_services_total": 10,
            "remaining_services": ["outlook", "teams", "github"],
            "backend_operational": True,
            "security_implemented": True,
        },
        "deployment_steps": [
            {
                "step": 1,
                "name": "Configure OAuth Services",
                "description": "Setup Microsoft Azure and GitHub OAuth applications",
                "status": "pending",
                "estimated_time": "1-2 hours",
            },
            {
                "step": 2,
                "name": "Setup Production Domain",
                "description": "Configure DNS and SSL/TLS certificates",
                "status": "pending",
                "estimated_time": "1 hour",
            },
            {
                "step": 3,
                "name": "Deploy to Production",
                "description": "Deploy application to production server",
                "status": "pending",
                "estimated_time": "30 minutes",
            },
            {
                "step": 4,
                "name": "Configure Monitoring",
                "description": "Setup health monitoring and alerting",
                "status": "pending",
                "estimated_time": "1 hour",
            },
            {
                "step": 5,
                "name": "Setup Backups",
                "description": "Configure automated database backups",
                "status": "pending",
                "estimated_time": "30 minutes",
            },
        ],
        "success_criteria": [
            "10/10 OAuth services operational",
            "Production domain accessible via HTTPS",
            "All health endpoints responding correctly",
            "Monitoring and alerting configured",
            "Automated backups running",
        ],
    }

    with open("production_deployment_plan.json", "w") as f:
        json.dump(plan, f, indent=2)

    print("✅ Created production_deployment_plan.json")


def create_monitoring_script():
    """Create simple monitoring script"""
    script_content = '''#!/usr/bin/env python3
"""
Simple Service Monitoring Script

Checks health endpoints and logs status.

Usage:
    python monitor_services.py
"""

import requests
import time
import json
from datetime import datetime

BASE_URL = "http://localhost:5058"
ENDPOINTS = [
    "/healthz",
    "/api/services/status",
    "/api/auth/oauth-status"
]

def check_endpoint(endpoint):
    """Check a single endpoint"""
    try:
        start = time.time()
        response = requests.get(f"{BASE_URL}{endpoint}", timeout=5)
        response_time = (time.time() - start) * 1000

        return {
            "endpoint": endpoint,
            "status_code": response.status_code,
            "response_time": response_time,
            "success": response.status_code == 200,
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        return {
            "endpoint": endpoint,
            "status_code": None,
            "response_time": None,
            "success": False,
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        }

def main():
    """Main monitoring function"""
    print("🔍 Atom AI Assistant Service Monitor")
    print("=" * 40)

    results = []
    for endpoint in ENDPOINTS:
        result = check_endpoint(endpoint)
        results.append(result)

        if result["success"]:
            print(f"✅ {endpoint}: {result['response_time']:.1f}ms")
        else:
            print(f"❌ {endpoint}: {result.get('error', 'Unknown error')}")

    # Save results
    with open("monitoring_results.json", "w") as f:
        json.dump({
            "timestamp": datetime.now().isoformat(),
            "results": results
        }, f, indent=2)

    print(f"📊 Monitoring completed: {sum(1 for r in results if r['success'])}/{len(results)} endpoints OK")

if __name__ == "__main__":
    main()
'''

    with open("monitor_services.py", "w") as f:
        f.write(script_content)

    print("✅ Created monitor_services.py")


def main():
    """Main execution function"""
    print("🚀 Starting Production Deployment Setup")
    print("=" * 50)
    print(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 50)

    try:
        # Create all configuration files
        create_oauth_config()
        create_production_env()
        create_setup_script()
        create_backup_script()
        create_deployment_plan()
        create_monitoring_script()

        print("")
        print("🎉 PRODUCTION DEPLOYMENT SETUP COMPLETED")
        print("=" * 50)
        print("📁 Created Files:")
        print("   - oauth_production_config.json")
        print("   - .env.production")
        print("   - setup_oauth.sh")
        print("   - backup_database.sh")
        print("   - production_deployment_plan.json")
        print("   - monitor_services.py")
        print("")
        print("💡 Next Steps:")
        print("   1. Run: bash setup_oauth.sh")
        print("   2. Configure OAuth credentials in .env.production")
        print("   3. Deploy to production server")
        print("   4. Setup monitoring and backups")
        print("")
        print("✅ System is ready for production deployment!")

    except Exception as e:
        print(f"❌ Setup failed: {e}")
        return 1

    return 0


if __name__ == "__main__":
    exit(main())
