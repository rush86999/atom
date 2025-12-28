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
    
    def __init__(self, db_url: Optional[str] = None):
        from core.config import get_config
        self.config = get_config()
        
        jobstores = {}
        
        # Use configured job store
        if self.config.scheduler.job_store_type == 'redis' and self.config.redis.enabled:
            try:
                from apscheduler.jobstores.redis import RedisJobStore
                jobstores['default'] = RedisJobStore(
                    host=self.config.redis.host,
                    port=self.config.redis.port,
                    db=self.config.redis.db,
                    password=self.config.redis.password
                )
                logger.info("WorkflowScheduler using RedisJobStore")
            except Exception as e:
                logger.warning(f"Failed to initialize RedisJobStore: {e}. Falling back to SQLAlchemy.")
                jobstores['default'] = SQLAlchemyJobStore(url=db_url or self.config.scheduler.job_store_url)
        else:
            job_store_url = db_url or self.config.scheduler.job_store_url
            jobstores['default'] = SQLAlchemyJobStore(url=job_store_url)
            logger.info(f"WorkflowScheduler using SQLAlchemyJobStore")

        self.scheduler = AsyncIOScheduler(
            jobstores=jobstores,
            job_defaults={
                'misfire_grace_time': self.config.scheduler.misfire_grace_time,
                'coalesce': self.config.scheduler.coalesce,
                'max_instances': self.config.scheduler.max_instances
            }
        )
        self.engine = None # Will be set later to avoid circular imports
        
    def start(self):
        """Start the scheduler"""
        if not self.scheduler.running:
            self.reschedule_system_pipelines()
            self.scheduler.start()
            logger.info("WorkflowScheduler started")

    def reschedule_system_pipelines(self):
        """Register or refresh System Pipelines (Memory Ingestion) based on settings"""
        try:
            from core.automation_settings import get_automation_settings
            settings = get_automation_settings().get_settings()
            pipeline_config = settings.get("pipelines", {})

            from integrations.atom_sales_memory_pipeline import sales_pipeline
            from integrations.atom_projects_memory_pipeline import projects_pipeline
            from integrations.atom_finance_memory_pipeline import finance_pipeline
            
            pipelines = {
                'sales': sales_pipeline,
                'projects': projects_pipeline,
                'finance': finance_pipeline
            }

            for name, pipeline in pipelines.items():
                config = pipeline_config.get(name, {})
                mode = config.get("mode", "scheduled")
                job_id = f"system_{name}_ingestion"

                if mode == "real_time":
                    # For real-time, we use a high-frequency interval (e.g., 1 minute)
                    trigger = IntervalTrigger(minutes=1)
                    logger.info(f"Setting {name} pipeline to REAL-TIME (1m interval)")
                else:
                    # Scheduled mode uses cron
                    cron_expr = config.get("cron", "*/30 * * * *" if name != 'finance' else "0 * * * *")
                    trigger = CronTrigger.from_crontab(cron_expr)
                    logger.info(f"Setting {name} pipeline to SCHEDULED ({cron_expr})")

                self.scheduler.add_job(
                    pipeline.run_pipeline,
                    trigger,
                    id=job_id,
                    replace_existing=True
                )

            logger.info("✓ System Memory Pipelines (Re)Scheduled")
        except Exception as e:
            logger.error(f"Error rescheduling system pipelines: {e}")
            
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
            from ai.automation_engine import AutomationEngine
            engine = AutomationEngine()
            
            # Load workflows
            from core.workflow_endpoints import load_workflows
            workflows = load_workflows()
            workflow_def = next((w for w in workflows if w.get('id') == workflow_id or w.get('workflow_id') == workflow_id), None)
            
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
        return job_id

    def schedule_workflow_cron(self, job_id: str, workflow_id: str, cron_expression: str):
        """Schedule a workflow using cron expression"""
        self.scheduler.add_job(
            self._execute_job,
            CronTrigger.from_crontab(cron_expression),
            args=[workflow_id],
            id=job_id,
            replace_existing=True
        )
        logger.info(f"Scheduled cron job {job_id} for workflow {workflow_id}: {cron_expression}")
        return job_id

    def schedule_workflow_interval(self, job_id: str, workflow_id: str, interval_minutes: int):
        """Schedule a workflow using interval"""
        self.scheduler.add_job(
            self._execute_job,
            IntervalTrigger(minutes=interval_minutes),
            args=[workflow_id],
            id=job_id,
            replace_existing=True
        )
        logger.info(f"Scheduled interval job {job_id} for workflow {workflow_id}: {interval_minutes}m")
        return job_id

    def schedule_workflow_once(self, job_id: str, workflow_id: str, run_date: str):
        """Schedule a workflow once at a specific date"""
        self.scheduler.add_job(
            self._execute_job,
            DateTrigger(run_date=run_date),
            args=[workflow_id],
            id=job_id,
            replace_existing=True
        )
        logger.info(f"Scheduled one-time job {job_id} for workflow {workflow_id} at {run_date}")
        return job_id

    def remove_job(self, job_id: str) -> bool:
        """Remove a scheduled job"""
        try:
            self.scheduler.remove_job(job_id)
            logger.info(f"Removed job {job_id}")
            return True
        except Exception:
            return False
        
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
