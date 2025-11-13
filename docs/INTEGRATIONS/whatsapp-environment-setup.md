# WhatsApp Business Integration Environment Configuration

## Environment Variables

Copy the following configuration to your `.env` file or environment settings:

### Core API Configuration
```bash
# Environment Setting
ENVIRONMENT=development

# WhatsApp Business API - Development
WHATSAPP_ACCESS_TOKEN_DEV=your_dev_access_token_here
WHATSAPP_PHONE_NUMBER_ID_DEV=your_dev_phone_number_id_here
WHATSAPP_WEBHOOK_VERIFY_TOKEN_DEV=your_custom_webhook_verify_token_dev
WHATSAPP_WEBHOOK_URL_DEV=http://localhost:5058/api/whatsapp/webhook

# WhatsApp Business API - Staging
WHATSAPP_ACCESS_TOKEN_STAGING=your_staging_access_token_here
WHATSAPP_PHONE_NUMBER_ID_STAGING=your_staging_phone_number_id_here
WHATSAPP_WEBHOOK_VERIFY_TOKEN_STAGING=your_custom_webhook_verify_token_staging
WHATSAPP_WEBHOOK_URL_STAGING=https://staging.your-domain.com/api/whatsapp/webhook

# WhatsApp Business API - Production
WHATSAPP_ACCESS_TOKEN_PRODUCTION=your_production_access_token_here
WHATSAPP_PHONE_NUMBER_ID_PRODUCTION=your_production_phone_number_id_here
WHATSAPP_WEBHOOK_VERIFY_TOKEN_PRODUCTION=your_custom_webhook_verify_token_production
WHATSAPP_WEBHOOK_URL_PRODUCTION=https://your-domain.com/api/whatsapp/webhook
```

### Business Profile Configuration
```bash
# Business Profile
WHATSAPP_BUSINESS_NAME=ATOM AI Assistant
WHATSAPP_BUSINESS_DESCRIPTION=AI-powered business automation platform
WHATSAPP_BUSINESS_EMAIL=support@atom.ai
WHATSAPP_BUSINESS_WEBSITE=https://atom.ai
WHATSAPP_BUSINESS_ADDRESS=123 Tech Street, Silicon Valley, CA 94000
WHATSAPP_BUSINESS_PHONE=+1-555-ATM-0000
```

### Feature Configuration
```bash
# Auto Reply
WHATSAPP_AUTO_REPLY_ENABLED=false

# Business Hours
WHATSAPP_BUSINESS_HOURS_ENABLED=true
WHATSAPP_BUSINESS_HOURS_START=09:00
WHATSAPP_BUSINESS_HOURS_END=18:00

# Data Retention
WHATSAPP_MESSAGE_RETENTION_DAYS=30

# Rate Limiting
WHATSAPP_RATE_LIMITING_ENABLED=true
WHATSAPP_MESSAGES_PER_SECOND=50
WHATSAPP_MESSAGES_PER_MINUTE=1000
WHATSAPP_MESSAGES_PER_HOUR=10000
WHATSAPP_API_CALLS_PER_HOUR=1000
```

### Security & Monitoring
```bash
# Webhook Security
WHATSAPP_WEBHOOK_SECURITY_ENABLED=true

# Analytics Tracking
WHATSAPP_ANALYTICS_TRACKING_ENABLED=true

# Health Monitoring
WHATSAPP_HEALTH_CHECK_INTERVAL=60
WHATSAPP_MAX_CONSECUTIVE_FAILURES=5

# Alert Webhook (Optional)
WHATSAPP_ALERT_WEBHOOK=https://your-alert-endpoint.com/webhook
```

### Database Configuration
```bash
# Database Settings
DATABASE_HOST=localhost
DATABASE_NAME=atom_development
DATABASE_USER=postgres
DATABASE_PASSWORD=your_database_password
DATABASE_PORT=5432
```

## Setup Instructions

### 1. Get WhatsApp Business API Credentials

