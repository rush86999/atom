# Enhanced Google Services Integration

This document provides comprehensive information about the Enhanced Google Services integration in ATOM, including Gmail, Google Calendar, and Google Drive services.

## Overview

The Enhanced Google Services provide advanced integration capabilities for Google Workspace, including:

- **Enhanced Gmail API**: Advanced email management, search, and analytics
- **Enhanced Calendar API**: Comprehensive calendar management, event scheduling, and analytics
- **Google Drive Integration**: File management, search, and collaboration features
- **OAuth Token Management**: Secure token storage and refresh handling
- **Database Integration**: PostgreSQL-based token and data persistence

## Features

### Enhanced Gmail API

#### Core Capabilities
- **Email Management**: List, read, send, and delete emails
- **Advanced Search**: Full-text search with filters and sorting
- **Email Analytics**: Sentiment analysis, thread analysis, and statistics
- **Batch Operations**: Efficient processing of multiple emails
- **Attachment Handling**: Download and manage email attachments
- **Thread Management**: Complete email conversation handling

#### Key Endpoints
- `POST /api/gmail/enhanced/messages/list` - List messages
- `POST /api/gmail/enhanced/messages/get` - Get specific message
- `POST /api/gmail/enhanced/messages/send` - Send message
- `POST /api/gmail/enhanced/messages/search` - Search messages
- `POST /api/gmail/enhanced/threads/get` - Get email thread
- `POST /api/gmail/enhanced/messages/labels` - Manage labels
- `POST /api/gmail/enhanced/attachments/download` - Download attachments
- `POST /api/gmail/enhanced/analytics` - Email analytics

#### Advanced Features
- **Sentiment Analysis**: AI-powered email sentiment detection
- **Auto-Categorization**: Smart email categorization
- **Priority Scoring**: Email importance ranking
- **Response Suggestions**: AI-generated email replies
- **Spam Detection**: Advanced spam filtering

### Enhanced Calendar API

#### Core Capabilities
- **Event Management**: Create, read, update, and delete events
- **Calendar Management**: List and manage multiple calendars
- **Recurring Events**: Support for complex recurring event patterns
- **Free/Busy Lookup**: Real-time availability checking
- **Event Scheduling**: Smart meeting time suggestions
- **Calendar Analytics**: Meeting statistics and insights

#### Key Endpoints
- `POST /api/calendar/enhanced/events/list` - List events
- `POST /api/calendar/enhanced/events/create` - Create event
- `POST /api/calendar/enhanced/events/update` - Update event
- `POST /api/calendar/enhanced/events/delete` - Delete event
- `POST /api/calendar/enhanced/calendars/list` - List calendars
- `POST /api/calendar/enhanced/events/recurring` - Manage recurring events
- `POST /api/calendar/enhanced/freebusy` - Check availability
- `POST /api/calendar/enhanced/events/suggest-time` - Find meeting times
- `POST /api/calendar/enhanced/calendars/share` - Share calendar
- `POST /api/calendar/enhanced/analytics` - Calendar analytics

#### Advanced Features
- **Smart Scheduling**: AI-powered meeting time optimization
- **Conflict Resolution**: Automatic scheduling conflict handling
- **Room Booking**: Integration with Google Meet and conference rooms
- **Event Reminders**: Customizable reminder system
- **Calendar Sync**: Cross-calendar synchronization

### Database Integration

#### OAuth Token Management
- **Secure Storage**: Encrypted token storage in PostgreSQL
- **Automatic Refresh**: Token refresh handling
- **User Mapping**: Multi-user token management
- **Session Management**: Secure session handling

#### Schema
```sql
-- Google OAuth tokens table
CREATE TABLE google_oauth_tokens (
    id SERIAL PRIMARY KEY,
    user_id VARCHAR(255) NOT NULL,
    email VARCHAR(255) NOT NULL,
    access_token TEXT NOT NULL,
    refresh_token TEXT NOT NULL,
    token_type VARCHAR(50) DEFAULT 'Bearer',
    scope TEXT,
    expires_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    workspace_id VARCHAR(255),
    UNIQUE(user_id, email)
);
```

## Installation & Setup

### Prerequisites
- Python 3.8+
- PostgreSQL database
- Google Cloud Project with OAuth 2.0 credentials
- Required Google API scopes

### Environment Variables
```bash
# Google OAuth Configuration
GOOGLE_CLIENT_ID=your_google_client_id
GOOGLE_CLIENT_SECRET=your_google_client_secret
GOOGLE_REDIRECT_URI=http://localhost:3000/oauth/google/callback

# Required API Scopes
GOOGLE_SCOPES=https://www.googleapis.com/auth/gmail.readonly,https://www.googleapis.com/auth/gmail.send,https://www.googleapis.com/auth/calendar,https://www.googleapis.com/auth/calendar.events,https://www.googleapis.com/auth/drive.readonly

# Database Configuration
DB_HOST=localhost
DB_PORT=5432
DB_NAME=atom
DB_USER=postgres
DB_PASSWORD=your_password
```

### Google Cloud Setup
1. Create a Google Cloud Project
2. Enable the following APIs:
   - Gmail API
   - Google Calendar API
   - Google Drive API
