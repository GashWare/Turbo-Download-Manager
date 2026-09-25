"""
Lightweight Background HTTP API Server for Browser Extensions and IPC.
Enables browser extensions (Firefox, Chrome, Edge) to send URLs, cookies, and headers directly to Turbo Download Manager.
"""

from __future__ import annotations
import json
import threading
import urllib.parse
from http.server import HTTPServer, BaseHTTPRequestHandler
from typing import Optional, Callable, Dict, Any


DEFAULT_API_PORT = 9666


class ApiRequestHandler(BaseHTTPRequestHandler):
    """Handles HTTP requests from browser extensions and local CLI."""

    server_ref: Optional[ApiServer] = None

    def _send_cors_headers(self) -> None:
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization, X-Requested-With")

    def do_OPTIONS(self) -> None:
        self.send_response(204)
        self._send_cors_headers()
        self.end_headers()

    def do_GET(self) -> None:
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path.rstrip("/")

        if path in ("", "/health", "/status", "/api/status"):
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self._send_cors_headers()
            self.end_headers()
            resp = {
                "status": "ok",
                "app": "Turbo Download Manager",
                "version": "2.0.0",
                "connected": True
            }
            if self.server_ref and self.server_ref.status_callback:
                try:
                    resp.update(self.server_ref.status_callback())
                except Exception:
                    pass
            self.wfile.write(json.dumps(resp).encode("utf-8"))
        elif path in ("/add", "/api/add"):
            # Support GET query parameter dispatch e.g. /add?url=...
            query = urllib.parse.parse_qs(parsed.query)
            url = query.get("url", [""])[0]
            if url and self.server_ref and self.server_ref.on_add_download:
                data = {
                    "url": url,
                    "filename": query.get("filename", [""])[0] or None,
                    "auto_start": query.get("auto_start", ["true"])[0].lower() == "true",
                    "audio_only": query.get("audio_only", ["false"])[0].lower() == "true"
                }
                self.server_ref.on_add_download(data)
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self._send_cors_headers()
                self.end_headers()
                self.wfile.write(json.dumps({"status": "ok", "message": "Download task queued"}).encode("utf-8"))
            else:
                self.send_response(400)
                self.send_header("Content-Type", "application/json")
                self._send_cors_headers()
                self.end_headers()
                self.wfile.write(json.dumps({"error": "Missing url parameter"}).encode("utf-8"))
        else:
            self.send_response(404)
            self._send_cors_headers()
            self.end_headers()

    def do_POST(self) -> None:
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path.rstrip("/")

        if path in ("/add", "/api/add", "/api/download"):
            try:
                content_length = int(self.headers.get("Content-Length", 0))
                body = self.rfile.read(content_length).decode("utf-8")
                data = json.loads(body) if body else {}

                url = data.get("url", "").strip()
                if not url:
                    self.send_response(400)
                    self.send_header("Content-Type", "application/json")
                    self._send_cors_headers()
                    self.end_headers()
                    self.wfile.write(json.dumps({"error": "Missing URL"}).encode("utf-8"))
                    return

                if self.server_ref and self.server_ref.on_add_download:
                    self.server_ref.on_add_download(data)

                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self._send_cors_headers()
                self.end_headers()
                self.wfile.write(json.dumps({
                    "status": "ok",
                    "success": True,
                    "message": "Download task received and queued in Turbo Download Manager"
                }).encode("utf-8"))
            except Exception as e:
                self.send_response(500)
                self.send_header("Content-Type", "application/json")
                self._send_cors_headers()
                self.end_headers()
                self.wfile.write(json.dumps({"error": str(e)}).encode("utf-8"))
        else:
            self.send_response(404)
            self._send_cors_headers()
            self.end_headers()

    def log_message(self, format, *args):
        # Suppress standard logging to keep terminal clean
        pass


class ApiServer:
    """Embedded HTTP REST Server for Browser Extension integration."""

    def __init__(
        self,
        port: int = DEFAULT_API_PORT,
        on_add_download: Optional[Callable[[Dict[str, Any]], None]] = None,
        status_callback: Optional[Callable[[], Dict[str, Any]]] = None
    ):
        self.port = port
        self.on_add_download = on_add_download
        self.status_callback = status_callback
        self._server: Optional[HTTPServer] = None
        self._thread: Optional[threading.Thread] = None
        self._running = False

    def start(self) -> bool:
        """Starts the local HTTP server in a background daemon thread."""
        try:
            handler_class = ApiRequestHandler
            handler_class.server_ref = self
            self._server = HTTPServer(("127.0.0.1", self.port), handler_class)
            self._running = True
            self._thread = threading.Thread(target=self._server.serve_forever, daemon=True, name="ApiServer")
            self._thread.start()
            return True
        except Exception:
            self._running = False
            return False

    def stop(self) -> None:
        """Stops the local HTTP server."""
        self._running = False
        if self._server:
            try:
                self._server.shutdown()
                self._server.server_close()
            except Exception:
                pass


def send_url_to_running_instance(url: str, port: int = DEFAULT_API_PORT, data: Optional[dict] = None) -> bool:
    """Helper to check if a local instance is running and forward a download request."""
    import urllib.request
    try:
        payload = data or {"url": url}
        if "url" not in payload:
            payload["url"] = url
        req = urllib.request.Request(
            f"http://127.0.0.1:{port}/add",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST"
        )
        with urllib.request.urlopen(req, timeout=1.5) as resp:
            if resp.status == 200:
                return True
    except Exception:
        pass
    return False
