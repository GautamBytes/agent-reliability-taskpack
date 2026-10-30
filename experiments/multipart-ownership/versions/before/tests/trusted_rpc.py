import atexit
import base64
import json
import os
from pathlib import Path
import select
import signal
import subprocess
import sys
import tempfile
import time


class RequestEntityTooLarge(Exception):
    pass


def pack(value):
    return base64.b64encode(value).decode()


def unpack(value):
    return base64.b64decode(value, validate=True)


_worker = None
_errors = None


def close():
    global _worker
    if _worker is not None:
        try:
            os.killpg(_worker.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        _worker.wait(timeout=5)
        _worker = None


atexit.register(close)


def call(operation, **arguments):
    global _worker, _errors
    if _worker is None:
        _errors = tempfile.TemporaryFile()
        env = {"PATH": os.environ.get("PATH", "/usr/local/bin:/usr/bin:/bin"), "LANG": "C.UTF-8", "HOME": "/nonexistent", "TASK_REPO": os.environ["TASK_REPO"], "TASK_WORKER_UID": os.environ.get("TASK_WORKER_UID", str(os.getuid()))}
        _worker = subprocess.Popen([sys.executable, "-I", str(Path(__file__).with_name("worker.py"))], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=_errors, env=env, start_new_session=True, bufsize=0)
    request = json.dumps({"operation": operation, **arguments}).encode() + b"\n"
    try:
        _worker.stdin.write(request)
        _worker.stdin.flush()
        response = bytearray()
        deadline = time.monotonic() + 4
        while not response.endswith(b"\n"):
            remaining = deadline - time.monotonic()
            if remaining <= 0 or not select.select([_worker.stdout], [], [], max(0, remaining))[0]:
                raise TimeoutError("Candidate worker response deadline exceeded")
            chunk = os.read(_worker.stdout.fileno(), 65536)
            if not chunk:
                raise RuntimeError("Candidate worker exited without a response")
            response.extend(chunk)
            if len(response) > 2 * 1024 * 1024:
                raise RuntimeError("Candidate worker output exceeded its limit")
        result = json.loads(response)
    except BaseException:
        close()
        raise
    if "error" in result:
        error = result["error"]
        if error["type"] == "RequestEntityTooLarge":
            raise RequestEntityTooLarge(error["message"])
        if error["type"] == "ValueError":
            raise ValueError(error["message"])
        raise RuntimeError(error)
    return result["value"]


def decoded(boundary, chunks):
    result = call("decode", boundary=pack(boundary), chunks=[pack(chunk) for chunk in chunks])
    return [(name, filename, unpack(data)) for name, filename, data in result]
