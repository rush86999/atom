# 🚀 Atom Development Guide

This guide will help you set up and run the Atom personal assistant with all the newly completed features.

## 📋 Completed Features

The following core features have been implemented and are ready to use:

### ✅ Unified Calendar Service
- Multi-provider calendar integration (Google, Outlook, CalDAV)
- Real-time event synchronization
- Available time slot detection
- Database-backed event storage

### ✅ Task Management System
- Full CRUD operations for tasks
- Priority and status tracking
- Due date management
- Dashboard statistics

### ✅ Unified Messaging Hub
- Cross-platform message aggregation
- Read/unread status management
- Message search functionality
- Platform-based statistics

### ✅ Meeting Transcription Service
- Deepgram integration for real-time transcription
- Meeting summarization
- Action item extraction
- Key topic identification

### ✅ Database Integration
- PostgreSQL with connection pooling
- Secure OAuth token storage
- Efficient data modeling
- Automatic table initialization

## 🛠️ Setup Instructions

### Prerequisites

- Python 3.8+
- Node.js 16+
- PostgreSQL 12+
- Docker (optional, for containerized deployment)

### 1. Environment Configuration

Copy the example environment file and configure your settings:

```bash
cp .env.example .env
```

Edit `.env` with your actual values:

```env
# Database Configuration
DATABASE_URL=postgresql://username:password@localhost:5432/atom_development
DB_HOST=localhost
DB_PORT=5432
DB_NAME=atom_development
DB_USER=atom_user
DB_PASSWORD=CHANGE_THIS_PASSWORD

# API Keys for External Services
DEEPGRAM_API_KEY=your_deepgram_api_key_here
OPENAI_API_KEY=your_openai_api_key_here

# OAuth Configuration (for calendar integration)
GOOGLE_CLIENT_ID=your_google_oauth_client_id
GOOGLE_CLIENT_SECRET=your_google_oauth_client_secret
GOOGLE_REDIRECT_URI=http://localhost:3000/auth/google/callback

MICROSOFT_CLIENT_ID=your_microsoft_client_id
MICROSOFT_CLIENT_SECRET=your_microsoft_client_secret
MICROSOFT_REDIRECT_URI=http://localhost:3000/auth/microsoft/callback

# Flask Application
FLASK_SECRET_KEY=your_flask_secret_key
PYTHON_API_PORT=5058
```

### 2. Database Setup

#### Option A: Using Docker (Recommended)

```bash
# Start PostgreSQL with Docker
docker run -d \
  --name atom-postgres \
  -e POSTGRES_DB=atom_development \
  -e POSTGRES_USER=atom_user \
  -e POSTGRES_PASSWORD=CHANGE_THIS_PASSWORD \
  -p 5432:5432 \
  postgres:15-alpine

# Or use the provided docker-compose
docker-compose -f docker-compose.postgraphile.auth.yaml up -d
```

#### Option B: Manual PostgreSQL Setup

```sql
-- Connect to PostgreSQL and create database
CREATE DATABASE atom_development;
CREATE USER atom_user WITH PASSWORD 'CHANGE_THIS_PASSWORD';
GRANT ALL PRIVILEGES ON DATABASE atom_development TO atom_user;
```

### 3. Backend Setup

```bash
# Navigate to backend directory
cd atom/backend/python-api-service

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Initialize database tables
python init_database.py

# Start the backend server
python main_api_app.py
```

The backend API will be available at `http://localhost:5058`

### 4. Frontend Setup

```bash
# Navigate to frontend directory
cd atom/frontend-nextjs

# Install dependencies
npm install

# Start the development server
npm run dev
```

The frontend will be available at `http://localhost:3000`

### 5. Test the Integration

Run the comprehensive test script to verify all features:

```bash
# From the project root
python test_api_endpoints.py
```

## 🔧 API Endpoints

### Calendar Endpoints
- `GET /api/calendar/events` - Get user calendar events
- `POST /api/calendar/sync` - Force calendar synchronization
- `GET /api/calendar/available-slots` - Find available time slots
- `GET /api/calendar/providers` - List configured calendar providers

### Task Endpoints
- `GET /api/tasks` - Get user tasks
- `POST /api/tasks` - Create new task
- `PUT /api/tasks/{id}` - Update task
- `POST /api/tasks/{id}/complete` - Mark task as complete
- `DELETE /api/tasks/{id}` - Delete task
- `GET /api/tasks/stats` - Get task statistics

