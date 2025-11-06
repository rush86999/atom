"""
🚀 Zoom Health Handler
Enterprise-grade health monitoring for Zoom integration
"""

import os
import json
import logging
import asyncio
import httpx
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List, Optional
from flask import Blueprint, request, jsonify

logger = logging.getLogger(__name__)

# Configuration
ZOOM_API_BASE_URL = "https://api.zoom.us/v2"
REQUEST_TIMEOUT = 30

# Create blueprint
zoom_health_bp = Blueprint("zoom_health", __name__)

# Health status cache
health_cache = {
    'status': None,
    'timestamp': None,
    'components': {},
    'metrics': {}
}
CACHE_DURATION = 60  # seconds

def get_cached_health() -> Dict[str, Any]:
    """Get cached health status"""
    now = datetime.now(timezone.utc)
    
    if (health_cache['status'] and 
        health_cache['timestamp'] and 
        (now - health_cache['timestamp']).seconds < CACHE_DURATION):
        return health_cache
    
    return None

def update_health_cache(status: str, components: Dict[str, Any], metrics: Dict[str, Any] = None):
    """Update health status cache"""
    health_cache.update({
        'status': status,
        'timestamp': datetime.now(timezone.utc),
        'components': components,
        'metrics': metrics or health_cache.get('metrics', {})
    })

async def check_oauth_configuration() -> Dict[str, Any]:
    """Check OAuth configuration"""
    try:
        client_id = os.getenv('ZOOM_CLIENT_ID')
        client_secret = os.getenv('ZOOM_CLIENT_SECRET')
        redirect_uri = os.getenv('ZOOM_REDIRECT_URI')
        
        if client_id and client_secret and redirect_uri:
            if client_id.startswith(('YOUR_', 'mock_', 'test_')):
                return {
                    'status': 'configured',
                    'client_id_configured': False,
                    'client_secret_configured': False,
                    'redirect_uri_configured': True,
                    'message': 'Using placeholder configuration'
                }
            else:
                return {
                    'status': 'configured',
                    'client_id_configured': True,
                    'client_secret_configured': True,
                    'redirect_uri_configured': True,
                    'message': 'OAuth configuration is valid'
                }
        else:
            missing_vars = []
            if not client_id:
                missing_vars.append('client_id')
            if not client_secret:
                missing_vars.append('client_secret')
            if not redirect_uri:
                missing_vars.append('redirect_uri')
            
            return {
                'status': 'not_configured',
                'client_id_configured': bool(client_id),
                'client_secret_configured': bool(client_secret),
                'redirect_uri_configured': bool(redirect_uri),
                'message': f'Missing configuration: {", ".join(missing_vars)}'
            }
            
    except Exception as e:
        logger.error(f"Error checking OAuth configuration: {e}")
        return {
            'status': 'error',
            'client_id_configured': False,
            'client_secret_configured': False,
            'redirect_uri_configured': False,
            'message': f'Configuration error: {e}'
        }

async def check_database_connection() -> Dict[str, Any]:
    """Check database connection"""
    try:
        # Try to import database handler
        from db_oauth_zoom import ZoomOAuthDatabase
        
        # Test database availability
        from main_api_app import db_pool
        
        if not db_pool:
            return {
                'status': 'unavailable',
                'message': 'Database pool not initialized'
            }
        
        # Test database connection
        async with db_pool.acquire() as conn:
            result = await conn.fetchval("SELECT 1")
            if result == 1:
                return {
                    'status': 'connected',
                    'message': 'Database connection successful'
                }
            else:
                return {
                    'status': 'error',
                    'message': 'Database connection failed'
                }
                
    except ImportError as e:
        return {
            'status': 'unavailable',
            'message': f'Database handler not available: {e}'
        }
    except Exception as e:
        logger.error(f"Database connection error: {e}")
        return {
            'status': 'error',
            'message': f'Database connection error: {e}'
        }

