"""
ATOM Platform - Main Flask Application
Production-ready Flask application with Google Drive and Zendesk integrations
"""

import os
import sys
import asyncio
import logging
from datetime import datetime
from flask import Flask, jsonify, send_from_directory
from flask_cors import CORS
from flask_sqlalchemy import SQLAlchemy
from flask_redis import FlaskRedis

# Add project root to path
project_root = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, project_root)

# Local imports
from loguru import logger
from config import get_config_instance, init_config
from extensions import db, redis_client
from health_check import init_health_checker, get_health_checker
from google_drive_routes import register_google_drive_routes
from google_drive_automation_routes import register_automation_routes

# Initialize Flask app
def create_app(config_name: str = None):
    """Create and configure Flask application"""
    
    # Initialize configuration
    config = init_config(config_name)
    
    # Create Flask app
    app = Flask(__name__)
    
    # Configure app
    app.config.update({
        'SECRET_KEY': config.security.secret_key,
        'DEBUG': config.debug,
        'HOST': config.host,
        'PORT': config.port,
        'FLASK_ENV': config_name or os.getenv('FLASK_ENV', 'development'),
        'SQLALCHEMY_DATABASE_URI': config.database.url,
        'SQLALCHEMY_TRACK_MODIFICATIONS': False,
        'SQLALCHEMY_ENGINE_OPTIONS': {
            'pool_size': config.database.pool_size,
            'max_overflow': config.database.max_overflow,
            'pool_timeout': config.database.pool_timeout,
            'pool_recycle': config.database.pool_recycle,
            'echo': config.database.echo
        },
        'REDIS_URL': config.redis.url,
        'GOOGLE_DRIVE_CLIENT_ID': config.google_drive.client_id,
        'GOOGLE_DRIVE_CLIENT_SECRET': config.google_drive.client_secret,
        'LANCE_DB_PATH': config.lancedb.path,
        'EMBEDDING_MODEL': config.lancedb.embedding_model,
        'SEARCH_ENABLED': config.search.enabled,
        'AUTOMATION_ENABLED': config.automation.enabled,
        'SYNC_ENABLED': config.sync.enabled,
        'INGESTION_ENABLED': config.ingestion.enabled
    })
    
    # Configure CORS
    cors_config = {
        "origins": config.security.allowed_origins,
        "methods": ["GET", "POST", "PUT", "DELETE", "OPTIONS"],
        "allow_headers": ["Content-Type", "Authorization", "X-Session-ID"],
        "supports_credentials": True
    }
    
    CORS(app, **cors_config)
    
    # Initialize extensions
    init_extensions(app)
    
    # Register blueprints
    register_blueprints(app)
    
    # Register error handlers
    register_error_handlers(app)
    
    # Register middleware
    register_middleware(app)
    
    # Initialize health checker
    init_health_checker(app)
    
    logger.info(f"Flask application created for environment: {config_name or 'default'}")
    logger.info(f"Debug mode: {config.debug}")
    logger.info(f"Database: {config.database.url}")
    logger.info(f"Redis: {config.redis.url}")
    
    return app

def init_extensions(app: Flask):
    """Initialize Flask extensions"""
    
    try:
        # Initialize SQLAlchemy
        db.init_app(app)
        
        # Initialize Redis
        redis_client.init_app(app)
        
        logger.info("Flask extensions initialized")
    
    except Exception as e:
        logger.error(f"Failed to initialize extensions: {e}")
        raise

