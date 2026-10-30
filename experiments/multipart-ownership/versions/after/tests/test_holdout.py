import io
import random
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
from trusted_rpc import call, decoded, unpack, pack, RequestEntityTooLarge


def message(boundary, parts):
    body = b""
    for name, filename, payload in parts:
        body += b"--" + boundary + b"\r\nContent-Disposition: form-data; name=\"" + name.encode() + b'"'
        if filename is not None:
            body += b'; filename="' + filename.encode() + b'"'
        body += b"\r\nContent-Type: application/octet-stream\r\n\r\n" + payload + b"\r\n"
    return body + b"--" + boundary + b"--\r\n"


PAYLOADS = [b"", b"\r", b"\n", b"\r\n", b"\r\r", b"\n\r", b"a\r", b"a\r\n", b"\r\nbinary\0\xff\r\n", bytes(range(256))]


@pytest.mark.parametrize("payload", PAYLOADS, ids=["empty", "cr", "lf", "crlf", "double-cr", "lf-cr", "tail-cr", "tail-crlf", "binary-newlines", "all-bytes"])
def test_regression_every_single_split_preserves_file_bytes(payload):
    boundary = b"boundary.A+1"
    expected = [("upload", "data.bin", payload)]
    body = message(boundary, expected)
    for split in range(1, len(body)):
        assert decoded(boundary, [body[:split], body[split:]]) == expected, split


@pytest.mark.parametrize("size", [1, 2, 3, 7, 13, 64])
def test_regression_fixed_fragment_sizes_preserve_mixed_parts(size):
    boundary = b"long-boundary-1423"
    expected = [("metadata", None, "हैलो\r\n".encode()), ("file", "binary.bin", b"\r\n\0\xff\r\n--long-boundary-1423X\r"), ("empty", None, b"")]
    body = message(boundary, expected)
    assert decoded(boundary, [body[i:i+size] for i in range(0, len(body), size)]) == expected


@pytest.mark.parametrize("seed", [173, 691, 1187])
def test_regression_seeded_partitions_preserve_boundary_lookalikes(seed):
    boundary = b"test-boundary"
    payload = b"\r\n--test-boundarX\n\r\n--test-boundary!\r\nabc\r\n"
    expected = [("file", "f.bin", payload), ("meta", None, b"tail\r")]
    body = message(boundary, expected)
    rng = random.Random(seed)
    for _ in range(25):
        chunks = []
        position = 0
        while position < len(body):
            size = rng.randint(1, 23)
            chunks.append(body[position:position+size])
            position += size
        assert decoded(boundary, chunks) == expected


@pytest.mark.parametrize("trailing", [b"\r", b"\r\r", b"\r\n", b"\n\r", b"\r\n\r\n"])
def test_regression_real_request_64k_boundary_keeps_payload(trailing):
    payload = b"\0" * 65535 + trailing
    result = call("generated-request", payload=pack(payload))
    assert unpack(result["file"]) == payload
    assert result["label"] == "unchanged"


@pytest.mark.parametrize("maximum", [1, 2, 11, 65536])
def test_regression_wsgi_short_reads_preserve_fields_and_files(maximum):
    boundary = b"separate-stream"
    payload = b"\r\n\0\xff\r\n" * 9
    parts = [("title", None, b"first\r\nlast"), ("upload", "f.bin", payload)]
    body = message(boundary, parts)
    result = call("fragmented-request", body=pack(body), maximum=maximum)
    assert result["title"] == "first\r\nlast"
    assert unpack(result["file"]) == payload
    assert result["read_calls"] > 0


def test_preservation_part_limit_is_enforced():
    body = message(b"limit", [("a", None, b"one"), ("b", None, b"two")])
    with pytest.raises(RequestEntityTooLarge):
        call("strict-form", body=pack(body), boundary="limit", max_parts=1)


def test_preservation_memory_limit_is_enforced():
    with pytest.raises(RequestEntityTooLarge):
        call("memory-limit", maximum=16, size=17)


