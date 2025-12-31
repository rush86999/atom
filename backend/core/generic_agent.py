import logging
import uuid
import json
from datetime import datetime
from typing import Dict, Any, List, Optional

import asyncio
from core.agent_governance_service import AgentGovernanceService
from core.models import AgentRegistry, AgentStatus, HITLActionStatus
from core.database import SessionLocal
from integrations.mcp_service import mcp_service
from core.byok_endpoints import get_byok_manager

# Import Core Engine
from core.react_agent_engine import ReActAgentEngine

logger = logging.getLogger(__name__)

class GenericAgent:
    """
    A runtime wrapper for dynamically configured agents.
    It reads instructions/tools from the AgentRegistry model and executes tasks using ReActAgentEngine.
    """
    
    def __init__(self, agent_model: AgentRegistry, workspace_id: str = "default"):
        self.id = agent_model.id
        self.name = agent_model.name
        self.config = agent_model.configuration or {}
        self.workspace_id = workspace_id
        
        # Initialize Core Engine
        self.engine = ReActAgentEngine(workspace_id=workspace_id)
        self.mcp = mcp_service
        
        # Extract Agent Config
        self.system_prompt = self.config.get("system_prompt", f"You are {self.name}, a helpful assistant.")
        self.allowed_tools = self.config.get("tools", "*") # Default to all tools for maximum capability
        
    async def execute(self, task_input: str, context: Dict[str, Any] = None, step_callback: Optional[callable] = None) -> Dict[str, Any]:
        """
        Execute a task using the ReAct (Reason-Act-Observe) loop via Engine.
        Accommodates timeouts and streaming callbacks.
        """
        context = context or {}
        start_time = datetime.utcnow()
        logger.info(f"Agent {self.name} ({self.id}) starting task: {task_input[:50]}")
        
        # 1. Prepare Tools Definition
        # For Generic Agent, we list everything available via MCP
        all_tools = await self.mcp.get_all_tools()
        tools_def = f"Available Tools:\n{json.dumps(all_tools, indent=2)}"
        
        # 2. Define Executor
        async def tool_executor(name: str, params: Dict) -> Any:
            # Governance Check
            db = SessionLocal()
            try:
                gov = AgentGovernanceService(db)
                auth_check = gov.can_perform_action(self.id, name)
                
                if auth_check.get("requires_human_approval"):
                     # ... (HITL logic similar to before, simplified for engine integration)
                     return "Action requires human approval (HITL not fully integrated in new engine yet)."
                elif not auth_check["allowed"]:
                     return f"Governance Error: {auth_check['reason']}"
            finally:
                db.close()

            # Execute
            return await self.mcp.call_tool(name, params, context=context)

        # 3. Run Loop
        try:
             result = await self.engine.run_loop(
                 user_input=task_input,
                 tools_definition=tools_def,
                 tool_executor=tool_executor,
                 system_prompt=self.system_prompt,
                 max_loops=self.config.get("max_steps", 10)
             )

             final_answer = result.output
             status = result.status
             steps = [s.model_dump() for s in result.steps]

        except Exception as e:
            logger.error(f"Agent execution failed: {e}")
            final_answer = f"Error during execution: {str(e)}"
            status = "failed"
            steps = []
            
        # 3. Record Experience (Legacy Hook)
        execution_result = {
            "output": final_answer,
            "steps": steps,
            "status": status,
            "timestamp": start_time.isoformat()
        }
        
        # await self._record_execution(task_input, execution_result) # Restored if needed
        
        return execution_result
