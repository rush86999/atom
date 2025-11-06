# ATOM Google Drive Integration - Setup Guide

## 🎯 **Quick Start Guide**

### **1. Environment Setup**

```bash
# Clone the repository
git clone https://github.com/atom/backend.git
cd backend/python-api-service

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Install Google Drive specific dependencies
pip install google-api-python-client google-auth-oauthlib
pip install lancedb sentence-transformers
pip install flask asyncio aiohttp aiofiles
pip install pandas numpy
pip install loguru
pip install asyncpg redis
```

### **2. Environment Configuration**

Create `.env` file:
```env
# Google Drive API Configuration
GOOGLE_DRIVE_CLIENT_ID="your-google-client-id.apps.googleusercontent.com"
GOOGLE_DRIVE_CLIENT_SECRET="your-google-client-secret"
GOOGLE_DRIVE_REDIRECT_URI="http://localhost:8000/auth/google/callback"
GOOGLE_DRIVE_SCOPES="https://www.googleapis.com/auth/drive https://www.googleapis.com/auth/drive.file"

# LanceDB Configuration
LANCE_DB_PATH="/path/to/lancedb/data"
EMBEDDING_MODEL="all-MiniLM-L6-v2"

# Database Configuration
DATABASE_URL="postgresql://username:password@localhost:5432/atom"
REDIS_URL="redis://localhost:6379/0"

# Flask Configuration
FLASK_ENV="development"
FLASK_DEBUG=True
FLASK_HOST="0.0.0.0"
FLASK_PORT="8000"

# Search Configuration
SEARCH_PROVIDERS="google_drive,local,api"
SEARCH_INDEX_PATH="/path/to/search/index"

# Automation Configuration
WORKFLOW_ENGINE_ENABLED=True
MAX_CONCURRENT_WORKFLOWS=10
DEFAULT_WORKFLOW_TIMEOUT=300

# Logging Configuration
LOG_LEVEL="INFO"
LOG_FILE_PATH="/path/to/logs/atom.log"
```

### **3. Google Drive API Setup**