@pytest.mark.parametrize("ending", [b"", b"\r", b"\r\n--b"])
def test_preservation_truncated_input_is_rejected(ending):
    prefix = b'--b\r\nContent-Disposition: form-data; name="value"\r\n\r\ndata'
    payload = prefix + ending
    with pytest.raises(ValueError):
        call("strict-form", body=pack(payload), boundary="b", max_parts=None)


def test_preservation_streaming_produces_data_before_eof():
    boundary = b"stream"
    header = b'--stream\r\nContent-Disposition: form-data; name="file"; filename="f"\r\n\r\n'
    assert call("stream-progress", boundary=pack(boundary), body=pack(header + b"\r\n" + b"x" * 131072))["emitted_bytes"] >= 65536



def padded_message(boundary, parts, opening=b"", intermediate=b"", closing=b"", ending=b"\r\n", epilogue=b""):
    body = bytearray()
    for index, (name, filename, payload) in enumerate(parts):
        padding = opening if index == 0 else intermediate
        body.extend(b"--" + boundary + padding + b"\r\nContent-Disposition: form-data; name=\"" + name.encode() + b'"')
        if filename is not None:
            body.extend(b'; filename="' + filename.encode() + b'"')
        body.extend(b"\r\nContent-Type: application/octet-stream\r\n\r\n" + payload + b"\r\n")
    return bytes(body) + b"--" + boundary + b"--" + closing + ending + epilogue


def chunks_of(body, size):
    return [body[index:index+size] for index in range(0, len(body), size)]


@pytest.mark.parametrize("pads", [(b" ", b"", b""), (b"", b"\t", b""), (b"", b"", b" \t"), (b" \t", b"\t ", b" \t \t")], ids=["opening", "intermediate", "closing", "all-lines"])
def test_hard_padding_every_single_split(pads):
    boundary = b"pad.+?=()'_"
    expected = [("tag", None, b"first\r\n"), ("upload", "f.bin", bytes(range(256)) + b"\r\n"), ("tag", None, b"last\r")]
    body = padded_message(boundary, expected, *pads)
    for split in range(1, len(body)):
        assert decoded(boundary, [body[:split], body[split:]]) == expected, split


@pytest.mark.parametrize("padding", [b"", b" ", b"\t \t"], ids=["plain", "space", "tabs"])
def test_hard_eof_closing_every_single_split(padding):
    boundary = b"eof-boundary"
    expected = [("upload", "f.bin", b"\x00\xff\r\nlast\r")]
    body = padded_message(boundary, expected, closing=padding, ending=b"")
    for split in range(1, len(body)):
        assert decoded(boundary, [body[:split], body[split:]]) == expected, split
    assert decoded(boundary, chunks_of(body, 1)) == expected


@pytest.mark.parametrize("suffix", [b"X", b"!", b"-", b"--", b" \tX", b"\t!"], ids=["letter", "bang", "extra-dash", "two-extra-dashes", "space-tab-letter", "tab-bang"])
def test_hard_false_closing_is_payload_at_every_split(suffix):
    boundary = b"false-close"
    payload = b"prefix\r\n--" + boundary + b"--" + suffix + b"\r\n" + bytes(range(256)) + b"\r"
    expected = [("upload", "f.bin", payload), ("tail", None, b"still here")]
    body = padded_message(boundary, expected)
    for split in range(1, len(body)):
        assert decoded(boundary, [body[:split], body[split:]]) == expected, split


@pytest.mark.parametrize("suffix", [b" X", b"\t!", b" \t---X"], ids=["space-letter", "tab-bang", "mixed-dashes"])
def test_hard_false_padded_separator_is_payload(suffix):
    boundary = b"padding-lookalike"
    payload = b"before\r\n--" + boundary + suffix + b"\r\nafter\r\n"
    expected = [("file", "raw.bin", payload), ("end", None, b"ok")]
    body = padded_message(boundary, expected, opening=b"\t", intermediate=b" ", closing=b"\t ")
    for split in range(1, len(body)):
        assert decoded(boundary, [body[:split], body[split:]]) == expected, split


