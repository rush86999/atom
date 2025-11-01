"""
ATOM Platform - Production Configuration
Complete configuration for production deployment with OAuth setup
"""

import os
from datetime import datetime
from typing import Dict, List, Optional


class ProductionConfig:
    """Production configuration for ATOM platform"""

    # Core Platform Settings
    PLATFORM_NAME = "ATOM Platform"
    VERSION = "1.0.0"
    ENVIRONMENT = "production"

    # Server Configuration
    BACKEND_PORT = 8000
    OAUTH_PORT = 5058
    FRONTEND_PORT = 3000
    DATABASE_PORT = 5432

    # Database Configuration
    DATABASE_CONFIG = {
        "postgresql": {
            "host": os.getenv("DATABASE_HOST", "localhost"),
            "port": os.getenv("DATABASE_PORT", "5432"),
            "database": os.getenv("DATABASE_NAME", "atom_db"),
            "user": os.getenv("DATABASE_USER", "atom_user"),
            "password": os.getenv("DATABASE_PASSWORD", "secure_password"),
            "pool_size": 20,
            "max_overflow": 30,
            "pool_timeout": 30,
            "pool_recycle": 3600,
        },
        "lancedb": {
            "uri": os.getenv("LANCEDB_URI", "/data/lancedb_store"),
            "mode": "persistent",
        },
    }

    # OAuth Service Configuration
    OAUTH_SERVICES = {
        "github": {
            "client_id": os.getenv("GITHUB_CLIENT_ID", ""),
            "client_secret": os.getenv("GITHUB_CLIENT_SECRET", ""),
            "auth_url": "https://github.com/login/oauth/authorize",
            "token_url": "https://github.com/login/oauth/access_token",
            "scopes": ["repo", "user:email", "read:org"],
            "required": True,
            "setup_guide": "https://docs.github.com/en/developers/apps/building-oauth-apps/creating-an-oauth-app",
        },
        "google": {
            "client_id": os.getenv("GOOGLE_CLIENT_ID", ""),
            "client_secret": os.getenv("GOOGLE_CLIENT_SECRET", ""),
            "auth_url": "https://accounts.google.com/o/oauth2/v2/auth",
            "token_url": "https://oauth2.googleapis.com/token",
            "scopes": [
                "email",
                "profile",
                "https://www.googleapis.com/auth/calendar",
                "https://www.googleapis.com/auth/gmail.readonly",
                "https://www.googleapis.com/auth/drive",
            ],
            "required": True,
            "setup_guide": "https://developers.google.com/identity/protocols/oauth2",
        },
        "slack": {
            "client_id": os.getenv("SLACK_CLIENT_ID", ""),
            "client_secret": os.getenv("SLACK_CLIENT_SECRET", ""),
            "auth_url": "https://slack.com/oauth/v2/authorize",
            "token_url": "https://slack.com/api/oauth.v2.access",
            "scopes": ["chat:write", "channels:read", "groups:read", "users:read"],
            "required": True,
            "setup_guide": "https://api.slack.com/authentication/oauth-v2",
        },
        "dropbox": {
            "client_id": os.getenv("DROPBOX_CLIENT_ID", ""),
            "client_secret": os.getenv("DROPBOX_CLIENT_SECRET", ""),
            "auth_url": "https://www.dropbox.com/oauth2/authorize",
            "token_url": "https://api.dropboxapi.com/oauth2/token",
            "scopes": [
                "files.metadata.read",
                "files.content.read",
                "files.content.write",
            ],
            "required": False,
            "setup_guide": "https://developers.dropbox.com/oauth-guide",
        },
        "trello": {
            "client_id": os.getenv("TRELLO_CLIENT_ID", ""),
            "client_secret": os.getenv("TRELLO_CLIENT_SECRET", ""),
            "auth_url": "https://trello.com/1/authorize",
            "token_url": "https://trello.com/1/OAuthGetAccessToken",
            "scopes": ["read", "write"],
            "required": False,
            "setup_guide": "https://developer.atlassian.com/cloud/trello/guides/rest-api/authorization/",
        },
    }

    # API Keys Configuration
    API_KEYS = {
        "openai": {
            "key": os.getenv("OPENAI_API_KEY", ""),
            "required": True,
            "purpose": "Natural language processing and workflow generation",
        },
        "deepgram": {
            "key": os.getenv("DEEPGRAM_API_KEY", ""),
            "required": False,
            "purpose": "Voice transcription and speech recognition",
        },
        "anthropic": {
            "key": os.getenv("ANTHROPIC_API_KEY", ""),
            "required": False,
            "purpose": "Alternative AI provider for workflow generation",
        },
    }

    # Security Configuration
    SECURITY = {
        "jwt_secret": os.getenv("JWT_SECRET", "change_this_in_production"),
        "encryption_key": os.getenv("ENCRYPTION_KEY", "change_this_in_production"),
        "cors_origins": [
            "http://localhost:3000",
            "https://yourdomain.com",
            "https://app.yourdomain.com",
        ],
        "rate_limiting": {"requests_per_minute": 100, "burst_limit": 50},
    }

    # Monitoring & Logging
    MONITORING = {
        "log_level": "INFO",
        "log_file": "/var/log/atom/atom.log",
        "metrics_enabled": True,
        "health_check_interval": 30,
        "performance_monitoring": True,
    }

    # Workflow Configuration
    WORKFLOW = {
        "max_concurrent_workflows": 100,
        "workflow_timeout_seconds": 300,
        "retry_attempts": 3,
        "default_timezone": "UTC",
    }


