# Salesforce Integration Guide

## Overview

The Salesforce integration provides comprehensive CRM capabilities within the ATOM platform. This integration enables account management, contact administration, opportunity tracking, lead management, and sales analytics using Salesforce's REST API and OAuth 2.0 authentication.

## Features

- 🔐 **OAuth 2.0 Authentication** - Secure connection to Salesforce API
- 🏢 **Account Management** - Create, view, and manage company accounts
- 👥 **Contact Administration** - Manage customer and prospect contacts
- 💼 **Opportunity Tracking** - Track sales opportunities and pipeline
- 📈 **Lead Management** - Capture and qualify sales leads
- 📊 **Sales Analytics** - Pipeline analytics and performance metrics
- 🔍 **Advanced Search** - Search across all Salesforce objects
- 🛠️ **API Integration** - Full access to Salesforce REST API

## Architecture

### Backend Components

1. **Salesforce Routes** (`/api/salesforce/*`) - FastAPI endpoints for CRM functionality
2. **Authentication Handler** - OAuth 2.0 token management
3. **Integration Service** - Core Salesforce API integration logic
4. **Data Transformation** - Salesforce object mapping and processing

### Frontend Components

1. **SalesforceIntegration Component** - Main integration interface
2. **Account Management** - Company account management interface
3. **Contact Administration** - Contact management and organization
4. **Opportunity Dashboard** - Sales pipeline visualization
5. **Analytics Dashboard** - Performance metrics and insights

## Setup Instructions

### 1. Prerequisites

- Salesforce Developer Account with Connected App
- OAuth 2.0 credentials configured
- ATOM backend service running
- Salesforce API access enabled

### 2. Backend Configuration

#### Environment Variables

Add the following to your `.env` file:

```bash
# Salesforce OAuth Configuration
SALESFORCE_CLIENT_ID=your_salesforce_client_id
SALESFORCE_CLIENT_SECRET=your_salesforce_client_secret
SALESFORCE_REDIRECT_URI=http://localhost:5058/api/auth/salesforce/callback
SALESFORCE_INSTANCE_URL=https://your-instance.salesforce.com

# Optional: Additional configuration
SALESFORCE_API_VERSION=v59.0
SALESFORCE_USERNAME=your_username
SALESFORCE_PASSWORD=your_password_with_token
```

#### Salesforce Connected App Setup