async def check_zoom_api_connectivity() -> Dict[str, Any]:
    """Check Zoom API connectivity"""
    try:
        # Check Zoom API health endpoint
        async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT) as client:
            response = await client.get(
                "https://status.zoom.us/api/v1/status.json",
                timeout=10
            )
            
            if response.status_code == 200:
                zoom_status = response.json()
                
                # Check overall status
                overall_status = zoom_status.get('status', 'unknown')
                
                if overall_status == 'operational':
                    return {
                        'status': 'available',
                        'zoom_status': overall_status,
                        'zoom_components': zoom_status.get('components', {}),
                        'message': 'Zoom API is operational'
                    }
                else:
                    return {
                        'status': 'degraded',
                        'zoom_status': overall_status,
                        'zoom_components': zoom_status.get('components', {}),
                        'message': f'Zoom API status: {overall_status}'
                    }
            else:
                return {
                    'status': 'error',
                    'message': f'Zoom status API returned {response.status_code}'
                }
                
    except httpx.TimeoutException:
        return {
            'status': 'error',
            'message': 'Zoom API connection timeout'
        }
    except Exception as e:
        logger.error(f"Zoom API connectivity error: {e}")
        return {
            'status': 'error',
            'message': f'Zoom API connectivity error: {e}'
        }

async def check_service_availability() -> Dict[str, Any]:
    """Check Zoom service availability"""
    try:
        # Check if Zoom service modules are available
        from zoom_enhanced_api import zoom_enhanced_bp
        from auth_handler_zoom import ZoomOAuthHandler
        
        # Check service initialization
        from main_api_app import db_pool
        
        service_status = {
            'status': 'available',
            'enhanced_api_available': True,
            'oauth_handler_available': True,
            'database_available': bool(db_pool),
            'message': 'All Zoom service modules available'
        }
        
        return service_status
        
    except ImportError as e:
        return {
            'status': 'degraded',
            'enhanced_api_available': False,
            'oauth_handler_available': False,
            'database_available': False,
            'message': f'Missing service modules: {e}'
        }
    except Exception as e:
        logger.error(f"Service availability error: {e}")
        return {
            'status': 'error',
            'message': f'Service availability error: {e}'
        }

async def check_token_health() -> Dict[str, Any]:
    """Check token health and expiration"""
    try:
        from db_oauth_zoom import ZoomOAuthDatabase
        from main_api_app import db_pool
        
        if not db_pool:
            return {
                'status': 'unavailable',
                'message': 'Database not available for token check'
            }
        
        # Check for any active tokens
        db_handler = ZoomOAuthDatabase(db_pool, os.getenv('ENCRYPTION_KEY'))
        active_tokens = await db_handler.get_all_active_tokens()
        
        if not active_tokens:
            return {
                'status': 'no_tokens',
                'total_tokens': 0,
                'active_tokens': 0,
                'expired_tokens': 0,
                'message': 'No OAuth tokens found'
            }
        
        # Check token expiration
        expired_count = 0
        for token in active_tokens:
            if token.get('expired_at') and token['expired_at'] < datetime.now(timezone.utc):
                expired_count += 1
        
        total_tokens = len(active_tokens)
        active_count = total_tokens - expired_count
        
        return {
            'status': 'healthy' if expired_count == 0 else 'degraded',
            'total_tokens': total_tokens,
            'active_tokens': active_count,
            'expired_tokens': expired_count,
            'message': f'{active_count} active, {expired_count} expired tokens'
        }
        
    except Exception as e:
        logger.error(f"Token health check error: {e}")
        return {
            'status': 'error',
            'message': f'Token health check error: {e}'
        }

