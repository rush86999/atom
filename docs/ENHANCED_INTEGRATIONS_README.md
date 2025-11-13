# 🚀 ATOM Enhanced Integrations - Google, Microsoft, Dropbox

## Overview

This repository contains the enhanced integration system for ATOM platform, providing comprehensive API coverage for Google Workspace, Microsoft 365, and Dropbox services with enterprise-grade features.

## 🌟 Features

### Google Workspace Integration
- **Calendar**: Event management, recurring events, free/busy lookup, sharing
- **Gmail**: Send/receive emails, label management, search, settings
- **Drive**: File operations, folder management, sharing, search
- **User Management**: Profile information, account details

### Microsoft 365 Integration
- **Outlook Calendar**: Event scheduling, attendee management, recurrence
- **Outlook Email**: Send/receive emails, attachments, search
- **OneDrive**: File operations, folder management, sharing, versioning
- **Teams**: Team management, channel operations, messaging

### Dropbox Integration
- **File Operations**: Upload, download, delete, move, copy
- **Folder Management**: Create, list, organize folders
- **Search**: Advanced search across files and folders
- **Sharing**: Create shared links, manage permissions
- **Versioning**: Access file history, restore versions
- **Preview**: Generate file previews
- **Metadata**: Detailed file information, custom properties
- **Space Usage**: Monitor storage usage

## 📋 System Requirements

- Node.js 18+ (for frontend development)
- Python 3.9+ (for backend services)
- PostgreSQL 13+ (for data storage)
- Redis 6+ (for caching)
- Docker (optional, for containerized deployment)

## 🛠️ Architecture

### Frontend (Tauri + React + TypeScript)
```
src/ui-shared/
├── integrations/
│   ├── google/
│   │   ├── services/
│   │   ├── auth/
│   │   └── skills/googleSkillsEnhanced.ts
│   ├── microsoft/
│   │   ├── services/
│   │   ├── auth/
│   │   └── skills/microsoftSkillsEnhanced.ts
│   └── dropbox/
│       ├── services/
│       ├── auth/
│       └── skills/dropboxSkillsEnhanced.ts
└── core/
    ├── storage/
    ├── encryption/
    └── event-bus/
```

### Backend (Python Flask + Async Services)
```
backend/python-api-service/
├── google_services_enhanced.py
├── microsoft_services_enhanced.py
├── dropbox_services_enhanced.py
├── google_enhanced_api.py
├── microsoft_enhanced_api.py
├── dropbox_enhanced_api.py
└── enhanced_main_app.py
```

## 🚀 Quick Start

### 1. Environment Setup

Clone the repository:
```bash
git clone <repository-url>
cd atom
```

### 2. Backend Setup

Navigate to the backend directory:
```bash
cd backend/python-api-service
```

Create a virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

Install dependencies:
```bash
pip install -r requirements.txt
```

### 3. Environment Configuration

Copy the example environment file:
```bash
cp .env.example .env
```

Edit `.env` with your API credentials:

```bash
# Encryption Key (generate with: python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())")
ATOM_OAUTH_ENCRYPTION_KEY=your_fernet_encryption_key_here

# Google Workspace
GOOGLE_CLIENT_ID=your_google_client_id
GOOGLE_CLIENT_SECRET=your_google_client_secret
GOOGLE_REDIRECT_URI=http://localhost:3000/oauth/google/callback

# Microsoft 365
MICROSOFT_CLIENT_ID=your_microsoft_client_id
MICROSOFT_CLIENT_SECRET=your_microsoft_client_secret
MICROSOFT_REDIRECT_URI=http://localhost:3000/oauth/microsoft/callback

# Dropbox
DROPBOX_APP_KEY=your_dropbox_app_key
DROPBOX_APP_SECRET=your_dropbox_app_secret
DROPBOX_REDIRECT_URI=http://localhost:3000/oauth/dropbox/callback

# Database
DATABASE_URL=postgresql://user:password@localhost:5432/atom
REDIS_URL=redis://localhost:6379/0

# Application
FLASK_SECRET_KEY=your_flask_secret_key
PYTHON_API_PORT=8000
```

### 4. Database Setup

Initialize the database:
```bash
python scripts/init_database.py
```

