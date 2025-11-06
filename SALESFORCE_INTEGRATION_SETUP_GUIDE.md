# Salesforce Integration Setup Guide

## Overview

This guide provides comprehensive instructions for setting up and configuring Salesforce integration with the ATOM Agent Memory System. The integration enables secure OAuth 2.0 authentication, CRM data management, and advanced sales analytics.

## Prerequisites

- Salesforce Developer Account or Production Org
- ATOM Agent Memory System deployed
- Access to Salesforce Setup menu
- Administrative permissions for OAuth app configuration

## Step 1: Salesforce Connected App Setup

### 1.1 Create Connected App in Salesforce

1. Log in to your Salesforce org
2. Navigate to **Setup** → **App Manager** → **New Connected App**
3. Configure the connected app with the following settings:

**Basic Information:**
- **Connected App Name**: `ATOM Agent Memory System`
- **API Name**: `ATOM_Agent_Memory_System`
- **Contact Email**: Your email address
- **Description**: `ATOM Agent Memory System Integration`

**API (Enable OAuth Settings):**
- ✅ **Enable OAuth Settings**
- **Callback URL**: `https://your-backend-domain.com/api/auth/salesforce/callback`
- **Selected OAuth Scopes**:
  - ✅ **Access and manage your data (api)**
  - ✅ **Perform requests at any time (refresh_token, offline_access)**
  - ✅ **Access your basic information (id, profile, email, address, phone)**

**Web App Settings:**
- ✅ **Enable Client Credentials Flow**
- ✅ **Require Secret for Web Server Flow**

### 1.2 Retrieve OAuth Credentials

After creating the connected app, copy these values:

- **Consumer Key (Client ID)**
- **Consumer Secret (Client Secret)**
- **Callback URL** (must match your backend domain)

## Step 2: Environment Configuration

### 2.1 Backend Environment Variables

Add the following environment variables to your backend configuration:

```bash
# Salesforce OAuth Configuration
SALESFORCE_CLIENT_ID="your-consumer-key-here"
SALESFORCE_CLIENT_SECRET="your-consumer-secret-here"
SALESFORCE_REDIRECT_URI="https://your-backend-domain.com/api/auth/salesforce/callback"
SALESFORCE_API_VERSION="57.0"

# Optional: Custom Salesforce instance (use for sandbox/testing)
# SALESFORCE_INSTANCE_URL="https://your-instance.salesforce.com"
```

### 2.2 Database Configuration

The Salesforce integration requires a PostgreSQL database with the following tables:

```sql
-- OAuth tokens table (automatically created by the system)
CREATE TABLE IF NOT EXISTS salesforce_oauth_tokens (
    id SERIAL PRIMARY KEY,
    user_id VARCHAR(255) NOT NULL,
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
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(user_id)
);
```

## Step 3: Integration Verification

### 3.1 Health Check Endpoints

Verify the integration is working by testing these endpoints:

```bash
# Overall health
GET /api/salesforce/health

# Token health for specific user
GET /api/salesforce/health/tokens?user_id=your_user_id

# Connection test
GET /api/salesforce/health/connection?user_id=your_user_id

# Comprehensive health summary
GET /api/salesforce/health/summary?user_id=your_user_id
```

### 3.2 Service Registry Verification

Check that Salesforce appears in the service registry:

```bash
GET /api/services
```

Look for these Salesforce services:
- `salesforce_service`
- `salesforce_handler`
- `auth_handler_salesforce`
- `salesforce_enhanced_api`

## Step 4: OAuth Flow Testing

### 4.1 Initiate OAuth Flow

1. **Get Authorization URL:**
   ```bash
   GET /api/auth/salesforce/authorize?user_id=your_user_id
   ```

2. **Redirect User to Salesforce:**
   Users will be redirected to Salesforce for authentication and authorization.

3. **Handle Callback:**
   Salesforce will redirect back to your callback URL with an authorization code.

### 4.2 Token Management

The system automatically handles:
- Token storage and encryption
- Token refresh (before expiration)
- Token revocation
- Secure token lifecycle management

## Step 5: API Endpoints

### 5.1 Core CRM Operations

**Contacts:**
```bash
# List contacts
GET /api/salesforce/contacts?user_id=your_user_id

# Create contact
POST /api/salesforce/contacts
{
  "user_id": "your_user_id",
  "LastName": "Doe",
  "FirstName": "John",
  "Email": "john.doe@example.com"
}
```

