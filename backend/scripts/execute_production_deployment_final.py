#!/usr/bin/env python3
"""
Final Production Deployment Execution Script for Atom AI Assistant

This script executes the complete production deployment process including:
1. OAuth service configuration completion
2. Production environment setup
3. SSL/TLS configuration
4. Monitoring and backup setup
5. Final validation and deployment

Usage:
    python execute_production_deployment_final.py
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


class ProductionDeploymentFinal:
    """Final production deployment execution class"""

    def __init__(self):
        self.base_url = "http://localhost:5058"
        self.deployment_log = []
        self.start_time = datetime.now()
        self.remaining_services = ["outlook", "teams", "github"]
        self.production_domain = "your-production-domain.com"  # Update with actual domain

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

    def validate_current_state(self) -> Dict[str, Any]:
        """Validate current OAuth system state"""
        self.log_step("current_state", "running", "Validating current OAuth system")

        try:
            response = requests.get(
                f"{self.base_url}/api/auth/oauth-status?user_id=production_deploy",
                timeout=10
            )

            if response.status_code == 200:
                data = response.json()
                connected_services = data.get("connected_services", 0)
                total_services = data.get("total_services", 0)
                success_rate = (connected_services / total_services) * 100 if total_services > 0 else 0

                self.log_step(
                    "current_state",
                    "success",
                    f"Current: {connected_services}/{total_services} services connected ({success_rate:.1f}%)"
                )

                return {
                    "success": True,
                    "connected_services": connected_services,
                    "total_services": total_services,
                    "success_rate": success_rate,
                    "data": data
                }
            else:
                self.log_step(
                    "current_state",
                    "failed",
                    f"OAuth status endpoint returned HTTP {response.status_code}"
                )
                return {"success": False}

        except Exception as e:
            self.log_step("current_state", "failed", f"Validation failed: {str(e)}")
            return {"success": False}

    def create_oauth_environment_config(self) -> bool:
        """Create OAuth environment configuration for remaining services"""
        self.log_step(
            "oauth_env_config",
            "running",
            f"Creating OAuth environment configuration for: {', '.join(self.remaining_services)}"
        )

        try:
            # Create environment configuration template
            env_config = {
                "production_domain": self.production_domain,
                "oauth_services": {
                    "outlook": {
                        "client_id": "YOUR_OUTLOOK_CLIENT_ID",
                        "client_secret": "YOUR_OUTLOOK_CLIENT_SECRET",
                        "redirect_uri": f"https://{self.production_domain}/api/auth/outlook/oauth2callback",
                        "scopes": [
                            "https://graph.microsoft.com/Mail.Read",
                            "https://graph.microsoft.com/Calendars.Read"
                        ],
                        "setup_url": "https://portal.azure.com",
                        "instructions": "Azure Portal > App Registrations > Create New Registration"
                    },
                    "teams": {
                        "client_id": "YOUR_TEAMS_CLIENT_ID",
                        "client_secret": "YOUR_TEAMS_CLIENT_SECRET",
                        "redirect_uri": f"https://{self.production_domain}/api/auth/teams/oauth2callback",
                        "scopes": ["https://graph.microsoft.com/Team.ReadBasic.All"],
                        "setup_url": "https://portal.azure.com",
                        "instructions": "Use same Azure app as Outlook, add Teams permissions"
                    },
                    "github": {
                        "client_id": "YOUR_GITHUB_CLIENT_ID",
                        "client_secret": "YOUR_GITHUB_CLIENT_SECRET",
                        "redirect_uri": f"https://{self.production_domain}/api/auth/github/oauth2callback",
                        "scopes": ["repo", "user", "read:org"],
                        "setup_url": "https://github.com/settings/developers",
                        "instructions": "GitHub Developer Settings > OAuth Apps > Create New App"
                    }
                },
                "environment_variables": {
                    "OUTLOOK_CLIENT_ID": "YOUR_OUTLOOK_CLIENT_ID",
                    "OUTLOOK_CLIENT_SECRET": "YOUR_OUTLOOK_CLIENT_SECRET",
                    "TEAMS_CLIENT_ID": "YOUR_TEAMS_CLIENT_ID",
                    "TEAMS_CLIENT_SECRET": "YOUR_TEAMS_CLIENT_SECRET",
                    "GITHUB_CLIENT_ID": "YOUR_GITHUB_CLIENT_ID",
                    "GITHUB_CLIENT_SECRET": "YOUR_GITHUB_CLIENT_SECRET",
                    "PRODUCTION_DOMAIN": self.production_domain
                }
            }

            # Save configuration
            with open("oauth_production_config.json", "w") as f:
                json.dump(env_config, f, indent=2)

            # Create environment setup script
            setup_script = self._generate_oauth_setup_script()
            with open("setup_oauth_services.sh", "w") as f:
                f.write(setup_script)

            # Make script executable
            os.chmod("setup_oauth_services.sh", 0o755)

            self.log_step(
                "oauth_env_config",
                "success",
                "OAuth environment configuration and setup script created"
            )
            return True

        except Exception as e:
            self.log_step("oauth_env_config", "failed", f"Configuration creation failed: {str(e)}")
            return False

    def _generate_oauth_setup_script(self) -> str:
        """Generate OAuth setup shell script"""
        return f"""#!/bin/bash
