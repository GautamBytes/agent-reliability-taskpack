import argparse
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import uuid


ROOT = Path(__file__).resolve().parent
IMAGE = "oss-werkzeug-v2-verifier:author"


def run(command, **kwargs):
    return subprocess.run(command, text=True, capture_output=True, check=True, **kwargs)


def main():
    parser = argparse.ArgumentParser(description="Build the private verifier and grade the baseline, reference and partial fixes.")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--include-adversarial", action="store_true")
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    build = run(["docker", "build", "--tag", IMAGE, str(ROOT / "tests")])
    (args.output / "build.log").write_text(build.stdout + build.stderr)
    variants = [("baseline", None, 0), ("reference", ROOT / "solution" / "reference.patch", 1)]
    variants += [(path.stem, path, 0) for path in sorted((ROOT / "mutants").glob("*.patch"))]
    if args.include_adversarial:
        variants += [(path.stem, path, 0) for path in sorted((ROOT / "adversarial").glob("*.patch"))]
    summary = []
    for label, patch, expected in variants:
        output = args.output / label
        output.mkdir()
        with tempfile.TemporaryDirectory(prefix="werkzeug-control-") as directory:
            repo = Path(directory) / "repo"
            shutil.copytree(ROOT / "environment" / "repo", repo, ignore=shutil.ignore_patterns(".git", "__pycache__", ".pytest_cache"))
            if patch is not None:
                run(["git", "apply", str(patch)], cwd=repo)
            name = "werkzeug-control-" + uuid.uuid4().hex[:12]
            run(["docker", "create", "--name", name, "--network", "none", "--read-only", "--tmpfs", "/tmp:rw,nosuid,nodev,size=256m", "--volume", "/logs/verifier", "--memory", "1g", "--cpus", "2", "--pids-limit", "128", "--security-opt", "no-new-privileges", "--mount", f"type=bind,src={repo},dst=/app/repo,readonly", IMAGE, "bash", "/tests/test.sh"])
            try:
                execution = run(["docker", "start", "--attach", name], timeout=150)
                (output / "runner.log").write_text(execution.stdout + execution.stderr)
                run(["docker", "cp", f"{name}:/logs/verifier/.", str(output)])
            finally:
                run(["docker", "rm", "--force", "--volumes", name])
        result = json.loads((output / "results.json").read_text())
        record = {"variant": label, "expected_reward": expected, **{key: result[key] for key in ("reward", "tests_run", "passed", "failed", "skipped")}}
        assert record["reward"] == expected and record["tests_run"] == 65 and record["skipped"] == 0, record
        summary.append(record)
        print(json.dumps(record), flush=True)
    (args.output / "summary.json").write_text(json.dumps({"all_expected_outcomes": True, "runtime": "Docker, candidate UID 1000", "variants": summary}, indent=2) + "\n")


if __name__ == "__main__":
    main()
