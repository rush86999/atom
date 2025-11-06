# ATOM Slack Integration API Documentation

## Overview

The ATOM Slack Integration provides a comprehensive set of APIs for connecting, managing, and analyzing Slack workspaces. This document covers all available endpoints, authentication methods, usage examples, and implementation details.

## Table of Contents

1. [Authentication](#authentication)
2. [Base URL](#base-url)
3. [Response Format](#response-format)
4. [Error Handling](#error-handling)
5. [Endpoints](#endpoints)
   - [Health Check](#health-check)
   - [Workspace Management](#workspace-management)
   - [Channel Operations](#channel-operations)
   - [Message Operations](#message-operations)
   - [User Management](#user-management)
   - [File Management](#file-management)
   - [Search](#search)
   - [Analytics](#analytics)
   - [Event Handling](#event-handling)
   - [Data Ingestion](#data-ingestion)
   - [Configuration](#configuration)
6. [Rate Limiting](#rate-limiting)
7. [Webhooks](#webhooks)
8. [SDK Examples](#sdk-examples)
9. [Troubleshooting](#troubleshooting)

## Authentication

### OAuth 2.0 Flow

The Slack integration uses OAuth 2.0 for authentication. Follow these steps:

#### 1. Initiate OAuth Flow

```http
POST /api/auth/slack/authorize
Content-Type: application/json

{
  "user_id": "user123",
  "scopes": [
    "channels:read",
    "channels:history",
    "groups:read",
    "groups:history",
    "im:read",
    "im:history",
    "mpim:read",
    "mpim:history",
    "users:read",
    "files:read",
    "reactions:read",
    "team:read",
    "chat:write",
    "chat:write.public"
  ]
}
```

**Response:**
```json
{
  "ok": true,
  "authorization_url": "https://slack.com/oauth/v2/authorize?...",
  "state": "random_state_string"
}
```

#### 2. Handle OAuth Callback

```http
POST /api/auth/slack/callback
Content-Type: application/json

{
  "code": "authorization_code_from_slack",
  "state": "state_parameter_from_oauth_request"
}
```

**Response:**
```json
{
  "ok": true,
  "access_token": "xoxb-...",
  "token_type": "bot",
  "scope": "channels:read,channels:history,...",
  "bot_user_id": "U1234567890",
  "team_id": "T1234567890",
  "team_name": "Company Workspace"
}
```

### Required Scopes

- **Read Operations:** `channels:read`, `channels:history`, `groups:read`, `groups:history`, `im:read`, `im:history`, `mpim:read`, `mpim:history`, `users:read`, `files:read`, `reactions:read`, `team:read`
- **Write Operations:** `chat:write`, `chat:write.public`
- **Webhook Operations:** (configured in Slack App settings)

## Base URL

```
https://your-atom-domain.com/api/integrations/slack
```

## Response Format

### Success Response

```json
{
  "ok": true,
  "data": { ... },
  "timestamp": "2023-12-01T12:00:00Z"
}
```

### Error Response

```json
{
  "ok": false,
  "error": {
    "code": "SLACK_API_ERROR",
    "message": "Detailed error description",
    "details": { ... }
  },
  "timestamp": "2023-12-01T12:00:00Z"
}
```

## Error Handling

### Common Error Codes

| Code | Description | Resolution |
|------|-------------|------------|
| `AUTH_REQUIRED` | User not authenticated | Complete OAuth flow |
| `TOKEN_EXPIRED` | Access token expired | Refresh token or re-authenticate |
| `RATE_LIMITED` | API rate limit exceeded | Wait and retry |
| `WORKSPACE_NOT_FOUND` | Workspace not accessible | Check workspace permissions |
| `CHANNEL_NOT_FOUND` | Channel not accessible | Check channel permissions |
| `INSUFFICIENT_PERMISSIONS` | Missing required scopes | Update OAuth scopes |
| `NETWORK_ERROR` | Connection failed | Check network connectivity |

## Endpoints

### Health Check

#### Check Service Health

```http
POST /health
```

**Response:**
```json
{
  "ok": true,
  "status": "healthy",
  "service": "slack_integration",
  "version": "2.0.0",
  "capabilities": [
    "oauth_flow",
    "webhook_verification",
    "rate_limiting",
    "error_handling",
    "caching",
    "user_management",
    "channel_operations",
    "message_operations",
    "search",
    "file_management"
  ],
  "service_status": {
    "connected": true,
    "last_check": "2023-12-01T12:00:00Z",
    "error_count": 0,
    "total_requests": 150
  }
}
```

### Workspace Management

#### List Workspaces

```http
POST /workspaces
Content-Type: application/json

{
  "user_id": "user123"
}
```

**Response:**
```json
{
  "ok": true,
  "workspaces": [
    {
      "id": "T1234567890",
      "name": "Company Workspace",
      "domain": "company",
      "url": "https://company.slack.com",
      "icon": {
        "image_34": "https://.../icon.png"
      },
      "enterprise_id": "E1234567890",
      "enterprise_name": "Company Enterprise",
      "is_verified": true,
      "plan": "enterprise",
      "total_users": 150,
      "total_channels": 25
    }
  ],
  "total_count": 1,
  "timestamp": "2023-12-01T12:00:00Z"
}
```

#### Get Workspace Details

```http
POST /workspace/details
Content-Type: application/json

{
  "user_id": "user123",
  "workspace_id": "T1234567890"
}
```

### Channel Operations

#### List Channels

```http
POST /channels
Content-Type: application/json

{
  "user_id": "user123",
  "workspace_id": "T1234567890",
  "include_private": false,
  "include_archived": false,
  "limit": 100
}
```

**Response:**
```json
{
  "ok": true,
  "channels": [
    {
      "id": "C1234567890",
      "name": "general",
      "display_name": "general",
      "purpose": {
        "value": "Company-wide announcements"
      },
      "topic": {
        "value": "Company updates"
      },
      "is_private": false,
      "is_archived": false,
      "is_general": true,
      "is_shared": false,
      "num_members": 150,
      "created": 1609459200,
      "workspace_id": "T1234567890",
      "workspace_name": "Company Workspace"
    }
  ],
  "total_count": 25,
  "filters": {
    "include_private": false,
    "include_archived": false,
    "limit": 100
  }
}
```

### Message Operations

#### Get Messages

```http
POST /messages
Content-Type: application/json

{
  "user_id": "user123",
  "workspace_id": "T1234567890",
  "channel_id": "C1234567890",
  "limit": 100,
  "latest": "1234567890.123456",
  "oldest": "1234567000.123456",
  "filters": {
    "from_user": "me",
    "has_files": false,
    "starred": false,
    "pinned": false
  }
}
```

**Response:**
```json
{
  "ok": true,
  "messages": [
    {
      "id": "1234567890.123456",
      "text": "Hello from ATOM!",
      "user": "U1234567890",
      "user_name": "john.doe",
      "channel": "C1234567890",
      "channel_name": "general",
      "team": "T1234567890",
      "ts": "1234567890.123456",
      "thread_ts": "1234567890.123456",
      "type": "message",
      "subtype": null,
      "reactions": [
        {
          "name": "thumbsup",
          "count": 3,
          "users": ["U1234567890", "U0987654321"]
        }
      ],
      "files": [],
      "pinned_to": [],
      "is_starred": false,
      "reply_count": 2,
      "has_files": false,
      "has_reactions": true,
      "reaction_count": 3
    }
  ],
  "has_more": true,
  "total": 100,
  "filters": {
    "from_user": "me",
    "has_files": false,
    "starred": false,
    "pinned": false
  }
}
```

#### Send Message

```http
POST /messages/send
Content-Type: application/json

{
  "user_id": "user123",
  "workspace_id": "T1234567890",
  "channel_id": "C1234567890",
  "text": "Hello from ATOM!",
  "thread_ts": "1234567890.123456"
}
```

**Response:**
```json
{
  "ok": true,
  "message": {
    "id": "1234567891.123457",
    "text": "Hello from ATOM!",
    "user": "U1234567890",
    "channel": "C1234567890",
    "team": "T1234567890",
    "ts": "1234567891.123457",
    "thread_ts": "1234567890.123456"
  }
}
```

### User Management

#### List Users

```http
POST /users
Content-Type: application/json

{
  "user_id": "user123",
  "workspace_id": "T1234567890",
  "include_restricted": false,
  "include_bots": false,
  "limit": 100
}
```

**Response:**
```json
{
  "ok": true,
  "users": [
    {
      "id": "U1234567890",
      "name": "john.doe",
      "real_name": "John Doe",
      "display_name": "John Doe",
      "profile": {
        "email": "john.doe@company.com",
        "image_24": "https://.../avatar.png"
      },
      "is_bot": false,
      "is_admin": false,
      "is_owner": false,
      "presence": "active",
      "workspace_id": "T1234567890"
    }
  ],
  "total_count": 150,
  "filters": {
    "include_restricted": false,
    "include_bots": false,
    "limit": 100
  }
}
```

### File Management

#### List Files

```http
POST /files
Content-Type: application/json

{
  "user_id": "user123",
  "workspace_id": "T1234567890",
  "channel_id": "C1234567890",
  "uploaded_by": "U1234567890",
  "file_type": "pdf",
  "limit": 50
}
```

**Response:**
```json
{
  "ok": true,
  "files": [
    {
      "id": "F1234567890",
      "name": "document.pdf",
      "title": "Important Document",
      "mimetype": "application/pdf",
      "filetype": "pdf",
      "pretty_type": "PDF",
      "size": 1048576,
      "user": "U1234567890",
      "uploader_name": "john.doe",
      "url_private": "https://files.slack.com/...",
      "permalink": "https://company.slack.com/files/...",
      "created": 1609459200,
      "timestamp": 1609459200,
      "is_public": false,
      "workspace_id": "T1234567890"
    }
  ],
  "total": 45,
  "paging": {
    "page": 1,
    "pages": 2,
    "per_page": 50,
    "total": 45
  }
}
```

### Search

#### Search Messages

```http
POST /search
Content-Type: application/json

{
  "user_id": "user123",
  "workspace_id": "T1234567890",
  "query": "project deadline",
  "channel_id": "C1234567890",
  "sort": "timestamp",
  "sort_dir": "desc",
  "count": 50
}
```

**Response:**
```json
{
  "ok": true,
  "messages": [
    {
      "id": "1234567890.123456",
      "text": "The project deadline is next Friday",
      "user": "U1234567890",
      "user_name": "john.doe",
      "channel": "C1234567890",
      "channel_name": "general",
      "ts": "1234567890.123456",
      "score": 0.95
    }
  ],
  "paging": {
    "page": 1,
    "pages": 3,
    "per_page": 50,
    "total": 125
  },
  "total": 50,
  "query": "project deadline",
  "search_filters": {
    "channel_id": "C1234567890",
    "sort": "timestamp",
    "sort_dir": "desc",
    "count": 50
  }
}
```

### Analytics

#### Get Activity Analytics

```http
POST /analytics/activity
Content-Type: application/json

{
  "user_id": "user123",
  "date_range": {
    "start": "2023-11-01",
    "end": "2023-11-30"
  },
  "aggregation": "daily"
}
```

**Response:**
```json
{
  "ok": true,
  "analytics": {
    "activity_over_time": [
      {
        "period": "2023-11-01",
        "message_count": 150,
        "unique_users": 12,
        "active_channels": 8
      },
      {
        "period": "2023-11-02",
        "message_count": 180,
        "unique_users": 14,
        "active_channels": 9
      }
    ],
    "top_users": [
      {
        "user_id": "U1234567890",
        "user_name": "john.doe",
        "message_count": 85,
        "channels_used": 5,
        "avg_message_length": 120
      }
    ],
    "top_channels": [
      {
        "channel_id": "C1234567890",
        "channel_name": "general",
        "message_count": 200,
        "unique_users": 15,
        "avg_message_length": 95
      }
    ],
    "summary": {
      "total_messages": 3300,
      "total_users": 25,
      "total_channels": 12
    }
  }
}
```

### Event Handling

#### Handle Webhook Events

```http
POST /events
Content-Type: application/json
X-Slack-Request-Timestamp: 1234567890
X-Slack-Signature: v0=<signature>

{
  "type": "event_callback",
  "event": {
    "type": "message",
    "user": "U1234567890",
    "text": "Hello world",
    "channel": "C1234567890",
    "ts": "1234567890.123456"
  }
}
```

**Response:**
```json
{
  "ok": true,
  "status": "processed",
  "event_type": "message",
  "timestamp": "2023-12-01T12:00:00Z"
}
```

#### URL Verification

```http
POST /events
Content-Type: application/json

{
  "type": "url_verification",
  "challenge": "test_challenge_string"
}
```

**Response:**
```json
{
  "challenge": "test_challenge_string"
}
```

### Data Ingestion

#### Start Data Ingestion

```http
POST /ingest
Content-Type: application/json

{
  "user_id": "user123",
  "workspace_id": "T1234567890",
  "config": {
    "syncOptions": {
      "messageTypes": ["messages", "replies", "files"],
      "realTimeSync": true,
      "syncFrequency": "realtime"
    },
    "filters": {
      "includePrivate": false,
      "includeArchived": false,
      "excludeBots": false
    },
    "features": {
      "reactions": true,
      "threads": true,
      "files": true
    }
  }
}
```

**Response:**
```json
{
  "ok": true,
  "ingestion": {
    "ingestion_id": "slack_ingest_T1234567890_1701388800",
    "status": "started",
    "workspace_id": "T1234567890",
    "config": { ... },
    "estimated_items": 5000,
    "started_at": "2023-12-01T12:00:00Z"
  }
}
```

### Configuration

#### Get Configuration

```http
GET /config
```

**Response:**
```json
{
  "ok": true,
  "config": {
    "oauth_configured": true,
    "webhook_configured": true,
    "scopes": [
      "channels:read",
      "channels:history",
      "users:read",
      "chat:write",
      "files:read"
    ],
    "features": {
      "realtime_events": true,
      "analytics": true,
      "search": true,
      "file_management": true
    }
  }
}
```

#### Update Configuration

```http
POST /config
Content-Type: application/json

{
  "realtime_events": true,
  "analytics_enabled": true,
  "search_enabled": true
}
```

## Rate Limiting

### Slack API Rate Limits

The Slack integration respects Slack's rate limits:

| Tier | Requests per Second | Usage |
|------|-------------------|--------|
| Tier 1 | 1 per minute | Search APIs |
| Tier 2 | 1 per second | Message actions |
| Tier 3 | 20+ per second | Message fetching |

### Rate Limit Headers

All responses include rate limit information:

```http
X-RateLimit-Limit: 100
X-RateLimit-Remaining: 95
X-RateLimit-Reset: 1701390400
```

### Handling Rate Limits

When rate limited, the API returns:

```json
{
  "ok": false,
  "error": {
    "code": "RATE_LIMITED",
    "message": "Rate limit exceeded. Retry after 60 seconds",
    "retry_after": 60
  }
}
```

## Webhooks

### Event Subscriptions

Configure your Slack App to send events to:

```
https://your-atom-domain.com/api/integrations/slack/events
```

### Supported Events

- `message` - New messages
- `message_changed` - Message edits
- `message_deleted` - Message deletions
- `file_shared` - File uploads
- `file_deleted` - File deletions
- `channel_created` - New channels
- `channel_deleted` - Channel deletions
- `channel_archive` - Channel archival
- `channel_unarchive` - Channel restoration
- `team_join` - New user joins
- `team_leave` - User leaves
- `app_home_opened` - App home opened
- `app_mention` - App mentioned

### Event Verification

All webhook requests are verified using Slack's signing secret:

1. Extract `X-Slack-Request-Timestamp` and `X-Slack-Signature` headers
2. Check timestamp is within 5 minutes
3. Create signature: `v0=` + HMAC-SHA256(signing_secret, "v0:timestamp:body")
4. Compare with provided signature

## SDK Examples

### Python SDK

```python
from integrations.slack_service_unified import SlackUnifiedService

# Initialize service
service = SlackUnifiedService({
    'client_id': 'your_client_id',
    'client_secret': 'your_client_secret',
    'signing_secret': 'your_signing_secret'
})

# Get OAuth URL
auth_url = await service.get_oauth_url('user123', ['channels:read', 'users:read'])
print(f"Visit: {auth_url}")

# Exchange code for token
token_data = await service.exchange_code_for_token('authorization_code')
access_token = token_data['access_token']

# Test connection
connection = await service.test_connection(access_token)
print(f"Connected: {connection['connected']}")

# Get workspaces
workspaces = await service.list_workspaces(access_token)
print(f"Found {len(workspaces)} workspaces")

# Get channels
channels = await service.list_channels(access_token)
print(f"Found {len(channels)} channels")

# Send message
message = await service.post_message(
    access_token,
    'C1234567890',
    'Hello from ATOM!'
)
print(f"Message sent: {message['ts']}")

# Close service
await service.close()
```

### JavaScript/TypeScript SDK

```typescript
import { SlackIntegrationManager } from './components/SlackManagerV2';

function MySlackIntegration() {
  return (
    <SlackIntegrationManager
      userId="user123"
      atomIngestionPipeline={atomIngestionPipeline}
      onIngestionComplete={(result) => {
        console.log('Ingestion complete:', result);
      }}
      onConfigurationChange={(config) => {
        console.log('Configuration changed:', config);
      }}
    />
  );
}
```

### React Component

```tsx
import React from 'react';
import { SlackManagerV2 } from '@atom/slack-integration';

export default function SlackIntegrationPage() {
  return (
    <div className="container">
      <h1>Slack Integration</h1>
      <SlackManagerV2
        userId="current-user"
        onError={(error) => {
          console.error('Slack error:', error);
        }}
      />
    </div>
  );
}
```

## Troubleshooting

### Common Issues

#### 1. OAuth Flow Fails

**Symptoms:**
- OAuth URL generation fails
- Callback handling fails
- Token exchange fails

**Solutions:**
- Verify `SLACK_CLIENT_ID` and `SLACK_CLIENT_SECRET` environment variables
- Check redirect URI matches Slack App configuration
- Ensure required scopes are requested
- Verify state parameter handling

#### 2. API Rate Limiting

**Symptoms:**
- Frequent "rate limited" errors
- Slow response times
- Failed requests

**Solutions:**
- Implement exponential backoff
- Use pagination for large datasets
- Cache frequently accessed data
- Optimize API call patterns

#### 3. Webhook Events Not Received

**Symptoms:**
- No events received
- Event verification failures
- Missing event types

**Solutions:**
- Verify `SLACK_SIGNING_SECRET` is configured
- Check webhook URL is accessible
- Ensure event subscriptions are enabled in Slack App
- Verify request signature verification

#### 4. Data Ingestion Issues

**Symptoms:**
- Ingestion fails to start
- Slow ingestion progress
- Missing data

**Solutions:**
- Check workspace and channel permissions
- Verify access tokens are valid
- Monitor ingestion logs for errors
- Adjust configuration settings

#### 5. Search Not Working

**Symptoms:**
- No search results
- Search errors
- Slow search performance

**Solutions:**
- Verify search permissions
- Check message indexing status
- Optimize search queries
- Use specific search filters

### Debug Mode

Enable debug logging:

```bash
# Backend
export LOG_LEVEL=debug
export SLACK_DEBUG=true

# Frontend
localStorage.setItem('atom_debug', 'true')
```

### Health Monitoring

Monitor service health:

```bash
# Check service status
curl -X POST https://your-domain.com/api/integrations/slack/health

# Check rate limits
curl -X POST https://your-domain.com/api/integrations/slack/health | jq '.service_status'
```

### Logs and Monitoring

Key log locations:
- Backend: `/var/log/atom/slack-integration.log`
- Frontend: Browser console (in debug mode)
- Webhook: Event processing logs

Monitor:
- Connection status
- Error rates
- API response times
- Ingestion progress

## Support

For support and issues:

- **Documentation**: https://docs.atom.com/slack-integration
- **GitHub Issues**: https://github.com/atom-platform/slack-integration/issues
- **Support Email**: slack-support@atom.com
- **Community**: https://community.atom.com/c/slack

## Changelog

### v2.0.0 (2023-12-01)
- Complete rewrite with unified service architecture
- Enhanced error handling and rate limiting
- Real-time event processing
- Advanced search and analytics
- Comprehensive testing suite
- Improved documentation

### v1.5.0 (2023-10-15)
- Added webhook support
- Enhanced search capabilities
- Improved error messages

### v1.0.0 (2023-08-01)
- Initial release
- Basic OAuth and API endpoints
- Message and channel operations

---

*Last updated: December 1, 2023*