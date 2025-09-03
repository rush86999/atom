# Atom Project - Complete OAuth & API Key Management System

## 🚀 OAuth System Overview

The Atom project features a comprehensive OAuth 2.0 implementation for third-party integrations. The system supports multiple providers with secure token storage, automatic refresh, and full integration management.

### Supported OAuth Providers
- ✅ **Google Drive** - File access and management
- ✅ **Asana** - Task and project management  
- ✅ **Dropbox** - Cloud storage integration
- ✅ **Box** - Enterprise file sharing
- ✅ **Trello** - Project management boards
- ✅ **Shopify** - E-commerce platform
- ✅ **Zoho** - Business applications suite

## 🔑 API Key Management

The system also includes secure API key management for services that don't support OAuth:
- Secure encryption of API keys at rest
- User-friendly interface for key management
- Integration with the orchestration system

## 🛠️ Setup & Configuration

### Quick Start
1. Copy `.env.template` to `.env` and configure values
2. Run services:
   - Python API: `cd backend && docker-compose up`
   - Frontend: `cd frontend-nextjs && npm run dev`
   - Desktop: `cd desktop && npm run tauri dev`

### OAuth Provider Setup
For each OAuth provider, you need to:

1. **Register your application** with the provider's developer portal
2. **Add credentials** to your `.env` file:
   ```bash
   # Google
   GOOGLE_CLIENT_ID=your_google_client_id
   GOOGLE_CLIENT_SECRET=your_google_client_secret
   
   # Asana
   ASANA_CLIENT_ID=your_asana_client_id
   ASANA_CLIENT_SECRET=your_asana_client_secret
   
   # Dropbox
   DROPBOX_CLIENT_ID=your_dropbox_client_id
   DROPBOX_CLIENT_SECRET=your_dropbox_client_secret
   
   # Box
   BOX_CLIENT_ID=your_box_client_id
   BOX_CLIENT_SECRET=your_box_client_secret
   
   # Trello
   TRELLO_CLIENT_ID=your_trello_client_id
   TRELLO_CLIENT_SECRET=your_trello_client_secret
   
   # Shopify
   SHOPIFY_CLIENT_ID=your_shopify_client_id
   SHOPIFY_CLIENT_SECRET=your_shopify_client_secret
   
   # Zoho
   ZOHO_CLIENT_ID=your_zoho_client_id
   ZOHO_CLIENT_SECRET=your_zoho_client_secret
   ```

3. **Configure redirect URIs** in your provider dashboard:
   - All services: `http://localhost:3000/api/oauth/[service]/callback`
   - Replace `[service]` with the provider name (google, asana, dropbox, etc.)

### Encryption Setup
Generate a secure encryption key for API key storage:
```bash
# Generate a 256-bit encryption key
node -e "console.log(require('crypto').randomBytes(32).toString('hex'))"
```

Add the key to your `.env` file:
```bash
ENCRYPTION_KEY=your_generated_64_character_hex_key_here
```

## 🏗️ Architecture & OAuth Flow

### OAuth Architecture

The OAuth system consists of three main components:

1. **OAuth Service** (`src/services/oauthService.ts`) - Handles OAuth flows and token management
2. **Database Service** (`src/services/oauthDatabaseService.ts`) - Manages token storage and retrieval
3. **API Routes** (`pages/api/oauth/`) - Handles HTTP endpoints for OAuth flows

### OAuth Flow Sequence

1. **Initiation**: User clicks "Connect" on integrations page
2. **Redirect**: Browser redirects to OAuth provider's authorization page
3. **Callback**: Provider redirects back with authorization code
4. **Token Exchange**: Server exchanges code for access/refresh tokens
5. **Storage**: Tokens are encrypted and stored in database
6. **Usage**: Tokens are used for API calls to integrated services

### API Key Management Flow

1. **Storage**: User enters API key in settings interface
2. **Encryption**: Key is encrypted using AES-256-GCM before storage
3. **Retrieval**: Keys are decrypted on-demand for API calls
4. **Rotation**: Users can update or delete keys as needed

## 📊 Database Schema

### OAuth Token Tables
```sql
-- Google Drive OAuth Tokens
CREATE TABLE user_gdrive_oauth_tokens (
    user_id VARCHAR(255) PRIMARY KEY,
    gdrive_user_email VARCHAR(255) NOT NULL,
    access_token TEXT NOT NULL,
    refresh_token TEXT,
    expires_at TIMESTAMP,
    token_type VARCHAR(50),
    scope TEXT,
    external_user_id VARCHAR(255),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Similar tables exist for all supported providers
```

