from datetime import datetime
import logging
import os
from typing import Any, Dict, List, Optional
from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.date import DateTrigger
from apscheduler.triggers.interval import IntervalTrigger

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

            # NOTE: integrations/atom_finance_memory_pipeline was removed
            # (commit 6561cf5b8 — broken syntax + missing stripe_service dep,
            # never worked). Its dangling import here silently killed
            # rescheduling of the sales/projects pipelines too, because the
            # ImportError aborted this whole method. Re-add only if the
            # module is ever revived with working deps.
            from integrations.atom_projects_memory_pipeline import projects_pipeline
            from integrations.atom_sales_memory_pipeline import sales_pipeline

            pipelines = {
                'sales': sales_pipeline,
                'projects': projects_pipeline,
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
                    cron_expr = config.get("cron", "*/30 * * * *")
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
    async def _execute_job(workflow_id: str, input_data: Dict[str, Any] = None, authorized: bool = False):
        """Internal job function to execute a workflow.

        R69: the schedule caller decides whether the scheduler may run critical
        definitions (steps or AutomationEngine nodes). Critical executions only
        fire when the scheduling user held WORKFLOW_MANAGE at schedule time —
        otherwise the fire is a no-op.
        """
        logger.info(f"Executing scheduled workflow: {workflow_id}")

        try:
            # Load workflows
            from core.workflow_endpoints import load_workflows
            from core.workflow_security import (
                has_critical_automation_nodes,
                has_critical_definition,
            )
            workflows = load_workflows()
            workflow_def = next((w for w in workflows if w.get('id') == workflow_id or w.get('workflow_id') == workflow_id), None)
            if workflow_def is None:
                # DB templates (WorkflowTemplate) live outside workflows.json but
                # are schedulable — resolve them so the scheduled job actually fires.
                from core.workflow_endpoints import _load_template_definition
                workflow_def = _load_template_definition(workflow_id)

            if workflow_def:
                # R69: skip critical definitions (orchestrator steps OR
                # AutomationEngine nodes) unless the scheduler was authorized.
                if (has_critical_definition(workflow_def) or has_critical_automation_nodes(workflow_def)) and not authorized:
                    logger.warning(
                        "Skipping scheduled critical workflow %s (schedule not authorized for WORKFLOW_MANAGE)",
                        workflow_id,
                    )
                    return
                # Route through the durable WorkflowEngine so scheduled
                # executions persist to the DB WorkflowExecution table and
                # appear in the Executions tab — the legacy AutomationEngine
                # only wrote executions.json.
                from core.workflow_engine import get_workflow_engine
                engine = get_workflow_engine()
                execution_id = await engine.start_workflow(workflow_def, input_data or {})
                logger.info(f"Scheduled execution {execution_id} started")
            else:
                # Self-heal (2026-09-05): the definition is gone (deleted
                # workflow/template) — remove every scheduled job still
                # pointing at it. Without this, a dead ID kept erroring on
                # every fire forever (8 such IDs in the live jobstore).
                try:
                    dead = [
                        job.id
                        for job in workflow_scheduler.scheduler.get_jobs()
                        if getattr(job, "args", None) and job.args[0] == workflow_id
                    ]
                    for dead_id in dead:
                        workflow_scheduler.scheduler.remove_job(dead_id)
                    logger.warning(
                        "Scheduled workflow %s not found — removed %d dead schedule(s): %s",
                        workflow_id, len(dead), dead,
                    )
                except Exception as cleanup_err:
                    logger.error(
                        "Scheduled workflow %s not found (dead-schedule cleanup failed: %s)",
                        workflow_id, cleanup_err,
                    )

        except Exception as e:
            logger.error(f"Error executing scheduled workflow {workflow_id}: {e}")

    def schedule_workflow(self, workflow_id: str, trigger_type: str, trigger_config: Dict[str, Any], input_data: Dict[str, Any] = None, authorized: bool = False) -> str:
        """
        Schedule a workflow execution.

        Args:
            workflow_id: ID of the workflow to schedule
            trigger_type: 'cron', 'interval', or 'date'
            trigger_config: Configuration for the trigger (e.g. cron expression)
            input_data: Optional input data for the workflow
            authorized: R69 — True only when the scheduling user held
                WORKFLOW_MANAGE, allowing critical definitions to fire.

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
            args=[workflow_id, input_data, authorized],
            id=job_id,
            replace_existing=True
        )
        return job_id

    def schedule_workflow_cron(self, job_id: str, workflow_id: str, cron_expression: str, authorized: bool = False):
        """Schedule a workflow using cron expression"""
        self.scheduler.add_job(
            self._execute_job,
            CronTrigger.from_crontab(cron_expression),
            args=[workflow_id, None, authorized],
            id=job_id,
            replace_existing=True
        )
        logger.info(f"Scheduled cron job {job_id} for workflow {workflow_id}: {cron_expression}")
        return job_id

    def schedule_workflow_interval(self, job_id: str, workflow_id: str, interval_minutes: int, authorized: bool = False):
        """Schedule a workflow using interval"""
        self.scheduler.add_job(
            self._execute_job,
            IntervalTrigger(minutes=interval_minutes),
            args=[workflow_id, None, authorized],
            id=job_id,
            replace_existing=True
        )
        logger.info(f"Scheduled interval job {job_id} for workflow {workflow_id}: {interval_minutes}m")
        return job_id

    def schedule_workflow_once(self, job_id: str, workflow_id: str, run_date: str, authorized: bool = False):
        """Schedule a workflow once at a specific date"""
        self.scheduler.add_job(
            self._execute_job,
            DateTrigger(run_date=run_date),
            args=[workflow_id, None, authorized],
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
