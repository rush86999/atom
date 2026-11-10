"""Owned loopback TLS termination fixture, not a production networking change."""
from pathlib import Path
import ssl,http.server,http.client,json,os
root=Path('/private/tmp/root-web-https-cookie-proof-20261109')
assert json.loads((root/'owner-marker.json').read_text())['no_system_trust_change']
class Proxy(http.server.BaseHTTPRequestHandler):
    protocol_version='HTTP/1.1'
    def log_message(self,*args):pass
    def forward(self):
        connection=http.client.HTTPConnection('127.0.0.1',18182,timeout=25)
        try:
            length=int(self.headers.get('Content-Length','0'))
            if length>2*1024*1024:self.send_error(413);return
            body=self.rfile.read(length) if length else None
            headers={k:v for k,v in self.headers.items() if k.lower() not in ['connection','transfer-encoding','content-length','x-forwarded-proto','x-forwarded-host']}
            headers['Host']='127.0.0.1:18184';headers['X-Forwarded-Proto']='https';headers['X-Forwarded-Host']='127.0.0.1:18184'
            connection.request(self.command,self.path,body=body,headers=headers)
            result=connection.getresponse();data=result.read();self.send_response(result.status)
            for key,value in result.getheaders():
                if key.lower() not in ['transfer-encoding','connection','content-length']:self.send_header(key,value)
            self.send_header('Content-Length',str(len(data)));self.end_headers();self.wfile.write(data)
        except (OSError,http.client.HTTPException):
            self.send_error(503,'Owned upstream unavailable')
        finally:connection.close()
    do_GET=forward;do_POST=forward
server=http.server.ThreadingHTTPServer(('127.0.0.1',18184),Proxy)
context=ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER);context.load_cert_chain(str(root/'server.crt'),str(root/'server.private.key'))
server.socket=context.wrap_socket(server.socket,server_side=True)
(root/'proxy.pid').write_text(str(os.getpid()));print(json.dumps({'owned_tls_proxy_pid':os.getpid(),'listen':18184,'upstream':18182,'cert_trust':'explicit fixture CA only; no system change'}),flush=True)
server.serve_forever()
