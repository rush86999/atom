# Enhanced Google, Microsoft, and Dropbox Integration Documentation

## Overview

This document describes the enhanced integrations for Google, Microsoft, and Dropbox services in the ATOM platform. These integrations provide comprehensive API coverage for each service with advanced features including authentication, file operations, search, sharing, and more.

## Architecture

### Frontend (Tauri + React)
- **Location**: `src/ui-shared/integrations/`
- **Skills**: Enhanced skill classes with complete API coverage
- **Type Safety**: Full TypeScript interfaces and types
- **Event Bus**: Real-time event communication
- **Error Handling**: Comprehensive error management
- **Encryption**: Secure token storage with Fernet encryption

### Backend (Python Flask)
- **Location**: `backend/python-api-service/`
- **Services**: Async service classes for each platform
- **API Endpoints**: RESTful API with Flask blueprints
- **Mock Mode**: Development testing without real API keys
- **Database**: Secure token storage with encryption
- **Logging**: Comprehensive logging with structured output

### Key Components

1. **Enhanced Services**: `google_services_enhanced.py`, `microsoft_services_enhanced.py`, `dropbox_services_enhanced.py`
2. **API Handlers**: `google_enhanced_api.py`, `microsoft_enhanced_api.py`, `dropbox_enhanced_api.py`
3. **Frontend Skills**: `googleSkillsEnhanced.ts`, `microsoftSkillsEnhanced.ts`, `dropboxSkillsEnhanced.ts`
4. **Authentication**: Complete OAuth flow handling with token management

## Google Workspace Integration

### Features
- **Calendar**: Event management, recurring events, free/busy, sharing
- **Gmail**: Send, receive, label management, settings
- **Drive**: File operations, folder management, sharing, search
- **User Management**: Profile information, account details

### API Endpoints

#### Calendar
- `POST /api/google/enhanced/calendar/list` - List calendars
- `POST /api/google/enhanced/calendar/create` - Create calendar
- `POST /api/google/enhanced/calendar/events/list` - List events
- `POST /api/google/enhanced/calendar/events/create` - Create event
- `POST /api/google/enhanced/calendar/events/create_recurring` - Create recurring event
- `POST /api/google/enhanced/calendar/free_busy` - Get free/busy information
- `POST /api/google/enhanced/calendar/share` - Share calendar

#### Gmail
- `POST /api/google/enhanced/gmail/messages/list` - List messages
- `POST /api/google/enhanced/gmail/messages/send` - Send message
- `POST /api/google/enhanced/gmail/labels/create` - Create label
- `POST /api/google/enhanced/gmail/settings` - Get settings

#### Drive
- `POST /api/google/enhanced/drive/files/list` - List files
- `POST /api/google/enhanced/drive/folders/create` - Create folder
- `POST /api/google/enhanced/drive/files/upload` - Upload file
- `POST /api/google/enhanced/drive/files/share` - Share file

#### User
- `POST /api/google/enhanced/user/info` - Get user information

### Frontend Usage

```typescript
import { googleCalendarEnhancedSkill, googleGmailEnhancedSkill, googleDriveEnhancedSkill } from './skills/googleSkillsEnhanced';

// Calendar operations
const calendars = await googleCalendarEnhancedSkill.execute({
  action: 'list_calendars'
}, { userId: 'user123' });

const event = await googleCalendarEnhancedSkill.execute({
  action: 'create_event',
  calendarId: 'primary',
  eventData: {
    summary: 'Team Meeting',
    start: { dateTime: '2024-01-01T10:00:00Z' },
    end: { dateTime: '2024-01-01T11:00:00Z' }
  }
}, { userId: 'user123' });

// Gmail operations
const messages = await googleGmailEnhancedSkill.execute({
  action: 'list_messages',
  query: 'is:unread',
  maxResults: 50
}, { userId: 'user123' });

// Drive operations
const files = await googleDriveEnhancedSkill.execute({
  action: 'list_files',
  query: 'name contains "report"'
}, { userId: 'user123' });
```

## Microsoft 365 Integration

### Features
- **Outlook Calendar**: Event management, attendee handling, recurrence
- **Outlook Email**: Send, receive, search, attachments
- **OneDrive**: File operations, folder management, sharing, versioning
- **Teams**: Team management, channel operations, messaging

### API Endpoints

#### Outlook Calendar
- `POST /api/microsoft/enhanced/calendar/list` - List calendars
- `POST /api/microsoft/enhanced/calendar/create` - Create calendar
- `POST /api/microsoft/enhanced/calendar/events/list` - List events
- `POST /api/microsoft/enhanced/calendar/events/create` - Create event

