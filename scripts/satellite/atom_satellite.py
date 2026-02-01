import asyncio
import json
import os
import sys
import subprocess
import argparse
import logging
from typing import Dict, Any, Optional

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("AtomSatellite")

try:
    import websockets
except ImportError:
    print("Error: 'websockets' library is required. Install with: pip install websockets")
    sys.exit(1)

# Optional Playwright Import
try:
    from playwright.async_api import async_playwright, Playwright, Browser, BrowserContext, Page
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False
    logger.warning("Playwright not found. Browser capabilities will be disabled. Install with: pip install playwright && playwright install")

SAAS_URL = os.getenv("ATOM_SAAS_URL", "ws://localhost:5058/api/ws/satellite/connect")

class BrowserManager:
    def __init__(self):
        self.playwright: Optional[Playwright] = None
        self.browser: Optional[Browser] = None
        self.context: Optional[BrowserContext] = None
        self.page: Optional[Page] = None
        self._lock = asyncio.Lock()

    async def start(self):
        if not PLAYWRIGHT_AVAILABLE:
            raise RuntimeError("Playwright is not installed.")
        
        async with self._lock:
            if not self.playwright:
                self.playwright = await async_playwright().start()
            
            if not self.context:
                # OPTION C: Agent Identity Persistence
                # Use a dedicated profile directory for the agent's browser sessions.
                # This allows the agent to stay logged in to sites across restarts.
                profile_dir = os.path.join(os.getcwd(), ".atom_agent_profile")
                os.makedirs(profile_dir, exist_ok=True)
                
                logger.info(f"Launching persistent browser context at {profile_dir}")
                
                # launch_persistent_context returns a context, and the browser is implicit.
                self.context = await self.playwright.chromium.launch_persistent_context(
                    user_data_dir=profile_dir,
                    headless=False,
                    args=['--no-sandbox', '--disable-setuid-sandbox']
                )
                
                self.browser = self.context.browser # Note: In persistent context, browser is accessible via context
                logger.info("Persistent browser launched.")

            if not self.page:
                # If there are already pages open in the persistent context, reuse the first one
                if len(self.context.pages) > 0:
                    self.page = self.context.pages[0]
                else:
                    self.page = await self.context.new_page()

    async def perform_action(self, action: str, params: Dict[str, Any]) -> Dict[str, Any]:
        if not self.page:
            await self.start()
        
        assert self.page # check for type checker
        
        try:
            if action == "navigate":
                url = params.get("url")
                if not url: return {"error": "url required"}
                await self.page.goto(url)
                title = await self.page.title()
                return {"success": True, "title": title, "url": self.page.url}

            elif action == "screenshot":
                path = params.get("path", "screenshot.png")
                await self.page.screenshot(path=path)
                return {"success": True, "path": path}
            
            elif action == "evaluate":
                script = params.get("script")
                if not script: return {"error": "script required"}
                result = await self.page.evaluate(script)
                return {"success": True, "result": result}
            
            elif action == "click":
                selector = params.get("selector")
                if not selector: return {"error": "selector required"}
                await self.page.click(selector)
                return {"success": True}

            elif action == "type":
                selector = params.get("selector")
                text = params.get("text")
                if not selector or text is None: return {"error": "selector and text required"}
                await self.page.click(selector)
                await self.page.keyboard.type(text)
                return {"success": True}
                
            else:
                return {"error": f"Unknown browser action: {action}"}

        except Exception as e:
            logger.error(f"Browser action failed: {e}")
            return {"error": str(e)}

    async def close(self):
        if self.context: await self.context.close()
        if self.browser: await self.browser.close()
        if self.playwright: await self.playwright.stop()

