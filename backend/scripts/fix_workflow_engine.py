# Fix syntax error in enhanced_workflow_engine.py
import re

# Read the file
with open('/home/developer/projects/atom/atom/enhance_workflow_engine.py', 'r') as f:
    content = f.read()

# Fix the async function syntax issue
# Replace the problematic section with proper async function
content = re.sub(
    r'async def _execute_workflow_advanced\(self, execution: WorkflowExecution\) -> Dict\[str, Any\]:\s*\n.*?"COMPLETED"\):\s*\n                execution\.status = WorkflowExecutionStatus\.COMPLETED\s*\n                execution\.output_data = self\._collect_execution_output\(execution\)\s*\n\s*\n            # Remove from active executions\s*\n            if execution\.id in self\.active_executions:\s*\n                del self\.active_executions\[execution\.id\]\s*\n\s*\n            return \{\s*\n                "success": execution\.status == WorkflowExecutionStatus\.COMPLETED,\s*\n                "execution_id": execution\.id,\s*\n                "status": execution\.status\.value,\s*\n                "execution_time": execution\.execution_time,\s*\n                "completed_steps": len\(\[s for s in execution\.steps if s\.status == StepExecutionStatus\.COMPLETED\]\),\s*\n                "failed_steps": len\(\[s for s in execution\.steps if s\.status == StepExecutionStatus\.FAILED\]\),\s*\n                "total_steps": len\(execution\.steps\)\s*\n            \}\s*\n\s*\n        except Exception as e:\s*\n            logger\.error\(f"Error in advanced workflow execution: \{str\(e\)\}"\)\s*\n            execution\.status = WorkflowExecutionStatus\.FAILED\s*\n            execution\.error = str\(e\)\s*\n            execution\.completed_at = datetime\.now\(\)\s*\n            return \{"success": False, "error": str\(e\)\}',
    '''async def _execute_workflow_advanced(self, execution: WorkflowExecution) -> Dict[str, Any]:
        """Execute workflow with advanced features"""
        try:
            execution.status = WorkflowExecutionStatus.RUNNING
            execution.started_at = datetime.now()
            
            # Initialize parallel groups
            self._initialize_parallel_groups(execution)
            
            # Execute steps with advanced logic
            while self._has_pending_steps(execution):
                # Find ready steps
                ready_steps = self._get_ready_steps(execution)
                
                if not ready_steps:
                    # Check for deadlock
                    if self._is_deadlocked(execution):
                        execution.status = WorkflowExecutionStatus.FAILED
                        execution.error = "Workflow deadlocked - circular dependencies detected"
                        break
                    # Wait for parallel steps to complete
                    await asyncio.sleep(0.1)
                    continue
                
                # Execute ready steps
                await self._execute_ready_steps(execution, ready_steps)
            
            # Finalize execution
            execution.completed_at = datetime.now()
            execution.execution_time = (execution.completed_at - execution.started_at).total_seconds()
            
            # Determine final status
            failed_steps = [s for s in execution.steps if s.status == StepExecutionStatus.FAILED]
            if failed_steps:
                execution.status = WorkflowExecutionStatus.FAILED
                execution.error = f"{len(failed_steps)} steps failed"
            else:
                execution.status = WorkflowExecutionStatus.COMPLETED
                execution.output_data = self._collect_execution_output(execution)
            
            # Remove from active executions
            if execution.id in self.active_executions:
                del self.active_executions[execution.id]
            
            return {
                "success": execution.status == WorkflowExecutionStatus.COMPLETED,
                "execution_id": execution.id,
                "status": execution.status.value,
                "execution_time": execution.execution_time,
                "completed_steps": len([s for s in execution.steps if s.status == StepExecutionStatus.COMPLETED]),
                "failed_steps": len([s for s in execution.steps if s.status == StepExecutionStatus.FAILED]),
                "total_steps": len(execution.steps)
            }
            
        except Exception as e:
            logger.error(f"Error in advanced workflow execution: {str(e)}")
            execution.status = WorkflowExecutionStatus.FAILED
            execution.error = str(e)
            execution.completed_at = datetime.now()
            return {"success": False, "error": str(e)}''',
    content,
    flags=re.DOTALL
)

# Write the fixed content
with open('/home/developer/projects/atom/atom/enhance_workflow_engine.py', 'w') as f:
    f.write(content)

print("Fixed syntax error in enhanced_workflow_engine.py")