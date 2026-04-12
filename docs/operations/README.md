# Operations Documentation

Deployment, monitoring, performance tuning, and troubleshooting.

## 📚 Quick Navigation

### Quick Reference
- **[Operations Guide](OPERATIONS_GUIDE.md)** - Daily operations and procedures ⭐ START HERE
- **[Troubleshooting](TROUBLESHOOTING.md)** - Common issues and solutions

### Deployment
- **[deployment.md](deployment.md)** - Deployment procedures

### Monitoring & Health
- **[Monitoring](monitoring.md)** - Monitoring setup
- **[Performance Monitoring](perf-monitoring.md)** - Performance monitoring
- **[Health Monitoring](health-monitoring.md)** - Health check system

### Performance
- **[Performance](performance.md)** - Performance optimization

### Integration Health
- **[Integration Health](integration-health.md)** - Integration monitoring

### Error Handling
- **[Error Handling](error-handling.md)** - Error handling guidelines

## 🔧 Daily Operations

### Health Checks
```bash
# Check service health
curl http://localhost:8000/health/live    # Liveness
curl http://localhost:8000/health/ready   # Readiness (DB + disk)
curl http://localhost:8000/health/metrics # Prometheus metrics
```

### Monitoring
- **Metrics**: Prometheus scraping at `/health/metrics`
- **Logs**: Structured JSON logs with context binding
- **Alerts**: Configure alerting rules in Prometheus

### Performance Targets
| Metric | Target | Current |
|--------|--------|---------|
| Health liveness | <10ms | ~2ms |
| Health readiness | <100ms | ~15ms |
| Metrics scrape | <50ms | ~8ms |

## 🚨 Incident Response

### Common Issues
1. **High Memory Usage**: Check agent execution count, restart services
2. **Database Connection Pool Exhausted**: Increase pool size, check for leaks
3. **Slow API Response**: Check database query performance, enable caching
4. **Agent Stuck**: Kill agent process, check governance state

### Rollback Procedure
```bash
# View recent commits
git log --oneline -n 10

# Rollback to previous commit
git checkout <commit-hash>
docker-compose -f docker-compose-personal.yml up -d --build
```

## 📊 Monitoring Setup

### Prometheus Configuration
```yaml
scrape_configs:
  - job_name: 'atom'
    static_configs:
      - targets: ['localhost:8000']
    metrics_path: '/health/metrics'
```

### Grafana Dashboards
- Import dashboard from `backend/docs/MONITORING_SETUP.md`
- Configure Prometheus data source
- Set up alerting rules

## 📖 Related Documentation

- **[Deployment](../DEPLOYMENT/README.md)** - Deployment guides
- **[Security](../SECURITY/README.md)** - Security operations
- **[Testing](../testing/README.md)** - Monitoring tests

---

*Last Updated: April 12, 2026*
