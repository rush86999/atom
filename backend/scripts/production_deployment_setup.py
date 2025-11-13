#!/usr/bin/env python3
"""
Production Deployment Configuration
Advanced Workflow Automation - Production Readiness

This script implements:
- Production configuration management
- Environment setup and validation
- Database configuration and migration
- Security configuration for production
- Monitoring and logging setup
- Deployment automation
"""

import os
import sys
import logging
import json
import yaml
import uuid
from datetime import datetime
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, field
from pathlib import Path

# Add backend directory to Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

logger = logging.getLogger(__name__)


@dataclass
class ProductionConfig:
    """Production configuration settings"""
    environment: str = "production"
    debug: bool = False
    log_level: str = "INFO"
    
    # Database Configuration
    database_url: str = ""
    database_pool_size: int = 20
    database_max_overflow: int = 30
    database_pool_timeout: int = 30
    database_pool_recycle: int = 3600
    
    # Redis Configuration (for caching and sessions)
    redis_url: str = ""
    redis_db: int = 0
    redis_password: Optional[str] = None
    redis_max_connections: int = 100
    
    # WebSocket Configuration
    websocket_host: str = "0.0.0.0"
    websocket_port: int = 8765
    websocket_ssl_enabled: bool = True
    websocket_cert_file: str = ""
    websocket_key_file: str = ""
    
    # Security Configuration
    secret_key: str = ""
    jwt_secret_key: str = ""
    jwt_expiration_hours: int = 24
    session_timeout_minutes: int = 30
    cors_origins: List[str] = field(default_factory=list)
    rate_limit_enabled: bool = True
    rate_limit_requests: int = 1000
    rate_limit_window_minutes: int = 60
    
    # Monitoring Configuration
    prometheus_enabled: bool = True
    prometheus_port: int = 9090
    health_check_enabled: bool = True
    health_check_port: int = 8080
    metrics_collection_enabled: bool = True
    log_analytics_enabled: bool = True
    
    # Performance Configuration
    max_concurrent_workflows: int = 1000
    workflow_timeout_minutes: int = 60
    task_queue_max_size: int = 10000
    cache_ttl_seconds: int = 3600
    
    # External Services Configuration
    gmail_api_key: str = ""
    slack_api_key: str = ""
    github_api_key: str = ""
    asana_api_key: str = ""
    trello_api_key: str = ""
    
    # Backup and Recovery
    backup_enabled: bool = True
    backup_schedule_hours: int = 24
    backup_retention_days: int = 30
    auto_recovery_enabled: bool = True
    
    # Email Configuration
    smtp_server: str = ""
    smtp_port: int = 587
    smtp_username: str = ""
    smtp_password: str = ""
    smtp_use_tls: bool = True


