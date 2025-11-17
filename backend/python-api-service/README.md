# ATOM Backend API Service

Advanced Task Orchestration & Management Backend API built with Flask, PostgreSQL, and WebSocket support.

## Architecture & Technology Stack

### Core Framework

- **Flask** with application factory pattern
- **SQLAlchemy** for ORM with PostgreSQL database
- **Flask-JWT-Extended** for authentication
- **Flask-SocketIO** for real-time WebSocket communication
- **Flask-Migrate** for database migrations

### Key Dependencies

- **Database**: PostgreSQL with psycopg2-binary
- **WebSocket**: Socket.IO with Redis message queue
- **Authentication**: JWT tokens with bcrypt password hashing
- **External APIs**: Requests, httpx for integrations
- **Monitoring**: psutil for system metrics, sentry-sdk for error tracking
- **AI/ML**: OpenAI, Anthropic, scikit-learn, transformers, torch
- **Background Jobs**: Celery with Redis broker

### Database Models (13 Core Entities)

- **User** - Core user management with preferences and settings
- **Task** - Task management with status, priority, due dates, subtasks
- **CalendarEvent** - Calendar events with recurrence and attendees
- **Message** - Unified messaging across platforms (Gmail, Slack, Teams)
- **Integration** - Third-party service connections and sync status
- **Workflow** - Automation workflows with triggers and actions
- **Note** - Personal and event-related notes
- **Transaction** - Financial transaction tracking
- **VoiceCommand** - Voice command definitions and usage tracking
- **AgentLog** - AI agent execution logs
- **DevProject** - Development project tracking

## API Endpoints Structure

### Authentication (/api/auth)

- User registration/login with JWT tokens
- Profile management and password changes
- Account deactivation

### Tasks (/api/tasks)

- Full CRUD operations with real-time updates
- Task statistics and filtering
- WebSocket notifications for task changes

### Calendar (/api/calendar)

- Event management with recurrence support
- Availability checking and scheduling
- Monthly/yearly event queries

### Communications (/api/communications)

- Unified messaging across platforms
- Message sync and status management
- Communication statistics

### Integrations (/api/integrations)

- Service connection management
- OAuth flows and sync operations
- Integration health monitoring

### Workflows (/api/workflows)

- Workflow creation and execution
- Template system for common automations
- Trigger-action based automation

### Agents (/api/agents)

- AI agent management and execution
- Agent performance tracking
- Specialized agents (Scheduler, Researcher, Communicator, Coder)

### Finances (/api/finances)

- Transaction tracking and categorization
- Financial summaries and insights
- Budget management

### Voice (/api/voice)

- Voice command processing and management
- Wake word and language support
- Voice command execution

### Health (/api/health)

- System health monitoring
- Performance metrics and alerts
- WebSocket health checks

## Key Features Implemented

### Real-time Communication

- WebSocket support with Socket.IO
- Real-time updates for tasks, calendar, messages
- Room-based communication for user-specific events

### Comprehensive Validation

- Input validation for all endpoints
- Data sanitization and type checking
- Business logic validation

### Error Handling & Logging

- Structured logging with configurable levels
- Comprehensive error handlers (400, 401, 403, 404, 500)
- Request logging middleware

### Security Features

- JWT-based authentication
- Password hashing with bcrypt
- CORS configuration
- Input sanitization

### Monitoring & Health Checks

- System resource monitoring (CPU, memory, disk)
- Database connectivity checks
- WebSocket health monitoring
- Performance metrics collection

### Configuration & Deployment

- Environment Configuration
  - Multiple config classes (Development, Production, Testing)
  - Environment variable-based configuration
  - Redis and database connection pooling
- Docker Support
  - Multi-service Docker Compose setup
  - PostgreSQL, Redis, and Celery workers
  - Health checks and restart policies
  - Production-ready Dockerfile with gunicorn

### Development Tools

- Comprehensive requirements.txt with categorized dependencies
- pytest for testing framework
- Black, flake8 for code quality
- Development database seeding

## Current Status

