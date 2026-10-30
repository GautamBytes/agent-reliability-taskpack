"""Run a local early-exit and protected-file control inside the verifier image."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if os.geteuid() != 0:
        raise RuntimeError("Run this control as root in the verifier image")
    with tempfile.TemporaryDirectory(prefix="anyio-control-") as temporary:
        work = Path(temporary)
        work.chmod(0o755)
        candidate = work / "candidate"
        shutil.copytree("/opt/baseline", candidate)
        audit = work / "audit"
        audit.mkdir(mode=0o700)
        os.chown(audit, 1000, 1000)
        protected = ["/tests/cancellation_cases.py", "/tests/case_names.py", "/tests/expected-cases.json"]
        candidate.joinpath("src/anyio/__init__.py").write_text(f'''
import glob
import json
import os
from pathlib import Path
checks = {{"uid": os.geteuid(), "gid": os.getegid()}}
for filename in {protected!r}:
    try:
        Path(filename).read_bytes()
    except PermissionError:
        checks[filename] = "denied"
    else:
        checks[filename] = "readable"
reports = [str(Path(directory) / "reports/private.xml") for directory in glob.glob("/tmp/anyio-grade-*")]
for filename in reports:
    try:
        Path(filename).write_text("tampered")
    except PermissionError:
        checks[filename] = "denied"
    else:
        checks[filename] = "writable"
Path({str(audit)!r}, str(os.getpid()) + ".json").write_text(json.dumps(checks))
os._exit(0)
''')
        subprocess.run([sys.executable, "-I", "/tests/verify.py", "--candidate", str(candidate), "--output", str(args.output)], check=True)
        result = json.loads((args.output / "results.json").read_text())
        private = next(stage for stage in result["stages"] if stage["stage"] == "private")
        assert result["reward"] == 0 and private["tests"] == private["failed"] == 20, result
        checks = [json.loads(path.read_text()) for path in audit.glob("*.json")]
        assert len(checks) >= 21, checks
        for check in checks:
            assert check.pop("uid") == check.pop("gid") == 1000, check
            assert check and set(check.values()) == {"denied"}, check
        (args.output / "boundary-control.json").write_text(json.dumps({"candidate_imports": len(checks), "uid": 1000, "protected_reads_and_writes": "denied", "early_exit_private_failures": 20, "reward": 0}, indent=2) + "\n")


if __name__ == "__main__":
    main()
