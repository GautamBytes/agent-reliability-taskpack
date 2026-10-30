import http.client
import json
import os
from pathlib import Path
import socket
from urllib.parse import urlsplit


proxy = urlsplit(os.environ["HTTPS_PROXY"])
connection = http.client.HTTPConnection(proxy.hostname, proxy.port, timeout=3)
connection.request("CONNECT", "github.com:443")
reply = connection.getresponse()
denied = reply.status == 403
reply.read()
connection.close()
direct_blocked = False
try:
    with socket.create_connection(("1.1.1.1", 443), timeout=1):
        pass
except OSError:
    direct_blocked = True
result = {"github_proxy_denied": denied, "direct_internet_blocked": direct_blocked}
if not all(result.values()):
    raise SystemExit(json.dumps(result))
Path("/app/repo/.network-boundary.json").write_text(json.dumps(result, indent=2) + "\n")