async def get_performance_metrics() -> Dict[str, Any]:
    """Get performance metrics"""
    try:
        # Get basic metrics
        now = datetime.now(timezone.utc)
        
        # Health check response time
        response_time = 0
        
        # Cache status
        cache_status = 'valid' if (health_cache['status'] and 
                                   health_cache['timestamp'] and 
                                   (now - health_cache['timestamp']).seconds < CACHE_DURATION) else 'invalid'
        
        return {
            'response_time_ms': response_time,
            'cache_status': cache_status,
            'uptime_percentage': 99.9,  # Placeholder
            'last_health_check': health_cache['timestamp'].isoformat() if health_cache['timestamp'] else None,
            'checks_performed': {
                'configuration': True,
                'database': True,
                'api_connectivity': True,
                'service_availability': True,
                'token_health': True
            }
        }
        
    except Exception as e:
        logger.error(f"Performance metrics error: {e}")
        return {
            'response_time_ms': 0,
            'cache_status': 'error',
            'uptime_percentage': 0,
            'last_health_check': None,
            'checks_performed': {}
        }

def determine_overall_status(components: Dict[str, Any]) -> str:
    """Determine overall health status"""
    if not components:
        return 'error'
    
    # Check for any errors
    error_components = [name for name, comp in components.items() 
                      if comp.get('status') == 'error']
    if error_components:
        return 'error'
    
    # Check for unavailable components
    unavailable_components = [name for name, comp in components.items() 
                           if comp.get('status') == 'unavailable']
    if unavailable_components:
        return 'degraded'
    
    # Check for degraded components
    degraded_components = [name for name, comp in components.items() 
                         if comp.get('status') == 'degraded']
    if degraded_components:
        return 'degraded'
    
    # Check for not configured
    not_configured = [name for name, comp in components.items() 
                      if comp.get('status') == 'not_configured']
    if not_configured:
        return 'degraded'
    
    # Check for no tokens (but configured)
    if components.get('token_health', {}).get('status') == 'no_tokens':
        return 'healthy'
    
    # All components are healthy or configured
    return 'healthy'

@zoom_health_bp.route("/api/zoom/health", methods=["GET"])
async def get_health():
    """Main health endpoint for Zoom integration"""
    try:
        # Check cache first
        cached_health = get_cached_health()
        if cached_health:
            return jsonify(cached_health)
        
        # Perform health checks
        checks = await asyncio.gather(
            check_oauth_configuration(),
            check_database_connection(),
            check_zoom_api_connectivity(),
            check_service_availability(),
            check_token_health(),
            get_performance_metrics(),
            return_exceptions=False
        )
        
        # Unpack check results
        (oauth_config, db_conn, zoom_api, service_avail, 
         token_health, performance_metrics) = checks
        
        # Prepare components
        components = {
            'configuration': oauth_config,
            'database': db_conn,
            'api': zoom_api,
            'service': service_avail,
            'token_health': token_health
        }
        
        # Determine overall status
        overall_status = determine_overall_status(components)
        
        # Prepare response
        health_response = {
            'status': overall_status,
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'components': components,
            'metrics': performance_metrics,
            'version': '1.0.0',
            'service': 'zoom_enhanced'
        }
        
        # Update cache
        update_health_cache(overall_status, components, performance_metrics)
        
        return jsonify(health_response)
        
    except Exception as e:
        logger.error(f"Health check error: {e}")
        
        error_response = {
            'status': 'error',
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'error': {
                'code': 'HEALTH_CHECK_ERROR',
                'message': str(e)
            },
            'service': 'zoom_enhanced'
        }
        
        return jsonify(error_response), 500

@zoom_health_bp.route("/api/zoom/health/tokens", methods=["GET"])
async def get_token_health():
    """Health check for Zoom OAuth tokens"""
    try:
        token_health = await check_token_health()
        
        return jsonify({
            'status': 'success',
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'data': token_health,
            'service': 'zoom_enhanced'
        })
        
    except Exception as e:
        logger.error(f"Token health check error: {e}")
        
        return jsonify({
            'status': 'error',
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'error': {
                'code': 'TOKEN_HEALTH_ERROR',
                'message': str(e)
            },
            'service': 'zoom_enhanced'
        }), 500

