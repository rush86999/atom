from datetime import datetime
import logging
import os
import sys
import subprocess
import threading
from fastapi import APIRouter
from core.base_routes import BaseAPIRouter

logger = logging.getLogger(__name__)

# Use a very specific prefix to avoid conflicts
router = BaseAPIRouter(prefix="/api/v1/demo", tags=["Demo"])

@router.get("/run")

@router.post("/run")
async def run_computer_use_demo():
    """Trigger the real Computer Use (Selenium) demo script"""
    
    # Get the base directory of the backend
    # This file is in backend/api/demo_routes.py
    current_dir = os.path.dirname(os.path.abspath(__file__))
    backend_dir = os.path.dirname(current_dir)
    script_path = os.path.join(backend_dir, "scripts", "real_app_automation.py")

    def execute_script():
        try:
            logger.info(f"⚡ Starting Computer Use Demo script: {script_path}")
            
            # Use the same python executable to ensure dependencies like selenium are available
            result = subprocess.run(
                [sys.executable, script_path],
                capture_output=True,
                text=True,
                check=True
            )
            logger.info("✅ Computer Use Demo script finished successfully")
            if result.stdout:
                logger.info(f"Script Output:\n{result.stdout}")
        except subprocess.CalledProcessError as e:
            logger.error(f"❌ Computer Use Demo script failed with code {e.returncode}: {e.stderr}")
            if e.stdout:
                logger.info(f"Script Output before crash:\n{e.stdout}")
        except Exception as e:
            logger.error(f"❌ Computer Use Demo script failed: {e}")

    # Start in a background thread to return immediate response to UI
    thread = threading.Thread(target=execute_script)
    thread.daemon = True
    thread.start()

    return {
        "ok": True,
        "message": "Computer Use Demo started in background browser window on desktop.",
        "timestamp": datetime.now().isoformat()
    }

@router.get("/status")
async def get_demo_status():
    return {"status": "ready", "engine": "selenium"}