class ProductionDeploymentManager:
    """Manages production deployment and configuration"""
    
    def __init__(self):
        self.config = ProductionConfig()
        self.deployment_path = Path("/opt/atom/production")
        self.config_path = self.deployment_path / "config"
        self.logs_path = self.deployment_path / "logs"
        self.backups_path = self.deployment_path / "backups"
        
    def setup_production_environment(self) -> Dict[str, Any]:
        """Setup production environment"""
        try:
            print("🚀 Setting Up Production Environment")
            print("=" * 60)
            
            # Create directory structure
            self._create_directory_structure()
            
            # Generate configuration files
            self._generate_configuration_files()
            
            # Setup security configuration
            self._setup_security_configuration()
            
            # Configure monitoring and logging
            self._setup_monitoring_configuration()
            
            # Setup database configuration
            self._setup_database_configuration()
            
            # Create deployment scripts
            self._create_deployment_scripts()
            
            # Setup health checks
            self._setup_health_checks()
            
            print("✅ Production environment setup completed")
            return {"success": True, "message": "Production environment configured successfully"}
            
        except Exception as e:
            logger.error(f"Error setting up production environment: {str(e)}")
            return {"success": False, "error": str(e)}
    
    def _create_directory_structure(self):
        """Create production directory structure"""
        print("\n📁 Creating Directory Structure...")
        
        directories = [
            self.deployment_path,
            self.config_path,
            self.logs_path,
            self.backups_path,
            self.deployment_path / "scripts",
            self.deployment_path / "ssl",
            self.deployment_path / "data",
            self.deployment_path / "temp"
        ]
        
        for directory in directories:
            directory.mkdir(parents=True, exist_ok=True)
            print(f"   ✅ Created: {directory}")
    
    def _generate_configuration_files(self):
        """Generate production configuration files"""
        print("\n⚙️ Generating Configuration Files...")
        
        # Main production config
        config_data = {
            "environment": self.config.environment,
            "debug": self.config.debug,
            "log_level": self.config.log_level,
            
            "database": {
                "url": self.config.database_url,
                "pool_size": self.config.database_pool_size,
                "max_overflow": self.config.database_max_overflow,
                "pool_timeout": self.config.database_pool_timeout,
                "pool_recycle": self.config.database_pool_recycle
            },
            
            "redis": {
                "url": self.config.redis_url,
                "db": self.config.redis_db,
                "password": self.config.redis_password,
                "max_connections": self.config.redis_max_connections
            },
            
            "websocket": {
                "host": self.config.websocket_host,
                "port": self.config.websocket_port,
                "ssl_enabled": self.config.websocket_ssl_enabled,
                "cert_file": self.config.websocket_cert_file,
                "key_file": self.config.websocket_key_file
            },
            
            "security": {
                "secret_key": self.config.secret_key or str(uuid.uuid4()),
                "jwt_secret_key": self.config.jwt_secret_key or str(uuid.uuid4()),
                "jwt_expiration_hours": self.config.jwt_expiration_hours,
                "session_timeout_minutes": self.config.session_timeout_minutes,
                "cors_origins": self.config.cors_origins,
                "rate_limit_enabled": self.config.rate_limit_enabled,
                "rate_limit_requests": self.config.rate_limit_requests,
                "rate_limit_window_minutes": self.config.rate_limit_window_minutes
            },
            
            "monitoring": {
                "prometheus_enabled": self.config.prometheus_enabled,
                "prometheus_port": self.config.prometheus_port,
                "health_check_enabled": self.config.health_check_enabled,
                "health_check_port": self.config.health_check_port,
                "metrics_collection_enabled": self.config.metrics_collection_enabled,
                "log_analytics_enabled": self.config.log_analytics_enabled
            },
            
            "performance": {
                "max_concurrent_workflows": self.config.max_concurrent_workflows,
                "workflow_timeout_minutes": self.config.workflow_timeout_minutes,
                "task_queue_max_size": self.config.task_queue_max_size,
                "cache_ttl_seconds": self.config.cache_ttl_seconds
            },
            
            "backup": {
                "enabled": self.config.backup_enabled,
                "schedule_hours": self.config.backup_schedule_hours,
                "retention_days": self.config.backup_retention_days,
                "auto_recovery_enabled": self.config.auto_recovery_enabled
            }
        }
        
        # Write YAML configuration
        config_file = self.config_path / "production.yaml"
        with open(config_file, 'w') as f:
            yaml.dump(config_data, f, default_flow_style=False)
        print(f"   ✅ Created: {config_file}")
        
        # Write JSON configuration (for Node.js services)
        json_config_file = self.config_path / "production.json"
        with open(json_config_file, 'w') as f:
            json.dump(config_data, f, indent=2)
        print(f"   ✅ Created: {json_config_file}")
        
        # Environment variables file
        env_file = self.config_path / ".env"
        env_content = f"""
# Production Environment Variables
ATOM_ENV={self.config.environment}
ATOM_DEBUG={self.config.debug}
ATOM_LOG_LEVEL={self.config.log_level}

# Database
DATABASE_URL={self.config.database_url}
DATABASE_POOL_SIZE={self.config.database_pool_size}

# Redis
REDIS_URL={self.config.redis_url}
REDIS_DB={self.config.redis_db}

# WebSocket
WEBSOCKET_HOST={self.config.websocket_host}
WEBSOCKET_PORT={self.config.websocket_port}
WEBSOCKET_SSL_ENABLED={self.config.websocket_ssl_enabled}

# Security
SECRET_KEY={config_data['security']['secret_key']}
JWT_SECRET_KEY={config_data['security']['jwt_secret_key']}
JWT_EXPIRATION_HOURS={self.config.jwt_expiration_hours}

# Monitoring
PROMETHEUS_ENABLED={self.config.prometheus_enabled}
PROMETHEUS_PORT={self.config.prometheus_port}
HEALTH_CHECK_ENABLED={self.config.health_check_enabled}
HEALTH_CHECK_PORT={self.config.health_check_port}

# Performance
MAX_CONCURRENT_WORKFLOWS={self.config.max_concurrent_workflows}
WORKFLOW_TIMEOUT_MINUTES={self.config.workflow_timeout_minutes}

# Backup
BACKUP_ENABLED={self.config.backup_enabled}
BACKUP_SCHEDULE_HOURS={self.config.backup_schedule_hours}
BACKUP_RETENTION_DAYS={self.config.backup_retention_days}
"""
        
        with open(env_file, 'w') as f:
            f.write(env_content.strip())
        print(f"   ✅ Created: {env_file}")
    
    def _setup_security_configuration(self):
        """Setup security configuration"""
        print("\n🔒 Setting Up Security Configuration...")
        
        # Generate SSL certificate (self-signed for development)
        ssl_config = {
            "country": "US",
            "state": "California",
            "locality": "San Francisco",
            "organization": "Atom Workflow Automation",
            "common_name": "localhost",
            "email": "noreply@atom.com"
        }
        
        ssl_config_file = self.config_path / "ssl_config.json"
        with open(ssl_config_file, 'w') as f:
            json.dump(ssl_config, f, indent=2)
        print(f"   ✅ Created: {ssl_config_file}")
        
        # Nginx configuration for reverse proxy
        nginx_config = """
server {
    listen 80;
    server_name localhost;
    return 301 https://$server_name$request_uri;
}

server {
    listen 443 ssl http2;
    server_name localhost;

    ssl_certificate /opt/atom/production/ssl/cert.pem;
    ssl_certificate_key /opt/atom/production/ssl/key.pem;
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers ECDHE-RSA-AES256-GCM-SHA512:DHE-RSA-AES256-GCM-SHA512:ECDHE-RSA-AES256-GCM-SHA384:DHE-RSA-AES256-GCM-SHA384;
    ssl_prefer_server_ciphers off;
    ssl_session_cache shared:SSL:10m;
    ssl_session_timeout 10m;

    # WebSocket proxy
    location /ws {
        proxy_pass http://localhost:8765;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        
        # WebSocket specific headers
        proxy_read_timeout 86400s;
        proxy_send_timeout 86400s;
    }

    # API proxy
    location /api {
        proxy_pass http://localhost:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    # Health check
    location /health {
        proxy_pass http://localhost:8080;
        access_log off;
    }

    # Static files
    location /static {
        alias /opt/atom/production/static;
        expires 1y;
        add_header Cache-Control "public, immutable";
    }

    # Security headers
    add_header X-Frame-Options "SAMEORIGIN" always;
    add_header X-XSS-Protection "1; mode=block" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header Referrer-Policy "no-referrer-when-downgrade" always;
    add_header Content-Security-Policy "default-src 'self' http: https: data: blob: 'unsafe-inline'" always;
}
"""
        
        nginx_config_file = self.config_path / "nginx.conf"
        with open(nginx_config_file, 'w') as f:
            f.write(nginx_config.strip())
        print(f"   ✅ Created: {nginx_config_file}")
        
        # Security policies configuration
        security_policies = {
            "password_policy": {
                "min_length": 12,
                "require_uppercase": True,
                "require_lowercase": True,
                "require_numbers": True,
                "require_symbols": True,
                "max_age_days": 90
            },
            "session_policy": {
                "timeout_minutes": 30,
                "max_concurrent_sessions": 3,
                "require_reauth_minutes": 60
            },
            "api_policy": {
                "rate_limit_per_minute": 100,
                "rate_limit_per_hour": 1000,
                "max_request_size_mb": 10,
                "allowed_methods": ["GET", "POST", "PUT", "DELETE", "PATCH"],
                "cors_policy": {
                    "allowed_origins": ["https://localhost"],
                    "allowed_methods": ["GET", "POST", "PUT", "DELETE", "OPTIONS"],
                    "allowed_headers": ["Authorization", "Content-Type", "X-Requested-With"],
                    "max_age_seconds": 3600
                }
            }
        }
        
        security_policies_file = self.config_path / "security_policies.json"
        with open(security_policies_file, 'w') as f:
            json.dump(security_policies, f, indent=2)
        print(f"   ✅ Created: {security_policies_file}")
    
    def _setup_monitoring_configuration(self):
        """Setup monitoring and logging configuration"""
        print("\n📊 Setting Up Monitoring Configuration...")
        
        # Prometheus configuration
        prometheus_config = """
global:
  scrape_interval: 15s
  evaluation_interval: 15s

rule_files:
  - "workflow_alerts.yml"

alerting:
  alertmanagers:
    - static_configs:
        - targets:
          - alertmanager:9093

scrape_configs:
  - job_name: 'atom-workflow-api'
    static_configs:
      - targets: ['localhost:8000']
    metrics_path: '/metrics'
    scrape_interval: 30s

  - job_name: 'atom-websocket-server'
    static_configs:
      - targets: ['localhost:8765']
    metrics_path: '/metrics'
    scrape_interval: 30s

  - job_name: 'atom-health-checks'
    static_configs:
      - targets: ['localhost:8080']
    metrics_path: '/metrics'
    scrape_interval: 60s

  - job_name: 'node-exporter'
    static_configs:
      - targets: ['localhost:9100']

  - job_name: 'redis-exporter'
    static_configs:
      - targets: ['localhost:9121']

  - job_name: 'postgres-exporter'
    static_configs:
      - targets: ['localhost:9187']
"""
        
        prometheus_config_file = self.config_path / "prometheus.yml"
        with open(prometheus_config_file, 'w') as f:
            f.write(prometheus_config.strip())
        print(f"   ✅ Created: {prometheus_config_file}")
        
        # Workflow alerts configuration
        workflow_alerts = """
groups:
  - name: workflow_alerts
    rules:
      - alert: WorkflowExecutionFailure
        expr: workflow_execution_failures_total > 0
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "Workflow execution failed"
          description: "Workflow {{ $labels.workflow_id }} has failed {{ $value }} times in the last 5 minutes"

      - alert: HighWorkflowExecutionTime
        expr: workflow_execution_duration_seconds > 300
        for: 10m
        labels:
          severity: warning
        annotations:
          summary: "High workflow execution time"
          description: "Workflow {{ $labels.workflow_id }} has been running for {{ $value }} seconds"

      - alert: WebSocketConnectionFailure
        expr: websocket_connection_errors_total > 10
        for: 2m
        labels:
          severity: critical
        annotations:
          summary: "High WebSocket connection errors"
          description: "{{ $value }} WebSocket connection errors in the last 2 minutes"

      - alert: DatabaseConnectionFailure
        expr: up{job="postgres-exporter"} == 0
        for: 1m
        labels:
          severity: critical
        annotations:
          summary: "Database connection failed"
          description: "Database is down for more than 1 minute"

      - alert: RedisConnectionFailure
        expr: up{job="redis-exporter"} == 0
        for: 1m
        labels:
          severity: critical
        annotations:
          summary: "Redis connection failed"
          description: "Redis is down for more than 1 minute"

      - alert: HighMemoryUsage
        expr: (node_memory_MemTotal_bytes - node_memory_MemAvailable_bytes) / node_memory_MemTotal_bytes > 0.8
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "High memory usage"
          description: "Memory usage is {{ $value | humanizePercentage }}"

      - alert: HighCPUUsage
        expr: 100 - (avg by(instance) (irate(node_cpu_seconds_total{mode="idle"}[5m])) * 100) > 80
        for: 10m
        labels:
          severity: warning
        annotations:
          summary: "High CPU usage"
          description: "CPU usage is {{ $value | humanizePercentage }}"
"""
        
        workflow_alerts_file = self.config_path / "workflow_alerts.yml"
        with open(workflow_alerts_file, 'w') as f:
            f.write(workflow_alerts.strip())
        print(f"   ✅ Created: {workflow_alerts_file}")
        
        # Grafana dashboard configuration
        grafana_dashboard = {
            "dashboard": {
                "id": None,
                "title": "Atom Workflow Automation Dashboard",
                "tags": ["atom", "workflow", "automation"],
                "timezone": "browser",
                "panels": [
                    {
                        "id": 1,
                        "title": "Workflow Executions",
                        "type": "graph",
                        "targets": [
                            {
                                "expr": "rate(workflow_executions_total[5m])",
                                "legendFormat": "Executions/sec"
                            },
                            {
                                "expr": "rate(workflow_execution_failures_total[5m])",
                                "legendFormat": "Failures/sec"
                            }
                        ],
                        "yAxes": [
                            {"label": "Rate per second"}
                        ]
                    },
                    {
                        "id": 2,
                        "title": "WebSocket Connections",
                        "type": "stat",
                        "targets": [
                            {
                                "expr": "websocket_connections_active",
                                "legendFormat": "Active Connections"
                            }
                        ]
                    },
                    {
                        "id": 3,
                        "title": "Workflow Execution Duration",
                        "type": "heatmap",
                        "targets": [
                            {
                                "expr": "workflow_execution_duration_seconds",
                                "legendFormat": "{{ workflow_id }}"
                            }
                        ]
                    },
                    {
                        "id": 4,
                        "title": "System Resources",
                        "type": "graph",
                        "targets": [
                            {
                                "expr": "100 - (avg by(instance) (irate(node_cpu_seconds_total{mode=\"idle\"}[5m])) * 100)",
                                "legendFormat": "CPU %"
                            },
                            {
                                "expr": "(node_memory_MemTotal_bytes - node_memory_MemAvailable_bytes) / node_memory_MemTotal_bytes * 100",
                                "legendFormat": "Memory %"
                            }
                        ]
                    }
                ],
                "time": {
                    "from": "now-1h",
                    "to": "now"
                },
                "refresh": "30s"
            }
        }
        
        grafana_dashboard_file = self.config_path / "grafana_dashboard.json"
        with open(grafana_dashboard_file, 'w') as f:
            json.dump(grafana_dashboard, f, indent=2)
        print(f"   ✅ Created: {grafana_dashboard_file}")
        
        # Logging configuration
        logging_config = {
            "version": 1,
            "disable_existing_loggers": False,
            "formatters": {
                "detailed": {
                    "format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
                },
                "json": {
                    "()": "pythonjsonlogger.jsonlogger.JsonFormatter",
                    "format": "%(asctime)s %(name)s %(levelname)s %(message)s"
                }
            },
            "handlers": {
                "console": {
                    "class": "logging.StreamHandler",
                    "level": "INFO",
                    "formatter": "detailed",
                    "stream": "ext://sys.stdout"
                },
                "file": {
                    "class": "logging.handlers.RotatingFileHandler",
                    "level": "DEBUG",
                    "formatter": "json",
                    "filename": "/opt/atom/production/logs/atom.log",
                    "maxBytes": 10485760,  # 10MB
                    "backupCount": 5
                },
                "workflow_file": {
                    "class": "logging.handlers.RotatingFileHandler",
                    "level": "INFO",
                    "formatter": "json",
                    "filename": "/opt/atom/production/logs/workflows.log",
                    "maxBytes": 10485760,  # 10MB
                    "backupCount": 10
                },
                "websocket_file": {
                    "class": "logging.handlers.RotatingFileHandler",
                    "level": "INFO",
                    "formatter": "json",
                    "filename": "/opt/atom/production/logs/websocket.log",
                    "maxBytes": 10485760,  # 10MB
                    "backupCount": 10
                }
            },
            "loggers": {
                "": {
                    "level": "INFO",
                    "handlers": ["console", "file"]
                },
                "atom.workflows": {
                    "level": "INFO",
                    "handlers": ["workflow_file"],
                    "propagate": False
                },
                "atom.websocket": {
                    "level": "INFO",
                    "handlers": ["websocket_file"],
                    "propagate": False
                }
            }
        }
        
        logging_config_file = self.config_path / "logging.yaml"
        with open(logging_config_file, 'w') as f:
            yaml.dump(logging_config, f)
        print(f"   ✅ Created: {logging_config_file}")
    
    def _setup_database_configuration(self):
        """Setup database configuration"""
        print("\n🗄️ Setting Up Database Configuration...")
        
        # PostgreSQL configuration
        postgres_config = """
# PostgreSQL Configuration for Atom Workflow Automation

# Connection Settings
listen_addresses = 'localhost'
port = 5432
max_connections = 200

# Memory Settings
shared_buffers = 256MB
effective_cache_size = 1GB
work_mem = 4MB
maintenance_work_mem = 64MB

# WAL Settings
wal_level = replica
max_wal_size = 1GB
min_wal_size = 80MB
checkpoint_completion_target = 0.9

# Query Performance
random_page_cost = 1.1
effective_io_concurrency = 200

# Logging Settings
log_statement = 'all'
log_min_duration_statement = 1000
log_checkpoints = on
log_connections = on
log_disconnections = on
log_lock_waits = on

# Security Settings
ssl = on
password_encryption = scram-sha-256
"""
        
        postgres_config_file = self.config_path / "postgresql.conf"
        with open(postgres_config_file, 'w') as f:
            f.write(postgres_config.strip())
        print(f"   ✅ Created: {postgres_config_file}")
        
        # Database migration script
        migration_script = """
#!/bin/bash
# Database Migration Script for Atom Workflow Automation

set -e

echo "🗄️ Starting Database Migration..."

# Database connection parameters
DB_HOST="localhost"
DB_PORT="5432"
DB_NAME="atom_production"
DB_USER="atom_user"
DB_PASSWORD="CHANGE_THIS_PASSWORD"

# Create database if it doesn't exist
echo "📝 Creating database..."
PGPASSWORD=$DB_PASSWORD psql -h $DB_HOST -p $DB_PORT -U postgres -c "CREATE DATABASE IF NOT EXISTS $DB_NAME;"

# Create user if it doesn't exist
echo "👤 Creating user..."
PGPASSWORD=$DB_PASSWORD psql -h $DB_HOST -p $DB_PORT -U postgres -c "DO $$\\nBEGIN;\\nIF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = '$DB_USER') THEN\\n    CREATE USER $DB_USER WITH PASSWORD '$DB_PASSWORD';\\nEND IF;\\n$$;"

# Grant privileges
echo "🔐 Granting privileges..."
PGPASSWORD=$DB_PASSWORD psql -h $DB_HOST -p $DB_PORT -U postgres -c "GRANT ALL PRIVILEGES ON DATABASE $DB_NAME TO $DB_USER;"

# Run migration files
echo "🔄 Running migrations..."
export PGPASSWORD=$DB_PASSWORD

# Create tables
psql -h $DB_HOST -p $DB_PORT -U $DB_USER -d $DB_NAME << 'EOF'
-- Workflows table
CREATE TABLE IF NOT EXISTS workflows (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(255) NOT NULL,
    description TEXT,
    category VARCHAR(100),
    user_id UUID NOT NULL,
    parameters JSONB DEFAULT '{}',
    template_id UUID,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    version INTEGER DEFAULT 1
);

-- Workflow executions table
CREATE TABLE IF NOT EXISTS workflow_executions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    workflow_id UUID NOT NULL REFERENCES workflows(id),
    status VARCHAR(50) NOT NULL,
    input_data JSONB DEFAULT '{}',
    output_data JSONB DEFAULT '{}',
    error_message TEXT,
    execution_time_seconds DECIMAL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    started_at TIMESTAMP WITH TIME ZONE,
    completed_at TIMESTAMP WITH TIME ZONE,
    user_id UUID NOT NULL
);

-- Workflow steps table
CREATE TABLE IF NOT EXISTS workflow_steps (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    execution_id UUID NOT NULL REFERENCES workflow_executions(id),
    step_order INTEGER NOT NULL,
    service VARCHAR(100) NOT NULL,
    action VARCHAR(100) NOT NULL,
    parameters JSONB DEFAULT '{}',
    status VARCHAR(50) NOT NULL,
    result JSONB,
    error_message TEXT,
    execution_time_seconds DECIMAL,
    started_at TIMESTAMP WITH TIME ZONE,
    completed_at TIMESTAMP WITH TIME ZONE
);

-- Templates table
CREATE TABLE IF NOT EXISTS workflow_templates (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(255) NOT NULL,
    description TEXT,
    category VARCHAR(100),
    author VARCHAR(100) NOT NULL,
    version VARCHAR(50) NOT NULL,
    parameters JSONB DEFAULT '{}',
    steps JSONB NOT NULL,
    tags TEXT[],
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Users table
CREATE TABLE IF NOT EXISTS users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    username VARCHAR(100) UNIQUE NOT NULL,
    email VARCHAR(255) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    is_active BOOLEAN DEFAULT TRUE,
    is_admin BOOLEAN DEFAULT FALSE,
    last_login TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Sessions table
CREATE TABLE IF NOT EXISTS sessions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id),
    session_token VARCHAR(255) UNIQUE NOT NULL,
    expires_at TIMESTAMP WITH TIME ZONE NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Audit log table
CREATE TABLE IF NOT EXISTS audit_log (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(id),
    action VARCHAR(100) NOT NULL,
    resource_type VARCHAR(100),
    resource_id UUID,
    old_values JSONB,
    new_values JSONB,
    ip_address INET,
    user_agent TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Indexes for performance
CREATE INDEX IF NOT EXISTS idx_workflows_user_id ON workflows(user_id);
CREATE INDEX IF NOT EXISTS idx_workflows_template_id ON workflows(template_id);
CREATE INDEX IF NOT EXISTS idx_workflow_executions_workflow_id ON workflow_executions(workflow_id);
CREATE INDEX IF NOT EXISTS idx_workflow_executions_user_id ON workflow_executions(user_id);
CREATE INDEX IF NOT EXISTS idx_workflow_executions_status ON workflow_executions(status);
CREATE INDEX IF NOT EXISTS idx_workflow_steps_execution_id ON workflow_steps(execution_id);
CREATE INDEX IF NOT EXISTS idx_workflow_steps_status ON workflow_steps(status);
CREATE INDEX IF NOT EXISTS idx_sessions_user_id ON sessions(user_id);
CREATE INDEX IF NOT EXISTS idx_sessions_token ON sessions(session_token);
CREATE INDEX IF NOT EXISTS idx_audit_log_user_id ON audit_log(user_id);
CREATE INDEX IF NOT EXISTS idx_audit_log_created_at ON audit_log(created_at);

EOF

echo "✅ Database migration completed successfully"
"""
        
        migration_script_file = self.config_path / "migrate_database.sh"
        with open(migration_script_file, 'w') as f:
            f.write(migration_script.strip())
        
        # Make script executable
        os.chmod(migration_script_file, 0o755)
        print(f"   ✅ Created: {migration_script_file}")
        
        # Redis configuration
        redis_config = """
# Redis Configuration for Atom Workflow Automation

# Network
bind 127.0.0.1
port 6379
protected-mode yes
requirepass CHANGE_THIS_REDIS_PASSWORD

# Memory
maxmemory 512mb
maxmemory-policy allkeys-lru

# Persistence
save 900 1
save 300 10
save 60 10000

# Security
rename-command FLUSHDB ""
rename-command FLUSHALL ""
rename-command DEBUG ""
rename-command CONFIG ""

# Performance
tcp-keepalive 300
timeout 0

# Logging
loglevel notice
logfile /var/log/redis/redis-server.log

# Clients
maxclients 10000
"""
        
        redis_config_file = self.config_path / "redis.conf"
        with open(redis_config_file, 'w') as f:
            f.write(redis_config.strip())
        print(f"   ✅ Created: {redis_config_file}")
    
    def _create_deployment_scripts(self):
        """Create deployment and management scripts"""
        print("\n🚀 Creating Deployment Scripts...")
        
        # Main deployment script
        deploy_script = """#!/bin/bash
# Main Deployment Script for Atom Workflow Automation

set -e

DEPLOYMENT_PATH="/opt/atom/production"
BACKUP_PATH="/opt/atom/production/backups"
LOG_FILE="/opt/atom/production/logs/deploy.log"

echo "🚀 Starting Atom Workflow Automation Deployment..."
echo "$(date): Deployment started" >> $LOG_FILE

# Function to log messages
log() {
    echo "$1"
    echo "$(date): $1" >> $LOG_FILE
}

# Check if running as root
if [ "$EUID" -ne 0 ]; then
    log "❌ This script must be run as root"
    exit 1
fi

# Create backup if this is not a fresh deployment
if [ -d "$DEPLOYMENT_PATH" ] && [ "$(ls -A $DEPLOYMENT_PATH)" ]; then
    log "📦 Creating backup..."
    BACKUP_NAME="backup_$(date +%Y%m%d_%H%M%S)"
    mkdir -p "$BACKUP_PATH/$BACKUP_NAME"
    cp -r $DEPLOYMENT_PATH/* "$BACKUP_PATH/$BACKUP_NAME/" 2>/dev/null || true
    log "✅ Backup created: $BACKUP_NAME"
fi

# Stop existing services
log "🛑 Stopping existing services..."
systemctl stop atom-workflow-api || true
systemctl stop atom-websocket-server || true
systemctl stop atom-scheduler || true

# Update application code
log "📥 Updating application code..."
cd $DEPLOYMENT_PATH
if [ -d "git" ]; then
    cd git
    git pull origin main
    cd ..
    rsync -av --exclude '.git' git/ $DEPLOYMENT_PATH/
fi

# Install dependencies
log "📦 Installing Python dependencies..."
python3 -m pip install -r requirements.txt --upgrade

# Run database migrations
log "🗄️ Running database migrations..."
$DEPLOYMENT_PATH/config/migrate_database.sh

# Update configuration
log "⚙️ Updating configuration..."
if [ ! -f "$DEPLOYMENT_PATH/config/.env" ]; then
    cp $DEPLOYMENT_PATH/config/.env.example $DEPLOYMENT_PATH/config/.env
    log "⚠️ Please configure environment variables in $DEPLOYMENT_PATH/config/.env"
fi

# Build static assets
log "🎨 Building static assets..."
npm run build || echo "⚠️ npm build failed, continuing..."

# Set permissions
log "🔒 Setting permissions..."
chown -R atom:atom $DEPLOYMENT_PATH
chmod +x $DEPLOYMENT_PATH/scripts/*.sh

# Start services
log "🚀 Starting services..."
systemctl daemon-reload
systemctl enable atom-workflow-api
systemctl enable atom-websocket-server
systemctl enable atom-scheduler
systemctl start atom-workflow-api
systemctl start atom-websocket-server
systemctl start atom-scheduler

# Health check
log "🏥 Running health checks..."
sleep 10

if curl -f http://localhost:8080/health > /dev/null 2>&1; then
    log "✅ Health check passed"
else
    log "❌ Health check failed"
    echo "$(date): Health check failed" >> $LOG_FILE
    exit 1
fi

log "🎉 Deployment completed successfully!"
echo "$(date): Deployment completed" >> $LOG_FILE

# Display status
systemctl status atom-workflow-api --no-pager -l
systemctl status atom-websocket-server --no-pager -l
systemctl status atom-scheduler --no-pager -l
"""
        
        deploy_script_file = self.deployment_path / "scripts" / "deploy.sh"
        with open(deploy_script_file, 'w') as f:
            f.write(deploy_script.strip())
        os.chmod(deploy_script_file, 0o755)
        print(f"   ✅ Created: {deploy_script_file}")
        
        # Systemd service files
        workflow_api_service = """[Unit]
Description=Atom Workflow API
After=network.target postgresql.service redis.service

[Service]
Type=exec
User=atom
Group=atom
WorkingDirectory=/opt/atom/production
Environment=PATH=/opt/atom/production/venv/bin
ExecStart=/opt/atom/production/venv/bin/python -m uvicorn main:app --host 0.0.0.0 --port 8000
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
"""
        
        workflow_api_service_file = self.deployment_path / "scripts" / "atom-workflow-api.service"
        with open(workflow_api_service_file, 'w') as f:
            f.write(workflow_api_service.strip())
        print(f"   ✅ Created: {workflow_api_service_file}")
        
        websocket_server_service = """[Unit]
Description=Atom WebSocket Server
After=network.target postgresql.service redis.service

[Service]
Type=exec
User=atom
Group=atom
WorkingDirectory=/opt/atom/production
Environment=PATH=/opt/atom/production/venv/bin
ExecStart=/opt/atom/production/venv/bin/python websocket_server.py
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
"""
        
        websocket_server_service_file = self.deployment_path / "scripts" / "atom-websocket-server.service"
        with open(websocket_server_service_file, 'w') as f:
            f.write(websocket_server_service.strip())
        print(f"   ✅ Created: {websocket_server_service_file}")
        
        # Monitoring script
        monitoring_script = """#!/bin/bash
# Monitoring Script for Atom Workflow Automation

DEPLOYMENT_PATH="/opt/atom/production"
LOG_FILE="/opt/atom/production/logs/monitoring.log"

log() {
    echo "$1"
    echo "$(date): $1" >> $LOG_FILE
}

# Check service status
check_service() {
    local service=$1
    if systemctl is-active --quiet $service; then
        log "✅ $service is running"
    else
        log "❌ $service is not running"
        systemctl restart $service
    fi
}

# Check system resources
check_resources() {
    # CPU usage
    CPU_USAGE=$(top -bn1 | grep "Cpu(s)" | sed "s/.*, *\\([0-9.]*\\)%* id.*/\\1/" | awk '{print 100 - $1}')
    if (( $(echo "$CPU_USAGE > 80" | bc -l) )); then
        log "⚠️ High CPU usage: ${CPU_USAGE}%"
    fi
    
    # Memory usage
    MEMORY_USAGE=$(free | grep Mem | awk '{printf("%.2f", $3/$2 * 100.0)}')
    if (( $(echo "$MEMORY_USAGE > 80" | bc -l) )); then
        log "⚠️ High memory usage: ${MEMORY_USAGE}%"
    fi
    
    # Disk usage
    DISK_USAGE=$(df / | awk 'NR==2 {print $5}' | sed 's/%//')
    if [ $DISK_USAGE -gt 80 ]; then
        log "⚠️ High disk usage: ${DISK_USAGE}%"
    fi
}

# Check connectivity
check_connectivity() {
    # Database
    if PGPASSWORD=$DB_PASSWORD psql -h $DB_HOST -p $DB_PORT -U $DB_USER -d $DB_NAME -c "SELECT 1;" > /dev/null 2>&1; then
        log "✅ Database connection is OK"
    else
        log "❌ Database connection failed"
    fi
    
    # Redis
    if redis-cli -h $REDIS_HOST -p $REDIS_PORT -a $REDIS_PASSWORD ping > /dev/null 2>&1; then
        log "✅ Redis connection is OK"
    else
        log "❌ Redis connection failed"
    fi
    
    # WebSocket
    if curl -f http://localhost:8765/health > /dev/null 2>&1; then
        log "✅ WebSocket server is responding"
    else
        log "❌ WebSocket server is not responding"
    fi
}

log "🔍 Starting system monitoring..."

# Check services
check_service "atom-workflow-api"
check_service "atom-websocket-server"
check_service "atom-scheduler"

# Check resources
check_resources

# Check connectivity
check_connectivity

log "✅ Monitoring completed"
"""
        
        monitoring_script_file = self.deployment_path / "scripts" / "monitor.sh"
        with open(monitoring_script_file, 'w') as f:
            f.write(monitoring_script.strip())
        os.chmod(monitoring_script_file, 0o755)
        print(f"   ✅ Created: {monitoring_script_file}")
        
        # Backup script
        backup_script = """#!/bin/bash
# Backup Script for Atom Workflow Automation

BACKUP_PATH="/opt/atom/production/backups"
DB_BACKUP_PATH="$BACKUP_PATH/database"
CONFIG_BACKUP_PATH="$BACKUP_PATH/config"
LOG_FILE="/opt/atom/production/logs/backup.log"

log() {
    echo "$1"
    echo "$(date): $1" >> $LOG_FILE
}

# Create backup directories
mkdir -p $DB_BACKUP_PATH
mkdir -p $CONFIG_BACKUP_PATH

log "📦 Starting backup process..."

# Database backup
log "🗄️ Creating database backup..."
DB_NAME="atom_production"
DB_USER="atom_user"
DB_PASSWORD="CHANGE_THIS_PASSWORD"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)

PGPASSWORD=$DB_PASSWORD pg_dump -h localhost -U $DB_USER -d $DB_NAME | gzip > "$DB_BACKUP_PATH/db_backup_$TIMESTAMP.sql.gz"

# Configuration backup
log "⚙️ Creating configuration backup..."
tar -czf "$CONFIG_BACKUP_PATH/config_backup_$TIMESTAMP.tar.gz" /opt/atom/production/config/

# Application backup
log "📱 Creating application backup..."
tar -czf "$BACKUP_PATH/app_backup_$TIMESTAMP.tar.gz" /opt/atom/production/ --exclude=/opt/atom/production/logs --exclude=/opt/atom/production/backups --exclude=/opt/atom/production/temp

# Cleanup old backups (keep last 30 days)
log "🧹 Cleaning up old backups..."
find $BACKUP_PATH -name "*.gz" -mtime +30 -delete

log "✅ Backup completed successfully"
log "📊 Backup size: $(du -sh $BACKUP_PATH | cut -f1)"
"""
        
        backup_script_file = self.deployment_path / "scripts" / "backup.sh"
        with open(backup_script_file, 'w') as f:
            f.write(backup_script.strip())
        os.chmod(backup_script_file, 0o755)
        print(f"   ✅ Created: {backup_script_file}")
    
    def _setup_health_checks(self):
        """Setup health check endpoints"""
        print("\n🏥 Setting Up Health Checks...")
        
        health_check_server = """
#!/usr/bin/env python3
"""
Health Check Server for Atom Workflow Automation
"""

import os
import sys
import json
import asyncio
import aiohttp
import psycopg2
import redis
from datetime import datetime
from pathlib import Path

# Add deployment path to Python path
sys.path.append('/opt/atom/production')

class HealthCheckServer:
    def __init__(self):
        self.port = 8080
        self.db_url = os.getenv('DATABASE_URL', '')
        self.redis_url = os.getenv('REDIS_URL', '')
        
    async def health_check(self, request):
        """Main health check endpoint"""
        status = {
            "status": "healthy",
            "timestamp": datetime.now().isoformat(),
            "version": "1.0.0",
            "checks": {}
        }
        
        overall_healthy = True
        
        # Database health check
        try:
            conn = psycopg2.connect(self.db_url)
            cursor = conn.cursor()
            cursor.execute("SELECT 1")
            cursor.close()
            conn.close()
            status["checks"]["database"] = {"status": "healthy", "message": "Database connection successful"}
        except Exception as e:
            status["checks"]["database"] = {"status": "unhealthy", "message": str(e)}
            overall_healthy = False
        
        # Redis health check
        try:
            r = redis.from_url(self.redis_url)
            r.ping()
            status["checks"]["redis"] = {"status": "healthy", "message": "Redis connection successful"}
        except Exception as e:
            status["checks"]["redis"] = {"status": "unhealthy", "message": str(e)}
            overall_healthy = False
        
        # WebSocket server health check
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get('http://localhost:8765/health', timeout=5) as response:
                    if response.status == 200:
                        status["checks"]["websocket"] = {"status": "healthy", "message": "WebSocket server responding"}
                    else:
                        raise Exception(f"WebSocket server returned status {response.status}")
        except Exception as e:
            status["checks"]["websocket"] = {"status": "unhealthy", "message": str(e)}
            overall_healthy = False
        
        # API server health check
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get('http://localhost:8000/health', timeout=5) as response:
                    if response.status == 200:
                        status["checks"]["api"] = {"status": "healthy", "message": "API server responding"}
                    else:
                        raise Exception(f"API server returned status {response.status}")
        except Exception as e:
            status["checks"]["api"] = {"status": "unhealthy", "message": str(e)}
            overall_healthy = False
        
        # System resources check
        try:
            import psutil
            
            cpu_percent = psutil.cpu_percent(interval=1)
            memory = psutil.virtual_memory()
            disk = psutil.disk_usage('/')
            
            resources = {
                "cpu_percent": cpu_percent,
                "memory_percent": memory.percent,
                "disk_percent": (disk.used / disk.total) * 100
            }
            
            # Check if resources are within acceptable limits
            if cpu_percent < 80 and memory.percent < 80 and resources["disk_percent"] < 80:
                status["checks"]["resources"] = {"status": "healthy", "data": resources}
            else:
                status["checks"]["resources"] = {"status": "warning", "data": resources}
                
        except Exception as e:
            status["checks"]["resources"] = {"status": "unhealthy", "message": str(e)}
            overall_healthy = False
        
        # Set overall status
        if not overall_healthy:
            status["status"] = "unhealthy"
        
        # Return appropriate HTTP status
        http_status = 200 if overall_healthy else 503
        
        return web.json_response(status, status=http_status)
    
    async def ready_check(self, request):
        """Readiness check endpoint"""
        return web.json_response({
            "status": "ready",
            "timestamp": datetime.now().isoformat()
        })
    
    async def live_check(self, request):
        """Liveness check endpoint"""
        return web.json_response({
            "status": "alive",
            "timestamp": datetime.now().isoformat()
        })
    
    async def start_server(self):
        """Start the health check server"""
        app = web.Application()
        
        app.router.add_get('/health', self.health_check)
        app.router.add_get('/ready', self.ready_check)
        app.router.add_get('/live', self.live_check)
        
        runner = web.AppRunner(app)
        await runner.setup()
        site = web.TCPSite(runner, 'localhost', self.port)
        await site.start()
        print(f"🏥 Health check server started on port {self.port}")

if __name__ == '__main__':
    health_server = HealthCheckServer()
    asyncio.run(health_server.start_server())
"""
        
        health_check_file = self.deployment_path / "health_check_server.py"
        with open(health_check_file, 'w') as f:
            f.write(health_check_server.strip())
        os.chmod(health_check_file, 0o755)
        print(f"   ✅ Created: {health_check_file}")
    
    def create_cron_jobs(self):
        """Create cron jobs for maintenance tasks"""
        print("\n⏰ Creating Cron Jobs...")
        
        crontab_content = """
# Cron Jobs for Atom Workflow Automation
# Edit with: crontab -e -u atom

# Backup every day at 2 AM
0 2 * * * /opt/atom/production/scripts/backup.sh >> /opt/atom/production/logs/backup.log 2>&1

# Monitoring every 5 minutes
*/5 * * * * /opt/atom/production/scripts/monitor.sh >> /opt/atom/production/logs/monitoring.log 2>&1

# Log rotation every day at 3 AM
0 3 * * * /usr/sbin/logrotate /opt/atom/production/config/logrotate.conf

# Database maintenance every Sunday at 4 AM
0 4 * * 0 psql -h localhost -U atom_user -d atom_production -c "VACUUM ANALYZE;" >> /opt/atom/production/logs/maintenance.log 2>&1

# Clean up temp files every hour
0 * * * * find /opt/atom/production/temp -type f -mtime +1 -delete
"""
        
        crontab_file = self.config_path / "crontab.txt"
        with open(crontab_file, 'w') as f:
            f.write(crontab_content.strip())
        print(f"   ✅ Created: {crontab_file}")
        
        # Log rotation configuration
        logrotate_config = """
/opt/atom/production/logs/*.log {
    daily
    missingok
    rotate 30
    compress
    delaycompress
    notifempty
    create 644 atom atom
    postrotate
        systemctl reload atom-workflow-api || true
        systemctl reload atom-websocket-server || true
    endscript
}

/var/log/postgresql/*.log {
    weekly
    missingok
    rotate 8
    compress
    delaycompress
    notifempty
    create 644 postgres postgres
    postrotate
        systemctl reload postgresql || true
    endscript
}

/var/log/redis/redis-server.log {
    weekly
    missingok
    rotate 8
    compress
    delaycompress
    notifempty
    create 644 redis redis
    postrotate
        systemctl reload redis || true
    endscript
}
"""
        
        logrotate_file = self.config_path / "logrotate.conf"
        with open(logrotate_file, 'w') as f:
            f.write(logrotate_config.strip())
        print(f"   ✅ Created: {logrotate_file}")


