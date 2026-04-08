# Atom Marketplace Documentation

> **Last Updated:** April 7, 2026
> **Purpose:** Complete guide to the Atom Marketplace for community skills, agents, and integrations

**[← Back to Documentation Index](../INDEX.md)**

---

## Overview

The Atom Marketplace is a centralized hub for discovering, evaluating, and installing community-published resources. It enables self-hosted Atom instances to connect to the broader Atom ecosystem and access thousands of pre-built automation components.

### What You Can Find in the Marketplace

- **5,000+ Community Skills**: Pre-built automation components for common tasks
- **Agent Templates**: Complete, autonomous agents with pre-learned capabilities
- **Integration Templates**: Ready-to-use integrations with popular services
- **Specialist Domains**: Pre-configured agent domains for specific business functions

### Key Features

- **Privacy-First**: Opt-in analytics with aggregated, anonymized data only
- **Bidirectional Sync**: Share your ratings and feedback with the community
- **Real-Time Updates**: Automatic synchronization with the marketplace
- **Governance-Gated**: Maturity-based access control for security
- **Federated Architecture**: Self-hosted instances maintain control while accessing community resources

---

## Documentation

### Getting Started

| Document | Description |
|----------|-------------|
| [**Connection Guide**](connection.md) | **START HERE:** Complete guide for connecting your Atom instance to the marketplace |
| [**Quick Start**](#quick-start) | 5-minute setup guide |

### Core Features

| Document | Description |
|----------|-------------|
| [**Skill Marketplace**](skills.md) | Browse, install, and publish community skills |
| [**Analytics & Sync**](analytics.md) | Privacy-first analytics and bidirectional synchronization |

### Reference

| Document | Description |
|----------|-------------|
| [**Update Summary**](update-summary.md) | Recent updates and changelog |

---

## Quick Start

### 1. Get Your API Token

1. Visit [https://atomagentos.com](https://atomagentos.com)
2. Create an account or log in
3. Navigate to **Settings → API Tokens**
4. Generate a new marketplace token
5. Copy the token (format: `at_saas_xxxxx`)

### 2. Configure Your Environment

Add the following to your `.env` file:

```bash
# Marketplace Connection
MARKETPLACE_API_URL=https://atomagentos.com
MARKETPLACE_API_TOKEN=at_saas_your_token_here
MARKETPLACE_SYNC_ENABLED=true
```

### 3. Restart Atom

```bash
atom restart
# or
docker-compose -f docker-compose-personal.yml restart
```

### 4. Verify Connection

```bash
curl http://localhost:8000/api/admin/sync/status
```

Expected response:
```json
{
  "success": true,
  "data": {
    "marketplace_connected": true,
    "last_sync": "2026-04-07T10:30:00Z"
  }
}
```

---

## Marketplace Features

### 🛒 Skill Marketplace

Browse and install thousands of community-built skills:

- **Search**: Full-text search by name, description, and category
- **Ratings**: Community-driven 1-5 star ratings with reviews
- **Categories**: Organized by domain (data, automation, integration, etc.)
- **One-Click Install**: Automatic dependency management and conflict resolution
- **Governance**: Maturity-based access control (STUDENT blocked, INTERN requires approval)

**[→ Skill Marketplace Guide](skills.md)**

### 📊 Analytics & Synchronization

Privacy-first analytics that help improve the ecosystem:

- **Opt-In**: Analytics reporting is disabled by default
- **Aggregated Data Only**: No individual user data or message contents
- **Transparent**: All data stored locally before transmission
- **Bidirectional Sync**: Share your ratings and feedback with the community

**[→ Analytics Guide](analytics.md)**

### 🔗 Connection Management

Robust connection management with automatic retry:

- **Health Checks**: Periodic connectivity verification
- **Auto-Reconnect**: Automatic reconnection on transient failures
- **Conflict Resolution**: Configurable strategies for sync conflicts
- **Federation**: Cross-instance agent sharing (optional)

**[→ Connection Guide](connection.md)**

---

## Configuration Reference

### Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `MARKETPLACE_API_URL` | Yes | - | Marketplace API URL (typically `https://atomagentos.com`) |
| `MARKETPLACE_API_TOKEN` | Yes | - | Your marketplace API token (format: `at_saas_xxxxx`) |
| `MARKETPLACE_SYNC_ENABLED` | No | `false` | Enable marketplace synchronization |
| `MARKETPLACE_SYNC_INTERVAL_MINUTES` | No | `15` | Sync interval in minutes (range: 5-60) |
| `MARKETPLACE_RATING_SYNC_INTERVAL_MINUTES` | No | `30` | Rating sync interval in minutes |
| `ANALYTICS_ENABLED` | No | `false` | Enable usage analytics reporting |
| `INSTANCE_NAME` | No | `unnamed` | Friendly name for this instance |

### Sync Conflict Strategies

| Strategy | Description |
|----------|-------------|
| `local_wins` | Local changes always take precedence |
| `remote_wins` | Remote changes always take precedence |
| `latest_wins` | Most recent change takes precedence |
| `manual` | Require manual resolution for all conflicts |

---

## Security & Privacy

### Data Privacy

- **No Individual Data**: We only collect aggregated metrics (execution counts, success rates)
- **No Message Contents**: Your task data and conversations never leave your instance
- **Opt-In Analytics**: Analytics are disabled by default
- **Transparent**: All collected data is visible in your local database

### Security Best Practices

- **Token Security**: Treat your `MARKETPLACE_API_TOKEN` like a password
- **HTTPS Only**: All marketplace communication uses encrypted HTTPS
- **Token Rotation**: Rotate your API tokens periodically
- **Access Control**: Use maturity-based governance to control skill access

---

## Troubleshooting

### Common Issues

**Issue:** "Connection refused" error
- **Solution:** Verify `MARKETPLACE_API_URL` is correct and check network connectivity

**Issue:** "Invalid API token" error
- **Solution:** Regenerate your token at atomagentos.com and update `.env`

**Issue:** Skills not syncing
- **Solution:** Check `MARKETPLACE_SYNC_ENABLED=true` and verify logs for sync errors

**Issue:** Analytics not reporting
- **Solution:** Ensure `ANALYTICS_ENABLED=true` and restart services

### Debug Mode

Enable debug logging for marketplace operations:

```bash
# Add to .env
LOG_LEVEL=DEBUG
MARKETPLACE_DEBUG=true

# Restart Atom
atom restart
```

### Getting Help

- **Documentation**: [Connection Guide](connection.md)
- **Issues**: [GitHub Issues](https://github.com/rush86999/atom/issues)
- **Community**: [Atom Discord](https://discord.gg/atom)

---

## API Reference

### Status Endpoint

Check marketplace connection status:

```bash
GET /api/admin/sync/status
```

### Manual Sync

Trigger immediate synchronization:

```bash
POST /api/admin/sync/trigger
```

### Skills List

List all available marketplace skills:

```bash
GET /api/marketplace/skills
```

---

## Related Documentation

- [Community Skills Integration](../COMMUNITY_SKILLS.md) - 5,000+ OpenClaw/ClawHub skills
- [Python Package Support](../PYTHON_PACKAGES.md) - NumPy, Pandas, 350K+ packages
- [npm Package Support](../NPM_PACKAGE_SUPPORT.md) - Lodash, Express, 2M+ packages
- [Advanced Skill Execution](../ADVANCED_SKILL_EXECUTION.md) - Skill composition and dynamic loading

---

## Changelog

### April 2026
- Added marketplace connection guide
- Updated API URLs to `https://atomagentos.com`
- Added analytics and synchronization documentation
- Enhanced skill marketplace with ratings and categories

### February 2026
- Initial marketplace implementation
- PostgreSQL-based local marketplace
- Community skills integration (5,000+ skills)

---

**Need Help?**
- Start with the [Connection Guide](connection.md)
- Check the [Troubleshooting section](#troubleshooting)
- Report issues on [GitHub](https://github.com/rush86999/atom/issues)
