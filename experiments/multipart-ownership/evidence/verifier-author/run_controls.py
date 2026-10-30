import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import uuid


ROOT = Path(__file__).resolve().parents[2]


def run(command, **options):
    result = subprocess.run(command, text=True, capture_output=True, timeout=300, **options)
    if result.returncode:
        raise RuntimeError(result.stderr[-6000:] or result.stdout[-6000:])
    return result


def main():
    parser = argparse.ArgumentParser(description="Run fixed-source controls with no model attempt.")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--version", choices=("before", "after"), default="after")
    parser.add_argument("--variant", action="append")
    args = parser.parse_args()
    task = ROOT / "versions" / args.version
    after = ROOT / "versions/after"
    patches = {"baseline": None, "prior-hard-reference": ROOT / "versions/before/solution/reference.patch", "reference": after / "solution/reference.patch", "alternative-exitstack": after / "solution/alternative-exitstack.patch", "early-collections": ROOT / "evidence/verifier-author/alternatives/early-collections.patch"}
    patches.update({path.stem: path for path in (after / "mutants").glob("*.patch")})
    selected = args.variant or ["baseline", "prior-hard-reference", "reference", "alternative-exitstack", "quota-only", "close-current-only", "one-write", "trust-content-length", "exception-only-cleanup", "omit-request-forwarding", "close-first-duplicate"]
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    image = "ownership-grader-" + args.version + ":controls"
    build = run(["docker", "build", "--tag", image, str(task / "tests")])
    (output / "build.log").write_text(build.stdout + build.stderr)
    rows = []
    for variant in selected:
        target = output / variant
        target.mkdir()
        with tempfile.TemporaryDirectory(prefix="ownership-verifier-control-") as name:
            repository = Path(name) / "repo"
            shutil.copytree(task / "environment/repo", repository, ignore=shutil.ignore_patterns(".git", "__pycache__", ".pytest_cache", "*.pyc"))
            patch = patches[variant]
            if patch:
                run(["git", "apply", "--check", str(patch)], cwd=repository)
                run(["git", "apply", str(patch)], cwd=repository)
            production = repository / "src/werkzeug"
            source_hashes = {str(path.relative_to(production)): hashlib.sha256(path.read_bytes()).hexdigest() for path in production.rglob("*") if path.is_file() and "__pycache__" not in path.parts and path.suffix != ".pyc"}
            container = "ownership-control-" + uuid.uuid4().hex[:12]
            run(["docker", "create", "--name", container, "--network", "none", "--cpus", "2", "--memory", "1g", "--pids-limit", "512", "--security-opt", "no-new-privileges", "--read-only", "--tmpfs", "/tmp:rw,nosuid,nodev,size=512m", "--volume", "/logs/verifier", "--mount", f"type=bind,src={repository},dst=/app/repo,readonly", image, "bash", "/tests/test.sh"])
            try:
                execution = run(["docker", "start", "--attach", container])
                (target / "container.stdout").write_text(execution.stdout)
                (target / "container.stderr").write_text(execution.stderr)
                run(["docker", "cp", f"{container}:/logs/verifier/.", str(target)])
            finally:
                subprocess.run(["docker", "rm", "--force", "--volumes", container], capture_output=True)
        metrics = json.loads((target / "results.json").read_text())
        assert source_hashes == metrics["source_hashes"], "Verifier graded a different source tree"
        row = {"version": args.version, "variant": variant, "source_hashes_verified": True, "patch_sha256": hashlib.sha256(patch.read_bytes()).hexdigest() if patch else None, **{key: metrics[key] for key in ("reward", "tests_run", "passed", "failed", "skipped")}}
        rows.append(row)
        print(json.dumps(row), flush=True)
    (output / "summary.json").write_text(json.dumps({"description": "Fixed-source offline controls, no model attempts", "rows": rows}, indent=2) + "\n")


if __name__ == "__main__":
    main()
