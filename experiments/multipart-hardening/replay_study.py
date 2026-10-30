import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import uuid

from study import ROOT, read, sha, source_files


def run(command, **kwargs):
    result = subprocess.run(command, capture_output=True, text=True, timeout=600, **kwargs)
    if result.returncode:
        raise RuntimeError(result.stderr[-6000:] or result.stdout[-6000:])
    return result


def replay(name, output, target_version=None):
    trial = ROOT / "runs/curated" / name
    summary = read(trial / "summary.json")
    submitted_version = summary["version"]
    version = target_version or submitted_version
    folder = ROOT / "versions" / version
    output.mkdir(parents=True, exist_ok=False)
    image = "oss-study-replay-" + version + ":local"
    built = run(["docker", "build", "--tag", image, str(folder / "tests")])
    (output / "build.log").write_text(built.stdout + built.stderr)
    with tempfile.TemporaryDirectory(prefix="multipart-study-replay-") as directory:
        repository = Path(directory) / "repo"
        shutil.copytree(ROOT / "versions" / submitted_version / "environment/repo", repository,
                        ignore=shutil.ignore_patterns(".git", "__pycache__", ".pytest_cache", "*.pyc"))
        patch = trial / "submitted.patch"
        assert sha(patch) == summary["patch_sha256"]
        if patch.stat().st_size:
            run(["git", "apply", "--check", str(patch)], cwd=repository)
            run(["git", "apply", str(patch)], cwd=repository)
        actual_source = {key: hashlib.sha256(value).hexdigest() for key, value in source_files(repository).items()}
        assert actual_source == read(trial / "submitted-source-sha256.json")
        container = "multipart-study-replay-" + uuid.uuid4().hex[:12]
        run(["docker", "create", "--name", container, "--network", "none", "--cpus", "2", "--memory", "1g",
             "--pids-limit", "512", "--security-opt", "no-new-privileges", "--read-only", "--tmpfs", "/tmp:rw,nosuid,nodev,size=512m",
             "--volume", "/logs/verifier", "--mount", f"type=bind,src={repository},dst=/app/repo,readonly", image, "bash", "/tests/test.sh"])
        try:
            execution = run(["docker", "start", "--attach", container])
            (output / "container.stdout").write_text(execution.stdout)
            (output / "container.stderr").write_text(execution.stderr)
            run(["docker", "cp", f"{container}:/logs/verifier/.", str(output)])
        finally:
            subprocess.run(["docker", "rm", "--force", "--volumes", container], capture_output=True)
    metrics = read(output / "results.json")
    reward = float((output / "reward.txt").read_text())
    verifier_hashes = {"src/werkzeug/" + key: value for key, value in metrics.get("source_hashes", {}).items()}
    assert verifier_hashes == actual_source, "Verifier graded different source bytes"
    expected_names = read(folder / "tests/expected-cases.json")
    if reward == 1:
        assert sorted(case["name"] for case in metrics["cases"]) == sorted(expected_names)
        assert metrics["tests_run"] == metrics["passed"] == len(expected_names) and metrics["failed"] == metrics["skipped"] == 0
    record = {"attempt": name, "submitted_version": submitted_version, "verifier_version": version,
              "cross_grade": version != submitted_version, "source_hashes_verified": True,
              "patch_sha256": summary["patch_sha256"], "reward": reward,
              "checks": {key: metrics[key] for key in ("tests_run", "passed", "failed", "skipped")}}
    if version == submitted_version:
        original = read(trial / "results.json")
        statuses = lambda value: sorted((case["name"], case["status"]) for case in value["cases"])
        record.update(matches_native_reward=reward == summary["native_reward"], matches_native_case_statuses=statuses(metrics) == statuses(original))
        assert record["matches_native_reward"] and record["matches_native_case_statuses"], record
    (output / "replay.json").write_text(json.dumps(record, indent=2) + "\n")
    print(json.dumps(record), flush=True)
    return record


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Reconstruct submitted source and reproduce native study scores; cross-grading is labelled separately.")
    parser.add_argument("attempt", help="Recorded attempt ID or all")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--cross-grade", choices=("basic", "hard"))
    args = parser.parse_args()
    names = sorted(path.parent.name for path in (ROOT / "runs/curated").glob("*/summary.json")) if args.attempt == "all" else [args.attempt]
    records = [replay(name, args.output.resolve() / name if args.attempt == "all" else args.output.resolve(), args.cross_grade) for name in names]
    if args.attempt == "all":
        (args.output / "summary.json").write_text(json.dumps(records, indent=2) + "\n")
