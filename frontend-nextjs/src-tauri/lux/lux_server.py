#!/usr/bin/env python3
"""
LUX Local Server
Runs LUX computer use functionality locally within Tauri desktop app
"""

import os
import sys
import json
import asyncio
import logging
import argparse
from pathlib import Path
from typing import Dict, Any, Optional
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import uvicorn
import base64
import io

# Add LUX modules to path
sys.path.insert(0, Path(__file__).parent)

from lux_model import get_lux_model, ComputerActionType
from lux_config import lux_config

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Create FastAPI app
app = FastAPI(
    title="LUX Local Server",
    description="Local LUX computer use server for desktop automation",
    version="1.0.0"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global LUX model instance
lux_model = None
server_port = 8080

async def get_lux_instance():
    """Get or create LUX model instance"""
    global lux_model
    if lux_model is None:
        try:
            lux_model = await get_lux_model()
            logger.info("LUX model initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize LUX model: {e}")
            raise
    return lux_model

@app.get("/")
async def root():
    """Health check endpoint"""
    return {
        "name": "LUX Local Server",
        "status": "running",
        "version": "1.0.0",
        "purpose": "Local computer use automation"
    }

@app.get("/health")
async def health_check():
    """Detailed health check"""
    try:
        # Check if we have API keys
        keys = lux_config.get_all_keys()
        has_anthropic = bool(lux_config.get_anthropic_key())

        return {
            "status": "healthy",
            "api_keys_loaded": len(keys),
            "anthropic_available": has_anthropic,
            "screen_automation": "ready" if has_anthropic else "needs_api_key"
        }
    except Exception as e:
        return JSONResponse(
            status_code=503,
            content={
                "status": "unhealthy",
                "error": str(e)
            }
        )

@app.post("/command")
async def execute_command(request: Dict[str, Any]):
    """Execute a natural language command"""
    try:
        if "command" not in request:
            raise HTTPException(status_code=400, detail="Command is required")

        command = request["command"]
        logger.info(f"Executing command: {command}")

        lux = await get_lux_instance()
        result = await lux.execute_command(command)

        return result

    except Exception as e:
        logger.error(f"Command execution failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/screen")
async def get_screen_info():
    """Get screen information and elements"""
    try:
        lux = await get_lux_instance()
        screen_info = await lux.get_screen_info()
        return screen_info
    except Exception as e:
        logger.error(f"Screen info failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/screenshot")
async def get_screenshot():
    """Capture and return screenshot"""
    try:
        lux = await get_lux_instance()
        screenshot = await lux.capture_screen()

        # Convert to base64 for JSON response
        buffer = io.BytesIO()
        screenshot.save(buffer, format='PNG')
        screenshot_base64 = base64.b64encode(buffer.getvalue()).decode()

        return {
            "success": True,
            "screenshot": screenshot_base64,
            "size": screenshot.size,
            "format": "PNG"
        }
    except Exception as e:
        logger.error(f"Screenshot failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/templates")
async def get_automation_templates():
    """Get built-in automation templates"""
    try:
        templates = [
            {
                "id": "open-slack",
                "name": "Open Slack",
                "description": "Opens Slack application and waits for it to load",
                "commands": ["open Slack app", "wait 3 seconds"],
                "category": "communication"
            },
            {
                "id": "check-gmail",
                "name": "Check Gmail",
                "description": "Opens browser and navigates to Gmail",
                "commands": [
                    "open Chrome",
                    "type gmail.com",
                    "press Enter",
                    "wait 2 seconds"
                ],
                "category": "productivity"
            },
            {
                "id": "take-notes",
                "name": "Take Notes",
                "description": "Opens notes app and creates new note",
                "commands": [
                    "open Notes app",
                    "wait 1 second",
                    "type 'Meeting Notes'",
                    "press Enter"
                ],
                "category": "productivity"
            }
        ]

        return {
            "success": True,
            "templates": templates,
            "total": len(templates)
        }
    except Exception as e:
        logger.error(f"Templates failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/batch")
async def execute_batch_commands(request: Dict[str, Any]):
    """Execute multiple commands in sequence"""
    try:
        if "commands" not in request:
            raise HTTPException(status_code=400, detail="Commands list is required")

        commands = request["commands"]
        if not isinstance(commands, list):
            raise HTTPException(status_code=400, detail="Commands must be a list")

        results = []
        lux = await get_lux_instance()

        for i, command in enumerate(commands):
            try:
                logger.info(f"Executing batch command {i+1}/{len(commands)}: {command}")
                result = await lux.execute_command(command)
                results.append({
                    "command": command,
                    "success": result.get("success", False),
                    "result": result
                })
            except Exception as e:
                results.append({
                    "command": command,
                    "success": False,
                    "error": str(e)
                })

        return {
            "success": True,
            "batch_size": len(commands),
            "results": results
        }

    except Exception as e:
        logger.error(f"Batch execution failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/status")
async def get_lux_status():
    """Get current LUX status and capabilities"""
    try:
        keys = lux_config.get_all_keys()
        validation = lux_config.validate_keys()

        return {
            "initialized": lux_model is not None,
            "api_keys": len(keys),
            "key_validation": validation,
            "screen_resolution": None,  # Will be populated when model is initialized
            "capabilities": [
                "screen_capture",
                "command_interpretation",
                "desktop_automation",
                "ocr",
                "element_detection"
            ]
        }
    except Exception as e:
        logger.error(f"Status check failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

def main():
    """Main function to run the LUX server"""
    global server_port

    parser = argparse.ArgumentParser(description="LUX Local Server")
    parser.add_argument("--port", type=int, default=8080, help="Port to run the server on")
    parser.add_argument("--host", type=str, default="127.0.0.1", help="Host to bind the server to")

    args = parser.parse_args()
    server_port = args.port

    logger.info(f"Starting LUX Local Server on http://{args.host}:{args.port}")

    try:
        uvicorn.run(
            app,
            host=args.host,
            port=args.port,
            log_level="info"
        )
    except KeyboardInterrupt:
        logger.info("LUX Local Server stopped")
    except Exception as e:
        logger.error(f"Failed to start LUX server: {e}")

if __name__ == "__main__":
    main()