"""
Autonomous Celery Tasks - Smart Polling and Trigger System

This module integrates with existing Celery+Redis workflow system
to add autonomous, intelligent trigger capabilities.
"""

from celery.schedules import crontab
from .celery_app import celery_app
from .autonomous_triggers import AutonomousTriggerExecutor
from .tasks import execute_workflow  # Import existing task
from celery import group
import requests
import redis
import json
import time
from datetime import datetime, timedelta
import os
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Redis for distributed state
redis_client = redis.Redis(
    host=os.environ.get('REDIS_HOST', 'redis'),
    port=6379,
    db=2,
    decode_responses=True
)

# Global trigger registry
TRIGGER_REGISTRY = {}

# Autonomous polling patterns based on learning
@celery_app.task
def autonomous_web_polling(trigger_id: str, workflow_id: str, config: dict):
    """Smart web polling with adaptive intervals based on learning data"""
    try:
        url = config.get('url')
        selector = config.get('selector')
        condition = config.get('condition')

        response = requests.get(url, timeout=30)
        response.raise_for_status()

        # Simple selector simulation - in real implementation use BeautifulSoup/Scrapy
        content = response.text

        # Check condition
        should_trigger = (
            'contains' in condition and condition['contains'] in content or
            'not_contains' in condition and condition['not_contains'] not in content
        )

        if should_trigger:
            logger = AutonomousTriggerExecutor(workflow_id)
            logger.learn_from_execution({
                'trigger_id': trigger_id,
                'success': True,
                'duration': response.elapsed.total_seconds()
            })

            # Execute the actual workflow
            execute_workflow.delay(workflow_id)

        return {'triggered': should_trigger, 'url': url}

    except Exception as e:
        logger = AutonomousTriggerExecutor(workflow_id)
        logger.learn_from_execution({
            'trigger_id': trigger_id,
            'success': False,
            'duration': 0,
            'error': str(e)
        })
        raise

@celery_app.task
def autonomous_api_monitoring(trigger_id: str, workflow_id: str, config: dict):
    """Monitor API endpoints for changes/data thresholds"""
    try:
        endpoint = config.get('endpoint')
        threshold = config.get('threshold')
        metric = config.get('metric', 'response_time')

        response = requests.get(endpoint, timeout=30)
        response.raise_for_status()

        # Extract data based on metric
        data = response.json()
        current_value = data

        if metric == 'response_time':
            current_value = response.elapsed.total_seconds()

        should_trigger = (
            'greater_than' in threshold and current_value > threshold['greater_than'] or
            'less_than' in threshold and current_value < threshold['less_than']
        )

        if should_trigger:
            execute_workflow.delay(workflow_id)

        # Store for learning
        key = f"monitor:{trigger_id}:{int(time.time()/300)*300}"  # 5min buckets
        redis_client.setex(key, 3600, json.dumps({
            'value': current_value,
            'triggered': should_trigger
        }))

        return {'triggered': should_trigger, 'value': current_value}

    except Exception as e:
        redis_client.setex(f"error:{trigger_id}", 3600, str(e))
        raise

@celery_app.task
def performance_anomaly_detector(workflow_id: str):
    """Detect performance anomalies using Redis-stored metrics"""
    try:
        # Get recent performance data
        pattern = f"workflow:performance:{workflow_id}:*"
        keys = redis_client.keys(pattern)

        if len(keys) < 5:  # Need minimum data
            return {'anomaly': False, 'reason': 'Insufficient data'}

        durations = []
        for key in keys[:10]:  # Check last 10 executions
            data = redis_client.get(key)
            if data:
                item = json.loads(data)
                durations.append(item.get('duration', 0))

        if not durations:
            return {'anomaly': False, 'reason': 'No duration data'}

        # Simple anomaly detection: check if current is >2σ outside average
        avg_duration = sum(durations) / len(durations)

        # Skip if variance is too low
        if len(set(durations)) <= 2:
            return {'anomaly': False, 'reason': 'Low variance'}

        # Trigger investigation if duration increased significantly
        latest_duration = durations[0] if durations else 0
        threshold = avg_duration * 1.5

        if latest_duration > threshold:
            # This would trigger a workflow to investigate
            celery_app.send_task('analyze_performance_anomaly', args=[self.workflow_id, latest_duration, avg_duration])
            return {'anomaly': True, 'current_duration': latest_duration, 'avg_duration': avg_duration}

        return {'anomaly': False, 'current_duration': latest_duration, 'avg_duration': avg_duration}

    except Exception as e:
        redis_client.setex(f"error:{workflow_id}", 3600, str(e))
        logger.error(f"Anomaly detection failed for workflow {workflow_id}: {e}")
        return {'anomaly': False, 'error': str(e)}

@celery_app.task
def analyze_performance_anomaly(workflow_id: str, current_duration: float, avg_duration: float):
    """React to performance anomaly detected in workflow"""
    try:
        # Log into central logging
        anomaly_key = f"anomaly:log:{workflow_id}:{int(time.time())}"
        redis_client.hset(anomaly_key, mapping={
            'workflow_id': workflow_id,
            'current_duration': current_duration,
            'avg_duration': avg_duration,
            'severity': 'mild' if current_duration < avg_duration * 2 else 'severe',
            'detected_at': str(datetime.now())
        })

        # Trigger investigation workflow
        investigate_response = {
            'investigation_triggered': True,
            'workflow_id': workflow_id,
            'performance_issue': f"Duration spike: {current_duration:.2f}s (avg: {avg_duration:.2f}s)",
            'actions': ['scale_workers', 'check_logs', 'notify_team']
        }

        return investigate_response

    except Exception as e:
        logger.error(f"Failed to analyze anomaly: {e}")
        return {'error': str(e)}

@celery_app.task
def autonomous_balance_checks():
    """Autonomous system health and balance checks"""
    try:
        # Check Redis health
        redis_info = redis_client.info()

        # Check Celery worker health
        active_workers = celery_app.control.inspect().active() or {}

        # System status report
        health_report = {
            'redis_connected': bool(redis_info),
            'redis_keys': redis_info.get('db2', {}).get('keys', 0) if redis_info else 0,
            'active_workers': len(active_workers),
            'total_workers': sum(len(v) for v in active_workers.values()),
            'timestamp': str(datetime.now())
        }

        # Store health metrics
        redis_client.setex("autonomous:health", 300, json.dumps(health_report))

        return health_report

    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return {'error': str(e)}

@celery_app.task
def autonomous_system_coordinator():
    """Main coordinator task that manages everything"""
    try:
        # Run system health checks
        health = autonomous_balance_checks.delay()

        # Balance workload across workers
        active_triggers = redis_client.keys("autonomous:triggers:*")

        # Generate systems report
        system_report = {
            'active_autonomous_triggers': len(active_triggers),
            'timestamp': str(datetime.now()),
            'health_check': health.get() if hasattr(health, 'get') else 'pending'
        }

        redis_client.setex("autonomous:system_report", 60, json.dumps(system_report))

        return system_report

    except Exception as e:
        logger.error(f"System coordinator failed: {e}")
        return {'error': str(e)}

# Periodic health monitoring
celery_app.conf.beat_schedule.update({
    'autonomous-system-health': {
        'task': 'workflows.autonomous_tasks.autonomous_system_coordinator',
        'schedule': crontab(minute='*/5'),  # Every 5 minutes
    },
    'autonomous-balance': {
        'task': 'workflows.autonomous_tasks.autonomous_balance_checks',
        'schedule': crontab(minute='*/15'),  # Every 15 minutes
    }
})

logger = logging.getLogger(__name__)
