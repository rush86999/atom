# Figma Integration for ATOM Backend

Complete Figma design management and collaboration system for ATOM Enterprise Backend.

## 🎨 Overview

This integration provides comprehensive access to Figma's design ecosystem, including:
- File management and browsing
- Team and project collaboration
- Component library access
- Advanced search functionality
- OAuth authentication
- Health monitoring
- Real-time commenting and collaboration

## 📁 File Structure

```
backend/python-api-service/
├── figma_service_real.py              # Core Figma service implementation
├── figma_handler.py                  # REST API endpoints
├── figma_health_handler.py           # Health monitoring endpoints
├── figma_enhanced_api.py            # Enhanced API with advanced features
├── db_oauth_figma.py               # Database operations for OAuth tokens
├── figma_integration_register.py     # Registration utilities
├── desktop-figma-integration.ts    # TypeScript desktop integration
├── test_figma_integration.py        # Comprehensive test suite
└── FIGMA_INTEGRATION_README.md    # This documentation
```

## 🚀 Quick Start

### 1. Environment Configuration

Add these variables to your `.env` file:

```bash
# Figma OAuth Configuration
FIGMA_CLIENT_ID=your_figma_client_id
FIGMA_CLIENT_SECRET=your_figma_client_secret
FIGMA_REDIRECT_URI=http://localhost:3000/oauth/figma/callback

# Figma API Configuration (for testing)
FIGMA_ACCESS_TOKEN=your_figma_access_token
FIGMA_REFRESH_TOKEN=your_figma_refresh_token
FIGMA_USER_ID=your_figma_user_id
FIGMA_USER_NAME=Your Name
FIGMA_USER_EMAIL=your.email@company.com
FIGMA_USER_AVATAR=https://example.com/avatar.png
FIGMA_USER_DEPARTMENT=Design
FIGMA_USER_TITLE=UI/UX Designer
FIGMA_ORG_ID=your_org_id
FIGMA_TEAM_IDS=team-1,team-2
```

### 2. Install Dependencies

```bash
pip install aiohttp httpx asyncpg flask flask-cors python-dotenv loguru
```

### 3. Run the Server

```bash
python main_api_app.py
```

The server will start on `http://localhost:8000`.

## 🔌 API Endpoints

### Health & Status

| Method | Endpoint | Description |
|--------|-----------|-------------|
| GET | `/api/figma/health` | Basic health check |
| GET | `/api/figma/health/detailed` | Comprehensive health monitoring |
| GET | `/api/figma/health/summary` | Health status summary |
| GET | `/api/figma/health/tokens` | Token health check |
| GET | `/api/figma/health/connection` | API connectivity test |

### OAuth Authentication

| Method | Endpoint | Description |
|--------|-----------|-------------|
| GET | `/api/oauth/figma/url` | Generate OAuth URL |
| POST | `/api/oauth/figma/callback` | Handle OAuth callback |

### File Management

| Method | Endpoint | Description |
|--------|-----------|-------------|
| GET | `/api/figma/files` | List user files |
| POST | `/api/integrations/figma/files` | Enhanced files listing with filtering |

### Team Management

| Method | Endpoint | Description |
|--------|-----------|-------------|
| GET | `/api/figma/teams` | List user teams |
| GET | `/api/figma/users` | List team members |
| POST | `/api/integrations/figma/teams` | Enhanced teams listing |

### Project Management

| Method | Endpoint | Description |
|--------|-----------|-------------|
| GET | `/api/figma/projects` | List team projects |
| POST | `/api/integrations/figma/projects` | Enhanced projects listing |

### Component Management

| Method | Endpoint | Description |
|--------|-----------|-------------|
| GET | `/api/figma/components` | List file components |
| GET | `/api/figma/styles` | List file styles |
| POST | `/api/integrations/figma/components` | Enhanced components listing |

### Search

| Method | Endpoint | Description |
|--------|-----------|-------------|
| POST | `/api/figma/search` | Search across Figma |
| POST | `/api/integrations/figma/search` | Enhanced search with filters |

### User Profile

| Method | Endpoint | Description |
|--------|-----------|-------------|
| GET | `/api/figma/users/profile` | Get user profile |
| POST | `/api/integrations/figma/user/profile` | Enhanced user profile |

### Collaboration

| Method | Endpoint | Description |
|--------|-----------|-------------|
| POST | `/api/figma/comments` | Add comment to file |
| GET | `/api/figma/versions` | Get file version history |
| POST | `/api/figma/export` | Export file in specific format |

## 🔧 Usage Examples

### Getting User Files

```python
import aiohttp

async def get_figma_files():
    async with aiohttp.ClientSession() as session:
        response = await session.get(
            "http://localhost:8000/api/figma/files",
            params={
                "user_id": "user_123",
                "team_id": "team_123",
                "limit": 50
            }
        )
        data = await response.json()
        return data["files"]
```

### Searching Figma

```python
async def search_figma():
    async with aiohttp.ClientSession() as session:
        response = await session.post(
            "http://localhost:8000/api/figma/search",
            json={
                "user_id": "user_123",
                "query": "button component",
                "search_type": "components",
                "limit": 20
            }
        )
        data = await response.json()
        return data["results"]
```

### Enhanced File Listing with Filtering

```python
async def get_filtered_files():
    async with aiohttp.ClientSession() as session:
        response = await session.post(
            "http://localhost:8000/api/integrations/figma/files",
            json={
                "user_id": "user_123",
                "team_id": "team_123",
                "include_archived": False,
                "file_type": "figma",
                "sort_by": "last_modified",
                "sort_order": "desc",
                "limit": 25
            }
        )
        data = await response.json()
        return data["data"]["files"]
```

