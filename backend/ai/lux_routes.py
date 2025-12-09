"""
LUX Model API Routes
Computer Use and Desktop Automation endpoints
"""

import logging
from typing import Dict, List, Optional, Any
from fastapi import APIRouter, HTTPException, BackgroundTasks
from pydantic import BaseModel
from ai.lux_model import LuxModel, get_lux_model
import asyncio
import os
from datetime import datetime

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/atom/lux", tags=["LUX Computer Use"])

class CommandRequest(BaseModel):
    command: str
    context: Optional[str] = None
    take_screenshot_after: bool = False

class CommandResponse(BaseModel):
    success: bool
    command: str
    actions: List[Dict[str, Any]]
    execution_time: float
    timestamp: str
    screenshot_data: Optional[str] = None
    error: Optional[str] = None

class ScreenInfoResponse(BaseModel):
    screen_resolution: Dict[str, int]
    elements_found: int
    elements: List[Dict[str, Any]]
    timestamp: str

class BatchCommandRequest(BaseModel):
    commands: List[str]
    delay_between_commands: float = 1.0
    stop_on_error: bool = False

class AutomationTemplate(BaseModel):
    name: str
    description: str
    commands: List[str]
    parameters: Dict[str, Any] = {}

class AutomationTemplateResponse(BaseModel):
    success: bool
    template_id: str
    template: Optional[AutomationTemplate] = None
    error: Optional[str] = None

# In-memory storage for automation templates (in production, use database)
automation_templates = {
    "open_slack": {
        "name": "Open Slack",
        "description": "Opens Slack application",
        "commands": ["open Slack app"],
        "parameters": {}
    },
    "check_email": {
        "name": "Check Email",
        "description": "Opens Gmail and checks for new emails",
        "commands": [
            "open Chrome",
            "type gmail.com and press Enter",
            "wait 2 seconds",
            "take screenshot"
        ],
        "parameters": {}
    },
    "create_document": {
        "name": "Create Document",
        "description": "Opens Pages/Word and creates new document",
        "commands": [
            "open Pages app",
            "wait 1 second",
            "type 'New Document'",
            "save document as 'Untitled'"
        ],
        "parameters": {
            "document_name": "Untitled",
            "app": "Pages"
        }
    }
}

@router.post("/command", response_model=CommandResponse)
async def execute_command(request: CommandRequest):
    """
    Execute a natural language command using LUX model
    """
    try:
        lux = await get_lux_model()

        # Execute the command
        result = await lux.execute_command(request.command)

        # Take screenshot after execution if requested
        screenshot_data = None
        if request.take_screenshot_after and result.get("success"):
            try:
                screenshot = await lux.capture_screen()
                import base64
                from io import BytesIO

                buffer = BytesIO()
                screenshot.save(buffer, format='PNG')
                screenshot_data = base64.b64encode(buffer.getvalue()).decode('utf-8')
            except Exception as e:
                logger.error(f"Failed to take post-execution screenshot: {e}")

        return CommandResponse(
            success=result.get("success", False),
            command=request.command,
            actions=result.get("actions", []),
            execution_time=result.get("execution_time", 0.0),
            timestamp=result.get("timestamp", datetime.now().isoformat()),
            screenshot_data=screenshot_data,
            error=result.get("error")
        )

    except Exception as e:
        logger.error(f"Command execution failed: {e}")
        raise HTTPException(status_code=500, detail=f"Command execution failed: {str(e)}")

@router.post("/batch-command", response_model=List[CommandResponse])
async def execute_batch_commands(request: BatchCommandRequest):
    """
    Execute multiple commands in sequence
    """
    try:
        lux = await get_lux_model()
        results = []

        for command in request.commands:
            try:
                result = await lux.execute_command(command)
                results.append(CommandResponse(
                    success=result.get("success", False),
                    command=command,
                    actions=result.get("actions", []),
                    execution_time=result.get("execution_time", 0.0),
                    timestamp=result.get("timestamp", datetime.now().isoformat()),
                    error=result.get("error")
                ))

                # Stop on error if configured
                if not result.get("success") and request.stop_on_error:
                    break

                # Delay between commands
                if command != request.commands[-1]:
                    await asyncio.sleep(request.delay_between_commands)

            except Exception as e:
                results.append(CommandResponse(
                    success=False,
                    command=command,
                    actions=[],
                    execution_time=0.0,
                    timestamp=datetime.now().isoformat(),
                    error=str(e)
                ))

                if request.stop_on_error:
                    break

        return results

    except Exception as e:
        logger.error(f"Batch command execution failed: {e}")
        raise HTTPException(status_code=500, detail=f"Batch execution failed: {str(e)}")

@router.get("/screen", response_model=ScreenInfoResponse)
async def get_screen_info():
    """
    Analyze current screen and identify interactive elements
    """
    try:
        lux = await get_lux_model()
        info = await lux.get_screen_info()

        if "error" in info:
            raise HTTPException(status_code=500, detail=info["error"])

        return ScreenInfoResponse(**info)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Screen analysis failed: {e}")
        raise HTTPException(status_code=500, detail=f"Screen analysis failed: {str(e)}")

