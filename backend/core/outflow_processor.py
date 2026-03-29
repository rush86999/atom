"""
Outflow Processor for Redis Queue Integration
Handles execution of OutflowExecution records fetched from the Redis queue.
Includes robust status tracking and result logging.
Support for OAuth tokens and tenant-specific settings.
"""

import logging
import time
from datetime import datetime, timezone
from typing import Dict, Any, Optional

# Upstream specific imports
from core.database import get_db_session
from core.models import OutflowExecution, IntegrationToken, TenantSetting
from core.outflow_executors import EmailOutflowExecutor, ApiCallOutflowExecutor

logger = logging.getLogger(__name__)


async def process_outflow(outflow_id: str) -> Dict[str, Any]:
    """
    Process an outflow execution from the Redis queue.
    Standardized reconciliation from SaaS functional implementation.
    
    Args:
        outflow_id: ID of the OutflowExecution to process
        
    Returns:
        Dict with execution results
    """
    start_time = time.time()
    
    with get_db_session() as db:
        outflow = db.query(OutflowExecution).filter(OutflowExecution.id == outflow_id).first()
        
        if not outflow:
            error_msg = f"OutflowExecution {outflow_id} not found in database"
            logger.error(error_msg)
            return {"status": "error", "message": error_msg}
            
        if outflow.status in ["success", "failed"] and outflow.attempts >= outflow.max_attempts:
            logger.info(f"Outflow {outflow_id} already processed or max attempts reached.")
            return {"status": "skipped", "message": "Already processed"}

        try:
            # Update status to running
            outflow.status = "running"
            outflow.started_at = datetime.now(timezone.utc)
            outflow.attempts += 1
            outflow.last_attempt_at = datetime.now(timezone.utc)
            db.commit()
            
            # Select executor
            executor = None
            if outflow.outflow_type == "email":
                executor = EmailOutflowExecutor()
            elif outflow.outflow_type in ["api_call", "webhook"]:
                executor = ApiCallOutflowExecutor()
            else:
                raise ValueError(f"Unsupported outflow type: {outflow.outflow_type}")
                
            # Context for the executor (Auth, Credentials, etc.)
            execution_context = {
                "tenant_id": outflow.tenant_id,
                "token": None,
                "smtp_settings": None
            }
            
            # 1. Check for OAuth Token
            if outflow.integration_token_id:
                token = db.query(IntegrationToken).filter(IntegrationToken.id == outflow.integration_token_id).first()
                if token:
                    execution_context["token"] = token
                    logger.info(f"Using OAuth Token for outflow {outflow_id} (Provider: {token.provider})")
            
            # 2. Check for Tenant SMTP Settings (BYO-SMTP)
            else:
                settings = db.query(TenantSetting).filter(
                    TenantSetting.tenant_id == outflow.tenant_id,
                    TenantSetting.setting_key.startswith("smtp_")
                ).all()
                if settings:
                    execution_context["smtp_settings"] = {s.setting_key: s.setting_value for s in settings}
                    logger.info(f"Using Tenant SMTP settings for outflow {outflow_id}")
            
            # Execute
            result = await executor.execute(outflow.target, outflow.payload, context=execution_context)
            
            # Update record with results
            outflow.status = result.get("status", "failed")
            outflow.response_code = result.get("response_code")
            outflow.response_body = result.get("response_body")
            outflow.error_message = result.get("error_message")
            outflow.error_details = result.get("error_details")
            outflow.completed_at = datetime.now(timezone.utc)
            
            # Record duration
            outflow.execution_duration_ms = (time.time() - start_time) * 1000
            
            db.commit()
            logger.info(f"Outflow {outflow_id} processed with status: {outflow.status}")
            
            return result

        except Exception as e:
            logger.error(f"Failed to process outflow {outflow_id}: {e}", exc_info=True)
            
            # Update record with failure
            outflow.status = "failed"
            outflow.error_message = str(e)
            outflow.completed_at = datetime.now(timezone.utc)
            outflow.execution_duration_ms = (time.time() - start_time) * 1000
            
            db.commit()
            
            return {"status": "failed", "error": str(e)}
