import asyncio
import json
import logging
import os
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from core.agent_governance_service import AgentGovernanceService
from core.agent_world_model import AgentExperience, WorldModelService
from core.database import get_db_session
from core.llm.byok_handler import BYOKHandler
from core.models import AgentRegistry, AgentStatus, HITLActionStatus
from core.react_models import ReActObservation, ReActStep, ToolCall
from integrations.mcp_service import mcp_service

# Try to import instructor for structured parsing
try:
    import instructor
    from openai import AsyncOpenAI
    INSTRUCTOR_AVAILABLE = True
except ImportError:
    INSTRUCTOR_AVAILABLE = False
    instructor = None
    AsyncOpenAI = None

logger = logging.getLogger(__name__)

class GenericAgent:
    """
    A runtime wrapper for dynamically configured agents.
    It reads instructions/tools from the AgentRegistry model and executes tasks.
    Uses instructor for robust Pydantic-validated ReAct parsing when available.
    """
    
    CORE_TOOLS_NAMES = [
        "mcp_tool_search",
        "save_business_fact",
        "verify_citation",
        "ingest_knowledge_from_text", 
        "request_human_intervention",
        "get_system_health"
        # Others can be discovered
    ]

    def __init__(self, agent_model: AgentRegistry, workspace_id: str = "default"):
        self.id = agent_model.id
        self.name = agent_model.name
        self.config = agent_model.configuration or {}
        self.workspace_id = workspace_id
        self.vision_enabled = getattr(agent_model, "vision_enabled", False)
        self.last_screenshot: Optional[str] = None # Base64 data
        
        # Initialize Services
        self.world_model = WorldModelService(workspace_id)
        self.mcp = mcp_service
        self.llm = BYOKHandler(workspace_id=workspace_id)
        self.session_tools: List[Dict[str, Any]] = [] # Lazy-loaded tools

        
        # Extract Agent Config
        self.system_prompt = self.config.get("system_prompt", f"You are {self.name}, a helpful assistant.")
        self.allowed_tools = self.config.get("tools", "*")
        
    async def execute(self, task_input: str, context: Dict[str, Any] = None, step_callback: Optional[callable] = None) -> Dict[str, Any]:
        """
        Execute a task using the ReAct (Reason-Act-Observe) loop.
        Accommodates timeouts and streaming callbacks.
        """
        context = context or {}
        start_time = datetime.now(timezone.utc)
        logger.info(f"Agent {self.name} ({self.id}) starting task: {task_input[:50]}")
        
        # 1. Recall Memory
        memory_context = await self.world_model.recall_experiences(
            agent=self._get_registry_model(),
            current_task_description=task_input
        )
        
        # Emit initial 'starting' event for UI responsiveness
        if step_callback:
            await step_callback({
                "step": 0,
                "thought": "Initializing agent context and memory...",
                "action": None,
                "output": None,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "status": "starting"
            })
        
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
                    
                    # Plan/Think - Use instructor for structured parsing
                    react_step = await self._react_step(task_input, memory_context, execution_history)
                    
                    thought = react_step.thought
                    action = react_step.action.model_dump() if react_step.action else None
                    answer = react_step.final_answer
                    
                    step_record = {
                        "step": current_step,
                        "thought": thought,
                        "action": action,
                        "output": None,
                        "timestamp": datetime.now(timezone.utc).isoformat()
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
                            
                            # Phase 14: Capture screenshot for vision analysis
                            if tool_name == "browser_screenshot" and "saved to" in str(observation):
                                try:
                                    import base64

                                    # Extract path from observation: "Screenshot saved to /tmp/screenshot_xyz.png"
                                    path = observation.split("saved to ")[-1].strip()
                                    if os.path.exists(path):
                                        with open(path, "rb") as f:
                                            self.last_screenshot = base64.b64encode(f.read()).decode("utf-8")
                                        logger.info(f"Captured screenshot from {path} for next ReAct step.")
                                except Exception as se:
                                    logger.warning(f"Failed to capture screenshot for vision: {se}")
                        
                        step_record["output"] = observation
                        execution_history += f"Observation: {str(observation)}\n"
                        
                        # Special handling for Tool Search
                        if tool_name == "mcp_tool_search" and "Found" in str(observation):
                            # The tool execution itself returns the text, but we need to fetch the objects 
                            # to add to session_tools. 
                            # Re-running search here efficiently (or could parse the Text, but re-running is safer)
                            query = tool_args.get("query", "")
                            found_tools = await self.mcp.search_tools(query, limit=5)
                            self.session_tools.extend(found_tools)
                            logger.info(f"Agent {self.name} lazy-loaded {len(found_tools)} tools for next step.")

                        
                        if step_callback:
                            await step_callback(step_record)
                        
                    else:
                        if current_step == max_steps:
                            # If we hit max steps without an answer, the last thought might contain something
                            final_answer = thought or "Maximum steps reached without final answer."
                            status = "max_steps_exceeded"
                            
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
            
        # 3. TRACE Framework Metrics (Phase 6.6)
        complexity = self.llm.analyze_query_complexity(task_input)
        
        # Heuristic for expected steps based on complexity
        # SIMPLE=1, MODERATE=3, COMPLEX=5, ADVANCED=8
        expected_steps_map = {
            "simple": 1,
            "moderate": 3,
            "complex": 5,
            "advanced": 8
        }
        expected_steps = expected_steps_map.get(complexity.value, 3)
        actual_steps = len(steps)
        
        # Efficiency Ratio: Actual / Expected (closer to 1.0 is ideal, > 1.0 is inefficient)
        step_efficiency = actual_steps / expected_steps
        
        # Plan Adherence Check
        # Basic heuristic: Did the agent reach a final answer, or was it forced?
        plan_adherence = 1.0 if status == "success" else 0.5
        if status in ["failed", "timeout"]:
             plan_adherence = 0.0

        # 4. LLM-as-a-Judge Audit (Phase 6.6)
        audit_report = None
        if self.config.get("audit_mode"):
            try:
                from core.agent_auditor import auditor
                audit_report = await auditor.audit_trace(task_input, {
                    "output": final_answer,
                    "steps": steps,
                    "status": status
                })
                logger.info(f"Audit completed for Agent {self.name}: Score {audit_report.get('score', 'N/A')}")
            except Exception as audit_err:
                logger.warning(f"Audit failed: {audit_err}")

        # 5. Record Experience
        execution_result = {
            "output": final_answer,
            "steps": steps,
            "status": status,
            "complexity": complexity.value,
            "step_efficiency": step_efficiency,
            "plan_adherence": plan_adherence,
            "audit_report": audit_report,
            "timestamp": start_time.isoformat()
        }
        
        await self._record_execution(task_input, execution_result)
        
        return execution_result

    async def _react_step(self, task_input: str, memory: Dict, history: str) -> ReActStep:
        """
        Generate a single ReAct step with Pydantic validation.
        Uses instructor for structured output when available.
        """
        # Get available tools (Core + Session Lazy Loaded)
        all_tools = await self.mcp.get_all_tools()
        
        # 1. Filter Logic
        active_tools = []
        
        # If agent has explicit "allowed_tools", respect that (ignore core/lazy if restricted subset)
        # But if allowed_tools is "*", we use Lazy Loading
        if self.allowed_tools == "*":
             # Core Tools + Session Tools
             active_tools = [t for t in all_tools if t["name"] in self.CORE_TOOLS_NAMES]
             active_tools.extend(self.session_tools)
        else:
             # Explicit list in config
             active_tools = [t for t in all_tools if t["name"] in self.allowed_tools]
        
        # Deduplicate
        seen_tools = set()
        unique_active_tools = []
        for t in active_tools:
            if t["name"] not in seen_tools:
                unique_active_tools.append(t)
                seen_tools.add(t["name"])

        # Inject special "mcp_tool_search" if not present
        if "mcp_tool_search" not in [t["name"] for t in unique_active_tools]:
             unique_active_tools.append({
                 "name": "mcp_tool_search",
                 "description": "Search for more capabilities/tools if you can't find what you need in the current list. Returns list of tools that you can then use in the NEXT step.",
                 "parameters": {"query": "string"}
             })

        tool_descriptions = json.dumps([{"name": t["name"], "description": t.get("description", "")} for t in unique_active_tools], indent=2)
        
        system_prompt = f"""{self.system_prompt}

AVAILABLE TOOLS:
{tool_descriptions}

FORMAT: You must respond with structured output containing:
- thought: Your reasoning about what to do next
- action: If you need to use a tool, provide {{"tool": "tool_name", "params": {{...}}}}
- final_answer: If you have enough information to answer, provide the response

Only provide EITHER action OR final_answer, not both.

ORCHESTRATION POWERS:
- You can discover and call external integrations (Salesforce, Slack, HubSpot, etc.)
- You can list and trigger automated workflows
- You can spawn sub-specialty agents to help you
- You can INGEST KNOWLEDGE from text and files (PDF, CSV, Excel) into Atom's long-term memory
- You can SEARCH FORMULAS and business logic to ensure calculation accuracy
- You can PUSH/CREATE/UPDATE data (leads, deals, tasks, invoices, tickets, orders, files) across ALL 46+ integrations in a granular way
- You can DISCOVER connected integrations and SEARCH across all of them simultaneously
- You can use 'create_record' and 'update_record' for universal granular manipulation of any connected system
- **IMPORTANT**: Use `save_business_fact` to store "Truths" (policies, rules). If you see a Fact in memory, VERIFY its citations (`verify_citation`) if it's critical.
"""
        
        # Build rich memory context for the prompt
        experiences = memory.get('experiences', [])
        knowledge = memory.get('knowledge', [])
        formulas = memory.get('formulas', [])
        facts = memory.get('business_facts', [])
        
        memory_sections = []
        if experiences:
            exp_summaries = [f"- {e.get('input_summary', 'Task')[:80]}... → {e.get('outcome', 'completed')}" for e in experiences[:3]]
            memory_sections.append(f"PAST EXPERIENCES:\n" + "\n".join(exp_summaries))
        if knowledge:
            doc_summaries = [f"- {k.get('text', '')[:100]}..." for k in knowledge[:3]]
            memory_sections.append(f"RELEVANT KNOWLEDGE:\n" + "\n".join(doc_summaries))
        if formulas:
            formula_summaries = [f"- {f.get('name', 'Formula')}: {f.get('description', '')[:60]}" for f in formulas[:3]]
            memory_sections.append(f"AVAILABLE FORMULAS:\n" + "\n".join(formula_summaries))
        if facts:
            fact_summaries = [f"- [Status: {f.verification_status}] {f.fact} (Source: {f.metadata.get('source', 'unknown')})" for f in facts[:3]]
            memory_sections.append(f"TRUSTED BUSINESS FACTS:\n" + "\n".join(fact_summaries))
        
        memory_display = "\n\n".join(memory_sections) if memory_sections else "(No prior context)"
        
        # --- Chaos Engineering: Noise Injection (Phase 6.6) ---
        noise = self.config.get("chaos_noise_level", 0.0)
        if noise > 0:
            import random
            if random.random() < noise:
                junk_signals = [
                    "SYSTEM_MAINTENANCE: Server cluster 7 is undergoing routine patching.",
                    "NOTIFICATION: Your subscription for 'Cloud Storage' will renew in 4 days.",
                    "DATA_NOISE: [CRC_CHECK_SUM_ERROR] at memory address 0xAF32.",
                    "USER_CHITCHAT: By the way, I think the weather is nice today.",
                    "LOG: Background process 'sync_worker_9' completed with 0 errors."
                ]
                noise_signal = random.choice(junk_signals)
                memory_display += f"\n\n[UNCORRELATED_SIGNAL]: {noise_signal}"
                logger.info(f"Chaos Engineering: Injected noise into Agent {self.name} context.")

        user_prompt = f"""Request: {task_input}

MEMORY CONTEXT:
{memory_display}

Execution History:
{history if history else "(Starting fresh)"}

What is your next step?"""

        # Use BYOK's tenant-aware structured generation (respects BYOK vs Managed subscription)
        # Pass screenshot if available and vision is enabled
        image_payload = self.last_screenshot if self.vision_enabled else None
        
        structured_result = await self.llm.generate_structured_response(
            prompt=user_prompt,
            system_instruction=system_prompt,
            response_model=ReActStep,
            temperature=0.2,
            task_type="reasoning",
            agent_id=self.id,
            image_payload=image_payload
        )
        
        # Consume the screenshot after one use to prevent stale visual context
        self.last_screenshot = None
        
        if structured_result:
            return structured_result
        
        # Fallback: Use BYOK handler for raw response
        raw_response = await self.llm.generate_response(
            prompt=user_prompt,
            system_instruction=system_prompt,
            model_type="fast",
            temperature=0.3,
            agent_id=self.id
        )
        
        # Handle error responses
        if not raw_response or "not initialized" in str(raw_response).lower():
            return ReActStep(
                thought="LLM not available",
                final_answer=raw_response if raw_response else "Unable to process - LLM not configured."
            )
        
        # Simple fallback parsing
        return ReActStep(
            thought=raw_response[:200] if raw_response else "Unable to reason",
            final_answer=raw_response if "answer" in raw_response.lower() else None
        )
        
    async def _step_act(self, tool_name: str, args: Dict, context: Dict = None, step_callback: Optional[callable] = None) -> Any:
        """Execute a tool via MCP with Governance Check"""
        try:
            # 1. Governance Maturity Check
            with get_db_session() as db:
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
        success = result["status"] == "success"

        # Calculate robust confidence score
        # 1.0 = Perfect success
        # 0.5 = Timeout or max steps
        # 0.0 = Error/Failure
        confidence = 1.0 if success else 0.5
        if result["status"] == "failed":
            confidence = 0.0

        experience = AgentExperience(
            id=str(uuid.uuid4()),
            agent_id=self.id,
            task_type="custom_task_react",
            input_summary=input_text[:200],
            outcome=result["status"],
            learnings=result.get("output", "")[:500],
            confidence_score=confidence,
            step_efficiency=result.get("step_efficiency", 1.0),
            metadata_trace={
                "complexity": result.get("complexity"),
                "step_count": len(result.get("steps", [])),
                "plan_adherence": result.get("plan_adherence"),
                "audit_report": result.get("audit_report"),
                "duration_seconds": (datetime.now(timezone.utc) - datetime.fromisoformat(result["timestamp"])).total_seconds() if "timestamp" in result else 0
            },
            agent_role=self.config.get("role", "specialty_agent"),
            specialty=self.config.get("specialty", "general"),
            timestamp=datetime.now(timezone.utc)
        )
        await self.world_model.record_experience(experience)

        # 2. Update Governance Maturity
        success = result["status"] == "success"
        with get_db_session() as db:
            try:
                gov = AgentGovernanceService(db)
                await gov.record_outcome(self.id, success=success)
            except Exception as e:
                logger.error(f"Failed to record governance outcome: {e}", exc_info=True)

    async def _wait_for_approval(self, action_id: str) -> bool:
        """Poll for HITL decision"""
        max_wait = self.config.get("hitl_timeout", 600) # Default 10 mins
        interval = 5
        elapsed = 0

        while elapsed < max_wait:
            with get_db_session() as db:
                gov = AgentGovernanceService(db)
                status_info = gov.get_approval_status(action_id)

                if status_info["status"] == HITLActionStatus.APPROVED.value:
                    return True
                if status_info["status"] == HITLActionStatus.REJECTED.value:
                    return False

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
