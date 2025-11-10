# Salesforce Integration Deployment Guide

## Overview

This guide provides comprehensive deployment instructions for the Salesforce integration in the ATOM Agent Memory System. The deployment process covers environment setup, configuration, database initialization, and production deployment.

## Prerequisites

### System Requirements
- **Operating System**: Linux (Ubuntu 20.04+), macOS, or Windows
- **Python**: 3.8 or higher
- **PostgreSQL**: 12+ (production) or SQLite (development)
- **Memory**: 2GB RAM minimum, 4GB recommended
- **Storage**: 1GB free disk space
- **Network**: Internet access for Salesforce API calls

### Required Software
- **Python Packages**: Flask, simple-salesforce, asyncpg, cryptography
- **Database**: PostgreSQL 12+ or SQLite3
- **Web Server**: Nginx (production) or built-in Flask server (development)
- **Process Manager**: systemd (Linux) or PM2 (Node.js)

## Deployment Architecture

### Component Overview
```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│   Desktop App   │────│   ATOM Backend   │────│   Salesforce    │
│  (TypeScript)   │    │   (Python/Flask) │    │     API         │
└─────────────────┘    └──────────────────┘    └─────────────────┘
                              │
                      ┌──────────────────┐
                      │   PostgreSQL     │
                      │   Database       │
                      └──────────────────┘
```

### Network Requirements
- **Outbound**: HTTPS to Salesforce APIs (login.salesforce.com, your-instance.salesforce.com)
- **Inbound**: HTTP/HTTPS for OAuth callbacks and API requests
- **Ports**: 5000 (development), 443 (production)

## Step-by-Step Deployment

### Step 1: Environment Preparation

#### 1.1 Server Setup
```bash
# Update system packages
sudo apt update && sudo apt upgrade -y

# Install required system packages
sudo apt install -y python3 python3-pip python3-venv postgresql postgresql-contrib nginx

# Create application user
sudo useradd -m -s /bin/bash atom
sudo passwd atom
```

#### 1.2 Python Environment
```bash
# Switch to application user
sudo su - atom

# Create virtual environment
python3 -m venv /home/atom/venv
source /home/atom/venv/bin/activate

# Install Python packages
pip install --upgrade pip
pip install flask==2.3.0
pip install simple-salesforce==1.12.0
pip install asyncpg==0.28.0
pip install cryptography==41.0.0
pip install gunicorn==21.2.0
```

### Step 2: Database Configuration

#### 2.1 PostgreSQL Setup (Production)
```bash
# Switch to postgres user
sudo -u postgres psql

# Create database and user
CREATE DATABASE atom_production;
CREATE USER atom_user WITH PASSWORD 'secure_password';
GRANT ALL PRIVILEGES ON DATABASE atom_production TO atom_user;

# Create Salesforce OAuth table
\c atom_production

CREATE TABLE salesforce_oauth_tokens (
    id SERIAL PRIMARY KEY,
    user_id VARCHAR(255) NOT NULL UNIQUE,
    access_token TEXT NOT NULL,
    refresh_token TEXT,
    expires_at TIMESTAMP WITH TIME ZONE,
    scope TEXT,
    organization_id VARCHAR(255),
    profile_id VARCHAR(255),
    instance_url TEXT,
    username VARCHAR(255),
    environment VARCHAR(50),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_salesforce_user_id ON salesforce_oauth_tokens(user_id);
CREATE INDEX idx_salesforce_expires_at ON salesforce_oauth_tokens(expires_at);

\q
```

#### 2.2 SQLite Setup (Development)
```bash
# The application will automatically create SQLite database
# No additional setup required for development
```

### Step 3: Salesforce Connected App Configuration

#### 3.1 Create Connected App in Salesforce
1. **Log in to Salesforce**: Navigate to Setup → Platform Tools → Apps → App Manager
2. **Create New Connected App**:
   - **Basic Information**:
     - Connected App Name: `ATOM Agent Memory System`
     - API Name: `ATOM_Agent_Memory_System`
     - Contact Email: Your email address
   - **API (Enable OAuth Settings)**:
     - ✅ Enable OAuth Settings
     - Callback URL: `https://your-domain.com/api/auth/salesforce/callback`
     - Selected OAuth Scopes:
       - Access and manage your data (api)
       - Perform requests on your behalf at any time (refresh_token, offline_access)
       - Provide access to your data via the Web (web)
3. **Save and Retrieve Credentials**:
   - Consumer Key → `SALESFORCE_CLIENT_ID`
   - Consumer Secret → `SALESFORCE_CLIENT_SECRET`

#### 3.2 Configure IP Restrictions (Optional)
- In Connected App settings, configure allowed IP ranges for enhanced security
- Add your server's public IP address

### Step 4: Application Configuration

