from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import select
import socket
import threading
from urllib.parse import urlsplit


LOG = Path("/logs/proxy/connections.jsonl")
LOCK = threading.Lock()
ALLOWED_SUFFIXES = ("openai.com", "chatgpt.com")


def record(host, decision):
    row = {"time": datetime.now(timezone.utc).isoformat(), "host": host, "decision": decision}
    with LOCK:
        with LOG.open("a") as output:
            output.write(json.dumps(row) + "\n")


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, *args):
        pass

    def do_GET(self):
        body = b"ok\n" if self.path == "/health" else b"not found\n"
        self.send_response(200 if self.path == "/health" else 404)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_CONNECT(self):
        try:
            address = urlsplit("//" + self.path)
            host = (address.hostname or "").lower().rstrip(".")
            permitted = address.port == 443 and address.username is None and address.password is None and any(
                host == suffix or host.endswith("." + suffix) for suffix in ALLOWED_SUFFIXES
            )
        except ValueError:
            host, permitted = "invalid-address", False
        if not permitted:
            record(host, "deny")
            self.send_error(403, "Only model and authentication endpoints are allowed")
            return
        try:
            remote = socket.create_connection((host, 443), timeout=30)
        except OSError:
            record(host, "connect-failed")
            self.send_error(502, "Model endpoint unavailable")
            return
        record(host, "allow")
        self.send_response(200, "Connection established")
        self.end_headers()
        self.wfile.flush()
        self.connection.settimeout(30)
        remote.settimeout(30)
        try:
            while True:
                readable, _, _ = select.select([self.connection, remote], [], [], 120)
                if not readable:
                    return
                for source in readable:
                    chunk = source.recv(65536)
                    if not chunk:
                        return
                    target = remote if source is self.connection else self.connection
                    target.sendall(chunk)
        except OSError:
            return
        finally:
            remote.close()
            self.close_connection = True


if __name__ == "__main__":
    LOG.parent.mkdir(parents=True, exist_ok=True)
    ThreadingHTTPServer(("0.0.0.0", 3128), Handler).serve_forever()
