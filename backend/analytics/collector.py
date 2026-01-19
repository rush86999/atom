import asyncio
import logging
from datetime import datetime
from core.database import SessionLocal
from analytics.models import WorkflowExecutionLog

logger = logging.getLogger(__name__)

class AsyncAnalyticsCollector:
    _instance = None
    
    @classmethod
    def get_instance(cls):
        if not cls._instance:
            cls._instance = cls()
        return cls._instance

    async def log_step(self, execution_id, workflow_id, step_id, step_type, start_time, end_time, status, error=None, trigger_data=None, results=None):
        """Non-blocking log submission"""
        try:
            duration = (end_time - start_time).total_seconds() * 1000
            
            log_entry = {
                "execution_id": execution_id,
                "workflow_id": workflow_id,
                "step_id": step_id,
                "step_type": str(step_type),
                "start_time": start_time,
                "end_time": end_time,
                "duration_ms": duration,
                "status": status,
                "error_code": str(error) if error else None,
                "trigger_data": trigger_data,
                "results": results
            }
            
            # Spawn fire-and-forget task
            # Using asyncio.create_task to ensure it runs on the event loop without blocking
            asyncio.create_task(self._persist_log(log_entry))
        except Exception as e:
            logger.error(f"Failed to queue analytics log: {e}")

    async def _persist_log(self, data):
        """Persist to DB in separate thread"""
        try:
            # Run blocking DB operation in a separate thread
            await asyncio.to_thread(self._sync_write, data)
        except Exception as e:
            logger.error(f"Failed to write analytics log: {e}")

    def _sync_write(self, data):
        try:
            with SessionLocal() as db:
                log = WorkflowExecutionLog(**data)
                db.add(log)
                db.commit()
        except Exception as e:
            logger.error(f"DB Write Error in Analytics: {e}")
