from fastapi import FastAPI
from backend.api.agent_routes import router as agent_router
from backend.api.workflow_debugging import router as workflow_router
from backend.api.canvas_routes import router as canvas_router

app = FastAPI()

# Include API routes
app.include_router(agent_router)
app.include_router(workflow_router)
app.include_router(canvas_router)

@app.get("/")
async def read_root():
    return {"Hello": "World"}
