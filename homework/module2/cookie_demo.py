from http.server import BaseHTTPRequestHandler, HTTPServer

PAGE = b"""<!doctype html><meta charset=utf-8><title>HttpOnly demo</title>
<pre id=out></pre>
<script>
document.getElementById('out').textContent =
  'document.cookie = "' + document.cookie + '"';
</script>"""


class H(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Set-Cookie", "session_id=s3cr3t-abc123; Path=/; HttpOnly; SameSite=Lax")
        self.send_header("Set-Cookie", "theme=dark; Path=/; SameSite=Lax")
        self.send_header("Content-Length", str(len(PAGE)))
        self.end_headers()
        self.wfile.write(PAGE)
    def log_message(self, *a): pass

    
HTTPServer(("127.0.0.1", 8001), H).serve_forever()
