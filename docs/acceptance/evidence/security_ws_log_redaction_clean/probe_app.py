from fastapi import FastAPI, WebSocket
from core.logging_config import setup_logging

try:
    setup_logging(level="INFO", format_type="json")
except TypeError:
    # Mirror the old main_api_app fallback: no centralized logging config.
    pass
app = FastAPI()

@app.get("/")
def root():
    return {"ok": True}

@app.websocket("/ws")
async def ws(websocket: WebSocket):
    await websocket.accept()
    await websocket.close()

@app.websocket("/ws/reject")
async def ws_reject(websocket: WebSocket):
    await websocket.close(code=1008)
