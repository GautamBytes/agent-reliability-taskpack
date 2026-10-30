from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

from case_names import CASE_NAMES


@pytest.mark.parametrize("backend", ["asyncio", "trio"])
@pytest.mark.parametrize("case", CASE_NAMES)
def test_cancellation_behavior(case: str, backend: str) -> None:
    script = Path(__file__).with_name("private_case_runner.py")
    try:
        result = subprocess.run(
            [sys.executable, "-I", str(script), os.environ["PRIVATE_CASE_REPOSITORY"], case, backend],
            env=os.environ.copy(),
            capture_output=True,
            text=True,
            timeout=5,
        )
    except subprocess.TimeoutExpired as exc:
        pytest.fail(f"{case} on {backend} did not complete within 5 seconds: {exc}")
    assert result.returncode == 0, result.stdout + result.stderr
    assert result.stdout.strip() == f"completed {case} on {backend}"
