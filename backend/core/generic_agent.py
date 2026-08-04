import asyncio
from datetime import datetime, timezone
import json
import logging
import os
from typing import Any, Dict, List, Optional
import uuid

from core.agent_governance_service import AgentGovernanceService
from core.agent_world_model import AgentExperience, WorldModelService
from core.database import get_db_session
from core.llm_service import LLMService
from core.models import AgentRegistry, AgentStatus, HITLActionStatus
from core.react_models import ReActObservation, ReActStep, ToolCall
from integrations.mcp_service import mcp_service
from core.reflection_service import ReflectionService
from core.graduation_service import GraduationService
from core.llm.canvas_summary_service import CanvasSummaryService

# Instructor library is used internally by LLMService for structured output
# No need to import directly here
instructor = None  # Reserved for future direct use if needed
INSTRUCTOR_AVAILABLE = False  # LLMService handles instructor internally

logger = logging.getLogger(__name__)

# SupervisorAgent-style observation filter (additive, flag-gated, default OFF).
# See core/observation_filter_service.py.
try:
    from core.observation_filter_service import (
        OBSERVATION_FILTER_ENABLED,
        ObservationFilterService,
    )

    _OBS_FILTER_AVAILABLE = True
except Exception:  # pragma: no cover - defensive
    _OBS_FILTER_AVAILABLE = False
    OBSERVATION_FILTER_ENABLED = False

    class ObservationFilterService:  # type: ignore[no-redef]
        async def filter_history(self, *a, **kw):
            return "", {}

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

        # LLM Integration Note:
        # Agent classes now use LLMService as the single source of truth for all LLM interactions.
        # LLMService wraps BYOKHandler and provides a unified interface with:
        # - Structured generation (via instructor integration)
        # - Cognitive tier routing (5-tier system)
        # - Cost tracking and telemetry
        # - BYOK key resolution
        #
        # Architecture layers:
        # - Layer 1 (Bottom): AsyncOpenAI/AsyncAnthropic clients (provider SDKs)
        # - Layer 2 (Middle): BYOKHandler (unified internal interface)
        # - Layer 3 (Top): LLMService (single source of truth for all code)
        # - All code: Uses Layer 3 (LLMService) for unified observability and management
        self.llm = LLMService(workspace_id=workspace_id)

        # Initialize Services (must come after self.llm is created)
        self.world_model = WorldModelService(workspace_id)
        self.reflection_service = ReflectionService(workspace_id)
        self.canvas_summary_service = CanvasSummaryService(self.llm)
        self.mcp = mcp_service
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
        optimization = context.get("optimization", {})
        max_steps = optimization.get("max_steps") or self.config.get("max_steps", 5)
        mentorship_mode = optimization.get("mentorship_mode", False)
        
        timeout_seconds = self.config.get("timeout_seconds", 300) # Default 5 mins
        steps = []
        final_answer = None
        status = "success"
        
        try:
            async def run_loop():
                nonlocal final_answer, status
                current_step = 0
                execution_history = ""

                # Workstream G — in-loop parallel tool execution (default ON).
                try:
                    from core.hallucination_config import (
                        is_parallel_tools_enabled as _is_parallel_tools_enabled,
                    )
                except Exception:  # pragma: no cover - defensive
                    _is_parallel_tools_enabled = lambda: False
                _parallel_tools_enabled = _is_parallel_tools_enabled()

                while current_step < max_steps:
                    current_step += 1

                    # Spend gate: check the tenant budget BEFORE the expensive
                    # LLM call. When denied, halt the loop cleanly with a
                    # budget-exceeded status (mirrors the max_steps/timeout exit
                    # paths below).
                    budget_check = await self._check_budget_before_react()
                    if not budget_check.get("allowed"):
                        final_answer = (
                            f"Budget limit reached — execution halted. "
                            f"({budget_check.get('reason') or 'over budget'})"
                        )
                        status = "budget_exceeded"
                        logger.warning(
                            f"Budget gate halted agent {getattr(self, 'name', '?')} at "
                            f"step {current_step}: {budget_check.get('reason')}"
                        )
                        break

                    # Plan/Think - Use instructor for structured parsing
                    react_step = await self._react_step(task_input, memory_context, execution_history, context)

                    thought = react_step.thought
                    action = react_step.action.model_dump() if react_step.action else None
                    answer = react_step.final_answer

                    # Workstream G degradation: if parallel tools are disabled
                    # but the model emitted `actions`, promote the first action
                    # so the step still executes through the single-action path.
                    if react_step.actions and not _parallel_tools_enabled:
                        react_step.action = react_step.actions[0]
                        action = react_step.action.model_dump()

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

                    # ── Parallel tool execution (Workstream G) ──────────────
                    # Multiple independent tools emitted via `actions` — execute
                    # in parallel with all-or-nothing HITL batch approval and
                    # stream each result. `continue` skips the single-action path.
                    if react_step.actions and _parallel_tools_enabled:
                        parallel_results = await self._execute_parallel_tools(
                            react_step.actions, context, step_callback
                        )
                        for pr in parallel_results:
                            p_tool = pr["tool_name"]
                            p_params = pr.get("params") or {}
                            p_record = {
                                "step": current_step,
                                "thought": thought,
                                "action": {"tool": p_tool, "params": p_params},
                                "output": str(pr["output"])[:500],
                                "timestamp": datetime.now(timezone.utc).isoformat(),
                            }
                            if step_callback:
                                await step_callback(p_record)
                            execution_history += (
                                f"Action: {p_tool}({json.dumps(p_params)})\n"
                                f"Observation: {pr['output']}\n"
                            )
                            try:
                                from core.atom_meta_agent import _is_error_observation
                            except Exception:  # pragma: no cover - defensive
                                _is_error_observation = lambda _o: False  # type: ignore
                            if _is_error_observation(pr["output"]):
                                execution_history += (
                                    f"[CRITIQUE] The action {p_tool} returned an "
                                    f"error: {str(pr['output'])[:200]}. Re-plan "
                                    f"before retrying.\n"
                                )
                            steps.append(p_record)
                        continue

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
                        # RTK compression: compress verbose tool/terminal output
                        # before it enters the execution history. Lossless for
                        # structured data (JSON/SQL/API responses skipped).
                        try:
                            from core.llm.compression import get_compression_pipeline
                            _obs_str = str(observation)
                            _compressed, _rtk_m = (
                                get_compression_pipeline().compress_tool_output(_obs_str)
                            )
                            if _rtk_m.savings_tokens > 0:
                                observation = _compressed
                        except Exception:
                            pass  # compression must never break the agent loop
                        execution_history += f"Observation: {str(observation)}\n"

                        # ── In-loop self-correction (Workstream A) ────────────
                        # Mirror of the atom_meta_agent hook: when the observation
                        # looks like an error / blocked result, append a
                        # deterministic critique so the model re-plans the next
                        # step instead of repeating the same failing action.
                        try:
                            from core.atom_meta_agent import _is_error_observation
                        except Exception:  # pragma: no cover - defensive
                            _is_error_observation = lambda _o: False  # type: ignore
                        if _is_error_observation(observation):
                            execution_history += (
                                f"[CRITIQUE] The action {tool_name} returned an error: "
                                f"{str(observation)[:200]}. Re-plan before retrying.\n"
                            )

                        # ── SupervisorAgent-style observation filter ─────────
                        # Additive + flag-gated + default OFF. Wrapped in
                        # try/except; failures only logged at debug level. See
                        # core/observation_filter_service.py.
                        try:
                            if _OBS_FILTER_AVAILABLE and OBSERVATION_FILTER_ENABLED:
                                _obs_filter = ObservationFilterService(llm=self.llm)
                                _new_hist, _obs_metrics = await _obs_filter.filter_history(
                                    execution_history, current_step, task_input
                                )
                                if _obs_metrics.get("savings_tokens", 0) > 0:
                                    execution_history = _new_hist
                        except Exception as _of_err:
                            logger.debug("observation filter skipped: %s", _of_err)

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
            
        # 2.5: Generate Reflection/Critique on failure (Phase 215)
        if status in ["failed", "timeout", "max_steps_exceeded", "budget_exceeded"]:
            try:
                await self.reflection_service.generate_critique(
                    agent_id=self.id,
                    task_input=task_input,
                    intent=self.config.get("specialty", "general task"),
                    action="react_loop",
                    outcome=status
                )
                logger.info(f"Self-Evolution: Generated critique for Agent {self.name} failure.")
            except Exception as ref_err:
                logger.warning(f"Failed to generate self-critique: {ref_err}")
            
        # 3. TRACE Framework Metrics (Phase 6.6)
        complexity = self.llm._get_handler().analyze_query_complexity(task_input)
        
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
        # Normalize internal loop sentinels to valid ExecutionStatus values at
        # the execution boundary. ``budget_exceeded`` is an in-loop signal; if
        # it leaks into the returned payload, the API/WS layer serializes an
        # invalid status to consumers (DB persistence maps it separately, but
        # the return value must be valid on its own).
        if status == "budget_exceeded":
            status = "failed"
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

    def _retrieve_skill_instructions(self, task_input: str) -> str:
        """Prompt-time skill auto-injection (Workstream C, mirror of meta-agent).

        Returns an empty string when the flag is off / no skills match / DB
        unavailable — never raises, never blocks the ReAct loop.
        """
        try:
            from core.database import get_db_session
            from core.hallucination_config import is_skill_injection_enabled
            from core.skill_retrieval_service import get_skill_retrieval_service

            if not is_skill_injection_enabled():
                return ""
            with get_db_session() as skills_db:
                return get_skill_retrieval_service().retrieve_top_skills(
                    skills_db,
                    getattr(self, "tenant_id", None),
                    self.workspace_id,
                    task_input,
                    limit=3,
                )
        except Exception as e:
            logger.debug(f"skill injection skipped: {e}")
            return ""

    async def _check_budget_before_react(self) -> Dict[str, Any]:
        """Spend gate: check the tenant budget BEFORE the expensive LLM call.

        Previously the budget was only checked per-tool, so the LLM planning
        call ran ungated every iteration. This closes the gap so a run over
        budget in hard_stop (or soft_stop without an active episode) halts at
        the next LLM call. Fail-open on error, matching the convention in
        BudgetEnforcementService.
        """
        tenant_id = getattr(self, "tenant_id", None) or "default"
        try:
            from core.budget_enforcement_service import BudgetEnforcementService

            svc = BudgetEnforcementService()
            return await svc.check_budget_before_action(
                tenant_id=tenant_id,
                agent_id=getattr(self, "id", None) or "generic_agent",
                action="llm_react_step",
            )
        except Exception as e:
            logger.warning(f"Budget pre-check failed (fail-open): {e}")
            return {"allowed": True, "reason": "budget-check-error", "enforcement_mode": "unknown"}

    async def _react_step(self, task_input: str, memory: Dict, history: str, context: Dict = None) -> ReActStep:
        """
        Generate a single ReAct step with Pydantic validation.
        """
        context = context or {}
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
        
        optimization = context.get("optimization", {})
        agent_model_tier = optimization.get("model") or "auto"
        mentorship_mode = optimization.get("mentorship_mode", False)
        
        mentorship_focus = ""
        if mentorship_mode:
            mentorship_focus = f"\nMENTORSHIP FOCUS: This task has high historical complexity or rejection rates. Be extra cautious, verify all tool outputs, and provide detailed reasoning for every step.\n"

        skill_instructions = self._retrieve_skill_instructions(task_input)

        system_prompt = f"""{self.system_prompt}{mentorship_focus}

{skill_instructions}

AVAILABLE TOOLS:
{tool_descriptions}

FORMAT: You must respond with structured output containing:
- thought: Your reasoning about what to do next
- action: If you need to use a SINGLE tool, provide {{"tool": "tool_name", "params": {{...}}}}
- actions: If you need to use MULTIPLE INDEPENDENT tools at once, provide [{{"tool": "tool_name", "params": {{...}}}}, ...]. Only use this when the tools do NOT depend on each other's output — they run in parallel.
- final_answer: If you have enough information to answer, provide the response

Only provide EITHER action OR actions OR final_answer, not multiple.

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

        # WORKSPACE FIELD GUIDE — curated memory snapshot (Workstream E).
        try:
            from core.field_guide_service import get_field_guide_service
            _guide = get_field_guide_service().get_field_guide_context(self.workspace_id)
            if _guide:
                memory_sections.append(_guide)
        except Exception as e:
            logger.debug(f"field guide recall failed: {e}")

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

        # --- Phase 14.5: Semantic Visual Description ---
        semantic_ui_summary = ""
        canvas_id = context.get("canvas_id")
        if canvas_id:
            try:
                # In Upstream, we use the local CanvasPresentationSummaryService or port the SaaS one
                # For consistency with SaaS port, we use the port we just made
                from core.llm.canvas_summary_service import CanvasSummaryService as CSS
                # If vision is DISABLED or it's M2.7, we use the summary instead of screenshot
                # Identify M2.7 by routing info
                is_minimax = "minimax" in str(self.llm._get_handler().default_provider_id).lower()
                if not self.vision_enabled or is_minimax:
                    canvas_state = context.get("canvas_state", {})
                    if canvas_state:
                        semantic_ui_summary = await self.canvas_summary_service.generate_summary(
                            canvas_type=context.get("canvas_type", "generic"),
                            canvas_state=canvas_state,
                            agent_task=task_input
                        )
                        logger.info(f"Generated semantic UI summary for {self.name} (Canvas: {canvas_id})")
            except Exception as e:
                logger.warning(f"Failed to generate semantic summary: {e}")

        # Retrieve past critiques for context
        critiques = await self.reflection_service.get_relevant_critiques(
            agent_id=self.id,
            task_input=task_input
        )
        critique_display = "\n".join([f"- CRITIQUE: {c.critique}" for c in critiques[:2]])

        user_prompt = f"""Request: {task_input}

