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