class SatelliteClient:
    def __init__(self, api_key: str, allow_exec: bool = False, allow_browser: bool = False):
        self.api_key = api_key
        self.allow_exec = allow_exec
        self.allow_browser = allow_browser
        self.uri = f"{SAAS_URL}?key={self.api_key}" # Initial auth in query param
        self.browser_manager = BrowserManager() if (PLAYWRIGHT_AVAILABLE and self.allow_browser) else None

    @property
    def capabilities(self):
        caps = []
        if self.allow_exec:
            caps.append("terminal")
        if self.browser_manager:
            caps.append("browser")
        return caps

    # ... execute_tool ... (unchanged logic relying on self.capabilities/self.browser_manager)
    async def execute_tool(self, tool_name: str, args: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a tool request locally."""
        logger.info(f"Executing tool: {tool_name}")

        if tool_name == "run_terminal":
            if not "terminal" in self.capabilities:
                return {"error": "Execution denied. Start satellite with --allow-exec to enable."}
            
            command = args.get("command")
            if not command: return {"error": "No command provided"}
                
            logger.info(f"Running command: {command}")
            try:
                process = await asyncio.create_subprocess_shell(
                    command,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE
                )
                stdout, stderr = await process.communicate()
                return {
                    "stdout": stdout.decode().strip(),
                    "stderr": stderr.decode().strip(),
                    "returncode": process.returncode
                }
            except Exception as e:
                logger.error(f"Execution handling error: {e}")
                return {"error": str(e)}

        elif tool_name == "browser_action":
            if not self.browser_manager:
                return {"error": "Browser capabilities disabled or unavailable."}
            
            action = args.get("action")
            if not action: return {"error": "No action specified"}
            
            return await self.browser_manager.perform_action(action, args)
        
        return {"error": f"Unknown tool: {tool_name}"}

    async def run(self):
        """Main WebSocket loop."""
        logger.info(f"Connecting to Atom SaaS at {SAAS_URL}...")
        logger.info(f"Capabilities: {self.capabilities}")
        
        backoff = 1
        
        while True:
            try:
                async with websockets.connect(self.uri) as websocket:
                    logger.info("Connected!")
                    backoff = 1
                    
                    # 1. Send Identity / Handshake
                    handshake = {
                        "type": "identify",
                        "capabilities": self.capabilities,
                        "metadata": {
                            "hostname": os.uname().nodename,
                            "platform": sys.platform
                        }
                    }
                    await websocket.send(json.dumps(handshake))
                    logger.info("Sent identity handshake.")

                    # 2. Listen loop
                    while True:
                        message = await websocket.recv()
                        data = json.loads(message)
                        
                        if data.get("type") == "tool_call":
                            request_id = data.get("request_id")
                            tool = data.get("tool")
                            args = data.get("arguments", {})
                            
                            logger.info(f"Request {request_id}: {tool}")
                            
                            # Execute
                            result = await self.execute_tool(tool, args)
                            
                            # Respond
                            response = {
                                "type": "tool_result",
                                "request_id": request_id,
                                "result": result
                            }
                            await websocket.send(json.dumps(response))
                            logger.info("Result sent.")

            except (websockets.exceptions.ConnectionClosed, ConnectionRefusedError):
                logger.warning(f"Connection lost. Reconnecting in {backoff}s...")
                await asyncio.sleep(backoff)
                backoff = min(backoff * 2, 30)
            except Exception as e:
                logger.error(f"Unexpected error: {e}. Reconnecting in 5s...")
                await asyncio.sleep(5)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Atom Satellite - Local Node Link")
    parser.add_argument("--key", required=True, help="Your Atom API Key (sk-...)")
    parser.add_argument("--allow-exec", action="store_true", help="Allow SaaS to execute commands on this machine")
    parser.add_argument("--allow-browser", action="store_true", help="Allow SaaS to control local browser")
    
    args = parser.parse_args()
    
    client = SatelliteClient(args.key, args.allow_exec, args.allow_browser)
    
    try:
        asyncio.run(client.run())
    except KeyboardInterrupt:
        print("\nStopping Satellite...")
