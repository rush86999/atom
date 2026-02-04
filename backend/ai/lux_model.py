"""
LUX Model Integration for Computer Use
Advanced AI model for desktop automation and computer control
"""

import asyncio
import base64
import io
import json
import logging
import os
import platform
import subprocess
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple
import anthropic
from PIL import Image, ImageGrab

try:
    import pyautogui
    PYAUTOGUI_AVAILABLE = True
except (ImportError, KeyError):
    # KeyError can happen on headless systems seeking FILE_ATTRIBUTE_REPARSE_POINT
    PYAUTOGUI_AVAILABLE = False
    pyautogui = None

from pathlib import Path
import cv2
import numpy as np

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

    def __init__(self, api_key: Optional[str] = None, governance_callback: Optional[callable] = None):
        """
        Initialize LUX model with API key
        
        Args:
            api_key: Anthropic API key
            governance_callback: Async function(action_type: str, details: dict) -> bool
                               Returns True if action is allowed, False otherwise.
        """
        self.api_key = api_key or lux_config.get_anthropic_key()
        self.governance_callback = governance_callback
        
        if not self.api_key:
            # Fallback for testing if not set
            logger.warning("ANTHROPIC_API_KEY not found in config, checking env")
            self.api_key = os.getenv("ANTHROPIC_API_KEY") or os.getenv("LUX_MODEL_API_KEY")
            
        if not self.api_key:
             logger.warning("No API KEY found for LuxModel. Some features will fail.")

        if self.api_key:
            self.client = anthropic.Anthropic(api_key=self.api_key)
        else:
            self.client = None
            
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

        # Computer use model configuration
        self.model_config = {
            "model": "claude-3-5-sonnet-20241022",
            "max_tokens": 4096,
            "temperature": 0.1
        }

        logger.info(f"LUX Model initialized for computer use")

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
        screenshot.save(buffer, format='PNG')
        return base64.b64encode(buffer.getvalue()).decode('utf-8')

    async def analyze_screen(self, screenshot: Image.Image, task: str = "Analyze the screen") -> List[ScreenElement]:
        """Analyze screen and identify interactive elements"""
        if not self.client:
            logger.error("Cannot analyze screen: No API Client")
            return []
            
        try:
            encoded_image = self.encode_screenshot(screenshot)

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

            message = {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": prompt
                    },
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": "image/png",
                            "data": encoded_image
                        }
                    }
                ]
            }

            response = self.client.messages.create(
                messages=[message],
                **self.model_config
            )

            # Parse response
            result_text = response.content[0].text
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
        if not self.client:
             # Basic fallback logic for testing without API key
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

            content_parts = [{"type": "text", "text": prompt}]

            if screenshot:
                encoded_image = self.encode_screenshot(screenshot)
                content_parts.append({
                    "type": "image",
                    "source": {
                        "type": "base64",
                        "media_type": "image/png",
                        "data": encoded_image
                    }
                })

            message = {"role": "user", "content": content_parts}

            response = self.client.messages.create(
                messages=[message],
                **self.model_config,
                timeout=30.0  # Add timeout
            )

            # Parse actions with better error handling
            result_text = response.content[0].text
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

        except anthropic.APIConnectionError as e:
            logger.error(f"API connection error: {e}")
            # Retry for connection errors
            if retry_count < 3:
                logger.info(f"Retrying due to connection error (attempt {retry_count + 1}/3)")
                await asyncio.sleep(2 ** retry_count)  # Exponential backoff
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

    async def execute_command(self, command: str) -> Dict[str, Any]:
        """Execute a natural language command"""
        try:
            start_time = datetime.now()

            # Take initial screenshot
            screenshot = await self.capture_screen()

            # Interpret command
            # Pass screenshot if we have a client, otherwise it might just return fallback
            actions = await self.interpret_command(command, screenshot)

            if not actions:
                return {
                    "success": False,
                    "error": "No actions could be interpreted from command",
                    "command": command,
                    "timestamp": start_time.isoformat()
                }

            # Execute actions
            executed_actions = []
            for i, action in enumerate(actions):
                try:
                    success = await self.execute_action(action)
                    executed_actions.append({
                        "action": action.description,
                        "success": success,
                        "confidence": action.confidence
                    })

                    # Take screenshot after action if not the last one
                    if i < len(actions) - 1 and action.action_type != ComputerActionType.SCREENSHOT:
                        screenshot = await self.capture_screen()

                except Exception as e:
                    executed_actions.append({
                        "action": action.description,
                        "success": False,
                        "error": str(e),
                        "confidence": action.confidence
                    })

            end_time = datetime.now()

            return {
                "success": True,
                "command": command,
                "actions": executed_actions,
                "execution_time": (end_time - start_time).total_seconds(),
                "timestamp": start_time.isoformat()
            }

        except Exception as e:
            logger.error(f"Command execution failed: {e}")
            return {
                "success": False,
                "error": str(e),
                "command": command,
                "timestamp": datetime.now().isoformat()
            }

# Global LUX model instance
lux_model = None

async def get_lux_model() -> LuxModel:
    """Get or create LUX model instance"""
    global lux_model
    if lux_model is None:
        lux_model = LuxModel()
    return lux_model
