#!/usr/bin/env python3
"""
Minimal test backend for E2E testing
"""
import json
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs

class TestAPIHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        """Handle GET requests"""
        parsed_path = urlparse(self.path)
        
        # Health check
        if self.path == '/healthz':
            self._send_json_response({"status": "ok"})
        elif self.path == '/api/v1/services':
            self._send_json_response({
                "services": [
                    {"name": "test_service", "status": "active", "type": "mock"}
                ]
            })
        else:
            self._send_404()
    
    def do_POST(self):
        """Handle POST requests"""
        parsed_path = urlparse(self.path)
        
        if self.path == '/api/v1/services':
            self._send_json_response({"message": "Service created"})
        else:
            self._send_404()
    
    def _send_json_response(self, data, status=200):
        """Send JSON response"""
        self.send_response(status)
        self.send_header('Content-type', 'application/json')
        self.end_headers()
        self.wfile.write(json.dumps(data).encode())
    
    def _send_404(self):
        """Send 404 response"""
        self.send_response(404)
        self.send_header('Content-type', 'application/json')
        self.end_headers()
        self.wfile.write(json.dumps({"error": "Not found"}).encode())

def run_server():
    """Run the test server"""
    server_address = ('', 5058)
    httpd = HTTPServer(server_address, TestAPIHandler)
    print("🚀 Test server running on http://localhost:5058")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n🛑 Server stopped")
        httpd.server_close()

if __name__ == "__main__":
    run_server()