**Accounts:**
```bash
# List accounts
GET /api/salesforce/accounts?user_id=your_user_id

# Create account
POST /api/salesforce/accounts
{
  "user_id": "your_user_id",
  "Name": "Acme Corporation"
}
```

**Opportunities:**
```bash
# List opportunities
GET /api/salesforce/opportunities?user_id=your_user_id

# Create opportunity
POST /api/salesforce/opportunities
{
  "user_id": "your_user_id",
  "Name": "Enterprise Deal",
  "StageName": "Prospecting",
  "CloseDate": "2024-12-31",
  "Amount": 50000
}
```

### 5.2 Enhanced API Features

**Sales Analytics:**
```bash
# Get sales pipeline analytics
GET /api/salesforce/enhanced/pipeline?user_id=your_user_id

# Get leads analytics
GET /api/salesforce/enhanced/leads?user_id=your_user_id
```

**Custom SOQL Queries:**
```bash
# Execute custom SOQL query
POST /api/salesforce/enhanced/query
{
  "user_id": "your_user_id",
  "query": "SELECT Id, Name, StageName FROM Opportunity WHERE StageName = 'Closed Won'"
}
```

## Step 6: Desktop App Integration

### 6.1 TypeScript Skills

The desktop app includes Salesforce skills in:
```typescript
src/skills/salesforceSkills.ts
```

Available functions:
- `listSalesforceContacts(userId)`
- `listSalesforceAccounts(userId)`
- `listSalesforceOpportunities(userId)`
- `createSalesforceContact(userId, lastName, firstName, email)`
- `createSalesforceAccount(userId, name)`
- `createSalesforceOpportunity(userId, name, stageName, closeDate, amount)`

### 6.2 Chat Commands

Users can interact with Salesforce via natural language:
- "Show me my Salesforce contacts"
- "Create a new account in Salesforce"
- "What's my sales pipeline status?"
- "List all open opportunities"

## Step 7: Troubleshooting

### 7.1 Common Issues

**OAuth Configuration Errors:**
- Verify callback URL matches exactly
- Check client ID and secret
- Ensure OAuth scopes are properly configured

**API Connection Issues:**
- Verify Salesforce instance URL
- Check API version compatibility
- Validate user permissions in Salesforce

**Token Management Issues:**
- Check token expiration times
- Verify refresh token availability
- Ensure database connectivity

### 7.2 Debug Endpoints

Use these endpoints for debugging:

```bash
# Check OAuth configuration
GET /api/salesforce/health

# Verify token status
GET /api/salesforce/health/tokens?user_id=your_user_id

# Test API connectivity
GET /api/salesforce/health/connection?user_id=your_user_id
```

### 7.3 Logs and Monitoring

Check application logs for:
- OAuth flow errors
- API rate limiting
- Token refresh failures
- Database connection issues

## Step 8: Security Best Practices

### 8.1 Token Security
- Tokens are encrypted at rest
- Automatic token refresh before expiration
- Secure token revocation
- Session timeout management

### 8.2 API Security
- Rate limiting on all endpoints
- Input validation and sanitization
- Secure error handling (no sensitive data exposure)
- CORS configuration for web clients

### 8.3 Data Protection
- GDPR-compliant data handling
- User consent for data access
- Secure data transmission (HTTPS/TLS)
- Regular security audits

## Step 9: Performance Optimization

### 9.1 Caching Strategy
- Implement response caching for frequently accessed data
- Use ETags for conditional requests
- Cache SOQL query results where appropriate

### 9.2 API Limits
- Monitor Salesforce API usage limits
- Implement bulk operations for large datasets
- Use efficient SOQL queries with selective fields

## Step 10: Production Deployment

### 10.1 Pre-Deployment Checklist
- [ ] OAuth credentials configured
- [ ] Database tables created
- [ ] Health endpoints responding
- [ ] Error handling tested
- [ ] Security review completed
- [ ] Performance testing completed

### 10.2 Monitoring Setup
- Configure health check monitoring
- Set up alerts for OAuth failures
- Monitor API rate limits
- Track integration usage metrics

## Support

For assistance with Salesforce integration:
1. Check application logs for detailed error information
2. Verify Salesforce connected app configuration
3. Test OAuth flow independently
4. Contact development team with specific error codes

---

**Last Updated**: 2024-11-01  
**Integration Version**: 1.0  
**Salesforce API Version**: 57.0