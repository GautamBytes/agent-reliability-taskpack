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


class ProbeAbort(BaseException):
    pass


class ProbeInput(ShortReads):
    def __init__(self, data, maximum, injected, fail_at=None):
        super().__init__(data, maximum)
        self.injected = injected
        self.fail_at = fail_at
        self.close_calls = 0

    def read(self, size=-1):
        if self.fail_at is not None and self.tell() >= self.fail_at:
            raise self.injected
        return super().read(size)

    def readinto(self, buffer):
        if self.fail_at is not None and self.tell() >= self.fail_at:
            raise self.injected
        return super().readinto(buffer)

    def close(self):
        self.close_calls += 1
        super().close()


class ProbeSink(io.BytesIO):
    def __init__(self, index, settings, injected):
        super().__init__()
        self.index = index
        self.settings = settings
        self.injected = injected
        self.accepted = bytearray()
        self.write_calls = 0
        self.close_calls = 0

    def write(self, data):
        self.write_calls += 1
        value = bytes(data)
        if self.index == self.settings.get("write_error_sink"):
            raise self.injected
        invalid = self.settings.get("invalid_write")
        if invalid is not None:
            values = {"zero": 0, "none": None, "negative": -1, "float": 1.5, "bool": True, "oversized": len(value) + 1}
            return values[invalid]
        maximum = self.settings.get("short_write")
        if maximum is not None:
            value = value[:maximum]
        self.accepted.extend(value)
        return super().write(value)

    def seek(self, *arguments):
        if self.index == self.settings.get("seek_error_sink"):
            raise self.injected
        return super().seek(*arguments)

    def close(self):
        self.close_calls += 1
        if self.index in self.settings.get("close_error_sinks", []):
            if self.settings.get("close_base_exception"):
                raise ProbeAbort("cleanup failed")
            raise OSError("cleanup failed")
        super().close()


