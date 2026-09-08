"""
LUX Model Integration for Computer Use
Advanced AI model for desktop automation and computer control
"""

import asyncio
import base64
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
import io
import json
import logging
import os
import platform
import subprocess
from typing import Any, Dict, List, Optional, Tuple

# LLM Service Integration
try:
    from core.llm_service import LLMService
    LLM_SERVICE_AVAILABLE = True
except ImportError:
    LLM_SERVICE_AVAILABLE = False

try:
    from PIL import Image, ImageGrab
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False
    Image = None
    ImageGrab = None

try:
    import pyautogui
    PYAUTOGUI_AVAILABLE = True
except (ImportError, KeyError):
    # KeyError can happen on headless systems seeking FILE_ATTRIBUTE_REPARSE_POINT
    PYAUTOGUI_AVAILABLE = False
    pyautogui = None

from pathlib import Path
import numpy as np

# cv2 (OpenCV) is an optional dependency used only by some computer-vision
# helpers in this module. It is NOT used by any code path below (no `cv2.`
# references exist here), but importing it unconditionally breaks the whole
# chat/agent/automation import chain on systems where OpenCV isn't installed
# (chat_routes → chat_orchestrator → agent_service → lux_model → cv2).
# Guard it like the PIL/pyautogui optional imports above.
try:
    import cv2
    CV2_AVAILABLE = True
except (ImportError, KeyError):
    CV2_AVAILABLE = False
    cv2 = None

from core.lux_config import lux_config

logger = logging.getLogger(__name__)

class ComputerActionType(Enum):
    """Types of computer actions LUX can perform"""
    CLICK = "click"
    TYPE = "type"
    SCROLL = "scroll"
    DRAG = "drag"
    KEYBOARD = "keyboard"
    SCREENSHOT = "screenshot"
    SEARCH = "search"
    OPEN_APP = "open_app"
    CLOSE_APP = "close_app"
    WAIT = "wait"
    OCR = "ocr"
    FIND_ELEMENT = "find_element"

@dataclass
class ComputerAction:
    """Represents a computer action"""
    action_type: ComputerActionType
    parameters: Dict[str, Any]
    confidence: float = 1.0
    description: str = ""

@dataclass
class ScreenElement:
    """Represents an element found on screen"""
    element_id: str
    bbox: Tuple[int, int, int, int]  # x, y, width, height
    text: Optional[str] = None
    description: str = ""
    confidence: float = 1.0