Run migrations:
```bash
python scripts/run_migrations.py
```

### 5. Start Backend Services

Start the enhanced API server:
```bash
python enhanced_main_app.py
```

The backend will be available at `http://localhost:8000`

### 6. Frontend Setup

Navigate to the frontend directory:
```bash
cd src/ui-shared
```

Install dependencies:
```bash
npm install
```

Start development server:
```bash
npm run dev
```

The frontend will be available at `http://localhost:3000`

## 🧪 Testing

### Run Integration Tests

Test all enhanced integrations:
```bash
cd backend/python-api-service
python test_enhanced_integrations.py
```

Test specific service:
```bash
python test_enhanced_integrations.py --service google
python test_enhanced_integrations.py --service microsoft
python test_enhanced_integrations.py --service dropbox
```

### Run Frontend Tests

```bash
cd src/ui-shared
npm test
```

### Run End-to-End Tests

```bash
npm run test:e2e
```

## 📚 API Documentation

### Google Enhanced APIs

#### Calendar Management
```http
POST /api/google/enhanced/calendar/list
POST /api/google/enhanced/calendar/create
POST /api/google/enhanced/calendar/events/list
POST /api/google/enhanced/calendar/events/create
POST /api/google/enhanced/calendar/events/create_recurring
POST /api/google/enhanced/calendar/free_busy
POST /api/google/enhanced/calendar/share
```

#### Gmail Management
```http
POST /api/google/enhanced/gmail/messages/list
POST /api/google/enhanced/gmail/messages/send
POST /api/google/enhanced/gmail/labels/create
POST /api/google/enhanced/gmail/settings
```

#### Drive Management
```http
POST /api/google/enhanced/drive/files/list
POST /api/google/enhanced/drive/folders/create
POST /api/google/enhanced/drive/files/upload
POST /api/google/enhanced/drive/files/share
```

### Microsoft Enhanced APIs

#### Outlook Calendar
```http
POST /api/microsoft/enhanced/calendar/list
POST /api/microsoft/enhanced/calendar/create
POST /api/microsoft/enhanced/calendar/events/list
POST /api/microsoft/enhanced/calendar/events/create
```

#### Outlook Email
```http
POST /api/microsoft/enhanced/email/send
POST /api/microsoft/enhanced/email/list
```

#### OneDrive
```http
POST /api/microsoft/enhanced/onedrive/files/list
POST /api/microsoft/enhanced/onedrive/folders/list
POST /api/microsoft/enhanced/onedrive/folders/create
POST /api/microsoft/enhanced/onedrive/upload
POST /api/microsoft/enhanced/onedrive/share
```

#### Teams
```http
POST /api/microsoft/enhanced/teams/list
POST /api/microsoft/enhanced/teams/channels/list
POST /api/microsoft/enhanced/teams/messages/list
POST /api/microsoft/enhanced/teams/messages/send
```

### Dropbox Enhanced APIs

#### User & File Management
```http
POST /api/dropbox/enhanced/user/info
POST /api/dropbox/enhanced/files/list
POST /api/dropbox/enhanced/folders/list
POST /api/dropbox/enhanced/folders/create
POST /api/dropbox/enhanced/files/upload
POST /api/dropbox/enhanced/files/download
POST /api/dropbox/enhanced/items/delete
POST /api/dropbox/enhanced/items/move
POST /api/dropbox/enhanced/items/copy
```

#### Advanced Features
```http
POST /api/dropbox/enhanced/search
POST /api/dropbox/enhanced/links/create
POST /api/dropbox/enhanced/metadata
POST /api/dropbox/enhanced/versions/list
POST /api/dropbox/enhanced/versions/restore
POST /api/dropbox/enhanced/preview
POST /api/dropbox/enhanced/space
```

## 🔧 Development

### Adding New Integrations

1. **Create Service Class**:
   ```python
   # backend/python-api-service/new_service_enhanced.py
   class NewServiceEnhanced:
       async def some_operation(self, **kwargs):
           # Implementation
           pass
   ```

2. **Create API Blueprint**:
   ```python
   # backend/python-api-service/new_service_enhanced_api.py
   new_service_bp = Blueprint("new_service_enhanced_bp", __name__)
   
   @new_service_bp.route("/api/new-service/enhanced/endpoint", methods=["POST"])
   def handle_endpoint():
       # Implementation
       pass
   ```