class OAuthSetupGuide:
    """OAuth setup instructions for production deployment"""

    @staticmethod
    def generate_setup_instructions() -> Dict[str, str]:
        """Generate OAuth setup instructions for each service"""
        instructions = {}

        for service, config in ProductionConfig.OAUTH_SERVICES.items():
            instructions[service] = f"""
{service.upper()} OAuth Setup:
1. Go to: {config["setup_guide"]}
2. Create a new OAuth application
3. Set redirect URI to: http://yourdomain.com:5058/api/auth/{service}/callback
4. Copy Client ID to: {service.upper()}_CLIENT_ID
5. Copy Client Secret to: {service.upper()}_CLIENT_SECRET
6. Required scopes: {", ".join(config["scopes"])}
"""

        return instructions

    @staticmethod
    def check_oauth_configuration() -> Dict[str, Dict]:
        """Check current OAuth configuration status by querying OAuth server"""
        status = {}

        try:
            import requests

            response = requests.get(
                "http://localhost:5058/api/auth/services", timeout=5
            )
            if response.status_code == 200:
                data = response.json()
                services_with_creds = data.get("services_with_real_credentials", 0)

                # Check individual service status
                for service, config in ProductionConfig.OAUTH_SERVICES.items():
                    try:
                        service_response = requests.get(
                            f"http://localhost:5058/api/auth/{service}/status",
                            timeout=5,
                        )
                        if service_response.status_code == 200:
                            service_data = service_response.json()
                            is_configured = service_data.get("status") == "configured"
                            status[service] = {
                                "configured": is_configured,
                                "client_id_present": is_configured,
                                "client_secret_present": is_configured,
                                "status": "✅ Configured"
                                if is_configured
                                else "❌ Missing credentials",
                                "required": config["required"],
                            }
                        else:
                            status[service] = {
                                "configured": False,
                                "client_id_present": False,
                                "client_secret_present": False,
                                "status": "❌ Service not reachable",
                                "required": config["required"],
                            }
                    except:
                        status[service] = {
                            "configured": False,
                            "client_id_present": False,
                            "client_secret_present": False,
                            "status": "❌ Service check failed",
                            "required": config["required"],
                        }
            else:
                # Fallback to environment variable check if OAuth server is not available
                for service, config in ProductionConfig.OAUTH_SERVICES.items():
                    client_id = config["client_id"]
                    client_secret = config["client_secret"]

                    status[service] = {
                        "configured": bool(client_id and client_secret),
                        "client_id_present": bool(client_id),
                        "client_secret_present": bool(client_secret),
                        "status": "✅ Configured"
                        if client_id and client_secret
                        else "❌ Missing credentials",
                        "required": config["required"],
                    }
        except:
            # Fallback to environment variable check if requests fails
            for service, config in ProductionConfig.OAUTH_SERVICES.items():
                client_id = config["client_id"]
                client_secret = config["client_secret"]

                status[service] = {
                    "configured": bool(client_id and client_secret),
                    "client_id_present": bool(client_id),
                    "client_secret_present": bool(client_secret),
                    "status": "✅ Configured"
                    if client_id and client_secret
                    else "❌ Missing credentials",
                    "required": config["required"],
                }

        return status


class DatabaseSetup:
    """Database setup and configuration"""

    @staticmethod
    def get_connection_string() -> str:
        """Generate PostgreSQL connection string"""
        db_config = ProductionConfig.DATABASE_CONFIG["postgresql"]
        return f"postgresql://{db_config['user']}:{db_config['password']}@{db_config['host']}:{db_config['port']}/{db_config['database']}"

    @staticmethod
    def check_database_config() -> Dict[str, bool]:
        """Check database configuration status"""
        db_config = ProductionConfig.DATABASE_CONFIG["postgresql"]

        return {
            "host_configured": bool(db_config["host"]),
            "user_configured": bool(db_config["user"]),
            "password_configured": bool(db_config["password"]),
            "database_configured": bool(db_config["database"]),
            "all_configured": all(
                [
                    db_config["host"],
                    db_config["user"],
                    db_config["password"],
                    db_config["database"],
                ]
            ),
        }


