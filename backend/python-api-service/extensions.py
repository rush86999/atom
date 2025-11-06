"""
ATOM Backend Extensions Configuration
Database, Redis, and other Flask extensions
"""

import os
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_redis import FlaskRedis
import redis
from typing import Optional, Dict, Any
import logging

# Configure logging
logger = logging.getLogger(__name__)

class FlaskRedisCustom(FlaskRedis):
    """Custom Redis client with additional functionality"""
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._redis_client = None
    
    def init_app(self, app):
        """Initialize with custom configuration"""
        
        # Get Redis configuration
        redis_url = app.config.get('REDIS_URL', 'redis://localhost:6379/0')
        redis_config = {
            'decode_responses': True,
            'socket_timeout': 5,
            'socket_connect_timeout': 5,
            'retry_on_timeout': True,
            'health_check_interval': 30
        }
        
        # Parse Redis URL for additional config
        if redis_url:
            try:
                import urllib.parse
                parsed = urllib.parse.urlparse(redis_url)
                
                if parsed.password:
                    redis_config['password'] = parsed.password
                
                if parsed.hostname:
                    redis_config['host'] = parsed.hostname
                
                if parsed.port:
                    redis_config['port'] = parsed.port
                
                if parsed.path:
                    redis_config['db'] = int(parsed.path[1:]) if parsed.path[1:].isdigit() else 0
                
            except Exception as e:
                logger.warning(f"Error parsing Redis URL: {e}")
        
        # Create Redis client
        try:
            self._redis_client = redis.Redis.from_url(redis_url, **redis_config)
            
            # Test connection
            self._redis_client.ping()
            
            # Initialize parent
            super().init_app(app)
            
            logger.info("Custom Redis client initialized successfully")
        
        except Exception as e:
            logger.error(f"Error initializing Redis client: {e}")
            self._redis_client = None
    
    @property
    def client(self):
        """Get Redis client"""
        return self._redis_client
    
    def ping(self) -> bool:
        """Ping Redis server"""
        try:
            if self._redis_client:
                return self._redis_client.ping()
            return False
        except Exception as e:
            logger.error(f"Redis ping error: {e}")
            return False
    
    def get_info(self) -> Dict[str, Any]:
        """Get Redis server info"""
        try:
            if self._redis_client:
                return self._redis_client.info()
            return {}
        except Exception as e:
            logger.error(f"Redis info error: {e}")
            return {}
    
    def set_with_ttl(self, key: str, value: str, ttl: int) -> bool:
        """Set key with TTL"""
        try:
            if self._redis_client:
                return self._redis_client.setex(key, ttl, value)
            return False
        except Exception as e:
            logger.error(f"Redis set_with_ttl error: {e}")
            return False
    
    def get_json(self, key: str) -> Optional[Dict[str, Any]]:
        """Get JSON value"""
        try:
            if self._redis_client:
                value = self._redis_client.get(key)
                return json.loads(value) if value else None
            return None
        except Exception as e:
            logger.error(f"Redis get_json error: {e}")
            return None
    
    def set_json(self, key: str, value: Dict[str, Any], ttl: Optional[int] = None) -> bool:
        """Set JSON value"""
        try:
            if self._redis_client:
                json_value = json.dumps(value, default=str)
                if ttl:
                    return self._redis_client.setex(key, ttl, json_value)
                else:
                    return self._redis_client.set(key, json_value)
            return False
        except Exception as e:
            logger.error(f"Redis set_json error: {e}")
            return False

class SQLAlchemyCustom(SQLAlchemy):
    """Custom SQLAlchemy with additional functionality"""
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._engine = None
    
    def init_app(self, app):
        """Initialize with custom configuration"""
        
        # Get database configuration
        database_url = app.config.get('DATABASE_URL')
        if not database_url:
            raise ValueError("DATABASE_URL is required")
        
        # Configure SQLAlchemy
        app.config['SQLALCHEMY_DATABASE_URI'] = database_url
        app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
        app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {
            'pool_size': app.config.get('DB_POOL_SIZE', 10),
            'max_overflow': app.config.get('DB_MAX_OVERFLOW', 20),
            'pool_timeout': app.config.get('DB_POOL_TIMEOUT', 30),
            'pool_recycle': app.config.get('DB_POOL_RECYCLE', 3600),
            'echo': app.config.get('DB_ECHO', False)
        }
        
        # Initialize parent
        super().init_app(app)
        
        # Store engine reference
        self._engine = self.engine
        
        logger.info("Custom SQLAlchemy initialized successfully")
    
    def health_check(self) -> bool:
        """Check database health"""
        try:
            if self._engine:
                with self._engine.connect() as conn:
                    conn.execute('SELECT 1')
                return True
            return False
        except Exception as e:
            logger.error(f"Database health check error: {e}")
            return False
    
    def get_engine_info(self) -> Dict[str, Any]:
        """Get engine information"""
        try:
            if self._engine:
                pool = self._engine.pool
                return {
                    'pool_size': pool.size(),
                    'checked_in': pool.checkedin(),
                    'checked_out': pool.checkedout(),
                    'overflow': pool.overflow(),
                    'invalid': pool.invalid()
                }
            return {}
        except Exception as e:
            logger.error(f"Engine info error: {e}")
            return {}
    
    def execute_raw(self, query: str, params: Optional[tuple] = None) -> Any:
        """Execute raw SQL query"""
        try:
            with self._engine.connect() as conn:
                result = conn.execute(query, params)
                conn.commit()
                return result
        except Exception as e:
            logger.error(f"Raw query execution error: {e}")
            raise
    
    def execute_transaction(self, queries: list) -> bool:
        """Execute multiple queries in transaction"""
        try:
            with self._engine.connect() as conn:
                with conn.begin():
                    for query, params in queries:
                        conn.execute(query, params)
                return True
        except Exception as e:
            logger.error(f"Transaction execution error: {e}")
            return False

