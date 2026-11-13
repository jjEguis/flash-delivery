"""Servidor local del frontend: archivos estáticos + proxy same-origin hacia API Gateway.

Lee el ApiId de app/.local/outputs.json (generado por scripts.provision) en cada
solicitud, de modo que reprovisionar no exige reiniciar. Solo biblioteca estándar.
"""
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parent
UPSTREAM = os.getenv("API_UPSTREAM", "http://ministack:4566").rstrip("/")
OUTPUTS = Path(os.getenv("OUTPUTS_FILE", ROOT.parent / "app" / ".local" / "outputs.json"))
FORWARD = ("authorization", "content-type", "idempotency-key")
MAX_BODY = 64 * 1024


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(ROOT), **kwargs)

    def end_headers(self):
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        super().end_headers()

    def _proxy(self):
        try:
            api_id = json.loads(OUTPUTS.read_text())["ApiId"]
        except (OSError, ValueError, KeyError):
            return self._json(503, {"error": {"code": "API_NOT_PROVISIONED", "requestId": "-",
                                              "message": "Ejecuta scripts.provision antes de abrir el frontend"}})
        length = int(self.headers.get("Content-Length") or 0)
        if length > MAX_BODY:
            return self._json(413, {"error": {"code": "INVALID_INPUT", "message": "Cuerpo demasiado grande", "requestId": "-"}})
        body = self.rfile.read(length) if length else None
        headers = {name: self.headers[name] for name in FORWARD if self.headers.get(name)}
        request = Request(f"{UPSTREAM}/_aws/execute-api/{api_id}/local{self.path}", data=body,
                          headers=headers, method=self.command)
        try:
            with urlopen(request, timeout=60) as response:
                status, payload, kind = response.status, response.read(), response.headers.get("Content-Type")
        except HTTPError as error:
            status, payload, kind = error.code, error.read(), error.headers.get("Content-Type")
        except URLError:
            return self._json(503, {"error": {"code": "DEPENDENCY_UNAVAILABLE", "requestId": "-",
                                              "message": "MiniStack no responde; revisa docker compose"}})
        self.send_response(status)
        self.send_header("Content-Type", kind or "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(payload)

    def _json(self, status, body):
        payload = json.dumps(body).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def do_GET(self):
        if self.path.startswith("/api/"):
            return self._proxy()
        if self.path == "/" or not (ROOT / self.path.split("?")[0].lstrip("/")).is_file():
            self.path = "/index.html"  # SPA con rutas por hash
        return super().do_GET()

    do_POST = do_PATCH = do_DELETE = _proxy

    def log_message(self, fmt, *args):
        if "/api/" in (args[0] if args else ""):
            super().log_message(fmt, *args)


if __name__ == "__main__":
    port = int(os.getenv("PORT", "8080"))
    print(f"FlashDelivery web en http://127.0.0.1:{port}")
    ThreadingHTTPServer(("0.0.0.0", port), Handler).serve_forever()
