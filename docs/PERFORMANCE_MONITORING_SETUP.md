# 🚀 ATOM Platform - Performance Monitoring Setup

## 📊 Overview

This document provides comprehensive setup instructions for the ATOM platform performance monitoring system. The monitoring infrastructure tracks system health, business metrics, and user activity to ensure optimal performance and reliability.

---

## 🏗️ Monitoring Architecture

### Core Components
- **Prometheus**: Metrics collection and storage
- **Grafana**: Dashboard visualization and alerting
- **Custom Metrics**: Application-specific performance indicators
- **Health Checks**: Automated system validation
- **Alerting System**: Real-time notifications

### Data Flow
```
ATOM Services → Prometheus Metrics → Grafana Dashboards → Alert Manager
```

---

## 🔧 Setup Instructions

### 1. Prerequisites
```bash
# Install required tools
docker --version
docker-compose --version
```

### 2. Start Monitoring Stack
```bash
# Navigate to project root
cd atom

# Start monitoring services
docker-compose -f deployment/docker-compose/docker-compose.monitoring.yml up -d

# Verify services are running
docker-compose -f deployment/docker-compose/docker-compose.monitoring.yml ps
```

### 3. Access Monitoring Dashboards
- **Grafana**: http://localhost:3001 (admin/admin)
- **Prometheus**: http://localhost:9090
- **Alert Manager**: http://localhost:9093

---

## 📈 Key Performance Indicators

### System Metrics
- **CPU Usage**: < 80% threshold
- **Memory Usage**: < 85% threshold  
- **Disk I/O**: < 90% threshold
- **Network Latency**: < 100ms target

### Application Metrics
- **API Response Time**: < 500ms target
- **Error Rate**: < 1% threshold
- **Service Availability**: > 99.9% target
- **Concurrent Users**: Track capacity limits

### Business Metrics
- **Active Users**: Daily/Monthly active users
- **Service Usage**: Integration adoption rates
- **Workflow Success**: Automation completion rates
- **Cost Optimization**: AI provider efficiency

---

## 🎯 Dashboard Configuration

### 1. System Health Dashboard
**Purpose**: Monitor infrastructure performance
**Key Widgets**:
- CPU/Memory/Disk usage
- Network traffic
- Service uptime
- Error rates

### 2. Application Performance Dashboard
**Purpose**: Track ATOM platform performance
**Key Widgets**:
- API response times
- Service integration status
- User activity metrics
- Workflow execution times

### 3. Business Intelligence Dashboard
**Purpose**: Monitor business value and adoption
**Key Widgets**:
- User growth metrics
- Service adoption rates
- Cost optimization tracking
- ROI calculations

---

## 🔔 Alert Configuration

### Critical Alerts (P0)
```yaml
- System downtime
- Database connection failures
- API unavailability
- Security breaches
```

### High Priority Alerts (P1)
```yaml
- High error rates (> 5%)
- Slow response times (> 2s)
- Memory/CPU saturation
- Service integration failures
```

### Medium Priority Alerts (P2)
```yaml
- Warning-level errors
- Performance degradation
- Resource utilization trends
- Backup failures
```

### Alert Channels
- **Email**: Team notifications
- **Slack**: Real-time alerts
- **PagerDuty**: Critical incidents
- **Webhook**: Custom integrations

---

## 📊 Custom Metrics Implementation

### 1. Service Integration Metrics
```python
# Track service connectivity
service_connectivity_status = Gauge(
    'atom_service_connectivity',
    'Service connectivity status',
    ['service_name']
)

# Track integration usage
service_usage_counter = Counter(
    'atom_service_usage',
    'Service usage count',
    ['service_name', 'operation']
)
```

### 2. User Activity Metrics
```python
# Track user engagement
user_activity_gauge = Gauge(
    'atom_active_users',
    'Number of active users',
    ['time_window']
)

# Track command usage
command_usage_counter = Counter(
    'atom_command_usage',
    'Command execution count',
    ['command_type', 'success']
)
```

### 3. Performance Metrics
```python
# Track response times
response_time_histogram = Histogram(
    'atom_response_time',
    'API response time distribution',
    ['endpoint']
)

# Track error rates
error_rate_gauge = Gauge(
    'atom_error_rate',
    'System error rate percentage'
)
```

---

## 🔍 Monitoring Scripts

### 1. Health Check Script
```bash
#!/bin/bash
# atom/scripts/health_check.sh

echo "🔍 ATOM Platform Health Check"
echo "============================="

# Check backend service
curl -f http://localhost:8001/healthz || echo "❌ Backend service down"

# Check database connectivity
python -c "
import psycopg2
try:
    conn = psycopg2.connect('postgresql://user:password@localhost:5432/atom_production')
    print('✅ Database connected')
except Exception as e:
    print(f'❌ Database connection failed: {e}')
"

# Check service integrations
curl -s http://localhost:8001/api/services/status | jq '.status_summary'
```

