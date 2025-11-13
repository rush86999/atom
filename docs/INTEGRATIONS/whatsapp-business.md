# WhatsApp Business Integration Documentation

## Overview

The WhatsApp Business integration provides comprehensive API access to WhatsApp Business Platform, enabling businesses to communicate with customers through the world's most popular messaging platform. This integration supports text messages, media sharing, template messages, customer support automation, and advanced analytics.

## Features

### Core Messaging
- **Send/Receive Messages**: Full bidirectional messaging support
- **Media Messages**: Support for images, audio, video, and documents
- **Template Messages**: Pre-approved templates for business communications
- **Interactive Messages**: Buttons, lists, and product catalogs
- **Message History**: Complete conversation tracking and storage

### Automation Capabilities
- **Customer Support**: Auto-responders, ticket creation, escalation rules
- **Appointment Reminders**: Automated scheduling reminders
- **Marketing Campaigns**: Targeted promotional message campaigns
- **Follow-up Sequences**: Automated follow-up based on customer interactions

### Analytics & Reporting
- **Message Statistics**: Detailed metrics on sent/received messages
- **Conversation Analytics**: Engagement and response time metrics
- **Customer Growth Tracking**: New contact acquisition and retention
- **Performance Monitoring**: Real-time status and health checks

## Setup Instructions

### 1. Prerequisites
- Active Meta Business Account
- WhatsApp Business Account (connected to Meta Business)
- Verified phone number for WhatsApp Business
- Facebook Developer account