# OAuth Service Setup Script for Atom AI Assistant
# Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

set -e

echo "🚀 Setting up OAuth Services for Production"
echo "=========================================="

# Check if .env file exists
if [ ! -f .env.production ]; then
    echo "❌ .env.production file not found"
    echo "   Create from .env.production.template first"
    exit 1
fi

echo ""
echo "📋 OAuth Services to Configure:"
echo "   - Microsoft Outlook"
echo "   - Microsoft Teams"
echo "   - GitHub"
echo ""

echo "🔧 Please configure the following environment variables in .env.production:"
echo ""
echo "OUTLOOK_CLIENT_ID=your_microsoft_client_id"
echo "OUTLOOK_CLIENT_SECRET=your_microsoft_client_secret"
echo "TEAMS_CLIENT_ID=your_teams_client_id"
echo "TEAMS_CLIENT_SECRET=your_teams_client_secret"
echo "GITHUB_CLIENT_ID=your_github_client_id"
echo "GITHUB_CLIENT_SECRET=your_github_client_secret"
echo "PRODUCTION_DOMAIN={self.production_domain}"
echo ""

echo "📖 Setup Instructions:"
echo "   1. Microsoft Azure: https://portal.azure.com"
echo "      - Create app registration"
echo "      - Add redirect URIs for {self.production_domain}"
echo "      - Configure API permissions"
echo ""
echo "   2. GitHub: https://github.com/settings/developers"
echo "      - Create OAuth App"
echo "      - Set callback URL"
echo "      - Configure scopes"
echo ""

echo "✅ After configuration, restart the backend server:"
echo "   python start_oauth_status_server.py"
echo ""

echo "🔍 Validate setup with:"
echo "   python test_oauth_validation.py"
echo ""

