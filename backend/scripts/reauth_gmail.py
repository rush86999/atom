import asyncio
import json
import os
import sys
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow

# Add the backend directory to sys.path
backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if backend_dir not in sys.path:
    sys.path.append(backend_dir)

from dotenv import load_dotenv

# Now import relative to backend root
from core.token_storage import token_storage

load_dotenv()

# Scopes required for the Gmail integration
SCOPES = [
    'https://www.googleapis.com/auth/gmail.readonly',
    'https://www.googleapis.com/auth/gmail.send',
    'https://www.googleapis.com/auth/gmail.compose',
    'https://www.googleapis.com/auth/gmail.modify'
]

import http.server
import socketserver
import urllib.parse
import webbrowser
from google_auth_oauthlib.flow import Flow


async def reauth_gmail():
    print("--- Gmail Re-authentication ---")
    
    client_id = os.getenv("GOOGLE_CLIENT_ID")
    client_secret = os.getenv("GOOGLE_CLIENT_SECRET")
    
    if not client_id or not client_secret:
        print("ERROR: GOOGLE_CLIENT_ID or GOOGLE_CLIENT_SECRET not found in environment.")
        return

    client_config = {
        "web": {
            "client_id": client_id,
            "client_secret": client_secret,
            "auth_uri": "https://accounts.google.com/o/oauth2/v2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
        }
    }

    # Redirect URI must match what's in Google Console
    redirect_uri = "http://localhost:8080/"
    
    flow = Flow.from_client_config(
        client_config, 
        scopes=SCOPES,
        redirect_uri=redirect_uri
    )

    auth_url, _ = flow.authorization_url(prompt='consent', access_type='offline')
    
    print(f"\n1. Opening browser for Gmail Authorization...")
    webbrowser.open(auth_url)

    # Local server to catch the code
    PORT = 8080
    CODE = None

    class OAuthCallbackHandler(http.server.SimpleHTTPRequestHandler):
        def do_GET(self):
            nonlocal CODE
            query = urllib.parse.urlparse(self.path).query
            params = urllib.parse.parse_qs(query)
            
            if "code" in params:
                CODE = params["code"][0]
                self.send_response(200)
                self.send_header("Content-type", "text/html")
                self.end_headers()
                
                html = """
                <!DOCTYPE html>
                <html lang="en">
                <head>
                    <meta charset="UTF-8">
                    <meta name="viewport" content="width=device-width, initial-scale=1.0">
                    <title>Success | Atom Authentication</title>
                    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700&display=swap" rel="stylesheet">
                    <style>
                        :root {
                            --bg-color: #050505;
                            --card-bg: rgba(20, 20, 20, 0.7);
                            --accent-color: #ea4335;
                            --text-primary: #ffffff;
                            --text-secondary: #a0a0a0;
                        }
                        body {
                            margin: 0;
                            padding: 0;
                            font-family: 'Inter', sans-serif;
                            background-color: var(--bg-color);
                            color: var(--text-primary);
                            display: flex;
                            align-items: center;
                            justify-content: center;
                            height: 100vh;
                            overflow: hidden;
                        }
                        .background {
                            position: absolute;
                            width: 100%;
                            height: 100%;
                            background: radial-gradient(circle at 50% 50%, #7f1d1d 0%, #050505 70%);
                            z-index: -1;
                            filter: blur(80px);
                            opacity: 0.5;
                        }
                        .card {
                            background: var(--card-bg);
                            backdrop-filter: blur(12px);
                            -webkit-backdrop-filter: blur(12px);
                            border: 1px solid rgba(255, 255, 255, 0.1);
                            border-radius: 24px;
                            padding: 48px;
                            text-align: center;
                            max-width: 400px;
                            width: 90%;
                            box-shadow: 0 25px 50px -12px rgba(0, 0, 0, 0.5);
                            transform: translateY(0);
                            animation: slideUp 0.6s cubic-bezier(0.16, 1, 0.3, 1);
                        }
                        @keyframes slideUp {
                            from { transform: translateY(20px); opacity: 0; }
                            to { transform: translateY(0); opacity: 1; }
                        }
                        .icon-container {
                            width: 80px;
                            height: 80px;
                            background: rgba(234, 67, 53, 0.1);
                            border-radius: 50%;
                            display: flex;
                            align-items: center;
                            justify-content: center;
                            margin: 0 auto 24px;
                        }
                        .checkmark {
                            width: 40px;
                            height: 40px;
                            stroke: var(--accent-color);
                            stroke-width: 3;
                            stroke-linecap: round;
                            stroke-linejoin: round;
                            fill: none;
                            stroke-dasharray: 100;
                            stroke-dashoffset: 100;
                            animation: dash 0.8s ease-in-out forwards 0.3s;
                        }
                        @keyframes dash {
                            to { stroke-dashoffset: 0; }
                        }
                        h1 {
                            font-size: 28px;
                            font-weight: 700;
                            margin: 0 0 12px;
                            letter-spacing: -0.02em;
                        }
                        p {
                            font-size: 16px;
                            color: var(--text-secondary);
                            line-height: 1.5;
                            margin-bottom: 32px;
                        }
                        .status-tag {
                            display: inline-block;
                            padding: 6px 12px;
                            background: rgba(34, 197, 94, 0.1);
                            color: #22c55e;
                            font-weight: 600;
                            font-size: 12px;
                            border-radius: 100px;
                            text-transform: uppercase;
                            letter-spacing: 0.05em;
                            margin-bottom: 16px;
                        }
                        .footer {
                            position: absolute;
                            bottom: 40px;
                            font-size: 12px;
                            color: rgba(255, 255, 255, 0.3);
                            letter-spacing: 0.1em;
                            text-transform: uppercase;
                        }
                    </style>
                </head>
                <body>
                    <div class="background"></div>
                    <div class="card">
                        <div class="status-tag">Connected</div>
                        <div class="icon-container">
                            <svg class="checkmark" viewBox="0 0 52 52">
                                <path d="M14.1 27.2l7.1 7.2 16.7-16.8"/>
                            </svg>
                        </div>
                        <h1>Gmail authenticated</h1>
                        <p>Your Gmail account is now successfully linked to Atom. You can close this tab and return to the terminal.</p>
                    </div>
                    <div class="footer">Powered by Atom AI</div>
                </body>
                </html>
                """
                self.wfile.write(html.encode())
            else:
                self.send_response(400)
                self.end_headers()
                self.wfile.write(b"<h1>Authentication Failed!</h1>")

    print(f"2. Waiting for callback on {redirect_uri}...")
    with socketserver.TCPServer(("", PORT), OAuthCallbackHandler) as httpd:
        httpd.handle_request()

    if CODE:
        print(f"3. Exchanging code for tokens...")
        flow.fetch_token(code=CODE)
        creds = flow.credentials

        # Convert credentials to a dictionary for storage
        token_data = {
            "access_token": creds.token,
            "refresh_token": creds.refresh_token,
            "token_uri": creds.token_uri,
            "client_id": creds.client_id,
            "client_secret": creds.client_secret,
            "scopes": creds.scopes,
            "token_type": "Bearer"
        }

        # Save the new token data
        token_storage.save_token("google", token_data)
        print("\n✅ SUCCESS: Gmail token updated and saved to oauth_tokens.json")
    else:
        print("\n❌ Failed to get authorization code.")

if __name__ == "__main__":
    asyncio.run(reauth_gmail())