1. Go to [Salesforce Setup](https://login.salesforce.com/)
2. Navigate to **Setup** → **App Manager**
3. Create a new **Connected App**
4. Configure the following:

**Basic Information:**
- Connected App Name: ATOM Integration
- API Name: ATOM_Integration
- Contact Email: your-email@company.com

**API (Enable OAuth Settings):**
- Enable OAuth Settings: ✅
- Callback URL: `http://localhost:5058/api/auth/salesforce/callback`
- Selected OAuth Scopes:
  - Access and manage your data (api)
  - Perform requests on your behalf at any time (refresh_token, offline_access)
  - Provide access to your data via the Web (web)

**Required Permissions:**
- API Enabled
- Access to REST API
- OAuth 2.0 enabled

### 3. API Endpoints

#### Authentication Endpoints
- `POST /api/salesforce/auth/callback` - Handle OAuth callback
- `POST /api/salesforce/auth/disconnect` - Disconnect integration
- `GET /api/salesforce/connection-status` - Check connection status

#### Account Management
- `GET /api/salesforce/accounts` - List accounts
- `POST /api/salesforce/accounts` - Create account
- `GET /api/salesforce/accounts/{account_id}` - Get account details
- `PUT /api/salesforce/accounts/{account_id}` - Update account
- `DELETE /api/salesforce/accounts/{account_id}` - Delete account

#### Contact Management
- `GET /api/salesforce/contacts` - List contacts
- `POST /api/salesforce/contacts` - Create contact
- `GET /api/salesforce/contacts/{contact_id}` - Get contact details
- `PUT /api/salesforce/contacts/{contact_id}` - Update contact
- `DELETE /api/salesforce/contacts/{contact_id}` - Delete contact

#### Opportunity Management
- `GET /api/salesforce/opportunities` - List opportunities
- `POST /api/salesforce/opportunities` - Create opportunity
- `GET /api/salesforce/opportunities/{opportunity_id}` - Get opportunity details
- `PUT /api/salesforce/opportunities/{opportunity_id}` - Update opportunity
- `DELETE /api/salesforce/opportunities/{opportunity_id}` - Delete opportunity

#### Lead Management
- `GET /api/salesforce/leads` - List leads
- `POST /api/salesforce/leads` - Create lead
- `GET /api/salesforce/leads/{lead_id}` - Get lead details
- `PUT /api/salesforce/leads/{lead_id}` - Update lead
- `DELETE /api/salesforce/leads/{lead_id}` - Delete lead

#### Analytics & Search
- `GET /api/salesforce/analytics/pipeline` - Get pipeline analytics
- `GET /api/salesforce/analytics/leads` - Get lead analytics
- `GET /api/salesforce/search` - Search Salesforce data

#### Health & Configuration
- `GET /api/salesforce/health` - Health check
- `GET /api/salesforce/config` - Integration configuration

## Usage Examples

### Creating an Account

```javascript
const accountData = {
  name: "ACME Corporation",
  type: "Customer",
  industry: "Technology",
  phone: "+1-555-0123",
  website: "https://acme.com",
  annual_revenue: 5000000,
  description: "Enterprise technology solutions provider"
};

const response = await fetch('/api/salesforce/accounts', {
  method: 'POST',
  headers: {
    'Content-Type': 'application/json',
  },
  body: JSON.stringify(accountData)
});
```

### Creating an Opportunity

```javascript
const opportunityData = {
  name: "Enterprise Software License",
  account_id: "0015e00000A1B2C3D",
  stage: "Proposal",
  amount: 150000,
  close_date: "2024-03-31",
  probability: 75,
  description: "Enterprise software license renewal"
};

const response = await fetch('/api/salesforce/opportunities', {
  method: 'POST',
  headers: {
    'Content-Type': 'application/json',
  },
  body: JSON.stringify(opportunityData)
});
```

### Searching Salesforce

```javascript
const searchQuery = "ACME Corporation";
const response = await fetch(`/api/salesforce/search?q=${encodeURIComponent(searchQuery)}`);
const results = await response.json();
```

## Frontend Integration

### Component Structure

```typescript
interface SalesforceAccount {
  id: string;
  name: string;
  type?: string;
  industry?: string;
  phone?: string;
  website?: string;
  annual_revenue?: number;
  description?: string;
  created_date?: string;
  last_modified_date?: string;
}

interface SalesforceContact {
  id: string;
  name: string;
  account_id?: string;
  account_name?: string;
  email?: string;
  phone?: string;
  title?: string;
  department?: string;
  created_date?: string;
  last_modified_date?: string;
}

interface SalesforceOpportunity {
  id: string;
  name: string;
  account_id?: string;
  account_name?: string;
  stage: string;
  amount?: number;
  close_date?: string;
  probability?: number;
  description?: string;
  created_date?: string;
  last_modified_date?: string;
}

interface SalesforceLead {
  id: string;
  name: string;
  company?: string;
  email?: string;
  phone?: string;
  status?: string;
  rating?: string;
  source?: string;
  created_date?: string;
  last_modified_date?: string;
}
```

### Key Features

1. **Account Dashboard**
   - View all company accounts
   - Create new accounts
   - Account type and industry filtering
   - Revenue tracking and reporting

2. **Contact Management**
   - Browse organization contacts
   - Contact details and relationships
   - Email and phone integration
   - Department and title information

3. **Opportunity Tracking**
   - Sales pipeline visualization
   - Stage progression tracking
   - Deal amount and probability
   - Close date management

4. **Lead Management**
   - Lead capture and qualification
   - Status and rating tracking
   - Source attribution
   - Conversion tracking

5. **Analytics**
   - Pipeline total and win rate
   - Opportunity stage distribution
   - Lead source analysis
   - Performance metrics

## Security Considerations

### OAuth Security
- Use secure token storage with encryption
- Implement token refresh mechanisms
- Validate redirect URIs
- Use state parameter for CSRF protection

### API Security
- Validate all API requests
- Implement rate limiting
- Use HTTPS for all communications
- Regular security audits

### Data Protection
- Encrypt sensitive customer data
- Implement access controls
- GDPR compliance for EU customers
- Data retention policies

## Troubleshooting

### Common Issues

1. **Authentication Failures**
   - Verify OAuth credentials
   - Check redirect URI configuration
   - Ensure proper API permissions
   - Validate security token

2. **API Rate Limits**
   - Salesforce has strict API limits
   - Implement request throttling
   - Use bulk API for large operations
   - Monitor API usage

3. **Data Access Issues**
   - Check user permissions in Salesforce
   - Verify object and field-level security
   - Ensure proper sharing rules
   - Check organization-wide defaults

### Debugging Tips

1. Enable detailed logging
2. Test with Salesforce sandbox environment
3. Use Salesforce's API workbench for testing
4. Monitor network requests and responses
5. Check Salesforce debug logs

## Performance Optimization

### Caching Strategies
- Cache account and contact lists
- Implement request deduplication
- Use appropriate cache TTLs
- Cache frequently accessed metadata

### API Optimization
- Use composite requests for multiple operations
- Implement pagination for large datasets
- Use selective field queries
- Batch operations where possible

### Data Synchronization
- Implement incremental sync
- Use change data capture (CDC)
- Handle deleted records
- Conflict resolution strategies

## Monitoring & Metrics

### Key Metrics to Track
- API response times
- OAuth token refresh success rate
- Data synchronization success rate
- Error rates by operation type
- User engagement metrics

### Health Checks
- Regular connection status checks
- API endpoint availability
- Token validity monitoring
- Data consistency validation

## Production Deployment

### Environment Setup
1. Configure production Connected App
2. Set up SSL certificates
3. Configure production redirect URIs
4. Update environment variables
5. Set up monitoring and alerting

### Scaling Considerations
- Horizontal scaling for API requests
- Database optimization for CRM data
- Load balancing for high availability
- CDN for static assets

## Support & Resources

### Documentation
- [Salesforce REST API Documentation](https://developer.salesforce.com/docs/atlas.en-us.api_rest.meta/api_rest/)
- [OAuth 2.0 Guide](https://help.salesforce.com/s/articleView?id=sf.remoteaccess_oauth_web_server_flow.htm)
- [Apex Developer Guide](https://developer.salesforce.com/docs/atlas.en-us.apexcode.meta/apexcode/)

### Support Channels
- Salesforce Developer Support
- ATOM Integration Team
- Community Forums
- Stack Exchange Salesforce

## Version History

### v1.0.0 (Current)
- Initial Salesforce integration
- Account, Contact, Opportunity, Lead management
- Sales analytics and pipeline tracking
- Advanced search capabilities
- OAuth 2.0 authentication

### Planned Features
- Custom object support
- Advanced reporting and dashboards
- Workflow automation integration
- Real-time event processing
- Mobile optimization

---

**Last Updated**: 2024-01-15  
**Integration Version**: 1.0.0  
**Salesforce API Version**: v59.0  
**Status**: Production Ready