@router.post("/screenshot")
async def take_screenshot():
    """
    Take a screenshot and return base64 encoded image
    """
    try:
        lux = await get_lux_model()
        screenshot = await lux.capture_screen()

        import base64
        from io import BytesIO

        buffer = BytesIO()
        screenshot.save(buffer, format='PNG')
        image_data = base64.b64encode(buffer.getvalue()).decode('utf-8')

        return {
            "success": True,
            "image_data": image_data,
            "timestamp": datetime.now().isoformat(),
            "resolution": {
                "width": lux.screen_width,
                "height": lux.screen_height
            }
        }

    except Exception as e:
        logger.error(f"Screenshot failed: {e}")
        raise HTTPException(status_code=500, detail=f"Screenshot failed: {str(e)}")

@router.get("/templates")
async def get_automation_templates():
    """
    Get available automation templates
    """
    try:
        return {
            "success": True,
            "templates": automation_templates,
            "count": len(automation_templates)
        }
    except Exception as e:
        logger.error(f"Failed to get templates: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get templates: {str(e)}")

@router.post("/templates/{template_id}")
async def execute_template(template_id: str, parameters: Optional[Dict[str, Any]] = None):
    """
    Execute an automation template
    """
    try:
        if template_id not in automation_templates:
            raise HTTPException(status_code=404, detail=f"Template '{template_id}' not found")

        template = automation_templates[template_id]
        commands = template["commands"]

        # Apply parameters to commands (simple string replacement)
        if parameters:
            for param, value in parameters.items():
                commands = [cmd.replace(f"{{{param}}}", str(value)) for cmd in commands]

        lux = await get_lux_model()
        results = []

        for command in commands:
            try:
                result = await lux.execute_command(command)
                results.append({
                    "command": command,
                    "success": result.get("success", False),
                    "actions": result.get("actions", []),
                    "error": result.get("error")
                })
            except Exception as e:
                results.append({
                    "command": command,
                    "success": False,
                    "actions": [],
                    "error": str(e)
                })

        return {
            "success": True,
            "template_name": template["name"],
            "template_id": template_id,
            "results": results,
            "total_commands": len(commands),
            "successful_commands": sum(1 for r in results if r["success"])
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Template execution failed: {e}")
        raise HTTPException(status_code=500, detail=f"Template execution failed: {str(e)}")

@router.post("/templates")
async def create_template(template: AutomationTemplate):
    """
    Create a new automation template
    """
    try:
        template_id = template.name.lower().replace(" ", "_")

        if template_id in automation_templates:
            raise HTTPException(status_code=400, detail=f"Template '{template_id}' already exists")

        automation_templates[template_id] = {
            "name": template.name,
            "description": template.description,
            "commands": template.commands,
            "parameters": template.parameters
        }

        return {
            "success": True,
            "template_id": template_id,
            "message": f"Template '{template.name}' created successfully"
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Template creation failed: {e}")
        raise HTTPException(status_code=500, detail=f"Template creation failed: {str(e)}")

@router.get("/status")
async def get_lux_status():
    """
    Get LUX model status and capabilities
    """
    try:
        has_api_key = bool(os.getenv("ANTHROPIC_API_KEY"))

        capabilities = [
            "screen_analysis",
            "natural_language_commands",
            "click_interactions",
            "keyboard_input",
            "application_control",
            "automation_templates",
            "batch_processing"
        ]

        if has_api_key:
            capabilities.extend([
                "ai_screen_interpretation",
                "element_detection",
                "ocr_support"
            ])

        return {
            "success": True,
            "model": "LUX Computer Use Model",
            "status": "ready" if has_api_key else "no_api_key",
            "capabilities": capabilities,
            "has_api_key": has_api_key,
            "supported_actions": [
                "click", "type", "keyboard", "scroll",
                "open_app", "screenshot", "wait", "ocr"
            ],
            "template_count": len(automation_templates),
            "timestamp": datetime.now().isoformat()
        }

    except Exception as e:
        logger.error(f"Status check failed: {e}")
        raise HTTPException(status_code=500, detail=f"Status check failed: {str(e)}")

@router.delete("/templates/{template_id}")
async def delete_template(template_id: str):
    """
    Delete an automation template
    """
    try:
        if template_id not in automation_templates:
            raise HTTPException(status_code=404, detail=f"Template '{template_id}' not found")

        template_name = automation_templates[template_id]["name"]
        del automation_templates[template_id]

        return {
            "success": True,
            "message": f"Template '{template_name}' deleted successfully"
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Template deletion failed: {e}")
        raise HTTPException(status_code=500, detail=f"Template deletion failed: {str(e)}")

# BYOK (Bring Your Own Key) endpoints
@router.post("/configure-api-key")
async def configure_api_key(api_key: str):
    """
    Configure custom API key for LUX model
    """
    try:
        # Validate API key by attempting to initialize model
        test_model = LuxModel(api_key=api_key)

        # Update environment variable for this session
        os.environ["ANTHROPIC_API_KEY"] = api_key

        return {
            "success": True,
            "message": "API key configured successfully",
            "configured_at": datetime.now().isoformat()
        }

    except Exception as e:
        logger.error(f"API key configuration failed: {e}")
        raise HTTPException(status_code=400, detail=f"Invalid API key: {str(e)}")