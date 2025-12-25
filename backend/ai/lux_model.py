"""
LUX Model Integration for Computer Use
Advanced AI model for desktop automation and computer control
"""

import os
import json
import asyncio
import logging
import base64
import subprocess
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
import anthropic
from PIL import Image, ImageGrab
import io
import platform
import pyautogui
import cv2
import numpy as np
from pathlib import Path
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

    def __init__(self, api_key: Optional[str] = None):
        """Initialize LUX model with API key"""
        self.api_key = api_key or lux_config.get_anthropic_key()
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
            
        self.screen_width, self.screen_height = pyautogui.size()
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

    async def interpret_command(self, command: str, screenshot: Optional[Image.Image] = None) -> List[ComputerAction]:
        """Interpret natural language command into computer actions"""
        if not self.client:
             # Basic fallback logic for testing without API key
             if "calculator" in command.lower():
                 return [ComputerAction(ComputerActionType.OPEN_APP, {"app_name": "Calculator"}, 1.0, "Open Calculator")]
             return []

        try:
            content_parts = [{"type": "text", "text": f"""
You are a computer automation AI. Convert this natural language command into specific computer actions.

Command: {command}

Available actions:
- click: Click at coordinates or on element
- type: Type text at current cursor location
- keyboard: Press keyboard shortcuts
- scroll: Scroll in direction
- open_app: Open application
- screenshot: Take screenshot
- wait: Wait for specified time
- ocr: Extract text from screen region
- find_element: Locate specific element

Return as JSON:
{{
    "actions": [
        {{
            "action_type": "click",
            "parameters": {{"coordinates": [x, y], "element_id": "optional"}},
            "confidence": 0.95,
            "description": "Click on button"
        }}
    ]
}}
"""}]

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
                **self.model_config
            )

            # Parse actions
            result_text = response.content[0].text
            try:
                if "```json" in result_text:
                    json_str = result_text.split('```json')[1].split('```')[0]
                elif "```" in result_text:
                     json_str = result_text.split('```')[1].split('```')[0]
                else:
                    json_str = result_text
                    
                result_data = json.loads(json_str)
                actions = []
                for action_data in result_data.get('actions', []):
                    action_type = ComputerActionType(action_data.get('action_type', 'click'))
                    actions.append(ComputerAction(
                        action_type=action_type,
                        parameters=action_data.get('parameters', {}),
                        confidence=action_data.get('confidence', 1.0),
                        description=action_data.get('description', '')
                    ))
                return actions
            except Exception as e:
                logger.error(f"Failed to parse command: {e}")
                return []

        except Exception as e:
            logger.error(f"Command interpretation failed: {e}")
            return []

    async def execute_action(self, action: ComputerAction) -> bool:
        """Execute a computer action"""
        try:
            logger.info(f"Executing action: {action.action_type} - {action.description}")
            
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
                    subprocess.run(['start', app_name], shell=True)
                else:
                    subprocess.run([app_name])
                return True

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
