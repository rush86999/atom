"""
Autonomous Triggers for Celery-Redis Workflows

This module provides intelligent, autonomous trigger detection and execution
for existing React Flow workflows running on Celery/Redis infrastructure.
"""

from celery import shared_task, group, chain
from celery.schedules import crontab
from datetime import datetime, timedelta
import redis
import json
import requests
import hashlib
from sqlalchemy.orm import Session
from typing import Dict, Any, List, Optional
import logging
from dataclasses import dataclass
import os
from .celery_app import celery_app
from . import database, models

# Redis connection for triggers
redis_client = redis.Redis(
    host=os.environ.get('REDIS_HOST', 'redis'),
    port=6379,
    db=1,
    decode_responses=True
)

# Configuration
MAX_RETRIES = 3
TRIGGER_LEARNING_WINDOW = 3600  # 1 hour
ANOMALY_DETECTION_THRESHOLD = 0.1

import os

logger = logging.getLogger(__name__)

@dataclass
class AutonomousTrigger:
    """Smart trigger with learning capabilities for existing workflows"""
    id: str
    workflow_id: str
    trigger_type: str  # 'schedule', 'webhook', 'condition', 'anomaly', 'predictive'
    parameters: Dict[str, Any]
    conditions: Dict[str, Any]
    learning_config: Dict[str, Any]
    enabled: bool = True
    last_run: Optional[datetime] = None
    run_count: int = 0
    success_rate: float = 1.0

class AutonomousTriggerExecutor:
    """Self-learning trigger executor for Celery workflows"""

    def __init__(self, workflow_id: str):
        self.workflow_id = workflow_id
        self.trigger_key = f"autonomous:triggers:{workflow_id}"
        self.metrics_key = f"autonomous:metrics:{workflow_id}"

    def register_trigger(self, trigger: AutonomousTrigger) -> bool:
        """Register a new autonomous trigger with Redis"""
        try:
            # Store in Redis with TTL for learning
            key = f"{self.trigger_key}:{trigger.id}"
            trigger_data = {
                'id': trigger.id,
                'workflow_id': trigger.workflow_id,
                'trigger_type': trigger.trigger_type,
                'parameters': json.dumps(trigger.parameters),
                'conditions': json.dumps(trigger.conditions),
                'learning_config': json.dumps(trigger.learning_config),
                'enabled': trigger.enabled,
                'run_count': trigger.run_count,
                'success_rate': trigger.success_rate
            }

            redis_client.hset(key, mapping=trigger_data)
            redis_client.expire(key, TRIGGER_LEARNING_WINDOW)

            logger.info(f"Registered autonomous trigger {trigger.id} for workflow {trigger.workflow_id}")
            return True

        except Exception as e:
            logger.error(f"Failed to register trigger: {e}")
            return False

    def learn_from_execution(self, execution_data: Dict[str, Any]):
        """Update trigger learning based on execution results"""
        try:
            # Update success metrics
            trigger_id = execution_data.get('trigger_id', 'default')
            success = execution_data.get('success', False)
            duration = execution_data.get('duration', 0)

            # Get current metrics
            metrics_key = f"{self.metrics_key}:{trigger_id}"
            current_metrics = redis_client.hgetall(metrics_key) or {}

            run_count = int(current_metrics.get('run_count', 0))
            success_count = int(current_metrics.get('success_count', 0))

            # Update counts
            run_count += 1
            if success:
                success_count += 1

            success_rate = success_count / max(run_count, 1)

            # Store updated metrics
            redis_client.hset(metrics_key, mapping={
                'run_count': run_count,
                'success_count': success_count,
                'success_rate': success_rate,
                'last_execution': str(datetime.now()),
                'total_duration': int(current_metrics.get('total_duration', 0)) + duration
            })

        except Exception as e:
            logger.error(f"Learning update failed: {e}")

# Smart trigger factory
class TriggerFactory:
    @staticmethod
    def create_sales_threshold_trigger(workflow_id: str, threshold: float = 25.0) -> AutonomousTrigger:
        return AutonomousTrigger(
            id=f"sales_threshold_{hashlib.md5(f'{workflow_id}_{threshold}'.encode()).hexdigest()[:8]}",
            workflow_id=workflow_id,
            trigger_type='anomaly',
            parameters={'threshold_percentage': threshold},
            conditions={'sales_increase': threshold, 'time_window': '24h'},
            learning_config={
                'adapt_threshold': True,
                'min_executions': 5,
                'adjustment_factor': 0.1
            }
        )

    @staticmethod
    def create_web_monitoring_trigger(workflow_id: str, url: str, css_selector: str) -> AutonomousTrigger:
        return AutonomousTrigger(
            id=f"web_monitor_{hashlib.md5(f'{workflow_id}_{url}'.encode()).hexdigest()[:8]}",
            workflow_id=workflow_id,
            trigger_type='web-polling',
            parameters={'url': url, 'selector': css_selector, 'check_interval': 300},
            conditions={'element_changed': True, 'content_updated': True},
            learning_config={
                'optimize_interval': True,
                'min_success_rate': 0.8,
                'backoff_multiplier': 1.5
            }
        )

    @staticmethod
    def create_api_health_trigger(workflow_id: str, endpoint: str, threshold_ms: int = 2000) -> AutonomousTrigger:
        return AutonomousTrigger(
            id=f"api_health_{hashlib.md5(f'{workflow_id}_{endpoint}'.encode()).hexdigest()[:8]}",
            workflow_id=workflow_id,
            trigger_type='api-monitoring',
            parameters={'endpoint': endpoint, 'timeout': threshold_ms},
            conditions={'response_time': {'operator': 'gt', 'threshold': threshold_ms}},
            learning_config={
                'trend_detection': True,
                'predictive_alerts': True,
                'min_data_points': 10
            }
        )

    @staticmethod
    def create_performance_anomaly_trigger(workflow_id: str, metrics_threshold: float = 2.0) -> AutonomousTrigger:
        return AutonomousTrigger(
            id=f"perf_anomaly_{hashlib.md5(f'{workflow_id}'.encode()).hexdigest()[:8]}",
            workflow_id=workflow_id,
            trigger_type='anomaly',
            parameters={'z_score_threshold': metrics_threshold, 'lookback_hours': 24},
            conditions={'performance_degradation': True},
            learning_config={
                'adaptive_threshold': True,
                'seasonality_detection': True,
                'min_baseline_executions': 50
            }
        )

    @staticmethod
    def create_scheduled_trigger(workflow_id: str, cron_expression: str, adapt_schedule: bool = True) -> AutonomousTrigger:
        return AutonomousTrigger(
            id=f"scheduled_{hashlib.md5(f'{workflow_id}_{cron_expression}'.encode()).hexdigest()[:8]}",
            workflow_id=workflow_id,
            trigger_type='predictive',
            parameters={'cron_expression': cron_expression, 'optimize_for': 'success_rate'},
            conditions={'time_optimized': adapt_schedule},
            learning_config={
                'adapt_schedule': adapt_schedule,
                'optimization_window': 168,  # 1 week of data
                'min_confidence': 0.7
            }
        )