#### Outlook Email
- `POST /api/microsoft/enhanced/email/send` - Send email
- `POST /api/microsoft/enhanced/email/list` - List emails

#### OneDrive
- `POST /api/microsoft/enhanced/onedrive/files/list` - List files
- `POST /api/microsoft/enhanced/onedrive/folders/list` - List folders
- `POST /api/microsoft/enhanced/onedrive/folders/create` - Create folder
- `POST /api/microsoft/enhanced/onedrive/upload` - Upload file
- `POST /api/microsoft/enhanced/onedrive/share` - Share item

#### Teams
- `POST /api/microsoft/enhanced/teams/list` - List teams
- `POST /api/microsoft/enhanced/teams/channels/list` - List channels
- `POST /api/microsoft/enhanced/teams/messages/list` - List messages
- `POST /api/microsoft/enhanced/teams/messages/send` - Send message

### Frontend Usage

```typescript
import { outlookCalendarEnhancedSkill, outlookEmailEnhancedSkill, oneDriveEnhancedSkill, teamsEnhancedSkill } from './skills/microsoftSkillsEnhanced';

// Calendar operations
const calendars = await outlookCalendarEnhancedSkill.execute({
  action: 'list_calendars'
}, { userId: 'user123' });

// Email operations
const email = await outlookEmailEnhancedSkill.execute({
  action: 'send_email',
  toAddresses: ['user@example.com'],
  subject: 'Meeting Update',
  body: 'The meeting has been rescheduled...'
}, { userId: 'user123' });

// OneDrive operations
const files = await oneDriveEnhancedSkill.execute({
  action: 'list_files',
  folderId: 'root'
}, { userId: 'user123' });
```

## Dropbox Integration

### Features
- **File Operations**: Upload, download, delete, move, copy
- **Folder Management**: Create, list, organize
- **Search**: Advanced search across files and folders
- **Sharing**: Create shared links, manage permissions
- **Versioning**: Access file history, restore versions
- **Preview**: Generate file previews
- **Metadata**: Get detailed file information
- **Properties**: Custom file properties
- **Space Usage**: Monitor storage usage

### API Endpoints

#### User
- `POST /api/dropbox/enhanced/user/info` - Get user information

#### File & Folder Operations
- `POST /api/dropbox/enhanced/files/list` - List files and folders
- `POST /api/dropbox/enhanced/folders/list` - List folders
- `POST /api/dropbox/enhanced/folders/create` - Create folder
- `POST /api/dropbox/enhanced/files/upload` - Upload file
- `POST /api/dropbox/enhanced/files/download` - Download file
- `POST /api/dropbox/enhanced/items/delete` - Delete item
- `POST /api/dropbox/enhanced/items/move` - Move item
- `POST /api/dropbox/enhanced/items/copy` - Copy item

#### Search
- `POST /api/dropbox/enhanced/search` - Search files and folders

#### Sharing
- `POST /api/dropbox/enhanced/links/create` - Create shared link

#### Metadata
- `POST /api/dropbox/enhanced/metadata` - Get file metadata

#### Versioning
- `POST /api/dropbox/enhanced/versions/list` - List file versions
- `POST /api/dropbox/enhanced/versions/restore` - Restore file version

#### Preview
- `POST /api/dropbox/enhanced/preview` - Get file preview

#### Space Usage
- `POST /api/dropbox/enhanced/space` - Get space usage

### Frontend Usage

```typescript
import { dropboxEnhancedSkill } from './skills/dropboxSkillsEnhanced';

// List files
const files = await dropboxEnhancedSkill.execute({
  action: 'list_files',
  path: '/Documents',
  recursive: false
}, { userId: 'user123' });

// Upload file
const file = await dropboxEnhancedSkill.execute({
  action: 'upload_file',
  file_content: fileContent,
  file_name: 'document.pdf',
  folder_path: '/Documents'
}, { userId: 'user123' });

// Create shared link
const link = await dropboxEnhancedSkill.execute({
  action: 'create_shared_link',
  path: '/Documents/document.pdf',
  link_settings: {
    requested_visibility: 'public',
    allow_download: true
  }
}, { userId: 'user123' });
```

## Authentication

### OAuth Flow
1. **Authorization**: Generate authorization URL with required scopes
2. **Callback**: Handle OAuth callback with authorization code
3. **Token Exchange**: Exchange code for access and refresh tokens
4. **Token Storage**: Encrypt and store tokens securely
5. **Token Refresh**: Automatically refresh expired tokens

