
import asyncio
import logging
import os
from typing import Any, Dict, List, Optional
from pydantic import BaseModel

from core.service_factory import ServiceFactory
from integrations.mcp_service import mcp_service

# Try to import Lux SDK, fallback to local model if available
try:
    from oagi import LuxAgent
    HAS_SDK = True
except ImportError:
    HAS_SDK = False

from ai.lux_model import LuxModel

logger = logging.getLogger(__name__)

class AgentTask(BaseModel):
    id: str
    goal: str
    mode: str
    status: str
    logs: List[str] = []
    result: Optional[str] = None

class ComputerUseAgent:
    """
    Service for managing Lux Computer Use Agents.
    Supports 'actor', 'thinker', and 'tasker' modes.
    """
    
    
    def __init__(self, tenant_id: str = "default"):
        self.tenant_id = tenant_id
        self.default_mode = os.getenv("LUX_MODEL_MODE", "thinker")
        self._active_tasks: Dict[str, AgentTask] = {}
        self.mcp = mcp_service  # MCP access for web search and web access
        
        # We now rely on local LuxModel if SDK is missing
        logger.info(f"ComputerUseAgent initialized for tenant {tenant_id}")
            
    async def execute_task(self, goal: str, mode: Optional[str] = None) -> Dict[str, Any]:
        """
        Start a computer use task.
        """
        task_id = f"task_{len(self._active_tasks) + 1}_{int(asyncio.get_event_loop().time())}"
        mode = mode or self.default_mode
        
        task = AgentTask(
            id=task_id,
            goal=goal,
            mode=mode,
            status="running",
            logs=[f"Task started in {mode} mode: {goal}"]
        )
        self._active_tasks[task_id] = task
        
        # Run in background to not block API
        asyncio.create_task(self._run_agent_loop(task_id))
        
        return task.dict()
        
    async def _run_agent_loop(self, task_id: str):
        """
        Internal method to run the agent loop.
        handles both Real SDK execution and Mock fallback.
        """
        task = self._active_tasks.get(task_id)
        if not task:
            return

        try:
            # Use ServiceFactory to get the LuxModel instance
            # which is now tenant-aware and uses LLMService
            task.logs.append("Initializing Lux Agent (Unified Infrastructure)...")
            
            # Real Lux Execution via ServiceFactory resolved model
            agent = await ServiceFactory.get_lux_model(tenant_id=self.tenant_id)
            
            if True: # Key check handled inside LuxModel/LLMService now
                
                # --- Governance Setup ---
                from core.agent_governance_service import AgentGovernanceService
                from core.database import SessionLocal

                # Define callback for governance checks
                async def check_governance(action_type: str, details: Dict) -> bool:
                    try:
                        db = SessionLocal()
                        service = AgentGovernanceService(db)
                        
                        # Register Computer Use Agent if missing
                        agent = service.register_or_update_agent(
                            name="Computer Use Agent",
                            category="Desktop Automation",
                            module_path="backend.services.agent_service",
                            class_name="ComputerUseAgent",
                            description="AI Agent capable of controlling desktop mouse and keyboard."
                        )
                        
                        # Check permission
                        check = service.enforce_action(agent.id, action_type)
                        
                        if check["proceed"]:
                            return True
                        else:
                            # Log detailed reason for blockage
                            reason = check.get("reason", "Action blocked by governance policies.")
                            task.logs.append(f"⛔ Governance Blocked Action '{action_type}': {reason}")
                            return False
                    except Exception as e:
                        logger.error(f"Governance check failed: {e}")
                        # Fail safe: Block if check fails
                        return False
                    finally:
                        db.close()

                try:
                    # Execute
                    result_data = await agent.execute_command(task.goal)
                    
                    if result_data.get("success"):
                        task.status = "completed"
                        task.result = f"Task completed: {json.dumps(result_data.get('actions', []), indent=2)}"
                        task.logs.append(f"Success. Actions taken: {len(result_data.get('actions', []))}")
                    else:
                        task.status = "failed"
                        task.result = f"Task failed: {result_data.get('error')}"
                        task.logs.append(f"Failure: {result_data.get('error')}")
                        
                except Exception as model_err:
                     task.status = "failed"
                     task.result = str(model_err)
                     task.logs.append(f"Model Execution Error: {model_err}")
                
        except Exception as e:
            logger.error(f"Agent task failed: {e}")
            task.status = "failed"
            task.logs.append(f"Error: {str(e)}")
            task.result = str(e)

    def get_task_status(self, task_id: str) -> Optional[Dict[str, Any]]:
        task = self._active_tasks.get(task_id)
        return task.dict() if task else None

    def stop_task(self, task_id: str) -> bool:
        task = self._active_tasks.get(task_id)
        if task and task.status == "running":
            task.status = "stopped"
            task.logs.append("Task stopped by user.")
            return True
        return False

# Singleton instance
agent_service = ComputerUseAgent()
