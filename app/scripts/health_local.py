"""Alternativa HTTP explícita, independiente de API Gateway y MiniStack."""
from http.server import BaseHTTPRequestHandler, HTTPServer
from lambdas.health.handler import main as handler


class HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path != "/health":
            self.send_error(404)
            return
        response = handler({}, None)
        self.send_response(response["statusCode"])
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(response["body"].encode())


if __name__ == "__main__":
    print("Alternativa HTTP local: http://127.0.0.1:8080/health (sin API Gateway)", flush=True)
    HTTPServer(("127.0.0.1", 8080), HealthHandler).serve_forever()
