from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
from trusted_rpc import call, pack, unpack


@pytest.mark.parametrize("trailing", [b"\r", b"\r\r", b"\r\n", b"\n\r", b"\r\n\r\n"])
def test_regression_real_request_64k_boundary_keeps_payload(trailing):
    payload = b"\0" * 65535 + trailing
    result = call("generated-request", payload=pack(payload))
    assert unpack(result["file"]) == payload
    assert result["label"] == "unchanged"