### Message Endpoints
- `GET /api/messages` - Get user messages
- `POST /api/messages/{id}/read` - Mark message as read
- `POST /api/messages/batch/read` - Mark multiple messages as read
- `DELETE /api/messages/{id}` - Delete message
- `GET /api/messages/stats` - Get message statistics
- `GET /api/messages/search` - Search messages

### Transcription Endpoints
- `POST /api/transcription/transcribe` - Transcribe meeting audio
- `GET /api/transcription/meetings/{id}` - Get meeting transcription
- `GET /api/transcription/meetings/{id}/summary` - Get meeting summary
- `GET /api/transcription/health` - Transcription service health

## 🗃️ Database Schema

The system uses the following main tables:

- `user_oauth_tokens` - Secure storage of OAuth tokens
- `tasks` - User task management
- `messages` - Unified message storage
- `calendar_events` - Calendar event synchronization
- `meeting_transcriptions` - Meeting transcripts and summaries
- `plaid_items` - Financial integration data

## 🔐 OAuth Configuration

### Google Calendar Setup
1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project or select existing one
3. Enable Google Calendar API
4. Create OAuth 2.0 credentials
5. Add `http://localhost:3000/auth/google/callback` as authorized redirect URI
6. Add client ID and secret to your `.env` file

### Microsoft Outlook Setup
1. Go to [Azure Portal](https://portal.azure.com/)
2. Register a new application
3. Add API permissions for `Calendars.Read`
4. Add `http://localhost:3000/auth/microsoft/callback` as redirect URI
5. Add client ID and secret to your `.env` file

## 🎯 Usage Examples

### Calendar Integration
```bash
# Sync calendars for a user
curl -X POST http://localhost:5058/api/calendar/sync \
  -H "Content-Type: application/json" \
  -d '{"user_id": "test_user_001"}'

# Get calendar events
curl "http://localhost:5058/api/calendar/events?user_id=test_user_001"
```

### Task Management
```bash
# Create a new task
curl -X POST http://localhost:5058/api/tasks \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "test_user_001",
    "task": {
      "title": "Complete project proposal",
      "description": "Finish the client project proposal document",
      "due_date": "2024-01-15T14:30:00Z",
      "priority": "high",
      "status": "todo"
    }
  }'
```

### Meeting Transcription
```bash
# Transcribe meeting audio (base64 encoded)
curl -X POST http://localhost:5058/api/transcription/transcribe \
  -H "Content-Type: application/json" \
  -d '{
    "meeting_id": "meeting_001",
    "audio_data": "base64-encoded-audio-data",
    "sample_rate": 16000,
    "language": "en-US"
  }'
```

## 🐛 Troubleshooting

### Common Issues

1. **Database Connection Errors**
   - Verify PostgreSQL is running
   - Check `DATABASE_URL` in `.env` file
   - Ensure database and user exist

2. **OAuth Configuration Issues**
   - Verify redirect URIs match exactly
   - Check client IDs and secrets
   - Ensure required API permissions are granted

3. **Deepgram Transcription Fails**
   - Verify `DEEPGRAM_API_KEY` is set
   - Check internet connection for API calls

4. **CORS Issues**
   - Ensure frontend and backend are on same origin or CORS is configured
   - Check port numbers in configuration

### Debug Mode

Enable debug mode for detailed logging:

```bash
# Set debug environment variable
export DEBUG=true  # On Windows: set DEBUG=true

# Or add to .env file
DEBUG=true
```

## 📈 Monitoring

Check service health:

```bash
# Backend health
curl http://localhost:5058/healthz

# Transcription service health
curl http://localhost:5058/api/transcription/health
```

## 🚀 Deployment

### Production Deployment

1. **Environment Variables**
   - Set `FLASK_ENV=production`
   - Use production database URL
   - Configure proper CORS origins
   - Set secure secret keys

2. **Database**
   - Use managed PostgreSQL service
   - Enable connection pooling
   - Set up regular backups

3. **Scaling**
   - Use Gunicorn for production WSGI server
   - Implement Redis for caching
   - Set up load balancing for high traffic

### Docker Deployment

```bash
# Build and run with Docker Compose
docker-compose -f docker-compose.postgraphile.auth.yaml up -d --build

# View logs
docker-compose logs -f
```

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests for new functionality
5. Submit a pull request

## 📞 Support

For issues and questions:

1. Check the troubleshooting section above
2. Review API documentation
3. Check existing GitHub issues
4. Create a new issue with detailed description

## 📄 License

This project is licensed under the terms of the LICENSE file included in the repository.

---

**Happy Coding!** 🎉 Your Atom personal assistant is now ready to help manage calendars, tasks, messages, and meetings seamlessly.