### API Key Table
```sql
CREATE TABLE user_api_keys (
    id VARCHAR(255) PRIMARY KEY,
    user_id VARCHAR(255) NOT NULL,
    service VARCHAR(100) NOT NULL,
    name VARCHAR(255) NOT NULL,
    encrypted_key TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

## 🔧 API Endpoints

### OAuth Endpoints
- `GET /api/oauth/[service]/initiate` - Start OAuth flow
- `GET /api/oauth/[service]/callback` - Handle OAuth callback
- `POST /api/integrations/disconnect` - Disconnect integration

### Integration Management
- `GET /api/integrations/status` - Get connection status
- `GET/POST/PUT/DELETE /api/integrations/apikeys` - Manage API keys

## 🛡️ Security Features

### Token Security
- Refresh token rotation support
- Automatic token expiration handling
- Secure token revocation
- CSRF protection with state parameters

### API Key Security
- AES-256-GCM encryption at rest
- Secure key generation and storage
- No plaintext key exposure in UI
- Proper key rotation procedures

### Database Security
- Separate tables per service for isolation
- Indexed queries for performance
- Automatic timestamp tracking
- Foreign key constraints

## 🚀 Usage Examples

### Connecting to Google Drive
```typescript
// Initiate OAuth flow
window.location.href = '/api/oauth/google/initiate';

// Handle callback automatically
// Tokens are stored and managed by the system
```

### Managing API Keys
```typescript
// Save a new API key
const response = await fetch('/api/integrations/apikeys', {
  method: 'POST',
  body: JSON.stringify({
    service: 'openai',
    name: 'Production API Key',
    key: 'sk-...'
  })
});

// Get all API keys
const keys = await fetch('/api/integrations/apikeys');
```

### Checking Integration Status
```typescript
const status = await fetch('/api/integrations/status');
// Returns: {
//   google: { connected: true, email: 'user@example.com', lastConnected: '...' },
//   asana: { connected: false },
//   // ... other services
// }
```

## 🐛 Troubleshooting

### Common Issues

1. **Redirect URI Mismatch**
   - Ensure redirect URIs match exactly in provider dashboard
   - Use `http://localhost:3000/api/oauth/[service]/callback` for development

2. **Invalid OAuth Credentials**
   - Verify client ID and secret are correct
   - Check that OAuth scopes are properly configured

3. **Token Refresh Issues**
   - Ensure refresh tokens are being stored properly
   - Check token expiration handling

4. **Database Connection Issues**
   - Verify DATABASE_URL is set correctly
   - Check database permissions and table existence

### Debugging

Enable debug logging by setting:
```bash
LOG_LEVEL=debug
```

Check browser console and server logs for detailed error messages.

## 📝 Future Enhancements

### Planned Features
- [ ] Webhook-based token refresh notifications
- [ ] Multi-account support per service
- [ ] Token usage analytics and reporting
- [ ] Automated token rotation policies
- [ ] Integration with secret management systems
- [ ] Audit logging for all token operations

### Security Improvements
- [ ] Hardware Security Module (HSM) integration
- [ ] Key rotation automation
- [ ] Advanced threat detection
- [ ] Compliance reporting (SOC 2, ISO 27001)

## 🚀 OAuth System Overview

The Atom project features a comprehensive OAuth 2.0 implementation for third-party integrations. The system supports multiple providers with secure token storage, automatic refresh, and full integration management.

### Supported OAuth Providers
- ✅ **Google Drive** - File access and management
- ✅ **Asana** - Task and project management  
- ✅ **Dropbox** - Cloud storage integration
- ✅ **Box** - Enterprise file sharing
- ✅ **Trello** - Project management boards
- ✅ **Shopify** - E-commerce platform
- ✅ **Zoho** - Business applications suite

## 🛠️ Setup & OAuth Configuration

### Quick Start
1. Copy `.env.example` to `.env` and configure values
2. Run services:
   - Python API: `cd backend && docker-compose up`
   - Frontend: `cd frontend-nextjs && npm run dev`
   - Desktop: `cd desktop && npm run tauri dev`

### OAuth Provider Setup
For each OAuth provider, you need to:

1. **Register your application** with the provider's developer portal
2. **Add credentials** to your `.env` file:
   ```bash
   # Google Drive
   ATOM_GDRIVE_CLIENT_ID=your_google_client_id
   ATOM_GDRIVE_CLIENT_SECRET=your_google_client_secret
   
   # Asana
   ASANA_CLIENT_ID=your_asana_client_id
   ASANA_CLIENT_SECRET=your_asana_client_secret
   
   # Other providers follow similar pattern
   ```

3. **Configure redirect URIs** in your provider dashboard:
   - Google: `http://localhost:5058/api/auth/gdrive/oauth2callback`
   - Asana: `http://localhost:5058/api/auth/asana/callback`
   - Dropbox: `http://localhost:5058/api/auth/dropbox/callback`
   - etc.

## 🏗️ Architecture & OAuth Flow

### System Architecture
- **Frontend**: Next.js (port 3000) - Integration management UI
- **API**: Flask (port 5058) - OAuth endpoints and token management
- **Database**: PostgreSQL - Encrypted token storage
- **Desktop**: Tauri wrapper

### OAuth Flow Sequence
1. **Initiation**: User clicks "Connect" in frontend → Redirect to provider auth page
2. **Authorization**: User grants permissions on provider's site
3. **Callback**: Provider redirects to Atom callback endpoint with auth code
4. **Token Exchange**: Backend exchanges code for access/refresh tokens
5. **Storage**: Tokens encrypted and stored in database
6. **Usage**: Services use stored tokens for API calls

### Security Features
- 🔒 **Token Encryption**: All tokens encrypted before database storage
- 🛡️ **CSRF Protection**: State parameters prevent CSRF attacks
- 🔄 **Automatic Refresh**: Refresh tokens handled automatically
- 🗑️ **Secure Disconnect**: Proper token revocation support

## 🔧 Environment Variables

### Required for OAuth
```bash
# Flask & Database
FLASK_SECRET_KEY=your_very_secret_key_here
DATABASE_URL=postgresql://user:pass@localhost:5432/atom_db
PYTHON_API_PORT=5058

# Google Drive OAuth
ATOM_GDRIVE_CLIENT_ID=your_google_client_id
ATOM_GDRIVE_CLIENT_SECRET=your_google_client_secret
ATOM_GDRIVE_REDIRECT_URI=http://localhost:5058/api/auth/gdrive/oauth2callback

# Asana OAuth
ASANA_CLIENT_ID=your_asana_client_id
ASANA_CLIENT_SECRET=your_asana_client_secret

# Dropbox OAuth
DROPBOX_APP_KEY=your_dropbox_app_key
DROPBOX_APP_SECRET=your_dropbox_app_secret

# Frontend URLs
APP_CLIENT_URL=http://localhost:3000
FRONTEND_OAUTH_SUCCESS_URL=/integrations?status=success
FRONTEND_OAUTH_FAILURE_URL=/integrations?status=failure
```

See `.env.example` for complete reference of all supported providers.

## 📁 Project Structure & OAuth Components

### Key OAuth Directories
```
atom/
├── backend/
│   └── python-api-service/
│       ├── auth_handler_*.py          # OAuth handlers (gdrive, asana, dropbox, etc.)
│       ├── db_oauth_*.py              # Database operations for each provider
│       ├── crypto_utils.py            # Token encryption/decryption
│       └── main_api_app.py            # Flask app with OAuth blueprints
├── frontend-nextjs/
│   ├── pages/
│   │   ├── integrations.tsx           # OAuth connection management UI
│   │   └── api/
│   │       └── integrations/          # Integration status API
│   └── src/
│       └── components/
│           └── Integrations/          # OAuth UI components
├── scripts/
│   ├── start-dev.sh                   # Development startup script
│   ├── test-oauth-endpoints.py        # OAuth health check
│   └── create-oauth-tables.sql        # Database schema
└── .env.example                       # OAuth configuration template
```

### OAuth API Endpoints
- `GET /api/auth/{provider}/initiate` - Start OAuth flow
- `GET /api/auth/{provider}/callback` - Handle OAuth callback
- `POST /api/auth/{provider}/disconnect` - Revoke connection
- `GET /api/auth/{provider}/status` - Check connection status
- `GET /api/integrations/status` - Get all integration statuses

### Database Schema
OAuth tokens are stored in provider-specific tables with:
- User ID reference
- Encrypted access and refresh tokens
- Expiration timestamps
- User email/identification
- Audit timestamps