### 2. API Configuration
1. **Create WhatsApp Business App**
   - Go to [Meta for Developers](https://developers.facebook.com/)
   - Create new app → Business → WhatsApp
   - Add phone number and complete verification

2. **Get API Credentials**
   - Access Token from App Dashboard
   - Phone Number ID from WhatsApp settings
   - Webhook verification token

3. **Configure Webhook**
   - Set webhook URL: `https://your-domain.com/api/whatsapp/webhook`
   - Subscribe to message events
   - Verify webhook with custom token

### 3. Environment Variables
```bash
# WhatsApp Business API Configuration
WHATSAPP_ACCESS_TOKEN=your_access_token_here
WHATSAPP_PHONE_NUMBER_ID=your_phone_number_id
WHATSAPP_WEBHOOK_VERIFY_TOKEN=your_custom_webhook_token
WHATSAPP_WEBHOOK_URL=https://your-domain.com/api/whatsapp/webhook
```

## API Endpoints

### Health & Status
```http
GET /api/whatsapp/health
```
Check integration health status and connectivity.

### Messaging
```http
POST /api/whatsapp/send
```
Send a message to a WhatsApp contact.

**Request Body:**
```json
{
  "to": "+1234567890",
  "type": "text|template|media|interactive",
  "content": {
    "body": "Message content" // Varies by type
  }
}
```

### Conversations
```http
GET /api/whatsapp/conversations?limit=50&offset=0
```
Retrieve list of conversations with pagination.

### Messages
```http
GET /api/whatsapp/messages/{whatsapp_id}?limit=100
```
Get message history for a specific contact.

### Templates
```http
POST /api/whatsapp/templates
```
Create a message template.

**Request Body:**
```json
{
  "template_name": "appointment_reminder",
  "category": "UTILITY|MARKETING|AUTHENTICATION",
  "language_code": "en",
  "components": [
    {
      "type": "body",
      "text": "Hello {{1}}, your appointment is scheduled for {{2}}."
    }
  ]
}
```

### Analytics
```http
GET /api/whatsapp/analytics?start_date=2024-01-01&end_date=2024-01-31
```
Get comprehensive analytics and metrics.

### Webhook
```http
POST /api/whatsapp/webhook
GET /api/whatsapp/webhook?hub.mode=subscribe&hub.verify_token=your_token
```
Handle incoming messages and webhook verification.

## Message Types

### Text Messages
```json
{
  "to": "+1234567890",
  "type": "text",
  "content": {
    "body": "Hello! How can we help you today?"
  }
}
```

### Template Messages
```json
{
  "to": "+1234567890",
  "type": "template",
  "content": {
    "name": "appointment_reminder",
    "language": {
      "code": "en"
    },
    "components": [
      {
        "type": "body",
        "parameters": [
          {
            "type": "text",
            "text": "John"
          },
          {
            "type": "text",
            "text": "January 15 at 2:00 PM"
          }
        ]
      }
    ]
  }
}
```

### Media Messages
```json
{
  "to": "+1234567890",
  "type": "image",
  "content": {
    "media_id": "media_id_here",
    "caption": "Product image"
  }
}
```

### Interactive Messages
```json
{
  "to": "+1234567890",
  "type": "interactive",
  "content": {
    "type": "button",
    "body": {
      "text": "Would you like to schedule an appointment?"
    },
    "action": {
      "buttons": [
        {
          "type": "reply",
          "reply": {
            "id": "yes",
            "title": "Yes"
          }
        },
        {
          "type": "reply",
          "reply": {
            "id": "no",
            "title": "No"
          }
        }
      ]
    }
  }
}
```

## Workflow Automation

### Customer Support Automation
```http
POST /workflows/whatsapp/automate
```

**Request:**
```json
{
  "type": "customer_support",
  "parameters": {
    "trigger_keywords": ["help", "support", "issue"],
    "auto_response": "Thank you for reaching out! Our support team will respond shortly.",
    "escalate_conditions": ["urgent", "emergency"]
  }
}
```

### Appointment Reminders
```json
{
  "type": "appointment_reminder",
  "parameters": {
    "reminder_intervals": [24, 2, 0.5],
    "template_name": "appointment_reminder"
  }
}
```

### Marketing Campaigns
```json
{
  "type": "marketing_campaign",
  "parameters": {
    "campaign_type": "promotion",
    "target_audience": "all_customers",
    "message_template": "special_offer"
  }
}
```

## Database Schema

### WhatsApp Contacts
```sql
CREATE TABLE whatsapp_contacts (
    id SERIAL PRIMARY KEY,
    whatsapp_id VARCHAR(50) UNIQUE NOT NULL,
    name VARCHAR(255),
    phone_number VARCHAR(20),
    profile_picture_url TEXT,
    about TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

### WhatsApp Messages
```sql
CREATE TABLE whatsapp_messages (
    id SERIAL PRIMARY KEY,
    message_id VARCHAR(100) UNIQUE NOT NULL,
    whatsapp_id VARCHAR(50) NOT NULL,
    message_type VARCHAR(20) NOT NULL,
    content JSONB NOT NULL,
    direction VARCHAR(10) NOT NULL,
    status VARCHAR(20) DEFAULT 'sent',
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (whatsapp_id) REFERENCES whatsapp_contacts(whatsapp_id)
);
```

### WhatsApp Templates
```sql
CREATE TABLE whatsapp_templates (
    id SERIAL PRIMARY KEY,
    template_name VARCHAR(100) NOT NULL,
    category VARCHAR(50) NOT NULL,
    language_code VARCHAR(10) NOT NULL,
    components JSONB NOT NULL,
    status VARCHAR(20) DEFAULT 'active',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

### WhatsApp Conversations
```sql
CREATE TABLE whatsapp_conversations (
    id SERIAL PRIMARY KEY,
    conversation_id VARCHAR(100) UNIQUE NOT NULL,
    whatsapp_id VARCHAR(50) NOT NULL,
    status VARCHAR(20) DEFAULT 'active',
    last_message_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    metadata JSONB,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (whatsapp_id) REFERENCES whatsapp_contacts(whatsapp_id)
);
```

## Error Handling

### Common Error Codes
- `400` - Invalid request parameters
- `401` - Invalid or expired access token
- `403` - Insufficient permissions
- `404` - Resource not found
- `429` - Rate limit exceeded
- `500` - Internal server error

### Error Response Format
```json
{
  "success": false,
  "error": "Error description",
  "error_code": "ERROR_CODE",
  "details": {
    "field": "validation_error"
  }
}
```

## Rate Limits

- **Messages**: 50 messages per second per phone number
- **Template Creation**: 10 templates per hour
- **API Calls**: 1000 calls per hour per app
- **Media Upload**: 100MB per file, 100 files per hour

## Security Considerations

### Authentication
- Use HTTPS for all API calls
- Securely store access tokens
- Implement token rotation
- Use webhook verification tokens

### Data Privacy
- GDPR compliance for EU customers
- Message encryption in transit and at rest
- User consent management
- Data retention policies

### Best Practices
- Validate all incoming webhooks
- Implement proper logging and monitoring
- Use environment variables for sensitive data
- Regular security audits

## Integration Examples

### React Component Usage
```tsx
import WhatsAppBusinessIntegration from './components/integrations/WhatsAppBusinessIntegration';

function App() {
  return (
    <div>
      <WhatsAppBusinessIntegration />
    </div>
  );
}
```

### Python Backend Integration
```python
from integrations.whatsapp_business_integration import WhatsAppBusinessIntegration

# Initialize integration
whatsapp = WhatsAppBusinessIntegration()
whatsapp.initialize({
    'access_token': 'your_token',
    'phone_number_id': 'your_phone_id',
    'webhook_verify_token': 'your_verify_token'
})

# Send message
result = whatsapp.send_message(
    to='+1234567890',
    message_type='text',
    content={'body': 'Hello from ATOM!'}
)
```

### Workflow Integration
```python
from integrations.workflow_automation_routes import _handle_customer_support_automation

# Setup customer support automation
result = await _handle_customer_support_automation({
    'trigger_keywords': ['help', 'support'],
    'auto_response': 'Our team will respond shortly.',
    'escalate_conditions': ['urgent', 'emergency']
})
```

## Troubleshooting

### Common Issues

1. **Webhook Not Receiving Messages**
   - Check webhook URL accessibility
   - Verify webhook subscription in Meta Business
   - Confirm webhook verification token

2. **Template Not Approved**
   - Check template compliance with WhatsApp policies
   - Ensure proper category selection
   - Wait 1-2 business days for approval

3. **Rate Limit Exceeded**
   - Implement message queuing
   - Use multiple phone numbers if needed
   - Monitor API usage metrics

4. **Authentication Failures**
   - Verify access token validity
   - Check phone number permissions
   - Ensure app is in production mode

### Monitoring

Monitor these key metrics:
- Message delivery rate
- Response time average
- Error rate percentage
- Webhook latency
- Template approval status

## Support

For technical support:
- Check the [Meta Business documentation](https://developers.facebook.com/docs/whatsapp)
- Review API status at [Meta Platform Status](https://developers.facebook.com/status/)
- Contact ATOM support through the platform

## Version History

### v1.0.0 (Current)
- Basic messaging functionality
- Template management
- Conversation tracking
- Analytics dashboard
- Workflow automation

### Planned Features
- Multi-language support
- Advanced analytics
- A/B testing for campaigns
- AI-powered responses
- Enhanced media handling