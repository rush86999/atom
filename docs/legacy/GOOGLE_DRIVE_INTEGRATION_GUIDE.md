# Google Drive Integration Guide

# Google Drive Integration Guide

## Overview

The Google Drive integration provides seamless access to your Google Drive files within the ATOM platform. This integration enables file browsing, search, document ingestion, and workflow automation with your Google Drive content.

## Features

- 🔐 **OAuth 2.0 Authentication** - Secure connection to Google Drive
- 📁 **File Browser** - Navigate folders and view files
- 🔍 **Advanced Search** - Search across all Google Drive content
- 📄 **Document Ingestion** - Add files to ATOM's search index
- 🔄 **Real-time Sync** - Keep file listings up to date
- 🛠️ **API Integration** - Full access to Google Drive APIs

## Setup Instructions

### 1. Prerequisites

- Google Cloud Console project with Google Drive API enabled
- OAuth 2.0 credentials configured
- ATOM backend service running

### 2. Backend Configuration

#### Environment Variables

Add the following to your `.env` file:

```bash
# Google Drive OAuth Configuration
GOOGLE_DRIVE_CLIENT_ID=your_client_id
GOOGLE_DRIVE_CLIENT_SECRET=your_client_secret
GOOGLE_DRIVE_REDIRECT_URI=http://localhost:5058/api/auth/gdrive/oauth2callback

# Optional: Custom scopes
GOOGLE_DRIVE_SCOPES=https://www.googleapis.com/auth/drive.readonly,https://www.googleapis.com/auth/userinfo.email
```

#### Google Cloud Console Setup

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project or select existing
3. Enable the **Google Drive API**
4. Configure OAuth 2.0 credentials:
   - Application type: Web application
   - Authorized redirect URIs: `http://localhost:5058/api/auth/gdrive/oauth2callback`
   - Add your production domain for production deployments

### 3. Frontend Integration

The Google Drive integration is available through multiple interfaces:

#### Web Interface
- Navigate to `/google-drive` for the full Google Drive interface
- Access via `/integrations/gdrive` for integration-specific view
- Available in Service Management dashboard

#### API Endpoints

All Google Drive endpoints are prefixed with `/api/gdrive`:

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/gdrive/connection-status` | GET | Check connection status |
| `/api/gdrive/list-files` | POST | List files and folders |
| `/api/gdrive/search` | POST | Search Google Drive |
| `/api/gdrive/get-file-metadata` | POST | Get file metadata |
| `/api/ingest-gdrive-document` | POST | Ingest file for search |
| `/api/auth/gdrive/authorize` | GET | Start OAuth flow |
| `/api/auth/gdrive/disconnect` | POST | Disconnect account |

## Usage Guide

### Connecting Google Drive

1. **Navigate to Google Drive Integration**
   - Go to `/google-drive` or find it in the integrations dashboard
   - Click "Connect Google Drive"

2. **OAuth Authorization**
   - You'll be redirected to Google's OAuth consent screen
   - Review the permissions and grant access
   - You'll be redirected back to ATOM

3. **Verification**
   - The connection status should show "Connected"
   - Your Google account email will be displayed

### File Management

#### Browsing Files
- Use the breadcrumb navigation to navigate folders
- Click folders to open them
- Click files to view them in Google Drive (opens in new tab)

#### File Operations
- **Ingest File**: Click the download icon to add file to ATOM's search index
- **Open in Drive**: Click the external link icon to open in Google Drive
- **Load More**: Use pagination for large folders

#### Search Capabilities
The integration supports:
- **Full-text search** across file contents
- **Metadata search** (filename, type, date)
- **Folder-specific search**
- **Semantic search** (when combined with ATOM's AI)

### Document Ingestion

When you ingest a Google Drive file:

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
   - Original files remain in Google Drive
   - No duplication of file storage

## API Reference

### Connection Status

```javascript
// Request
GET /api/gdrive/connection-status?user_id=user123

// Response
{
  "isConnected": true,
  "email": "user@example.com",
  "reason": null
}
```

### List Files

```javascript
// Request
POST /api/gdrive/list-files
{
  "user_id": "user123",
  "folder_id": "optional_folder_id",
  "query": "optional_search_query",
  "page_size": 50,
  "page_token": "optional_page_token"
}

