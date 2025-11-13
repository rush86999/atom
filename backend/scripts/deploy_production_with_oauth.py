#!/usr/bin/env python3
"""
Comprehensive Production Deployment with OAuth Completion

This script handles the complete production deployment of the Atom AI Assistant
including OAuth service completion, SSL/TLS configuration, monitoring setup,
and production validation.

Usage:
    python deploy_production_with_oauth.py
"""

import os
import sys
import json
import time
import subprocess
import requests
import secrets
from datetime import datetime
from typing import Dict, List, Any, Tuple


class ProductionDeploymentWithOAuth:
    """Complete production deployment with OAuth service completion"""

    def __init__(self):
        self.base_url = "http://localhost:5058"
        self.deployment_log = []
        self.start_time = datetime.now()
        self.remaining_services = ["outlook", "teams", "github"]

    def log_step(self, step_name: str, status: str, message: str = ""):
        """Log deployment step with timestamp"""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        log_entry = {
            "timestamp": timestamp,
            "step": step_name,
            "status": status,
            "message": message
        }
        self.deployment_log.append(log_entry)

        status_icon = "✅" if status == "success" else "❌" if status == "failed" else "⚠️"
        print(f"{status_icon} [{timestamp}] {step_name}: {message}")

    def validate_current_oauth_status(self) -> Dict[str, Any]:
        """Validate current OAuth system status"""
        self.log_step("oauth_status_validation", "running", "Validating current OAuth system status")

        try:
            response = requests.get(
                f"{self.base_url}/api/auth/oauth-status?user_id=production_deploy",
                timeout=10
            )

            if response.status_code == 200:
                data = response.json()
                connected_services = data.get("connected_services", 0)
                total_services = data.get("total_services", 0)

                self.log_step(
                    "oauth_status_validation",
                    "success",
                    f"Current OAuth status: {connected_services}/{total_services} services connected"
                )

                return {
                    "success": True,
                    "connected_services": connected_services,
                    "total_services": total_services,
                    "success_rate": connected_services / total_services if total_services > 0 else 0,
                    "data": data
                }
            else:
                self.log_step(
                    "oauth_status_validation",
                    "failed",
                    f"OAuth status endpoint returned HTTP {response.status_code}"
                )
                return {"success": False, "error": f"HTTP {response.status_code}"}

        except Exception as e:
            self.log_step(
                "oauth_status_validation",
                "failed",
                f"OAuth status validation failed: {str(e)}"
            )
            return {"success": False, "error": str(e)}

    def configure_remaining_oauth_services(self) -> bool:
        """Configure remaining OAuth services with placeholder credentials"""
        self.log_step(
            "oauth_service_completion",
            "running",
            f"Configuring remaining OAuth services: {', '.join(self.remaining_services)}"
        )

        # Create configuration template for remaining services
        oauth_config = {
            "outlook": {
                "client_id": "TODO_ADD_MICROSOFT_CLIENT_ID",
                "client_secret": "TODO_ADD_MICROSOFT_CLIENT_SECRET",
                "redirect_uri": "https://your-production-domain.com/api/auth/outlook/oauth2callback",
                "scopes": ["https://graph.microsoft.com/Mail.Read", "https://graph.microsoft.com/Calendars.Read"]
            },
            "teams": {
                "client_id": "TODO_ADD_MICROSOFT_TEAMS_CLIENT_ID",
                "client_secret": "TODO_ADD_MICROSOFT_TEAMS_CLIENT_SECRET",
                "redirect_uri": "https://your-production-domain.com/api/auth/teams/oauth2callback",
                "scopes": ["https://graph.microsoft.com/Team.ReadBasic.All"]
            },
            "github": {
                "client_id": "TODO_ADD_GITHUB_CLIENT_ID",
                "client_secret": "TODO_ADD_GITHUB_CLIENT_SECRET",
                "redirect_uri": "https://your-production-domain.com/api/auth/github/oauth2callback",
                "scopes": ["repo", "user", "read:org"]
            }
        }

        # Save OAuth configuration template
        config_file = "oauth_remaining_services_config.json"
        with open(config_file, "w") as f:
            json.dump(oauth_config, f, indent=2)

        self.log_step(
            "oauth_service_completion",
            "success",
            f"OAuth configuration template created: {config_file}"
        )

        # Create setup instructions
        instructions = self._generate_oauth_setup_instructions()
        instructions_file = "OAUTH_SERVICE_SETUP_INSTRUCTIONS.md"
        with open(instructions_file, "w") as f:
            f.write(instructions)

        self.log_step(
            "oauth_service_completion",
            "info",
            f"Setup instructions created: {instructions_file}"
        )

        return True

    def _generate_oauth_setup_instructions(self) -> str:
        """Generate OAuth service setup instructions"""
        return f"""# OAuth Service Setup Instructions

## Remaining Services to Configure

### 1. Microsoft Outlook/Teams
**Steps:**
1. Go to [Azure Portal](https://portal.azure.com)
2. Navigate to Azure Active Directory > App registrations
3. Create a new application registration
4. Configure redirect URIs:
   - `https://your-production-domain.com/api/auth/outlook/oauth2callback`
   - `https://your-production-domain.com/api/auth/teams/oauth2callback`
5. Add required API permissions:
   - Microsoft Graph > Mail.Read
   - Microsoft Graph > Calendars.Read
   - Microsoft Graph > Team.ReadBasic.All
6. Copy Client ID and Client Secret to environment variables

### 2. GitHub
**Steps:**
1. Go to [GitHub Developer Settings](https://github.com/settings/developers)
2. Create a new OAuth App
3. Configure:
   - Application name: Atom AI Assistant
   - Homepage URL: https://your-production-domain.com
   - Authorization callback URL: `https://your-production-domain.com/api/auth/github/oauth2callback`
4. Copy Client ID and Client Secret to environment variables

## Environment Variables to Set

```bash
# Microsoft Outlook/Teams
OUTLOOK_CLIENT_ID=your_microsoft_client_id
OUTLOOK_CLIENT_SECRET=your_microsoft_client_secret
TEAMS_CLIENT_ID=your_teams_client_id
TEAMS_CLIENT_SECRET=your_teams_client_secret

# GitHub
GITHUB_CLIENT_ID=your_github_client_id
GITHUB_CLIENT_SECRET=your_github_client_secret

# Production Domain
PRODUCTION_DOMAIN=your-production-domain.com
```

## Verification Steps
1. Update the environment variables above
2. Restart the backend server
3. Run OAuth validation: `python test_oauth_validation.py`
4. Verify all 10 services show as connected

Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
"""

    def setup_production_environment(self) -> bool:
        """Setup production environment configuration"""
        self.log_step("production_environment", "running", "Setting up production environment")

        try:
            # Generate production environment template
            env_template = self._generate_production_env_template()
            env_file = ".env.production.template"

            with open(env_file, "w") as f:
                f.write(env_template)

            self.log_step(
                "production_environment",
                "success",
                f"Production environment template created: {env_file}"
            )

            # Create production deployment configuration
            deployment_config = self._generate_deployment_config()
            config_file = "production_deployment_config.json"

            with open(config_file, "w") as f:
                json.dump(deployment_config, f, indent=2)

            self.log_step(
                "production_environment",
                "success",
                f"Deployment configuration created: {config_file}"
            )

            return True

        except Exception as e:
            self.log_step(
                "production_environment",
                "failed",
                f"Production environment setup failed: {str(e)}"
            )
            return False

    def _generate_production_env_template(self) -> str:
        """Generate production environment template"""
        return f"""# Production Environment Configuration
# Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

# Application Settings
FLASK_ENV=production
DEBUG=False
SECRET_KEY={secrets.token_urlsafe(32)}

# Server Configuration
HOST=0.0.0.0
PORT=5058
PRODUCTION_DOMAIN=your-production-domain.com

# Database Configuration
DATABASE_URL=postgresql://username:password@localhost/atom_production
# or for SQLite:
# DATABASE_URL=sqlite:///./data/atom_production.db

# Security Configuration
ATOM_OAUTH_ENCRYPTION_KEY={secrets.token_urlsafe(32)}
CSRF_ENABLED=True
SESSION_SECURE=True

# OAuth Configuration - Update with real credentials
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
OUTLOOK_CLIENT_ID=TODO_ADD_MICROSOFT_CLIENT_ID
OUTLOOK_CLIENT_SECRET=TODO_ADD_MICROSOFT_CLIENT_SECRET
TEAMS_CLIENT_ID=TODO_ADD_MICROSOFT_TEAMS_CLIENT_ID
TEAMS_CLIENT_SECRET=TODO_ADD_MICROSOFT_TEAMS_CLIENT_SECRET
GITHUB_CLIENT_ID=TODO_ADD_GITHUB_CLIENT_ID
GITHUB_CLIENT_SECRET=TODO_ADD_GITHUB_CLIENT_SECRET

# AI Provider Configuration
OPENAI_API_KEY=your_openai_api_key
ANTHROPIC_API_KEY=your_anthropic_api_key
DEEPSEEK_API_KEY=your_deepseek_api_key
GOOGLE_AI_API_KEY=your_google_ai_api_key

# Monitoring & Analytics
ENABLE_METRICS=True
LOG_LEVEL=INFO
HEALTH_CHECK_INTERVAL=30

# SSL/TLS Configuration (for production)
SSL_CERT_PATH=/path/to/ssl/certificate.crt
SSL_KEY_PATH=/path/to/ssl/private.key

# Rate Limiting
RATE_LIMIT_REQUESTS=1000
RATE_LIMIT_WINDOW=3600
"""

    def _generate_deployment_config(self) -> Dict[str, Any]:
        """Generate deployment configuration"""
        return {
            "deployment_id": f"atom_production_{self.start_time.strftime('%Y%m%d_%H%M%S')}",
            "timestamp": self.start_time.isoformat(),
            "components": {
                "backend": {
                    "status": "ready",
                    "port": 5058,
                    "health_endpoint": "/healthz",
                    "dependencies": ["database", "oauth_services"]
                },
                "database": {
                    "status": "configured",
                    "type": "sqlite",  # or "postgresql"
                    "path": "./data/atom_production.db"
                },
                "oauth_services": {
                    "status": "partial",
                    "connected": 7,
                    "total": 10,
                    "remaining": self.remaining_services
                },
                "security": {
                    "status": "implemented",
                    "features": ["csrf_protection", "token_encryption", "secure_sessions"]
                },
                "monitoring": {
                    "status": "configured",
                    "endpoints": ["/healthz", "/api/services/status", "/api/auth/oauth-status"]
                }
            },
            "deployment_steps": [
                "environment_configuration",
                "oauth_service_completion",
                "ssl_tls_setup",
                "monitoring_setup",
                "backup_configuration",
                "final_validation"
            ],
            "requirements": {
                "ssl_certificate": "required",
                "domain_configuration": "required",
                "environment_variables": "required",
                "database_backup": "recommended"
            }
        }

    def setup_ssl_tls_configuration(self) -> bool:
        """Setup SSL/TLS configuration for production"""
        self.log_step("ssl_tls_setup", "running", "Setting up SSL/TLS configuration")

        try:
            # Create SSL/TLS setup instructions
            ssl_instructions = self._generate_ssl_setup_instructions()
            ssl_file = "SSL_TLS_SETUP_GUIDE.md"

            with open(ssl_file, "w") as f:
                f.write(ssl_instructions)

            self.log_step(
                "ssl_tls_setup",
                "success",
                f"SSL/TLS setup guide created: {ssl_file}"
            )

            # Create nginx configuration template
            nginx_config = self._generate_nginx_config()
            nginx_file = "nginx_production.conf"

            with open(nginx_file, "w") as f:
                f.write(nginx_config)

            self.log_step(
                "ssl_tls_setup",
                "success",
                f"NGINX configuration template created: {nginx_file}"
            )

            return True

        except Exception as e:
            self.log_step(
                "ssl_tls_setup",
                "failed",
                f"SSL/TLS setup failed: {str(e)}"
            )
            return False

    def _generate_ssl_setup_instructions(self) -> str:
        """Generate SSL/TLS setup instructions"""
        return f"""# SSL/TLS Setup Guide for Production

## Options for SSL/TLS Certificate

### 1. Let's Encrypt (Free)
```bash
# Install certbot
sudo apt update
sudo apt install certbot python3-certbot-nginx

# Get certificate
sudo certbot --nginx -d your-production-domain.com

# Auto-renewal
sudo crontab -e
# Add: 0 12 * * * /usr/bin/certbot renew --quiet
```

### 2. Commercial Certificate
1. Purchase SSL certificate from provider (DigiCert, Comodo, etc.)
2. Generate CSR and private key
3. Submit CSR to certificate authority
4. Install issued certificate

### 3. Self-Signed (Development Only)
```bash
# Generate self-signed certificate (NOT for production)
openssl req -x509 -newkey rsa:4096 -keyout key.pem -out cert.pem -days 365 -nodes
```

## NGINX Configuration
See `nginx_production.conf` for complete configuration template.

## Environment Variables
```bash
SSL_CERT_PATH=/etc/ssl/certs/your-domain.crt
SSL_KEY_PATH=/etc/ssl/private/your-domain.key
```

## Verification
```bash
# Test SSL configuration
openssl s_client -connect your-production-domain.com:443

# Check certificate validity
openssl x509 -in /path/to/certificate.crt -text -noout
```

Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
"""

    def _generate_nginx_config(self) -> str:
        """Generate NGINX configuration template"""
        return f"""# NGINX Production Configuration for Atom AI Assistant
# Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

server {{
    listen 80;
    server_name your-production-domain.com;
    return 301 https://$server_name$request_uri;
}}

server {{
    listen 443 ssl http2;
    server_name your-production-domain.com;

    # SSL Configuration
    ssl_certificate /etc/ssl/certs/your-domain.crt;
    ssl_certificate_key /etc/ssl/private/your-domain.key;
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers ECDHE-RSA-AES256-GCM-SHA512:DHE-RSA-AES256-GCM-SHA512;
    ssl_prefer_server_ciphers off;

    # Security Headers
    add_header Strict-Transport-Security "max-age=63072000; includeSubDomains; preload";
    add_header X-Frame-Options DENY;
    add_header X-Content-Type-Options nosniff;
    add_header X-XSS-Protection "1; mode=block";
    add_header Referrer-Policy "strict-origin-when-cross-origin";

    # Proxy to Flask application
    location / {{
        proxy_pass http://localhost:5058;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;

        # WebSocket support
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
    }}

    # Static files
    location /static/ {{
        alias /path/to/your/static/files/;
        expires 1y;
        add_header Cache-Control "public, immutable";
    }}

    # Rate limiting
    limit_req_zone $binary_remote_addr zone=api:10m rate=10r/s;

    location /api/ {{
        limit_req zone=api burst=20 nodelay;
        proxy_pass http://localhost:5058;
    }}

    # Health checks
    location /healthz {{
        access_log off;
        proxy_pass http://localhost:5058;
    }}

    # OAuth callbacks - no rate limiting
    location /api/auth