3. Create OAuth 2.0 credentials
4. Configure authorized redirect URIs
5. Download and configure client credentials

### Database Setup
```sql
-- Create database (if not exists)
CREATE DATABASE atom;

-- Create the OAuth tokens table
CREATE TABLE google_oauth_tokens (
    id SERIAL PRIMARY KEY,
    user_id VARCHAR(255) NOT NULL,
    email VARCHAR(255) NOT NULL,
    access_token TEXT NOT NULL,
    refresh_token TEXT NOT NULL,
    token_type VARCHAR(50) DEFAULT 'Bearer',
    scope TEXT,
    expires_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    workspace_id VARCHAR(255),
    UNIQUE(user_id, email)
);

-- Create indexes for performance
CREATE INDEX idx_google_oauth_user_id ON google_oauth_tokens(user_id);
CREATE INDEX idx_google_oauth_email ON google_oauth_tokens(email);
CREATE INDEX idx_google_oauth_expires_at ON google_oauth_tokens(expires_at);
```

## API Usage

### Authentication
All API calls require valid Google OAuth tokens. Tokens are automatically managed and refreshed.

```javascript
// Example: Get Gmail messages
const response = await fetch('/api/gmail/enhanced/messages/list', {
  method: 'POST',
  headers: {
    'Content-Type': 'application/json',
  },
  body: JSON.stringify({
    user_id: 'user123',
    query: 'is:unread',
    max_results: 10
  })
});

const data = await response.json();
```

### Example Requests

#### Gmail - List Messages
```json
{
  "user_id": "user123",
  "query": "is:unread",
  "max_results": 10,
  "include_spam": false,
  "include_trash": false
}
```

#### Calendar - Create Event
```json
{
  "user_id": "user123",
  "calendar_id": "primary",
  "event": {
    "summary": "Team Meeting",
    "description": "Weekly team sync",
    "start": {
      "datetime": "2025-11-10T10:00:00Z",
      "timezone": "UTC"
    },
    "end": {
      "datetime": "2025-11-10T11:00:00Z",
      "timezone": "UTC"
    },
    "attendees": [
      {"email": "team@company.com"},
      {"email": "manager@company.com"}
    ],
    "conference_data": {
      "create_request": {
        "request_id": "meeting123"
      }
    }
  }
}
```

## Error Handling

### Common Errors
- `401 Unauthorized`: Invalid or expired OAuth token
- `403 Forbidden`: Insufficient API permissions
- `429 Rate Limited`: Too many API requests
- `500 Server Error`: Internal service error

### Error Response Format
```json
{
  "ok": false,
  "error": {
    "code": "UNAUTHORIZED",
    "message": "Google OAuth token not found or expired",
    "service": "gmail_enhanced"
  }
}
```

## Monitoring & Analytics

### Health Checks
- Service health: `/api/gmail/enhanced/health`
- Token validation: Built-in token health checks
- API rate limiting: Real-time rate limit monitoring

### Analytics Features
- **Email Statistics**: Sent/received counts, response times
- **Calendar Insights**: Meeting frequency, duration analysis
- **Usage Patterns**: Peak usage times, API call patterns
- **Performance Metrics**: Response times, error rates

## Security

### Token Security
- Encrypted token storage
- Automatic token refresh
- Secure token transmission (HTTPS)
- Token expiration handling

### Data Privacy
- User data isolation
- GDPR compliance
- Data retention policies
- Secure data handling

## Troubleshooting

### Common Issues
1. **OAuth Token Errors**: Check token expiration and refresh logic
2. **API Permission Errors**: Verify required scopes are enabled
3. **Database Connection Errors**: Check database configuration
4. **Rate Limiting**: Implement request throttling

### Debug Mode
Enable debug logging for detailed error information:
```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

## Development

### Local Development
1. Set up local PostgreSQL database
2. Configure environment variables
3. Create Google Cloud test project
4. Run database migrations
5. Start development server

### Testing
```bash
# Run unit tests
python -m pytest tests/gmail_enhanced/

# Run integration tests
python -m pytest tests/integration/google_services/

# Run all tests
python -m pytest tests/
```

### Contributing
1. Fork the repository
2. Create feature branch
3. Add tests for new functionality
4. Ensure all tests pass
5. Submit pull request

## Support

### Documentation
- [API Reference](./API_REFERENCE.md)
- [Database Schema](./DATABASE_SCHEMA.md)
- [OAuth Guide](./OAUTH_SETUP.md)

### Contact
- Technical Support: support@atom.com
- Development Team: dev@atom.com
- Issues: GitHub Issues

## Version History

### v1.0.0 (2025-11-05)
- Initial release of Enhanced Gmail API
- Enhanced Calendar API with advanced features
- Database integration for OAuth token management
- Comprehensive error handling and logging
- Health check endpoints
- Analytics and monitoring capabilities

### Upcoming Features
- Google Drive enhanced integration
- Advanced AI-powered features
- Real-time notifications
- Mobile app integration
- Enterprise SSO integration

---

For more detailed information, please refer to the individual API documentation files or contact the development team.