1. **Create Meta Business Account**
   - Go to [Meta Business Suite](https://business.facebook.com/)
   - Create or connect your business account

2. **Set Up WhatsApp Business API**
   - Navigate to [Meta for Developers](https://developers.facebook.com/)
   - Create new app → Business → WhatsApp
   - Add phone number and complete verification

3. **Get API Credentials**
   - Access Token: App Dashboard → WhatsApp → API Configuration
   - Phone Number ID: WhatsApp → Phone Numbers → Select number → Details
   - Webhook URL: Configure in your WhatsApp Business settings

### 2. Configure Environment

1. **Development Environment**
   ```bash
   # Copy to .env.local or .env.dev
   ENVIRONMENT=development
   WHATSAPP_ACCESS_TOKEN_DEV=EAAJZC... (your 200+ character token)
   WHATSAPP_PHONE_NUMBER_ID_DEV=123456789012345
   WHATSAPP_WEBHOOK_VERIFY_TOKEN_DEV=your_custom_token_dev
   ```

2. **Production Environment**
   ```bash
   # Copy to .env.production
   ENVIRONMENT=production
   WHATSAPP_ACCESS_TOKEN_PRODUCTION=EAAJZC... (your production token)
   WHATSAPP_PHONE_NUMBER_ID_PRODUCTION=987654321098765
   WHATSAPP_WEBHOOK_VERIFY_TOKEN_PRODUCTION=your_custom_token_prod
   ```

### 3. Database Setup

The WhatsApp integration requires PostgreSQL database tables. These are created automatically when the service initializes:

```sql
-- Tables are auto-created, but for reference:
-- whatsapp_contacts
-- whatsapp_messages  
-- whatsapp_templates
-- whatsapp_conversations
```

### 4. Webhook Configuration

1. **Set Webhook URL**
   ```bash
   # Development
   WHATSAPP_WEBHOOK_URL_DEV=http://localhost:5058/api/whatsapp/webhook
   
   # Production (must use HTTPS)
   WHATSAPP_WEBHOOK_URL_PRODUCTION=https://your-domain.com/api/whatsapp/webhook
   ```

2. **Configure in Meta Business**
   - Go to WhatsApp Manager → Webhooks
   - Set webhook URL
   - Subscribe to message events
   - Verify with your custom token

### 5. Business Hours Configuration

Enable business hours to restrict automated messaging:

```bash
WHATSAPP_BUSINESS_HOURS_ENABLED=true
WHATSAPP_BUSINESS_HOURS_START=09:00
WHATSAPP_BUSINESS_HOURS_END=18:00
```

### 6. Rate Limiting

Configure rate limits to comply with WhatsApp API restrictions:

```bash
# WhatsApp limits: 50 messages/second per phone number
WHATSAPP_MESSAGES_PER_SECOND=50
WHATSAPP_MESSAGES_PER_MINUTE=1000
WHATSAPP_MESSAGES_PER_HOUR=10000
```

## Security Best Practices

### 1. Access Token Security
- Use environment variables (never hardcode tokens)
- Implement token rotation for production
- Use least privilege access for tokens
- Monitor token usage and expiration

### 2. Webhook Security
- Use HTTPS for production webhooks
- Implement custom verification tokens
- Validate incoming webhook signatures
- Rate limit webhook endpoints

### 3. Data Privacy
- Configure appropriate data retention periods
- Implement GDPR compliance for EU customers
- Use encrypted database connections
- Regular security audits

## Testing Configuration

### Test Configuration Loading
```bash
cd backend
python -c "
from integrations.whatsapp_environment_config import get_whatsapp_config_with_validation
import json
result = get_whatsapp_config_with_validation()
print(f'Environment: {result[\"environment\"]}')
print(f'Valid: {result[\"validation\"][\"is_valid\"]}')
"
```

### Test API Connectivity
```bash
# Development
curl -H "Authorization: Bearer $WHATSAPP_ACCESS_TOKEN_DEV" \
     "https://graph.facebook.com/v18.0/me"

# Production  
curl -H "Authorization: Bearer $WHATSAPP_ACCESS_TOKEN_PRODUCTION" \
     "https://graph.facebook.com/v18.0/me"
```

### Test Webhook
```bash
# Test webhook verification (development)
curl "http://localhost:5058/api/whatsapp/webhook?hub.mode=subscribe&hub.verify_token=$WHATSAPP_WEBHOOK_VERIFY_TOKEN_DEV&hub.challenge=test_challenge"

# Production webhook test requires HTTPS and Meta's webhook testing tool
```

## Environment-Specific Settings

### Development Environment
- Local database connection
- HTTP webhook URLs allowed
- Verbose logging enabled
- Test data isolation

### Staging Environment
- Staging database
- HTTPS webhooks required
- Production-like configuration
- Integration testing enabled

### Production Environment
- Production database with backups
- HTTPS webhooks mandatory
- Rate limiting enforced
- Monitoring and alerts enabled
- Log level set to INFO or ERROR

## Troubleshooting

### Common Issues

1. **Access Token Invalid**
   ```bash
   # Check token format and permissions
   curl -H "Authorization: Bearer $WHATSAPP_ACCESS_TOKEN_DEV" \
        "https://graph.facebook.com/v18.0/debug_token?input_token=$WHATSAPP_ACCESS_TOKEN_DEV"
   ```

2. **Webhook Not Receiving Messages**
   ```bash
   # Test webhook connectivity
   ngrok http 5058  # For local development
   # Update webhook URL to use ngrok URL
   ```

3. **Database Connection Issues**
   ```bash
   # Test database connection
   psql -h $DATABASE_HOST -U $DATABASE_USER -d $DATABASE_NAME
   ```

4. **Rate Limit Exceeded**
   ```bash
   # Check current usage
   # Monitor in Meta Business Suite → WhatsApp → API Usage
   ```

### Debug Mode

Enable debug logging for troubleshooting:

```bash
# Add to .env
WHATSAPP_DEBUG_MODE=true
WHATSAPP_LOG_LEVEL=DEBUG
```

### Health Check Endpoints

```bash
# Service health
curl http://localhost:5058/api/whatsapp/service/health

# Service metrics  
curl http://localhost:5058/api/whatsapp/service/metrics
```

## Production Deployment Checklist

- [ ] All required environment variables set
- [ ] HTTPS webhook URLs configured
- [ ] Database backups enabled
- [ ] Rate limiting configured appropriately
- [ ] Monitoring and alerting set up
- [ ] Access tokens have appropriate permissions
- [ ] Data retention policies configured
- [ ] Security audit completed
- [ ] Load testing performed
- [ ] Fallback procedures documented