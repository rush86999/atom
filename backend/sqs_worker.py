"""
AWS SQS Worker
Processes background tasks from SQS queue
Replaces Celery for serverless AWS deployment
"""

import asyncio
from datetime import datetime
import json
import logging
import os
import signal
import sys
from typing import Any, Dict, Optional
import boto3
from botocore.exceptions import ClientError

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# AWS Configuration
AWS_REGION = os.getenv('AWS_REGION', 'us-east-1')
SQS_QUEUE_URL = os.getenv('SQS_QUEUE_URL', '')
SQS_DLQ_URL = os.getenv('SQS_DLQ_URL', '')  # Dead letter queue

# Initialize SQS client
sqs = boto3.client('sqs', region_name=AWS_REGION)


class TaskRegistry:
    """Registry of available task handlers"""
    
    _handlers: Dict[str, callable] = {}
    
    @classmethod
    def register(cls, task_name: str):
        """Decorator to register a task handler"""
        def decorator(func):
            cls._handlers[task_name] = func
            logger.info(f"Registered task handler: {task_name}")
            return func
        return decorator
    
    @classmethod
    def get_handler(cls, task_name: str) -> Optional[callable]:
        return cls._handlers.get(task_name)
    
    @classmethod
    def list_tasks(cls) -> list:
        return list(cls._handlers.keys())


# =====================
# Task Handlers
# =====================