@pytest.mark.parametrize("boundary", [b"plain", b"special.+?=()'_", b"Z" * 70], ids=["plain", "regex-special", "seventy-bytes"])
def test_hard_one_byte_and_seeded_partitions_preserve_mixed_parts(boundary):
    payload = b"\0\xff\r\n--" + boundary + b"--X\r\n--" + boundary + b" \t!\r\nlast\r"
    expected = [("tag", None, b"left\r\n"), ("upload", "raw.bin", payload), ("tag", None, b"right\r"), ("empty", "empty.bin", b"")]
    body = padded_message(boundary, expected, b"\t ", b" \t", b"\t", ending=b"")
    assert decoded(boundary, chunks_of(body, 1)) == expected
    for seed in (991, 2047, 7093):
        rng = random.Random(seed)
        for _ in range(8):
            position = 0
            chunks = []
            while position < len(body):
                size = rng.randint(1, 31)
                chunks.append(body[position:position+size])
                position += size
            assert decoded(boundary, chunks) == expected, seed


@pytest.mark.parametrize("operation", ["form-parts", "request-parts"], ids=["form-parser", "request"])
@pytest.mark.parametrize("maximum", [1, 7, 65536], ids=["one-byte", "seven-bytes", "whole-buffer"])
def test_hard_public_parser_paths_with_short_reads(operation, maximum):
    boundary = b"public-path"
    payload = b"\0\xff\r\n--public-path--X\r\n--public-path \t!\r"
    parts = [("tag", None, b"left\r\n"), ("upload", "raw.bin", payload), ("tag", None, b"right\r"), ("empty", "empty.bin", b"")]
    body = padded_message(boundary, parts, b" \t", b"\t", b" ", ending=b"")
    result = call(operation, boundary=pack(boundary), body=pack(body), maximum=maximum)
    assert result["fields"] == [["tag", "left\r\n"], ["tag", "right\r"]]
    assert [(name, filename, content_type, unpack(value)) for name, filename, content_type, value in result["files"]] == [("upload", "raw.bin", "application/octet-stream", payload), ("empty", "empty.bin", "application/octet-stream", b"")]
    assert result["read_calls"] > 0


@pytest.mark.parametrize("suffix", [b"--X", b"---", b" \tX", b"-"], ids=["closing-letter", "closing-extra-dash", "padded-letter", "single-dash"])
def test_hard_strict_parser_rejects_false_final_close(suffix):
    body = b'--strict\r\nContent-Disposition: form-data; name="value"\r\n\r\ndata\r\n--strict' + suffix
    with pytest.raises(ValueError):
        call("strict-form", body=pack(body), boundary="strict", max_parts=None)


@pytest.mark.parametrize("padding,tail,valid", [(b"", b"X\r\nnot-close", False), (b"\t ", b"X\r\nstill-data", False), (b" \t", b"\r\n", True)], ids=["bare-then-invalid", "padding-then-invalid", "padding-then-newline"])
def test_hard_ambiguous_close_waits_for_more_input(padding, tail, valid):
    boundary = b"pending"
    prefix = b'--pending\r\nContent-Disposition: form-data; name="file"; filename="f.bin"\r\n\r\ndata\r\n--pending--' + padding
    suffix = tail if valid else tail + b"\r\n--pending--\r\n"
    result = call("probe-decode", boundary=pack(boundary), prefix=pack(prefix), suffix=pack(suffix))
    assert result["ended_before_suffix"] is False
    assert result["part_completed_before_suffix"] is False
    expected = b"data" if valid else b"data\r\n--pending--" + padding + tail
    assert [(name, filename, unpack(value)) for name, filename, value in result["parts"]] == [("file", "f.bin", expected)]


def test_hard_streaming_padded_part_emits_before_eof():
    boundary = b"progress"
    header = b'--progress \t\r\nContent-Disposition: form-data; name="file"; filename="f.bin"\r\n\r\n'
    payload = (b"binary\0\xff\r\n--progress--X\r\n" * 5000) + b"tail\r"
    result = call("stream-fragments", boundary=pack(boundary), chunks=[pack(chunk) for chunk in chunks_of(header + payload, 4093)])
    emitted = unpack(result["payload"])
    assert len(emitted) >= 65536
    assert emitted == payload[:len(emitted)]
    assert result["ended"] is False


