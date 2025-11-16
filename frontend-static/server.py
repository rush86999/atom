import http.server
import json
import socketserver
import time
from http import HTTPStatus


class StaticFrontendHandler(http.server.SimpleHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/":
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-type", "text/html")
            self.end_headers()

            html_content = """
            <!DOCTYPE html>
            <html lang="en">
            <head>
                <meta charset="UTF-8">
                <meta name="viewport" content="width=device-width, initial-scale=1.0">
                <title>ATOM Agentic OS - Static Frontend</title>
                <style>
                    body {
                        font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
                        margin: 0;
                        padding: 0;
                        background-color: #f9fafb;
                        color: #111827;
                    }
                    .container {
                        max-width: 1200px;
                        margin: 0 auto;
                        padding: 2rem;
                    }
                    .header {
                        text-align: center;
                        margin-bottom: 3rem;
                    }
                    .title {
                        font-size: 3rem;
                        font-weight: bold;
                        margin-bottom: 1rem;
                        color: #1f2937;
                    }
                    .subtitle {
                        font-size: 1.25rem;
                        color: #6b7280;
                        margin-bottom: 2rem;
                    }
                    .status-grid {
                        display: grid;
                        grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
                        gap: 1.5rem;
                        margin-bottom: 3rem;
                    }
                    .status-card {
                        background: white;
                        border-radius: 0.75rem;
                        padding: 1.5rem;
                        box-shadow: 0 1px 3px rgba(0, 0, 0, 0.1);
                        border: 1px solid #e5e7eb;
                    }
                    .status-card.healthy {
                        border-left: 4px solid #10b981;
                    }
                    .status-card.warning {
                        border-left: 4px solid #f59e0b;
                    }
                    .status-card.error {
                        border-left: 4px solid #ef4444;
                    }
                    .status-title {
                        font-weight: 600;
                        font-size: 1.125rem;
                        margin-bottom: 0.5rem;
                    }
                    .status-value {
                        font-size: 1rem;
                        color: #6b7280;
                    }
                    .info-section {
                        background: white;
                        border-radius: 0.75rem;
                        padding: 1.5rem;
                        box-shadow: 0 1px 3px rgba(0, 0, 0, 0.1);
                        margin-bottom: 2rem;
                    }
                    .info-grid {
                        display: grid;
                        grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
                        gap: 1rem;
                    }
                    .info-item {
                        display: flex;
                        justify-content: space-between;
                        padding: 0.5rem 0;
                        border-bottom: 1px solid #f3f4f6;
                    }
                    .button {
                        background-color: #3b82f6;
                        color: white;
                        padding: 0.75rem 1.5rem;
                        border: none;
                        border-radius: 0.5rem;
                        font-size: 1rem;
                        cursor: pointer;
                        transition: background-color 0.2s;
                    }
                    .button:hover {
                        background-color: #2563eb;
                    }
                    .footer {
                        text-align: center;
                        margin-top: 3rem;
                        padding-top: 2rem;
                        border-top: 1px solid #e5e7eb;
                        color: #6b7280;
                    }
                </style>
            </head>
            <body>
                <div class="container">
                    <div class="header">
                        <h1 class="title">ATOM Agentic OS</h1>
                        <p class="subtitle">Static Frontend for E2E Testing</p>
                    </div>

                    <div class="status-grid">
                        <div class="status-card healthy">
                            <div class="status-title">Frontend</div>
                            <div class="status-value">Operational</div>
                        </div>
                        <div class="status-card healthy">
                            <div class="status-title">Backend API</div>
                            <div class="status-value">Connected</div>
                        </div>
                        <div class="status-card warning">
                            <div class="status-title">Agent Orchestration</div>
                            <div class="status-value">Not Available</div>
                        </div>
                    </div>

                    <div class="info-section">
                        <h2 style="margin-bottom: 1rem;">System Information</h2>
                        <div class="info-grid">
                            <div class="info-item">
                                <span>Version</span>
                                <span>1.0.0</span>
                            </div>
                            <div class="info-item">
                                <span>Environment</span>
                                <span>Development</span>
                            </div>
                            <div class="info-item">
                                <span>Last Updated</span>
                                <span id="timestamp">Loading...</span>
                            </div>
                            <div class="info-item">
                                <span>Uptime</span>
                                <span id="uptime">Loading...</span>
                            </div>
                        </div>
                    </div>

                    <div style="text-align: center;">
                        <button class="button" onclick="refreshStatus()">Refresh Status</button>
                    </div>

                    <div class="footer">
                        <p>ATOM Agentic OS &copy; 2025 - Static Frontend for E2E Testing</p>
                    </div>
                </div>

                <script>
                    function updateTimestamp() {
                        document.getElementById('timestamp').textContent = new Date().toLocaleString();
                        document.getElementById('uptime').textContent = Math.floor(performance.now() / 1000) + ' seconds';
                    }

                    function refreshStatus() {
                        updateTimestamp();
                        // Simulate API call
                        fetch('/api/health')
                            .then(response => response.json())
                            .then(data => {
                                console.log('Health check successful:', data);
                            })
                            .catch(error => {
                                console.log('Health check failed:', error);
                            });
                    }

                    // Initial update
                    updateTimestamp();
                    setInterval(updateTimestamp, 1000);
                </script>
            </body>
            </html>
            """
            self.wfile.write(html_content.encode("utf-8"))

        elif self.path == "/api/health":
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-type", "application/json")
            self.end_headers()

            health_data = {
                "status": "healthy",
                "service": "atom-frontend-static",
                "version": "1.0.0",
                "timestamp": time.time(),
                "uptime": time.time() - self.server.start_time,
                "environment": "development",
                "features": {
                    "backend": True,
                    "api": True,
                    "health": True,
                    "static": True,
                },
            }

            self.wfile.write(json.dumps(health_data).encode("utf-8"))

        elif self.path == "/health":
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-type", "text/plain")
            self.end_headers()
            self.wfile.write(b"OK")

        else:
            self.send_response(HTTPStatus.NOT_FOUND)
            self.send_header("Content-type", "text/plain")
            self.end_headers()
            self.wfile.write(b"404 - Not Found")


def run_server(port=3001):
    class Server(socketserver.TCPServer):
        def __init__(self, *args, **kwargs):
            self.start_time = time.time()
            super().__init__(*args, **kwargs)

    with Server(("", port), StaticFrontendHandler) as httpd:
        print(f"🌐 Static frontend server running on http://localhost:{port}")
        print(f"📁 Serving static HTML frontend for E2E testing")
        print(f"🔧 Available endpoints:")
        print(f"   - GET / (HTML frontend)")
        print(f"   - GET /api/health (JSON health check)")
        print(f"   - GET /health (Simple health check)")
        print(f"Press Ctrl+C to stop the server")

        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\n🛑 Server stopped")


if __name__ == "__main__":
    run_server()
