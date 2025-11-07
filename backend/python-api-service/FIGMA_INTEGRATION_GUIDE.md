# Figma Integration Guide

## Overview

The Figma integration provides comprehensive design collaboration and file management capabilities within the ATOM platform. This integration enables users to access their Figma design files, manage teams, browse component libraries, and collaborate in real-time directly from the ATOM interface.

## 🎨 Features

### Core Capabilities
- **File Management**: Browse, search, and manage Figma design files
- **Team Collaboration**: Access team projects and member information
- **Component Libraries**: Browse and search reusable design components
- **Real-time Collaboration**: Comment and provide feedback on designs
- **Version History**: Track design changes and iterations
- **Advanced Search**: Search across files, components, and teams

### Integration Benefits
- Seamless design workflow integration
- Centralized design asset management
- Cross-team collaboration capabilities
- Automated design system documentation
- Real-time design feedback loops

## 🔧 Technical Implementation

### Backend Components

#### 1. Core Service (`figma_service_real.py`)
- Complete Figma API integration
- Mock and real service implementations
- File, team, and component management
- Advanced search functionality

#### 2. Authentication (`auth_handler_figma.py`)
- OAuth 2.0 authentication flow
- Secure token management
- Refresh token handling
- User session management

#### 3. API Endpoints (`figma_handler.py`)
- RESTful API endpoints for all operations
- Health monitoring endpoints
- File operations (list, search, create)
- Team and project management
- Component library access

#### 4. Enhanced Features (`figma_enhanced_api.py`)
- Advanced search with filtering
- Bulk operations
- Performance optimization
- Caching mechanisms

### Frontend Components

#### 1. Main Integration Component (`FigmaIntegration.tsx`)
- Complete React component with TypeScript
- File browsing with thumbnails
- Team and project management
- Component library browser
- Real-time search functionality
- Connection status management

#### 2. Desktop Integration
- Desktop callback handlers
- Local file management
- Offline capabilities
- Desktop notifications

#### 3. Skills System (`figmaSkills.ts`)
- Natural language commands
- File creation and management
- Component search
- Feedback and commenting
- Team collaboration

## 🚀 Quick Start

### Prerequisites
- Figma account with API access
- Figma OAuth application credentials
- ATOM platform access

### Environment Setup

Add the following to your `.env` file:

```bash
# Figma OAuth Configuration
FIGMA_CLIENT_ID=your_figma_client_id
FIGMA_CLIENT_SECRET=your_figma_client_secret
FIGMA_REDIRECT_URI=http://localhost:3000/oauth/figma/callback

# Figma API Configuration
FIGMA_ACCESS_TOKEN=your_figma_access_token
FIGMA_REFRESH_TOKEN=your_figma_refresh_token
FIGMA_USER_ID=your_figma_user_id
FIGMA_USER_NAME=Your Name
FIGMA_USER_EMAIL=your.email@company.com
FIGMA_USER_AVATAR=https://example.com/avatar.png
FIGMA_ORG_ID=your_org_id
FIGMA_TEAM_IDS=team-1,team-2
```

### Installation Steps

1. **Install Dependencies**
   ```bash
   pip install aiohttp httpx asyncpg flask flask-cors python-dotenv loguru
   ```

2. **Start the Backend**
   ```bash
   python main_api_app.py
   ```

3. **Configure Frontend**
   - Ensure the Figma integration is registered in ServiceManagement
   - Verify dashboard routes include Figma status
   - Test the FigmaIntegration component

4. **Test Integration**
   ```bash
   python test_figma_integration.py
   ```

## 🔌 API Reference

### Authentication Endpoints

| Method | Endpoint | Description |
|--------|-----------|-------------|
| GET | `/api/auth/figma/authorize` | Initiate OAuth flow |
| GET | `/api/auth/figma/callback` | Handle OAuth callback |
| GET | `/api/auth/figma/status` | Check authentication status |
| POST | `/api/auth/figma/disconnect` | Disconnect Figma account |

### File Management

| Method | Endpoint | Description |
|--------|-----------|-------------|
| GET | `/api/figma/files` | List user files |
| POST | `/api/integrations/figma/files` | Enhanced file listing |
| GET | `/api/figma/files/{file_key}` | Get file details |
| POST | `/api/figma/files/{file_key}/comments` | Add comment to file |

### Team Management

| Method | Endpoint | Description |
|--------|-----------|-------------|
| GET | `/api/figma/teams` | List user teams |
| GET | `/api/figma/teams/{team_id}/projects` | List team projects |
| GET | `/api/figma/teams/{team_id}/members` | List team members |

### Component Management

| Method | Endpoint | Description |
|--------|-----------|-------------|
| GET | `/api/figma/components` | List components |
| GET | `/api/figma/files/{file_key}/components` | Get file components |
| GET | `/api/figma/components/search` | Search components |

