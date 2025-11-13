#!/usr/bin/env python3
"""
Simple ATOM Backend Test
"""

import os
import sys
import time
import asyncio
from pathlib import Path

# Add backend directory to path
backend_dir = Path(__file__).parent / "backend"
sys.path.insert(0, str(backend_dir))

async def test_backend():
    """Test backend functionality"""
    print("🌟 Testing ATOM Platform Backend")
    print("=" * 40)
    
    try:
        # Import app
        from main_api_app import app
        print("✅ Backend app imported successfully")
        
        # Test FastAPI app
        print(f"✅ FastAPI app: {app.title}")
        print(f"📋 Routes: {len(app.routes)} routes loaded")
        
        # Test health endpoint (if it exists)
        for route in app.routes:
            if hasattr(route, 'path') and route.path == "/health":
                print("✅ Health endpoint found")
                break
        else:
            print("⚠️  Health endpoint not found")
        
        return True
        
    except Exception as e:
        print(f"❌ Backend test failed: {e}")
        return False

if __name__ == "__main__":
    success = asyncio.run(test_backend())
    
    if success:
        print("\n🎉 Backend test PASSED!")
        print("📋 Next steps:")
        print("   1. Start frontend: ./start_frontend.sh")
        print("   2. Test integrations in browser")
        print("   3. Configure API keys for integrations")
    else:
        print("\n❌ Backend test FAILED!")
        print("🔧 Troubleshooting:")
        print("   1. Check Python version: python --version")
        print("   2. Install dependencies: pip install fastapi uvicorn")
        print("   3. Check backend directory: ls -la backend/")
    
    sys.exit(0 if success else 1)