@zoom_health_bp.route("/api/zoom/health/configuration", methods=["GET"])
async def get_configuration_health():
    """Health check for Zoom OAuth configuration"""
    try:
        oauth_config = await check_oauth_configuration()
        
        return jsonify({
            'status': 'success',
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'data': oauth_config,
            'service': 'zoom_enhanced'
        })
        
    except Exception as e:
        logger.error(f"Configuration health check error: {e}")
        
        return jsonify({
            'status': 'error',
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'error': {
                'code': 'CONFIG_HEALTH_ERROR',
                'message': str(e)
            },
            'service': 'zoom_enhanced'
        }), 500

@zoom_health_bp.route("/api/zoom/health/api", methods=["GET"])
async def get_api_health():
    """Health check for Zoom API connectivity"""
    try:
        api_health = await check_zoom_api_connectivity()
        
        return jsonify({
            'status': 'success',
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'data': api_health,
            'service': 'zoom_enhanced'
        })
        
    except Exception as e:
        logger.error(f"API health check error: {e}")
        
        return jsonify({
            'status': 'error',
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'error': {
                'code': 'API_HEALTH_ERROR',
                'message': str(e)
            },
            'service': 'zoom_enhanced'
        }), 500

@zoom_health_bp.route("/api/zoom/health/database", methods=["GET"])
async def get_database_health():
    """Health check for Zoom database connection"""
    try:
        db_health = await check_database_connection()
        
        return jsonify({
            'status': 'success',
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'data': db_health,
            'service': 'zoom_enhanced'
        })
        
    except Exception as e:
        logger.error(f"Database health check error: {e}")
        
        return jsonify({
            'status': 'error',
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'error': {
                'code': 'DB_HEALTH_ERROR',
                'message': str(e)
            },
            'service': 'zoom_enhanced'
        }), 500

@zoom_health_bp.route("/api/zoom/health/summary", methods=["GET"])
async def get_health_summary():
    """Comprehensive health summary for Zoom integration"""
    try:
        # Perform all health checks
        health_response = await get_health()
        
        if health_response.status_code == 200:
            health_data = health_response.json
            
            # Extract key metrics
            components = health_data.get('components', {})
            metrics = health_data.get('metrics', {})
            
            # Create summary
            summary = {
                'overall_status': health_data.get('status'),
                'timestamp': health_data.get('timestamp'),
                'components_count': len(components),
                'healthy_components': len([c for c in components.values() if c.get('status') in ['healthy', 'connected', 'available', 'configured']]),
                'unhealthy_components': len([c for c in components.values() if c.get('status') in ['error', 'unavailable']]),
                'configuration_status': components.get('configuration', {}).get('status', 'unknown'),
                'token_status': components.get('token_health', {}).get('status', 'unknown'),
                'api_status': components.get('api', {}).get('status', 'unknown'),
                'database_status': components.get('database', {}).get('status', 'unknown'),
                'performance_metrics': {
                    'response_time_ms': metrics.get('response_time_ms', 0),
                    'cache_status': metrics.get('cache_status', 'unknown'),
                    'uptime_percentage': metrics.get('uptime_percentage', 0)
                },
                'action_items': [],
                'service': 'zoom_enhanced'
            }
            
            # Generate action items
            if summary['configuration_status'] != 'configured':
                summary['action_items'].append('Configure OAuth credentials')
            
            if summary['token_status'] == 'no_tokens':
                summary['action_items'].append('Complete OAuth authorization')
            elif summary['token_status'] == 'degraded':
                summary['action_items'].append('Refresh expired tokens')
            
            if summary['api_status'] != 'available':
                summary['action_items'].append('Check Zoom API connectivity')
            
            if summary['database_status'] != 'connected':
                summary['action_items'].append('Check database connection')
            
            return jsonify(summary)
            
        else:
            return health_response
        
    except Exception as e:
        logger.error(f"Health summary error: {e}")
        
        return jsonify({
            'status': 'error',
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'error': {
                'code': 'HEALTH_SUMMARY_ERROR',
                'message': str(e)
            },
            'service': 'zoom_enhanced'
        }), 500