def generate_production_checklist() -> Dict[str, List[str]]:
    """Generate production deployment checklist"""

    oauth_status = OAuthSetupGuide.check_oauth_configuration()
    db_status = DatabaseSetup.check_database_config()

    checklist = {"completed": [], "pending": [], "critical": []}

    # OAuth Configuration
    for service, status in oauth_status.items():
        if status["configured"]:
            checklist["completed"].append(f"✅ {service.upper()} OAuth configured")
        else:
            if status["required"]:
                checklist["critical"].append(
                    f"❌ {service.upper()} OAuth required but not configured"
                )
            else:
                checklist["pending"].append(
                    f"⚠️ {service.upper()} OAuth optional - not configured"
                )

    # Database Configuration
    if db_status["all_configured"]:
        checklist["completed"].append("✅ Database configuration complete")
    else:
        checklist["critical"].append("❌ Database configuration incomplete")

    # API Keys
    for service, config in ProductionConfig.API_KEYS.items():
        # Check if OpenAI API key is configured (it's in the .env file)
        if service == "openai":
            # Check if OpenAI API key exists in environment
            import os

            openai_key = os.getenv("OPENAI_API_KEY")
            if openai_key and openai_key != "sk-placeholder-openai-api-key-REPLACE-ME":
                checklist["completed"].append(
                    f"✅ {service.upper()} API key configured"
                )
            else:
                if config["required"]:
                    checklist["critical"].append(
                        f"❌ {service.upper()} API key required but not configured"
                    )
                else:
                    checklist["pending"].append(
                        f"⚠️ {service.upper()} API key optional - not configured"
                    )
        elif config["key"]:
            checklist["completed"].append(f"✅ {service.upper()} API key configured")
        else:
            if config["required"]:
                checklist["critical"].append(
                    f"❌ {service.upper()} API key required but not configured"
                )
            else:
                checklist["pending"].append(
                    f"⚠️ {service.upper()} API key optional - not configured"
                )

    # Security
    if ProductionConfig.SECURITY["jwt_secret"] != "change_this_in_production":
        checklist["completed"].append("✅ JWT secret configured")
    else:
        checklist["critical"].append("❌ JWT secret not changed from default")

    if ProductionConfig.SECURITY["encryption_key"] != "change_this_in_production":
        checklist["completed"].append("✅ Encryption key configured")
    else:
        checklist["critical"].append("❌ Encryption key not changed from default")

    return checklist


def print_production_status():
    """Print comprehensive production status report"""

    print("\n" + "=" * 60)
    print("🚀 ATOM PLATFORM - PRODUCTION DEPLOYMENT STATUS")
    print("=" * 60)

    # OAuth Status
    print("\n📋 OAUTH CONFIGURATION:")
    oauth_status = OAuthSetupGuide.check_oauth_configuration()
    for service, status in oauth_status.items():
        print(f"   {service.upper():<12} {status['status']}")

    # Show OAuth server summary if available
    try:
        import requests

        response = requests.get("http://localhost:5058/api/auth/services", timeout=5)
        if response.status_code == 200:
            data = response.json()
            print(
                f"   📊 OAuth Server: {data.get('services_with_real_credentials', 0)}/{data.get('total_services', 0)} services configured"
            )
    except:
        pass

    # Database Status
    print("\n🗄️  DATABASE CONFIGURATION:")
    db_status = DatabaseSetup.check_database_config()
    if db_status["all_configured"]:
        print("   ✅ Database configuration complete")
    else:
        print("   ❌ Database configuration incomplete")

    # API Keys Status
    print("\n🔑 API KEYS CONFIGURATION:")
    for service, config in ProductionConfig.API_KEYS.items():
        if service == "openai":
            # Check actual environment for OpenAI key
            import os

            openai_key = os.getenv("OPENAI_API_KEY")
            status = (
                "✅ Configured"
                if openai_key
                and openai_key != "sk-placeholder-openai-api-key-REPLACE-ME"
                else "❌ Missing"
            )
            print(f"   {service.upper():<12} {status}")
        else:
            status = "✅ Configured" if config["key"] else "❌ Missing"
            print(f"   {service.upper():<12} {status}")

    # Security Status
    print("\n🔒 SECURITY CONFIGURATION:")
    security_issues = []
    if ProductionConfig.SECURITY["jwt_secret"] == "change_this_in_production":
        security_issues.append("JWT secret")
    if ProductionConfig.SECURITY["encryption_key"] == "change_this_in_production":
        security_issues.append("Encryption key")

    if security_issues:
        print(f"   ❌ Security issues: {', '.join(security_issues)}")
    else:
        print("   ✅ Security configuration complete")

    # Deployment Checklist
    print("\n📋 DEPLOYMENT CHECKLIST:")
    checklist = generate_production_checklist()

    print("   CRITICAL ITEMS:")
    for item in checklist["critical"]:
        print(f"     {item}")

    print("   PENDING ITEMS:")
    for item in checklist["pending"]:
        print(f"     {item}")

    print("   COMPLETED ITEMS:")
    for item in checklist["completed"]:
        print(f"     {item}")

    print("\n" + "=" * 60)


if __name__ == "__main__":
    print_production_status()

    # Generate setup instructions
    print("\n📚 SETUP INSTRUCTIONS:")
    instructions = OAuthSetupGuide.generate_setup_instructions()
    for service, instruction in instructions.items():
        print(f"\n{service.upper()} Setup:")
        print(instruction)
