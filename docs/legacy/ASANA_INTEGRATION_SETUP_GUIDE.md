# Asana Integration Setup Guide

## Overview

The Asana integration provides comprehensive task and project management capabilities within ATOM. This guide covers the complete setup process from OAuth configuration to API endpoints.

## Prerequisites

- ATOM backend server running
- PostgreSQL database configured
- Asana developer account
- Python 3.8+ environment

## 1. Asana OAuth App Configuration

### Step 1: Create Asana Developer App

1. Go to [Asana Developer Console](https://app.asana.com/-/developer_console)
2. Click "Create New App"
3. Fill in the app details:
   - **App Name**: `ATOM Integration`
   - **Description**: `ATOM AI Assistant Integration`
   - **Organization**: Your organization

### Step 2: Configure OAuth Settings

1. In your app settings, go to "App Credentials"
2. Configure the following redirect URIs:
   ```
   http://localhost:5058/api/auth/asana/callback
   http://localhost:3000/oauth/asana/callback
   ```

3. Note your credentials:
   - **Client ID**
   - **Client Secret**

### Step 3: Set Required Scopes

Ensure your app requests the following OAuth scopes:
- `default`
- `tasks:read`
- `tasks:write`
- `projects:read`
- `projects:write`
- `workspaces:read`
- `users:read`

## 2. Environment Configuration

### Required Environment Variables

Add the following to your `.env` file:

```bash
# Asana OAuth Configuration
ASANA_CLIENT_ID=your_asana_client_id
ASANA_CLIENT_SECRET=your_asana_client_secret
ASANA_REDIRECT_URI=http://localhost:5058/api/auth/asana/callback

# Database Configuration
DATABASE_URL=postgresql://user:password@localhost:5432/atom_db
```

### Optional Configuration

```bash
# For production
ASANA_REDIRECT_URI=https://your-domain.com/api/auth/asana/callback

# Test configuration
TEST_USER_ID=test_user_asana
```

## 3. Database Setup

### Run Database Migrations

Execute the Asana schema to create required tables:

```bash
psql -d atom_db -f asana_schema.sql
```

### Schema Overview

The integration creates the following tables:

1. **user_asana_oauth_tokens** - Stores encrypted OAuth tokens
2. **user_asana_tasks** - Task metadata cache
3. **user_asana_projects** - Project metadata cache

## 4. Backend Integration

### Service Registration

The Asana integration is automatically registered when the backend starts. Verify registration:

```bash
curl http://localhost:5058/api/asana/health
```

Expected response:
```json
{
  "ok": true,
  "service": "asana",
  "status": "registered",
  "message": "Asana integration is registered and ready for OAuth configuration",
  "needs_oauth": true
}
```

### Available Endpoints

#### OAuth Endpoints
- `GET /api/auth/asana/authorize` - Initiate OAuth flow
- `GET /api/auth/asana/callback` - Handle OAuth callback
- `GET /api/auth/asana/status` - Check connection status
- `POST /api/auth/asana/refresh` - Refresh access token
- `POST /api/auth/asana/disconnect` - Disconnect integration

#### Task Management
- `POST /api/asana/search` - Search tasks
- `POST /api/asana/list-tasks` - List project tasks
- `POST /api/asana/create-task` - Create new task
- `POST /api/asana/update-task` - Update existing task

#### Project Management
- `POST /api/asana/projects` - List projects
- `POST /api/asana/sections` - List project sections
- `POST /api/asana/teams` - List workspace teams
- `POST /api/asana/users` - List workspace users
- `POST /api/asana/user-profile` - Get user profile

## 5. Frontend Integration

### Skills Available

The following Asana skills are available in the frontend:

```typescript
// Task Management
searchAsana(userId: string, projectId: string, query: string)
listAsanaTasks(userId: string, projectId: string)
createAsanaTask(userId: string, projectId: string, name: string, notes?: string, dueOn?: string, assignee?: string)
updateAsanaTask(userId: string, taskId: string, name?: string, notes?: string, dueOn?: string, completed?: boolean)

// Project Management
getAsanaProjects(userId: string, workspaceId?: string, limit?: number, offset?: string)
getAsanaSections(userId: string, projectId: string, limit?: number, offset?: string)
getAsanaTeams(userId: string, workspaceId: string, limit?: number, offset?: string)
getAsanaUsers(userId: string, workspaceId: string, limit?: number, offset?: string)
getAsanaUserProfile(userId: string, targetUserId?: string)
```

### UI Components

The integration includes React components for:
- **AsanaManager** - Main integration management
- **AsanaDesktopManager** - Desktop-specific integration
- **AsanaDesktopCallback** - OAuth callback handler
- **AsanaSkills** - Skill integration component

## 6. Testing the Integration

### Run Comprehensive Tests

```bash
python test_complete_asana_integration.py
```

### Manual Testing Steps

1. **Test Health Endpoint**
   ```bash
   curl http://localhost:5058/api/asana/health
   ```

2. **Test OAuth Initiation**
   ```bash
   curl "http://localhost:5058/api/auth/asana/authorize?user_id=test_user"
   ```

3. **Test Without Authentication** (should return AUTH_ERROR)
   ```bash
   curl -X POST http://localhost:5058/api/asana/search \
     -H "Content-Type: application/json" \
     -d '{"user_id": "test_user", "project_id": "test_project", "query": "test"}'
   ```

## 7. OAuth Flow Implementation

### Step-by-Step OAuth Process

1. **Initiation**: User clicks "Connect Asana" in ATOM UI
2. **Authorization**: User grants permissions in Asana
3. **Callback**: Asana redirects to ATOM with authorization code
4. **Token Exchange**: ATOM exchanges code for access/refresh tokens
5. **Storage**: Tokens encrypted and stored in database
6. **Confirmation**: User sees successful connection message

### Token Management

- Access tokens are automatically refreshed when expired
- Tokens are encrypted before storage
- Refresh tokens are used to maintain long-term access

## 8. Security Considerations

### Token Encryption
- All OAuth tokens are encrypted using AES-256
- Encryption keys should be stored securely
- Database connections use SSL/TLS

### CSRF Protection
- OAuth flows include state parameter for CSRF protection
- Session-based authentication validation

### Scope Management
- Minimal required scopes requested
- Users can review granted permissions in Asana

## 9. Troubleshooting

### Common Issues

1. **OAuth Redirect URI Mismatch**
   - Ensure redirect URI matches exactly in Asana app settings
   - Check for trailing slashes and protocol (http vs https)

2. **Invalid Client Credentials**
   - Verify ASANA_CLIENT_ID and ASANA_CLIENT_SECRET environment variables
   - Check for typos or encoding issues

3. **Database Connection Issues**
   - Verify DATABASE_URL is correctly formatted
   - Check PostgreSQL is running and accessible

4. **Token Refresh Failures**
   - Verify refresh token is stored correctly
   - Check token expiration handling

### Debug Mode

Enable debug logging by setting:
```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

## 10. Production Deployment

### Environment Variables for Production

```bash
# Production OAuth
ASANA_CLIENT_ID=your_production_client_id
ASANA_CLIENT_SECRET=your_production_client_secret
ASANA_REDIRECT_URI=https://your-production-domain.com/api/auth/asana/callback

# Production Database
DATABASE_URL=postgresql://user:password@production-db:5432/atom_db_prod
```

### Security Best Practices

1. **Use HTTPS** in production for all OAuth callbacks
2. **Rotate client secrets** regularly
3. **Monitor token usage** and refresh patterns
4. **Implement rate limiting** for API endpoints
5. **Regular security audits** of the integration

## 11. API Reference

### Request/Response Format

All endpoints follow this pattern:

**Request:**
```json
{
  "user_id": "string",
  // endpoint-specific parameters
}
```

**Response:**
```json
{
  "ok": true,
  "data": {
    // endpoint-specific data
  }
}
```

**Error Response:**
```json
{
  "ok": false,
  "error": {
    "code": "ERROR_CODE",
    "message": "Human readable error message"
  }
}
```

### Error Codes

- `AUTH_ERROR` - User not authenticated with Asana
- `VALIDATION_ERROR` - Missing or invalid parameters
- `CONFIG_ERROR` - Server configuration issue
- `NETWORK_ERROR` - Connection to Asana API failed

## 12. Support and Maintenance

### Monitoring

- Monitor `/api/asana/health` endpoint
- Track OAuth token refresh success rates
- Log API usage and error rates

### Updates

- Keep Asana Python SDK updated
- Monitor Asana API changelog for breaking changes
- Test integration after Asana API updates

### Support Channels

- Check ATOM documentation
- Review Asana API documentation
- Contact development team for integration issues

---

**Last Updated**: 2024
**Version**: 1.0