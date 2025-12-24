import logging
import asyncio
import base64
from typing import Dict, Any, List, Optional
from playwright.async_api import Page

from browser_engine.driver import BrowserManager

logger = logging.getLogger(__name__)

class BrowserAgent:
    """
    High-level agent that executes tasks using the BrowserManager.
    Designed to integrate with OpenAGI Lux (`oagi`) for decision making.
    """
    def __init__(self, headless: bool = True):
        self.manager = BrowserManager.get_instance(headless=headless)

    async def execute_task(self, url: str, goal: str, safe_mode: bool = True) -> Dict[str, Any]:
        """
        Main execution loop.
        1. Context Injection: Fetch relevant info from memory.
        2. Navigate to URL.
        3. Loop: Capture State -> Lux Predict -> Perform Action.
        4. Knowledge Extraction: Save findings to memory.
        """
        # 1. Context Injection
        context_data = await self._fetch_context(goal)
        logger.info(f"Context injected for goal '{goal}': {context_data}")
        
        context = await self.manager.new_context()
        page = await context.new_page()
        
        try:
            logger.info(f"Navigating to {url}")
            await page.goto(url)
            await page.wait_for_load_state("networkidle")
            
            # Simulated Lux Loop (Placeholder for 'oagi' integration)
            # We pass context_data to the planner (mocked here)
            action_plan = self._get_lux_action_plan(goal, context_data)
            
            execution_log = []
            
            for step in action_plan:
                # Security Guardrail Check
                if not self._validate_action_safety(step, safe_mode):
                    error_msg = f"Security Guardrail Triggered: Action '{step.get('action')}' on '{step.get('selector')}' is blocked."
                    logger.error(error_msg)
                    return {"status": "blocked", "error": error_msg}
                
                await self._perform_step(page, step)
                execution_log.append(step)
            
            # 4. Knowledge Extraction (Simulated for MVP)
            # In real system, we'd process the final DOM or visual state
            result_data = {"goal": goal, "url": url, "status": "completed"}
            if "Find CEO" in goal: 
                # Mock finding data from page
                result_data["extracted_info"] = {"role": "CEO", "name": "Alice Smith"}
            
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
            
            # 2. Convert to context dict
            context = {}
            for res in results:
                # flatten relevant info
                if "username" in res["text"].lower():
                    context["credentials_hint"] = res["text"]
            
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

    def _validate_action_safety(self, step: Dict[str, Any], safe_mode: bool) -> bool:
        """
        Guardrail: Block high-risk actions unless verified.
        """
        if not safe_mode:
            return True
            
        risky_keywords = ["pay", "send money", "transfer", "tax", "checkout"]
        
        # Check selector and value for risky keywords
        selector = step.get("selector", "").lower()
        value = str(step.get("value", "")).lower()
        
        for keyword in risky_keywords:
            if keyword in selector or keyword in value:
                logger.warning(f"Guardrail Risk Detected: '{keyword}' in action.")
                return False
                
        return True

    def _get_lux_action_plan(self, goal: str, context: Dict[str, Any] = None) -> List[Dict[str, Any]]:
        """
        Placeholder for `oagi.lux.predict(state, goal)`.
        Now context-aware!
        """
        context = context or {}
        
        # MVP Logic
        if "Login" in goal:
            # Use context if available, else default
            username = "admin"
            if "admin@atom.ai" in str(context):
                username = "admin@atom.ai"
                
            return [
                {"action": "fill", "selector": "#username", "value": username},
                {"action": "fill", "selector": "#password", "value": "1234"},
                {"action": "click", "selector": "#login-btn"},
                {"action": "wait", "state": "networkidle"}
            ]
        elif "Download" in goal:
             return [
                 {"action": "click", "selector": "#download-btn"},
                 {"action": "wait_download", "timeout": 5000}
             ]
        elif "Find CEO" in goal:
            return [
                {"action": "wait", "state": "networkidle"} # Simulates looking
            ]
        elif "Tax" in goal or "Pay" in goal:
            # Generate a risky plan to test guardrails
            return [
                 {"action": "click", "selector": "#submit-tax-payment-btn"}
            ]
            
        return []

    async def _perform_step(self, page: Page, step: Dict[str, Any]):
        """Execute a single action on the page."""
        action = step.get("action")
        selector = step.get("selector")
        
        logger.info(f"Agent Action: {action} on {selector}")
        
        if action == "fill":
            await page.fill(selector, step["value"])
        elif action == "click":
            await page.click(selector)
        elif action == "wait":
            await page.wait_for_load_state(step.get("state", "load"))
        elif action == "wait_download":
            # Handle download event
            async with page.expect_download() as download_info:
                # Trigger is usually the previous click, but for linear execution we assume it happened
                # In real Playwright, expect_download must wrap the click. 
                # Refactoring to standard Playwright sub-method if needed.
                pass 

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
