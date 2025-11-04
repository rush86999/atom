# Outlook Integration Documentation

## Overview

The ATOM Outlook integration provides comprehensive email and calendar automation capabilities through natural language commands and a rich desktop interface.

## Features

### 📧 Email Management
- **Send Emails**: Compose and send emails with recipients, subject, and body
- **Retrieve Emails**: Get recent emails, filter by read status
- **Search Emails**: Find emails using search queries
- **Triage Emails**: Automatic categorization and prioritization

### 📅 Calendar Management
- **Create Events**: Schedule meetings with attendees, location, and details
- **Retrieve Events**: View upcoming calendar events
- **Search Events**: Find specific calendar events
- **Update Events**: Modify existing event details
- **Delete Events**: Remove calendar events

## Installation

### Prerequisites
- ATOM Desktop Application
- Microsoft Outlook/Microsoft 365 Account
- OAuth 2.0 Configuration (see below)

### Setup
1. Open ATOM Desktop App
2. Navigate to **Settings > Integrations**
3. Click **Connect Outlook Account**
4. Complete OAuth flow in browser
5. Grant necessary permissions

## OAuth Configuration

### Required Environment Variables
```bash
# Microsoft OAuth Configuration
OUTLOOK_CLIENT_ID=your_outlook_client_id
OUTLOOK_CLIENT_SECRET=your_outlook_client_secret
OUTLOOK_TENANT_ID=your_outlook_tenant_id  # or 'common'
OUTLOOK_REDIRECT_URI=http://localhost:3000/oauth/outlook/callback
```

### Required Permissions
- `Mail.Read` - Read emails
- `Mail.Send` - Send emails
- `Mail.ReadWrite` - Modify emails
- `Calendars.Read` - Read calendar events
- `Calendars.ReadWrite` - Create and modify events
- `User.Read` - Read user profile
- `offline_access` - Refresh tokens

## Usage

### Natural Language Commands

#### Email Commands
```bash
# Send email
"Send an email to john@example.com with subject 'Meeting Update' and message 'The meeting has been rescheduled to 3 PM'"

# Get emails
"Show me my recent emails"
"Get unread emails"
"Show me 5 recent emails"

# Search emails
"Search emails for 'project update'"
"Find emails from team@company.com"

# Triage emails
"Triage my emails by priority"
"Organize my emails"
```

#### Calendar Commands
```bash
# Create event
"Create a calendar event 'Team Meeting' tomorrow at 2 PM in Conference Room A"
"Schedule a call with client tomorrow at 3 PM"

# Get events
"Show me my upcoming events"
"Display my calendar for this week"
"Get my next 5 events"

# Search events
"Search calendar for 'client meeting'"
"Find events with 'project review'"

# Update event
"Update event 'Team Meeting' to tomorrow at 3 PM"
```

#### Utility Commands
```bash
# Get help
"Outlook help"
"What can I do with Outlook?"

# Check status
"Is Outlook connected?"
"Outlook status"
```

### Quick Action Buttons

The enhanced chat interface provides quick action buttons:
- **📧 Recent Emails**: Retrieve latest emails
- **📅 Calendar Events**: Show upcoming events  
- **❓ Help**: Display help information

## API Reference

### Tauri Commands

#### Email Commands
```typescript
// Send email
await invoke('send_outlook_email', {
  userId: string,
  to: string[],
  subject: string,
  body: string,
  cc?: string[],
  bcc?: string[]
});

// Get emails
await invoke('get_outlook_emails', {
  userId: string,
  limit?: number,
  unread?: boolean
});

// Search emails
await invoke('search_outlook_emails', {
  userId: string,
  query: string,
  limit?: number
});
```

#### Calendar Commands
```typescript
// Create event
await invoke('create_outlook_calendar_event', {
  userId: string,
  subject: string,
  start_time: string,
  end_time: string,
  body?: string,
  location?: string,
  attendees?: string[]
});

// Get events
await invoke('get_outlook_calendar_events', {
  userId: string,
  limit?: number
});

// Update event
await invoke('update_outlook_calendar_event', {
  userId: string,
  eventId: string,
  subject?: string,
  start_time?: string,
  end_time?: string,
  body?: string,
  location?: string,
  attendees?: string[]
});
```

