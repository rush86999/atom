# Production Monitoring Setup Guide

## Health Monitoring Endpoints
- `GET /healthz` - Application health
- `GET /api/services/status` - Service status
- `GET /api/auth/oauth-status` - OAuth service status

## Basic Monitoring Setup

### 1. System Monitoring
```bash
# Install basic monitoring tools
sudo apt install htop iotop nethogs

# Monitor logs
tail -f backend.log
```

### 2. Application Metrics
Add to your Flask app:
```python
from prometheus_flask_exporter import PrometheusMetrics

metrics = PrometheusMetrics(app)
metrics.info('app_info', 'Application info', version='1.0.0')
```

### 3. Database Backup
```bash
#!/bin/bash
# backup_database.sh
BACKUP_DIR="/backups/atom"
DATE=$(date +%Y%m%d_%H%M%S)
DB_FILE="./data/atom_production.db"

mkdir -p $BACKUP_DIR
sqlite3 $DB_FILE ".backup $BACKUP_DIR/atom_backup_$DATE.db"
find $BACKUP_DIR -name "*.db" -mtime +7 -delete
```

## Alerting Setup
Monitor for:
- High response times (>500ms)
- OAuth service failures
- Database connection issues
- SSL certificate expiry

## Performance Metrics to Track
- Response time per endpoint
- OAuth flow success rates
- Service connection status
- Error rates and types

Generated: 2025-11-01 12:29:48
