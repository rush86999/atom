import datetime
import functools
import logging
from advanced_workflow_orchestrator import AdvancedWorkflowOrchestrator
from analytics.collector import AsyncAnalyticsCollector

logger = logging.getLogger(__name__)

def activate_analytics(orchestrator_instance: AdvancedWorkflowOrchestrator):
    """
    Monkey-patches the AdvancedWorkflowOrchestrator's execution method
    to automatically record execution metrics.
    """
    logger.info("🧬 Activating Workflow DNA (Analytics Instrumentation) for AdvancedWorkflowOrchestrator...")
    
    # Capture the original method
    # Note: simple assignment like `original = inst.method` captures a bound method.
    # We need to be careful not to create infinite recursion.
    original_method = orchestrator_instance._execute_workflow_step
    
    # Create the wrapper
    async def instrumented_execute_step(self, workflow, step_id, context):
        start_time = datetime.datetime.now()
        
        # Resolve step details
        step = next((s for s in workflow.steps if s.step_id == step_id), None)
        step_type = step.step_type.value if step and hasattr(step.step_type, 'value') else "unknown"
        if step_type == "unknown" and step:
             step_type = str(step.step_type)

        status = "COMPLETED"
        error = None
        
        try:
            # Call original method
            # Since original_method is already bound to the instance (if we captured it from instance),
            # we might not need to pass 'self' again if we just call it?
            # actually, if we replace the method on the instance, 'self' will be passed 
            # to our wrapper.
            # But 'original_method' is the OLD bound method.
            # So we should call `original_method(workflow, step_id, context)` directly depending on how it was captured.
            
            # If we captured `inst._execute_workflow_step`, it IS a bound method.
            # So we don't pass self.
            await original_method(workflow, step_id, context)
            
            # Check context for status (it might have failed inside)
            result = context.results.get(step_id)
            if result and result.get("status") == "failed":
                status = "FAILED"
                error = result.get("error")
                
        except Exception as e:
            status = "FAILED"
            error = str(e)
            raise e
            
        finally:
            end_time = datetime.datetime.now()
            
            # Log to sidecar
            # MAPPING FIX: 
            # 1. WorkflowContext.workflow_id IS the execution_id (e.g. exec_123)
            # 2. Real Workflow Definition ID is usually in input_data OR we treat the execution ID as the workflow ID if missing.
            
            execution_id = getattr(context, 'workflow_id', 'unknown')
            
            # Try to find the Definition ID
            workflow_def_id = context.input_data.get("_ui_workflow_id") if context.input_data else None
            # Fallback: if we can't find a definition ID, use the execution ID or 'ad-hoc'
            if not workflow_def_id:
                 workflow_def_id = "ad-hoc" 

            if execution_id != "unknown":
                await AsyncAnalyticsCollector.get_instance().log_step(
                    execution_id=execution_id,
                    workflow_id=workflow_def_id,
                    step_id=step_id,
                    step_type=step_type,
                    start_time=start_time,
                    end_time=end_time,
                    status=status,
                    error=error,
                    results=context.results.get(step_id) if hasattr(context, 'results') else None
                )
            
    # Apply the patch
    # We are replacing a BOUND method on the instance.
    # The wrapper function `instrumented_execute_step` expects `self` as first arg.
    # We need to bind it to the instance manually or use partial.
    orchestrator_instance._execute_workflow_step = functools.partial(instrumented_execute_step, orchestrator_instance)
    
    logger.info("✅ Workflow DNA Active: Instrumentation applied to AdvancedWorkflowOrchestrator.")
