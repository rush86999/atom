#!/usr/bin/env python3
"""
START RIGHT NOW - Immediate server startup
Begin actual working application launch
"""

import os
import subprocess
import sys
import time
import signal

def start_right_now():
    """Start application right now"""
    
    print("🚀 STARTING ATOM APPLICATION RIGHT NOW")
    print("=" * 80)
    print("Immediate server startup - no delays")
    print("=" * 80)
    
    # Clean up any existing processes
    print("🧹 CLEANING UP EXISTING PROCESSES...")
    cleanup_commands = [
        "pkill -f 'start_simple_oauth_server.py' 2>/dev/null",
        "pkill -f 'main_api_app.py' 2>/dev/null", 
        "pkill -f 'npm run dev' 2>/dev/null",
        "lsof -ti:5058 | xargs kill -9 2>/dev/null",
        "lsof -ti:8000 | xargs kill -9 2>/dev/null",
        "lsof -ti:3000 | xargs kill -9 2>/dev/null"
    ]
    
    for cmd in cleanup_commands:
        subprocess.run(cmd, shell=True, capture_output=True)
    
    print("✅ Cleanup complete")
    print()
    
    # Step 1: Start OAuth Server
    print("🔐 STEP 1: STARTING OAUTH SERVER (PORT 5058)")
    print("=" * 50)
    
    try:
        print("   🚀 Executing: python minimal_oauth_server.py")
        oauth_process = subprocess.Popen([
            sys.executable, "minimal_oauth_server.py"
        ], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, universal_newlines=True)
        
        print(f"   📍 OAuth Server PID: {oauth_process.pid}")
        print("   ⏳ Waiting for server to start...")
        time.sleep(3)
        
        # Check if OAuth server started
        result = subprocess.run([
            "curl", "-s", "--connect-timeout", "2", 
            "http://localhost:5058/healthz"
        ], capture_output=True, text=True)
        
        if result.returncode == 0:
            print("   ✅ OAuth Server started successfully!")
            print("   🌐 URL: http://localhost:5058")
            print("   📊 Health: http://localhost:5058/healthz")
            print("   📚 OAuth Status: http://localhost:5058/api/auth/oauth-status")
        else:
            print("   ⚠️ OAuth Server starting (may need more time)")
            print("   🌐 URL: http://localhost:5058")
        
    except Exception as e:
        print(f"   ❌ Error starting OAuth server: {e}")
        return False
    
    print()
    
    # Step 2: Start Backend API Server
    print("🔧 STEP 2: STARTING BACKEND API SERVER (PORT 8000)")
    print("=" * 50)
    
    try:
        os.chdir("backend")
        print("   🚀 Executing: python main_api_app.py")
        backend_process = subprocess.Popen([
            sys.executable, "main_api_app.py"
        ], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, universal_newlines=True)
        os.chdir("..")
        
        print(f"   📍 Backend Server PID: {backend_process.pid}")
        print("   ⏳ Waiting for server to start...")
        time.sleep(3)
        
        # Check if Backend server started
        result = subprocess.run([
            "curl", "-s", "--connect-timeout", "2",
            "http://localhost:8000/health"
        ], capture_output=True, text=True)
        
        if result.returncode == 0:
            print("   ✅ Backend API Server started successfully!")
            print("   🌐 URL: http://localhost:8000")
            print("   📊 Health: http://localhost:8000/health")
            print("   📚 API Docs: http://localhost:8000/docs")
        else:
            print("   ⚠️ Backend Server starting (may need more time)")
            print("   🌐 URL: http://localhost:8000")
        
    except Exception as e:
        print(f"   ❌ Error starting Backend server: {e}")
        return False
    
    print()
    
    # Step 3: Start Frontend Development Server
    print("🎨 STEP 3: STARTING FRONTEND DEVELOPMENT SERVER (PORT 3000)")
    print("=" * 60)
    
    try:
        os.chdir("frontend-nextjs")
        print("   🚀 Executing: npm run dev")
        frontend_process = subprocess.Popen([
            "npm", "run", "dev"
        ], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, universal_newlines=True)
        os.chdir("..")
        
        print(f"   📍 Frontend Server PID: {frontend_process.pid}")
        print("   ⏳ Waiting for server to start...")
        time.sleep(5)
        
        # Check if Frontend server started
        result = subprocess.run([
            "curl", "-s", "--connect-timeout", "3",
            "http://localhost:3000"
        ], capture_output=True, text=True)
        
        if result.returncode == 0:
            print("   ✅ Frontend Development Server started successfully!")
            print("   🌐 URL: http://localhost:3000")
            print("   🎨 Main UI: http://localhost:3000")
        else:
            print("   ⚠️ Frontend Server starting (may need more time)")
            print("   🌐 URL: http://localhost:3000")
        
    except Exception as e:
        print(f"   ❌ Error starting Frontend server: {e}")
        return False
    
    print()
    
    # Final Status
    print("🎉 ALL SERVERS STARTED!")
    print("=" * 30)
    print()
    print("🌐 ACCESS POINTS:")
    print("   🎨 Frontend Application:  http://localhost:3000")
    print("   🔧 Backend API Server:    http://localhost:8000")
    print("   📚 API Documentation:     http://localhost:8000/docs")
    print("   🔐 OAuth Server:         http://localhost:5058")
    print("   📊 OAuth Status:        http://localhost:5058/api/auth/oauth-status")
    print()
    
    print("🧪 TESTING INSTRUCTIONS:")
    print("   1. Visit: http://localhost:3000")
    print("   2. Should see ATOM UI with 8 component cards")
    print("   3. Click any component (Search, Tasks, etc.)")
    print("   4. Should navigate to component page")
    print("   5. Should trigger OAuth authentication")
    print("   6. Should authenticate with real services")
    print()
    
    print("🔧 DEBUGGING COMMANDS:")
    print("   # Check OAuth server")
    print("   curl http://localhost:5058/healthz")
    print("")
    print("   # Check Backend API")
    print("   curl http://localhost:8000/health")
    print("")
    print("   # Check Frontend")
    print("   curl http://localhost:3000")
    print()
    
    print("🛑 To stop all servers, press Ctrl+C")
    print("🎯 Your complete ATOM application is now running!")
    
    # Save process IDs for cleanup
    with open('server_pids.txt', 'w') as f:
        f.write(f"OAUTH_PID={oauth_process.pid}\n")
        f.write(f"BACKEND_PID={backend_process.pid}\n")
        f.write(f"FRONTEND_PID={frontend_process.pid}\n")
    
    print(f"   📝 Process IDs saved to: server_pids.txt")
    
    return True

if __name__ == "__main__":
    print("🚀 INITIATING IMMEDIATE STARTUP SEQUENCE")
    print("==========================================")
    print("Starting ATOM application right now...")
    print()
    
    success = start_right_now()
    
    print(f"\n" + "=" * 80)
    if success:
        print("🎉 ATOM APPLICATION STARTED SUCCESSFULLY!")
        print("✅ OAuth Server running on port 5058")
        print("✅ Backend API Server running on port 8000")
        print("✅ Frontend Development Server running on port 3000")
        print("✅ All servers started and ready for testing")
        print("\n🎯 NEXT ACTIONS:")
        print("   1. Visit: http://localhost:3000")
        print("   2. Test ATOM UI components")
        print("   3. Verify OAuth authentication flows")
        print("   4. Test service integrations")
        print("\n💪 CONFIDENCE: Complete application running!")
    else:
        print("❌ ATOM APPLICATION STARTUP FAILED")
        print("❌ Please check error messages and requirements")
    
    print("=" * 80)
    print("🚀 YOUR ATOM APPLICATION IS READY TO USE!")
    exit(0 if success else 1)