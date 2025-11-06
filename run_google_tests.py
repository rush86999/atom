#!/usr/bin/env python3
"""
🚀 STANDALONE TEST RUNNER
Direct test execution without subprocess
"""

import os
import sys
import json
import requests
from datetime import datetime, timedelta
from typing import Dict, Any, List

# Import test class
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from test_google_integration import GoogleIntegrationTester

async def main():
    """Main execution function"""
    print("🚀 Starting Google Integration Tests (Standalone)")
    print("=" * 50)
    
    # Create tester
    tester = GoogleIntegrationTester()
    
    # Test basic connection first
    try:
        response = requests.get(f"{tester.base_url}/health", timeout=2)
        print(f"✅ Connected to {tester.base_url}/health")
        print(f"   Response: {response.json()}")
    except Exception as e:
        print(f"❌ Cannot connect to {tester.base_url}/health")
        print(f"   Error: {e}")
        
        # Check if any process is listening on 5058
        import socket
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        result = sock.connect_ex(('localhost', 5058))
        sock.close()
        
        if result == 0:
            print(f"✅ Port 5058 is in use, but connection failed anyway")
        else:
            print(f"❌ Port 5058 is not in use")
            print("   Starting minimal API server...")
            
            # Try to start server inline
            import subprocess
            import threading
            import time
            
            api_file = os.path.join("backend", "python-api-service", "minimal_api_app.py")
            if os.path.exists(api_file):
                env = os.environ.copy()
                env['PYTHON_API_PORT'] = '5058'
                
                def start_server():
                    subprocess.run([sys.executable, api_file], env=env, cwd=".")
                
                server_thread = threading.Thread(target=start_server, daemon=True)
                server_thread.start()
                
                print("⏳ Waiting 3 seconds for server to start...")
                time.sleep(3)
                
                try:
                    response = requests.get(f"{tester.base_url}/health", timeout=2)
                    print(f"✅ Server started successfully: {response.json()}")
                except Exception as e2:
                    print(f"❌ Server still not accessible: {e2}")
                    return
            else:
                print(f"❌ API file not found: {api_file}")
                return
    
    # Run tests
    results = await tester.run_all_tests()
    
    # Save results
    tester.save_results()

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())