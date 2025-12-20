import os
import sys
import webbrowser
import http.server
import socketserver
import urllib.parse
from dotenv import load_dotenv

from dotenv import load_dotenv

# Load environment variables first
load_dotenv()

# Add backend to sys.path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.oauth_handler import OAuthHandler, NOTION_OAUTH_CONFIG

PORT = 8080
CODE = None

class OAuthCallbackHandler(http.server.SimpleHTTPRequestHandler):
    def do_GET(self):
        global CODE
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
                        --accent-color: #3b82f6;
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
                        background: radial-gradient(circle at 50% 50%, #1e3a8a 0%, #050505 70%);
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
                        background: rgba(59, 130, 246, 0.1);
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
                    .btn {
                        display: inline-block;
                        padding: 12px 24px;
                        background: var(--text-primary);
                        color: black;
                        font-weight: 600;
                        text-decoration: none;
                        border-radius: 12px;
                        transition: all 0.2s;
                    }
                    .btn:hover {
                        transform: scale(1.02);
                        box-shadow: 0 0 20px rgba(255, 255, 255, 0.2);
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
                    <h1>Notion authenticated</h1>
                    <p>Your workspace is now successfully linked to Atom. You can close this tab and return to the terminal.</p>
                </div>
                <div class="footer">Powered by Atom AI</div>
            </body>
            </html>
            """
            self.wfile.write(html.encode())
        else:
            self.send_response(400)
            self.end_headers()
            self.wfile.write(b"<h1>Authentication Failed!</h1><p>No code found in redirect.</p>")

def run_reauth():
    if not NOTION_OAUTH_CONFIG.client_id or not NOTION_OAUTH_CONFIG.client_secret:
        print("❌ Error: NOTION_CLIENT_ID or NOTION_CLIENT_SECRET not found in .env")
        return

    handler = OAuthHandler(NOTION_OAUTH_CONFIG)
    
    # Generate auth URL
    # Notion doesn't use scopes in the same way, but OAuthConfig handles it
    auth_url = handler.get_authorization_url()
    
    print(f"\n1. Opening browser for Notion Authorization...")
    print(f"URL: {auth_url}\n")
    print(f"⚠️  IMPORTANT: Ensure your 'Redirect URI' in Notion dashboard is set to: {NOTION_OAUTH_CONFIG.redirect_uri}")
    
    webbrowser.open(auth_url)
    
    print(f"2. Waiting for callback on {NOTION_OAUTH_CONFIG.redirect_uri} ...")
    # Determine port from redirect_uri
    parsed_uri = urllib.parse.urlparse(NOTION_OAUTH_CONFIG.redirect_uri)
    port = parsed_uri.port or 80
    
    try:
        with socketserver.TCPServer(("", port), OAuthCallbackHandler) as httpd:
            httpd.handle_request()
    except Exception as e:
        print(f"❌ Error starting local server: {e}")
        return
    
    if CODE:
        print(f"3. Exchanging code for tokens...")
        import asyncio
        try:
            tokens = asyncio.run(handler.exchange_code_for_tokens(CODE))
            
            access_token = tokens.get("access_token")
            workspace_name = tokens.get("workspace_name")
            
            print(f"\n✅ SUCCESS!")
            print(f"Workspace: {workspace_name}")
            print(f"Access Token: {access_token[:10]}...")
            
            print(f"\nUpdating .env file...")
            
            with open(".env", "r") as f:
                lines = f.readlines()
            
            with open(".env", "w") as f:
                found = False
                for line in lines:
                    if line.startswith("NOTION_TOKEN="):
                        f.write(f"NOTION_TOKEN={access_token}\n")
                        found = True
                    else:
                        f.write(line)
                if not found:
                    f.write(f"NOTION_TOKEN={access_token}\n")
            
            print("Done! Token saved to NOTION_TOKEN in .env")
        except Exception as e:
            print(f"❌ Token exchange failed: {e}")
    else:
        print("\n❌ Failed to get authorization code.")

if __name__ == "__main__":
    run_reauth()
