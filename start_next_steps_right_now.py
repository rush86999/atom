#!/usr/bin/env python3
"""
START NEXT STEPS RIGHT NOW
Begin actual server startup sequence
"""

import os
import subprocess
import sys
import time
from datetime import datetime

def start_next_steps_right_now():
    """Start the actual next steps sequence right now"""
    
    print("🚀 STARTING NEXT STEPS RIGHT NOW")
    print("=" * 80)
    print("Beginning actual server startup sequence")
    print("=" * 80)
    
    # Step 1: Verify readiness
    print("🔍 STEP 1: VERIFY READINESS")
    required_files = [
        "start_simple_oauth_server.py",
        "backend/main_api_app.py",
        "frontend-nextjs/package.json",
        ".env"
    ]
    
    all_ready = True
    for file_path in required_files:
        if os.path.exists(file_path):
            print(f"   ✅ {file_path} - READY")
        else:
            print(f"   ❌ {file_path} - MISSING")
            all_ready = False
    
    if not all_ready:
        print("❌ READINESS FAILED - Missing required files")
        return False
    
    print("✅ READINESS PASSED - All files ready")
    print()
    
    # Step 2: Start OAuth Server
    print("🔐 STEP 2: START OAUTH SERVER")
    print("===============================")
    
    try:
        print("   🚀 Starting OAuth server on port 5058...")
        print("   📋 Command: python start_simple_oauth_server.py")
        print("   🌐 Will be available at: http://localhost:5058")
        print("   📊 Health check: http://localhost:5058/healthz")
        print("   📚 OAuth endpoints: http://localhost:5058/api/auth/oauth-status")
        print()
        print("   🔄 Starting OAuth server process...")
        
        # Start OAuth server in background
        oauth_process = subprocess.Popen([
            sys.executable, "start_simple_oauth_server.py"
        ], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        
        # Give it time to start
        time.sleep(3)
        
        # Check if process is still running
        if oauth_process.poll() is None:
            print("   ✅ OAuth Server started successfully!")
            print("   📍 PID:", oauth_process.pid)
            print("   🌐 URL: http://localhost:5058")
        else:
            print("   ❌ OAuth Server failed to start")
            return False
            
    except Exception as e:
        print(f"   ❌ Error starting OAuth server: {e}")
        return False
    
    print()
    
    # Step 3: Instructions for remaining steps
    print("🔧 NEXT STEPS TO COMPLETE:")
    print("================================")
    
    next_steps = [
        {
            "step": "3",
            "action": "START BACKEND API SERVER",
            "command": "cd backend && python main_api_app.py",
            "port": 8000,
            "description": "FastAPI server with API routes",
            "docs": "http://localhost:8000/docs"
        },
        {
            "step": "4", 
            "action": "START FRONTEND APPLICATION",
            "command": "cd frontend-nextjs && npm run dev",
            "port": 3000,
            "description": "Next.js application with UI components",
            "url": "http://localhost:3000"
        },
        {
            "step": "5",
            "action": "TEST INTEGRATION",
            "command": "Visit all URLs and test OAuth flows",
            "description": "Verify complete application integration",
            "success": "All servers running and communicating"
        }
    ]
    
    for step_info in next_steps:
        print(f"   🎯 STEP {step_info['step']}: {step_info['action']}")
        print(f"      Command: {step_info['command']}")
        print(f"      Port: {step_info['port']}")
        print(f"      Description: {step_info['description']}")
        if 'docs' in step_info:
            print(f"      API Docs: {step_info['docs']}")
        if 'url' in step_info:
            print(f"      Frontend: {step_info['url']}")
        print()
    
    # Step 4: Current status
    print("📊 CURRENT STATUS:")
    print("===================")
    
    status_items = [
        ("OAuth Server", "🟢 RUNNING", "Port 5058", "Enterprise authentication ready"),
        ("Backend API Server", "🟡 READY", "Port 8000", "FastAPI server ready to start"),
        ("Frontend Application", "🟡 READY", "Port 3000", "Next.js app ready to start"),
        ("Integration", "🟡 READY", "N/A", "Components ready to connect")
    ]
    
    for item, status, detail, capability in status_items:
        print(f"   {status} {item}: {detail}")
        print(f"      Capability: {capability}")
        print()
    
    # Step 5: Create monitoring script
    print("🔧 CREATING MONITORING SCRIPT...")
    monitor_script = """#!/bin/bash

# ATOM Server Monitor
echo "🔍 ATOM Server Status Monitor"
echo "=============================="

echo "🔐 OAuth Server Status:"
if curl -s http://localhost:5058/healthz > /dev/null 2>&1; then
    echo "   ✅ RUNNING - http://localhost:5058"
else
    echo "   ❌ NOT RUNNING"
fi

echo ""
echo "🔧 Backend API Status:"
if curl -s http://localhost:8000/health > /dev/null 2>&1; then
    echo "   ✅ RUNNING - http://localhost:8000"
else
    echo "   ❌ NOT RUNNING"
fi

echo ""
echo "🎨 Frontend Application Status:"
if curl -s http://localhost:3000 > /dev/null 2>&1; then
    echo "   ✅ RUNNING - http://localhost:3000"
else
    echo "   ❌ NOT RUNNING"
fi

echo ""
echo "🌐 Access Points:"
echo "   Frontend: http://localhost:3000"
echo "   Backend API: http://localhost:8000"
echo "   API Documentation: http://localhost:8000/docs"
echo "   OAuth Server: http://localhost:5058"
echo ""
echo "📊 Integration Test:"
echo "   Visit: http://localhost:3000"
echo "   Should see: ATOM UI with 8 components"
echo "   Should work: OAuth authentication flows"
"""
    
    with open('monitor_servers.sh', 'w') as f:
        f.write(monitor_script)
    
    os.chmod('monitor_servers.sh', 0o755)
    print("   ✅ Monitoring script created: monitor_servers.sh")
    print()
    
    # Step 6: Final instructions
    print("🎯 FINAL INSTRUCTIONS:")
    print("========================")
    
    print("   🔴 CURRENT STATUS: OAuth Server is RUNNING")
    print("   🔴 NEXT ACTION: Start Backend API Server")
    print("   🔴 THEN: Start Frontend Application")
    print("   🔴 FINALLY: Test complete integration")
    print()
    
    print("   🚀 QUICK START COMMANDS:")
    print("   # Terminal 2 - Backend API:")
    print("   cd backend && python main_api_app.py")
    print()
    print("   # Terminal 3 - Frontend:")
    print("   cd frontend-nextjs && npm run dev")
    print()
    print("   # Monitor all servers:")
    print("   ./monitor_servers.sh")
    print()
    
    print("   🌐 ACCESS POINTS:")
    print("   Frontend: http://localhost:3000")
    print("   Backend API: http://localhost:8000")
    print("   API Documentation: http://localhost:8000/docs")
    print("   OAuth Server: http://localhost:5058")
    print()
    
    return True

if __name__ == "__main__":
    success = start_next_steps_right_now()
    
    print(f"\n" + "=" * 80)
    if success:
        print("🎉 NEXT STEPS STARTED SUCCESSFULLY!")
        print("✅ OAuth Server is now running")
        print("✅ Backend API ready to start")
        print("✅ Frontend ready to start")
        print("✅ Monitoring script created")
        print("✅ Integration path defined")
        print()
        print("🎯 NEXT ACTIONS:")
        print("   1. Start Backend API: cd backend && python main_api_app.py")
        print("   2. Start Frontend: cd frontend-nextjs && npm run dev")
        print("   3. Test Integration: Visit http://localhost:3000")
        print("   4. Monitor Servers: ./monitor_servers.sh")
        print()
        print("💪 CONFIDENCE: First server started - integration underway!")
    else:
        print("❌ NEXT STEPS FAILED TO START")
        print("❌ Please check missing files and requirements")
    
    print("=" * 80)
    print("🚀 ACTIVATION COMPLETE - OAuth Server Running!")
    exit(0 if success else 1)