@pytest.mark.parametrize("epilogue", [b"after\r\ntext", bytes(range(256))], ids=["text", "binary"])
def test_hard_epilogue_never_enters_file_payload(epilogue):
    boundary = b"epilogue"
    expected = [("upload", "f.bin", b"file\r\n")]
    body = padded_message(boundary, expected, closing=b"\t ", epilogue=epilogue)
    assert decoded(boundary, [body]) == expected
    assert decoded(boundary, chunks_of(body, 1)) == expected


OWNERSHIP_PATHS = ["multipart", "form", "convenience", "request"]


def ownership_message(parts, lengths=None, padded=False, epilogue=b""):
    value = bytearray()
    lengths = lengths or {}
    for index, (name, filename, payload) in enumerate(parts):
        value.extend(b"--ownership" + (b" \t" if padded else b"") + b"\r\nContent-Disposition: form-data; name=\"" + name.encode() + b'"')
        if filename is not None:
            value.extend(b'; filename="' + filename.encode() + b'"')
        value.extend(b"\r\nContent-Type: application/octet-stream\r\n")
        if index in lengths:
            value.extend(b"Content-Length: " + str(lengths[index]).encode() + b"\r\n")
        value.extend(b"\r\n" + payload + b"\r\n")
    return bytes(value) + b"--ownership--" + (b"\t " if padded else b"") + b"\r\n" + epilogue


def owned(body, **arguments):
    result = call("owned-parse", body=pack(body), **arguments)
    assert "construction_error" not in result, result
    return result["rounds"][-1]


def assert_borrowed_input(round_result):
    assert round_result["input_closed"] is False
    assert round_result["input_close_calls"] == 0


def assert_rollback(round_result, minimum=0):
    assert_borrowed_input(round_result)
    assert len(round_result["sinks"]) >= minimum
    assert all(sink["close_calls"] == 1 for sink in round_result["sinks"]), round_result


@pytest.mark.parametrize("path", OWNERSHIP_PATHS)
@pytest.mark.parametrize("scenario", ["inclusive", "per-file", "aggregate"])
def test_ownership_public_paths_enforce_actual_byte_quotas(path, scenario):
    parts = [("tag", None, b"abc"), ("upload", "f.bin", b"\0\xff\r\n")]
    body = ownership_message(parts)
    limits = {"max_file_size": 4, "max_form_data_size": 7}
    if scenario == "per-file":
        limits["max_file_size"] = 3
    if scenario == "aggregate":
        limits["max_form_data_size"] = 6
    result = owned(body, path=path, limits=limits, maximum=1, content_length=None)
    if scenario == "inclusive":
        assert result["error"] is None, result
        assert result["fields"] == [["tag", "abc"]]
        assert [(key, filename, unpack(value)) for key, filename, value in result["files"]] == [("upload", "f.bin", b"\0\xff\r\n")]
        assert len(result["sinks"]) == 1
        assert result["sinks"][0]["close_calls"] == 0
        assert result["sinks"][0]["closed"] is False
        assert_borrowed_input(result)
    else:
        assert result["error"]["type"] == "RequestEntityTooLarge", result
        assert_rollback(result, 1)
        assert len(unpack(result["sinks"][0]["payload"])) <= 3


