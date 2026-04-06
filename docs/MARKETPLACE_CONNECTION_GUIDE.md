# Marketplace Connection Guide

**Last Updated:** 2026-04-06

This guide explains how to connect your self-hosted Atom instance to the Atom SaaS marketplace to access thousands of community-published agents and skills.

## Overview

The Atom marketplace is hosted at `https://atomagentos.com` and provides:

- **5,000+ Community Skills**: Pre-built skills for common automation tasks
- **Agent Templates**: Complete, autonomous agents with pre-learned capabilities
- **Real-Time Updates**: Automatic synchronization with the marketplace
- **Bidirectional Sync**: Share your ratings and feedback with the community

## Quick Start

### 1. Get Your API Token

1. Visit [https://atomagentos.com](https://atomagentos.com)
2. Create an account or log in
3. Navigate to Settings → API Tokens
4. Generate a new marketplace token
5. Copy the token (format: `at_saas_xxxxx`)

### 2. Configure Your Environment

Add the following to your `.env` file:

```bash
# ==============================================================================
# MARKETPLACE CONNECTION
# ==============================================================================

# Marketplace API URL (Public Atom SaaS)
MARKETPLACE_API_URL=https://atomagentos.com

# Your Marketplace API Token
MARKETPLACE_API_TOKEN=at_saas_your_token_here

# Enable marketplace sync (recommended: true)
MARKETPLACE_SYNC_ENABLED=true

# Sync interval in minutes (default: 15, range: 5-60)
MARKETPLACE_SYNC_INTERVAL_MINUTES=15

# Rating sync interval in minutes (default: 30)
MARKETPLACE_RATING_SYNC_INTERVAL_MINUTES=30

# Federation key for cross-instance agent sharing (optional)
FEDERATION_API_KEY=sk-federation-shared-key
```

### 3. Restart Your Atom Instance

```bash
# Docker deployment
docker-compose restart

# Native deployment
cd backend
python -m uvicorn main_api_app:app --reload
```

### 4. Verify Connection

```bash
# Check sync status
curl http://localhost:8000/api/admin/sync/status

# Expected response:
{
  "success": true,
  "sync": {
    "status": "idle",
    "last_sync_at": "2026-04-06T14:15:00Z",
    "last_successful_sync_at": "2026-04-06T14:15:00Z"
  },
  "cache": {
    "skills_count": 1250,
    "categories_count": 24
  }
}
```

## Features

### Browse Marketplace Skills

```bash
# List available skills
curl http://localhost:8000/api/marketplace/skills?limit=20

# Search for specific skills
curl http://localhost:8000/api/marketplace/skills?query=sales&category=crm
```

### Browse Agent Templates

```bash
# List published agents
curl http://localhost:8000/api/federation/agents?limit=50 \
  -H "X-Federation-Key: sk-federation-shared-key"

# Get agent template details
curl http://localhost:8000/api/federation/agents/{template_id} \
  -H "X-Federation-Key: sk-federation-shared-key"
```

### Install Skills

```bash
# Install a skill from marketplace
curl -X POST http://localhost:8000/api/marketplace/skills/{skill_id}/install \
  -H "X-API-Key: your_local_api_key"
```

### Rate and Review

```bash
# Rate a skill
curl -X POST http://localhost:8000/api/marketplace/skills/{skill_id}/rate \
  -H "Content-Type: application/json" \
  -d '{"rating": 5, "review": "Excellent skill for automation!"}'
```

## Configuration Options

### Sync Behavior

```bash
# Conflict resolution strategy
# Options: remote_wins, local_wins, merge, manual
MARKETPLACE_CONFLICT_STRATEGY=remote_wins
```

- **remote_wins**: Marketplace data overwrites local (recommended)
- **local_wins**: Local data takes precedence
- **merge**: Intelligent field-level merge
- **manual**: Log conflicts for manual resolution

### Sync Intervals

```bash
# How often to poll for skill updates
MARKETPLACE_SYNC_INTERVAL_MINUTES=15

# How often to upload your ratings
MARKETPLACE_RATING_SYNC_INTERVAL_MINUTES=30
```

**Recommended intervals:**
- Development: 15 minutes (skills), 30 minutes (ratings)
- Production: 10 minutes (skills), 20 minutes (ratings)
- High Traffic: 5 minutes (skills), 15 minutes (ratings)

### WebSocket Real-Time Updates

```bash
# Enable real-time marketplace updates
MARKETPLACE_WS_URL=wss://atomagentos.com/ws
MARKETPLACE_WS_RECONNECT_ATTEMPTS=10
MARKETPLACE_WS_HEARTBEAT_INTERVAL=30
```

Real-time updates provide:
- Instant notifications for new skills
- Real-time rating updates
- Automatic cache invalidation

## Troubleshooting

### Connection Issues

**Problem:** Cannot connect to marketplace

```bash
# Test connectivity
curl -I https://atomagentos.com/health

# Expected: HTTP 200
```

**Solution:**
1. Check internet connectivity
2. Verify firewall allows outbound HTTPS
3. Confirm DNS resolution: `nslookup atomagentos.com`
4. Check API token validity

### Sync Not Running

**Problem:** Skills not syncing

```bash
# Check scheduler enabled
curl http://localhost:8000/api/admin/sync/jobs

# Expected: 2 jobs (skill-sync, rating-sync)
```

**Solution:**
1. Set `MARKETPLACE_SYNC_ENABLED=true`
2. Verify `MARKETPLACE_API_TOKEN` is set
3. Check application logs for errors
4. Trigger manual sync: `curl -X POST http://localhost:8000/api/admin/sync/skills`

### Authentication Errors

**Problem:** 401 Unauthorized

```bash
# Verify API token
curl -H "Authorization: Bearer $MARKETPLACE_API_TOKEN" \
  https://atomagentos.com/api/marketplace/skills?limit=1

# Expected: HTTP 200 with skills array
```

**Solution:**
1. Regenerate API token in marketplace dashboard
2. Verify token format: `at_saas_xxxxx`
3. Check for extra spaces in `.env` file
4. Ensure token has marketplace access permissions

### Cache Issues

**Problem:** Stale skill data

```bash
# Clear cache and force sync
curl -X POST http://localhost:8000/api/admin/sync/cache/clear
curl -X POST http://localhost:8000/api/admin/sync/skills
```

**Solution:**
1. Manual sync triggers immediate update
2. Check cache expiration (24-hour TTL)
3. Verify database write permissions

## Security Best Practices

### API Token Security

- ✅ Store tokens in environment variables (not in code)
- ✅ Use separate tokens for dev/staging/production
- ✅ Rotate tokens every 90 days
- ❌ Never commit tokens to git
- ❌ Never share tokens in plaintext

### Network Security

- ✅ Use HTTPS for all marketplace connections
- ✅ Validate SSL certificates (disable only for testing)
- ✅ Restrict outbound access to marketplace IPs
- ✅ Monitor marketplace API usage

### Data Privacy

- ✅ Only sync public skill metadata
- ✅ Anonymize agent memory before publishing
- ✅ Review published agents before approval
- ✅ Implement rate limiting for API calls

## Advanced Usage

### Custom Marketplace Endpoint

For self-hosted marketplace or alternative endpoints:

```bash
MARKETPLACE_API_URL=https://your-marketplace.example.com
MARKETPLACE_WS_URL=wss://your-marketplace.example.com/ws
```

### Federation with Private Instances

For sharing agents across private instances:

```bash
# On Instance A (Publisher)
FEDERATION_API_KEY=sk-federation-shared-secret-123

# On Instance B (Consumer)
FEDERATION_API_KEY=sk-federation-shared-secret-123

# Both instances can now share agents
```

### Manual Skill Installation

Without marketplace sync:

```bash
# Download skill bundle from marketplace
curl https://atomagentos.com/api/marketplace/skills/{skill_id}/bundle \
  -H "Authorization: Bearer $MARKETPLACE_API_TOKEN" \
  -o skill-bundle.zip

# Install manually
curl -X POST http://localhost:8000/api/skills/install \
  -F "bundle=@skill-bundle.zip"
```

## API Reference

### Marketplace Endpoints

```bash
# List skills
GET /api/marketplace/skills?limit=20&offset=0&category=automation

# Get skill details
GET /api/marketplace/skills/{skill_id}

# Install skill
POST /api/marketplace/skills/{skill_id}/install

# Rate skill
POST /api/marketplace/skills/{skill_id}/rate

# Get skill reviews
GET /api/marketplace/skills/{skill_id}/reviews
```

### Federation Endpoints

```bash
# List agents
GET /api/federation/agents?limit=50

# Get agent bundle
GET /api/federation/agents/{template_id}

# Requires federation key:
# X-Federation-Key: sk-federation-shared-key
```

### Sync Management

```bash
# Check sync status
GET /api/admin/sync/status

# Trigger skill sync
POST /api/admin/sync/skills

# Trigger rating sync
POST /api/admin/sync/ratings

# View sync jobs
GET /api/admin/sync/jobs

# Clear cache
DELETE /api/admin/sync/cache
```

## Support

### Documentation

- **Marketplace Architecture**: [MARKETPLACE_ARCHITECTURE.md](../MARKETPLACE_ARCHITECTURE.md)
- **Federation Protocol**: [FEDERATION_PROTOCOL.md](../FEDERATION_PROTOCOL.md)
- **Sync Deployment**: [ATOM_SAAS_SYNC_DEPLOYMENT.md](ATOM_SAAS_SYNC_DEPLOYMENT.md)

### Community

- **GitHub Issues**: [https://github.com/rush86999/atom/issues](https://github.com/rush86999/atom/issues)
- **Marketplace**: [https://atomagentos.com](https://atomagentos.com)
- **Documentation**: [https://docs.atomagentos.com](https://docs.atomagentos.com)

### Getting Help

1. Check troubleshooting section above
2. Search existing GitHub issues
3. Review marketplace documentation
4. Open new issue with logs and error messages

---

**Version:** 1.0
**Platform:** Atom Open Source
**Last Updated:** 2026-04-06
