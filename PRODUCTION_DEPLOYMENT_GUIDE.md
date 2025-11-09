# ATOM Platform - Production Deployment Guide

## 🚀 Quick Start

### 1. System Requirements
- Docker & Docker Compose
- 4GB RAM minimum
- 10GB disk space

### 2. Deployment Steps
```bash
# Clone and setup
git clone <repository>
cd atom

# Start production stack
docker-compose -f docker-compose.production.yml up -d

# Verify deployment
./monitor_servers.sh
```

### 3. Access Points
- **Frontend**: http://localhost:3000
- **API Documentation**: http://localhost:8001/docs
- **Monitoring**: http://localhost:3001 (admin/admin)

## 📊 Integration Status

The platform supports 29 out of 30 integrations:

### Task Management
- ✅ Asana, Linear, Monday, Trello, Jira

### Communication
- ✅ Slack, Discord, Teams, Gmail, Outlook

### Development
- ✅ GitHub, GitLab, Bitbucket, Figma

### Business Tools
- ✅ Salesforce, HubSpot, Zendesk, Intercom, Freshdesk

## 🔧 Troubleshooting

### Common Issues
1. **Port conflicts**: Check if ports 3000, 8001, 5058 are available
2. **Database connection**: Verify PostgreSQL is running
3. **OAuth setup**: Configure environment variables for each service

### Monitoring
- Use `./monitor_servers.sh` for real-time status
- Check logs: `docker-compose logs -f`
- Metrics: http://localhost:3001

## 📞 Support
- Documentation: http://localhost:3000/docs
- API Reference: http://localhost:8001/docs
- System Status: http://localhost:8001/api/system/status