#### 4.1 Environment Variables
Create `/home/atom/.env` file:
```bash
# Salesforce Configuration
SALESFORCE_CLIENT_ID="your_consumer_key_from_connected_app"
SALESFORCE_CLIENT_SECRET="your_consumer_secret_from_connected_app"
SALESFORCE_REDIRECT_URI="https://your-domain.com/api/auth/salesforce/callback"
SALESFORCE_API_VERSION="57.0"

# Database Configuration (Production)
DATABASE_URL="postgresql://atom_user:secure_password@localhost/atom_production"

# Database Configuration (Development)
# DATABASE_URL="sqlite:///atom.db"

# Application Configuration
FLASK_ENV="production"
SECRET_KEY="your_secure_secret_key_here"
ENCRYPTION_KEY="your_encryption_key_for_token_storage"

# Logging Configuration
LOG_LEVEL="INFO"
LOG_FILE="/home/atom/logs/atom.log"
```

#### 4.2 Generate Secure Keys
```bash
# Generate secret key
python3 -c "import secrets; print(secrets.token_hex(32))"

# Generate encryption key
python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

### Step 5: Application Deployment

#### 5.1 Directory Structure
```bash
# Create application directory structure
mkdir -p /home/atom/{app,logs,backups}

# Copy application files to /home/atom/app/
# Ensure all Salesforce integration files are present:
# - salesforce_service.py
# - auth_handler_salesforce.py
# - db_oauth_salesforce.py
# - salesforce_handler.py
# - salesforce_health_handler.py
# - salesforce_enhanced_api.py
# - main_api_app.py
```

#### 5.2 Application Startup Script
Create `/home/atom/start_app.sh`:
```bash
#!/bin/bash

# Activate virtual environment
source /home/atom/venv/bin/activate

# Set environment variables
export $(cat /home/atom/.env | xargs)

# Start application with Gunicorn
cd /home/atom/app
exec gunicorn --bind 0.0.0.0:5000 --workers 4 --timeout 120 main_api_app:app
```

Make executable:
```bash
chmod +x /home/atom/start_app.sh
```

#### 5.3 Systemd Service (Production)
Create `/etc/systemd/system/atom.service`:
```ini
[Unit]
Description=ATOM Agent Memory System
After=network.target postgresql.service

[Service]
Type=simple
User=atom
Group=atom
WorkingDirectory=/home/atom/app
Environment=PATH=/home/atom/venv/bin
ExecStart=/home/atom/start_app.sh
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

Enable and start service:
```bash
sudo systemctl daemon-reload
sudo systemctl enable atom.service
sudo systemctl start atom.service
sudo systemctl status atom.service
```

### Step 6: Web Server Configuration (Production)

#### 6.1 Nginx Configuration
Create `/etc/nginx/sites-available/atom`:
```nginx
server {
    listen 80;
    server_name your-domain.com;
    return 301 https://$server_name$request_uri;
}

server {
    listen 443 ssl http2;
    server_name your-domain.com;

    ssl_certificate /etc/letsencrypt/live/your-domain.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/your-domain.com/privkey.pem;

    # Security headers
    add_header X-Frame-Options DENY;
    add_header X-Content-Type-Options nosniff;
    add_header X-XSS-Protection "1; mode=block";

    # Proxy to Flask application
    location / {
        proxy_pass http://127.0.0.1:5000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    # Static files (if any)
    location /static/ {
        alias /home/atom/app/static/;
        expires 1y;
        add_header Cache-Control "public, immutable";
    }
}
```

Enable site and restart Nginx:
```bash
sudo ln -s /etc/nginx/sites-available/atom /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl restart nginx
```

#### 6.2 SSL Certificate (Let's Encrypt)
```bash
sudo apt install certbot python3-certbot-nginx
sudo certbot --nginx -d your-domain.com
```

### Step 7: Health Monitoring

#### 7.1 Health Check Endpoints
Verify Salesforce integration health:
```bash
# Test overall health
curl https://your-domain.com/api/salesforce/health

# Test token health (for specific user)
curl "https://your-domain.com/api/salesforce/health/tokens?user_id=test_user"

# Test connection health
curl "https://your-domain.com/api/salesforce/health/connection?user_id=test_user"
```

#### 7.2 Monitoring Script
Create `/home/atom/monitor_salesforce.sh`:
```bash
#!/bin/bash

BASE_URL="https://your-domain.com"
ALERT_EMAIL="admin@your-domain.com"

# Check Salesforce health
response=$(curl -s -w "%{http_code}" "$BASE_URL/api/salesforce/health")
http_code=${response: -3}
health_data=${response%???}

if [ "$http_code" != "200" ]; then
    echo "Salesforce health check failed: HTTP $http_code" | mail -s "Salesforce Integration Alert" $ALERT_EMAIL
    exit 1
fi

# Parse health status
status=$(echo $health_data | jq -r '.status')
if [ "$status" != "healthy" ]; then
    echo "Salesforce integration unhealthy: $status" | mail -s "Salesforce Integration Alert" $ALERT_EMAIL
    exit 1
fi

echo "Salesforce integration healthy"
```

### Step 8: Backup Configuration