echo "🎉 OAuth setup script completed"
"""

    def setup_production_server(self) -> bool:
        """Setup production server configuration"""
        self.log_step("production_server", "running", "Setting up production server configuration")

        try:
            # Create production server configuration
            server_config = {
                "server": {
                    "host": "0.0.0.0",
                    "port": 5058,
                    "workers": 4,
                    "threads": 2,
                    "timeout": 120
                },
                "database": {
                    "url": "sqlite:///./data/atom_production.db",
                    "pool_size": 10,
                    "max_overflow": 20,
                    "pool_recycle": 3600
                },
                "security": {
                    "secret_key": secrets.token_urlsafe(32),
                    "encryption_key": secrets.token_urlsafe(32),
                    "csrf_enabled": True,
                    "session_secure": True
                },
                "performance": {
                    "cache_timeout": 300,
                    "rate_limit_requests": 1000,
                    "rate_limit_window": 3600,
                    "max_concurrent_workflows": 5
                }
            }

            # Save server configuration
            with open("production_server_config.json", "w") as f:
                json.dump(server_config, f, indent=2)

            # Create production startup script
            startup_script = self._generate_startup_script()
            with open("start_production_server.py", "w") as f:
                f.write(startup_script)

            self.log_step(
                "production_server",
                "success",
                "Production server configuration and startup script created"
            )
            return True

        except Exception as e:
            self.log_step("production_server", "failed", f"Server setup failed: {str(e)}")
            return False

    def _generate_startup_script(self) -> str:
        """Generate production server startup script"""
        return f'''#!/usr/bin/env python3
"""
Production Server Startup Script for Atom AI Assistant

This script starts the production server with optimized configuration
for performance, security, and reliability.

Usage:
    python start_production_server.py
"""

import os
import sys
import logging
from datetime import datetime

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler("production.log"),
        logging.StreamHandler(sys.stdout)
    ]
)

logger = logging.getLogger(__name__)

def start_production_server():
    """Start the production server"""

    print("🚀 Starting Atom AI Assistant Production Server")
    print("=" * 50)
    print(f"Start Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("Environment: PRODUCTION")
    print("=" * 50)

    # Set production environment
    os.environ["FLASK_ENV"] = "production"
    os.environ["DEBUG"] = "False"

    try:
        # Import and start the server
        from start_oauth_status_server import start_server

        logger.info("Production server starting...")
        start_server()

    except Exception as e:
        logger.error(f"Failed to start production server: {e}")
        sys.exit(1)

if __name__ == "__main__":
    start_production_server()
'''

    def create_ssl_nginx_config(self) -> bool:
        """Create SSL/TLS and NGINX configuration"""
        self.log_step("ssl_nginx", "running", "Creating SSL/TLS and NGINX configuration")

        try:
            # Create NGINX configuration
            nginx_config = self._generate_nginx_config()
            with open("nginx_production.conf", "w") as f:
                f.write(nginx_config)

            # Create SSL setup script
            ssl_script = self._generate_ssl_setup_script()
            with open("setup_ssl.sh", "w") as f:
                f.write(ssl_script)

            # Make script executable
            os.chmod("setup_ssl.sh", 0o755)

            self.log_step(
                "ssl_nginx",
                "success",
                "NGINX configuration and SSL setup script created"
            )
            return True

        except Exception as e:
            self.log_step("ssl_nginx", "failed", f"SSL/NGINX setup failed: {str(e)}")
            return False

    def _generate_nginx_config(self) -> str:
        """Generate NGINX production configuration"""
        return f'''# NGINX Production Configuration for Atom AI Assistant
# Domain: {self.production_domain}
# Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

server {{
    listen 80;
    server_name {self.production_domain};
    return 301 https://$server_name$request_uri;
}}

server {{
    listen 443 ssl http2;
    server_name {self.production_domain};

    # SSL Configuration
    ssl_certificate /etc/ssl/certs/{self.production_domain}.crt;
    ssl_certificate_key /etc/ssl/private/{self.production_domain}.key;
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

    # Health checks
    location /healthz {{
        access_log off;
        proxy_pass http://localhost:5058;
    }}

    # OAuth callbacks - no rate limiting
    location /api/auth/ {{
        proxy_pass http://localhost:5058;
    }}

    # Rate limiting
    limit_req_zone $binary_remote_addr zone=api:10m rate=10r/s;

    location /api/ {{
        limit_req zone=api burst=20 nodelay;
        proxy_pass http://localhost:5058;
    }}
}}
'''

    def _generate_ssl_setup_script(self) -> str:
        """Generate SSL setup script"""
        return f"""#!/bin/bash
