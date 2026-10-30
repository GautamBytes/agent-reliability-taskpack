import base64
import io
import json
import os
from pathlib import Path
import resource
import sys


repo = Path(os.environ["TASK_REPO"])
uid = int(os.environ["TASK_WORKER_UID"])
resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
resource.setrlimit(resource.RLIMIT_FSIZE, (8 * 1024 * 1024, 8 * 1024 * 1024))
if os.geteuid() == 0:
    os.setgroups([])
    os.setgid(uid)
    os.setuid(uid)
os.chdir(repo)
sys.path.insert(0, str(repo / "src"))

from werkzeug.formparser import FormDataParser
from werkzeug.sansio.multipart import Data, Epilogue, Field, File, MultipartDecoder, NeedData
from werkzeug.wrappers import Request


def unpack(value):
    return base64.b64decode(value, validate=True)


def pack(value):
    return base64.b64encode(value).decode()


class ShortReads(io.BytesIO):
    def __init__(self, data, maximum):
        super().__init__(data)
        self.maximum = maximum
        self.calls = 0

    def read(self, size=-1):
        self.calls += 1
        amount = self.maximum if size < 0 else min(size, self.maximum)
        return super().read(amount)

    def readinto(self, buffer):
        self.calls += 1
        return super().readinto(memoryview(buffer)[:self.maximum])


def operation(command):
    name = command["operation"]
    if name == "decode":
        decoder = MultipartDecoder(unpack(command["boundary"]))
        parts = []
        ended = False
        for chunk in [*[unpack(value) for value in command["chunks"]], None]:
            decoder.receive_data(chunk)
            while True:
                event = decoder.next_event()
                if isinstance(event, NeedData):
                    break
                if isinstance(event, (Field, File)):
                    parts.append([event.name, getattr(event, "filename", None), bytearray()])
                elif isinstance(event, Data):
                    if not parts:
                        raise ValueError("Data before a part")
                    parts[-1][2].extend(event.data)
                elif isinstance(event, Epilogue):
                    ended = True
                    break
            if ended:
                break
        if not ended:
            raise ValueError("No completed epilogue")
        return [[key, filename, pack(bytes(value))] for key, filename, value in parts]
    if name in {"probe-decode", "stream-fragments"}:
        decoder = MultipartDecoder(unpack(command["boundary"]))
        parts = []
        ended = False
        completed_part = False

        def consume(chunk):
            nonlocal ended, completed_part
            decoder.receive_data(chunk)
            while True:
                event = decoder.next_event()
                if isinstance(event, NeedData):
                    return
                if isinstance(event, (Field, File)):
                    parts.append([event.name, getattr(event, "filename", None), bytearray()])
                elif isinstance(event, Data):
                    if not parts:
                        raise ValueError("Data before a part")
                    parts[-1][2].extend(event.data)
                    if not event.more_data:
                        completed_part = True
                elif isinstance(event, Epilogue):
                    ended = True
                    return

        if name == "probe-decode":
            consume(unpack(command["prefix"]))
            ended_before_suffix = ended
            part_completed_before_suffix = completed_part
            consume(unpack(command["suffix"]))
            consume(None)
            if not ended:
                raise ValueError("No completed epilogue")
            return {"ended_before_suffix": ended_before_suffix, "part_completed_before_suffix": part_completed_before_suffix, "parts": [[key, filename, pack(bytes(value))] for key, filename, value in parts]}
        for value in command["chunks"]:
            consume(unpack(value))
        return {"ended": ended, "payload": pack(b"".join(bytes(part[2]) for part in parts))}
    if name in {"form-parts", "request-parts"}:
        boundary = unpack(command["boundary"]).decode("ascii")
        body = unpack(command["body"])
        stream = ShortReads(body, command["maximum"])
        if name == "form-parts":
            parser = FormDataParser(silent=False)
            _, fields, files = parser.parse(stream, "multipart/form-data", len(body), {"boundary": boundary})
            result = {"fields": list(fields.items(multi=True)), "files": [[key, value.filename, value.content_type, pack(value.read())] for key, value in files.items(multi=True)], "read_calls": stream.calls}
            for value in files.values():
                value.close()
            return result
        with Request.from_values(input_stream=stream, content_length=len(body), content_type='multipart/form-data; boundary="' + boundary + '"', method="POST") as request:
            return {"fields": list(request.form.items(multi=True)), "files": [[key, value.filename, value.content_type, pack(value.read())] for key, value in request.files.items(multi=True)], "read_calls": stream.calls}
    if name == "generated-request":
        payload = unpack(command["payload"])
        with Request.from_values(data={"upload": (io.BytesIO(payload), "binary.bin"), "label": "unchanged"}, method="POST") as request:
            return {"file": pack(request.files["upload"].read()), "label": request.form["label"]}
    if name == "fragmented-request":
        body = unpack(command["body"])
        stream = ShortReads(body, command["maximum"])
        with Request.from_values(input_stream=stream, content_length=len(body), content_type="multipart/form-data; boundary=separate-stream", method="POST") as request:
            return {"title": request.form["title"], "file": pack(request.files["upload"].read()), "read_calls": stream.calls}
    if name == "strict-form":
        body = unpack(command["body"])
        parser = FormDataParser(max_form_parts=command["max_parts"], silent=False)
        parser.parse(io.BytesIO(body), "multipart/form-data", len(body), {"boundary": command["boundary"]})
        return {"completed": True}
    if name == "memory-limit":
        MultipartDecoder(b"limit", max_form_memory_size=command["maximum"]).receive_data(b"x" * command["size"])
        return {"completed": True}
    if name == "stream-progress":
        decoder = MultipartDecoder(unpack(command["boundary"]))
        decoder.receive_data(unpack(command["body"]))
        emitted = 0
        while True:
            event = decoder.next_event()
            if isinstance(event, Data):
                emitted += len(event.data)
            if isinstance(event, NeedData):
                break
        return {"emitted_bytes": emitted}
    raise ValueError("Unknown worker operation")


for line in sys.stdin:
    try:
        response = {"value": operation(json.loads(line))}
    except Exception as error:
        response = {"error": {"type": type(error).__name__, "message": str(error)}}
    print(json.dumps(response), flush=True)