#### 8.1 Database Backups
Create `/home/atom/backup_database.sh`:
```bash
#!/bin/bash

BACKUP_DIR="/home/atom/backups"
DATE=$(date +%Y%m%d_%H%M%S)

# Backup PostgreSQL database
pg_dump -U atom_user atom_production > $BACKUP_DIR/atom_backup_$DATE.sql

# Compress backup
gzip $BACKUP_DIR/atom_backup_$DATE.sql

# Keep only last 7 backups
ls -t $BACKUP_DIR/atom_backup_*.sql.gz | tail -n +8 | xargs rm -f

echo "Backup completed: atom_backup_$DATE.sql.gz"
```

#### 8.2 Cron Job for Backups
```bash
# Add to crontab -e
0 2 * * * /home/atom/backup_database.sh
```

### Step 9: Security Hardening

#### 9.1 Firewall Configuration
```bash
# Enable UFW
sudo ufw enable

# Allow SSH, HTTP, HTTPS
sudo ufw allow ssh
sudo ufw allow http
sudo ufw allow https

# Deny all other incoming traffic
sudo ufw default deny incoming
```

#### 9.2 Application Security
- Ensure all environment variables are properly set
- Verify file permissions:
  ```bash
  sudo chown -R atom:atom /home/atom/
  sudo chmod 600 /home/atom/.env
  sudo chmod 700 /home/atom/backups/
  ```

#### 9.3 Regular Security Updates
```bash
# Set up automatic security updates
sudo apt install unattended-upgrades
sudo dpkg-reconfigure -plow unattended-upgrades
```

## Deployment Verification

### 10.1 Post-Deployment Checklist

- [ ] Application starts without errors
- [ ] Database connections established
- [ ] Salesforce OAuth table created
- [ ] Health endpoints responding
- [ ] SSL certificate valid
- [ ] Nginx configuration correct
- [ ] Firewall rules applied
- [ ] Backup system working
- [ ] Monitoring alerts configured

### 10.2 Integration Testing
```bash
# Test complete Salesforce integration
curl "https://your-domain.com/api/salesforce/health"
curl "https://your-domain.com/api/services"
curl "https://your-domain.com/api/auth/salesforce/authorize?user_id=test_user"
```

### 10.3 Performance Testing
```bash
# Test response times
time curl -s "https://your-domain.com/api/salesforce/health" > /dev/null

# Test concurrent requests
for i in {1..10}; do
    curl -s "https://your-domain.com/api/salesforce/health" &
done
wait
```

## Troubleshooting

### Common Issues and Solutions

#### Issue: OAuth Authentication Fails
**Symptoms**: 401 errors, "Invalid client credentials"
**Solutions**:
- Verify SALESFORCE_CLIENT_ID and SALESFORCE_CLIENT_SECRET
- Check Salesforce Connected App configuration
- Ensure redirect URI matches exactly

#### Issue: Database Connection Errors
**Symptoms**: "Database connection not available"
**Solutions**:
- Verify DATABASE_URL format
- Check PostgreSQL service status
- Confirm user permissions

#### Issue: SSL Certificate Problems
**Symptoms**: Browser warnings, connection refused
**Solutions**:
- Renew Let's Encrypt certificate: `sudo certbot renew`
- Check Nginx configuration: `sudo nginx -t`

#### Issue: Performance Problems
**Symptoms**: Slow response times, timeouts
**Solutions**:
- Increase Gunicorn workers
- Add database connection pooling
- Implement response caching

## Maintenance

### Regular Maintenance Tasks

#### Daily
- Check application logs for errors
- Monitor health endpoints
- Verify backup completion

#### Weekly
- Review security logs
- Update system packages
- Clean up old log files

#### Monthly
- Review and rotate encryption keys
- Test disaster recovery procedures
- Update Salesforce API version if needed

### Update Procedures

#### Application Updates
```bash
# Stop application
sudo systemctl stop atom.service

# Backup current version
cp -r /home/atom/app /home/atom/app_backup_$(date +%Y%m%d)

# Deploy new version
# (Copy new files to /home/atom/app/)

# Restart application
sudo systemctl start atom.service

# Verify deployment
sudo systemctl status atom.service
curl https://your-domain.com/api/salesforce/health
```

## Support and Monitoring

### Log Files
- Application logs: `/home/atom/logs/atom.log`
- System logs: `/var/log/syslog`
- Nginx logs: `/var/log/nginx/access.log`, `/var/log/nginx/error.log`

### Monitoring Tools
- **Application**: Custom health endpoints
- **System**: htop, iotop, nethogs
- **Network**: netstat, tcpdump
- **Database**: pg_stat_activity, pg_locks

### Contact Information
- **Technical Support**: support@your-domain.com
- **Emergency Contact**: +1-555-123-4567
- **Salesforce Support**: https://help.salesforce.com

## Conclusion

The Salesforce integration deployment is now complete and ready for production use. The system provides enterprise-grade CRM capabilities with secure OAuth 2.0 authentication, comprehensive monitoring, and robust backup procedures.

**Next Steps**:
1. Perform final integration testing with real Salesforce data
2. Train users on Salesforce integration features
3. Monitor system performance for first 48 hours
4. Schedule regular security reviews

**Deployment Date**: $(date)
**Salesforce API Version**: 57.0
**Status**: ✅ PRODUCTION READY