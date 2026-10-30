import argparse
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import uuid


EXPERIMENT = Path(__file__).resolve().parents[2]
PACK = EXPERIMENT.parents[1]


def run(command, **options):
    result = subprocess.run(command, text=True, capture_output=True, timeout=300, **options)
    if result.returncode:
        raise RuntimeError(result.stderr[-6000:] or result.stdout[-6000:])
    return result


def main():
    parser = argparse.ArgumentParser(description="Run fixed source controls through a private task verifier without any coding agent.")
    parser.add_argument("version", choices=("basic", "hard"))
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--variant", action="append", choices=("baseline", "reference", "old-complete", "upstream-3089-only", "strip-payload-newlines", "hard-reference", "fragmented-data"))
    args = parser.parse_args()
    task = EXPERIMENT / "versions" / args.version
    original = PACK / "tasks" / "werkzeug-multipart"
    patches = {"baseline": None, "fragmented-data": EXPERIMENT / "evidence/verifier-author/alternatives/fragmented-data.patch", "reference": task / "solution/reference.patch", "hard-reference": EXPERIMENT / "versions/hard/solution/reference.patch", "old-complete": original / "solution/reference.patch", "upstream-3089-only": original / "mutants/upstream-3089-only.patch", "strip-payload-newlines": original / "mutants/strip-payload-newlines.patch"}
    selected = args.variant or ["baseline", "old-complete", "upstream-3089-only", "strip-payload-newlines"]
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    image = f"oss-hardening-grader-{args.version}:final"
    build = run(["docker", "build", "--tag", image, str(task / "tests")])
    (output / "build.log").write_text(build.stdout + build.stderr)
    rows = []
    for variant in selected:
        target = output / variant
        target.mkdir()
        with tempfile.TemporaryDirectory(prefix="multipart-hardening-control-") as name:
            repository = Path(name) / "repo"
            shutil.copytree(task / "environment/repo", repository, ignore=shutil.ignore_patterns(".git", "__pycache__", ".pytest_cache", "*.pyc"))
            patch = patches[variant]
            if patch:
                run(["git", "apply", "--check", str(patch)], cwd=repository)
                run(["git", "apply", str(patch)], cwd=repository)
            container = "multipart-control-" + uuid.uuid4().hex[:12]
            run(["docker", "create", "--name", container, "--network", "none", "--cpus", "2", "--memory", "1g", "--pids-limit", "512", "--security-opt", "no-new-privileges", "--read-only", "--tmpfs", "/tmp:rw,nosuid,nodev,size=512m", "--volume", "/logs/verifier", "--mount", f"type=bind,src={repository},dst=/app/repo,readonly", image, "bash", "/tests/test.sh"])
            try:
                execution = run(["docker", "start", "--attach", container])
                (target / "container.stdout").write_text(execution.stdout)
                (target / "container.stderr").write_text(execution.stderr)
                run(["docker", "cp", f"{container}:/logs/verifier/.", str(target)])
            finally:
                subprocess.run(["docker", "rm", "--force", "--volumes", container], capture_output=True)
        metrics = json.loads((target / "results.json").read_text())
        row = {"version": args.version, "variant": variant, **{key: metrics[key] for key in ("reward", "tests_run", "passed", "failed", "skipped")}}
        rows.append(row)
        print(json.dumps(row), flush=True)
    (output / "summary.json").write_text(json.dumps({"description": "Fixed-source Docker controls, no model attempts", "rows": rows}, indent=2) + "\n")


if __name__ == "__main__":
    main()
