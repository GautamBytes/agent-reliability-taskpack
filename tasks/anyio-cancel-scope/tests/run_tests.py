#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path
from xml.etree import ElementTree as ET


def timeout_report(destination: Path, group: str, detail: str) -> None:
    suite = ET.Element("testsuite", name=group, tests="1", failures="0", errors="1")
    test = ET.SubElement(suite, "testcase", classname="runner", name="bounded_run")
    ET.SubElement(test, "error", message=detail).text = detail
    ET.ElementTree(suite).write(destination, encoding="unicode", xml_declaration=True)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", type=Path, required=True)
    parser.add_argument("--group", choices=["public", "private", "all"], default="all")
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    repo = args.repo.resolve()
    here = Path(__file__).resolve().parent
    output = args.output_dir.resolve()
    output.mkdir(parents=True, exist_ok=True)
    if os.geteuid() != 0:
        raise RuntimeError("The trusted pytest coordinator must run as root")
    env = {
        "PATH": "/usr/local/bin:/usr/bin:/bin",
        "HOME": os.environ.get("HOME", "/tmp"),
        "LANG": "C.UTF-8",
        "PYTEST_DISABLE_PLUGIN_AUTOLOAD": "1",
        "PYTHONDONTWRITEBYTECODE": "1",
    }
    public_output = output.parent / "public-results"
    public_output.mkdir(mode=0o700, exist_ok=True)
    os.chown(public_output, 1000, 1000)
    results = {}
    groups = ["public", "private"] if args.group == "all" else [args.group]
    for group in groups:
        report = output / f"{group}.xml"
        report.unlink(missing_ok=True)
        case_env = env.copy()
        if group == "public":
            child_report = public_output / "public.xml"
            child_report.unlink(missing_ok=True)
            case_env["PYTHONPATH"] = os.pathsep.join([str(repo / "src"), str(here)])
            command = [sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", "-p", "anyio.pytest_plugin", "-p", "preservation_plugin", str(repo / "tests/test_taskgroups.py"), f"--junitxml={child_report}"]
            privileges = {"user": 1000, "group": 1000, "extra_groups": []}
            cwd = repo
        else:
            child_report = report
            case_env["PRIVATE_CASE_REPOSITORY"] = str(repo)
            command = [sys.executable, "-I", "-m", "pytest", "-q", "-p", "no:cacheprovider", "-c", "/dev/null", f"--confcutdir={here}", str(here / "test_regressions.py"), f"--junitxml={report}"]
            privileges = {}
            cwd = here
        try:
            result = subprocess.run(command, cwd=cwd, env=case_env, text=True, capture_output=True, timeout=90, **privileges)
            if group == "public" and child_report.is_file() and not child_report.is_symlink():
                report.write_bytes(child_report.read_bytes())
            (output / f"{group}.log").write_text(result.stdout + result.stderr)
            results[group] = result.returncode
            print(result.stdout, end="")
            print(result.stderr, end="", file=sys.stderr)
        except subprocess.TimeoutExpired as exc:
            message = f"{group} did not complete within 90 seconds"
            (output / f"{group}.log").write_text(message + "\n" + str(exc))
            timeout_report(report, group, message)
            results[group] = 124
        if not report.is_file():
            timeout_report(report, group, "pytest exited without a JUnit report")
            results[group] = results[group] or 1
    (output / "summary.json").write_text(json.dumps(results, indent=2) + "\n")
    return int(any(results.values()))


if __name__ == "__main__":
    raise SystemExit(main())