def register_blueprints(app: Flask):
    """Register application blueprints"""
    
    try:
        # Register Google Drive routes
        register_google_drive_routes(app)
        
        # Register automation routes
        register_automation_routes(app)
        
        # Register Document Intelligence routes
        try:
            from document_intelligence_routes import register_document_intelligence_routes
            register_document_intelligence_routes(app)
            logger.info("Document Intelligence routes registered successfully")
        except ImportError as e:
            logger.warning(f"Document Intelligence integration not available: {e}")
        except Exception as e:
            logger.error(f"Failed to register Document Intelligence integration: {e}")
        
        # Register Cross-Service AI routes
        try:
            from cross_service_ai_routes import register_cross_service_ai_routes
            register_cross_service_ai_routes(app)
            logger.info("Cross-Service AI routes registered successfully")
        except ImportError as e:
            logger.warning(f"Cross-Service AI integration not available: {e}")
        except Exception as e:
            logger.error(f"Failed to register Cross-Service AI integration: {e}")
        
        # Register Advanced AI Models routes
        try:
            from advanced_ai_models_routes import register_advanced_ai_models_routes
            register_advanced_ai_models_routes(app)
            logger.info("Advanced AI Models routes registered successfully")
        except ImportError as e:
            logger.warning(f"Advanced AI Models integration not available: {e}")
        except Exception as e:
            logger.error(f"Failed to register Advanced AI Models integration: {e}")
        
        # Register Zendesk integration
        try:
            from zendesk_integration_register import register_zendesk_integration
            zendesk_success = register_zendesk_integration(app)
            if zendesk_success:
                logger.info("Zendesk integration registered successfully")
        except ImportError as e:
            logger.warning(f"Zendesk integration not available: {e}")
        except Exception as e:
            logger.error(f"Failed to register Zendesk integration: {e}")
        
        # Register QuickBooks integration
        try:
            from quickbooks_integration_register import register_quickbooks_integration
            quickbooks_success = register_quickbooks_integration(app)
            if quickbooks_success:
                logger.info("QuickBooks integration registered successfully")
        except ImportError as e:
            logger.warning(f"QuickBooks integration not available: {e}")
        except Exception as e:
            logger.error(f"Failed to register QuickBooks integration: {e}")
        
        # Register HubSpot integration
        try:
            from hubspot_integration_register import register_hubspot_integration
            hubspot_success = register_hubspot_integration(app)
            if hubspot_success:
                logger.info("HubSpot integration registered successfully")
        except ImportError as e:
            logger.warning(f"HubSpot integration not available: {e}")
        except Exception as e:
            logger.error(f"Failed to register HubSpot integration: {e}")
        
        # Register health check routes
        @app.route('/health', methods=['GET'])
        async def health_check():
            """Health check endpoint"""
            try:
                health_checker = get_health_checker()
                health_status = await health_checker.check_health(detailed=True)
                
                return jsonify({
                    "status": health_status.status,
                    "message": health_status.message,
                    "timestamp": health_status.timestamp.isoformat(),
                    "response_time": health_status.response_time,
                    "uptime": health_status.uptime,
                    "version": health_status.version,
                    "details": health_status.details
                }), 200 if health_status.status == "healthy" else 503
            
            except Exception as e:
                logger.error(f"Health check failed: {e}")
                return jsonify({
                    "status": "error",
                    "message": f"Health check failed: {str(e)}",
                    "timestamp": datetime.utcnow().isoformat()
                }), 500
        
        # Application info endpoint
        @app.route('/', methods=['GET'])
        def app_info():
            """Application information"""
            return jsonify({
                "name": "ATOM Platform",
                "version": "2.0.0",
                "description": "Advanced platform with Google Drive integration, comprehensive customer support via Zendesk, complete accounting with QuickBooks, and marketing automation with HubSpot",
                "environment": app.config.get('FLASK_ENV', 'unknown'),
                "features": {
                    "google_drive_integration": True,
                    "zendesk_integration": True,
                    "quickbooks_integration": True,
                    "hubspot_integration": True,
                    "semantic_search": app.config.get('SEARCH_ENABLED', False),
                    "workflow_automation": app.config.get('AUTOMATION_ENABLED', False),
                    "real_time_sync": app.config.get('SYNC_ENABLED', False),
                    "content_processing": app.config.get('INGESTION_ENABLED', False)
                },
                "integrations": {
                    "google_drive": {"status": "production", "features": ["file_sync", "search", "automation"]},
                    "zendesk": {"status": "production", "features": ["tickets", "users", "analytics", "oauth"]},
                    "quickbooks": {"status": "production", "features": ["accounting", "invoicing", "reporting", "financial_management"]},
                    "hubspot": {"status": "production", "features": ["marketing_automation", "lead_generation", "crm", "campaigns"]}
                },
                "endpoints": {
                    "health": "/health",
                    "info": "/",
                    "google_drive": "/api/google-drive",
                    "automation": "/api/google-drive/automation",
                    "docs": "/docs"
                },
                "timestamp": datetime.utcnow().isoformat()
            })
        
        # API documentation endpoint
        @app.route('/docs', methods=['GET'])
        def docs():
            """API documentation"""
            return jsonify({
                "message": "ATOM Google Drive Integration API",
                "version": "2.0.0",
                "description": "Complete Google Drive integration with automation",
                "main_endpoints": {
                    "authentication": {
                        "start_auth": "POST /api/google-drive/auth/start",
                        "complete_auth": "POST /api/google-drive/auth/complete",
                        "validate_session": "POST /api/google-drive/auth/validate",
                        "invalidate_session": "POST /api/google-drive/auth/invalidate"
                    },
                    "files": {
                        "list_files": "GET /api/google-drive/files",
                        "get_file": "GET /api/google-drive/files/:id",
                        "upload_file": "POST /api/google-drive/files/upload",
                        "download_file": "GET /api/google-drive/files/:id/download",
                        "delete_file": "DELETE /api/google-drive/files/:id"
                    },
                    "search": {
                        "search": "GET /api/google-drive/search",
                        "facets": "GET /api/google-drive/search/facets",
                        "suggestions": "GET /api/google-drive/search/suggestions"
                    },
                    "automation": {
                        "create_workflow": "POST /api/google-drive/automation/workflows",
                        "execute_workflow": "POST /api/google-drive/automation/workflows/:id/execute",
                        "list_workflows": "GET /api/google-drive/automation/workflows",
                        "create_webhook": "POST /api/google-drive/automation/triggers/webhooks"
                    }
                },
                "openapi_spec": "/docs/openapi.json",
                "postman_collection": "/docs/postman.json"
            })
        
        logger.info("Application blueprints registered")
    
    except Exception as e:
        logger.error(f"Failed to register blueprints: {e}")
        raise

