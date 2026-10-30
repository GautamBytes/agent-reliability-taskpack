import json
import os
from pathlib import Path
import shutil
import signal
import subprocess
import sys
import tempfile
import time


HERE = Path(__file__).resolve().parent
BASELINE = Path(os.environ.get("TASK_BASELINE", "/opt/baseline"))
CANDIDATE = Path(os.environ.get("TASK_CANDIDATE", "/app/repo"))
RESULTS = Path(os.environ.get("TASK_RESULTS", "/logs/verifier"))
ALLOWED = ("packages/better-auth/src", "packages/core/src", "docs/lib/copy-schema")


def production(path):
    return path.suffix in {".ts", ".tsx"} and not path.name.endswith((".test.ts", ".spec.ts", ".test.tsx", ".spec.tsx")) and "__tests__" not in path.parts


def run(arguments, cwd, stdout_path, stderr_path, timeout=120):
    environment = {
        "PATH": os.environ.get("PATH", "/usr/local/bin:/usr/bin:/bin"), "HOME": str(cwd / ".task-home"),
        "NODE_NO_WARNINGS": "1", "DO_NOT_TRACK": "1", "BETTER_AUTH_TELEMETRY": "0",
        "TASK_JSON_REPORT": str(cwd / "vitest-results.json"),
    }
    privilege = {"user": 1000, "group": 1000, "extra_groups": []} if os.geteuid() == 0 else {}
    with stdout_path.open("wb") as output, stderr_path.open("wb") as errors:
        process = subprocess.Popen(arguments, cwd=cwd, env=environment, stdout=output, stderr=errors, start_new_session=True, **privilege)
        try:
            return process.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            os.killpg(process.pid, signal.SIGKILL)
            process.wait()
            return 124
        finally:
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass


def prepare(destination):
    shutil.copytree(BASELINE, destination, ignore=shutil.ignore_patterns("node_modules", ".git", "_task_tests", "vitest.eval.config.ts", "vitest-results.json"))
    for relative in ALLOWED:
        candidate_tree = CANDIDATE / relative
        if candidate_tree.is_symlink() or not candidate_tree.is_dir():
            raise ValueError(f"Missing or symlinked candidate source tree: {relative}")
        for path in candidate_tree.rglob("*"):
            if path.is_symlink():
                raise ValueError(f"Symlinked candidate path: {path.relative_to(CANDIDATE)}")
        target_tree = destination / relative
        for path in list(target_tree.rglob("*")):
            if path.is_file() and production(path):
                path.unlink()
        for path in candidate_tree.rglob("*"):
            if path.is_file() and production(path):
                target = destination / path.relative_to(CANDIDATE)
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(path, target)
    for path in [BASELINE, *BASELINE.glob("packages/*")]:
        dependencies = path / "node_modules"
        if dependencies.is_dir():
            target = destination / path.relative_to(BASELINE) / "node_modules"
            if target.exists() or target.is_symlink():
                target.unlink()
            if path == BASELINE:
                target.mkdir()
                for dependency in dependencies.iterdir():
                    if dependency.name not in {".vite", ".vite-temp"}:
                        (target / dependency.name).symlink_to(dependency, target_is_directory=dependency.is_dir())
            else:
                target.symlink_to(dependencies, target_is_directory=True)
    tests = destination / "_task_tests"
    tests.mkdir(exist_ok=True)
    for name in ("holdout.test.ts", "preservation-migrations.test.ts", "type-contract.ts"):
        shutil.copyfile(HERE / name, tests / name)
    template = (HERE / "vitest.template.ts").read_text()
    template = template.replace("'packages/better-auth/src/db/get-migration-schema.test.ts'", "'_task_tests/preservation-migrations.test.ts', '_task_tests/holdout.test.ts'")
    template = template.replace("'/private/tmp/betterauth-v2-work/initial-results.json'", "process.env.TASK_JSON_REPORT")
    (destination / "vitest.task.config.ts").write_text(template)
    shutil.copyfile(HERE / "tsconfig.template.json", destination / "tsconfig.task.json")
    if os.geteuid() == 0:
        for path in [destination, *destination.rglob("*")]:
            if not path.is_symlink():
                os.chown(path, 1000, 1000)
    for path in tests.iterdir():
        if os.geteuid() == 0:
            os.chown(path, 0, 0)
        path.chmod(0o444)
    if os.geteuid() == 0:
        os.chown(tests, 0, 0)
    tests.chmod(0o555)


def main():
    RESULTS.mkdir(parents=True, exist_ok=True)
    RESULTS.chmod(0o700)
    (RESULTS / "reward.txt").write_text("0\n")
    started = int(time.time() * 1000)
    cases = []
    valid = False
    try:
        with tempfile.TemporaryDirectory(prefix="better-auth-grade-") as directory:
            parent = Path(directory)
            parent.chmod(0o755)
            root = parent / "repo"
            prepare(root)
            compile_code = run([str(BASELINE / "node_modules/.bin/tsc"), "--project", "tsconfig.task.json"], root, RESULTS / "types.stdout", RESULTS / "types.stderr")
            cases.append({"name": "focused TypeScript schema contract", "status": "passed" if compile_code == 0 else "failed", "duration": 0})
            test_code = run([str(BASELINE / "node_modules/.bin/vitest"), "run", "--config", "vitest.task.config.ts"], root, RESULTS / "tests.stdout", RESULTS / "tests.stderr")
            child_report = root / "vitest-results.json"
            if child_report.exists():
                raw = json.loads(child_report.read_text())
                shutil.copyfile(child_report, RESULTS / "vitest.json")
                for suite in raw.get("testResults", []):
                    for assertion in suite.get("assertionResults", []):
                        status = "passed" if assertion["status"] == "passed" else "skipped" if assertion["status"] in {"pending", "todo", "skipped"} else "failed"
                        cases.append({"name": assertion["fullName"], "status": status, "duration": assertion.get("duration") or 0, "message": "\n".join(assertion.get("failureMessages", []))[-5000:]})
            expected = json.loads((HERE / "expected-tests.json").read_text())
            actual = sorted(case["name"] for case in cases)
            private_intact = all((root / "_task_tests" / name).read_bytes() == (HERE / name).read_bytes() for name in ("holdout.test.ts", "preservation-migrations.test.ts", "type-contract.ts"))
            valid = compile_code == test_code == 0 and actual == expected and private_intact and all(case["status"] == "passed" for case in cases)
    except Exception as error:
        (RESULTS / "grader-error.txt").write_text(f"{type(error).__name__}: {error}\n")
    passed = sum(case["status"] == "passed" for case in cases)
    skipped = sum(case["status"] == "skipped" for case in cases)
    metrics = {"tests_run": len(cases), "passed": passed, "failed": len(cases) - passed - skipped, "skipped": skipped, "all_required_checks_passed": valid, "cases": cases}
    (RESULTS / "results.json").write_text(json.dumps(metrics, indent=2) + "\n")
    ctrf = {"results": {"tool": {"name": "better-auth-oss-verifier"}, "summary": {"tests": len(cases), "passed": passed, "failed": len(cases) - passed - skipped, "skipped": skipped, "pending": 0, "other": 0, "start": started, "stop": int(time.time() * 1000)}, "tests": cases}}
    (RESULTS / "ctrf.json").write_text(json.dumps(ctrf, indent=2) + "\n")
    if valid:
        (RESULTS / "reward.txt").write_text("1\n")
    print(json.dumps({key: value for key, value in metrics.items() if key != "cases"}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
