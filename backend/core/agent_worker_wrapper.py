import logging
from typing import Dict, Any

logger = logging.getLogger(__name__)

def execute_agent_background(task_data: Dict[str, Any]):
    """
    Background worker function for executing an agent task.
    This is called by the RQ worker.
    """
    try:
        from core.atom_meta_agent import AtomMetaAgent, AgentTriggerMode
        
        request = task_data.get("request")
        context = task_data.get("context", {})
        trigger_mode_str = task_data.get("trigger_mode", "manual")
        tenant_id = task_data.get("tenant_id", "default")
        
        # Convert string trigger mode back to enum if needed
        # (Assuming the caller passes the value string)
        
        # ``request`` may be None/absent on malformed tasks; coerce to a string
        # before slicing so the log line never crashes the worker before it
        # reaches the agent (and surfaces the missing input downstream).
        request_str = (request or "")[:50]
        logger.info(f"Background worker: Executing agent for {tenant_id} - Request: {request_str}...")
        
        # We need an event loop for the async execute method
        import asyncio
        atom = AtomMetaAgent(tenant_id)
        
        # Create a new event loop for this thread if necessary
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        try:
            result = loop.run_until_complete(atom.execute(
                request=request,
                context=context,
                trigger_mode=AgentTriggerMode(trigger_mode_str)
            ))
        finally:
            # #7 fix: close the loop to prevent resource leak across many invocations.
            loop.close()
        
        logger.info(f"Background worker: Execution completed for {tenant_id}")
        return result
        
    except Exception as e:
        logger.error(f"Background agent execution failed: {e}", exc_info=True)
        raise e
