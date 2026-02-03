import http.server
import os
import socketserver
import threading

PORT = 8083

class MockBankHandler(http.server.SimpleHTTPRequestHandler):
    def do_POST(self):
        # Handle Login Simulation
        if self.path == "/login":
            length = int(self.headers['Content-Length'])
            post_data = self.rfile.read(length).decode('utf-8')
            
            # Simple check
            if "username=admin" in post_data and "password=1234" in post_data:
                self.send_response(303)
                self.send_header('Location', '/dashboard.html')
                self.end_headers()
            else:
                self.send_response(401)
                self.end_headers()
                self.wfile.write(b"Invalid Credentials")
        else:
            super().do_POST()

    def do_GET(self):
        # Serve PDF as attachment to force download
        if self.path.endswith(".pdf"):
            # We must use send_head() logic or manual file serving to inject headers *before* body
            # SimpleHTTPRequestHandler.do_GET calls send_head()
            # But overriding send_head is complex.
            # Easiest way: call super().send_head(), capture return, add header? No, content sent.
            
            # Manual overwrite for PDF
            f = self.send_head()
            if f:
                try:
                    self.copyfile(f, self.wfile)
                finally:
                    f.close()
        else:
            super().do_GET()

    def end_headers(self):
        if self.path.endswith(".pdf"):
            self.send_header("Content-Disposition", 'attachment; filename="statement.pdf"')
        super().end_headers()

def run_server():
    os.chdir(os.path.dirname(os.path.abspath(__file__)))
    # Explicitly bind to 127.0.0.1 to avoid IPv6 issues
    with socketserver.TCPServer(("127.0.0.1", PORT), MockBankHandler) as httpd:
        print(f"Mock Bank Server serving at port {PORT}")
        httpd.serve_forever()

if __name__ == "__main__":
    run_server()
