import logging
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore
from apscheduler.executors.pool import ThreadPoolExecutor
from sqlalchemy.orm import Session
import uuid
import datetime
import json

from core.database import SessionLocal, engine
from core.models import AgentJob, AgentJobStatus

logger = logging.getLogger(__name__)

class AgentScheduler:
    _instance = None

    def __init__(self):
        jobstores = {
            'default': SQLAlchemyJobStore(engine=engine)
        }
        executors = {
            'default': ThreadPoolExecutor(20)
        }
        job_defaults = {
            'coalesce': False,
            'max_instances': 3
        }
        self.scheduler = BackgroundScheduler(
            jobstores=jobstores, 
            executors=executors, 
            job_defaults=job_defaults
        )
        self.scheduler.start()
        logger.info("AgentScheduler started.")

    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            cls._instance = AgentScheduler()
        return cls._instance

    def schedule_job(self, agent_id: str, cron_expression: str, func, args=None):
        """
        Schedule a recurring agent job.
        cron_expression format: "* * * * *" (minute hour day month day_of_week)
        """
        # Simple parser for "every X minutes" vs full cron
        # For MVP, we assume cron string passed to from_crontab or keyword args
        # But APScheduler usually takes separate args (minute='*', hour='9')
        # We will implement a simplified 'interval' or 'cron' parser if needed.
        # Here we assume caller passes a dict of cron args for simplicity in this MVP.
        
        job_id = str(uuid.uuid4())
        
        # Wrapped function to log to DB
        def managed_execution(*args, **kwargs):
            self._execute_and_log(agent_id, func, *args, **kwargs)

        # Assuming cron_expression is a dict for add_job keywords (e.g., {'minute': '*/5'})
        # or we accept a CronTrigger.
        # For safety/simplicity in this file generation, let's just use add_job directly
        # But we need to handle the trigger parsing.
        
        # Fallback: if input is a dict, unpack it. If string, try to parse
        trigger_args = {}
        if isinstance(cron_expression, dict):
            trigger_args = cron_expression
        else:
            # Very basic string parser (e.g. "*/5 * * * *")
            parts = cron_expression.split()
            if len(parts) == 5:
                trigger_args = {
                    'minute': parts[0],
                    'hour': parts[1],
                    'day': parts[2],
                    'month': parts[3],
                    'day_of_week': parts[4]
                }

        self.scheduler.add_job(
            managed_execution,
            'cron',
            id=job_id,
            args=args,
            **trigger_args
        )
        logger.info(f"Scheduled job {job_id} for agent {agent_id} with trigger {trigger_args}")
        return job_id

    def _execute_and_log(self, agent_id: str, func, *args, **kwargs):
        """
        Execution wrapper that creates AgentJob record.
        """
        db = SessionLocal()
        job_record = AgentJob(
            id=str(uuid.uuid4()),
            agent_id=agent_id,
            status=AgentJobStatus.RUNNING.value,
            logs=""
        )
        db.add(job_record)
        db.commit()
        
        try:
            # We need to run async function in sync ThreadPool
            # This is tricky with APScheduler + AsyncIO
            # Usually we'd use AsyncIOScheduler if main loop is async
            # But here we are in a thread. We will run asyncio.run()
            import asyncio
            result = asyncio.run(func(*args, **kwargs))
            
            job_record.status = AgentJobStatus.SUCCESS.value
            job_record.end_time = datetime.datetime.now()
            job_record.result_summary = json.dumps(result, default=str)
            
        except Exception as e:
            logger.error(f"Job failed: {e}")
            job_record.status = AgentJobStatus.FAILED.value
            job_record.end_time = datetime.datetime.now()
            job_record.logs = str(e)
            
        finally:
            db.commit()
            db.close()