#### OAuth Commands
```typescript
// Check connection
await invoke('check_outlook_tokens', {
  userId: string
});

// Disconnect
await invoke('disconnect_outlook', {
  userId: string
});

// Refresh tokens
await invoke('refresh_outlook_tokens', {
  userId: string,
  refresh_token: string
});
```

## Skills Development

### Creating Custom Outlook Skills

```typescript
import { outlookEmailSkill, SkillExecutionContext } from '../skills/outlookSkills';

class CustomEmailSkill {
  async execute(params: any, context: SkillExecutionContext) {
    // Custom email processing logic
    const emails = await outlookEmailSkill.execute({
      action: 'get',
      limit: 10
    }, context);
    
    // Process emails
    return {
      success: true,
      processedEmails: emails.count
    };
  }
}
```

### Extending NLP Service

```typescript
import { nlpService } from '../services/nlpService';

// Add custom intent patterns
const customPatterns = {
  'outlook_custom_action': [
    /custom.*email.*action/i,
    /email.*custom.*command/i
  ]
};

// Add to existing service
nlpService.addIntentPatterns('outlook_custom_action', customPatterns);
```

## Architecture

### Components

1. **OutlookDesktopManager**: React component for OAuth and UI
2. **OutlookEmailSkill**: Email automation logic
3. **OutlookCalendarSkill**: Calendar automation logic
4. **NLPService**: Natural language processing
5. **TauriCommands**: Desktop app integration
6. **OAuthHandler**: Microsoft Graph OAuth flow

### Data Flow

```
User Input → NLP Service → Skills → Tauri Commands → Microsoft Graph API
                ↓
           Event Bus → UI Updates → User Feedback
```

### Security

- OAuth 2.0 with Microsoft Graph
- Token encryption and secure storage
- Refresh token rotation
- Scope-based permissions
- Connection status monitoring

## Troubleshooting

### Common Issues

#### OAuth Connection Failed
**Problem**: OAuth flow doesn't complete successfully
**Solution**: 
- Verify environment variables
- Check redirect URI configuration
- Ensure correct tenant ID
- Validate OAuth app permissions

#### Emails Not Loading
**Problem**: Email retrieval returns empty results
**Solution**:
- Check token validity
- Verify Mail.Read permissions
- Test Microsoft Graph API connection
- Check user mailbox access

#### Calendar Events Missing
**Problem**: Calendar events not displaying
**Solution**:
- Verify Calendars.Read permissions
- Check user calendar access
- Test timezone configuration
- Validate date parsing

### Debug Mode

Enable debug logging by setting:
```bash
LOG_LEVEL=debug
```

### Log Locations

- **Desktop App**: Console logs in developer tools
- **Tauri Commands**: Rust console output
- **OAuth Flow**: Network logs in browser
- **Microsoft Graph**: Azure portal activity logs

## Performance

### Optimization Tips

1. **Email Retrieval**: Use limits and pagination
2. **Search Queries**: Optimize for specific filters
3. **Event Caching**: Cache calendar events locally
4. **Token Refresh**: Implement background refresh
5. **Batch Operations**: Group multiple operations

### Monitoring

Key metrics to monitor:
- OAuth success rate
- API response times
- Token refresh frequency
- Error rates by operation
- User engagement metrics

## Support

### Documentation Updates
- Feature requests and documentation improvements
- Bug reports and troubleshooting guides
- API reference updates

### Community
- Integration examples and templates
- Best practices and tips
- User-contributed skills

## Changelog

### v1.0.0 (2025-11-02)
- Initial Outlook integration release
- Email send/get/search/triage capabilities
- Calendar create/get/search/update/delete capabilities
- Natural language command processing
- OAuth 2.0 integration with Microsoft Graph
- Enhanced chat interface
- Comprehensive testing suite

### Planned Features
- Email template management
- Calendar event templates
- Email rule automation
- Meeting scheduling assistants
- Integration with other ATOM services

---

*Last updated: November 2, 2025*