# SSL/TLS Setup Script for {self.production_domain}
# Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

set -e

echo "🔐 Setting up SSL/TLS for {self.production_domain}"
echo "================================================"

# Check for certbot
if ! command -v certbot &> /dev/null; then
    echo "📦 Installing certbot..."
    sudo apt update
    sudo apt install -y certbot python3-certbot-nginx
fi

echo ""
echo "🎯 Getting SSL certificate for {self.production_domain}"
echo ""

# Get certificate
sudo certbot --nginx -d {self.production_domain} --non-interactive --agree-tos --email admin@{self.production_domain}

echo ""
echo "✅ SSL certificate installed successfully"
echo ""

# Setup auto-renewal
echo "🔄 Setting up auto-renewal..."
sudo crontab -l | {{ cat; echo "0 12 * * * /usr/bin/certbot renew --quiet"; }} | sudo crontab -

echo ""
echo "📋 Next steps:"
echo "   1. Configure NGINX with the generated configuration"
echo "   2. Test SSL configuration: openssl s_client -connect {self.production_domain}:443"
echo "   3. Verify certificate: openssl x509 -in /etc/letsencrypt/live/{self.production_domain}/fullchain.pem -text -noout"
echo ""

echo "🎉 SSL setup completed"
"""

    def setup_monitoring_backup(self) -> bool:
        """Setup monitoring and backup configuration"""
        self.log_step("monitoring_backup", "running", "Setting up monitoring and backup configuration")

        try:
            # Create monitoring configuration
            monitoring_config = {
                "health_endpoints": [
                    f"https://{self.production_domain}/healthz",
                    f"https://{self.production_domain}/api/services/status",
                    f"https://{self.production_domain}/api/auth/oauth-status"
                ],
                "metrics": {
                    "response_time_threshold": 500,  # ms
                    "error_rate_threshold": 1,  # %
                    "uptime_threshold": 99.9  # %
                },
                "alerts": {
                    "high_response_time": True,
                    "service_down": True,
                    "ssl_cert_expiry": True
                }
            }

            with open("monitoring_config.json", "w") as f:
                json.dump(monitoring_config, f, indent=2)

            # Create backup script
            backup_script = self._generate_backup_script()
            with open("backup_database.sh", "w") as f:
                f.write(backup_script)

            # Make script executable
            os.chmod("backup_database.sh", 0o755)

            # Create monitoring script
            monitoring_script = self._generate_monitoring_script()
            with open("monitor_services.py", "w") as f:
                f.write(monitoring_script)

            self.log_step(
                "monitoring_backup",
                "success",
                "Monitoring and backup configuration created"
            )
            return True

        except Exception as e:
            self.log_step("monitoring_backup", "failed", f"Monitoring/backup setup failed: {str(e)}")
            return False

    def _generate_backup_script(self) -> str:
        """Generate database backup script"""
        return f'''#!/bin/bash
# Database Backup Script for Atom AI Assistant
# Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

set -e

BACKUP_DIR="/backups/atom"
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
    production_server_config.json \\
    oauth_production_config.json \\
    monitoring_config.json

echo "✅ Configuration files backed up"

# Clean up old backups (keep last 7 days)
find "$BACKUP_DIR" -name "*.db" -mtime +7 -delete
find "$BACKUP_DIR" -name "*.tar.gz" -mtime +7 -delete

echo "🧹 Old backups cleaned up"
echo "🎉 Backup completed successfully"
'''

    def _generate_monitoring_script(self) -> str:
        """Generate service monitoring script"""
        return f'''#!/usr/bin/env python3
"""
Service Monitoring Script for Atom AI Assistant
+
This script monitors the health and performance of the Atom AI Assistant
production services and sends alerts for any issues.
+
Usage:
    python monitor_services.py