### Search & Analytics

| Method | Endpoint | Description |
|--------|-----------|-------------|
| POST | `/api/figma/search` | Search across Figma |
| GET | `/api/figma/analytics` | Get usage analytics |
| GET | `/api/figma/health` | Health check |

## 💡 Usage Examples

### React Component Usage

```typescript
import { FigmaIntegration } from '@atom/ui-shared/integrations/figma/FigmaIntegration';

function DesignDashboard() {
  return (
    <FigmaIntegration
      userId="user-123"
      isConnected={true}
      onConnect={() => console.log('Figma connected')}
      onDisconnect={() => console.log('Figma disconnected')}
    />
  );
}
```

### API Usage Examples

#### Get User Files
```python
import aiohttp

async def get_figma_files(user_id: str):
    async with aiohttp.ClientSession() as session:
        response = await session.get(
            "http://localhost:8000/api/figma/files",
            params={"user_id": user_id, "limit": 50}
        )
        data = await response.json()
        return data["files"]
```

#### Search Components
```python
async def search_components(user_id: str, query: str):
    async with aiohttp.ClientSession() as session:
        response = await session.post(
            "http://localhost:8000/api/figma/search",
            json={
                "user_id": user_id,
                "query": query,
                "search_type": "components",
                "limit": 20
            }
        )
        data = await response.json()
        return data["results"]
```

### Chat Commands

The integration supports natural language commands:

- "Create a new Figma file called Mobile App Design"
- "Show me all my Figma files"
- "Search for button components in Figma"
- "Add comment about the navigation design"

## 🔒 Security Features

### Authentication Security
- OAuth 2.0 with PKCE support
- Secure token storage with encryption
- Automatic token refresh
- Session timeout management

### Data Protection
- User data isolation
- Request validation and sanitization
- Rate limiting and throttling
- Secure API communication

### Compliance
- GDPR-compliant data handling
- Privacy-first design
- Audit logging
- Data retention policies

## 📊 Monitoring & Analytics

### Health Monitoring
- API connectivity status
- Service availability
- Response time tracking
- Error rate monitoring

### Usage Analytics
- File access patterns
- Team collaboration metrics
- Component usage statistics
- Search performance

### Performance Metrics
- API response times
- Cache hit rates
- Concurrent user limits
- Resource utilization

## 🐛 Troubleshooting

### Common Issues

#### OAuth Connection Issues
1. **Invalid Client ID/Secret**
   - Verify credentials in environment variables
   - Check redirect URI configuration
   - Ensure proper OAuth scopes

2. **Token Expiration**
   - Implement refresh token logic
   - Monitor token expiration times
   - Use proactive token renewal

#### API Rate Limits
1. **Rate Limit Exceeded**
   - Implement exponential backoff
   - Use caching for repeated requests
   - Monitor API usage patterns

2. **Performance Issues**
   - Enable response caching
   - Optimize database queries
   - Use background processing

### Debug Mode

Enable detailed logging:

```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

### Health Check Debugging

Use detailed health endpoint:

```bash
curl "http://localhost:8000/api/figma/health/detailed?user_id=user_123"
```

## 🔄 Maintenance

### Regular Tasks
- Monitor API rate limits
- Update OAuth tokens
- Refresh component caches
- Clean up expired sessions

### Performance Optimization
- Implement response caching
- Optimize database queries
- Use background processing
- Monitor resource usage

### Security Updates
- Regular dependency updates
- Security patch application
- Token rotation
- Access review

## 📈 Scaling Considerations

### Horizontal Scaling
- Stateless service design
- Shared session storage
- Load balancer configuration
- Database connection pooling

### Performance Optimization
- CDN integration for thumbnails
- Response compression
- Query optimization
- Background job processing

### High Availability
- Multi-region deployment
- Failover mechanisms
- Backup and recovery
- Monitoring and alerting

## 🤝 Support

### Documentation
- API documentation
- Integration guides
- Troubleshooting guides
- Best practices

### Community Support
- Issue reporting
- Feature requests
- Community forums
- Knowledge base

### Professional Support
- Enterprise support plans
- Custom integration services
- Training and onboarding
- Performance optimization

---

## 🎉 Summary

The Figma integration provides a comprehensive, production-ready solution for design management and collaboration within the ATOM ecosystem. With complete API coverage, robust security features, and seamless user experience, it enables teams to streamline their design workflows and enhance collaboration.

**Key Benefits:**
- ✅ Complete Figma API integration
- ✅ Secure OAuth authentication
- ✅ Advanced search and filtering
- ✅ Real-time collaboration features
- ✅ Comprehensive health monitoring
- ✅ Production-ready error handling
- ✅ Performance optimization
- ✅ Security best practices

This integration is ready for enterprise deployment and can handle large-scale design workflows with reliability and performance.