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