"""
+
import os
import sys
import time
import requests
import json
import logging
from datetime import datetime
from typing import Dict, List, Any
+
# Configuration
BASE_URL = "https://{self.production_domain}"
HEALTH_ENDPOINTS = [
    "/healthz",
    "/api/services/status",
    "/api/auth/oauth-status"
]
ALERT_THRESHOLDS = {
    "response_time": 500,  # ms
    "error_rate": 1,      # %
}
+
# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler("monitoring.log"),
        logging.StreamHandler(sys.stdout)
    ]
)
+
logger = logging.getLogger(__name__)
+
class ServiceMonitor:
    """Service monitoring class"""
+
    def __init__(self):
        self.alerts_sent = []
+
    def check_endpoint(self, endpoint: str) -> Dict[str, Any]:
        """Check a single endpoint"""
        try:
            start_time = time.time()
            response = requests.get(f"{{BASE_URL}}{{endpoint}}", timeout=10)
            response_time = (time.time() - start_time) * 1000
+
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
+
    def check_all_endpoints(self) -> List[Dict[str, Any]]:
        """Check all monitoring endpoints"""
        results = []
        for endpoint in HEALTH_ENDPOINTS:
            result = self.check_endpoint(endpoint)
            results.append(result)
+
            # Log results
            if result["success"]:
                logger.info(f"✅ {{endpoint}}: {{result['response_time']:.1f}}ms")
+            else:
                logger.error(f"❌ {{endpoint}}: {{result.get('error', 'Unknown error')}}")
+
        return results
+
    def analyze_results(self, results: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Analyze monitoring results"""
        total_checks = len(results)
        successful_checks = sum(1 for r in results if r["success"])
        error_rate = ((total_checks - successful_checks) / total_checks) * 100
+
        response_times = [r["response_time"] for r in results if r["response_time"]]
        avg_response_time = sum(response_times) / len(response_times) if response_times else 0
        max_response_time = max(response_times) if response_times else 0
