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
from enum import Enum, auto
import anthropic
from PIL import Image, ImageGrab
import io
import platform
import pyautogui
import cv2
import numpy as np
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
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
    action_type: 'ComputerActionType'
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
            raise ValueError("ANTHROPIC_API_KEY is required for LUX model")

        self.client = anthropic.Anthropic(api_key=self.api_key)
        self.screen_width, self.screen_height = pyautogui.size()

        # Fix: Implement bounded screenshot cache to prevent memory leaks
        self.screenshot_cache = {}
        self.max_cache_size = 10

        # Thread pool for blocking operations
        self.thread_pool = ThreadPoolExecutor(max_workers=4)

        # Computer use model configuration
        self.model_config = {
            "model": "claude-3-5-sonnet-20241022",
            "max_tokens": 4096,
            "temperature": 0.1
        }

        logger.info(f"LUX Model initialized for computer use with API key: {self.api_key[:10]}...")

    def _capture_screen_sync(self, region: Optional[Tuple[int, int, int, int]] = None) -> Image.Image:
        """Synchronous screenshot capture for thread pool"""
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

  async def capture_screen(self, region: Optional[Tuple[int, int, int, int]] = None) -> Image.Image:
        """Capture screen screenshot with optional region (non-blocking)"""
        try:
            # Fix: Run blocking screenshot operation in thread pool
            loop = asyncio.get_event_loop()
            screenshot = await loop.run_in_executor(
                self.thread_pool,
                self._capture_screen_sync,
                region
            )

            # Fix: Implement cache management to prevent memory leaks
            cache_key = str(region) if region else "full_screen"
            self.screenshot_cache[cache_key] = screenshot

            # Remove oldest entries if cache exceeds limit
            if len(self.screenshot_cache) > self.max_cache_size:
                oldest_key = next(iter(self.screenshot_cache))
                del self.screenshot_cache[oldest_key]

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
                result_data = json.loads(result_text.split('```json')[1].split('```')[0])
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
                result_data = json.loads(result_text.split('```json')[1].split('```')[0])
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

    def _execute_click_sync(self, x: int, y: int) -> None:
        """Synchronous click operation"""
        pyautogui.click(x, y)

    def _execute_type_sync(self, text: str) -> None:
        """Synchronous type operation"""
        pyautogui.typewrite(text)

    def _execute_keyboard_sync(self, keys: List[str]) -> None:
        """Synchronous keyboard operation"""
        pyautogui.hotkey(*keys)

    def _execute_scroll_sync(self, direction: str, amount: int) -> None:
        """Synchronous scroll operation"""
        if direction == 'down':
            pyautogui.scroll(-amount)
        else:
            pyautogui.scroll(amount)

    def _execute_open_app_sync(self, app_name: str) -> None:
        """Synchronous app opening operation"""
        if platform.system() == "Darwin":
            subprocess.run(['open', '-a', app_name])
        elif platform.system() == "Windows":
            subprocess.run(['start', app_name], shell=True)
        else:
            subprocess.run([app_name])

    async def execute_action(self, action: ComputerAction) -> bool:
        """Execute a computer action"""
        try:
            loop = asyncio.get_event_loop()

            if action.action_type == ComputerActionType.CLICK:
                params = action.parameters
                if 'coordinates' in params:
                    x, y = params['coordinates']
                    # Fix: Run blocking pyautogui operations in thread pool
                    await loop.run_in_executor(
                        self.thread_pool,
                        self._execute_click_sync,
                        x, y
                    )
                elif 'element_id' in params:
                    # Would find element by ID and click it
                    pass
                return True

            elif action.action_type == ComputerActionType.TYPE:
                text = action.parameters.get('text', '')
                # Fix: Run blocking pyautogui operations in thread pool
                await loop.run_in_executor(
                    self.thread_pool,
                    self._execute_type_sync,
                    text
                )
                return True

            elif action.action_type == ComputerActionType.KEYBOARD:
                keys = action.parameters.get('keys', [])
                # Fix: Run blocking pyautogui operations in thread pool
                await loop.run_in_executor(
                    self.thread_pool,
                    self._execute_keyboard_sync,
                    keys
                )
                return True

            elif action.action_type == ComputerActionType.SCROLL:
                direction = action.parameters.get('direction', 'down')
                amount = action.parameters.get('amount', 5)
                # Fix: Run blocking pyautogui operations in thread pool
                await loop.run_in_executor(
                    self.thread_pool,
                    self._execute_scroll_sync,
                    direction, amount
                )
                return True

            elif action.action_type == ComputerActionType.OPEN_APP:
                app_name = action.parameters.get('app_name', '')
                # Fix: Run blocking subprocess operations in thread pool
                await loop.run_in_executor(
                    self.thread_pool,
                    self._execute_open_app_sync,
                    app_name
                )
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

    async def execute_command(self, command: str) -> Dict[str, Any]:
        """Execute a natural language command"""
        try:
            start_time = datetime.now()

            # Take initial screenshot
            screenshot = await self.capture_screen()

            # Interpret command
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

    async def get_screen_info(self) -> Dict[str, Any]:
        """Get current screen information"""
        try:
            screenshot = await self.capture_screen()
            elements = await self.analyze_screen(screenshot)

            return {
                "screen_resolution": {
                    "width": self.screen_width,
                    "height": self.screen_height
                },
                "elements_found": len(elements),
                "elements": [
                    {
                        "id": elem.element_id,
                        "bbox": elem.bbox,
                        "text": elem.text,
                        "description": elem.description,
                        "confidence": elem.confidence
                    }
                    for elem in elements
                ],
                "timestamp": datetime.now().isoformat()
            }
        except Exception as e:
            logger.error(f"Failed to get screen info: {e}")
            return {"error": str(e)}

# Global LUX model instance
lux_model = None

async def cleanup_lux_model():
        """Cleanup global LUX model instance"""
        global lux_model
        if lux_model is not None:
            lux_model.cleanup()
            lux_model = None
            logger.info("Global LUX Model instance cleaned up")

    async def get_lux_model() -> LuxModel:
        """Get or create LUX model instance"""
        global lux_model
        if lux_model is None:
            lux_model = LuxModel()
        return lux_model