@pytest.mark.parametrize("case", ["empty-zero", "per-file-reset", "utf8-raw-bytes", "fields-ignore-file-limit", "declared-low", "declared-negative", "declared-huge", "declared-invalid", "fields-only-total", "metadata-excluded", "retry-not-double-counted"], ids=str)
def test_ownership_quota_accounting_boundaries(case):
    settings = {}
    lengths = {}
    padded = False
    epilogue = b""
    fail = False
    if case == "empty-zero":
        parts = [("empty", None, b""), ("upload", "empty.bin", b"")]
        limits = {"max_file_size": 0, "max_form_data_size": 0}
    elif case == "per-file-reset":
        parts = [("upload", "one.bin", b"abc"), ("upload", "two.bin", b"def")]
        limits = {"max_file_size": 3, "max_form_data_size": 6}
    elif case == "utf8-raw-bytes":
        parts = [("tag", None, "é".encode()), ("upload", "f.bin", b"x")]
        limits = {"max_file_size": 1, "max_form_data_size": 2}
        fail = True
    elif case == "fields-ignore-file-limit":
        parts = [("field", None, b"abcdefgh"), ("upload", "empty.bin", b"")]
        limits = {"max_file_size": 0, "max_form_data_size": None}
    elif case.startswith("declared-"):
        parts = [("upload", "f.bin", b"abcde")]
        declared = {"declared-low": "0", "declared-negative": "-9", "declared-huge": "99999", "declared-invalid": "not-a-number"}[case]
        lengths = {0: declared}
        limits = {"max_file_size": 4 if case != "declared-huge" else 5, "max_form_data_size": None}
        fail = case != "declared-huge"
    elif case == "fields-only-total":
        parts = [("tag", None, b"ab"), ("tag", None, b"cde")]
        limits = {"max_file_size": None, "max_form_data_size": 4}
        fail = True
    elif case == "metadata-excluded":
        parts = [("name" * 20, None, b"ab"), ("upload", "filename" * 20, b"cd")]
        limits = {"max_file_size": 2, "max_form_data_size": 4}
        padded = True
        epilogue = b"epilogue" * 20
    else:
        parts = [("tag", None, b"x"), ("upload", "f.bin", b"abcd")]
        limits = {"max_file_size": 4, "max_form_data_size": 5}
        settings = {"short_write": 1}
    result = owned(ownership_message(parts, lengths, padded, epilogue), limits=limits, settings=settings, maximum=13)
    if fail:
        assert result["error"]["type"] == "RequestEntityTooLarge", result
        assert_rollback(result)
        if limits["max_file_size"] is not None:
            assert all(len(unpack(sink["payload"])) <= limits["max_file_size"] for sink in result["sinks"])
    else:
        assert result["error"] is None, result
        assert_borrowed_input(result)
        assert result["fields"] == [[name, payload.decode()] for name, filename, payload in parts if filename is None]
        assert [(name, filename, unpack(value)) for name, filename, value in result["files"]] == [(name, filename, payload) for name, filename, payload in parts if filename is not None]
        assert all(sink["close_calls"] == 0 and not sink["closed"] for sink in result["sinks"])


@pytest.mark.parametrize("path", OWNERSHIP_PATHS)
@pytest.mark.parametrize("setting", ["max_file_size", "max_form_data_size"])
def test_ownership_invalid_configuration_is_not_silenced(path, setting):
    for invalid in (-1, True, 1.5, "4"):
        result = call("validate-limits", path=path, limits={setting: invalid})
        assert result == {"error": "ValueError"}, (path, setting, invalid, result)
    for valid in (None, 0, 4):
        assert call("validate-limits", path=path, limits={setting: valid}) == {"error": None}


@pytest.mark.parametrize("path", ["form", "convenience", "request"])
def test_ownership_new_quotas_do_not_apply_to_urlencoded(path):
    body = b"tag=hello&tag=world"
    result = owned(body, path=path, limits={"max_file_size": 0, "max_form_data_size": 0}, mimetype="application/x-www-form-urlencoded", content_type="application/x-www-form-urlencoded", maximum=65536)
    assert result["error"] is None, result
    assert result["fields"] == [["tag", "hello"], ["tag", "world"]]
    assert result["sinks"] == []
    assert_borrowed_input(result)


@pytest.mark.parametrize("maximum", [1, 3, 11])
def test_ownership_positive_short_writes_preserve_complete_files(maximum):
    parts = [("upload", "a.bin", bytes(range(256)) + b"\r"), ("upload", "b.bin", b"\0\xff\r\nlast\r\n"), ("last", None, b"done")]
    result = owned(ownership_message(parts), settings={"short_write": maximum}, maximum=19)
    assert result["error"] is None, result
    assert [(name, filename, unpack(value)) for name, filename, value in result["files"]] == [(name, filename, payload) for name, filename, payload in parts if filename is not None]
    assert all(sink["close_calls"] == 0 and not sink["closed"] for sink in result["sinks"])
    assert_borrowed_input(result)


