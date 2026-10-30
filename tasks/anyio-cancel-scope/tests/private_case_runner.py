"""Preload trusted test code, then execute it with candidate privileges.

This protects files and the pytest report. It is standard behavioral evaluation;
malicious candidate Python can still counterfeit its in-process completion marker.
"""
from __future__ import annotations

import os
from pathlib import Path
import sys


def main() -> None:
    if os.geteuid() != 0:
        raise RuntimeError("The trusted launcher must start as root")
    source = Path(__file__).with_name("cancellation_cases.py")
    code = compile(source.read_bytes(), str(source), "exec")
    repository, case, backend = sys.argv[1:]
    os.setgroups([])
    os.setgid(1000)
    os.setuid(1000)
    if os.geteuid() != 1000 or os.getegid() != 1000:
        raise RuntimeError("Candidate privilege drop failed")
    sys.path.insert(0, str(Path(repository) / "src"))
    sys.argv = [str(source), case, backend]
    exec(code, {"__name__": "__main__", "__file__": str(source)})


if __name__ == "__main__":
    main()