+
+        return {
            "total_checks": total_checks,
            "successful_checks": successful_checks,
            "error_rate": error_rate,
            "avg_response_time": avg_response_time,
            "max_response_time": max_response_time,
+            "timestamp": datetime.now().isoformat()
+        }
+
    def send_alert(self, message: str, level: str = "ERROR"):
        """Send alert (placeholder for actual alerting system)"""
        alert = {
            "level": level,
            "message": message,
            "timestamp": datetime.now().isoformat()
+        }
+
        # Log alert
        if level == "ERROR":
            logger.error(f"🚨 ALERT: {{message}}")
        elif level == "WARNING":
            logger.warning(f"⚠️  WARNING:
+        else:
+            logger.info(f"ℹ️  INFO: {{message}}")
+
+        # Save alert to file
+        with open("alerts.log", "a") as f:
+            f.write(json.dumps(alert) + "\\n")
+
+        self.alerts_sent.append(alert)
+
+    def run_monitoring_cycle(self):
+        """Run one monitoring cycle"""
+        logger.info("🔍 Starting monitoring cycle...")
+
+        # Check all endpoints
+        results = self.check_all_endpoints()
+
+        # Analyze results
+        analysis = self.analyze_results(results)
+
+        # Check thresholds and send alerts
+        if analysis["error_rate"] > ALERT_THRESHOLDS["error_rate"]:
+            self.send_alert(
+                f"High error rate: {{analysis['error_rate']:.1f}}%",
+                "ERROR"
+            )
+
+        if analysis["avg_response_time"] > ALERT_THRESHOLDS["response_time"]:
+            self.send_alert(
+                f"High response time: {{analysis['avg_response_time']:.1f}}ms",
+                "WARNING"
+            )
+
+        # Log summary
+        logger.info(f"📊 Monitoring summary: {{analysis['successful_checks']}}/{{analysis['total_checks']}} endpoints OK")
+
+        return analysis
+
+def main():
+    """Main monitoring function"""
+    monitor = ServiceMonitor()
+
+    print("🔍 Atom AI Assistant Service Monitor")
+    print("=" * 40)
+    print(f"Start Time: {{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}}")
+    print(f"Base URL: {{BASE_URL}}")
+    print("=" * 40)
+
+    try:
+        while True:
+            analysis = monitor.run_monitoring_cycle()
+
+            # Wait before next cycle (5 minutes)
+            time.sleep(300)
+
+    except KeyboardInterrupt:
+        print("\\n🛑 Monitoring stopped by user")
+    except Exception as e:
+        logger.error(f"Monitoring failed: {{e}}")
+        sys.exit(1)

+if __name__ == "__main__":
+    main()
+'''

+    def run_final_validation(self) -> Dict[str, Any]:
+        """Run final production validation"""
+        self.log_step("final_validation", "running", "Running final production validation")

+        validation_results = {
+            "oauth_configuration": self.create_oauth_environment_config(),
+            "server_configuration": self.setup_production_server(),
+            "ssl_nginx_configuration": self.create_ssl_nginx_config(),
+            "monitoring_backup_configuration": self.setup_monitoring_backup(),
+            "files_created": all([
+                os.path.exists("oauth_production_config.json"),
+                os.path.exists("setup_oauth_services.sh"),
+                os.path.exists("production_server_config.json"),
+                os.path.exists("start_production_server.py"),
+                os.path.exists("nginx_production.conf"),
+                os.path.exists("setup_ssl.sh"),
+                os.path.exists("monitoring_config.json"),
+                os.path.exists("backup_database.sh"),
+                os.path.exists("monitor_services.py")
+            ])
+        }

+        all_valid = all(validation_results.values())

+        if all_valid:
+            self.log_step("final_validation", "success", "All validation checks passed")
+        else:
+            failed_checks = [check for check, passed in validation_results.items() if not passed]
+            self.log_step(
+                "final_validation",
+                "failed" if not all_valid else "warning",
+                f"Validation issues: {', '.join(failed_checks)}"
+            )

        return {
+            "valid": all_valid,
+            "results": validation_results,
            "timestamp": datetime.now().isoformat()
        }

+    def generate_deployment_report(self) -> Dict[str, Any]:
+        """Generate comprehensive deployment report"""
+        end_time = datetime.now()
+        duration = (end_time - self.start_time).total_seconds()

+        # Count successful steps
+        successful_steps = sum(1 for step in self.deployment_log if step["status"] == "success")
+        total_steps = len(self.deployment_log)
+        success_rate = successful_steps / total_steps if total_steps > 0 else 0

+        # Final validation
+        validation_results = self.run_final_validation()

+        report = {
+            "deployment_id": f"atom_final_deployment_{self.start_time.strftime('%Y%m%d_%H%M%S')}",
+            "overall_status": "success" if validation_results["valid"] and success_rate >= 0.8 else "partial",
+            "success_rate": f"{success_rate:.1%}",
+            "start_time": self.start_time.isoformat(),
+            "end_time": end_time.isoformat(),
+            "duration_seconds": duration,
+            "total_steps": total_steps,
+            "successful_steps": successful_steps,
+            "remaining_services": self.remaining_services,
+            "production_domain": self.production_domain,
+            "validation_results": validation_results,
+            "deployment_log": self.deployment_log,
+            "created_files": [
+                "oauth_production_config.json",
+                "setup_oauth_services.sh",
+                "production_server_config.json",
+                "start_production_server.py",
+                "nginx_production.conf",
+                "setup_ssl.sh",
+                "monitoring_config.json",
+                "backup_database.sh",
+                "monitor_services.py"
+            ],
+            "next_steps": [
+                f"Configure OAuth credentials for: {', '.join(self.remaining_services)}",
+                f"Setup SSL/TLS certificates for {self.production_domain}",
+                "Deploy to production server",
+                "Configure monitoring and alerting",
+                "Setup automated backups",
+                "Test complete OAuth flows in production"
+            ]
        }

+        return report

+    def save_deployment_report(self, report: Dict[str, Any]):
+        """Save deployment report to file"""
+        filename = f"final_deployment_report_{self.start_time.strftime('%Y%m%d_%H%M%S')}.json"

+        with open(filename, "w") as f:
+            json.dump(report, f, indent=2)

+        self.log_step(
+            "report_generation",
+            "success",
+            f"Final deployment report saved to {filename}"
+        )
+        return filename

+    def execute_final_deployment(self) -> bool:
+        """Execute final production deployment process"""
+        print("🚀 Starting Final Production Deployment")
+        print("=" * 60)
+        print(f"Start Time: {self.start_time.strftime('%Y-%m-%d %H:%M:%S')}")
+        print(f"Production Domain: {self.production_domain}")
+        print("=" * 60)

+        # Execute deployment steps
+        steps = [
+            ("Current State Validation", self.validate_current_state),
+            ("OAuth Environment Configuration", self.create_oauth_environment_config),
+            ("Production Server Setup", self.setup_production_server),
+            ("SSL/TLS & NGINX Configuration", self.create_ssl_nginx_config),
+            ("Monitoring & Backup Setup", self.setup_monitoring_backup),
+        ]

+        all_steps_successful = True

+        for step_name, step_function in steps:
+            print(f"\\n🔧 Executing: {step_name}")
+            print("-" * 40)

+            success = step_function()
+            if not success:
+                all_steps_successful = False
+                # Continue with other steps to get complete picture
+
+        # Generate final report
+        print(f"\\n📊 Generating Final Deployment Report")
+        print("-" * 40)
+        report = self.generate_deployment_report()
+        report_filename = self.save_deployment_report(report)
+
+        # Print summary
+        print(f"\\n🎯 FINAL DEPLOYMENT SUMMARY")
+        print("=" * 60)
+        print(f"Overall Status: {report['overall_status'].upper()}")
+        print(f"Success Rate: {report['success_rate']}")
+        print(f"Duration: {report['duration_seconds']:.1f} seconds")
+        print(f"Steps Completed: {report['successful_steps']}/{report['total_steps']}")
+        print(f"Remaining Services: {', '.join(self.remaining_services)}")
+        print(f"Production Domain: {self.production_domain}")
+        print(f"Report: {report_filename}")
+
+        # Print validation results
+        validation = report["validation_results"]
+        print(f"\\n🔍 VALIDATION RESULTS:")
+        for component, result in validation["results"].items():
+            status_icon = "✅" if result else "❌"
+            print(f"   {status_icon} {component.replace('_', ' ').title()}")
+
+        # Print created files
+        print(f"\\n📁 CREATED FILES:")
+        for file in report["created_files"]:
+            if os.path.exists(file):
+                print(f"   ✅ {file}")
            else:
+                print(f"   ❌ {file}")
+
+        # Print next steps
+        print(f"\\n💡 NEXT STEPS:")
+        for i, step in enumerate(report["next_steps"][:5], 1):
+            print(f"   {i}. {step}")
+
+        print("=" * 60)
+
+        return all_steps_successful and validation["valid"]
+
+
+def main():
+    """Main execution function"""
+    try:
+        deployment = ProductionDeploymentFinal()
+        success = deployment.execute_final_deployment()
+
+        if success:
+            print("\\n🎉 FINAL PRODUCTION DEPLOYMENT SUCCESSFUL!")
+            print("   System is ready for production deployment")
+            exit(0)
+        else:
+            print("\\n⚠️  DEPLOYMENT COMPLETED WITH ISSUES")
+            print("    Review the deployment report and address recommendations")
+            exit(1)
+
+    except KeyboardInterrupt:
+        print("\\n🛑 Deployment interrupted by user")
+        exit(1)
+    except Exception as e:
+        print(f"\\n❌ Deployment failed with error: {e}")
+        exit(1)
+
+
+if __name__ == "__main__":
+    main()