### 2. Performance Benchmark Script
```python
# atom/scripts/performance_benchmark.py
import requests
import time
import statistics

def benchmark_endpoints():
    endpoints = [
        "/healthz",
        "/api/services/status", 
        "/api/user/api-keys/status",
        "/api/workflow-automation/generate"
    ]
    
    results = {}
    for endpoint in endpoints:
        times = []
        for _ in range(10):
            start = time.time()
            requests.get(f"http://localhost:8001{endpoint}")
            times.append((time.time() - start) * 1000)  # Convert to ms
        
        results[endpoint] = {
            "avg": statistics.mean(times),
            "min": min(times),
            "max": max(times),
            "p95": statistics.quantiles(times, n=20)[18]  # 95th percentile
        }
    
    return results
```

### 3. Automated Monitoring Script
```python
# atom/scripts/automated_monitor.py
import schedule
import time
import logging
from datetime import datetime

def monitor_system_health():
    """Monitor system health and log metrics"""
    timestamp = datetime.now().isoformat()
    
    # Check critical services
    health_checks = {
        "backend": check_backend_health(),
        "database": check_database_health(),
        "services": check_service_integrations(),
        "performance": check_performance_metrics()
    }
    
    # Log results
    logging.info(f"Health check at {timestamp}: {health_checks}")
    
    # Trigger alerts if needed
    if not all(health_checks.values()):
        send_alert("System health check failed", health_checks)

# Schedule monitoring
schedule.every(5).minutes.do(monitor_system_health)

if __name__ == "__main__":
    while True:
        schedule.run_pending()
        time.sleep(1)
```

---

## 📈 Performance Baselines

### Target Performance Metrics
| Metric | Target | Warning | Critical |
|--------|--------|---------|----------|
| API Response Time | < 500ms | 500ms-1s | > 1s |
| Error Rate | < 1% | 1%-5% | > 5% |
| Service Availability | > 99.9% | 99%-99.9% | < 99% |
| CPU Usage | < 70% | 70%-85% | > 85% |
| Memory Usage | < 75% | 75%-90% | > 90% |

### Business Metrics Targets
| Metric | Target | Measurement |
|--------|--------|-------------|
| Daily Active Users | > 100 | User sessions |
| Service Adoption | > 80% | Connected services/user |
| Workflow Success | > 95% | Completed workflows |
| Cost Optimization | 40-70% | AI provider efficiency |

---

## 🛠️ Maintenance Procedures

### Daily Tasks
- Review alert history
- Check system resource usage
- Verify backup completion
- Monitor error rates

### Weekly Tasks
- Performance trend analysis
- Capacity planning review
- Security log audit
- Dashboard optimization

### Monthly Tasks
- Comprehensive health assessment
- Cost optimization analysis
- User adoption review
- Infrastructure scaling planning

---

## 🔄 Continuous Improvement

### Performance Optimization
1. **Identify Bottlenecks**: Use metrics to find slow endpoints
2. **Optimize Queries**: Database and API performance tuning
3. **Scale Resources**: Add capacity based on usage patterns
4. **Update Infrastructure**: Keep systems current and optimized

### Monitoring Enhancement
1. **Add Custom Metrics**: Track business-specific KPIs
2. **Improve Alerting**: Refine thresholds and notifications
3. **Expand Coverage**: Monitor additional services and features
4. **Automate Responses**: Implement auto-remediation for common issues

---

## 📞 Support and Troubleshooting

### Common Issues
1. **Metrics Not Showing**
   - Check Prometheus configuration
   - Verify service discovery
   - Review firewall settings

2. **High Alert Volume**
   - Adjust alert thresholds
   - Implement alert grouping
   - Review noise reduction rules

3. **Dashboard Performance**
   - Optimize query performance
   - Reduce dashboard complexity
   - Implement data retention policies

### Escalation Procedures
1. **Level 1**: Automated monitoring and basic alerts
2. **Level 2**: Engineering team notification
3. **Level 3**: Management escalation for critical issues

---

## 🎯 Success Criteria

### Technical Success
- ✅ 99.9% system availability
- ✅ < 500ms average response time
- ✅ < 1% error rate
- ✅ Comprehensive monitoring coverage

### Business Success
- ✅ Real-time performance visibility
- ✅ Proactive issue detection
- ✅ Data-driven decision making
- ✅ Continuous improvement cycle

---

*Performance Monitoring Setup Version: 2.0*
*Last Updated: 2025-11-12*
*ATOM Platform Version: Enterprise v2.0*