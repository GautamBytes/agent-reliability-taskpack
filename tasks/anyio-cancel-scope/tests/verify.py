import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import shutil
import signal
import stat
import subprocess
import sys
import tempfile
import time
import xml.etree.ElementTree as ET


def source_tree(root):
    directory = root / "src" / "anyio"
    if (root / "src").is_symlink() or directory.is_symlink() or not directory.is_dir():
        raise ValueError("Missing regular src/anyio directory")
    files = {}
    size = 0
    for path in sorted(directory.rglob("*")):
        info = path.lstat()
        relative = path.relative_to(directory)
        if stat.S_ISLNK(info.st_mode) or not (stat.S_ISDIR(info.st_mode) or stat.S_ISREG(info.st_mode)):
            raise ValueError("Source must contain only regular files and directories")
        if len(str(relative).encode()) > 512:
            raise ValueError("Source path exceeds task limits")
        if stat.S_ISREG(info.st_mode) and "__pycache__" not in relative.parts and path.suffix != ".pyc":
            size += info.st_size
            if size > 8 * 1024 * 1024 or len(files) >= 500:
                raise ValueError("Source exceeds task limits")
            data = path.read_bytes()
            if len(data) != info.st_size:
                raise ValueError("Source changed during collection")
            files[str(relative)] = data
    if "__init__.py" not in files:
        raise ValueError("Incomplete src/anyio source tree")
    return files


def run_tests(repository, private, reports, output, home):
    env = {
        "PATH": "/usr/local/bin:/usr/bin:/bin",
        "HOME": str(home),
        "LANG": "C.UTF-8",
        "PYTHONDONTWRITEBYTECODE": "1",
        "PYTEST_DISABLE_PLUGIN_AUTOLOAD": "1",
    }
    command = [sys.executable, "-I", str(private / "run_tests.py"), "--repo", str(repository), "--group", "all", "--output-dir", str(reports)]
    started = time.monotonic()
    with tempfile.TemporaryFile() as stdout, tempfile.TemporaryFile() as stderr:
        process = subprocess.Popen(command, cwd=repository, env=env, stdout=stdout, stderr=stderr, start_new_session=True)
        timeout = False
        try:
            process.wait(timeout=200)
        except subprocess.TimeoutExpired:
            timeout = True
            os.killpg(process.pid, signal.SIGKILL)
            process.wait()
        finally:
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
        stdout.seek(0)
        stderr.seek(0)
        (output / "runner.stdout").write_bytes(stdout.read(4 * 1024 * 1024))
        (output / "runner.stderr").write_bytes(stderr.read(4 * 1024 * 1024))
    return {"exit_code": process.returncode, "timeout": timeout, "seconds": round(time.monotonic() - started, 3)}