@pytest.mark.parametrize("returned", ["zero", "none", "negative", "oversized", "float", "bool"])
def test_ownership_invalid_write_result_fails_and_releases_stream(returned):
    body = ownership_message([("upload", "f.bin", b"some bytes")])
    result = owned(body, settings={"invalid_write": returned})
    assert result["error"]["type"] == "OSError", result
    assert_rollback(result, 1)


@pytest.mark.parametrize("failure", ["reader", "writer", "seek", "factory", "decoder", "fields-collection", "files-collection"])
@pytest.mark.parametrize("base_exception", [False, True], ids=["ordinary-exception", "base-exception"])
def test_ownership_every_failure_releases_completed_and_current_sinks(failure, base_exception):
    parts = [("upload", "first.bin", b"first"), ("upload", "second.bin", b"Q" * 31), ("last", None, b"done")]
    body = ownership_message(parts)
    settings = {"base_exception": base_exception}
    minimum = 2
    if failure == "reader":
        settings["read_error_at"] = body.index(b"Q" * 31) + 7
    elif failure == "writer":
        settings["write_error_sink"] = 1
    elif failure == "seek":
        settings["seek_error_sink"] = 1
    elif failure == "factory":
        settings["factory_error_call"] = 2
        minimum = 1
    elif failure == "decoder":
        body = ownership_message(parts[:2]).rsplit(b"\r\n--ownership--", 1)[0]
    else:
        settings["collection_error_call"] = 1 if failure == "fields-collection" else 2
        minimum = 0
    result = owned(body, settings=settings, maximum=1)
    assert result["error"] is not None, result
    if failure != "decoder":
        assert result["error"]["is_original"] is True, result
        assert result["error"]["type"] == ("ProbeAbort" if base_exception else "OSError")
    else:
        assert result["error"]["type"] == "ValueError"
    assert_rollback(result, minimum)


@pytest.mark.parametrize("close_base_exception", [False, True], ids=["close-oserror", "close-base-exception"])
def test_ownership_cleanup_failure_preserves_original_and_continues(close_base_exception):
    body = ownership_message([("upload", "one.bin", b"one"), ("upload", "two.bin", b"two"), ("upload", "three.bin", b"three")])
    result = owned(body, settings={"write_error_sink": 2, "close_error_sinks": [0], "close_base_exception": close_base_exception}, maximum=1)
    assert result["error"]["is_original"] is True, result
    assert result["error"]["type"] == "OSError"
    assert_rollback(result, 3)
    assert result["sinks"][1]["closed"] is True
    assert result["sinks"][2]["closed"] is True


def test_ownership_shared_factory_stream_is_cleaned_once():
    body = ownership_message([("upload", "one.bin", b"first"), ("upload", "two.bin", b"second")]).rsplit(b"\r\n--ownership--", 1)[0]
    result = owned(body, settings={"shared_sink": True}, maximum=1)
    assert result["error"]["type"] == "ValueError", result
    assert len(result["sinks"]) == 1
    assert_rollback(result, 1)


def test_ownership_silent_value_error_fallback_still_cleans_all_sinks():
    body = ownership_message([("upload", "one.bin", b"first"), ("upload", "two.bin", b"second")])
    result = owned(body, path="form", settings={"write_error_sink": 1, "value_exception": True}, silent=True, maximum=1)
    assert result["error"] is None, result
    assert result["fields"] == result["files"] == []
    assert_rollback(result, 2)


@pytest.mark.parametrize("path", ["form", "convenience"])
def test_ownership_quota_error_is_not_hidden_by_silent_mode(path):
    body = ownership_message([("upload", "f.bin", b"too large")])
    result = owned(body, path=path, limits={"max_file_size": 1}, silent=True, maximum=1)
    assert result["error"]["type"] == "RequestEntityTooLarge", result
    assert_rollback(result, 1)