@TaskRegistry.register('send_email')
async def handle_send_email(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Send email via integration"""
    from integrations.gmail_service import GmailService
    
    tenant_id = payload.get('tenant_id')
    to = payload.get('to')
    subject = payload.get('subject')
    body = payload.get('body')
    
    service = GmailService(tenant_id)
    result = await service.send_email(to, subject, body)
    
    return {'success': True, 'message_id': result.get('id')}


@TaskRegistry.register('sync_integration')
async def handle_sync_integration(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Sync data from an integration"""
    from integrations import get_integration_service
    
    tenant_id = payload.get('tenant_id')
    provider = payload.get('provider')
    sync_type = payload.get('sync_type', 'full')
    
    service = get_integration_service(provider, tenant_id)
    if hasattr(service, 'sync'):
        result = await service.sync(sync_type)
        return {'success': True, 'synced': result}
    
    return {'success': False, 'error': 'Service does not support sync'}


@TaskRegistry.register('process_ai_request')
async def handle_ai_request(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Process AI/LLM request"""
    from core.ai_service import AIService
    
    tenant_id = payload.get('tenant_id')
    request_type = payload.get('request_type')
    messages = payload.get('messages', [])
    model = payload.get('model', 'gpt-4o-mini')
    
    service = AIService(tenant_id)
    result = await service.generate(
        messages=messages,
        model=model,
        request_type=request_type
    )
    
    return {'success': True, 'response': result}


@TaskRegistry.register('ingest_document')
async def handle_ingest_document(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Ingest document into LanceDB memory"""
    from core.lancedb_handler import LanceDBHandler
    
    tenant_id = payload.get('tenant_id')
    content = payload.get('content')
    metadata = payload.get('metadata', {})
    
    handler = LanceDBHandler(tenant_id)
    doc_id = await handler.ingest(content, metadata)
    
    return {'success': True, 'document_id': doc_id}


@TaskRegistry.register('execute_workflow')
async def handle_execute_workflow(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Execute a workflow"""
    from ai.automation_engine import AutomationEngine
    
    tenant_id = payload.get('tenant_id')
    workflow_id = payload.get('workflow_id')
    input_data = payload.get('input', {})
    
    engine = AutomationEngine(tenant_id)
    result = await engine.execute_workflow(workflow_id, input_data)
    
    return {'success': True, 'result': result}


@TaskRegistry.register('shopify_agent')
async def handle_shopify_agent(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Run Shopify business agent"""
    from integrations.shopify_service import ShopifyAgentOrchestrator
    
    tenant_id = payload.get('tenant_id')
    action = payload.get('action', 'full_cycle')
    params = payload.get('params', {})
    
    orchestrator = ShopifyAgentOrchestrator(tenant_id)
    
    if action == 'full_cycle':
        result = await orchestrator.run_full_cycle()
    elif action == 'inventory_check':
        result = await orchestrator.inventory.monitor_low_stock(params.get('threshold', 10))
    elif action == 'process_orders':
        result = await orchestrator.orders.process_pending_orders()
    else:
        return {'success': False, 'error': f'Unknown action: {action}'}
    
    return {'success': True, 'result': result}
@TaskRegistry.register('global_ingestion_pulse')
async def handle_global_pulse(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Execute global ingestion heartbeat"""
    from core.periodic_tasks import run_global_ingestion_pulse
    return await run_global_ingestion_pulse()


@TaskRegistry.register('sync_document_ingestion')
async def handle_document_ingestion_sync(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Sync documents from an integration via AutoDocumentIngestionService"""
    from core.auto_document_ingestion import get_document_ingestion_service
    
    tenant_id = payload.get('tenant_id', 'default')
    integration_id = payload.get('integration_id')
    force = payload.get('force', False)
    
    if not integration_id:
        return {'success': False, 'error': 'No integration_id provided'}
        
    service = get_document_ingestion_service(tenant_id)
    result = await service.sync_integration(integration_id, force=force)
    
    return {'success': True, 'result': result}


@TaskRegistry.register('sync_dashboard_stats')
async def handle_sync_dashboard_stats(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Sync dashboard analytics from integrations (Salesforce, HubSpot)"""
    from core.analytics_sync_service import AnalyticsSyncService
    
    workspace_id = payload.get('workspace_id')
    if not workspace_id:
        return {'success': False, 'error': 'No workspace_id provided'}
        
    await AnalyticsSyncService.sync_all_analytics(workspace_id)
    return {'success': True, 'message': 'Analytics sync complete'}



# =====================
# SQS Message Processing
# =====================

async def process_message(message: Dict[str, Any]) -> bool:
    """Process a single SQS message"""
    receipt_handle = message['ReceiptHandle']
    
    try:
        body = json.loads(message['Body'])
        task_name = body.get('task')
        payload = body.get('payload', {})
        task_id = body.get('task_id', 'unknown')
        
        logger.info(f"Processing task: {task_name} (ID: {task_id})")
        
        handler = TaskRegistry.get_handler(task_name)
        if not handler:
            logger.error(f"Unknown task type: {task_name}")
            # Move to DLQ
            if SQS_DLQ_URL:
                sqs.send_message(QueueUrl=SQS_DLQ_URL, MessageBody=message['Body'])
            return True  # Delete from main queue
        
        # Execute handler
        start_time = datetime.now()
        result = await handler(payload)
        elapsed = (datetime.now() - start_time).total_seconds()
        
        logger.info(f"Task {task_name} completed in {elapsed:.2f}s: {result}")
        
        # Delete message on success
        sqs.delete_message(QueueUrl=SQS_QUEUE_URL, ReceiptHandle=receipt_handle)
        return True
        
    except Exception as e:
        logger.error(f"Task processing failed: {e}", exc_info=True)
        # Let message retry (visibility timeout will expire)
        return False


async def poll_queue():
    """Poll SQS queue for messages"""
    logger.info(f"Polling SQS queue: {SQS_QUEUE_URL}")
    
    while True:
        try:
            response = sqs.receive_message(
                QueueUrl=SQS_QUEUE_URL,
                MaxNumberOfMessages=10,
                WaitTimeSeconds=20,  # Long polling
                VisibilityTimeout=300,  # 5 minutes to process
                MessageAttributeNames=['All']
            )
            
            messages = response.get('Messages', [])
            if messages:
                logger.info(f"Received {len(messages)} messages")
                
                # Process messages concurrently
                tasks = [process_message(msg) for msg in messages]
                await asyncio.gather(*tasks, return_exceptions=True)
            
        except ClientError as e:
            logger.error(f"SQS error: {e}")
            await asyncio.sleep(5)
        except Exception as e:
            logger.error(f"Unexpected error: {e}", exc_info=True)
            await asyncio.sleep(5)


# =====================
# Helper: Dispatch Task
# =====================

def dispatch_task(task_name: str, payload: Dict[str, Any], delay_seconds: int = 0) -> str:
    """
    Dispatch a task to SQS queue
    Call this from FastAPI endpoints to queue background work
    """
    import uuid
    
    task_id = str(uuid.uuid4())
    message_body = json.dumps({
        'task': task_name,
        'task_id': task_id,
        'payload': payload,
        'dispatched_at': datetime.utcnow().isoformat()
    })
    
    params = {
        'QueueUrl': SQS_QUEUE_URL,
        'MessageBody': message_body,
        'MessageAttributes': {
            'TaskName': {'StringValue': task_name, 'DataType': 'String'},
            'TaskId': {'StringValue': task_id, 'DataType': 'String'}
        }
    }
    
    if delay_seconds > 0:
        params['DelaySeconds'] = min(delay_seconds, 900)  # Max 15 min
    
    response = sqs.send_message(**params)
    
    logger.info(f"Dispatched task {task_name} (ID: {task_id})")
    return task_id


# =====================
# Main Entry Point
# =====================

def main():
    if not SQS_QUEUE_URL:
        logger.error("SQS_QUEUE_URL environment variable not set")
        sys.exit(1)
    
    logger.info("Starting SQS Worker")
    logger.info(f"Available tasks: {TaskRegistry.list_tasks()}")
    
    # Handle graceful shutdown
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    def shutdown(sig, frame):
        logger.info(f"Received {sig}, shutting down...")
        loop.stop()
        sys.exit(0)
    
    signal.signal(signal.SIGINT, shutdown)
    signal.signal(signal.SIGTERM, shutdown)
    
    try:
        loop.run_until_complete(poll_queue())
    except KeyboardInterrupt:
        logger.info("Worker stopped by user")
    finally:
        loop.close()


if __name__ == '__main__':
    main()
