import asyncio
import base64
import io
import logging
import os
from typing import Any, Dict, List, Optional
from ai.lux_model import ComputerActionType, LuxModel
from browser_engine.driver import BrowserManager
from PIL import Image
from playwright.async_api import Page

from integrations.mcp_service import mcp_service

logger = logging.getLogger(__name__)

class BrowserAgent:
    """
    High-level agent that executes tasks using the BrowserManager.
    Designed to integrate with OpenAGI Lux (`oagi`) for decision making.
    """
    def __init__(self, headless: bool = True):
        self.manager = BrowserManager.get_instance(headless=headless)
        self.mcp = mcp_service  # MCP access for web search and web access
        self.lux = LuxModel() # Vision-based brain

    async def execute_task(
        self, 
        url: str, 
        goal: str, 
        safe_mode: bool = True,
        user_id: Optional[str] = None,
        agent_id: Optional[str] = None,
        db_session: Optional[Any] = None # SQLAlchemy Session
    ) -> Dict[str, Any]:
        """
        Main execution loop.
        Includes RBAC checks if db_session is provided.
        """
        # 0. Governance / Access Check
        if db_session and user_id and agent_id:
            from core.agent_governance_service import AgentGovernanceService
            gov = AgentGovernanceService(db_session)
            if not gov.can_access_agent_data(user_id, agent_id):
                logger.error(f"Access Denied: User {user_id} cannot access Agent {agent_id}")
                return {"status": "failed", "error": "Access Denied: Role/Specialty mismatch"}

        # 1. Context Injection
        context_data = await self._fetch_context(goal)
        logger.info(f"Context injected for goal '{goal}': {context_data}")
        
        context = await self.manager.new_context()
        page = await context.new_page()
        
        try:
            logger.info(f"Navigating to {url}")
            await page.goto(url)
            await page.wait_for_load_state("networkidle")
            
            execution_log = []
            max_steps = 10
            
            for i in range(max_steps):
                # 3. Capture State (Visual)
                screenshot_bytes = await page.screenshot(type="png")
                screenshot_img = Image.open(io.BytesIO(screenshot_bytes))

                # 4. Lux Predict (Visual Reasoning)
                # We ask Lux to interpret the current state vs the goal
                state_desc = f"Current URL: {page.url}. I am on step {i+1} of '{goal}'."

                # Context integration
                prompt_context = ""
                if context_data.get("business_facts"):
                    prompt_context += f"\nCONSTRAINT/FACTS: {'; '.join(context_data['business_facts'])}"
                if context_data.get("credentials_hint"):
                    prompt_context += f"\nHINT: {context_data['credentials_hint']}"

                full_prompt = f"{goal}. {state_desc} {prompt_context}"

                # Track action planning performance
                import time
                plan_start = time.time()

                actions = await self.lux.interpret_command(full_prompt, screenshot_img)

                plan_time = time.time() - plan_start
                logger.info(f"Lux action planning took {plan_time:.2f}s, generated {len(actions)} actions")

                if not actions:
                    logger.info("No more actions predicted by Lux. Goal might be reached.")
                    break
                    
                for action in actions:
                    # Security Guardrail Check
                    if not self._validate_action_safety(action, safe_mode):
                        error_msg = f"Security Guardrail Triggered: Action '{action.action_type}' is blocked."
                        logger.error(error_msg)
                        return {"status": "blocked", "error": error_msg}
                    
                    # 5. Perform Action
                    await self._perform_lux_action(page, action)
                    execution_log.append(action.description)
                    
                    # Short wait for UI to react
                    await asyncio.sleep(1)

            # 6. Knowledge Extraction
            result_data = {"goal": goal, "url": url, "status": "completed", "steps": execution_log}
            await self._save_knowledge(result_data)
                
            return {"status": "success", "message": "Task completed", "data": result_data}
            
        except Exception as e:
            logger.error(f"Task failed: {e}")
            await page.screenshot(path="error_screenshot.png")
            return {"status": "failed", "error": str(e)}
        finally:
            await context.close()

    async def _fetch_context(self, goal: str) -> Dict[str, Any]:
        """
        Query LanceDB for context relevant to the goal.
        """
        try:
            from core.lancedb_handler import get_lancedb_handler
            handler = get_lancedb_handler()
            
            # 1. Search semantic memory
            results = handler.search("documents", goal, limit=3)

            # 2. Search Business Facts
            from core.agent_world_model import WorldModelService
            wm = WorldModelService(workspace_id="default") # Default for now, ideally passed in
            facts = await wm.get_relevant_business_facts(goal, limit=3)
            
            # 3. Convert to context dict
            context = {
                "business_facts": [f"{f.fact} (Source: {f.citations})" for f in facts]
            }
            for res in results:
                # flatten relevant info
                if "username" in res["text"].lower():
                    context["credentials_hint"] = res["text"]
            
            if facts:
                logger.info(f"Injecting {len(facts)} business facts into Browser Agent context")

            return context
        except ImportError:
            logger.warning("Core modules not available, skipping context injection")
            return {}
        except Exception as e:
            logger.warning(f"Context fetch failed: {e}")
            return {}

    async def _save_knowledge(self, data: Dict[str, Any]):
        """
        Save execution results to Knowledge Graph.
        """
        try:
            from core.knowledge_ingestion import get_knowledge_ingestion
            ingestor = get_knowledge_ingestion()
            
            # Create a textual representation of the result
            text = f"Agent Execution Result: {data.get('goal')} on {data.get('url')}. Info: {data.get('extracted_info', {})}"
            
            # Ingest
            await ingestor.process_document(text, doc_id=f"agent_run_{base64.b64encode(os.urandom(6)).decode('utf-8')}", source="browser_agent")
            
        except ImportError:
            logger.warning("Core modules not available, skipping knowledge save")
        except Exception as e:
            logger.warning(f"Knowledge save failed: {e}")

    def _validate_action_safety(self, action: Any, safe_mode: bool) -> bool:
        """
        Guardrail: Block high-risk actions unless verified.
        """
        if not safe_mode:
            return True
            
        risky_keywords = ["pay", "send money", "transfer", "tax", "checkout"]
        
        # Check description and parameters for risky keywords
        description = action.description.lower()
        params = str(action.parameters).lower()
        
        for keyword in risky_keywords:
            if keyword in description or keyword in params:
                logger.warning(f"Guardrail Risk Detected: '{keyword}' in action.")
                return False
                
        return True

    def _get_lux_action_plan(self, goal: str, context: Dict[str, Any] = None) -> List[Dict[str, Any]]:
        """
        Legacy method - kept for backward compatibility.
        This method is no longer used; the main execution loop uses lux.interpret_command() directly.

        The real AI action planning happens in execute_task() at line 79:
            actions = await self.lux.interpret_command(full_prompt, screenshot_img)

        This Lux integration uses Claude 3.5 Sonnet for visual reasoning and action planning.
        """
        logger.warning("_get_lux_action_plan() called but is deprecated. Use lux.interpret_command() instead.")
        return []

    async def _perform_lux_action(self, page: Page, action: Any):
        """Execute a single Lux action using Playwright."""
        action_type = action.action_type
        params = action.parameters
        
        logger.info(f"Agent Action: {action_type} - {action.description}")
        
        if action_type == ComputerActionType.CLICK:
            if 'coordinates' in params:
                x, y = params['coordinates']
                await page.mouse.click(x, y)
            elif 'selector' in params:
                await page.click(params['selector'])
                
        elif action_type == ComputerActionType.TYPE:
            text = params.get('text', '')
            selector = params.get('selector')
            # If coordinates provided, click first to focus
            if 'coordinates' in params:
                x, y = params['coordinates']
                await page.mouse.click(x, y)
            elif selector:
                await page.fill(selector, text)
                return
            await page.keyboard.type(text)
            
        elif action_type == ComputerActionType.KEYBOARD:
            keys = params.get('keys', [])
            for key in keys:
                await page.keyboard.press(key)
                
        elif action_type == ComputerActionType.SCROLL:
            direction = params.get('direction', 'down')
            amount = params.get('amount', 500)
            if direction == 'down':
                await page.mouse.wheel(0, amount)
            else:
                await page.mouse.wheel(0, -amount)
                
        elif action_type == ComputerActionType.WAIT:
            duration = params.get('duration', 1.0)
            await asyncio.sleep(duration)

    async def login_and_download(self, url: str, creds: Dict[str, str]):
        """
        Specific workflow method for Phase 19 verification.
        Combines logic to ensure 'expect_download' works correctly.
        """
        context = await self.manager.new_context()
        page = await context.new_page()
        
        try:
            logger.info(f"Navigating to {url}")
            await page.goto(url)
            
            # 1. Login
            await page.fill("#username", creds["username"])
            await page.fill("#password", creds["password"])
            logger.info("Submitting login form...")
            await page.click("#login-btn")
            
            # Use explicit navigation wait
            logger.info("Waiting for dashboard redirect...")
            await page.wait_for_url("**/dashboard.html", timeout=5000)
            logger.info("Dashboard loaded.")
            
            # 2. Download
            # Explicitly wait for the button before clicking
            await page.wait_for_selector("#download-btn")
            
            logger.info("Clicking download button...")
            async with page.expect_download(timeout=5000) as download_info:
                await page.click("#download-btn")
            
            logger.info("Download event detected.")
            download = await download_info.value
            # Wait for download to finish
            path = await download.path()
            logger.info(f"Downloaded file to {path}")
            
            # Save for verification
            await download.save_as("downloaded_statement.pdf")
            
            return {"status": "success", "file": "downloaded_statement.pdf"}
            
        except Exception as e:
            logger.error(f"Workflow failed: {e}")
            return {"status": "error", "message": str(e)}
        finally:
            # Ensure context closed cleanly
            try:
                await context.close()
            except Exception:
                pass

    async def _capture_state(self, page: Page) -> Dict[str, Any]:
        """
        Capture state for Lux Model (OpenAGI).
        """
        # 1. Screenshot
        screenshot = await page.screenshot(type="jpeg", field="base64")
        
        # 2. Accessibility Tree (or DOM)
        snapshot = await page.accessibility.snapshot()
        
        return {
            "screenshot_base64": screenshot,
            "accessibility_tree": snapshot,
            "url": page.url
        }
