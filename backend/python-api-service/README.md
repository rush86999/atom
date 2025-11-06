# ATOM Backend - Enhanced Services

A comprehensive Python Flask backend providing enhanced integration capabilities for multiple services including Google Workspace, Microsoft 365, Slack, Notion, GitHub, and more.

## 🚀 Features

### Core Services
- **Enhanced Google Services**: Gmail, Calendar, Drive with advanced features
- **Microsoft 365 Integration**: Outlook, Teams, OneDrive
- **Communication Platforms**: Slack, Discord
- **Productivity Tools**: Notion, Asana, Trello, Linear
- **Development Tools**: GitHub, Jira, Figma
- **Workflow Automation**: Multi-service workflow orchestration
- **Voice Integration**: Voice-enabled API interactions

### Enhanced Google Services (NEW)
- **Gmail Enhanced**: Advanced email management, AI analytics, smart categorization
- **Calendar Enhanced**: Intelligent scheduling, recurring events, analytics
- **Drive Integration**: File management, search, collaboration features
- **OAuth Token Management**: Secure token storage and refresh handling

### Enhanced Salesforce Integration (NEW)
- **Account Management**: Comprehensive CRM account data and relationship management
- **Contact Management**: Advanced contact data with communication tracking
- **Opportunity Management**: Full sales pipeline with forecasting and analytics
- **Lead Management**: Lead scoring, conversion tracking, and nurturing
- **Advanced Analytics**: Sales intelligence, pipeline analysis, and reporting
- **OAuth Token Management**: Enterprise-grade token storage and refresh handling

### Key Capabilities
- 🔄 Real-time synchronization
- 🔐 Secure OAuth 2.0 authentication
- 📊 Advanced analytics and reporting
- 🤖 AI-powered features
- 🛡️ Enterprise-grade security
- 📈 Scalable architecture
- 🌐 RESTful API design
- 📱 Mobile-friendly endpoints

## 📁 Project Structure

```
python-api-service/
├── main_api_app.py              # Main Flask application
├── gmail_enhanced_api.py        # Enhanced Gmail API
├── calendar_enhanced_api.py     # Enhanced Calendar API
├── db_oauth_google.py           # Google OAuth database handler
├── auth_handler_*.py           # OAuth handlers for various services
├── *_enhanced_api.py           # Enhanced API modules
├── db_oauth_*.py              # Database OAuth handlers
├── workflow_*.py              # Workflow management
├── voice_integration_api.py    # Voice integration
├── storage_*.py               # Storage APIs
├── sync/                     # Synchronization services
├── integrations/              # Service integrations
├── tests/                     # Test suite
├── .env.google.template       # Google services environment template
├── README_GOOGLE_ENHANCED.md # Detailed Google services documentation
└── test_google_enhanced.py    # Google services test suite
```

## 🛠️ Installation

### Prerequisites
- Python 3.8+
- PostgreSQL 12+
- Redis (for caching)
- Node.js 14+ (for frontend)

### Quick Start

1. **Clone the repository**
```bash
git clone https://github.com/your-org/atom-backend.git
cd atom-backend/python-api-service
```

2. **Create virtual environment**
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. **Install dependencies**
```bash
pip install -r requirements.txt
```

4. **Configure environment variables**
```bash
# Copy Google services template
cp .env.google.template .env

# Edit with your configuration
nano .env
```

5. **Set up database**
```bash
# Create database
createdb atom

# Run migrations (if available)
python migrate.py
```

6. **Start the application**
```bash
python main_api_app.py
```

The API will be available at `http://localhost:8000`

## 🔐 Authentication Setup

### Google Services
1. Create Google Cloud Project
2. Enable required APIs (Gmail, Calendar, Drive)
3. Create OAuth 2.0 credentials
4. Configure environment variables

### Microsoft 365
1. Register app in Azure AD
2. Configure API permissions
3. Set up OAuth redirect URI

### Other Services
- **Slack**: Create Slack app
- **GitHub**: Register OAuth app
- **Notion**: Create integration
- **Jira**: Configure OAuth

## 📚 API Documentation

### Enhanced Google Services

#### Gmail API
```bash
# List messages
POST /api/gmail/enhanced/messages/list
{
  "user_id": "user123",
  "query": "is:unread",
  "max_results": 10
}

# Send message
POST /api/gmail/enhanced/messages/send
{
  "user_id": "user123",
  "message": {
    "to": "recipient@example.com",
    "subject": "Test Email",
    "body": "Hello from ATOM!"
  }
}
```

#### Calendar API
```bash
# Create event
POST /api/calendar/enhanced/events/create
{
  "user_id": "user123",
  "event": {
    "summary": "Team Meeting",
    "start": {"datetime": "2025-11-10T10:00:00Z"},
    "end": {"datetime": "2025-11-10T11:00:00Z"}
  }
}
```

### Other Services