class AutonomousTriggerEngine:
    """Main engine for managing autonomous triggers"""

    def __init__(self, workflow_id: str):
        self.workflow_id = workflow_id
        self.executor = AutonomousTriggerExecutor(workflow_id)
        self.registry = []

    def start_all_triggers(self):
        """Start all autonomous triggers for this workflow"""
        try:
            # Get all triggers for this workflow
            pattern = f"autonomous:triggers:{self.workflow_id}:*"
            trigger_keys = redis_client.keys(pattern)

            for key in trigger_keys:
                trigger_data = redis_client.hgetall(key)
                if trigger_data:
                    trigger = AutonomousTrigger(
                        id=trigger_data['id'],
                        workflow_id=trigger_data['workflow_id'],
                        trigger_type=trigger_data['trigger_type'],
                        parameters=json.loads(trigger_data['parameters']),
                        conditions=json.loads(trigger_data['conditions']),
                        learning_config=json.loads(trigger_data['learning_config']),
                        enabled=bool(trigger_data.get('enabled', True)),
                        run_count=int(trigger_data.get('run_count', 0)),
                        success_rate=float(trigger_data.get('success_rate', 1.0))
                    )

                    # Schedule the trigger based on type
                    self._schedule_trigger(trigger)

        except Exception as e:
            logger.error(f"Failed to start triggers: {e}")

    def _schedule_trigger(self, trigger: AutonomousTrigger):
        """Schedule trigger execution with Celery"""
        try:
            from .autonomous_tasks import autonomous_web_polling, autonomous_api_monitoring, performance_anomaly_detector

            if trigger.trigger_type == 'web-polling':
                autonomous_web_polling.apply_async(
                    args=[trigger.id, trigger.workflow_id, trigger.parameters],
                    countdown=60  # Start in 60 seconds
                )

            elif trigger.trigger_type == 'api-monitoring':
                autonomous_api_monitoring.apply_async(
                    args=[trigger.id, trigger.workflow_id, trigger.parameters],
                    countdown=120
                )

            elif trigger.trigger_type == 'anomaly':
                performance_anomaly_detector.delay(trigger.workflow_id)

            elif trigger.trigger_type == 'predictive':
                # Schedule based on cron or learning
                if trigger.parameters.get('cron_expression'):
                    celery_app.conf.beat_schedule.update({
                        f'predictive-{trigger.id}': {
                            'task': 'workflows.tasks.execute_workflow',
                            'schedule': crontab(*trigger.parameters['cron_expression'].split()),
                            'args': [trigger.workflow_id]
                        }
                    })

        except Exception as e:
            logger.error(f"Failed to schedule trigger {trigger.id}: {e}")

    def stop_trigger(self, trigger_id: str):
        """Stop and disable a specific trigger"""
        try:
            key = f"autonomous:triggers:{self.workflow_id}:{trigger_id}"
            redis_client.hset(key, 'enabled', 'false')
            logger.info(f"Stopped trigger {trigger_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to stop trigger {trigger_id}: {e}")
            return False

    def gettrigger_status(self, trigger_id: str):
        """Get current trigger status and metrics"""
        try:
            key = f"autonomous:triggers:{self.workflow_id}:{trigger_id}"
            trigger_data = redis_client.hgetall(key)

            if not trigger_data:
                return None

            metrics_key = f"autonomous:metrics:{self.workflow_id}:{trigger_id}"
            metrics = redis_client.hgetall(metrics_key)

            return {
                'trigger': trigger_data,
                'metrics': metrics,
                'last_updated': str(datetime.now())
            }

        except Exception as e:
            logger.error(f"Failed to get trigger status: {e}")
            return None
        )

class AutonomousTriggerEngine:
    """Main engine for managing autonomous triggers"""

    def __init__(self, workflow_id: str):
        self.workflow_id = workflow_id
        self.executor = AutonomousTriggerExecutor(workflow_id)
        self.registry = []

    def start_all_triggers(self):
        """Start all autonomous triggers for this workflow"""
        try:
            # Get all triggers for this workflow
            pattern = f"autonomous:triggers:{self.workflow_id}:*"
            trigger_keys =