### Token Management
- **Encryption**: Fernet encryption for token storage
- **Database**: Secure token persistence
- **Refresh**: Automatic token refresh
- **Revocation**: Secure token revocation on logout

### Environment Variables

```bash
# Google
GOOGLE_CLIENT_ID=your_google_client_id
GOOGLE_CLIENT_SECRET=your_google_client_secret
GOOGLE_REDIRECT_URI=http://localhost:3000/oauth/google/callback

# Microsoft
MICROSOFT_CLIENT_ID=your_microsoft_client_id
MICROSOFT_CLIENT_SECRET=your_microsoft_client_secret
MICROSOFT_REDIRECT_URI=http://localhost:3000/oauth/microsoft/callback

# Dropbox
DROPBOX_APP_KEY=your_dropbox_app_key
DROPBOX_APP_SECRET=your_dropbox_app_secret
DROPBOX_REDIRECT_URI=http://localhost:3000/oauth/dropbox/callback

# Encryption
ATOM_OAUTH_ENCRYPTION_KEY=your_fernet_encryption_key
```

## Development Setup

### Backend
```bash
cd backend/python-api-service
pip install -r requirements.txt
python enhanced_main_app.py
```

### Frontend
```bash
cd src/ui-shared
npm install
npm run dev
```

### Testing
```bash
# Run enhanced API tests
python test_enhanced_integrations.py

# Run frontend skill tests
npm test skills
```

## Error Handling

### Frontend
- **Try-Catch**: Comprehensive error catching
- **Event Bus**: Error event propagation
- **User Feedback**: Clear error messages
- **Logging**: Structured error logging

### Backend
- **Exception Handling**: Try-catch blocks
- **Error Responses**: Standardized error format
- **Logging**: Detailed error logging
- **Graceful Degradation**: Fallback to mock data

## Mock Mode

For development without real API keys, the integrations support mock mode:

### Backend
- **Automatic Detection**: Detects missing credentials
- **Mock Responses**: Realistic mock data
- **Consistent Interface**: Same API as production

### Frontend
- **Mock Service**: Frontend mock service
- **Development Mode**: Easy development setup
- **Testing**: Comprehensive test coverage

## Performance Optimization

### Caching
- **Token Cache**: In-memory token caching
- **API Response Cache**: Response caching where appropriate
- **File Cache**: Temporary file caching

### Async Operations
- **Non-blocking**: All operations are asynchronous
- **Concurrent**: Multiple concurrent requests
- **Timeouts**: Proper timeout handling

### Rate Limiting
- **API Limits**: Respect API rate limits
- **Backoff**: Exponential backoff for retries
- **Queue**: Request queuing for bulk operations

## Security

### Data Protection
- **Encryption**: All sensitive data encrypted
- **HTTPS**: Secure communication
- **Token Security**: Secure token handling

### Access Control
- **User Scoping**: User-scoped operations
- **Permission Checks**: Verify permissions before actions
- **Audit Trail**: Log all sensitive operations

## Monitoring

### Logging
- **Structured Logging**: JSON format logging
- **Log Levels**: Appropriate log levels
- **Centralized**: Centralized log collection

### Metrics
- **API Metrics**: Request/response metrics
- **Error Metrics**: Error rate tracking
- **Performance Metrics**: Response time tracking

## Future Enhancements

### Planned Features
- **Real-time Updates**: WebSocket real-time updates
- **Batch Operations**: Bulk operation support
- **Advanced Search**: Enhanced search capabilities
- **Analytics**: Usage analytics and insights

### Integrations
- **Additional Services**: More SaaS integrations
- **Custom Integrations**: Custom API integrations
- **Third-party**: Third-party service integration

## Troubleshooting

### Common Issues

1. **Authentication Errors**
   - Check environment variables
   - Verify redirect URIs
   - Check token encryption key

2. **API Rate Limits**
   - Check rate limit status
   - Implement backoff
   - Use batch operations

3. **File Upload Errors**
   - Check file size limits
   - Verify file permissions
   - Check available space

4. **Search Issues**
   - Verify search syntax
   - Check index status
   - Validate permissions

### Debug Mode

Enable debug mode for detailed logging:

```bash
# Backend
export FLASK_DEBUG=1
export LOG_LEVEL=DEBUG

# Frontend
export VITE_DEBUG=true
```

## Conclusion

The enhanced integrations provide comprehensive coverage for Google, Microsoft, and Dropbox services with enterprise-grade features including security, performance optimization, and extensive error handling. The modular architecture allows for easy extension and maintenance while providing a consistent developer experience across all services.

For additional information or support, refer to the project documentation or contact the development team.