1. **Create Google Cloud Project**
   - Go to [Google Cloud Console](https://console.cloud.google.com/)
   - Create new project: "ATOM Google Drive Integration"

2. **Enable APIs**
   - Google Drive API
   - Google Drive API (v3)
   - OAuth 2.0 API

3. **Create OAuth 2.0 Credentials**
   - Go to "Credentials" → "Create Credentials" → "OAuth 2.0 Client ID"
   - Select "Web application"
   - Add authorized redirect URIs
   - Download JSON credentials file

4. **Configure OAuth Consent Screen**
   - Set application name: "ATOM"
   - Add developer contact information
   - Add required scopes

### **4. Database Setup**

```sql
-- Create database
CREATE DATABASE atom;

-- Create user
CREATE USER atom_user WITH PASSWORD 'your_password';
GRANT ALL PRIVILEGES ON DATABASE atom TO atom_user;

-- Connect to atom database
\c atom;

-- Create tables (schema will be created automatically by migrations)
```

### **5. Redis Setup**

```bash
# Install Redis
sudo apt-get install redis-server  # Ubuntu
brew install redis  # macOS

# Start Redis
sudo systemctl start redis-server
sudo systemctl enable redis-server

# Test Redis
redis-cli ping
```

### **6. Run the Application**

```bash
# Initialize database and tables
python scripts/init_database.py

# Start the Flask application
python app.py

# Or use Gunicorn for production
gunicorn -w 4 -b 0.0.0.0:8000 app:app
```

## 🔧 **Configuration Details**

### **Core Configuration (config.py)**
```python
import os
from typing import Dict, Any

class Config:
    # Flask Configuration
    SECRET_KEY = os.getenv('SECRET_KEY', 'dev-secret-key-change-in-production')
    DEBUG = os.getenv('FLASK_DEBUG', 'False').lower() == 'true'
    HOST = os.getenv('FLASK_HOST', '0.0.0.0')
    PORT = int(os.getenv('FLASK_PORT', 8000))
    
    # Google Drive Configuration
    GOOGLE_DRIVE_CLIENT_ID = os.getenv('GOOGLE_DRIVE_CLIENT_ID')
    GOOGLE_DRIVE_CLIENT_SECRET = os.getenv('GOOGLE_DRIVE_CLIENT_SECRET')
    GOOGLE_DRIVE_REDIRECT_URI = os.getenv('GOOGLE_DRIVE_REDIRECT_URI')
    GOOGLE_DRIVE_SCOPES = os.getenv('GOOGLE_DRIVE_SCOPES').split(',')
    
    # Database Configuration
    DATABASE_URL = os.getenv('DATABASE_URL')
    REDIS_URL = os.getenv('REDIS_URL')
    
    # Search Configuration
    LANCE_DB_PATH = os.getenv('LANCE_DB_PATH', './lancedb')
    EMBEDDING_MODEL = os.getenv('EMBEDDING_MODEL', 'all-MiniLM-L6-v2')
    
    # Automation Configuration
    WORKFLOW_ENGINE_ENABLED = os.getenv('WORKFLOW_ENGINE_ENABLED', 'True').lower() == 'true'
    MAX_CONCURRENT_WORKFLOWS = int(os.getenv('MAX_CONCURRENT_WORKFLOWS', 10))
    DEFAULT_WORKFLOW_TIMEOUT = int(os.getenv('DEFAULT_WORKFLOW_TIMEOUT', 300))
    
    # Logging Configuration
    LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO')
    LOG_FILE_PATH = os.getenv('LOG_FILE_PATH', './logs/atom.log')

class DevelopmentConfig(Config):
    DEBUG = True
    LOG_LEVEL = 'DEBUG'

class ProductionConfig(Config):
    DEBUG = False
    LOG_LEVEL = 'INFO'

class TestingConfig(Config):
    TESTING = True
    DATABASE_URL = 'sqlite:///test.db'
    REDIS_URL = 'redis://localhost:6379/1'

config = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'testing': TestingConfig,
    'default': DevelopmentConfig
}
```

### **Application Factory (app.py)**
```python
import os
from flask import Flask
from flask_cors import CORS
from logging.config import dictConfig
from config import config

def create_app(config_name=None):
    app = Flask(__name__)
    
    # Load configuration
    config_name = config_name or os.getenv('FLASK_ENV', 'development')
    app.config.from_object(config[config_name])
    
    # Setup logging
    setup_logging(app)
    
    # Enable CORS
    CORS(app, origins=['http://localhost:3000', 'http://localhost:8080'])
    
    # Initialize extensions
    init_extensions(app)
    
    # Register blueprints
    register_blueprints(app)
    
    # Initialize services
    init_services(app)
    
    return app

def setup_logging(app):
    """Setup application logging"""
    dictConfig({
        'version': 1,
        'formatters': {
            'default': {
                'format': '[%(asctime)s] %(levelname)s: %(message)s',
                'datefmt': '%Y-%m-%d %H:%M:%S'
            }
        },
        'handlers': {
            'file': {
                'class': 'logging.FileHandler',
                'filename': app.config['LOG_FILE_PATH'],
                'formatter': 'default',
                'level': app.config['LOG_LEVEL']
            },
            'console': {
                'class': 'logging.StreamHandler',
                'formatter': 'default',
                'level': app.config['LOG_LEVEL']
            }
        },
        'root': {
            'level': app.config['LOG_LEVEL'],
            'handlers': ['file', 'console']
        }
    })

def init_extensions(app):
    """Initialize Flask extensions"""
    from extensions import db, redis_client
    db.init_app(app)
    redis_client.init_app(app)

def register_blueprints(app):
    """Register Flask blueprints"""
    from google_drive_integration_register import register_google_drive_integration
    register_google_drive_integration(app)

def init_services(app):
    """Initialize application services"""
    with app.app_context():
        from google_drive_service import get_google_drive_service
        from google_drive_memory import get_google_drive_memory_service
        from google_drive_automation import get_google_drive_automation_service
        
        # Initialize services
        drive_service = get_google_drive_service()
        memory_service = get_google_drive_memory_service()
        automation_service = get_google_drive_automation_service()
        
        print(f"✅ Google Drive services initialized")
        print(f"   - Drive Service: {'✅' if drive_service else '❌'}")
        print(f"   - Memory Service: {'✅' if memory_service else '❌'}")
        print(f"   - Automation Service: {'✅' if automation_service else '❌'}")

if __name__ == '__main__':
    app = create_app()
    app.run(host='0.0.0.0', port=8000, debug=True)
```

## 🧪 **Testing Setup**

### **Run Tests**
```bash
# Install test dependencies
pip install pytest pytest-flask pytest-asyncio pytest-cov

# Run all tests
pytest tests/ -v

# Run with coverage
pytest tests/ --cov=google_drive --cov-report=html

# Run specific test file
pytest tests/test_google_drive_service.py -v
```

### **Test Configuration (pytest.ini)**
```ini
[tool:pytest]
testpaths = tests
python_files = test_*.py
python_classes = Test*
python_functions = test_*
addopts = -v --tb=short
asyncio_mode = auto
```

## 🐳 **Docker Setup**

### **Dockerfile**
```dockerfile
FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application
COPY . .

# Create non-root user
RUN useradd -m -u 1000 atom && chown -R atom:atom /app
USER atom

# Expose port
EXPOSE 8000

# Start application
CMD ["gunicorn", "-w", "4", "-b", "0.0.0.0:8000", "app:app"]
```

### **Docker Compose (docker-compose.yml)**
```yaml
version: '3.8'

services:
  app:
    build: .
    ports:
      - "8000:8000"
    environment:
      - FLASK_ENV=production
      - DATABASE_URL=postgresql://atom:password@db:5432/atom
      - REDIS_URL=redis://redis:6379/0
    depends_on:
      - db
      - redis
    volumes:
      - ./lancedb:/app/lancedb
      - ./logs:/app/logs

  db:
    image: postgres:15
    environment:
      - POSTGRES_DB=atom
      - POSTGRES_USER=atom
      - POSTGRES_PASSWORD=password
    volumes:
      - postgres_data:/var/lib/postgresql/data
    ports:
      - "5432:5432"

  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"
    volumes:
      - redis_data:/data

volumes:
  postgres_data:
  redis_data:
```

### **Docker Commands**
```bash
# Build and start services
docker-compose up --build

# Run in background
docker-compose up -d

# View logs
docker-compose logs -f app

# Stop services
docker-compose down
```

## 📊 **Monitoring & Health Checks**

### **Health Check Endpoint**
```python
@app.route('/health')
def health_check():
    return {
        'status': 'healthy',
        'timestamp': datetime.utcnow().isoformat(),
        'services': {
            'google_drive': check_google_drive_health(),
            'lancedb': check_lancedb_health(),
            'database': check_database_health(),
            'redis': check_redis_health()
        }
    }
```

### **Health Check Script**
```bash
#!/bin/bash
# health_check.sh

HEALTH_URL="http://localhost:8000/health"
RESPONSE=$(curl -s -o /dev/null -w "%{http_code}" $HEALTH_URL)

if [ $RESPONSE -eq 200 ]; then
    echo "✅ Application is healthy"
    exit 0
else
    echo "❌ Application is unhealthy (HTTP $RESPONSE)"
    exit 1
fi
```

## 🔍 **Troubleshooting**

### **Common Issues**

1. **Google Drive OAuth Error**
   - Check CLIENT_ID and CLIENT_SECRET in .env
   - Verify redirect URI matches Google Console
   - Ensure required scopes are enabled

2. **Database Connection Error**
   - Verify DATABASE_URL format
   - Check database is running
   - Confirm user has correct permissions

3. **LanceDB Error**
   - Check LANCE_DB_PATH permissions
   - Ensure disk space is available
   - Verify embedding model is accessible

4. **Redis Connection Error**
   - Check REDIS_URL format
   - Verify Redis server is running
   - Test with `redis-cli ping`

### **Debug Mode**
```python
# Enable debug logging
import logging
logging.basicConfig(level=logging.DEBUG)

# Check service status
from google_drive_service import get_google_drive_service
service = get_google_drive_service()
print(f"Drive Service Status: {service is not None}")
```

## 📚 **Next Steps**

After completing the setup:

1. **Test Core Services**
   - Google Drive authentication
   - File upload/download
   - Semantic search

2. **Configure Workflows**
   - Create automation workflows
   - Set up triggers and actions
   - Test workflow execution

3. **Integrate with Search UI**
   - Register search provider
   - Test search functionality
   - Configure filters and facets

4. **Monitor Performance**
   - Set up monitoring dashboards
   - Configure alerts
   - Optimize based on metrics

## 🆘 **Support**

For issues:
1. Check logs in `./logs/atom.log`
2. Run health check script
3. Review troubleshooting guide
4. Create GitHub issue with details

---

**🎉 Setup Complete! Your ATOM Google Drive integration is ready to use!**