def register_error_handlers(app: Flask):
    """Register error handlers"""
    
    @app.errorhandler(400)
    def bad_request(error):
        """Handle 400 Bad Request"""
        return jsonify({
            "success": False,
            "error": "Bad Request",
            "message": str(error),
            "status_code": 400
        }), 400
    
    @app.errorhandler(401)
    def unauthorized(error):
        """Handle 401 Unauthorized"""
        return jsonify({
            "success": False,
            "error": "Unauthorized",
            "message": "Authentication required",
            "status_code": 401
        }), 401
    
    @app.errorhandler(403)
    def forbidden(error):
        """Handle 403 Forbidden"""
        return jsonify({
            "success": False,
            "error": "Forbidden",
            "message": "Access denied",
            "status_code": 403
        }), 403
    
    @app.errorhandler(404)
    def not_found(error):
        """Handle 404 Not Found"""
        return jsonify({
            "success": False,
            "error": "Not Found",
            "message": "Resource not found",
            "status_code": 404
        }), 404
    
    @app.errorhandler(405)
    def method_not_allowed(error):
        """Handle 405 Method Not Allowed"""
        return jsonify({
            "success": False,
            "error": "Method Not Allowed",
            "message": "HTTP method not allowed",
            "status_code": 405
        }), 405
    
    @app.errorhandler(429)
    def rate_limit_exceeded(error):
        """Handle 429 Rate Limit Exceeded"""
        return jsonify({
            "success": False,
            "error": "Rate Limit Exceeded",
            "message": "Too many requests",
            "status_code": 429
        }), 429
    
    @app.errorhandler(500)
    def internal_server_error(error):
        """Handle 500 Internal Server Error"""
        logger.error(f"Internal server error: {error}")
        return jsonify({
            "success": False,
            "error": "Internal Server Error",
            "message": "An unexpected error occurred",
            "status_code": 500
        }), 500
    
    @app.errorhandler(502)
    def bad_gateway(error):
        """Handle 502 Bad Gateway"""
        return jsonify({
            "success": False,
            "error": "Bad Gateway",
            "message": "Invalid response from upstream server",
            "status_code": 502
        }), 502
    
    @app.errorhandler(503)
    def service_unavailable(error):
        """Handle 503 Service Unavailable"""
        return jsonify({
            "success": False,
            "error": "Service Unavailable",
            "message": "Service temporarily unavailable",
            "status_code": 503
        }), 503
    
    logger.info("Error handlers registered")

def register_middleware(app: Flask):
    """Register request/response middleware"""
    
    @app.before_request
    def before_request():
        """Process before request"""
        from flask import g
        import time
        
        # Store request start time
        g.start_time = time.time()
        
        # Log request
        logger.debug(f"Request: {request.method} {request.path}")
    
    @app.after_request
    def after_request(response):
        """Process after request"""
        from flask import g
        
        # Calculate response time
        response_time = 0
        if hasattr(g, 'start_time'):
            response_time = time.time() - g.start_time
        
        # Add response headers
        response.headers['X-Response-Time'] = f"{response_time:.3f}s"
        response.headers['X-Application-Version'] = '2.0.0'
        response.headers['X-Timestamp'] = datetime.utcnow().isoformat()
        
        # Log response
        logger.debug(f"Response: {response.status_code} ({response_time:.3f}s)")
        
        return response
    
    logger.info("Middleware registered")

async def initialize_app(app: Flask):
    """Initialize application services"""
    
    try:
        logger.info("Initializing application services...")
        
        # Initialize database
        await initialize_database(app)
        
        # Initialize Redis
        await initialize_redis(app)
        
        # Initialize background services
        await initialize_background_services(app)
        
        logger.info("Application services initialized successfully")
        
    except Exception as e:
        logger.error(f"Failed to initialize application services: {e}")
        raise

async def initialize_database(app: Flask):
    """Initialize database"""
    
    try:
        with app.app_context():
            # Import database models if needed
            # from models import *
            
            # Create all tables
            db.create_all()
            
            logger.info("Database initialized")
    
    except Exception as e:
        logger.error(f"Failed to initialize database: {e}")
        raise