@pytest.mark.parametrize("first_fails", [False, True], ids=["after-success", "after-failure"])
def test_ownership_reused_parser_starts_fresh_quota_counters(first_fails):
    first = ownership_message([("upload", "one.bin", b"abcde" if first_fails else b"abcd")])
    second = ownership_message([("tag", None, b"x"), ("upload", "two.bin", b"abc")])
    result = call("owned-parse", bodies=[pack(first), pack(second)], path="multipart", limits={"max_file_size": 4, "max_form_data_size": 4}, maximum=1)
    assert "construction_error" not in result, result
    rounds = result["rounds"]
    assert len(rounds) == 2
    assert (rounds[0]["error"]["type"] if rounds[0]["error"] else None) == ("RequestEntityTooLarge" if first_fails else None)
    assert rounds[1]["error"] is None, result
    assert rounds[1]["fields"] == [["tag", "x"]]
    assert rounds[1]["files"] == [["upload", "two.bin", pack(b"abc")]]
    assert_borrowed_input(rounds[0])
    assert_borrowed_input(rounds[1])
    assert rounds[1]["sinks"][-1]["close_calls"] == 0


@pytest.mark.parametrize("close_error", [False, True], ids=["normal", "one-close-fails"])
def test_ownership_request_close_handles_duplicate_names_and_shared_streams(close_error):
    result = call("request-close", settings={"close_error_sinks": [0] if close_error else []}, close_rounds=2)
    assert result["errors"] == [None, None], result
    assert result["input_closed"] is False
    assert result["factory_calls"] == 0
    for index, round_result in enumerate(result["rounds"], start=1):
        assert [sink["close_calls"] for sink in round_result] == [index, index, index]
    if not close_error:
        assert all(sink["closed"] for sink in result["rounds"][-1])


def test_ownership_request_close_does_not_trigger_lazy_parsing():
    result = call("request-close", settings={"uncached": True})
    assert result["errors"] == [None], result
    assert result["factory_calls"] == 0
    assert result["files_cached"] is False
    assert result["input_closed"] is False
    assert [sink["close_calls"] for sink in result["rounds"][0]] == [0, 0, 0]


def test_ownership_successful_transfer_survives_later_parse_failure():
    first = ownership_message([("upload", "first.bin", b"abc")])
    second = ownership_message([("upload", "second.bin", b"12345")])
    result = call("owned-parse", bodies=[pack(first), pack(second)], path="multipart", limits={"max_file_size": 4, "max_form_data_size": 4}, maximum=1)
    rounds = result["rounds"]
    assert rounds[0]["error"] is None, result
    assert rounds[1]["error"]["type"] == "RequestEntityTooLarge", result
    assert len(rounds[1]["sinks"]) == 2
    assert rounds[1]["sinks"][0]["close_calls"] == 0
    assert rounds[1]["sinks"][0]["closed"] is False
    assert unpack(rounds[1]["sinks"][0]["payload"]) == b"abc"
    assert rounds[1]["sinks"][1]["close_calls"] == 1
    assert rounds[1]["sinks"][1]["closed"] is True
    assert len(unpack(rounds[1]["sinks"][1]["payload"])) <= 4
    assert_borrowed_input(rounds[0])
    assert_borrowed_input(rounds[1])


def test_ownership_field_quota_failure_cleans_an_earlier_completed_file():
    body = ownership_message([("upload", "first.bin", b"ab"), ("field", None, b"12345")])
    result = owned(body, limits={"max_form_data_size": 4}, maximum=1)
    assert result["error"]["type"] == "RequestEntityTooLarge", result
    assert len(result["sinks"]) == 1
    assert_rollback(result, 1)
    assert result["sinks"][0]["closed"] is True
    assert unpack(result["sinks"][0]["payload"]) == b"ab"


def test_ownership_public_keyword_only_arguments_and_request_defaults():
    result = call("api-contract")
    assert result["request_defaults"] == {"max_file_size": None, "max_form_data_size": None}
    for name in ("multipart", "form", "convenience"):
        assert result["signatures"][name] == {"max_file_size": {"kind": "KEYWORD_ONLY", "default": None}, "max_form_data_size": {"kind": "KEYWORD_ONLY", "default": None}}
