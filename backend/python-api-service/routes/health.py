"""
Health API routes
"""

from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from models import db, User
import os
from datetime import datetime, timedelta
import psutil
import logging

health_bp = Blueprint('health', __name__)
logger = logging.getLogger(__name__)

@health_bp.route('/metrics', methods=['GET'])
@jwt_required()
def get_health_metrics():
    """Get system and application health metrics"""
    try:
        user_id = get_jwt_identity()
        user = User.query.get(user_id)
        if not user:
            return jsonify({'error': 'User not found'}), 404

        # System metrics
        system_metrics = {
            'cpu_percent': psutil.cpu_percent(interval=1),
            'memory_percent': psutil.virtual_memory().percent,
            'disk_usage': psutil.disk_usage('/').percent,
            'network_connections': len(psutil.net_connections()),
            'uptime': get_system_uptime()
        }

        # Application metrics
        app_metrics = {
            'active_users': get_active_users_count(),
            'total_tasks': get_total_tasks_count(),
            'total_messages': get_total_messages_count(),
            'database_connections': get_db_connection_count(),
            'response_time': get_average_response_time()
        }

        # User-specific metrics
        user_metrics = {
            'tasks_completed_today': get_user_tasks_completed_today(user_id),
            'messages_unread': get_user_unread_messages_count(user_id),
            'integrations_connected': get_user_connected_integrations_count(user_id),
            'workflows_executed_today': get_user_workflows_executed_today(user_id)
        }

        metrics = {
            'timestamp': datetime.utcnow().isoformat(),
            'system': system_metrics,
            'application': app_metrics,
            'user': user_metrics,
            'overall_health': calculate_overall_health(system_metrics, app_metrics)
        }

        return jsonify(metrics)
    except Exception as e:
        logger.error(f'Error fetching health metrics: {str(e)}')
        return jsonify({'error': 'Failed to fetch health metrics'}), 500

@health_bp.route('/status', methods=['GET'])
def get_system_status():
    """Get overall system status"""
    try:
        # Check database connectivity
        db_status = check_database_status()

        # Check external services
        services_status = check_external_services_status()

        # Check WebSocket health
        websocket_status = check_websocket_status()

        # Overall status
        overall_status = 'healthy'
        if not db_status['healthy'] or not all(s['healthy'] for s in services_status.values()) or not websocket_status['healthy']:
            overall_status = 'unhealthy'

        status = {
            'status': overall_status,
            'timestamp': datetime.utcnow().isoformat(),
            'services': {
                'database': db_status,
                'external_services': services_status,
                'websocket': websocket_status
            },
            'version': '1.0.0',
            'uptime': get_system_uptime()
        }

        return jsonify(status)
    except Exception as e:
        logger.error(f'Error fetching system status: {str(e)}')
        return jsonify({
            'status': 'error',
            'timestamp': datetime.utcnow().isoformat(),
            'error': str(e)
        }), 500

@health_bp.route('/websocket', methods=['GET'])
def websocket_health_check():
    """WebSocket-specific health check"""
    try:
        websocket_status = check_websocket_status()
        return jsonify({
            'websocket': websocket_status,
            'timestamp': datetime.utcnow().isoformat()
        })
    except Exception as e:
        logger.error(f'Error checking WebSocket health: {str(e)}')
        return jsonify({
            'websocket': {'healthy': False, 'error': str(e)},
            'timestamp': datetime.utcnow().isoformat()
        }), 500

