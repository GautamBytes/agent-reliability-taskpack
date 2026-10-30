import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import signal
import subprocess
import sys
import tempfile
import time
import xml.etree.ElementTree as ET


def source_tree(root):
    directory = root / "src" / "werkzeug"
    if not directory.is_dir() or directory.is_symlink():
        raise ValueError("Missing regular src/werkzeug directory")
    files = []
    size = 0
    for path in directory.rglob("*"):
        if path.is_symlink():
            raise ValueError("Source symlinks are not allowed")
        if path.is_file() and "__pycache__" not in path.parts and path.suffix != ".pyc":
            size += path.stat().st_size
            files.append(path)
    if size > 8 * 1024 * 1024 or len(files) > 500:
        raise ValueError("Source exceeds task limits")
    return directory, files


def run_stage(name, command, repository, output, uid, trusted=False):
    env = {"PATH": os.environ.get("PATH", "/usr/local/bin:/usr/bin:/bin"), "HOME": "/tmp", "LANG": "C.UTF-8", "PYTHONPATH": str(Path(__file__).resolve().parent if trusted else repository / "src"), "PYTHONDONTWRITEBYTECODE": "1", "PYTEST_DISABLE_PLUGIN_AUTOLOAD": "1", "TASK_REPO": str(repository), "TASK_WORKER_UID": str(uid)}
    kwargs = {"user": uid, "group": uid, "extra_groups": []} if os.geteuid() == 0 and not trusted else {}
    started = time.monotonic()
    with tempfile.TemporaryFile() as stdout, tempfile.TemporaryFile() as stderr:
        process = subprocess.Popen(command, cwd=repository, env=env, stdout=stdout, stderr=stderr, start_new_session=True, **kwargs)
        timeout = False
        try:
            process.wait(timeout=90)
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
        (output / f"{name}.stdout").write_bytes(stdout.read(4 * 1024 * 1024))
        (output / f"{name}.stderr").write_bytes(stderr.read(4 * 1024 * 1024))
    return {"exit_code": process.returncode, "timeout": timeout, "seconds": round(time.monotonic() - started, 3)}


def junit(path):
    root = ET.parse(path).getroot()
    cases = []
    for case in root.iter("testcase"):
        status = "failed" if case.find("failure") is not None or case.find("error") is not None else "skipped" if case.find("skipped") is not None else "passed"
        classname = case.attrib.get("classname", "").rsplit(".", 1)[-1]
        cases.append({"name": classname + "." + case.attrib["name"], "status": status, "duration": float(case.attrib.get("time", 0)) * 1000})
    return cases


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--candidate", type=Path, default=Path("/app/repo"))
    parser.add_argument("--baseline", type=Path, default=Path("/opt/baseline"))
    parser.add_argument("--output", type=Path, default=Path("/logs/verifier"))
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    args.output.chmod(0o700)
    (args.output / "reward.txt").write_text("0\n")
    private = Path(__file__).resolve().parent
    candidate, files = source_tree(args.candidate)
    checksums = {str(path.relative_to(candidate)): hashlib.sha256(path.read_bytes()).hexdigest() for path in files}
    uid = 1000 if os.geteuid() == 0 else os.getuid()
    stages = []
    cases = []
    with tempfile.TemporaryDirectory(prefix="werkzeug-grade-") as temporary:
        work = Path(temporary)
        work.chmod(0o755)
        repo = work / "repo"
        shutil.copytree(args.baseline, repo, ignore=shutil.ignore_patterns(".git", "__pycache__", ".pytest_cache", "*.pyc"))
        shutil.rmtree(repo / "src" / "werkzeug")
        shutil.copytree(candidate, repo / "src" / "werkzeug", ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
        for path in [repo, *repo.rglob("*")]:
            if path.is_dir():
                path.chmod(0o755)
            else:
                path.chmod(0o444)
        reports = work / "reports"
        reports.mkdir(mode=0o777)
        reports.chmod(0o777)
        private_reports = work / "private-reports"
        private_reports.mkdir(mode=0o700)
        commands = {
            "preservation": [sys.executable, "-m", "pytest", "-p", "no:cacheprovider", "-p", "pytest_timeout", "--timeout=5", "tests/sansio/test_multipart.py", "tests/test_formparser.py", "-k", "not test_decoder_data_start_with_different_newline_positions", "-q", f"--junitxml={reports / 'preservation.xml'}"],
            "holdout": [sys.executable, "-I", "-m", "pytest", "-p", "no:cacheprovider", "-p", "pytest_timeout", "--timeout=5", "-c", "/dev/null", str(private / "test_holdout.py"), "-q", f"--junitxml={private_reports / 'holdout.xml'}"],
        }
        for name, command in commands.items():
            result = run_stage(name, command, repo, args.output, uid, trusted=name == "holdout")
            path = (private_reports if name == "holdout" else reports) / f"{name}.xml"
            stage_cases = junit(path) if path.is_file() else []
            if path.is_file():
                shutil.copyfile(path, args.output / path.name)
            for case in stage_cases:
                case["name"] = name + ":" + case["name"]
            result.update(stage=name, tests=len(stage_cases), passed=sum(c["status"] == "passed" for c in stage_cases), failed=sum(c["status"] == "failed" for c in stage_cases), skipped=sum(c["status"] == "skipped" for c in stage_cases))
            stages.append(result)
            cases.extend(stage_cases)
    counts = {"preservation": 31, "holdout": 5}
    expected_path = private / "expected-cases.json"
    expected_cases = json.loads(expected_path.read_text())
    actual_names = sorted(case["name"] for case in cases)
    successful = all(stage["exit_code"] == 0 and not stage["timeout"] and stage["tests"] == counts[stage["stage"]] and stage["passed"] == stage["tests"] for stage in stages)
    successful = successful and actual_names == expected_cases
    result = {"reward": int(successful), "tests_run": len(cases), "passed": sum(c["status"] == "passed" for c in cases), "failed": sum(c["status"] == "failed" for c in cases), "skipped": sum(c["status"] == "skipped" for c in cases), "stages": stages, "cases": cases, "source_hashes": checksums, "local_privilege_boundary": os.geteuid() == 0}
    (args.output / "results.json").write_text(json.dumps(result, indent=2) + "\n")
    (args.output / "ctrf.json").write_text(json.dumps({"results": {"tool": {"name": "werkzeug-oss-verifier"}, "summary": {"tests": len(cases), "passed": result["passed"], "failed": result["failed"], "skipped": result["skipped"], "pending": 0, "other": 0}, "tests": cases}}, indent=2) + "\n")
    (args.output / "reward.txt").write_text("1\n" if successful else "0\n")
    print(json.dumps({key: result[key] for key in ("reward", "tests_run", "passed", "failed", "skipped")}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