async def initialize_redis(app: Flask):
    """Initialize Redis"""
    
    try:
        # Test Redis connection
        if redis_client:
            redis_client.ping()
            logger.info("Redis connected")
        else:
            logger.warning("Redis not available")
    
    except Exception as e:
        logger.error(f"Failed to initialize Redis: {e}")
        raise

async def initialize_background_services(app: Flask):
    """Initialize background services"""
    
    try:
        # Initialize Google Drive services
        if app.config.get('GOOGLE_DRIVE_CLIENT_ID'):
            from google_drive_service import get_google_drive_service
            from google_drive_memory import get_google_drive_memory_service
            from google_drive_search_integration import get_google_drive_search_provider
            from google_drive_automation_engine import get_automation_engine
            from google_drive_trigger_system import get_google_drive_trigger_system
            from google_drive_action_system import get_google_drive_action_system
            
            # Pre-load services
            logger.info("Initializing Google Drive services...")
            
            # Initialize services (they'll be loaded on-demand)
            services = [
                ("Google Drive Service", get_google_drive_service),
                ("Memory Service", get_google_drive_memory_service),
                ("Search Provider", get_google_drive_search_provider),
                ("Automation Engine", get_automation_engine),
                ("Trigger System", get_google_drive_trigger_system),
                ("Action System", get_google_drive_action_system)
            ]
            
            for service_name, service_getter in services:
                try:
                    service = await service_getter()
                    if service:
                        logger.info(f"{service_name} initialized")
                    else:
                        logger.warning(f"{service_name} not available")
                except Exception as e:
                    logger.error(f"{service_name} initialization failed: {e}")
        
        logger.info("Background services initialized")
    
    except Exception as e:
        logger.error(f"Failed to initialize background services: {e}")
        logger.warning("Some services may not be available")

def run_app(app: Flask, host: str = None, port: int = None, debug: bool = None):
    """Run Flask application"""
    
    try:
        # Get configuration
        host = host or app.config.get('HOST', '0.0.0.0')
        port = port or app.config.get('PORT', 8000)
        debug = debug if debug is not None else app.config.get('DEBUG', False)
        
        # Initialize application
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(initialize_app(app))
        finally:
            loop.close()
        
        # Run application
        logger.info(f"Starting application on {host}:{port}")
        logger.info(f"Debug mode: {debug}")
        logger.info(f"Environment: {app.config.get('FLASK_ENV', 'unknown')}")
        logger.info(f"Features enabled:")
        logger.info(f"  - Google Drive Integration: ✓")
        logger.info(f"  - Semantic Search: {'✓' if app.config.get('SEARCH_ENABLED') else '✗'}")
        logger.info(f"  - Workflow Automation: {'✓' if app.config.get('AUTOMATION_ENABLED') else '✗'}")
        logger.info(f"  - Real-time Sync: {'✓' if app.config.get('SYNC_ENABLED') else '✗'}")
        logger.info(f"  - Content Processing: {'✓' if app.config.get('INGESTION_ENABLED') else '✗'}")
        
        logger.info(f"Key endpoints:")
        logger.info(f"  - Health Check: http://{host}:{port}/health")
        logger.info(f"  - Application Info: http://{host}:{port}/")
        logger.info(f"  - API Documentation: http://{host}:{port}/docs")
        logger.info(f"  - Google Drive API: http://{host}:{port}/api/google-drive")
        logger.info(f"  - Automation API: http://{host}:{port}/api/google-drive/automation")
        
        app.run(
            host=host,
            port=port,
            debug=debug,
            threaded=True,
            use_reloader=debug  # Don't use reloader in production
        )
    
    except KeyboardInterrupt:
        logger.info("Application stopped by user")
    
    except Exception as e:
        logger.error(f"Failed to run application: {e}")
        raise

# Application factory
def create_and_run_app(config_name: str = None, **kwargs):
    """Create and run Flask application"""
    
    try:
        # Create app
        app = create_app(config_name)
        
        # Run app
        run_app(app, **kwargs)
    
    except Exception as e:
        logger.error(f"Failed to create and run application: {e}")
        sys.exit(1)

# Create default app
app = create_app()

# Export main functions
if __name__ == '__main__':
    # Get environment
    env = os.getenv('FLASK_ENV', 'development')
    
    # Create and run app
    create_and_run_app(
        config_name=env,
        host=os.getenv('FLASK_HOST', '0.0.0.0'),
        port=int(os.getenv('FLASK_PORT', 8000)),
        debug=os.getenv('FLASK_DEBUG', 'false').lower() == 'true'
    )

# Export app for other modules
__all__ = [
    'create_app',
    'create_and_run_app',
    'app'
]