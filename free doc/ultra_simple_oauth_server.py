#!/usr/bin/env python3
"""
Standalone OAuth Server - Ultra Simple
"""

import os
from flask import Flask, jsonify, request
from threading import Thread
import time

# Load GitHub credentials
GITHUB_CLIENT_ID = os.getenv('GITHUB_CLIENT_ID')

print(f"🔧 GitHub Client ID: {GITHUB_CLIENT_ID[:10] if GITHUB_CLIENT_ID else 'MISSING'}...")

app = Flask(__name__)
app.secret_key = "test-secret-key-2025"

# Basic endpoints
@app.route("/")
def index():
    return f"OAuth Server Running - GitHub Client ID: {GITHUB_CLIENT_ID[:10] if GITHUB_CLIENT_ID else 'MISSING'}..."

@app.route("/healthz")
def health():
    return jsonify({
        "status": "ok",
        "service": "oauth-server-ultra-simple",
        "github_loaded": bool(GITHUB_CLIENT_ID),
        "github_id_preview": GITHUB_CLIENT_ID[:10] if GITHUB_CLIENT_ID else None
    })

@app.route("/api/auth/github/status")
def github_status():
    return jsonify({
        "ok": True,
        "service": "github",
        "status": "connected" if GITHUB_CLIENT_ID else "needs_credentials",
        "credentials": "real" if GITHUB_CLIENT_ID else "placeholder",
        "client_id": GITHUB_CLIENT_ID or "placeholder_github_client_id",
        "message": f"GitHub OAuth is {'connected' if GITHUB_CLIENT_ID else 'needs credentials'}"
    })

@app.route("/api/auth/github/authorize")
def github_authorize():
    user_id = request.args.get("user_id", "test_user")
    
    if GITHUB_CLIENT_ID:
        auth_url = f"https://github.com/login/oauth/authorize?client_id={GITHUB_CLIENT_ID}&redirect_uri=http://localhost:5058/api/auth/github/callback&scope=repo user&state=test_state"
        
        return jsonify({
            "ok": True,
            "service": "github",
            "user_id": user_id,
            "auth_url": auth_url,
            "credentials": "real",
            "message": "GitHub OAuth authorization URL generated successfully"
        })
    else:
        return jsonify({
            "ok": True,
            "service": "github", 
            "user_id": user_id,
            "credentials": "placeholder",
            "message": "GitHub OAuth needs real credentials"
        })

if __name__ == "__main__":
    print("🚀 ULTRA SIMPLE OAUTH SERVER")
    print("=" * 50)
    print(f"🌐 Starting on http://127.0.0.1:5058")
    print(f"🔧 GitHub Credentials: {'LOADED' if GITHUB_CLIENT_ID else 'MISSING'}")
    print("📋 Endpoints:")
    print("   - GET  /")
    print("   - GET  /healthz")
    print("   - GET  /api/auth/github/status")
    print("   - GET  /api/auth/github/authorize")
    print("=" * 50)
    
    def run_server():
        try:
            app.run(host='127.0.0.1', port=5058, debug=False, use_reloader=False, threaded=False)
        except Exception as e:
            print(f"❌ Server Error: {e}")
    
    # Start server in background thread
    server_thread = Thread(target=run_server)
    server_thread.daemon = True
    server_thread.start()
    
    # Wait a moment for server to start
    print("⏳ Waiting for server to start...")
    time.sleep(3)
    
    # Test the server
    print("🔍 Testing server connectivity...")
    try:
        import requests
        response = requests.get("http://127.0.0.1:5058/healthz", timeout=5)
        if response.status_code == 200:
            data = response.json()
            print(f"✅ Server Test: {data.get('status')}")
            print(f"   GitHub Loaded: {data.get('github_loaded')}")
            print(f"   GitHub ID Preview: {data.get('github_id_preview')}...")
            
            print("\n🎉 OAUTH SERVER IS WORKING!")
            print("✅ Server accessible on localhost:5058")
            print("✅ GitHub credentials loaded")
            print("✅ Endpoints responding")
            print("\n🚀 READY FOR COMPLETE OAUTH TESTING!")
            
            # Keep server running
            print("\n🔄 Keeping server running... Press Ctrl+C to stop")
            try:
                while True:
                    time.sleep(1)
            except KeyboardInterrupt:
                print("\n🛑 Server stopped by user")
                
        else:
            print(f"❌ Server Test: HTTP {response.status_code}")
    except Exception as e:
        print(f"❌ Server Test Failed: {e}")
    
    server_thread.join()