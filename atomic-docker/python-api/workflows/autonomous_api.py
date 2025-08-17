"""
Autonomous API Endpoints for React Flow Workflows
Integrates with existing Celery+Redis infrastructure for smart triggers
"""

from fastapi import FastAPI, HTTPException, Depends, BackgroundTasks
from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
import json
import time
import redis
import os
from sqlalchemy.orm import Session
from .celery_app import celery_app
from .tasks import execute_workflow
from .autonomous_triggers import AutonomousTrigger, AutonomousTriggerExecutor, TriggerFactory
from .autonomous_tasks import (
    autonomous_web_polling,
    autonomous_api_monitoring,
    performance_anomaly_detector
)

app = FastAPI()

# Redis connection
redis_client = redis.Redis(
    host=os.environ.get('REDIS_HOST', 'redis'),
    port=6379,
    db=3,
    decode_responses=True
)

# Import from your existing models
from . import database, models

class AutonomousTriggerRequest(BaseModel):
    workflow_id: str
    trigger_type: str = Field(..., description="Type: schedule, web-polling, api-monitoring, anomaly-detection")
    parameters: Dict[str, Any]
    conditions: Dict[str, Any]
    schedule: Optional[str] = None
    enable_learning: bool = True

class TriggerResponse(BaseModel):
    id: str
    workflow_id: str
    status: str
    next_run: Optional[datetime]
    last_run: Optional[datetime]
    success_rate: float
    run_count: int

# API Endpoints

@app.post("/triggers/smart", response_model=TriggerResponse)
async def create_autonomous_trigger(trigger: AutonomousTriggerRequest):
    """Create a new autonomous trigger for existing workflow"""
    try:
        trigger_executor = AutonomousTriggerExecutor(trigger.workflow_id)

        # Create appropriate trigger based on type
        if trigger.trigger_type == "sales-threshold":
            new_trigger = TriggerFactory.create_sales_threshold_trigger(
                trigger.workflow_id,
                trigger.parameters.get('threshold', 25.0)
            )

        elif trigger.trigger_type == "web-polling":
            new_trigger = AutonomousTrigger(
                id=f"webpoll_{int(time.time())}",
                workflow_id=trigger.workflow_id,
                trigger_type="web-polling",
                parameters=trigger.parameters,
                conditions=trigger.conditions,
                learning_config={'enabled': trigger.enable_learning},
                schedule=trigger.schedule
            )

        elif trigger.trigger_type == "api-monitoring":
            new_trigger = AutonomousTrigger(
                id=f"apimonitor_{int(time.time())}",
                workflow_id=trigger.workflow_id,
                trigger_type="api-monitoring",
                parameters=trigger.parameters,
                conditions=trigger.conditions,
                learning_config={'enabled': trigger.enable_learning}
            )

        else:
            raise HTTPException(400, f"Unsupported trigger type: {trigger.trigger_type}")

        trigger_executor.register_trigger(new_trigger)

        # Schedule the autonomous task with Celery
        if trigger.schedule:
            self._schedule_periodic_task(trigger.trigger_type, new_trigger)

        return TriggerResponse(
            id=new_trigger.id,
            workflow_id=new_trigger.workflow_id,
            status="active" if new_trigger.enabled else "inactive",
            next_run=None,  # Will be calculated based on learning
            last_run=None,
            success_rate=new_trigger.success_rate,
            run_count=new_trigger.run_count
        )

    except Exception as e:
        raise HTTPException(500, f"Failed to create trigger: {str(e)}")

@app.post("/triggers/predictive-schedule")
async def optimize_workflow_schedule(workflow_id: str):
    """Generate optimal schedule based on historical execution data"""
    try:
        metrics = redis_client.hgetall(f"autonomous:metrics:{workflow_id}")

        if not metrics:
            return {"prediction": None, "reason": "Insufficient historical data"}

        # Analyze execution patterns
        historical_runs = load_scheduling_data(workflow_id)
        if len(historical_runs) < 5:
            return {"suggestion": "daily_11:00", "confidence": 0.3}

        # Simple ML: Find optimal hour based on success rates
        hour_analysis = analyze_optimal_hour(historical_runs)
        best_hour = max(hour_analysis.items(), key=lambda x: x[1]['success_rate'])

        return {
            "optimal_schedule": f"0 {best_hour[0]} * * *",  # Cron format
            "confidence": best_hour[1]['confidence'],
            "current_success_rate": best_hour[1]['success_rate'],
            "evidence": hour_analysis
        }

    except Exception as e:
        raise HTTPException(500, f"Scheduling optimization failed: {str(e)}")