class LuxModel:
    """LUX Model for Computer Use and Desktop Automation"""

    def __init__(self, tenant_id: str = "default", governance_callback: Optional[callable] = None):
        """
        Initialize LUX model
        
        Args:
            tenant_id: Tenant ID for metered AI operations
            governance_callback: Async function(action_type: str, details: dict) -> bool
                                Returns True if action is allowed, False otherwise.
        """
        self.tenant_id = tenant_id
        self.governance_callback = governance_callback
        
        # Use unified LLMService for all AI interactions
        self.llm_service = None
        if LLM_SERVICE_AVAILABLE:
            self.llm_service = LLMService(tenant_id=tenant_id)
            logger.info(f"LuxModel initialized with LLMService for tenant: {tenant_id}")
            
        if PYAUTOGUI_AVAILABLE:
            try:
                self.screen_width, self.screen_height = pyautogui.size()
            except Exception:
                self.screen_width, self.screen_height = 1920, 1080 # Fallback
                logger.warning("Could not get screen size, defaulting to 1080p")
        else:
            self.screen_width, self.screen_height = 1920, 1080
            logger.warning("PyAutoGUI not available. Computer Use features will be disabled.")

        self.screenshot_cache = {}

        # Computer use model configuration. Model is an EXPLICIT pick routed
        # through LLMService/BPC: the frontier-reserved gate leaves named
        # picks alone, and provider fallback still applies when the
        # configured model's provider has no key (the ranked list stays
        # available behind the pin). Default: gpt-6-astra (see lux_config).
        self.model_config = {
            "model": lux_config.get_computer_use_model(),
            "max_tokens": 4096,
            "temperature": 0.1
        }

        logger.info(
            f"LUX Model initialized for computer use "
            f"(model={self.model_config['model']})"
        )

    async def capture_screen(self, region: Optional[Tuple[int, int, int, int]] = None) -> Image.Image:
        """Capture screen screenshot with optional region"""
        try:
            if region:
                x, y, width, height = region
                screenshot = pyautogui.screenshot(region=(x, y, width, height))
            else:
                screenshot = pyautogui.screenshot()

            # Convert to RGB for consistency
            if screenshot.mode != 'RGB':
                screenshot = screenshot.convert('RGB')

            return screenshot
        except Exception as e:
            logger.error(f"Failed to capture screen: {e}")
            raise

    def encode_screenshot(self, screenshot: Image.Image) -> str:
        """Encode screenshot to base64 for API"""
        buffer = io.BytesIO()
        screenshot.save(buffer, format="PNG")
        return base64.b64encode(buffer.getvalue()).decode('utf-8')

    def encode_screenshot_for_model(self, screenshot: Image.Image, max_edge: int = 1568) -> str:
        """Encode a screenshot as downscaled JPEG, raw base64 (no data: prefix).

        Token/cost control for the computer-use loop: a full-res PNG of a
        retina desktop is multiple MB — at gpt-6-astra's $10/M input that
        dominates the cost of every step. Resizing so the longest edge is
        <= ~1568px (and re-encoding as quality-85 JPEG) keeps per-step
        vision tokens roughly an order of magnitude lower with no measured
        accuracy loss for UI-element targeting; Anthropic's computer-use
        guidance recommends capping screenshot edges (~2000px) for exactly
        this reason. The routing layer wraps raw base64 in the
        data:image/jpeg URL itself.
        """
        img = screenshot
        if img.mode != "RGB":
            img = img.convert("RGB")
        if max(img.size) > max_edge:
            img.thumbnail((max_edge, max_edge), Image.LANCZOS)
        buffer = io.BytesIO()
        img.save(buffer, format="JPEG", quality=85)
        return base64.b64encode(buffer.getvalue()).decode("utf-8")

    async def analyze_screen(self, screenshot: Image.Image, task: str = "Analyze the screen") -> List[ScreenElement]:
        """Analyze screen and identify interactive elements"""
        if not self.llm_service:
            logger.error("Cannot analyze screen: LLMService not available")
            return []
            
        try:
            encoded_image = self.encode_screenshot_for_model(screenshot)

            prompt = f"""You are a computer vision AI that analyzes screenshots and identifies interactive elements.
            Analyze this screenshot and identify:
            1. Buttons, links, text fields, and other interactive elements
            2. Their approximate bounding boxes (x, y, width, height)
            3. Any visible text labels
            4. Descriptions of what each element does

            Task: {task}

            Return results as JSON with this format:
            {{
                "elements": [
                    {{
                        "id": "element_1",
                        "bbox": [x, y, width, height],
                        "text": "visible text or null",
                        "description": "what this element is",
                        "confidence": 0.95
                    }}
                ]
            }}

            Use the full screen resolution {self.screen_width}x{self.screen_height} for coordinates."""

            message = {"role": "user", "content": prompt}

            response_data = await self.llm_service.generate_completion(
                messages=[message],
                model=self.model_config["model"],
                tenant_id=self.tenant_id,
                task_type="computer_use",
                image_payload=encoded_image,
                **{k: v for k, v in self.model_config.items() if k != "model"}
            )

            if not response_data.get("success"):
                logger.error(f"Screen analysis failed: {response_data.get('error')}")
                return []

            # Parse response
            result_text = response_data.get("content", "")
            try:
                # Extract JSON from potential markdown blocks
                if "```json" in result_text:
                    json_str = result_text.split('```json')[1].split('```')[0]
                elif "```" in result_text:
                     json_str = result_text.split('```')[1].split('```')[0]
                else:
                    json_str = result_text
                    
                result_data = json.loads(json_str)
                elements = []
                for elem in result_data.get('elements', []):
                    elements.append(ScreenElement(
                        element_id=elem.get('id', ''),
                        bbox=tuple(elem.get('bbox', [0, 0, 0, 0])),
                        text=elem.get('text'),
                        description=elem.get('description', ''),
                        confidence=elem.get('confidence', 1.0)
                    ))
                return elements
            except Exception as e:
                logger.error(f"Failed to parse screen analysis: {e}")
                return []

        except Exception as e:
            logger.error(f"Screen analysis failed: {e}")
            return []

    async def interpret_command(self, command: str, screenshot: Optional[Image.Image] = None, retry_count: int = 0) -> List[ComputerAction]:
        """
        Interpret natural language command into computer actions with enhanced prompting and retry logic.

        Args:
            command: Natural language command to execute
            screenshot: Optional screenshot for visual context
            retry_count: Current retry attempt (for internal use)

        Returns:
            List of ComputerAction objects
        """
        if not self.llm_service:
             # Basic fallback logic for testing without LLM service
             if "calculator" in command.lower():
                 return [ComputerAction(ComputerActionType.OPEN_APP, {"app_name": "Calculator"}, 1.0, "Open Calculator")]
             return []

        try:
            # Enhanced prompt with better instructions
            prompt = f"""You are an advanced computer automation AI with visual understanding capabilities.
Your task is to convert natural language commands into precise, executable computer actions.

COMMAND: {command}

AVAILABLE ACTIONS:
1. click - Click at coordinates (x, y) or on element
2. type - Type text at current cursor location or into a field
3. keyboard - Press keyboard shortcuts (e.g., ["cmd", "c"] for copy)
4. scroll - Scroll in direction ("up", "down", "left", "right")
5. drag - Drag from coordinates to coordinates
6. wait - Wait for specified time (seconds)
7. ocr - Extract text from screen region
8. find_element - Locate specific UI element

ACTION GENERATION RULES:
- Break complex commands into multiple simple actions
- Use specific coordinates when UI elements are visible
- Include reasonable waiting for UI responses
- Add descriptions for each action explaining what it does
- Set confidence scores (0.0 to 1.0) based on certainty
- Use coordinates: [x, y] format (0,0 is top-left)
- For typing, always focus element first (click) then type

RESPONSE FORMAT (JSON only):
{{
    "actions": [
        {{
            "action_type": "click",
            "parameters": {{"coordinates": [x, y], "selector": "#optional-css-selector"}},
            "confidence": 0.95,
            "description": "Click on the login button"
        }}
    ],
    "reasoning": "Brief explanation of the action plan"
}}

IMPORTANT:
- Return ONLY valid JSON, no markdown formatting
- Be specific with coordinates based on what you see
- If screenshot provided, use visual information to locate elements
- If unsure, set confidence lower and describe what you see"""

            # Screenshot goes through `image_payload` (the routing layer's
            # vision contract) rather than an embedded content part: embedded
            # parts were invisible to vision routing and could land the turn
            # on a vision-blind model.
            image_kwargs = {}
            if screenshot:
                image_kwargs["image_payload"] = self.encode_screenshot_for_model(screenshot)

            message = {"role": "user", "content": prompt}

            response_data = await self.llm_service.generate_completion(
                messages=[message],
                tenant_id=self.tenant_id,
                task_type="computer_use",
                **image_kwargs,
                **self.model_config
            )

            if not response_data.get("success"):
                logger.error(f"Command interpretation failed: {response_data.get('error')}")
                return []

            # Parse actions with better error handling
            result_text = response_data.get("content", "")
            logger.debug(f"Lux response: {result_text[:200]}...")  # Log first 200 chars

            try:
                # Try multiple parsing strategies
                json_str = None

                # Strategy 1: Extract from markdown code blocks
                if "```json" in result_text:
                    json_str = result_text.split('```json')[1].split('```')[0].strip()
                elif "```" in result_text:
                    json_str = result_text.split('```')[1].split('```')[0].strip()
                else:
                    # Strategy 2: Try to parse entire response as JSON
                    json_str = result_text.strip()

                # Remove any non-JSON content before/after
                json_str = json_str.strip()
                if json_str.startswith('{'):
                    result_data = json.loads(json_str)

                    actions = []
                    for action_data in result_data.get('actions', []):
                        try:
                            action_type_str = action_data.get('action_type', 'click')
                            action_type = ComputerActionType(action_type_str)
                            actions.append(ComputerAction(
                                action_type=action_type,
                                parameters=action_data.get('parameters', {}),
                                confidence=action_data.get('confidence', 1.0),
                                description=action_data.get('description', '')
                            ))
                        except ValueError as e:
                            logger.warning(f"Unknown action type '{action_type_str}': {e}")
                            continue

                    logger.info(f"Successfully parsed {len(actions)} actions from Lux response")
                    return actions
                else:
                    logger.error("Response does not appear to be JSON")
                    return []

            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse JSON from Lux response: {e}")
                logger.debug(f"Problematic response: {result_text}")

                # Retry logic for parsing failures
                if retry_count < 2:
                    logger.info(f"Retrying command interpretation (attempt {retry_count + 1}/2)")
                    await asyncio.sleep(1)  # Brief wait before retry
                    return await self.interpret_command(command, screenshot, retry_count + 1)

                return []

        except Exception as e:
            logger.error(f"Command interpretation failed: {e}")
            return []

    async def execute_action(self, action: ComputerAction) -> bool:
        """Execute a computer action"""
        try:
            logger.info(f"Executing action: {action.action_type} - {action.description}")
            
            # Governance Check
            if self.governance_callback:
                allowed = await self.governance_callback(
                    action_type=action.action_type.value,
                    details=action.parameters
                )
                if not allowed:
                    logger.warning(f"Action blocked by governance: {action.action_type}")
                    return False
            
            if action.action_type == ComputerActionType.CLICK:
                params = action.parameters
                if 'coordinates' in params:
                    x, y = params['coordinates']
                    # Clamp model-emitted coordinates to the live screen
                    # bounds — a hallucinated off-screen click hits nothing
                    # (or the wrong monitor on multi-display setups).
                    x = max(0, min(int(x), max(0, self.screen_width - 1)))
                    y = max(0, min(int(y), max(0, self.screen_height - 1)))
                    pyautogui.click(x, y)
                elif 'element_id' in params:
                    # Would find element by ID and click it
                    pass
                return True

            elif action.action_type == ComputerActionType.TYPE:
                text = action.parameters.get('text', '')
                pyautogui.typewrite(text)
                return True

            elif action.action_type == ComputerActionType.KEYBOARD:
                keys = action.parameters.get('keys', [])
                pyautogui.hotkey(*keys)
                return True

            elif action.action_type == ComputerActionType.SCROLL:
                direction = action.parameters.get('direction', 'down')
                amount = action.parameters.get('amount', 5)
                if direction == 'down':
                    pyautogui.scroll(-amount)
                else:
                    pyautogui.scroll(amount)
                return True

            elif action.action_type == ComputerActionType.OPEN_APP:
                app_name = action.parameters.get('app_name', '')
                if platform.system() == "Darwin":
                     # Use specialized open command for Mac
                    try:
                        subprocess.run(['open', '-a', app_name], check=True)
                    except subprocess.CalledProcessError:
                         # Fallback for some apps or if full path needed
                         subprocess.run(['open', app_name], check=False)
                elif platform.system() == "Windows":
                    os.startfile("calc")
                else:
                    try:
                        os.startfile(app_name)
                        return True
                    except Exception as e:
                        logger.error(f"Failed to open app {app_name}: {e}")
                        return False

            elif action.action_type == ComputerActionType.WAIT:
                duration = action.parameters.get('duration', 1.0)
                await asyncio.sleep(duration)
                return True

            elif action.action_type == ComputerActionType.SCREENSHOT:
                # Screenshot already handled by caller
                return True

        except Exception as e:
            logger.error(f"Failed to execute action {action.action_type}: {e}")
            return False
        return True

    @staticmethod
    def _extract_json(text: str) -> Optional[Dict[str, Any]]:
        """Best-effort JSON extraction from a model response.

        Tries markdown-fenced blocks first, then the whole text. Returns
        None when nothing JSON-shaped is found.
        """
        json_str = None
        if "```json" in text:
            json_str = text.split('```json')[1].split('```')[0].strip()
        elif "```" in text:
            json_str = text.split('```')[1].split('```')[0].strip()
        else:
            json_str = text.strip()
        # Trim to the outermost braces — reasoning models prepend prose.
        _start = json_str.find('{')
        _end = json_str.rfind('}')
        if _start == -1 or _end <= _start:
            return None
        try:
            parsed = json.loads(json_str[_start:_end + 1])
            return parsed if isinstance(parsed, dict) else None
        except json.JSONDecodeError:
            return None

    async def decide_next_action(
        self,
        command: str,
        screenshot: Optional[Image.Image] = None,
        history: Optional[List[str]] = None,
    ) -> Optional[Dict[str, Any]]:
        """One decide step of the computer-use loop.

        Returns a decision dict:
            {"done": bool, "action": Optional[ComputerAction],
             "reasoning": str, "summary": str}
        or None when the model call/parse failed.

        One action per observation is deliberate: mature computer-use
        harnesses (Anthropic's computer-use tool, OpenAI's CUA) all
        re-observe the screen after every action instead of executing a
        blind multi-action plan — desktop state changes under you, and a
        plan built on a stale screenshot misfires.
        """
        if not self.llm_service:
            # Compat fallback for key-less dev runs (interpret_command keeps
            # its calculator demo path).
            if "calculator" in command.lower():
                return {
                    "done": False,
                    "action": ComputerAction(
                        ComputerActionType.OPEN_APP, {"app_name": "Calculator"}, 1.0,
                        "Open Calculator"),
                    "reasoning": "fallback", "summary": "",
                }
            return None

        history = history or []
        history_block = "\n".join(history[-8:]) or "(none yet — this is the first step)"

        system_prompt = (
            "You are a computer-use agent controlling a real desktop through "
            "one action per step. After each action you will receive a fresh "
            "screenshot. Respond with EXACTLY ONE JSON object and nothing else:\n"
            '{"reasoning": "why this action", "action": {"action_type": "...", '
            '"parameters": {...}, "confidence": 0.0-1.0}, "done": false, '
            '"summary": "final answer once done"}\n'
            "Set done=true (with summary) when the task is complete or clearly "
            "impossible. Action types: click (parameters.coordinates [x,y]), "
            "type (parameters.text — click the field first), keyboard "
            "(parameters.keys e.g. [\"cmd\",\"c\"]), scroll (parameters.direction "
            "up/down, parameters.amount), drag (parameters.from [x,y], "
            "parameters.to [x,y]), open_app (parameters.app_name), wait "
            "(parameters.duration seconds), screenshot, ocr, find_element.\n"
            f"Coordinates are in pixels on a {self.screen_width}x{self.screen_height} "
            "screen, (0,0) top-left. Stay strictly inside those bounds."
        )

        user_prompt = (
            f"TASK: {command}\n\n"
            f"ACTIONS TAKEN SO FAR:\n{history_block}\n\n"
            "The attached screenshot is the CURRENT screen state. Decide the "
            "single next action (or done)."
        )

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]

        image_kwargs = {}
        if screenshot is not None:
            image_kwargs["image_payload"] = self.encode_screenshot_for_model(screenshot)

        response_data = await self.llm_service.generate_completion(
            messages=messages,
            model=self.model_config["model"],
            tenant_id=self.tenant_id,
            task_type="computer_use",
            **image_kwargs,
            **{k: v for k, v in self.model_config.items() if k != "model"}
        )

        if not response_data.get("success"):
            logger.error(f"Computer-use step failed: {response_data.get('error')}")
            return None

        result_text = response_data.get("content", "") or ""
        data = self._extract_json(result_text)
        if data is None:
            logger.error("Computer-use step returned no parseable JSON")
            return None

        done = bool(data.get("done"))
        action = None
        action_data = data.get("action") or {}
        action_type_str = str(action_data.get("action_type", "") or "").lower()
        if not done and action_type_str and action_type_str != "done":
            try:
                action = ComputerAction(
                    ComputerActionType(action_type_str),
                    action_data.get("parameters", {}) or {},
                    float(action_data.get("confidence", 1.0)),
                    action_data.get("description", "") or action_type_str,
                )
            except ValueError as e:
                # Unknown action type: treat the step as failed (None) so the
                # loop's failure handling re-plans from a fresh screenshot.
                logger.warning(f"Unknown action type '{action_type_str}': {e}")
                return None
        elif action_type_str == "done":
            done = True

        return {
            "done": done,
            "action": action,
            "reasoning": data.get("reasoning", ""),
            "summary": data.get("summary", ""),
        }

    async def run_task(
        self,
        command: str,
        max_steps: Optional[int] = None,
        step_settle_seconds: float = 1.0,
    ) -> Dict[str, Any]:
        """Agentic computer-use loop: observe -> decide -> act -> re-observe.

        Grounded in established harness practice (Anthropic computer-use
        tool docs / agentic-loop engineering guidance): a simple while-loop
        alternating one model decision and one executed action, a fresh
        screenshot every step, a hard step budget, and per-action governance.

        Safety rails:
        - max_steps (default from lux_config, env ATOM_COMPUTER_USE_MAX_STEPS)
          bounds the loop even when the model never says done.
        - governance_callback (when provided) is a HARD stop — one blocked
          action aborts the task; it is policy, not a retryable failure.
        - Three consecutive failed actions abort (persistent misfires mean
          the model is lost; more steps just move the user's desktop
          around).
        - Coordinates are clamped to screen bounds in execute_action.
        """
        start_time = datetime.now()
        steps_limit = max_steps if max_steps is not None else lux_config.get_max_steps()

        if not PYAUTOGUI_AVAILABLE:
            return {
                "success": False,
                "error": "PyAutoGUI not available — computer use is disabled on this host",
                "command": command,
                "timestamp": start_time.isoformat(),
            }

        executed_actions: List[Dict[str, Any]] = []
        history: List[str] = []
        final_summary = ""
        task_done = False
        consecutive_failures = 0

        try:
            for step in range(steps_limit):
                screenshot = await self.capture_screen()
                decision = await self.decide_next_action(command, screenshot, history)

                if decision is None:
                    if not executed_actions:
                        return {
                            "success": False,
                            "error": "No action could be interpreted from command",
                            "command": command,
                            "timestamp": start_time.isoformat(),
                        }
                    logger.warning("Computer-use step unparseable — stopping task")
                    break

                if decision.get("done"):
                    task_done = True
                    final_summary = decision.get("summary") or decision.get("reasoning") or ""
                    break

                action: ComputerAction = decision["action"]
                if action is None:
                    # Model said not-done but emitted no action — count as a
                    # failed step and let the loop re-plan.
                    consecutive_failures += 1
                    if consecutive_failures >= 3:
                        break
                    continue

                # Governance is a hard stop, not a retryable failure.
                if self.governance_callback:
                    allowed = await self.governance_callback(
                        action_type=action.action_type.value,
                        details=action.parameters,
                    )
                    if not allowed:
                        logger.warning(
                            f"Computer-use task aborted by governance at step "
                            f"{step + 1}: {action.action_type.value}"
                        )
                        executed_actions.append({
                            "step": step + 1,
                            "action": action.description or action.action_type.value,
                            "success": False,
                            "blocked_by_governance": True,
                            "confidence": action.confidence,
                        })
                        return {
                            "success": False,
                            "error": "Task blocked by governance policy",
                            "command": command,
                            "actions": executed_actions,
                            "steps": len(executed_actions),
                            "done": False,
                            "execution_time": (datetime.now() - start_time).total_seconds(),
                            "timestamp": start_time.isoformat(),
                        }

                try:
                    success = await self.execute_action(action)
                except Exception as e:
                    logger.error(f"Action execution raised: {e}")
                    success = False

                executed_actions.append({
                    "step": step + 1,
                    "action": action.description or action.action_type.value,
                    "action_type": action.action_type.value,
                    "success": success,
                    "confidence": action.confidence,
                })
                history.append(
                    f"{step + 1}. {action.action_type.value}("
                    f"{json.dumps(action.parameters, default=str)}) -> "
                    f"{'ok' if success else 'FAILED'}"
                )

                if success:
                    consecutive_failures = 0
                else:
                    consecutive_failures += 1
                    if consecutive_failures >= 3:
                        logger.warning("Three consecutive failed actions — aborting task")
                        break

                # Let the UI settle before the next observation so the fresh
                # screenshot reflects the action's effect.
                await asyncio.sleep(step_settle_seconds)

            return {
                "success": any(a.get("success") for a in executed_actions),
                "command": command,
                "actions": executed_actions,
                "steps": len(executed_actions),
                "done": task_done,
                "summary": final_summary,
                "execution_time": (datetime.now() - start_time).total_seconds(),
                "timestamp": start_time.isoformat(),
            }

        except Exception as e:
            logger.error(f"Computer-use task failed: {e}")
            return {
                "success": False,
                "error": str(e),
                "command": command,
                "actions": executed_actions,
                "steps": len(executed_actions),
                "done": False,
                "execution_time": (datetime.now() - start_time).total_seconds(),
                "timestamp": start_time.isoformat(),
            }

    async def execute_command(self, command: str) -> Dict[str, Any]:
        """Execute a natural language command via the agentic computer-use loop.

        Kept as the public entry point for existing callers (agent_service,
        browser_engine); it now re-observes the screen between actions
        instead of executing a blind one-shot plan.
        """
        return await self.run_task(command)

# Global LUX model instance
lux_model = None

async def get_lux_model(tenant_id: str = "default") -> LuxModel:
    """Get or create LUX model instance"""
    global lux_model
    if lux_model is None or lux_model.tenant_id != tenant_id:
        lux_model = LuxModel(tenant_id=tenant_id)
    return lux_model
