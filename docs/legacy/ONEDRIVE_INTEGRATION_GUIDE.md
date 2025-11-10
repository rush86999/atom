# OneDrive Integration Guide

## Overview

The OneDrive integration provides seamless access to your Microsoft OneDrive files within the ATOM platform. This integration enables file browsing, search, document ingestion, and workflow automation with your OneDrive content using Microsoft Graph API.

## Features

- 🔐 **OAuth 2.0 Authentication** - Secure connection to Microsoft OneDrive
- 📁 **File Browser** - Navigate folders and view files with breadcrumb navigation
- 🔍 **Advanced Search** - Search across all OneDrive content
- 📄 **Document Ingestion** - Add files to ATOM's search index
- 🔄 **Real-time Sync** - Keep file listings up to date
- 🛠️ **API Integration** - Full access to Microsoft Graph API

## Setup Instructions

### 1. Prerequisites

- Microsoft Azure App Registration with Microsoft Graph API permissions
- OAuth 2.0 credentials configured
- ATOM backend service running

### 2. Backend Configuration

#### Environment Variables

Add the following to your `.env` file:

```bash
# OneDrive OAuth Configuration
ONEDRIVE_CLIENT_ID=your_azure_client_id
ONEDRIVE_CLIENT_SECRET=your_azure_client_secret
ONEDRIVE_REDIRECT_URI=http://localhost:5058/api/auth/onedrive/callback

# Optional: Access token for direct API access
ONEDRIVE_ACCESS_TOKEN=your_access_token
```

#### Azure App Registration Setup