{f"SEMANTIC UI LAYOUT (SCREEN READER):{semantic_ui_summary}" if semantic_ui_summary else ""}
{f"SELF-EVOLUTION CRITIQUES (LEARN FROM THESE):{critique_display}" if critique_display else ""}
MEMORY CONTEXT:
{memory_display}

Execution History:
{history if history else "(Starting fresh)"}

What is your next step?"""

        # Use BYOK's tenant-aware structured generation (respects BYOK vs Managed subscription)
        # Pass screenshot if available and vision is enabled
        image_payload = self.last_screenshot if self.vision_enabled else None
        
        structured_result = await self.llm.generate_structured(
            prompt=user_prompt,
            system_instruction=system_prompt,
            response_model=ReActStep,
            temperature=0.2,
            model=agent_model_tier,
            agent_id=self.id,
            image_payload=image_payload
        )
        
        # Consume the screenshot after one use to prevent stale visual context
        self.last_screenshot = None
        
        if structured_result:
            return structured_result
        
        # Fallback: Use LLMService for raw response
        raw_response = await self.llm.generate(
            prompt=user_prompt,
            system_instruction=system_prompt,
            model=agent_model_tier if agent_model_tier != "reasoning" else "quality",
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
        
    async def _step_act(self, tool_name: str, args: Dict, context: Dict = None, step_callback: Optional[callable] = None, pre_approved: bool = False) -> Any:
        """Execute a tool via MCP with Governance Check

        ``pre_approved`` (Workstream G): when True, the governance/HITL check is
        skipped — the caller (the parallel-tools batch) has already run it and
        obtained all-or-nothing approval for the whole batch.
        """
        try:
            # 1. Governance Maturity Check
            if not pre_approved:
                with get_db_session() as db:
                    gov = AgentGovernanceService(db)
                    # Async variant: the sync can_perform_action can't await the
                    # budget check inside a running loop (spend-limit bypass).
                    auth_check = await gov.can_perform_action_async(self.id, tool_name)

                    if auth_check.get("requires_human_approval"):
                        # Create HITL Action
                        action_id = gov.request_approval(
                            agent_id=self.id,
                            action_type=tool_name,
                            params=args,
                            reason=auth_check["reason"]
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
                return f"Error: Tool '{tool_name}' not found. Check tool name."
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
                
                # 5. Graduation Check (Autonomous Promotion)
                if success:
                    try:
                        # Skill promotion logic
                        skill_id = self.config.get("active_skill_id")
                        if skill_id:
                             graduation = GraduationService(db)
                             promotion_result = await graduation.check_skill_promotion(
                                 agent_id=self.id,
                                 skill_id=skill_id,
                                 complexity=result.get("complexity", "moderate")
                             )
                             if promotion_result.get("promoted"):
                                 logger.info(f"Agent {self.name} skill {skill_id} promoted to AUTONOMOUS!")
                    except Exception as ge:
                        logger.warning(f"Graduation check failed: {ge}")
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

    async def _wait_for_all_approvals(self, action_ids: List[str]) -> bool:
        """All-or-nothing HITL batch approval (Workstream G).

        Returns True only when ALL actions are APPROVED; any REJECTION (or the
        batch timeout) returns False — the caller must NOT execute any tool.
        """
        max_wait = self.config.get("hitl_timeout", 600)
        interval = 5
        elapsed = 0

        while elapsed < max_wait:
            with get_db_session() as db:
                gov = AgentGovernanceService(db)
                all_approved = True
                for action_id in action_ids:
                    status_info = gov.get_approval_status(action_id)
                    if status_info["status"] == HITLActionStatus.REJECTED.value:
                        return False
                    if status_info["status"] != HITLActionStatus.APPROVED.value:
                        all_approved = False
                if all_approved:
                    return True

            await asyncio.sleep(interval)
            elapsed += interval

        return False  # Timeout

    async def _execute_parallel_tools(
        self,
        actions: List[ToolCall],
        context: Dict,
        step_callback: Optional[callable],
    ) -> List[Dict[str, Any]]:
        """Execute multiple independent tools in parallel (Workstream G).

        Mirror of ``AtomMetaAgent._execute_parallel_tools``. Governance is
        checked once per tool up front; any tool requiring approval forces HITL
        batch approval (all-or-nothing). ``mcp_tool_search`` is executed
        serially (it mutates ``session_tools`` — would race under gather).
        Falls back to sequential execution when ``ATOM_PARALLEL_TOOLS=false``.
        """
        from core.hallucination_config import (
            get_max_parallel_tools,
            is_parallel_tools_enabled,
        )

        if not is_parallel_tools_enabled():
            records = []
            for act in actions[: get_max_parallel_tools()]:
                observation = await self._step_act(
                    act.tool, act.params, context, step_callback
                )
                records.append({
                    "tool_name": act.tool,
                    "params": act.params,
                    "output": observation,
                    "verified_kind": "unverified",
                    "verified_evidence": None,
                })
            return records

        max_tools = get_max_parallel_tools()
        serial_actions = [a for a in actions if a.tool == "mcp_tool_search"]
        parallel_actions = [a for a in actions if a.tool != "mcp_tool_search"][:max_tools]

        # 1. Governance pre-check for the whole batch (all-or-nothing).
        action_ids: List[str] = []
        with get_db_session() as db:
            gov = AgentGovernanceService(db)
            for act in parallel_actions:
                auth_check = await gov.can_perform_action_async(self.id, act.tool)
                if auth_check.get("requires_human_approval"):
                    action_id = gov.request_approval(
                        agent_id=self.id,
                        action_type=act.tool,
                        params=act.params,
                        reason=auth_check["reason"],
                    )
                    action_ids.append(action_id)
                    if step_callback:
                        await step_callback({
                            "type": "hitl_paused",
                            "action_id": action_id,
                            "tool": act.tool,
                            "reason": auth_check["reason"],
                            "parallel_batch": True,
                        })
                elif not auth_check["allowed"]:
                    # Blocked — the whole batch is aborted (all-or-nothing).
                    return [
                        {
                            "tool_name": a.tool,
                            "params": a.params,
                            "output": f"Governance Error: {auth_check['reason']}",
                            "verified_kind": "blocked",
                            "verified_evidence": None,
                        }
                        for a in parallel_actions
                    ]

        if action_ids:
            approved = await self._wait_for_all_approvals(action_ids)
            if not approved:
                return [
                    {
                        "tool_name": a.tool,
                        "params": a.params,
                        "output": (
                            f"Governance Error: Action {a.tool} was REJECTED "
                            f"by user or timed out (parallel batch)."
                        ),
                        "verified_kind": "rejected",
                        "verified_evidence": None,
                    }
                    for a in parallel_actions
                ]

        # 2. Execute the parallel batch. Governance already granted above.
        results = await asyncio.gather(
            *[
                self._step_act(
                    a.tool, a.params, context, step_callback, pre_approved=True
                )
                for a in parallel_actions
            ],
            return_exceptions=True,
        )

        records: List[Dict[str, Any]] = []
        for act, res in zip(parallel_actions, results):
            if isinstance(res, Exception):
                observation = f"Tool Execution Failed: {res}. You can try to correct parameters or move to next step."
            else:
                observation = res
            records.append({
                "tool_name": act.tool,
                "params": act.params,
                "output": observation,
                "verified_kind": "unverified",
                "verified_evidence": None,
            })

        # 3. Serial tool-search actions (mutate session_tools — no race).
        for act in serial_actions:
            try:
                found_tools = await self.mcp.search_tools(
                    act.params.get("query", ""), limit=5
                )
                self.session_tools.extend(found_tools)
                observation = (
                    f"Found {len(found_tools)} new tools (total: "
                    f"{len(self.session_tools)}). They have been added to your "
                    f"toolkit for the next step: {[t['name'] for t in found_tools]}"
                )
            except Exception as e:
                observation = f"Tool search failed: {e}"
            records.append({
                "tool_name": act.tool,
                "params": act.params,
                "output": observation,
                "verified_kind": "unverified",
                "verified_evidence": None,
            })

        return records

    def _get_registry_model(self) -> AgentRegistry:
        """Helper to reconstruct the model for passing to services"""
        return AgentRegistry(
            id=self.id,
            name=self.name,
            configuration=self.config
        )