### ✅ Completed Phases

- **Phase 1: Core Infrastructure** - Flask setup, DB models, auth, WebSocket
- **Phase 2: API Development** - All major APIs implemented

### 🔄 In Progress

- **Phase 3: Advanced Features** - integrations, workflows, AI agents
- **Phase 4: Production Readiness** - CI/CD, monitoring, security

### 📋 Planned Features

- Real integrations with Google, Slack, GitHub
- AI agent capabilities with OpenAI/Anthropic
- Voice recognition and NLP
- Advanced analytics and reporting
- Multi-tenant architecture
- Mobile optimization

## Code Quality & Structure

### Well-Organized Architecture

- Clear separation of concerns (routes, models, utils)
- Consistent error handling patterns
- Comprehensive data validation
- Modular blueprint structure

### Production-Ready Features

- Database migrations with Alembic
- Environment-based configuration
- Docker containerization
- Health monitoring and logging
- Security best practices

### Extensible Design

- Plugin-like integration system
- Workflow automation framework
- Agent-based AI architecture
- Modular API design

## Features

- **Authentication & Authorization**: JWT-based authentication with role-based access control
- **Real-time Communication**: WebSocket support for live updates using Socket.IO
- **Task Management**: Complete CRUD operations for tasks with priority, status, and due dates
- **Calendar Integration**: Event management with recurring events and availability checking
- **Communication Hub**: Unified messaging across Gmail, Slack, Teams, and other platforms
- **Integration Framework**: Connect with 20+ services including Google Calendar, GitHub, Slack, etc.
- **Workflow Automation**: Create and execute automated workflows with triggers and actions
- **Autonomous Agents**: AI-powered agents for task execution and decision making
- **Voice Commands**: Voice-activated commands with natural language processing
- **Financial Tracking**: Transaction management and financial insights
- **Health Monitoring**: System and application health metrics and alerts
- **Advanced Analytics**: Performance monitoring and usage analytics

## Tech Stack

- **Backend**: Flask 2.3+ with SQLAlchemy
- **Database**: PostgreSQL with Flask-Migrate
- **Real-time**: Flask-SocketIO with Redis
- **Authentication**: Flask-JWT-Extended
- **Validation**: Marshmallow schemas
- **Caching**: Redis
- **Task Queue**: Celery
- **Monitoring**: Prometheus metrics
- **Documentation**: Flask-RESTX

## Quick Start

### Prerequisites

- Python 3.9+
- PostgreSQL 13+
- Redis 6+
- Node.js 16+ (for frontend)

### Installation