def main():
    """Main deployment setup"""
    print("🚀 PRODUCTION DEPLOYMENT SETUP")
    print("=" * 80)
    print("Setting up production environment for Atom Workflow Automation")
    print("=" * 80)
    
    try:
        # Check running user
        if os.geteuid() != 0:
            print("❌ This script must be run as root (use sudo)")
            return {"success": False, "error": "Root privileges required"}
        
        # Create deployment manager
        deployment_manager = ProductionDeploymentManager()
        
        # Setup production environment
        result = deployment_manager.setup_production_environment()
        
        if result.get("success"):
            print("\n" + "=" * 80)
            print("🎉 PRODUCTION SETUP COMPLETED SUCCESSFULLY!")
            print("=" * 80)
            print("\n📋 Next Steps:")
            print("1. Configure environment variables in /opt/atom/production/config/.env")
            print("2. Run database migration: /opt/atom/production/config/migrate_database.sh")
            print("3. Install systemd services: cp /opt/atom/production/scripts/*.service /etc/systemd/system/")
            print("4. Reload systemd: systemctl daemon-reload")
            print("5. Deploy application: /opt/atom/production/scripts/deploy.sh")
            print("6. Setup monitoring: cp /opt/atom/production/config/*.yml /etc/prometheus/")
            print("7. Setup cron jobs: crontab -e -u atom (paste content from /opt/atom/production/config/crontab.txt)")
            
            print("\n🔍 Verification Commands:")
            print("   curl http://localhost:8080/health")
            print("   curl http://localhost:8000/health")
            print("   curl http://localhost:8765/health")
            
            print("\n📊 Monitoring URLs:")
            print("   Prometheus: http://localhost:9090")
            print("   Grafana: http://localhost:3000")
            
            print("\n🔧 Management Commands:")
            print("   Deploy: /opt/atom/production/scripts/deploy.sh")
            print("   Monitor: /opt/atom/production/scripts/monitor.sh")
            print("   Backup: /opt/atom/production/scripts/backup.sh")
        else:
            print(f"\n❌ Production setup failed: {result.get('error')}")
        
        return result
        
    except Exception as e:
        print(f"\n❌ Setup failed with exception: {str(e)}")
        logger.error(f"Production setup failed: {str(e)}")
        return {"success": False, "error": str(e)}


if __name__ == "__main__":
    result = main()
    sys.exit(0 if result.get("success") else 1)