// Response
{
  "files": [
    {
      "id": "file123",
      "name": "document.pdf",
      "mimeType": "application/pdf",
      "isFolder": false,
      "modifiedTime": "2024-01-15T10:30:00Z",
      "webViewLink": "https://drive.google.com/file/d/file123/view",
      "size": 1024000
    }
  ],
  "nextPageToken": "next_page_token"
}
```

### Ingest Document

```javascript
// Request
POST /api/ingest-gdrive-document
{
  "user_id": "user123",
  "gdrive_file_id": "file123",
  "original_file_metadata": {
    "name": "document.pdf",
    "mimeType": "application/pdf",
    "webViewLink": "https://drive.google.com/file/d/file123/view"
  }
}

// Response
{
  "doc_id": "doc_abc123",
  "num_chunks_stored": 15
}
```

## Supported File Types

The integration supports all Google Drive file types:

| File Type | MIME Type | Ingestion Support |
|-----------|-----------|-------------------|
| Google Docs | `application/vnd.google-apps.document` | ✅ Full |
| Google Sheets | `application/vnd.google-apps.spreadsheet` | ✅ Full |
| Google Slides | `application/vnd.google-apps.presentation` | ✅ Full |
| PDF Files | `application/pdf` | ✅ Full |
| Microsoft Office | `application/vnd.openxmlformats...` | ✅ Full |
| Images | `image/*` | ⚠️ Limited (metadata only) |
| Videos | `video/*` | ⚠️ Limited (metadata only) |
| Folders | `application/vnd.google-apps.folder` | 🔄 Navigation only |

## Security & Permissions

### OAuth Scopes

The integration requests the following scopes:

- `https://www.googleapis.com/auth/drive.readonly` - Read file metadata and content
- `https://www.googleapis.com/auth/userinfo.email` - Get user email for identification

### Data Handling

- **No file modifications**: Integration is read-only
- **Encrypted storage**: OAuth tokens are encrypted at rest
- **User isolation**: Files are only accessible to the connected user
- **Temporary processing**: File content is processed but not permanently stored

## Troubleshooting

### Common Issues

#### Connection Failures
- **Invalid OAuth credentials**: Verify client ID and secret
- **Redirect URI mismatch**: Ensure redirect URI matches Google Cloud Console
- **Scope permissions**: User may need to grant additional permissions

#### File Access Issues
- **Permission denied**: File may not be shared with the connected account
- **File not found**: File may have been moved or deleted
- **Rate limiting**: Google Drive API quotas may be exceeded

#### Search/Ingestion Issues
- **Unsupported file type**: Some file types cannot be processed
- **Large files**: Files over 10MB may timeout
- **Corrupted files**: Some files may fail to process

### Debug Mode

Enable debug logging by setting:

```bash
LOG_LEVEL=DEBUG
```

This will provide detailed logs for troubleshooting OAuth flows and API calls.

## Performance Considerations

### API Quotas
- Google Drive API has daily quotas and rate limits
- Consider implementing caching for frequent operations
- Batch operations when possible

### File Size Limits
- Recommended maximum file size: 10MB
- Large files may timeout during processing
- Consider chunking for very large documents

### Caching Strategy
- File listings are cached for 5 minutes
- Metadata is cached for 15 minutes
- Search results are not cached for real-time accuracy

## Development

### Adding New Features

The integration is built with extensibility in mind:

1. **Backend Services** (`backend/python-api-service/`)
   - `gdrive_handler.py` - Main file operations
   - `auth_handler_gdrive.py` - OAuth authentication
   - `google_drive_service.py` - Core Google Drive API

2. **Frontend Components** (`frontend-nextjs/components/integrations/`)
   - `GoogleDriveIntegration.tsx` - Main React component
   - Available at `/google-drive` and `/integrations/gdrive`

3. **Shared Types** (`src/skills/gdriveSkills.ts`)
   - TypeScript interfaces for API responses
   - Shared between frontend and backend

### Testing

Run the integration tests:

```bash
# Backend tests
cd backend/python-api-service
python -m pytest tests/test_google_drive.py -v

# Frontend tests
cd frontend-nextjs
npm test -- GoogleDriveIntegration.test.tsx
```

## Support

For issues with the Google Drive integration:

1. Check the application logs for detailed error messages
2. Verify OAuth configuration in Google Cloud Console
3. Ensure the Google Drive API is enabled
4. Check network connectivity to Google APIs

## Changelog

### v2.0.0 (Current)
- Complete OAuth 2.0 integration
- File browser with breadcrumb navigation
- Document ingestion for search
- React-based frontend components
- Comprehensive API coverage

### v1.0.0
- Initial Google Drive integration
- Basic file listing capabilities
- Simple authentication flow

---

**Note**: This integration requires a working ATOM backend and properly configured Google Cloud Console project. Refer to the main ATOM documentation for general setup instructions.