See service-specific documentation:
- [Enhanced Google Services](./README_GOOGLE_ENHANCED.md)
- [Enhanced Salesforce Integration](./README_SALESFORCE_ENHANCED.md)
- [Microsoft 365 Integration](./README_MS365.md)
- [Slack Integration](./README_SLACK.md)
- [Notion Integration](./README_NOTION.md)

## 🧪 Testing

### Run Test Suite
```bash
# Test all services
python test_google_enhanced.py

# Test specific modules
python -m pytest tests/gmail_enhanced/
python -m pytest tests/calendar_enhanced/

# Run integration tests
python -m pytest tests/integration/
```

### Health Checks
```bash
# Application health
curl http://localhost:8000/healthz

# Google services health
curl -X POST http://localhost:8000/api/gmail/enhanced/health \
  -H "Content-Type: application/json" \
  -d '{"user_id": "test"}'

curl -X POST http://localhost:8000/api/calendar/enhanced/health \
  -H "Content-Type: application/json" \
  -d '{"user_id": "test"}'
```

## 📊 Monitoring

### Built-in Monitoring
- **Health Endpoints**: `/healthz`, `/api/*/health`
- **Metrics**: `/metrics` (Prometheus format)
- **Logging**: Structured JSON logging
- **Performance**: Request timing and error tracking

### Monitoring Stack
- **Prometheus**: Metrics collection
- **Grafana**: Visualization dashboards
- **ELK Stack**: Log aggregation
- **Jaeger**: Distributed tracing

## 🔧 Configuration

### Environment Variables
Key configuration options:

```bash
# Application
PYTHON_API_PORT=8000
FLASK_SECRET_KEY=your-secret-key

# Database
DB_HOST=localhost
DB_PORT=5432
DB_NAME=atom
DB_USER=postgres
DB_PASSWORD=password

# Google Services
GOOGLE_CLIENT_ID=your-google-client-id
GOOGLE_CLIENT_SECRET=your-google-client-secret

# Security
JWT_SECRET_KEY=your-jwt-secret
ENCRYPTION_KEY=your-encryption-key
```

### Service Configuration
Each service has its own configuration file:
- `config/google.py`: Google services
- `config/microsoft.py`: Microsoft 365
- `config/slack.py`: Slack integration

## 🚀 Deployment

### Docker
```bash
# Build image
docker build -t atom-backend .

# Run container
docker run -p 8000:8000 --env-file .env atom-backend
```

### Kubernetes
```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: atom-backend
spec:
  replicas: 3
  selector:
    matchLabels:
      app: atom-backend
  template:
    metadata:
      labels:
        app: atom-backend
    spec:
      containers:
      - name: atom-backend
        image: atom-backend:latest
        ports:
        - containerPort: 8000
```

### Production Considerations
- **Load Balancing**: Use reverse proxy (nginx/traefik)
- **SSL/TLS**: Enable HTTPS with Let's Encrypt
- **Rate Limiting**: Configure request throttling
- **Monitoring**: Set up alerting and dashboards
- **Backups**: Regular database and file backups

## 🤝 Contributing

### Development Workflow
1. Fork repository
2. Create feature branch
3. Write tests for new features
4. Ensure all tests pass
5. Submit pull request

### Code Standards
- **Python**: Follow PEP 8
- **Type Hints**: Add type annotations
- **Tests**: Minimum 80% code coverage
- **Documentation**: Update README and API docs
- **Security**: Follow security best practices

### Development Setup
```bash
# Install development dependencies
pip install -r requirements-dev.txt

# Set up pre-commit hooks
pre-commit install

# Run development server
python main_api_app.py --debug
```

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🆘 Support

### Getting Help
- **Documentation**: [Read the Docs](https://atom-docs.com)
- **Issues**: [GitHub Issues](https://github.com/your-org/atom-backend/issues)
- **Discussions**: [GitHub Discussions](https://github.com/your-org/atom-backend/discussions)
- **Discord**: [Community Server](https://discord.gg/atom)

### Troubleshooting
Common issues and solutions:

| Issue | Solution |
|-------|----------|
| OAuth token errors | Check client credentials and redirect URIs |
| Database connection errors | Verify database configuration and credentials |
| API rate limits | Implement request throttling and caching |
| Service timeouts | Adjust timeout values in configuration |

## 📈 Roadmap

### Upcoming Features
- [ ] **Enhanced Google Drive**: Advanced file management
- [ ] **AI Integration**: ChatGPT/GPT-4 integration
- [ ] **Real-time Notifications**: WebSocket support
- [ ] **Mobile API**: Native mobile app support
- [ ] **Enterprise Features**: SSO, RBAC, audit logs

### Version History
- **v3.0.0** (2025-11-05): Enhanced Google Services release
- **v2.5.0**: Microsoft 365 integration
- **v2.0.0**: Workflow automation
- **v1.0.0**: Initial release

---

**Built with ❤️ by the ATOM Team**

For detailed API documentation and guides, see our [documentation portal](https://docs.atom.com).