class CustomMigrate(Migrate):
    """Custom Flask-Migrate with additional functionality"""
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._directory = None
    
    def init_app(self, app):
        """Initialize with custom configuration"""
        
        # Configure migration directory
        migrations_dir = app.config.get('MIGRATIONS_DIR', 'migrations')
        app.config['MIGRATIONS_DIR'] = migrations_dir
        
        # Initialize parent
        super().init_app(app)
        
        self._directory = migrations_dir
        logger.info(f"Custom Migrate initialized with directory: {migrations_dir}")
    
    def get_migration_status(self) -> Dict[str, Any]:
        """Get migration status"""
        try:
            import alembic.migration
            import alembic.config
            
            config = alembic.config.Config()
            config.set_main_option('script_location', self._directory)
            
            with self.db.engine.connect() as connection:
                context = alembic.migration.MigrationContext.configure(connection)
                current_rev = context.get_current_revision()
                head_rev = context.get_head_revision()
                
                return {
                    'current_revision': current_rev,
                    'head_revision': head_rev,
                    'is_up_to_date': current_rev == head_rev,
                    'needs_upgrade': current_rev != head_rev
                }
        
        except Exception as e:
            logger.error(f"Migration status error: {e}")
            return {'error': str(e)}

# Initialize extensions
db = SQLAlchemyCustom()
redis_client = FlaskRedisCustom()

# Initialize migrate only if db is available
try:
    migrate = CustomMigrate()
except Exception as e:
    logger.warning(f"Migrate extension not available: {e}")
    migrate = None

# Extension utility functions
def check_database_health() -> Dict[str, Any]:
    """Check database health"""
    
    try:
        if db:
            is_healthy = db.health_check()
            info = db.get_engine_info()
            
            return {
                'status': 'healthy' if is_healthy else 'unhealthy',
                'details': info,
                'timestamp': datetime.utcnow().isoformat()
            }
        else:
            return {
                'status': 'unavailable',
                'error': 'Database extension not initialized',
                'timestamp': datetime.utcnow().isoformat()
            }
    
    except Exception as e:
        logger.error(f"Database health check error: {e}")
        return {
            'status': 'error',
            'error': str(e),
            'timestamp': datetime.utcnow().isoformat()
        }

def check_redis_health() -> Dict[str, Any]:
    """Check Redis health"""
    
    try:
        if redis_client:
            is_healthy = redis_client.ping()
            info = redis_client.get_info() if is_healthy else {}
            
            return {
                'status': 'healthy' if is_healthy else 'unhealthy',
                'details': {
                    'version': info.get('redis_version'),
                    'connected_clients': info.get('connected_clients'),
                    'used_memory': info.get('used_memory_human'),
                    'uptime_seconds': info.get('uptime_in_seconds')
                } if info else {},
                'timestamp': datetime.utcnow().isoformat()
            }
        else:
            return {
                'status': 'unavailable',
                'error': 'Redis extension not initialized',
                'timestamp': datetime.utcnow().isoformat()
            }
    
    except Exception as e:
        logger.error(f"Redis health check error: {e}")
        return {
            'status': 'error',
            'error': str(e),
            'timestamp': datetime.utcnow().isoformat()
        }

def get_extension_status() -> Dict[str, Any]:
    """Get status of all extensions"""
    
    db_health = check_database_health()
    redis_health = check_redis_health()
    
    status = {
        'database': db_health,
        'redis': redis_health,
        'migrate': {
            'status': 'available' if migrate else 'unavailable',
            'migration_status': migrate.get_migration_status() if migrate else None,
            'timestamp': datetime.utcnow().isoformat()
        }
    }
    
    # Overall status
    all_healthy = all(
        health['status'] in ['healthy', 'available'] 
        for health in status.values()
        if 'status' in health
    )
    
    status['overall'] = {
        'status': 'healthy' if all_healthy else 'degraded',
        'timestamp': datetime.utcnow().isoformat()
    }
    
    return status

# Extension initialization utilities
def init_extensions(app):
    """Initialize all extensions"""
    
    try:
        # Initialize database
        db.init_app(app)
        logger.info("Database extension initialized")
        
        # Initialize Redis
        redis_client.init_app(app)
        logger.info("Redis extension initialized")
        
        # Initialize migrations
        if migrate:
            migrate.init_app(app, db)
            logger.info("Migration extension initialized")
        
        logger.info("All extensions initialized successfully")
        return True
    
    except Exception as e:
        logger.error(f"Error initializing extensions: {e}")
        return False

def create_all_tables():
    """Create all database tables"""
    
    try:
        with app.app_context():
            db.create_all()
            logger.info("All database tables created")
            return True
    except Exception as e:
        logger.error(f"Error creating tables: {e}")
        return False

def drop_all_tables():
    """Drop all database tables"""
    
    try:
        with app.app_context():
            db.drop_all()
            logger.info("All database tables dropped")
            return True
    except Exception as e:
        logger.error(f"Error dropping tables: {e}")
        return False

# Export extensions and utilities
__all__ = [
    'db',
    'redis_client',
    'migrate',
    'check_database_health',
    'check_redis_health',
    'get_extension_status',
    'init_extensions',
    'create_all_tables',
    'drop_all_tables'
]

# Add datetime import
from datetime import datetime
import json