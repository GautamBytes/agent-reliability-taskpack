import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import uuid


ROOT = Path(__file__).resolve().parents[1]


def run(arguments, **kwargs):
    result = subprocess.run(arguments, text=True, capture_output=True, timeout=600, **kwargs)
    if result.returncode:
        raise RuntimeError(result.stderr[-6000:] or result.stdout[-6000:])
    return result


def replay(name, destination, rescore=False):
    trial = ROOT / "evidence" / "trials" / name
    summary = json.loads((trial / "summary.json").read_text())
    task = summary["task"]
    destination.mkdir(parents=True, exist_ok=False)
    image = f"oss-replay-{task}:local"
    built = run(["docker", "build", "--tag", image, str(ROOT / "tasks" / task / "tests")])
    (destination / "build.log").write_text(built.stdout + built.stderr)
    with tempfile.TemporaryDirectory(prefix="oss-replay-") as directory:
        repository = Path(directory) / "repo"
        shutil.copytree(ROOT / "tasks" / task / "environment" / "repo", repository,
                        ignore=shutil.ignore_patterns(".git", "node_modules", "__pycache__", ".pytest_cache", "*.pyc"))
        patch = trial / "submitted.patch"
        assert hashlib.sha256(patch.read_bytes()).hexdigest() == summary["patch_sha256"]
        if patch.stat().st_size:
            run(["git", "apply", "--check", str(patch)], cwd=repository)
            run(["git", "apply", str(patch)], cwd=repository)
        for path, expected in json.loads((trial / "submitted-source-sha256.json").read_text()).items():
            assert hashlib.sha256((repository / path).read_bytes()).hexdigest() == expected, path
        container = "oss-replay-" + uuid.uuid4().hex[:12]
        run(["docker", "create", "--name", container, "--network", "none", "--cpus", "2", "--memory", "3g",
             "--pids-limit", "512", "--security-opt", "no-new-privileges", "--read-only", "--tmpfs", "/tmp:rw,nosuid,nodev,size=2g",
             "--volume", "/logs/verifier", "--mount", f"type=bind,src={repository},dst=/app/repo,readonly", image, "bash", "/tests/test.sh"])
        try:
            result = run(["docker", "start", "--attach", container])
            (destination / "container.stdout").write_text(result.stdout)
            (destination / "container.stderr").write_text(result.stderr)
            run(["docker", "cp", f"{container}:/logs/verifier/.", str(destination)])
        finally:
            subprocess.run(["docker", "rm", "--force", "--volumes", container], capture_output=True)
    metrics = json.loads((destination / "results.json").read_text())
    expected_file = trial / "corrected-results.json" if (trial / "corrected-results.json").exists() and not rescore else trial / "results.json"
    original = json.loads(expected_file.read_text())
    reward = (destination / "reward.txt").read_text().strip()
    actual = sorted((case["name"], case["status"]) for case in metrics["cases"])
    expected = sorted((case["name"], case["status"]) for case in original["cases"])
    expected_reward = summary.get("original_reward", summary["reward"]) if rescore else summary["reward"]
    record = {"trial": name, "patch_sha256": summary["patch_sha256"], "reward": reward,
              "comparison_report": expected_file.name, "expected_reward": expected_reward,
              "matches_expected_reward": float(reward) == expected_reward, "matches_all_expected_case_statuses": actual == expected,
              "checks": len(actual), "source_hashes_verified": True}
    if rescore:
        assert summary["task"] == "better-auth-indexes"
        revision = json.loads((ROOT / "FAIRNESS_REVISION.json").read_text())
        assert {name for name, _ in actual} == {name for name, _ in expected}
        previous = dict(expected)
        record.update(fairness_revision=revision["id"], public_contract_unchanged=revision["public_contract_unchanged"],
                      changed_case_statuses=[{"name": name, "original": previous[name], "corrected": status} for name, status in actual if previous[name] != status])
    else:
        assert record["matches_expected_reward"] and record["matches_all_expected_case_statuses"], record
    (destination / "replay.json").write_text(json.dumps(record, indent=2) + "\n")
    print(json.dumps(record), flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Reconstruct a submitted source tree from its production patch and reproduce its final verification.")
    parser.add_argument("trial")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--rescore-fairness", action="store_true", help="Rescore an unchanged Better Auth patch after the recorded verifier fairness correction")
    args = parser.parse_args()
    replay(args.trial, args.output.resolve(), args.rescore_fairness)
