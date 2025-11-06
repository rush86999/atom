"""
Comprehensive Health Check System for ATOM Google Drive Integration
Monitors all services and provides detailed health information
"""

import asyncio
import json
import time
import psutil
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass, asdict
from loguru import logger

@dataclass
class HealthStatus:
    """Health status data class"""
    status: str  # 'healthy', 'degraded', 'unhealthy', 'unknown'
    message: str
    timestamp: datetime
    details: Dict[str, Any] = None
    response_time: Optional[float] = None
    uptime: Optional[float] = None
    version: Optional[str] = None

@dataclass
class ComponentHealth:
    """Component health data class"""
    name: str
    status: str
    message: str
    response_time: float
    details: Dict[str, Any] = None
    last_check: datetime = None

class HealthChecker:
    """Comprehensive health checker for ATOM integration"""
    
    def __init__(self, app=None):
        self.app = app
        self.start_time = time.time()
        self.check_history: List[HealthStatus] = []
        self.component_cache: Dict[str, ComponentHealth] = {}
        self.cache_ttl = 30  # seconds
        
        # Service check functions
        self.service_checks = {
            'flask': self._check_flask,
            'database': self._check_database,
            'redis': self._check_redis,
            'google_drive': self._check_google_drive,
            'lancedb': self._check_lancedb,
            'automation': self._check_automation,
            'search': self._check_search,
            'sync': self._check_sync,
            'ingestion': self._check_ingestion,
            'memory': self._check_system_memory,
            'disk': self._check_disk_space,
            'cpu': self._check_cpu_usage
        }
    
    async def check_health(self, detailed: bool = True) -> HealthStatus:
        """Perform comprehensive health check"""
        
        try:
            start_time = time.time()
            
            # Check all services
            components = await self._check_all_services()
            
            # Calculate overall status
            overall_status = self._calculate_overall_status(components)
            
            # Calculate response time
            response_time = time.time() - start_time
            
            # Calculate uptime
            uptime = time.time() - self.start_time
            
            # Get version
            version = await self._get_version()
            
            # Create health status
            health_status = HealthStatus(
                status=overall_status,
                message=self._get_status_message(overall_status, components),
                timestamp=datetime.utcnow(),
                details={
                    'components': components,
                    'summary': self._create_summary(components),
                    'environment': await self._get_environment_info()
                } if detailed else {},
                response_time=response_time,
                uptime=uptime,
                version=version
            )
            
            # Store in history
            self._store_health_status(health_status)
            
            return health_status
        
        except Exception as e:
            logger.error(f"Health check failed: {e}")
            return HealthStatus(
                status='error',
                message=f"Health check failed: {str(e)}",
                timestamp=datetime.utcnow(),
                details={'error': str(e)}
            )
    
    async def _check_all_services(self) -> List[ComponentHealth]:
        """Check all services"""
        
        components = []
        
        # Check each service
        for service_name, check_func in self.service_checks.items():
            try:
                # Check cache
                if service_name in self.component_cache:
                    cached = self.component_cache[service_name]
                    if (datetime.utcnow() - cached.last_check).seconds < self.cache_ttl:
                        components.append(cached)
                        continue
                
                # Perform health check
                component_health = await check_func()
                component_health.name = service_name
                component_health.last_check = datetime.utcnow()
                
                # Cache result
                self.component_cache[service_name] = component_health
                
                components.append(component_health)
            
            except Exception as e:
                logger.error(f"Health check failed for {service_name}: {e}")
                components.append(ComponentHealth(
                    name=service_name,
                    status='error',
                    message=f"Health check failed: {str(e)}",
                    response_time=0,
                    details={'error': str(e)},
                    last_check=datetime.utcnow()
                ))
        
        return components
    
    async def _check_flask(self) -> ComponentHealth:
        """Check Flask application health"""
        
        try:
            start_time = time.time()
            
            if not self.app:
                return ComponentHealth(
                    name='flask',
                    status='unhealthy',
                    message='Flask application not initialized',
                    response_time=0,
                    details={'error': 'App not found'}
                )
            
            # Test Flask configuration
            config = self.app.config
            required_configs = ['SECRET_KEY', 'DATABASE_URL']
            missing_configs = [cfg for cfg in required_configs if not config.get(cfg)]
            
            if missing_configs:
                return ComponentHealth(
                    name='flask',
                    status='degraded',
                    message=f'Missing configurations: {", ".join(missing_configs)}',
                    response_time=time.time() - start_time,
                    details={'missing_configs': missing_configs}
                )
            
            response_time = time.time() - start_time
            
            return ComponentHealth(
                name='flask',
                status='healthy',
                message='Flask application is running',
                response_time=response_time,
                details={
                    'debug_mode': config.get('DEBUG', False),
                    'host': config.get('HOST', 'localhost'),
                    'port': config.get('PORT', 8000),
                    'environment': config.get('FLASK_ENV', 'development')
                }
            )
        
        except Exception as e:
            return ComponentHealth(
                name='flask',
                status='error',
                message=f'Flask check failed: {str(e)}',
                response_time=0,
                details={'error': str(e)}
            )
    
    async def _check_database(self) -> ComponentHealth:
        """Check PostgreSQL database health"""
        
        try:
            start_time = time.time()
            
            if not self.app:
                return ComponentHealth(
                    name='database',
                    status='unknown',
                    message='App not available for database check',
                    response_time=0
                )
            
            from extensions import db
            
            if not db or not db.engine:
                return ComponentHealth(
                    name='database',
                    status='unhealthy',
                    message='Database engine not initialized',
                    response_time=0,
                    details={'error': 'Database engine not found'}
                )
            
            # Test database connection
            with db.engine.connect() as conn:
                # Test basic query
                result = conn.execute('SELECT 1, NOW()').fetchone()
                
                # Check table existence
                tables_result = conn.execute("""
                    SELECT COUNT(*) as count 
                    FROM information_schema.tables 
                    WHERE table_schema = 'public' 
                    AND table_name LIKE 'google_drive_%'
                """).fetchone()
                
                # Check database size
                size_result = conn.execute("""
                    SELECT pg_size_pretty(pg_database_size(current_database())) as size
                """).fetchone()
                
                # Check active connections
                connections_result = conn.execute("""
                    SELECT count(*) as connections 
                    FROM pg_stat_activity 
                    WHERE state = 'active'
                """).fetchone()
                
                response_time = time.time() - start_time
                
                return ComponentHealth(
                    name='database',
                    status='healthy',
                    message='Database is running and responsive',
                    response_time=response_time,
                    details={
                        'connection_test': 'passed',
                        'tables_found': tables_result['count'],
                        'database_size': size_result['size'],
                        'active_connections': connections_result['connections'],
                        'server_time': result['now'].isoformat()
                    }
                )
        
        except Exception as e:
            return ComponentHealth(
                name='database',
                status='unhealthy',
                message=f'Database connection failed: {str(e)}',
                response_time=0,
                details={'error': str(e)}
            )
    
    async def _check_redis(self) -> ComponentHealth:
        """Check Redis health"""
        
        try:
            start_time = time.time()
            
            if not self.app:
                return ComponentHealth(
                    name='redis',
                    status='unknown',
                    message='App not available for Redis check',
                    response_time=0
                )
            
            from extensions import redis_client
            
            if not redis_client:
                return ComponentHealth(
                    name='redis',
                    status='unhealthy',
                    message='Redis client not initialized',
                    response_time=0,
                    details={'error': 'Redis client not found'}
                )
            
            # Test Redis connection
            redis_client.ping()
            
            # Get Redis info
            info = redis_client.info()
            
            # Test basic operations
            test_key = 'health_check_test'
            redis_client.set(test_key, 'test_value', ex=10)
            test_value = redis_client.get(test_key)
            redis_client.delete(test_key)
            
            response_time = time.time() - start_time
            
            if test_value != 'test_value':
                return ComponentHealth(
                    name='redis',
                    status='degraded',
                    message='Redis basic operations failed',
                    response_time=response_time,
                    details={'error': 'Basic operations test failed'}
                )
            
            return ComponentHealth(
                name='redis',
                status='healthy',
                message='Redis is running and responsive',
                response_time=response_time,
                details={
                    'version': info.get('redis_version'),
                    'mode': info.get('redis_mode'),
                    'used_memory': info.get('used_memory_human'),
                    'connected_clients': info.get('connected_clients'),
                    'total_commands_processed': info.get('total_commands_processed'),
                    'uptime_in_seconds': info.get('uptime_in_seconds'),
                    'basic_operations': 'passed'
                }
            )
        
        except Exception as e:
            return ComponentHealth(
                name='redis',
                status='unhealthy',
                message=f'Redis connection failed: {str(e)}',
                response_time=0,
                details={'error': str(e)}
            )
    
    async def _check_google_drive(self) -> ComponentHealth:
        """Check Google Drive service health"""
        
        try:
            start_time = time.time()
            
            if not self.app:
                return ComponentHealth(
                    name='google_drive',
                    status='unknown',
                    message='App not available for Google Drive check',
                    response_time=0
                )
            
            # Check if Google Drive service is available
            try:
                from google_drive_service import get_google_drive_service
                service = get_google_drive_service()
                
                if not service:
                    return ComponentHealth(
                        name='google_drive',
                        status='degraded',
                        message='Google Drive service not initialized',
                        response_time=time.time() - start_time,
                        details={'error': 'Service not found'}
                    )
                
                # Check if there are any connected users
                if hasattr(service, 'get_connection_status'):
                    connection_status = await service.get_connection_status()
                else:
                    connection_status = {'connected': False}
                
                response_time = time.time() - start_time
                
                if connection_status.get('connected'):
                    return ComponentHealth(
                        name='google_drive',
                        status='healthy',
                        message='Google Drive service is connected',
                        response_time=response_time,
                        details=connection_status
                    )
                else:
                    return ComponentHealth(
                        name='google_drive',
                        status='degraded',
                        message='Google Drive service not connected',
                        response_time=response_time,
                        details=connection_status
                    )
            
            except ImportError:
                return ComponentHealth(
                    name='google_drive',
                    status='unknown',
                    message='Google Drive service not available',
                    response_time=time.time() - start_time,
                    details={'error': 'Service not available'}
                )
        
        except Exception as e:
            return ComponentHealth(
                name='google_drive',
                status='error',
                message=f'Google Drive check failed: {str(e)}',
                response_time=0,
                details={'error': str(e)}
            )
    
    async def _check_lancedb(self) -> ComponentHealth:
        """Check LanceDB health"""
        
        try:
            start_time = time.time()
            
            # Check LanceDB availability
            try:
                from google_drive_memory import get_google_drive_memory_service
                service = get_google_drive_memory_service()
                
                if not service:
                    return ComponentHealth(
                        name='lancedb',
                        status='degraded',
                        message='LanceDB service not initialized',
                        response_time=time.time() - start_time,
                        details={'error': 'Service not found'}
                    )
                
                # Test basic operations
                if hasattr(service, 'health_check'):
                    health_info = await service.health_check()
                else:
                    health_info = {'status': 'unknown'}
                
                response_time = time.time() - start_time
                
                return ComponentHealth(
                    name='lancedb',
                    status=health_info.get('status', 'healthy'),
                    message=f'LanceDB is {health_info.get("status", "running")}',
                    response_time=response_time,
                    details=health_info
                )
            
            except ImportError:
                return ComponentHealth(
                    name='lancedb',
                    status='unknown',
                    message='LanceDB service not available',
                    response_time=time.time() - start_time,
                    details={'error': 'Service not available'}
                )
        
        except Exception as e:
            return ComponentHealth(
                name='lancedb',
                status='error',
                message=f'LanceDB check failed: {str(e)}',
                response_time=0,
                details={'error': str(e)}
            )
    
    async def _check_automation(self) -> ComponentHealth:
        """Check automation service health"""
        
        try:
            start_time = time.time()
            
            # Check automation service availability
            try:
                from google_drive_automation import get_google_drive_automation_service
                service = get_google_drive_automation_service()
                
                if not service:
                    return ComponentHealth(
                        name='automation',
                        status='degraded',
                        message='Automation service not initialized',
                        response_time=time.time() - start_time,
                        details={'error': 'Service not found'}
                    )
                
                # Test basic operations
                if hasattr(service, 'health_check'):
                    health_info = await service.health_check()
                else:
                    health_info = {'status': 'unknown'}
                
                response_time = time.time() - start_time
                
                return ComponentHealth(
                    name='automation',
                    status=health_info.get('status', 'healthy'),
                    message=f'Automation service is {health_info.get("status", "running")}',
                    response_time=response_time,
                    details=health_info
                )
            
            except ImportError:
                return ComponentHealth(
                    name='automation',
                    status='unknown',
                    message='Automation service not available',
                    response_time=time.time() - start_time,
                    details={'error': 'Service not available'}
                )
        
        except Exception as e:
            return ComponentHealth(
                name='automation',
                status='error',
                message=f'Automation check failed: {str(e)}',
                response_time=0,
                details={'error': str(e)}
            )
    
    async def _check_search(self) -> ComponentHealth:
        """Check search service health"""
        
        try:
            start_time = time.time()
            
            # Check search service availability
            try:
                from google_drive_search_integration import _google_drive_search_provider
                
                if not _google_drive_search_provider:
                    return ComponentHealth(
                        name='search',
                        status='degraded',
                        message='Search provider not initialized',
                        response_time=time.time() - start_time,
                        details={'error': 'Provider not found'}
                    )
                
                # Test search provider
                provider_info = _google_drive_search_provider.get_provider_info()
                
                response_time = time.time() - start_time
                
                return ComponentHealth(
                    name='search',
                    status='healthy',
                    message='Search provider is available',
                    response_time=response_time,
                    details=provider_info
                )
            
            except ImportError:
                return ComponentHealth(
                    name='search',
                    status='unknown',
                    message='Search service not available',
                    response_time=time.time() - start_time,
                    details={'error': 'Service not available'}
                )
        
        except Exception as e:
            return ComponentHealth(
                name='search',
                status='error',
                message=f'Search check failed: {str(e)}',
                response_time=0,
                details={'error': str(e)}
            )
    
    async def _check_sync(self) -> ComponentHealth:
        """Check sync service health"""
        
        try:
            start_time = time.time()
            
            # Check sync service availability
            try:
                from google_drive_realtime_sync import get_google_drive_sync_service
                service = get_google_drive_sync_service()
                
                if not service:
                    return ComponentHealth(
                        name='sync',
                        status='degraded',
                        message='Sync service not initialized',
                        response_time=time.time() - start_time,
                        details={'error': 'Service not found'}
                    )
                
                # Test basic operations
                if hasattr(service, 'health_check'):
                    health_info = await service.health_check()
                else:
                    health_info = {'status': 'unknown'}
                
                response_time = time.time() - start_time
                
                return ComponentHealth(
                    name='sync',
                    status=health_info.get('status', 'healthy'),
                    message=f'Sync service is {health_info.get("status", "running")}',
                    response_time=response_time,
                    details=health_info
                )
            
            except ImportError:
                return ComponentHealth(
                    name='sync',
                    status='unknown',
                    message='Sync service not available',
                    response_time=time.time() - start_time,
                    details={'error': 'Service not available'}
                )
        
        except Exception as e:
            return ComponentHealth(
                name='sync',
                status='error',
                message=f'Sync check failed: {str(e)}',
                response_time=0,
                details={'error': str(e)}
            )
    
    async def _check_ingestion(self) -> ComponentHealth:
        """Check ingestion pipeline health"""
        
        try:
            start_time = time.time()
            
            # Check ingestion service availability
            try:
                from ingestion_pipeline import get_content_processor
                processor = get_content_processor()
                
                if not processor:
                    return ComponentHealth(
                        name='ingestion',
                        status='degraded',
                        message='Content processor not initialized',
                        response_time=time.time() - start_time,
                        details={'error': 'Processor not found'}
                    )
                
                # Test basic operations
                if hasattr(processor, 'health_check'):
                    health_info = await processor.health_check()
                else:
                    health_info = {'status': 'unknown'}
                
                response_time = time.time() - start_time
                
                return ComponentHealth(
                    name='ingestion',
                    status=health_info.get('status', 'healthy'),
                    message=f'Content processor is {health_info.get("status", "running")}',
                    response_time=response_time,
                    details=health_info
                )
            
            except ImportError:
                return ComponentHealth(
                    name='ingestion',
                    status='unknown',
                    message='Content processor not available',
                    response_time=time.time() - start_time,
                    details={'error': 'Processor not available'}
                )
        
        except Exception as e:
            return ComponentHealth(
                name='ingestion',
                status='error',
                message=f'Ingestion check failed: {str(e)}',
                response_time=0,
                details={'error': str(e)}
            )
    
    async def _check_system_memory(self) -> ComponentHealth:
        """Check system memory usage"""
        
        try:
            start_time = time.time()
            
            # Get memory information
            memory = psutil.virtual_memory()
            
            # Calculate status
            if memory.percent > 90:
                status = 'unhealthy'
            elif memory.percent > 80:
                status = 'degraded'
            else:
                status = 'healthy'
            
            response_time = time.time() - start_time
            
            return ComponentHealth(
                name='memory',
                status=status,
                message=f'Memory usage: {memory.percent:.1f}%',
                response_time=response_time,
                details={
                    'total': memory.total,
                    'available': memory.available,
                    'used': memory.used,
                    'percent': memory.percent,
                    'free': memory.free,
                    'buffers': getattr(memory, 'buffers', 0),
                    'cached': getattr(memory, 'cached', 0)
                }
            )
        
        except Exception as e:
            return ComponentHealth(
                name='memory',
                status='error',
                message=f'Memory check failed: {str(e)}',
                response_time=0,
                details={'error': str(e)}
            )
    
    async def _check_disk_space(self) -> ComponentHealth:
        """Check disk space usage"""
        
        try:
            start_time = time.time()
            
            # Get disk information
            disk = psutil.disk_usage('/')
            
            # Calculate status
            if disk.percent > 95:
                status = 'unhealthy'
            elif disk.percent > 85:
                status = 'degraded'
            else:
                status = 'healthy'
            
            response_time = time.time() - start_time
            
            return ComponentHealth(
                name='disk',
                status=status,
                message=f'Disk usage: {disk.percent:.1f}%',
                response_time=response_time,
                details={
                    'total': disk.total,
                    'used': disk.used,
                    'free': disk.free,
                    'percent': disk.percent,
                    'mountpoint': '/'
                }
            )
        
        except Exception as e:
            return ComponentHealth(
                name='disk',
                status='error',
                message=f'Disk check failed: {str(e)}',
                response_time=0,
                details={'error': str(e)}
            )
    
    async def _check_cpu_usage(self) -> ComponentHealth:
        """Check CPU usage"""
        
        try:
            start_time = time.time()
            
            # Get CPU information
            cpu_percent = psutil.cpu_percent(interval=1)
            cpu_count = psutil.cpu_count()
            cpu_freq = psutil.cpu_freq()
            
            # Calculate status
            if cpu_percent > 95:
                status = 'unhealthy'
            elif cpu_percent > 85:
                status = 'degraded'
            else:
                status = 'healthy'
            
            response_time = time.time() - start_time
            
            return ComponentHealth(
                name='cpu',
                status=status,
                message=f'CPU usage: {cpu_percent:.1f}%',
                response_time=response_time,
                details={
                    'percent': cpu_percent,
                    'count': cpu_count,
                    'frequency': {
                        'current': cpu_freq.current if cpu_freq else None,
                        'min': cpu_freq.min if cpu_freq else None,
                        'max': cpu_freq.max if cpu_freq else None
                    },
                    'load_average': psutil.getloadavg() if hasattr(psutil, 'getloadavg') else None
                }
            )
        
        except Exception as e:
            return ComponentHealth(
                name='cpu',
                status='error',
                message=f'CPU check failed: {str(e)}',
                response_time=0,
                details={'error': str(e)}
            )
    
    def _calculate_overall_status(self, components: List[ComponentHealth]) -> str:
        """Calculate overall system status"""
        
        if not components:
            return 'unknown'
        
        # Count status types
        status_counts = {'healthy': 0, 'degraded': 0, 'unhealthy': 0, 'error': 0, 'unknown': 0}
        
        for component in components:
            if component.status in status_counts:
                status_counts[component.status] += 1
        
        # Determine overall status
        if status_counts['error'] > 0 or status_counts['unhealthy'] > 0:
            return 'unhealthy'
        elif status_counts['degraded'] > 0:
            return 'degraded'
        elif status_counts['healthy'] > 0:
            return 'healthy'
        else:
            return 'unknown'
    
    def _get_status_message(self, overall_status: str, components: List[ComponentHealth]) -> str:
        """Generate status message"""
        
        if overall_status == 'healthy':
            return 'All systems are operational'
        elif overall_status == 'degraded':
            degraded_components = [c.name for c in components if c.status == 'degraded']
            return f'Some systems are degraded: {", ".join(degraded_components)}'
        elif overall_status == 'unhealthy':
            unhealthy_components = [c.name for c in components if c.status in ['unhealthy', 'error']]
            return f'Critical systems are unhealthy: {", ".join(unhealthy_components)}'
        else:
            return 'System status unknown'
    
    def _create_summary(self, components: List[ComponentHealth]) -> Dict[str, Any]:
        """Create summary of component health"""
        
        status_counts = {'healthy': 0, 'degraded': 0, 'unhealthy': 0, 'error': 0, 'unknown': 0}
        response_times = []
        
        for component in components:
            if component.status in status_counts:
                status_counts[component.status] += 1
            
            if component.response_time > 0:
                response_times.append(component.response_time)
        
        return {
            'total_components': len(components),
            'status_counts': status_counts,
            'average_response_time': sum(response_times) / len(response_times) if response_times else 0,
            'max_response_time': max(response_times) if response_times else 0,
            'min_response_time': min(response_times) if response_times else 0
        }
    
    async def _get_version(self) -> str:
        """Get application version"""
        
        try:
            # Try to get version from package
            try:
                import importlib.metadata
                return importlib.metadata.version('atom-backend')
            except ImportError:
                pass
            
            # Try to get from app config
            if self.app and hasattr(self.app, 'config'):
                return self.app.config.get('VERSION', '1.0.0')
            
            # Return default
            return '1.0.0'
        
        except Exception:
            return '1.0.0'
    
    async def _get_environment_info(self) -> Dict[str, Any]:
        """Get environment information"""
        
        try:
            env_info = {
                'flask_env': os.getenv('FLASK_ENV', 'development'),
                'python_version': f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
                'platform': sys.platform,
                'timezone': datetime.utcnow().astimezone().tzname()
            }
            
            return env_info
        
        except Exception as e:
            logger.error(f"Error getting environment info: {e}")
            return {'error': str(e)}
    
    def _store_health_status(self, health_status: HealthStatus):
        """Store health status in history"""
        
        try:
            self.check_history.append(health_status)
            
            # Keep only last 1000 entries
            if len(self.check_history) > 1000:
                self.check_history = self.check_history[-1000:]
        
        except Exception as e:
            logger.error(f"Error storing health status: {e}")
    
    def get_health_history(self, hours: int = 24) -> List[Dict[str, Any]]:
        """Get health history for specified hours"""
        
        try:
            cutoff_time = datetime.utcnow() - timedelta(hours=hours)
            
            history = []
            for status in self.check_history:
                if status.timestamp >= cutoff_time:
                    history.append(asdict(status))
            
            return history
        
        except Exception as e:
            logger.error(f"Error getting health history: {e}")
            return []

# Import required modules
import os
import sys

# Global health checker instance
_health_checker = None

def get_health_checker(app=None) -> HealthChecker:
    """Get global health checker instance"""
    
    global _health_checker
    
    if _health_checker is None:
        _health_checker = HealthChecker(app)
    
    return _health_checker

def init_health_checker(app):
    """Initialize health checker with Flask app"""
    
    global _health_checker
    _health_checker = HealthChecker(app)
    return _health_checker

# Export classes
__all__ = [
    'HealthChecker',
    'HealthStatus',
    'ComponentHealth',
    'get_health_checker',
    'init_health_checker'
]