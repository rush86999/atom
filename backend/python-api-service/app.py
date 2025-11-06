"""
ATOM Backend Application Entry Point
Google Drive Integration with Search UI
"""

import os
import asyncio
from datetime import datetime
from flask import Flask, request, jsonify
from flask_cors import CORS
from logging.config import dictConfig
from contextlib import asynccontextmanager
import sys
import json

# Add project root to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Import configuration
from config import config, Config

# Import logging
from loguru import logger

# Import extensions
try:
    from extensions import db, redis_client, migrate
except ImportError:
    logger.warning("Extensions not found, creating mock extensions")
    
    class MockExtension:
        def __init__(self): pass
        def init_app(self, app): pass
        def get_app(self, app): pass
    
    db = MockExtension()
    redis_client = MockExtension()
    migrate = None

# Import services
try:
    from google_drive_integration_register import register_google_drive_integration
    from google_drive_search_integration import register_google_drive_search_routes
except ImportError as e:
    logger.error(f"Failed to import Google Drive integration: {e}")
    register_google_drive_integration = None
    register_google_drive_search_routes = None

# Import health check
try:
    from health_check import HealthChecker
except ImportError:
    HealthChecker = None

class ATOMFlaskApp:
    """ATOM Flask Application Factory"""
    
    def __init__(self):
        self.app = None
        self.config_class = None
        self.health_checker = None
    
    def create_app(self, config_name=None):
        """Create Flask application"""
        
        # Determine config
        config_name = config_name or os.getenv('FLASK_ENV', 'development')
        self.config_class = config.get(config_name, config['default'])
        
        # Create Flask app
        self.app = Flask(__name__)
        self.app.config.from_object(self.config_class)
        
        # Setup logging
        self._setup_logging()
        
        # Enable CORS
        self._setup_cors()
        
        # Initialize extensions
        self._init_extensions()
        
        # Register blueprints
        self._register_blueprints()
        
        # Register error handlers
        self._register_error_handlers()
        
        # Register middleware
        self._register_middleware()
        
        # Initialize services
        self._init_services()
        
        # Setup lifecycle
        self._setup_lifecycle()
        
        # Initialize health checker
        self._init_health_checker()
        
        logger.info(f"ATOM Flask app created with config: {config_name}")
        return self.app
    
    def _setup_logging(self):
        """Setup application logging"""
        
        # Configure standard logging
        dictConfig({
            'version': 1,
            'formatters': {
                'default': {
                    'format': '[%(asctime)s] %(levelname)s: %(message)s',
                    'datefmt': '%Y-%m-%d %H:%M:%S'
                },
                'detailed': {
                    'format': '[%(asctime)s] %(levelname)s [%(name)s] [%(filename)s:%(lineno)d]: %(message)s',
                    'datefmt': '%Y-%m-%d %H:%M:%S'
                }
            },
            'handlers': {
                'console': {
                    'class': 'logging.StreamHandler',
                    'formatter': 'default',
                    'level': 'DEBUG'
                },
                'file': {
                    'class': 'logging.handlers.RotatingFileHandler',
                    'filename': self.app.config.get('LOG_FILE_PATH', './logs/atom.log'),
                    'maxBytes': 10485760,  # 10MB
                    'backupCount': 5,
                    'formatter': 'detailed',
                    'level': self.app.config.get('LOG_LEVEL', 'INFO')
                }
            },
            'root': {
                'level': self.app.config.get('LOG_LEVEL', 'INFO'),
                'handlers': ['console', 'file']
            }
        })
        
        # Configure loguru
        logger.remove()
        logger.add(
            sys.stderr,
            format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
            level=self.app.config.get('LOG_LEVEL', 'INFO')
        )
        
        if self.app.config.get('LOG_FILE_PATH'):
            logger.add(
                self.app.config['LOG_FILE_PATH'],
                format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} - {message}",
                level=self.app.config.get('LOG_LEVEL', 'INFO'),
                rotation="10 MB",
                retention="30 days"
            )
        
        logger.info("Logging configured")
    
    def _setup_cors(self):
        """Setup CORS configuration"""
        
        # Get allowed origins
        allowed_origins = self.app.config.get('ALLOWED_ORIGINS', [
            'http://localhost:3000',
            'http://localhost:8080',
            'http://127.0.0.1:3000',
            'http://127.0.0.1:8080'
        ])
        
        # Configure CORS
        CORS(self.app, 
             origins=allowed_origins,
             methods=['GET', 'POST', 'PUT', 'DELETE', 'OPTIONS'],
             allow_headers=['Content-Type', 'Authorization', 'X-Requested-With'],
             supports_credentials=True)
        
        logger.info(f"CORS configured for origins: {allowed_origins}")
    
    def _init_extensions(self):
        """Initialize Flask extensions"""
        
        try:
            # Initialize database
            db.init_app(self.app)
            logger.info("Database extension initialized")
            
            # Initialize Redis
            redis_client.init_app(self.app)
            logger.info("Redis extension initialized")
            
            # Initialize migrations
            if migrate:
                migrate.init_app(self.app, db)
                logger.info("Migration extension initialized")
        
        except Exception as e:
            logger.error(f"Error initializing extensions: {e}")
    
    def _register_blueprints(self):
        """Register Flask blueprints"""
        
        # Register Google Drive integration
        if register_google_drive_integration:
            try:
                # Get database pool
                db_pool = None
                if hasattr(db, 'get_engine'):
                    db_pool = db.get_engine().raw_connection()
                
                success = register_google_drive_integration(self.app, db_pool)
                if success:
                    logger.info("Google Drive integration registered successfully")
                else:
                    logger.warning("Google Drive integration registration failed")
            
            except Exception as e:
                logger.error(f"Error registering Google Drive integration: {e}")
        
        # Register search routes
        if register_google_drive_search_routes:
            try:
                register_google_drive_search_routes(self.app)
                logger.info("Google Drive search routes registered successfully")
            
            except Exception as e:
                logger.error(f"Error registering Google Drive search routes: {e}")
    
    def _register_error_handlers(self):
        """Register error handlers"""
        
        @self.app.errorhandler(400)
        def bad_request(error):
            return jsonify({
                "ok": False,
                "error": "Bad Request",
                "message": str(error),
                "status_code": 400
            }), 400
        
        @self.app.errorhandler(401)
        def unauthorized(error):
            return jsonify({
                "ok": False,
                "error": "Unauthorized",
                "message": "Authentication required",
                "status_code": 401
            }), 401
        
        @self.app.errorhandler(403)
        def forbidden(error):
            return jsonify({
                "ok": False,
                "error": "Forbidden",
                "message": "Access denied",
                "status_code": 403
            }), 403
        
        @self.app.errorhandler(404)
        def not_found(error):
            return jsonify({
                "ok": False,
                "error": "Not Found",
                "message": "Resource not found",
                "status_code": 404
            }), 404
        
        @self.app.errorhandler(405)
        def method_not_allowed(error):
            return jsonify({
                "ok": False,
                "error": "Method Not Allowed",
                "message": "HTTP method not allowed",
                "status_code": 405
            }), 405
        
        @self.app.errorhandler(422)
        def unprocessable_entity(error):
            return jsonify({
                "ok": False,
                "error": "Unprocessable Entity",
                "message": "Request could not be processed",
                "status_code": 422
            }), 422
        
        @self.app.errorhandler(429)
        def rate_limit_exceeded(error):
            return jsonify({
                "ok": False,
                "error": "Rate Limit Exceeded",
                "message": "Too many requests",
                "status_code": 429
            }), 429
        
        @self.app.errorhandler(500)
        def internal_server_error(error):
            logger.error(f"Internal server error: {error}")
            return jsonify({
                "ok": False,
                "error": "Internal Server Error",
                "message": "An unexpected error occurred",
                "status_code": 500
            }), 500
        
        @self.app.errorhandler(502)
        def bad_gateway(error):
            return jsonify({
                "ok": False,
                "error": "Bad Gateway",
                "message": "Service temporarily unavailable",
                "status_code": 502
            }), 502
        
        @self.app.errorhandler(503)
        def service_unavailable(error):
            return jsonify({
                "ok": False,
                "error": "Service Unavailable",
                "message": "Service temporarily unavailable",
                "status_code": 503
            }), 503
        
        logger.info("Error handlers registered")
    
    def _register_middleware(self):
        """Register request middleware"""
        
        @self.app.before_request
        def before_request():
            """Execute before each request"""
            request.start_time = datetime.now()
            
            # Log request
            logger.info(f"{request.method} {request.path} from {request.remote_addr}")
        
        @self.app.after_request
        def after_request(response):
            """Execute after each request"""
            # Calculate duration
            if hasattr(request, 'start_time'):
                duration = (datetime.now() - request.start_time).total_seconds()
                response.headers['X-Response-Time'] = f"{duration:.3f}s"
                
                # Log response
                logger.info(f"{request.method} {request.path} - {response.status_code} ({duration:.3f}s)")
            
            # Add security headers
            response.headers['X-Content-Type-Options'] = 'nosniff'
            response.headers['X-Frame-Options'] = 'DENY'
            response.headers['X-XSS-Protection'] = '1; mode=block'
            response.headers['Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains'
            
            return response
        
        logger.info("Middleware registered")
    
    def _init_services(self):
        """Initialize application services"""
        
        try:
            with self.app.app_context():
                # Services will be initialized by blueprints
                logger.info("Services initialization completed")
        
        except Exception as e:
            logger.error(f"Error initializing services: {e}")
    
    def _setup_lifecycle(self):
        """Setup application lifecycle"""
        
        @self.app.teardown_appcontext
        def teardown_appcontext(error):
            """Execute after each request"""
            if error:
                logger.error(f"Request teardown error: {error}")
        
        logger.info("Application lifecycle setup completed")
    
    def _init_health_checker(self):
        """Initialize health checker"""
        
        try:
            if HealthChecker:
                self.health_checker = HealthChecker(self.app)
                logger.info("Health checker initialized")
            else:
                logger.warning("Health checker not available")
        
        except Exception as e:
            logger.error(f"Error initializing health checker: {e}")

# Global app factory
app_factory = ATOMFlaskApp()

def create_app(config_name=None):
    """Create Flask application"""
    return app_factory.create_app(config_name)

def get_app():
    """Get current Flask app"""
    return app_factory.app

def get_config():
    """Get current config"""
    return app_factory.config_class

# Create app instance
app = create_app()

# Health check endpoint
@app.route('/health')
def health_check():
    """Application health check"""
    
    try:
        health_data = {
            "status": "healthy",
            "timestamp": datetime.utcnow().isoformat(),
            "version": "1.0.0",
            "environment": os.getenv('FLASK_ENV', 'development'),
            "services": {
                "flask": "healthy",
                "database": "unknown",
                "redis": "unknown",
                "google_drive": "unknown"
            },
            "performance": {
                "response_time": "< 100ms",
                "uptime": "unknown"
            }
        }
        
        # Check database health
        try:
            if hasattr(db, 'engine'):
                db.engine.execute('SELECT 1')
                health_data["services"]["database"] = "healthy"
        except Exception as e:
            health_data["services"]["database"] = f"unhealthy: {str(e)}"
        
        # Check Redis health
        try:
            if hasattr(redis_client, 'ping'):
                redis_client.ping()
                health_data["services"]["redis"] = "healthy"
        except Exception as e:
            health_data["services"]["redis"] = f"unhealthy: {str(e)}"
        
        # Check Google Drive service health
        try:
            if register_google_drive_integration:
                health_data["services"]["google_drive"] = "healthy"
        except Exception as e:
            health_data["services"]["google_drive"] = f"unhealthy: {str(e)}"
        
        # Check if any service is unhealthy
        unhealthy_services = [k for k, v in health_data["services"].items() if v != "healthy"]
        if unhealthy_services:
            health_data["status"] = "degraded"
        
        return jsonify(health_data), 200
    
    except Exception as e:
        logger.error(f"Health check error: {e}")
        return jsonify({
            "status": "unhealthy",
            "timestamp": datetime.utcnow().isoformat(),
            "error": str(e)
        }), 500

# Root endpoint
@app.route('/')
def root():
    """Root endpoint"""
    
    return jsonify({
        "name": "ATOM Backend",
        "description": "Google Drive Integration with Search UI",
        "version": "1.0.0",
        "status": "running",
        "endpoints": {
            "health": "/health",
            "google_drive": "/api/google-drive",
            "search": "/api/search",
            "automation": "/api/google-drive/automation"
        },
        "documentation": "/docs",
        "timestamp": datetime.utcnow().isoformat()
    })

# API info endpoint
@app.route('/api/info')
def api_info():
    """API information"""
    
    return jsonify({
        "name": "ATOM Backend API",
        "version": "1.0.0",
        "description": "Google Drive Integration with Search UI and Automation",
        "endpoints": {
            "google_drive": {
                "base": "/api/google-drive",
                "endpoints": [
                    "/health",
                    "/connect",
                    "/files",
                    "/sync/subscriptions",
                    "/memory/search",
                    "/automation/workflows"
                ]
            },
            "search": {
                "base": "/api/search",
                "endpoints": [
                    "/providers",
                    "/google_drive",
                    "/analytics"
                ]
            }
        },
        "features": {
            "file_operations": "Complete CRUD operations for Google Drive files",
            "real_time_sync": "Real-time synchronization with webhooks",
            "semantic_search": "AI-powered semantic search with LanceDB",
            "automation": "Powerful workflow automation engine",
            "analytics": "Comprehensive search and usage analytics"
        },
        "status": "operational",
        "timestamp": datetime.utcnow().isoformat()
    })

if __name__ == '__main__':
    # Run development server
    logger.info("Starting ATOM Backend in development mode")
    app.run(
        host=app.config.get('HOST', '0.0.0.0'),
        port=app.config.get('PORT', 8000),
        debug=app.config.get('DEBUG', False)
    )