def junit(path, group):
    if path.is_symlink() or not path.is_file() or not 0 < path.stat().st_size <= 4 * 1024 * 1024:
        raise ValueError(f"Missing or oversized {group} report")
    root = ET.parse(path).getroot()
    if root.tag not in {"testsuite", "testsuites"}:
        raise ValueError(f"Invalid {group} report root")
    cases = []
    for case in root.iter("testcase"):
        name = case.attrib.get("name", "")
        if not name:
            raise ValueError(f"Unnamed {group} case")
        identity = case.attrib.get("classname", "") + "." + name
        skipped = case.find("skipped")
        status = "failed" if case.find("failure") is not None or case.find("error") is not None else "skipped" if skipped is not None else "passed"
        skip_type = skipped.attrib.get("type", "") if skipped is not None else ""
        duration = float(case.attrib.get("time", 0))
        if not math.isfinite(duration) or duration < 0:
            raise ValueError(f"Invalid {group} case duration")
        cases.append({"name": group + ":" + identity, "status": status, "skip_type": skip_type, "duration": duration * 1000})
    declared = sum(int(s.attrib.get("tests", -100000)) for s in root.iter("testsuite"))
    if not cases or declared != len(cases):
        raise ValueError(f"Incomplete {group} report")
    return cases


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--candidate", type=Path, default=Path("/app/repo"))
    parser.add_argument("--baseline", type=Path, default=Path("/opt/baseline"))
    parser.add_argument("--output", type=Path, default=Path("/logs/verifier"))
    args = parser.parse_args()
    if os.geteuid() != 0:
        raise RuntimeError("The trusted verifier must run as root")
    args.output.mkdir(parents=True, exist_ok=True)
    args.output.chmod(0o700)
    (args.output / "reward.txt").write_text("0\n")
    result = {"reward": 0, "tests_run": 0, "passed": 0, "failed": 0, "skipped": 0, "stages": [], "cases": [], "source_hashes": {}, "local_privilege_boundary": True}
    try:
        private = Path(__file__).resolve().parent
        expected = json.loads((private / "expected-cases.json").read_text())
        files = source_tree(args.candidate)
        result["source_hashes"] = {name: hashlib.sha256(data).hexdigest() for name, data in files.items()}
        with tempfile.TemporaryDirectory(prefix="anyio-grade-") as temporary:
            work = Path(temporary)
            work.chmod(0o755)
            repo = work / "repo"
            shutil.copytree(args.baseline, repo, ignore=shutil.ignore_patterns(".git", "__pycache__", ".pytest_cache", "*.pyc"))
            source = repo / "src" / "anyio"
            shutil.rmtree(source)
            source.mkdir()
            for name, data in files.items():
                target = source / name
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(data)
            for path in [repo, *repo.rglob("*")]:
                path.chmod(0o755 if path.is_dir() else 0o444)
            reports = work / "reports"
            home = work / "home"
            reports.mkdir(mode=0o700)
            home.mkdir(mode=0o700)
            os.chown(home, 1000, 1000)
            run = run_tests(repo, private, reports, args.output, home)
            result["runner"] = run
            for group in ("public", "private"):
                cases = junit(reports / f"{group}.xml", group)
                shutil.copyfile(reports / f"{group}.xml", args.output / f"{group}.xml")
                log = reports / f"{group}.log"
                if log.is_file() and not log.is_symlink():
                    with log.open("rb") as stream:
                        (args.output / f"{group}.log").write_bytes(stream.read(4 * 1024 * 1024))
                identities = [{"name": case["name"], "status": case["status"], "skip_type": case["skip_type"]} for case in cases]
                exact = sorted(identities, key=lambda case: case["name"]) == expected[group]
                stage = {"stage": group, "tests": len(cases), "passed": sum(c["status"] == "passed" for c in cases), "failed": sum(c["status"] == "failed" for c in cases), "skipped": sum(c["status"] == "skipped" for c in cases), "expected_cases_match": exact}
                result["stages"].append(stage)
                result["cases"].extend(cases)
            result["reward"] = int(run["exit_code"] == 0 and not run["timeout"] and all(stage["expected_cases_match"] for stage in result["stages"]))
    except Exception as exc:
        result["error"] = f"{type(exc).__name__}: {exc}"
    result["tests_run"] = len(result["cases"])
    for status in ("passed", "failed", "skipped"):
        result[status] = sum(case["status"] == status for case in result["cases"])
    (args.output / "results.json").write_text(json.dumps(result, indent=2) + "\n")
    (args.output / "ctrf.json").write_text(json.dumps({"results": {"tool": {"name": "anyio-oss-verifier"}, "summary": {"tests": result["tests_run"], "passed": result["passed"], "failed": result["failed"], "skipped": result["skipped"], "pending": 0, "other": 0}, "tests": result["cases"]}}, indent=2) + "\n")
    (args.output / "reward.txt").write_text(f"{result['reward']}\n")
    print(json.dumps({key: result[key] for key in ("reward", "tests_run", "passed", "failed", "skipped")}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
