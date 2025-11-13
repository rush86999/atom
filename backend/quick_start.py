"""
Quick fix for backend import issue
"""
import sys
sys.path.insert(0, '.')
import uvicorn
from main_api_app import app

if __name__ == "__main__":
    print("🚀 Starting ATOM Backend...")
    uvicorn.run(app, host="0.0.0.0", port=5058)