3. **Create Frontend Skill**:
   ```typescript
   // src/ui-shared/integrations/new-service/skills/newServiceSkillsEnhanced.ts
   export class NewServiceEnhancedSkill implements IntegrationSkill {
       async execute(params: SkillParams, context: SkillExecutionContext): Promise<any> {
           // Implementation
       }
   }
   ```

4. **Register in Main App**:
   ```python
   # backend/python-api-service/enhanced_main_app.py
   if NEW_SERVICE_AVAILABLE:
       app.register_blueprint(new_service_bp, url_prefix="/api/new-service/enhanced")
   ```

### Mock Mode

For development without API keys, the services automatically enter mock mode:

- Realistic mock responses
- Same API interface as production
- Comprehensive test coverage
- Easy development setup

## 🔒 Security

### Authentication

- **OAuth 2.0**: Secure authentication flow
- **Token Encryption**: Fernet encryption for token storage
- **Token Refresh**: Automatic token refresh
- **Secure Storage**: Encrypted database storage

### Data Protection

- **HTTPS**: All communications encrypted
- **Input Validation**: Comprehensive input sanitization
- **Access Control**: User-scoped operations
- **Audit Trail**: Complete audit logging

## 📊 Monitoring & Logging

### Structured Logging

```json
{
  "timestamp": "2024-01-01T12:00:00Z",
  "level": "INFO",
  "service": "google-enhanced",
  "operation": "list_files",
  "user_id": "user123",
  "duration_ms": 150,
  "status": "success"
}
```

### Metrics

- **API Response Times**: Track performance
- **Error Rates**: Monitor service health
- **Usage Statistics**: Track API usage
- **User Activity**: Monitor user interactions

## 🚀 Deployment

### Docker Deployment

Build the Docker image:
```bash
docker build -t atom-enhanced-integrations .
```

Run with Docker Compose:
```bash
docker-compose up -d
```

### Production Deployment

1. **Environment Setup**: Configure production environment
2. **Database**: Set up PostgreSQL with migrations
3. **Redis**: Configure Redis for caching
4. **Load Balancer**: Set up nginx or similar
5. **SSL**: Configure SSL certificates
6. **Monitoring**: Set up monitoring and alerting

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch: `git checkout -b feature/new-feature`
3. Make changes and add tests
4. Run tests: `npm test && python test_enhanced_integrations.py`
5. Commit changes: `git commit -am 'Add new feature'`
6. Push to branch: `git push origin feature/new-feature`
7. Open a Pull Request

### Code Standards

- **TypeScript**: Strict typing for frontend
- **Python**: PEP 8 compliance
- **Testing**: 90%+ code coverage
- **Documentation**: Complete API documentation
- **Security**: Security review required

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🆘 Support

### Documentation

- [Enhanced Integrations Documentation](./ENHANCED_INTEGRATIONS_DOCUMENTATION.md)
- [API Reference](./API_REFERENCE.md)
- [Development Guide](./DEVELOPMENT_GUIDE.md)

### Issues

Report issues at: [GitHub Issues](https://github.com/your-org/atom/issues)

### Community

- [Discord Server](https://discord.gg/atom)
- [Discussion Forum](https://github.com/your-org/atom/discussions)

## 🗺️ Roadmap

### Q1 2024
- [ ] Real-time WebSocket updates
- [ ] Advanced batch operations
- [ ] Enhanced search capabilities
- [ ] Mobile app integration

### Q2 2024
- [ ] Additional SaaS integrations
- [ ] Custom API integrations
- [ ] Workflow automation builder
- [ ] Advanced analytics dashboard

### Q3 2024
- [ ] Machine learning integration
- [ ] Predictive analytics
- [ ] Advanced security features
- [ ] Enterprise SSO support

## 🎉 Acknowledgments

- **Google Workspace API** - For calendar, email, and drive APIs
- **Microsoft Graph API** - For Office 365 integration
- **Dropbox API** - For file storage and sharing
- **Open Source Community** - For valuable contributions

---

**Built with ❤️ by the ATOM Team**