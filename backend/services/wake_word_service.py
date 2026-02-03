
import asyncio
import json
import os
import sys
import numpy as np

try:
    import openwakeword
    from openwakeword.model import Model
except ImportError:
    openwakeword = None
    Model = None
import logging
import uvicorn
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from starlette.websockets import WebSocketState

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI()

# Configuration
# Path to the trained ONNX model
MODEL_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "data", "atom_wake_word.onnx")
# Use default if custom not found (or fallback to a pre-trained one from openwakeword for testing if needed)
# For this implementation, we assume the user's custom model exists or we fall back to a default like "hey jarvis" for test.
if not os.path.exists(MODEL_PATH):
    logger.warning(f"Custom model not found at {MODEL_PATH}. Using default openWakeWord models.")
    MODEL_PATH = None 

# Initialize the model (global to avoid reloading)
# openWakeWord models expect chunks of 1280 samples (80ms at 16khz) usually, but the library handles buffering.
wakeword_model = None

def get_model():
    global wakeword_model
    if Model is None:
        logger.warning("openwakeword not installed. Voice activation disabled.")
        return None

    if wakeword_model is None:
        logger.info("Loading Wake Word Model...")
        # If model_paths is provided, it loads that. Otherwise loads default.
        # inference_framework="onnx" is default.
        if MODEL_PATH:
             wakeword_model = Model(wakeword_models=[MODEL_PATH], inference_framework="onnx")
        else:
             # Fallback to a standard model (e.g. 'alexa', 'hey_mycroft') included in the library
             # or purely for 'atom' if we had it. Let's just load default to ensure it works.
             wakeword_model = Model(inference_framework="onnx")
    return wakeword_model

@app.websocket("/ws/audio")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    logger.info("Client connected to Wake Word Service")
    
    model = get_model()
    
    # We expect 16khz, 16-bit PCM audio chunks (bytes)
    # The chunk size depends on the client, but openwakeword is robust.
    
    try:
        while True:
            # Receive audio data
            data = await websocket.receive_bytes()
            
            # Convert bytes to numpy array (int16)
            # Assuming little-endian 16-bit PCM
            audio_chunk = np.frombuffer(data, dtype=np.int16)
            
            # Feed to model
            # predict() returns a dictionary of scores {model_name: score, ...}
            prediction = model.predict(audio_chunk)
            
            # Check for trigger
            for mdl_name, score in prediction.items():
                if score > 0.5: # Threshold
                    logger.info(f"Wake Word Detected: {mdl_name} (Score: {score})")
                    await websocket.send_json({
                        "type": "WAKE_WORD_DETECTED",
                        "transcript": "atom", # Mapping the model to the word "atom"
                        "model": mdl_name,
                        "score": float(score)
                    })
                    # Reset buffer after detection to avoid double triggers? 
                    # model.reset() # openwakeword doesn't typically need reset for continuous stream, but good for one-shot.
                    # For continuous, we just keep going.
                    
    except WebSocketDisconnect:
        logger.info("Client disconnected")
    except Exception as e:
        logger.error(f"Error in websocket loop: {e}")
        # Try to close if open
        if websocket.client_state == WebSocketState.CONNECTED:
            await websocket.close()

if __name__ == "__main__":
    logger.info("Starting Wake Word Service on port 8008...")
    uvicorn.run(app, host="0.0.0.0", port=8008)