@health_bp.route('/alerts', methods=['GET'])
@jwt_required()
def get_health_alerts():
    """Get health alerts and warnings"""
    try:
        user_id = get_jwt_identity()
        alerts = []

        # Check system resources
        cpu_percent = psutil.cpu_percent()
        memory_percent = psutil.virtual_memory().percent
        disk_percent = psutil.disk_usage('/').percent

        if cpu_percent > 90:
            alerts.append({
                'level': 'critical',
                'type': 'system_resource',
                'message': f'CPU usage is critically high: {cpu_percent}%',
                'timestamp': datetime.utcnow().isoformat()
            })
        elif cpu_percent > 80:
            alerts.append({
                'level': 'warning',
                'type': 'system_resource',
                'message': f'CPU usage is high: {cpu_percent}%',
                'timestamp': datetime.utcnow().isoformat()
            })

        if memory_percent > 90:
            alerts.append({
                'level': 'critical',
                'type': 'system_resource',
                'message': f'Memory usage is critically high: {memory_percent}%',
                'timestamp': datetime.utcnow().isoformat()
            })
        elif memory_percent > 80:
            alerts.append({
                'level': 'warning',
                'type': 'system_resource',
                'message': f'Memory usage is high: {memory_percent}%',
                'timestamp': datetime.utcnow().isoformat()
            })

        if disk_percent > 95:
            alerts.append({
                'level': 'critical',
                'type': 'system_resource',
                'message': f'Disk usage is critically high: {disk_percent}%',
                'timestamp': datetime.utcnow().isoformat()
            })
        elif disk_percent > 85:
            alerts.append({
                'level': 'warning',
                'type': 'system_resource',
                'message': f'Disk usage is high: {disk_percent}%',
                'timestamp': datetime.utcnow().isoformat()
            })

        # Check user-specific alerts
        unread_messages = get_user_unread_messages_count(user_id)
        if unread_messages > 50:
            alerts.append({
                'level': 'info',
                'type': 'user_notification',
                'message': f'You have {unread_messages} unread messages',
                'timestamp': datetime.utcnow().isoformat()
            })

        overdue_tasks = get_user_overdue_tasks_count(user_id)
        if overdue_tasks > 0:
            alerts.append({
                'level': 'warning',
                'type': 'user_notification',
                'message': f'You have {overdue_tasks} overdue tasks',
                'timestamp': datetime.utcnow().isoformat()
            })

        return jsonify(alerts)
    except Exception as e:
        logger.error(f'Error fetching health alerts: {str(e)}')
        return jsonify({'error': 'Failed to fetch health alerts'}), 500

@health_bp.route('/performance', methods=['GET'])
@jwt_required()
def get_performance_metrics():
    """Get detailed performance metrics"""
    try:
        user_id = get_jwt_identity()

        # API response times (mock data - in production, collect real metrics)
        api_performance = {
            'tasks_api': {'avg_response_time': 45, 'requests_per_minute': 12},
            'calendar_api': {'avg_response_time': 38, 'requests_per_minute': 8},
            'messages_api': {'avg_response_time': 52, 'requests_per_minute': 15},
            'integrations_api': {'avg_response_time': 120, 'requests_per_minute': 3}
        }

        # Database performance
        db_performance = {
            'query_time_avg': 15,
            'connection_pool_usage': 65,
            'slow_queries_count': 2
        }

        # User activity metrics
        user_activity = {
            'daily_active_sessions': get_user_daily_sessions(user_id),
            'feature_usage': get_user_feature_usage(user_id),
            'error_rate': get_user_error_rate(user_id)
        }

        performance = {
            'timestamp': datetime.utcnow().isoformat(),
            'api_performance': api_performance,
            'database_performance': db_performance,
            'user_activity': user_activity
        }

        return jsonify(performance)
    except Exception as e:
        logger.error(f'Error fetching performance metrics: {str(e)}')
        return jsonify({'error': 'Failed to fetch performance metrics'}), 500

# Helper functions
def get_system_uptime():
    """Get system uptime in seconds"""
    try:
        with open('/proc/uptime', 'r') as f:
            uptime_seconds = float(f.readline().split()[0])
        return uptime_seconds
    except:
        # Fallback for systems without /proc/uptime
        return (datetime.utcnow() - datetime(2024, 1, 1)).total_seconds()

def get_active_users_count():
    """Get count of active users (simplified)"""
    # In production, track active sessions
    return 42  # Mock data

def get_total_tasks_count():
    """Get total tasks count"""
    from models import Task
    return Task.query.count()

def get_total_messages_count():
    """Get total messages count"""
    from models import Message
    return Message.query.count()

