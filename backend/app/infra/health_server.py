"""Tiny HTTP health server for background workers.

Runs in a daemon thread on a secondary port so container orchestrators
can probe worker liveness independently of the main RQ / polling loop.
"""

from __future__ import annotations

import threading
from http.server import BaseHTTPRequestHandler, HTTPServer


def start_health_server(port: int, name: str) -> None:
    """Start a daemon HTTP server on the given port.

    Responds 200 OK at GET /health and 404 on all other paths.
    Runs in a daemon thread so it does not prevent process shutdown.
    """

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            if self.path == "/health":
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(b'{"status":"ok"}')
            else:
                self.send_response(404)
                self.end_headers()

        def log_message(self, fmt, *args):
            pass  # suppress stderr access-log noise

    server = HTTPServer(("0.0.0.0", port), Handler)

    thread = threading.Thread(
        target=server.serve_forever,
        daemon=True,
        name=f"health-server-{name}",
    )
    thread.start()
