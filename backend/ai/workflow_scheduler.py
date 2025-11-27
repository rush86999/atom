import logging
import os
from datetime import datetime
from typing import Dict, List, Any, Optional
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger
from apscheduler.triggers.date import DateTrigger

logger = logging.getLogger(__name__)

class WorkflowScheduler:
    """
    Manages scheduled workflow executions using APScheduler.
    Persists jobs to a SQLite database.
    """
    
    def __init__(self, db_url: str = "sqlite:///jobs.sqlite"):
        self.job_store_url = db_url
        self.scheduler = AsyncIOScheduler(
            jobstores={
                'default': SQLAlchemyJobStore(url=self.job_store_url)
            }
        )
        self.engine = None # Will be set later to avoid circular imports
        
    def start(self):
        """Start the scheduler"""
        if not self.scheduler.running:
            self.scheduler.start()
            logger.info("WorkflowScheduler started")
            
    def shutdown(self):
        """Shutdown the scheduler"""
        if self.scheduler.running:
            self.scheduler.shutdown()
            logger.info("WorkflowScheduler shutdown")
            
    def set_engine(self, engine):
        """Set the AutomationEngine instance"""
        self.engine = engine

    @staticmethod
    async def _execute_job(workflow_id: str, input_data: Dict[str, Any] = None):
        """Internal job function to execute a workflow"""
        logger.info(f"Executing scheduled workflow: {workflow_id}")
        
        try:
            # Instantiate engine on demand to ensure fresh state and avoid circular imports at module level
            from backend.ai.automation_engine import AutomationEngine
            engine = AutomationEngine()
            
            # Load workflows
            from backend.core.workflow_endpoints import load_workflows
            workflows = load_workflows()
            workflow_def = next((w for w in workflows if w['id'] == workflow_id), None)
            
            if workflow_def:
                # Execute with a special execution ID prefix
                execution_id = f"sched_{datetime.now().strftime('%Y%m%d%H%M%S')}_{workflow_id[:8]}"
                await engine.execute_workflow_definition(workflow_def, input_data or {}, execution_id=execution_id)
                logger.info(f"Scheduled execution {execution_id} completed")
            else:
                logger.error(f"Scheduled workflow {workflow_id} not found")
                
        except Exception as e:
            logger.error(f"Error executing scheduled workflow {workflow_id}: {e}")

    def schedule_workflow(self, workflow_id: str, trigger_type: str, trigger_config: Dict[str, Any], input_data: Dict[str, Any] = None) -> str:
        """
        Schedule a workflow execution.
        
        Args:
            workflow_id: ID of the workflow to schedule
            trigger_type: 'cron', 'interval', or 'date'
            trigger_config: Configuration for the trigger (e.g. cron expression)
            input_data: Optional input data for the workflow
            
        Returns:
            job_id: The ID of the scheduled job
        """
        job_id = f"job_{workflow_id}_{datetime.now().timestamp()}"
        
        trigger = None
        if trigger_type == 'cron':
            trigger = CronTrigger(**trigger_config)
        elif trigger_type == 'interval':
            trigger = IntervalTrigger(**trigger_config)
        elif trigger_type == 'date':
            trigger = DateTrigger(**trigger_config)
        else:
            raise ValueError(f"Unsupported trigger type: {trigger_type}")
            
        self.scheduler.add_job(
            self._execute_job,
            trigger=trigger,
            args=[workflow_id, input_data],
            id=job_id,
            replace_existing=True
        )
        
        logger.info(f"Scheduled workflow {workflow_id} with {trigger_type} trigger (Job ID: {job_id})")
        return job_id

    def remove_schedule(self, job_id: str):
        """Remove a scheduled job"""
        try:
            self.scheduler.remove_job(job_id)
            logger.info(f"Removed job {job_id}")
        except Exception as e:
            logger.error(f"Error removing job {job_id}: {e}")

    def list_jobs(self) -> List[Dict[str, Any]]:
        """List all scheduled jobs"""
        jobs = []
        for job in self.scheduler.get_jobs():
            jobs.append({
                "id": job.id,
                "next_run_time": job.next_run_time.isoformat() if job.next_run_time else None,
                "trigger": str(job.trigger)
            })
        return jobs

# Global instance
workflow_scheduler = WorkflowScheduler()
