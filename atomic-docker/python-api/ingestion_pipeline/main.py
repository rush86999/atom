import logging
import asyncio
from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.responses import JSONResponse

# Assuming pipeline_orchestrator is in the same directory or package
try:
    from .pipeline_orchestrator import run_ingestion_pipeline
except ImportError:
    from pipeline_orchestrator import run_ingestion_pipeline


# Configure basic logging for the FastAPI app if not already configured by orchestrator
logger = logging.getLogger(__name__)
if not logger.hasHandlers():
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[logging.StreamHandler()]
    )

app = FastAPI(
    title="Atom Ingestion Pipeline Service",
    description="Provides an API to trigger and manage the Notion to LanceDB ingestion pipeline.",
    version="0.1.0"
)

# Global flag to prevent multiple simultaneous pipeline runs if desired
is_pipeline_running = False
pipeline_task: Optional[asyncio.Task] = None

@app.on_event("startup")
async def startup_event():
    logger.info("Ingestion Pipeline Service starting up...")
    # Perform any one-time setup if needed, e.g., initial client checks from orchestrator's deps
    # For now, client initializations are handled within the modules when first called.

@app.on_event("shutdown")
async def shutdown_event():
    global pipeline_task
    logger.info("Ingestion Pipeline Service shutting down...")
    if pipeline_task and not pipeline_task.done():
        logger.info("Pipeline is running, attempting to cancel...")
        pipeline_task.cancel()
        try:
            await pipeline_task
        except asyncio.CancelledError:
            logger.info("Pipeline task cancelled successfully during shutdown.")
        except Exception as e:
            logger.error(f"Error during pipeline task cancellation on shutdown: {e}", exc_info=True)
    logger.info("Ingestion Pipeline Service shutdown complete.")


@app.post("/trigger-ingestion", status_code=202)
async def trigger_ingestion_endpoint(background_tasks: BackgroundTasks):
    """
    Triggers the ingestion pipeline to run in the background.
    """
    global is_pipeline_running
    global pipeline_task

    if is_pipeline_running:
        logger.warning("Ingestion pipeline is already running.")
        raise HTTPException(status_code=409, detail="Ingestion pipeline is already running.")

    is_pipeline_running = True
    logger.info("Triggering ingestion pipeline run in the background.")

    async def pipeline_wrapper():
        global is_pipeline_running
        global pipeline_task
        try:
            await run_ingestion_pipeline()
        except Exception as e:
            logger.error(f"Ingestion pipeline encountered an unhandled error: {e}", exc_info=True)
        finally:
            is_pipeline_running = False
            pipeline_task = None
            logger.info("Pipeline wrapper finished.")

    # Run in background_tasks to allow immediate response
    # background_tasks.add_task(pipeline_wrapper)
    # For long-running tasks, creating an asyncio.Task is often better for management
    pipeline_task = asyncio.create_task(pipeline_wrapper())


    return JSONResponse(
        content={"message": "Ingestion pipeline triggered successfully. It will run in the background."},
        status_code=202
    )

@app.get("/ingestion-status")
async def get_ingestion_status():
    """
    Returns the current status of the ingestion pipeline.
    """
    global is_pipeline_running
    if is_pipeline_running:
        return {"status": "running", "message": "Ingestion pipeline is currently running."}
    else:
        # TODO: Could potentially query a database or state file for last run status/timestamp
        return {"status": "idle", "message": "Ingestion pipeline is not currently running."}

if __name__ == "__main__":
    import uvicorn
    # This allows running the service directly for local testing
    # Example: python main.py (from within ingestion_pipeline directory)
    # Ensure environment variables are set (e.g., via a .env file loaded by pipeline_orchestrator or here)

    # from dotenv import load_dotenv
    # load_dotenv() # Load .env from current directory if it exists

    logger.info("Starting Ingestion Pipeline Service directly with Uvicorn...")
    uvicorn.run(app, host="0.0.0.0", port=8002, log_level="info")
    # Port 8002 is an example, can be configured.
```