1. Go to [Azure Portal](https://portal.azure.com/)
2. Navigate to **App Registrations**
3. Create a new app registration or select existing
4. Configure the following:

**Authentication:**
- Platform: Web
- Redirect URIs: `http://localhost:5058/api/auth/onedrive/callback`
- Add your production domain for production deployments

**API Permissions:**
- Microsoft Graph → Delegated Permissions
- `Files.ReadWrite.All` - Read and write user files
- `User.Read` - Read user profile
- `offline_access` - Maintain access to resources

**Certificates & Secrets:**
- Generate a new client secret
- Copy the client ID and secret for environment variables

### 3. Frontend Integration

The OneDrive integration is available through multiple interfaces:

#### Web Interface
- Navigate to `/onedrive` for the full OneDrive interface
- Access via `/integrations/onedrive` for integration-specific view
- Available in Service Management dashboard

#### API Endpoints

All OneDrive endpoints are prefixed with `/api/onedrive`:

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/onedrive/connection-status` | GET | Check connection status |
| `/api/onedrive/list-files` | GET | List files and folders |
| `/api/onedrive/search` | GET | Search OneDrive |
| `/api/onedrive/files/<file_id>` | GET | Get file metadata |
| `/api/onedrive/files/<file_id>/download` | GET | Download file content |
| `/api/onedrive/ingest-document` | POST | Ingest file for search |
| `/api/auth/onedrive/authorize` | GET | Start OAuth flow |
| `/api/auth/onedrive/callback` | GET | OAuth callback handler |
| `/api/auth/onedrive/disconnect` | POST | Disconnect account |
| `/api/onedrive/health` | GET | Health check |

## Usage Guide

### Connecting OneDrive

1. **Navigate to OneDrive Integration**
   - Go to `/onedrive` or find it in the integrations dashboard
   - Click "Connect OneDrive"

2. **OAuth Authorization**
   - You'll be redirected to Microsoft's OAuth consent screen
   - Review the permissions and grant access
   - You'll be redirected back to ATOM

3. **Verification**
   - The connection status should show "Connected"
   - Your Microsoft account email will be displayed

### File Management

#### Browsing Files
- Use the breadcrumb navigation to navigate folders
- Click folders to open them
- Click files to view them in OneDrive (opens in new tab)

#### File Operations
- **Ingest File**: Click the download icon to add file to ATOM's search index
- **Open in OneDrive**: Click the external link icon to open in OneDrive
- **Load More**: Use pagination for large folders

#### Search Capabilities
The integration supports:
- **Full-text search** across file contents
- **Metadata search** (filename, type, date)
- **Folder-specific search**
- **Semantic search** (when combined with ATOM's AI)

### Document Ingestion

When you ingest a OneDrive file:

1. **File Processing**
   - File content is extracted and processed
   - Text is chunked for optimal search
   - Metadata is preserved

2. **Search Integration**
   - File becomes searchable in ATOM
   - Available for AI-powered workflows
   - Integrated with semantic search

3. **Storage**
   - Processed content stored in LanceDB
   - Original files remain in OneDrive
   - No duplication of file storage

## API Reference

### Connection Status

```javascript
// Request
GET /api/onedrive/connection-status

// Response
{
  "is_connected": true,
  "email": "user@example.com",
  "display_name": "John Doe",
  "drive_id": "drive123",
  "drive_type": "business",
  "quota": {
    "used": 1024000000,
    "remaining": 5120000000,
    "total": 6144000000
  }
}
```

### List Files

```javascript
// Request
GET /api/onedrive/list-files?folder_id=root&page_size=100

// Response
{
  "files": [
    {
      "id": "file123",
      "name": "document.docx",
      "mime_type": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
      "is_folder": false,
      "created_time": "2024-01-15T10:30:00Z",
      "modified_time": "2024-01-15T10:30:00Z",
      "web_url": "https://onedrive.live.com/...",
      "size": 1024000,
      "icon": "📄"
    }
  ],
  "next_page_token": "next_page_token"
}
```

### Search Files

```javascript
// Request
GET /api/onedrive/search?q=project&page_size=50

// Response
{
  "files": [
    {
      "id": "file456",
      "name": "project-plan.docx",
      "mime_type": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
      "is_folder": false,
      "modified_time": "2024-01-15T10:30:00Z",
      "web_url": "https://onedrive.live.com/...",
      "size": 2048000,
      "icon": "📄"
    }
  ],
  "next_page_token": "next_page_token",
  "query": "project"
}
```

### Ingest Document

```javascript
// Request
POST /api/onedrive/ingest-document
{
  "file_id": "file123",
  "metadata": {
    "name": "document.docx",
    "mime_type": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "web_url": "https://onedrive.live.com/..."
  }
}

// Response
{
  "status": "success",
  "message": "File 'document.docx' ingested successfully",
  "file_id": "file123",
  "file_name": "document.docx",
  "size": 1024000
}
```

## Supported File Types

The integration supports all OneDrive file types:

| File Type | MIME Type | Ingestion Support |
|-----------|-----------|-------------------|
| Microsoft Word | `application/vnd.openxmlformats-officedocument.wordprocessingml.document` | ✅ Full |
| Microsoft Excel | `application/vnd.openxmlformats-officedocument.spreadsheetml.sheet` | ✅ Full |
| Microsoft PowerPoint | `application/vnd.openxmlformats-officedocument.presentationml.presentation` | ✅ Full |
| PDF Files | `application/pdf` | ✅ Full |
| Text Files | `text/plain` | ✅ Full |
| Images | `image/*` | ⚠️ Limited (metadata only) |
| Videos | `video/*` | ⚠️ Limited (metadata only) |
| Folders | N/A | 🔄 Navigation only |

## Security & Permissions

### OAuth Scopes

The integration requests the following Microsoft Graph scopes:

- `Files.ReadWrite.All` - Read and write user files
- `User.Read` - Read user profile information
- `offline_access` - Maintain access to resources

### Data Handling

- **Read-only operations**: Integration primarily reads files
- **Encrypted storage**: OAuth tokens are encrypted at rest
- **User isolation**: Files are only accessible to the connected user
- **Temporary processing**: File content is processed but not permanently stored

## Troubleshooting

### Common Issues

#### Connection Failures
- **Invalid OAuth credentials**: Verify client ID and secret in Azure Portal
- **Redirect URI mismatch**: Ensure redirect URI matches Azure configuration
- **Permission issues**: User may need admin consent for some permissions

#### File Access Issues
- **Permission denied**: File may not be accessible to the connected account
- **File not found**: File may have been moved or deleted
- **Rate limiting**: Microsoft Graph API quotas may be exceeded

#### Search/Ingestion Issues
- **Unsupported file type**: Some file types cannot be processed
- **Large files**: Files over 25MB may timeout
- **Corrupted files**: Some files may fail to process

### Debug Mode

Enable debug logging by setting:

```bash
LOG_LEVEL=DEBUG
```

This will provide detailed logs for troubleshooting OAuth flows and API calls.

## Performance Considerations

### API Quotas
- Microsoft Graph API has throttling limits
- Consider implementing caching for frequent operations
- Batch operations when possible

### File Size Limits
- Recommended maximum file size: 25MB
- Large files may timeout during processing
- Consider chunking for very large documents

### Caching Strategy
- File listings are cached for 5 minutes
- Metadata is cached for 15 minutes
- Search results are not cached for real-time accuracy

## Development

### Architecture

The OneDrive integration follows the same pattern as other integrations:

1. **Backend Services** (`backend/python-api-service/`)
   - `onedrive_routes.py` - Main file operations and API endpoints
   - `auth_handler_onedrive.py` - OAuth authentication
   - `onedrive_service.py` - Core OneDrive API service
   - `onedrive_health_handler.py` - Health monitoring
   - `onedrive_integration_register.py` - Integration registration

2. **Frontend Components** (`frontend-nextjs/components/integrations/`)
   - `OneDriveIntegration.tsx` - Main React component
   - Available at `/onedrive` and `/integrations/onedrive`

3. **Integration Points**
   - Registered in main API app (`main_api_app.py`)
   - Added to Service Management dashboard

### Testing

Run the integration tests:

```bash
# Backend tests
cd backend/python-api-service
python -m pytest tests/test_onedrive.py -v

# Frontend tests
cd frontend-nextjs
npm test -- OneDriveIntegration.test.tsx
```

## Support

For issues with the OneDrive integration:

1. Check the application logs for detailed error messages
2. Verify Azure App Registration configuration
3. Ensure Microsoft Graph API permissions are granted
4. Check network connectivity to Microsoft Graph API

## Changelog

### v2.0.0 (Current)
- Complete OAuth 2.0 integration with Microsoft Graph API
- File browser with breadcrumb navigation
- Document ingestion for search
- React-based frontend components
- Comprehensive API coverage

### v1.0.0
- Initial OneDrive integration
- Basic file listing capabilities
- Simple authentication flow

---

**Note**: This integration requires a working ATOM backend and properly configured Azure App Registration. Refer to the main ATOM documentation for general setup instructions.