1. **Clone the repository**

   ```bash
   git clone https://github.com/your-org/atom-backend.git
   cd atom-backend
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

4. **Set up environment variables**

   ```bash
   cp .env.example .env
   # Edit .env with your configuration
   ```

5. **Set up the database**

   ```bash
   # Create PostgreSQL database
   createdb atom_db

   # Run database migrations
   flask db upgrade
   ```

6. **Start Redis server**

   ```bash
   redis-server
   ```

7. **Run the application**

   ```bash
   # Development
   flask run

   # Production
   gunicorn --worker-class gevent --bind 0.0.0.0:3001 app:app
   ```

## API Endpoints

### Authentication

- `POST /api/auth/register` - User registration
- `POST /api/auth/login` - User login
- `POST /api/auth/refresh` - Refresh access token
- `GET /api/auth/profile` - Get user profile
- `PUT /api/auth/profile` - Update user profile

### Tasks

- `GET /api/tasks` - Get all tasks
- `POST /api/tasks` - Create new task
- `GET /api/tasks/<id>` - Get specific task
- `PUT /api/tasks/<id>` - Update task
- `DELETE /api/tasks/<id>` - Delete task
- `GET /api/tasks/stats` - Get task statistics

### Calendar

- `GET /api/calendar/events` - Get calendar events
- `POST /api/calendar/events` - Create calendar event
- `PUT /api/calendar/events/<id>` - Update event
- `DELETE /api/calendar/events/<id>` - Delete event
- `GET /api/calendar/availability` - Check availability

### Communications

- `GET /api/communications/messages` - Get messages
- `POST /api/communications/messages/send` - Send message
- `PUT /api/communications/messages/<id>/read` - Mark as read
- `GET /api/communications/stats` - Get communication stats

### Integrations

- `GET /api/integrations` - Get user integrations
- `POST /api/integrations/<id>/connect` - Connect integration
- `POST /api/integrations/<id>/sync` - Sync integration data
- `GET /api/integrations/available` - Get available integrations

### Workflows

- `GET /api/workflows` - Get workflows
- `POST /api/workflows` - Create workflow
- `POST /api/workflows/<id>/execute` - Execute workflow
- `PUT /api/workflows/<id>/toggle` - Enable/disable workflow

### Agents

- `GET /api/agents` - Get available agents
- `POST /api/agents/<id>/execute` - Execute agent
- `GET /api/agents/logs` - Get agent logs

### Finances

- `GET /api/finances/transactions` - Get transactions
- `POST /api/finances/transactions` - Create transaction
- `GET /api/finances/summary` - Get financial summary
- `GET /api/finances/insights` - Get financial insights

### Voice

- `GET /api/voice/commands` - Get voice commands
- `POST /api/voice/commands` - Create voice command
- `POST /api/voice/process` - Process voice command

### Health

- `GET /api/health/metrics` - Get health metrics
- `GET /api/health/status` - Get system status
- `GET /api/health/alerts` - Get health alerts

## WebSocket Events

### Client to Server

- `join` - Join a room for real-time updates
- `leave` - Leave a room

### Server to Client

- `task:created` - New task created
- `task:updated` - Task updated
- `task:deleted` - Task deleted
- `calendar:event:created` - Calendar event created
- `message:new` - New message received
- `integration:synced` - Integration data synced
- `workflow:executed` - Workflow executed
- `agent:log` - Agent activity logged

## Development

### Running Tests

```bash
pytest
```

### Code Quality

```bash
# Format code
black .

# Lint code
flake8 .

# Type checking
mypy .
```

### Database Migrations

```bash
# Create migration
flask db migrate -m "Migration message"

# Apply migration
flask db upgrade

# Rollback migration
flask db downgrade
```

## Deployment

### Docker

```bash
# Build image
docker build -t atom-backend .

# Run container
docker run -p 3001:3001 atom-backend
```

### Docker Compose

```yaml
version: '3.8'
services:
  atom-backend:
    build: .
    ports:
      - '3001:3001'
    environment:
      - DATABASE_URL=postgresql://user:password@db:5432/atom_db
      - REDIS_URL=redis://redis:6379/0
    depends_on:
      - db
      - redis

  db:
    image: postgres:13
    environment:
      - POSTGRES_DB=atom_db
      - POSTGRES_USER=user
      - POSTGRES_PASSWORD=password

  redis:
    image: redis:6-alpine
```

## Configuration

Environment variables are documented in `.env.example`. Key configurations include:

- Database connection strings
- JWT secrets
- External API keys
- Redis configuration
- Email settings
- File upload limits

## Monitoring

The application includes comprehensive monitoring:

- **Health Checks**: `/api/health/status` and `/api/health/metrics`
- **Metrics**: Prometheus-compatible metrics endpoint
- **Logging**: Structured logging with configurable levels
- **Performance**: Response time tracking and database query monitoring

## Security

- JWT token-based authentication
- Password hashing with bcrypt
- CORS protection
- Rate limiting
- Input validation and sanitization
- SQL injection prevention
- XSS protection

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests
5. Submit a pull request

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Support

For support and questions:

- Create an issue on GitHub
- Check the documentation
- Join our Discord community

## Roadmap

- [ ] GraphQL API support
- [ ] Advanced AI agent capabilities
- [ ] Mobile app API
- [ ] Advanced analytics dashboard
- [ ] Multi-tenant architecture
- [ ] Advanced workflow builder UI
- [ ] Voice command expansion
- [ ] Real-time collaboration features