## 🖥️ Desktop Integration

### TypeScript Usage

```typescript
import { FigmaDesktopService } from './desktop-figma-integration';

const figmaService = new FigmaDesktopService();

// Get user files
const files = await figmaService.getFiles({
  userId: 'user_123',
  teamId: 'team_123',
  includeArchived: false,
  limit: 50
});

// Search Figma
const searchResults = await figmaService.searchEnhanced({
  userId: 'user_123',
  query: 'design system',
  searchType: 'all',
  includeThumbnails: true
});

// Get user profile with team details
const userProfile = await figmaService.getUserProfile('user_123');
```

## 🧪 Testing

Run the comprehensive test suite:

```bash
python test_figma_integration.py
```

This will test:
- ✅ Health checks
- ✅ File management
- ✅ Team operations
- ✅ Project management
- ✅ Component access
- ✅ Search functionality
- ✅ OAuth flows
- ✅ Collaboration features
- ✅ End-to-end workflows

## 📊 Health Monitoring

The integration provides comprehensive health monitoring:

### Service Health
- API connectivity status
- Service availability
- Response times
- Error rates

### Database Health
- Connection status
- OAuth token storage
- Query performance
- Data integrity

### Token Health
- Access token validity
- Expiration tracking
- Refresh capability
- Scope verification

### Component Health
- Individual service status
- Overall system health
- Performance metrics
- Error diagnostics

## 🔒 Security Features

### OAuth Security
- Secure token storage
- Token encryption
- Refresh token management
- Scope-based access control

### Data Protection
- User data isolation
- Request validation
- Rate limiting
- Error sanitization

### Authentication
- Multi-factor support
- Session management
- Token expiration
- Secure callbacks

## 🚀 Advanced Features

### Enhanced Search
- Full-text search across files, components, and projects
- Filter by file type, team, project
- Relevance scoring
- Highlighted results

### Component Management
- Browse component libraries
- Filter by component type
- Metadata extraction
- Thumbnail support

### Team Collaboration
- Team member management
- Role-based permissions
- Guest user support
- Workspace information

### File Operations
- Version history tracking
- Export in multiple formats
- Comment and collaboration
- Archive management

## 📈 Performance Features

### Caching
- API response caching
- Component metadata caching
- Thumbnail caching
- Search result caching

### Optimization
- Pagination support
- Lazy loading
- Bulk operations
- Background processing

### Monitoring
- Request tracking
- Performance metrics
- Error logging
- Usage analytics

## 🔧 Configuration Options

### Service Configuration
```python
# In figma_service_real.py
FIGMA_API_BASE_URL = "https://api.figma.com/v1"
REQUEST_TIMEOUT = 30
MAX_RETRIES = 3
CACHE_TTL = 3600
```

### Database Configuration
```python
# Connection pooling
DB_MIN_SIZE = 2
DB_MAX_SIZE = 10
DB_TIMEOUT = 30
```

### API Configuration
```python
# Rate limiting
RATE_LIMIT_REQUESTS = 100
RATE_LIMIT_WINDOW = 3600

# Pagination
DEFAULT_LIMIT = 50
MAX_LIMIT = 100
```

## 🐛 Troubleshooting

### Common Issues

1. **OAuth Connection Failed**
   - Check client ID and secret
   - Verify redirect URI
   - Ensure proper scope configuration

2. **API Rate Limits**
   - Implement exponential backoff
   - Use caching for repeated requests
   - Monitor usage patterns

3. **Database Connection Issues**
   - Check connection parameters
   - Verify database is running
   - Check network connectivity

4. **Token Expiration**
   - Implement refresh token logic
   - Monitor token expiration
   - Use proactive renewal

### Debug Mode

Enable debug logging:

```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

### Health Check Debugging

Use detailed health endpoint:

```bash
curl "http://localhost:8000/api/figma/health/detailed?user_id=user_123"
```

## 📚 API Reference

### Response Format

```json
{
  "ok": true,
  "data": { ... },
  "endpoint": "files",
  "timestamp": "2024-06-15T10:30:00Z",
  "source": "figma_api"
}
```

### Error Format

```json
{
  "ok": false,
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "user_id is required",
    "endpoint": "files"
  },
  "timestamp": "2024-06-15T10:30:00Z"
}
```

### Pagination

```json
{
  "ok": true,
  "data": {
    "files": [ ... ],
    "total_count": 150,
    "pagination": {
      "limit": 50,
      "offset": 0,
      "has_more": true
    }
  }
}
```

## 🔄 Updates and Maintenance

### Version Updates
- Breaking changes documented
- Migration guides provided
- Backward compatibility maintained
- Rollback procedures

### Maintenance
- Scheduled maintenance windows
- Health monitoring alerts
- Performance optimization
- Security updates

## 📞 Support

### Documentation
- API documentation
- Integration guides
- Troubleshooting guides
- Best practices

### Community
- Issue reporting
- Feature requests
- Community forums
- Knowledge base

---

## 🎉 Summary

The Figma integration provides a comprehensive, production-ready solution for design management and collaboration within the ATOM ecosystem. With extensive API coverage, robust error handling, health monitoring, and desktop integration support, it enables seamless integration with Figma's powerful design platform.

**Key Features:**
- ✅ Complete Figma API coverage
- ✅ OAuth authentication with secure token management
- ✅ Advanced search and filtering
- ✅ Real-time collaboration features
- ✅ Comprehensive health monitoring
- ✅ TypeScript desktop integration
- ✅ Production-ready error handling
- ✅ Performance optimization
- ✅ Security best practices

This integration is ready for enterprise deployment and can handle large-scale design workflows with reliability and performance.