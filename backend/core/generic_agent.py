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
from core.llm.byok_handler import BYOKHandler

logger = logging.getLogger(__name__)

class GenericAgent:
    """
    A runtime wrapper for dynamically configured agents.
    It reads instructions/tools from the AgentRegistry model and executes tasks.
    """
    
    def __init__(self, agent_model: AgentRegistry, workspace_id: str = "default"):
        self.id = agent_model.id
        self.name = agent_model.name
        self.config = agent_model.configuration or {}
        self.workspace_id = workspace_id
        
        # Initialize Services
        self.world_model = WorldModelService(workspace_id)
        self.mcp = mcp_service
        self.llm = BYOKHandler(workspace_id=workspace_id) # Direct LLM access via BYOK
        
        # Extract Agent Config
        self.system_prompt = self.config.get("system_prompt", f"You are {self.name}, a helpful assistant.")
        self.allowed_tools = self.config.get("tools", "*") # Default to all tools for maximum capability
        
    async def execute(self, task_input: str, context: Dict[str, Any] = None, step_callback: Optional[callable] = None) -> Dict[str, Any]:
        """
        Execute a task using the ReAct (Reason-Act-Observe) loop.
        Accommodates timeouts and streaming callbacks.
        """
        context = context or {}
        start_time = datetime.utcnow()
        logger.info(f"Agent {self.name} ({self.id}) starting task: {task_input[:50]}")
        
        # 1. Recall Memory
        memory_context = await self.world_model.recall_experiences(
            agent=self._get_registry_model(),
            current_task_description=task_input
        )
        
        # 2. ReAct Loop with Timeout
        max_steps = self.config.get("max_steps", 5)
        timeout_seconds = self.config.get("timeout_seconds", 300) # Default 5 mins
        steps = []
        final_answer = None
        status = "success"
        
        try:
            async def run_loop():
                nonlocal final_answer, status
                current_step = 0
                execution_history = ""
                
                while current_step < max_steps:
                    current_step += 1
                    
                    # Plan/Think
                    llm_response = await self._step_think(task_input, memory_context, execution_history)
                    
                    # Parse
                    from core.agent_utils import parse_react_response
                    thought, action, answer = parse_react_response(llm_response)
                    
                    step_record = {
                        "step": current_step,
                        "thought": thought,
                        "action": action,
                        "output": None,
                        "timestamp": datetime.utcnow().isoformat()
                    }
                    
                    # Stream if callback provided
                    if step_callback:
                        await step_callback(step_record)
                    
                    # Accumulate history for next turn
                    if thought:
                        execution_history += f"Thought: {thought}\n"
                    
                    if answer:
                        step_record["final_answer"] = answer
                        final_answer = answer
                        steps.append(step_record)
                        execution_history += f"Final Answer: {answer}\n"
                        break
                    
                    if action:
                        # Execute Tool
                        execution_history += f"Action: {json.dumps(action)}\n"
                        
                        tool_name = action.get("tool")
                        tool_args = action.get("params", {})
                        
                        # Safety check
                        if self.allowed_tools != "*" and tool_name not in self.allowed_tools:
                            observation = f"Error: Tool '{tool_name}' is not allowed."
                        else:
                            observation = await self._step_act(tool_name, tool_args, context, step_callback)
                        
                        step_record["output"] = observation
                        execution_history += f"Observation: {str(observation)}\n"
                        
                        # Update stream with result
                        if step_callback:
                            await step_callback(step_record)
                        
                    else:
                        if current_step == max_steps:
                            final_answer = llm_response
                            status = "timeout_forced_answer"
                            
                    steps.append(step_record)

            # Wait for execution with timeout
            await asyncio.wait_for(run_loop(), timeout=timeout_seconds)

            if not final_answer:
                final_answer = "Maximum steps reached without final answer."
                status = "max_steps_exceeded"
                
        except asyncio.TimeoutError:
            logger.warning(f"Agent {self.name} timed out after {timeout_seconds}s")
            final_answer = f"Execution Timed Out after {timeout_seconds} seconds."
            status = "timeout"
                
        except Exception as e:
            logger.error(f"Agent execution failed: {e}")
            final_answer = f"Error during execution: {str(e)}"
            status = "failed"
            
        # 3. Record Experience
        execution_result = {
            "output": final_answer,
            "steps": steps,
            "status": status,
            "timestamp": start_time.isoformat()
        }
        
        await self._record_execution(task_input, execution_result)
        
        return execution_result

    async def _step_think(self, task_input: str, memory: Dict, history: str) -> str:
        """Generating the next thought/action plan"""
        
        system_prompt = f"""
{self.system_prompt}

You are an agent executing a task. You have access to the following tools:
{json.dumps(await self.mcp.get_all_tools(), indent=2)}

Use the following format:

Thought: you should always think about what to do
Action: the action to take, should be a valid JSON blob like {{"tool": "tool_name", "params": {{"key": "value"}}}}
Observation: the result of the action (provided by system)
... (this Thought/Action/Observation can repeat N times)
Final Answer: the final answer to the original input question

ORCHESTRATION POWERS:
- You can discover and call external integrations (Salesforce, Slack, HubSpot, etc.) via 'call_integration'.
- You can list and trigger automated workflows via 'list_workflows' and 'trigger_workflow'.
- You can even spawn sub-specialty agents to help you via 'spawn_agent'.

Context from Memory:
- Past Experiences: {json.dumps(memory.get('experiences', [])[:2], indent=2)}
- Knowledge Graph Context: {memory.get('knowledge_graph', 'N/A')}
- Relevant Documents: {json.dumps([k.get('text', '')[:200] for k in memory.get('knowledge', [])], indent=2)}
- Relevant Formulas: {json.dumps(memory.get('formulas', []), indent=2)}

Previous Steps:
{history}
"""
        user_prompt = f"Current Task: {task_input}\n\nProvide your next Thought and Action."
        
        return await self.llm.generate_response(
            prompt=user_prompt,
            system_instruction=system_prompt,
            model_type="fast",
            temperature=0.3 # Lower temp for logic
        )
        
    async def _step_act(self, tool_name: str, args: Dict, context: Dict = None, step_callback: Optional[callable] = None) -> Any:
        """Execute a tool via MCP with Governance Check"""
        try:
            # 1. Governance Maturity Check
            db = SessionLocal()
            try:
                gov = AgentGovernanceService(db)
                auth_check = gov.can_perform_action(self.id, tool_name)
                
                if auth_check.get("requires_human_approval"):
                    # Create HITL Action
                    action_id = gov.request_approval(
                        agent_id=self.id,
                        action_type=tool_name,
                        params=args,
                        reason=auth_check["reason"],
                        workspace_id=self.workspace_id
                    )
                    
                    logger.info(f"Action {tool_name} requires approval. Pausing agent...")
                    
                    if step_callback:
                        await step_callback({
                            "type": "hitl_paused",
                            "action_id": action_id,
                            "tool": tool_name,
                            "reason": auth_check["reason"]
                        })
                    
                    # Wait for approval
                    approved = await self._wait_for_approval(action_id)
                    if not approved:
                        return f"Governance Error: Action {tool_name} was REJECTED by user or timed out."
                    
                    logger.info(f"Action {tool_name} APPROVED. Proceeding...")
                    
                elif not auth_check["allowed"]:
                    return f"Governance Error: {auth_check['reason']}"
            finally:
                db.close()

            # 2. Execute via MCP Service (Dynamic Resolution)
            return await self.mcp.call_tool(tool_name, args, context=context)
            
        except Exception as e:
            error_msg = str(e)
            if "not found" in error_msg.lower():
                return f"Error: Tool '{tool_name}' not found on server '{server_id}'. Check tool name."
            elif "validation" in error_msg.lower() or "invalid" in error_msg.lower():
                return f"Error: Invalid arguments for '{tool_name}': {error_msg}. Please check schema and retry."
            elif "timeout" in error_msg.lower():
                return f"Error: Tool '{tool_name}' timed out. You may try once more if critical."
            
            return f"Tool Execution Failed: {error_msg}. You can try to correct parameters or move to next step."

    async def _record_execution(self, input_text: str, result: Dict):
        """Save result to World Model and update Governance maturity"""
        # 1. Save to World Model
        experience = AgentExperience(
            id=str(uuid.uuid4()),
            agent_id=self.id,
            task_type="custom_task_react",
            input_summary=input_text[:200],
            outcome=result["status"],
            learnings=result.get("output", "")[:500],
            agent_role=self.config.get("role", "specialty_agent"),
            specialty=self.config.get("specialty", "general"),
            timestamp=datetime.utcnow()
        )
        await self.world_model.record_experience(experience)

        # 2. Update Governance Maturity
        success = result["status"] == "success"
        db = SessionLocal()
        try:
            gov = AgentGovernanceService(db)
            await gov.record_outcome(self.id, success=success)
        except Exception as e:
            logger.error(f"Failed to record governance outcome: {e}")
        finally:
            db.close()

    async def _wait_for_approval(self, action_id: str) -> bool:
        """Poll for HITL decision"""
        max_wait = self.config.get("hitl_timeout", 600) # Default 10 mins
        interval = 5
        elapsed = 0
        
        while elapsed < max_wait:
            db = SessionLocal()
            try:
                gov = AgentGovernanceService(db)
                status_info = gov.get_approval_status(action_id)
                
                if status_info["status"] == HITLActionStatus.APPROVED.value:
                    return True
                if status_info["status"] == HITLActionStatus.REJECTED.value:
                    return False
            finally:
                db.close()
                
            await asyncio.sleep(interval)
            elapsed += interval
            
        return False # Timeout

    def _get_registry_model(self) -> AgentRegistry:
        """Helper to reconstruct the model for passing to services"""
        return AgentRegistry(
            id=self.id,
            name=self.name,
            configuration=self.config
        )