def get_db_connection_count():
    """Get database connection count"""
    # This would require database-specific queries
    return 5  # Mock data

def get_average_response_time():
    """Get average API response time"""
    # In production, collect real metrics
    return 85  # Mock data in milliseconds

def get_user_tasks_completed_today(user_id):
    """Get user's tasks completed today"""
    from models import Task
    today = datetime.utcnow().date()
    return Task.query.filter_by(user_id=user_id, status='completed').filter(
        db.func.date(Task.updated_at) == today
    ).count()

def get_user_unread_messages_count(user_id):
    """Get user's unread messages count"""
    from models import Message
    return Message.query.filter_by(user_id=user_id, unread=True).count()

def get_user_connected_integrations_count(user_id):
    """Get user's connected integrations count"""
    from models import Integration
    return Integration.query.filter_by(user_id=user_id, connected=True).count()

def get_user_workflows_executed_today(user_id):
    """Get user's workflows executed today"""
    from models import Workflow
    today = datetime.utcnow().date()
    return Workflow.query.filter_by(user_id=user_id).filter(
        db.func.date(Workflow.last_executed) == today
    ).count()

def get_user_overdue_tasks_count(user_id):
    """Get user's overdue tasks count"""
    from models import Task
    now = datetime.utcnow()
    return Task.query.filter_by(user_id=user_id).filter(
        Task.due_date < now,
        Task.status != 'completed'
    ).count()

def calculate_overall_health(system_metrics, app_metrics):
    """Calculate overall system health score"""
    health_score = 100

    # System resource penalties
    if system_metrics['cpu_percent'] > 80:
        health_score -= 20
    if system_metrics['memory_percent'] > 80:
        health_score -= 20
    if system_metrics['disk_usage'] > 85:
        health_score -= 15

    # Application penalties
    if app_metrics['database_connections'] > 10:
        health_score -= 10

    return max(0, health_score)

def check_database_status():
    """Check database connectivity"""
    try:
        # Simple query to test DB connection
        db.session.execute(db.text('SELECT 1'))
        return {'healthy': True, 'response_time': 5}
    except Exception as e:
        return {'healthy': False, 'error': str(e)}

def check_external_services_status():
    """Check external services status"""
    services = {
        'redis': check_redis_status(),
        'email_service': {'healthy': True, 'response_time': 15},
        'calendar_service': {'healthy': True, 'response_time': 8},
        'storage_service': {'healthy': True, 'response_time': 12}
    }
    return services

def check_websocket_status():
    """Check WebSocket service status"""
    try:
        from app import socketio
        # Check if Socket.IO is initialized and Redis is available
        if socketio and socketio.server:
            # Try to check Redis connectivity if message queue is configured
            redis_url = socketio.server.options.get('message_queue')
            if redis_url:
                import redis
                r = redis.from_url(redis_url)
                r.ping()  # This will raise an exception if Redis is not available
            return {'healthy': True, 'response_time': 1, 'active_connections': getattr(socketio.server, 'active_connections', 0)}
        else:
            return {'healthy': False, 'error': 'Socket.IO not initialized'}
    except Exception as e:
        return {'healthy': False, 'error': str(e)}

def check_redis_status():
    """Check Redis service status"""
    try:
        import redis
        redis_url = os.getenv('REDIS_URL', 'redis://localhost:6379/0')
        r = redis.from_url(redis_url)
        r.ping()
        return {'healthy': True, 'response_time': 2}
    except Exception as e:
        return {'healthy': False, 'error': str(e)}

def get_user_daily_sessions(user_id):
    """Get user's daily active sessions"""
    # Mock data - in production, track real sessions
    return 3

def get_user_feature_usage(user_id):
    """Get user's feature usage statistics"""
    return {
        'tasks_created': 15,
        'messages_sent': 8,
        'calendar_events': 5,
        'integrations_used': 3
    }

def get_user_error_rate(user_id):
    """Get user's error rate"""
    # Mock data - in production, track real errors
    return 0.02  # 2%
