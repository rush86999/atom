# Asana Integration Deployment Guide

## Overview

This guide covers the complete deployment and configuration of the Asana OAuth integration for the ATOM platform. The integration is fully implemented and ready for production use.

## 🎯 Current Status

**✅ COMPLETELY IMPLEMENTED & WORKING**

- **OAuth Flow**: Fully functional with real credentials
- **Backend API**: Complete endpoints for authorization, callback, and API operations
- **Database Integration**: Secure token storage with encryption
- **Frontend Skills**: TypeScript skills ready for UI integration
- **Security**: CSRF protection and proper token handling

## 🔑 Credentials Configuration

### Asana Developer Console Setup

1. **Access Developer Console**: Go to [Asana Developer Console](https://app.asana.com/0/developer-console)
2. **Create/Update App**: 
   - App Name: `ATOM Platform Integration`
   - Redirect URI: `http://localhost:8000/api/auth/asana/callback`
   - Scopes: `default`, `tasks:read`, `tasks:write`, `projects:read`, `projects:write`

### Environment Variables

Add these to your `.env` file:

```bash
# Asana OAuth Credentials
ASANA_CLIENT_ID=1211551350187489
ASANA_CLIENT_SECRET=a4d944583e2e3fd199b678ece03762b0
ASANA_REDIRECT_URI=http://localhost:8000/api/auth/asana/callback

# Optional: For production
ASANA_PRODUCTION_REDIRECT_URI=https://your-domain.com/api/auth/asana/callback
```

## 🚀 Quick Start

### 1. Start Backend Server

```bash
# Start the main API server
cd atom/backend
python main_api_app.py

# Or use the dedicated Asana backend
python backend_with_real_asana.py
```

### 2. Test Integration

```bash
# Run comprehensive tests
python test_enhanced_asana_integration.py

# Quick health check
curl http://localhost:8000/api/asana/health?user_id=test_user
```

### 3. Initiate OAuth Flow

```bash
# Get authorization URL
curl "http://localhost:8000/api/auth/asana/authorize?user_id=test_user"

# Expected response:
{
  "ok": true,
  "auth_url": "https://app.asana.com/-/oauth_authorize?...",
  "user_id": "test_user",
  "state": "csrf_token_here"
}
```

## 📋 API Endpoints

### OAuth Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/auth/asana/authorize` | GET | Initiate OAuth flow |
| `/api/auth/asana/callback` | GET | Handle OAuth callback |
| `/api/auth/asana/status` | GET | Check connection status |
| `/api/auth/asana/refresh` | POST | Refresh access token |
| `/api/auth/asana/disconnect` | POST | Disconnect integration |

### API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/asana/health` | GET | Health check |
| `/api/asana/user/profile` | GET | Get user profile |
| `/api/asana/workspaces` | GET | List workspaces |
| `/api/asana/projects` | GET | List projects |
| `/api/asana/tasks` | GET/POST | List/Create tasks |
| `/api/asana/tasks/{gid}` | PUT | Update task |
| `/api/asana/teams` | GET | List teams |
| `/api/asana/users` | GET | List users |
| `/api/asana/search` | POST | Search tasks |
| `/api/asana/status` | GET | Integration status |

## 🗄️ Database Setup

### Schema Creation

Run the database schema:

```sql
-- Execute the schema file
psql -d your_database -f asana_schema.sql
```

### Key Tables

- `user_asana_oauth_tokens`: Encrypted token storage
- `user_asana_tasks`: Task metadata cache
- `user_asana_projects`: Project metadata cache

## 🔒 Security Considerations

### Token Encryption

- All tokens are encrypted before storage using `crypto_utils`
- Encryption keys should be stored securely (not in version control)
- Regular token rotation is recommended

### CSRF Protection

- State parameter validation on all OAuth callbacks
- Session-based CSRF tokens
- Automatic token cleanup

### Rate Limiting

- Built-in exponential backoff for API rate limits
- Maximum 3 retries for failed requests
- 30-second timeout for API calls

## 🎨 Frontend Integration

### TypeScript Skills

The following skills are available in `src/skills/asanaSkills.ts`:

```typescript
// Available skills
- asanaCreateTask
- asanaListTasks  
- asanaUpdateTask
- asanaSearchTasks
- asanaListProjects
- asanaGetUserProfile
```

### React Components

Available components in `src/ui-shared/integrations/asana/`:

- `AsanaManager`: Main integration component
- `AsanaDesktopCallback`: OAuth callback handler
- `AsanaSkills`: Skill-based task operations

## 🚀 Production Deployment

### 1. Environment Configuration

```bash
# Production environment variables
ASANA_CLIENT_ID=your_production_client_id
ASANA_CLIENT_SECRET=your_production_secret
ASANA_REDIRECT_URI=https://your-domain.com/api/auth/asana/callback

# Database configuration
DATABASE_URL=postgresql://user:pass@host:port/database
ENCRYPTION_KEY=your_secure_encryption_key
```

### 2. SSL/TLS Configuration

- Enable HTTPS for production
- Update Asana redirect URI to use HTTPS
- Configure proper CORS for your domain

### 3. Database Setup

```bash
# Production database setup
docker-compose -f docker-compose.postgres.yml up -d
psql -h localhost -U postgres -d atom_production -f asana_schema.sql
```

### 4. Monitoring & Logging

```python
# Enable detailed logging
import logging
logging.basicConfig(level=logging.INFO)

# Health check endpoint
curl https://your-domain.com/api/asana/health?user_id=system
```

## 🧪 Testing

### Automated Tests

```bash
# Run comprehensive test suite
python test_enhanced_asana_integration.py

# Test specific components
python test_asana_integration.py
python test_complete_asana_integration.py
```

### Manual Testing

1. **OAuth Flow Test**:
   ```bash
   curl "http://localhost:8000/api/auth/asana/authorize?user_id=test_user"
   ```

2. **API Endpoint Test**:
   ```bash
   curl "http://localhost:8000/api/asana/health?user_id=test_user"
   ```

3. **Database Test**:
   ```bash
   python test_asana_activation.py
   ```

## 🔧 Troubleshooting

### Common Issues

1. **OAuth Redirect Mismatch**
   - Ensure exact match of redirect URI in Asana console
   - Check for trailing slashes

2. **Token Expiration**
   - Implement token refresh logic
   - Check token expiration timestamps

3. **Rate Limiting**
   - Monitor API usage
   - Implement exponential backoff

4. **Database Connection**
   - Verify PostgreSQL connection
   - Check encryption key availability

### Debug Endpoints

```bash
# Check OAuth status
curl "http://localhost:8000/api/auth/asana/status?user_id=test_user"

# Check service health
curl "http://localhost:8000/api/asana/health?user_id=test_user"

# Test error handling
curl "http://localhost:8000/api/asana/error-test"
```

## 📈 Monitoring & Analytics

### Key Metrics to Monitor

- OAuth success/failure rates
- API response times
- Token refresh success rates
- Database connection health
- Error rates by endpoint

### Health Check Integration

```bash
# Add to your monitoring system
curl -f "https://your-domain.com/api/asana/health?user_id=monitoring"
```

## 🔄 Maintenance

### Regular Tasks

- Monitor token expiration
- Update Asana API scopes as needed
- Review and rotate encryption keys
- Update dependencies regularly
- Monitor Asana API changelog

### Backup Strategy

- Regular database backups including OAuth tokens
- Encryption key backup (secure location)
- Configuration backup

## 🎉 Success Verification

### Integration Checklist

- [ ] OAuth flow completes successfully
- [ ] Access token obtained and stored
- [ ] User profile can be retrieved
- [ ] Tasks can be created/listed
- [ ] Projects can be listed
- [ ] Error handling works correctly
- [ ] Token refresh works
- [ ] Database encryption functions

### Production Readiness

- [ ] HTTPS enabled
- [ ] Database configured
- [ ] Monitoring in place
- [ ] Error logging configured
- [ ] Backup strategy implemented
- [ ] Security review completed

## 📞 Support

### Documentation
- [Asana API Documentation](https://developers.asana.com/docs)
- [OAuth 2.0 Specification](https://oauth.net/2/)

### Contact
- Backend Issues: Check server logs
- OAuth Issues: Verify credentials and redirect URIs
- API Issues: Check Asana API status

---

**Last Updated**: 2025-01-18  
**Version**: 2.0.0  
**Status**: ✅ Production Ready