def ownership_operation(command):
    from werkzeug.datastructures import FileStorage, MultiDict
    from werkzeug.formparser import MultiPartParser, parse_form_data

    settings = command.get("settings", {})
    injected = ProbeAbort("original abort") if settings.get("base_exception") else ValueError("original value") if settings.get("value_exception") else OSError("original I/O")
    sinks = []
    factory_calls = 0
    collection_calls = 0

    def factory(*arguments, **keywords):
        nonlocal factory_calls
        factory_calls += 1
        if factory_calls == settings.get("factory_error_call"):
            raise injected
        if settings.get("shared_sink") and sinks:
            return sinks[0]
        sink = ProbeSink(len(sinks), settings, injected)
        sinks.append(sink)
        return sink

    class ProbeCollection(MultiDict):
        def __init__(self, *arguments, **keywords):
            nonlocal collection_calls
            collection_calls += 1
            if collection_calls == settings.get("collection_error_call"):
                raise injected
            super().__init__(*arguments, **keywords)

    class ProbeRequest(Request):
        def _get_file_stream(self, total_content_length, content_type, filename=None, content_length=None):
            return factory(total_content_length=total_content_length, content_type=content_type, filename=filename, content_length=content_length)

    def observations():
        return [{"payload": pack(bytes(sink.accepted)), "close_calls": sink.close_calls, "closed": sink.closed, "write_calls": sink.write_calls} for sink in sinks]

    if command["operation"] == "api-contract":
        import inspect
        signatures = {}
        for name, target in (("multipart", MultiPartParser), ("form", FormDataParser), ("convenience", parse_form_data)):
            parameters = inspect.signature(target).parameters
            signatures[name] = {key: {"kind": parameters[key].kind.name, "default": parameters[key].default} if key in parameters else None for key in ("max_file_size", "max_form_data_size")}
        return {"signatures": signatures, "request_defaults": {key: getattr(Request, key, "missing") for key in ("max_file_size", "max_form_data_size")}}
    path = command.get("path", "multipart")
    limits = command.get("limits", {})
    if command["operation"] == "validate-limits":
        try:
            if path == "multipart":
                MultiPartParser(**limits)
            elif path == "form":
                FormDataParser(silent=True, **limits)
            elif path == "request":
                request = ProbeRequest({})
                for key, value in limits.items():
                    setattr(request, key, value)
                request.make_form_data_parser()
            else:
                parse_form_data({"wsgi.input": io.BytesIO(), "REQUEST_METHOD": "POST", "CONTENT_TYPE": "text/plain", "CONTENT_LENGTH": "0"}, silent=True, **limits)
        except BaseException as error:
            return {"error": type(error).__name__}
        return {"error": None}

    if command["operation"] == "request-close":
        sink_settings = dict(settings)
        for index in range(3):
            sinks.append(ProbeSink(index, sink_settings, injected))
        request = ProbeRequest({"wsgi.input": io.BytesIO(b"borrowed")})
        if not settings.get("uncached"):
            request.__dict__["files"] = MultiDict([("duplicate", FileStorage(sinks[0], "first")), ("duplicate", FileStorage(sinks[1], "second")), ("shared", FileStorage(sinks[0], "third")), ("other", FileStorage(sinks[2], "fourth"))])
        errors = []
        rounds = []
        for _ in range(command.get("close_rounds", 1)):
            try:
                request.close()
                errors.append(None)
            except BaseException as error:
                errors.append(type(error).__name__)
            rounds.append(observations())
        return {"rounds": rounds, "errors": errors, "input_closed": request.environ["wsgi.input"].closed, "factory_calls": factory_calls, "files_cached": "files" in request.__dict__}

    encoded_bodies = command.get("bodies", [command.get("body")])
    streams = [ProbeInput(unpack(encoded), command.get("maximum", 7), injected, settings.get("read_error_at")) for encoded in encoded_bodies]
    parser = None
    try:
        if path == "multipart":
            parser = MultiPartParser(stream_factory=factory, cls=ProbeCollection, buffer_size=command.get("buffer_size", 64), **limits)
        elif path == "form":
            parser = FormDataParser(stream_factory=factory, cls=ProbeCollection, silent=command.get("silent", False), **limits)
    except BaseException as error:
        return {"rounds": [{"error": {"type": type(error).__name__, "is_original": error is injected, "message": str(error)}, "fields": [], "files": [], "sinks": observations(), "new_sinks": len(sinks), "input_closed": streams[0].closed, "input_close_calls": streams[0].close_calls, "read_calls": streams[0].calls}], "factory_calls": factory_calls}
    rounds = []
    for encoded, stream in zip(encoded_bodies, streams):
        body = unpack(encoded)
        request = None
        error_info = None
        fields = []
        files = []
        before_sinks = len(sinks)
        declared = command.get("content_length", len(body))
        environ = {"wsgi.input": stream, "REQUEST_METHOD": "POST", "CONTENT_TYPE": command.get("content_type", "multipart/form-data; boundary=ownership"), "wsgi.url_scheme": "http", "SERVER_NAME": "localhost", "SERVER_PORT": "80"}
        if declared is not None:
            environ["CONTENT_LENGTH"] = str(declared)
        else:
            environ["wsgi.input_terminated"] = True
        try:
            if path == "multipart":
                form, result_files = parser.parse(stream, b"ownership", declared)
            elif path == "form":
                _, form, result_files = parser.parse(stream, command.get("mimetype", "multipart/form-data"), declared, {"boundary": "ownership"})
            elif path == "convenience":
                _, form, result_files = parse_form_data(environ, stream_factory=factory, cls=ProbeCollection, silent=command.get("silent", False), **limits)
            else:
                request = ProbeRequest(environ)
                for key, value in limits.items():
                    setattr(request, key, value)
                form, result_files = request.form, request.files
            fields = list(form.items(multi=True))
            files = [[name, storage.filename, pack(storage.read())] for name, storage in result_files.items(multi=True)]
        except BaseException as error:
            error_info = {"type": type(error).__name__, "is_original": error is injected, "message": str(error)}
        rounds.append({"error": error_info, "fields": fields, "files": files, "sinks": observations(), "new_sinks": len(sinks) - before_sinks, "input_closed": stream.closed, "input_close_calls": stream.close_calls, "read_calls": stream.calls})
    return {"rounds": rounds, "factory_calls": factory_calls}


def operation(command):
    name = command["operation"]
    if name in {"owned-parse", "validate-limits", "request-close", "api-contract"}:
        return ownership_operation(command)
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
