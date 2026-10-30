import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import tarfile
import tempfile
import uuid


TASK = Path(__file__).resolve().parents[1]


def command(args, **kwargs):
    result = subprocess.run(args, text=True, capture_output=True, **kwargs)
    if result.returncode:
        raise RuntimeError(result.stderr or result.stdout)
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--image", default="oss-betterauth-verifier:local")
    parser.add_argument("--variant", action="append")
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    variants = {"baseline": None, "reference": TASK / "solution/reference.patch"}
    variants.update({path.stem: path for path in sorted((TASK / "mutants").glob("*.patch"))})
    variants.update({path.stem: path for path in sorted((TASK / "alternatives").glob("*.patch"))})
    selected = args.variant or list(variants)
    summary = []
    for variant in selected:
        patch = variants[variant]
        target = args.output / variant
        target.mkdir()
        with tempfile.TemporaryDirectory(prefix="better-auth-control-") as temporary:
            with tarfile.open(TASK / "tests/baseline.tar.gz") as archive:
                archive.extractall(temporary, filter="data")
            repo = next(Path(temporary).iterdir())
            if patch:
                command(["git", "apply", str(patch)], cwd=repo)
            name = "better-auth-control-" + uuid.uuid4().hex[:12]
            command(["docker", "create", "--name", name, "--network", "none", "--cpus", "2", "--memory", "2g", "--pids-limit", "512", "--security-opt", "no-new-privileges", "--read-only", "--tmpfs", "/tmp:rw,nosuid,nodev,size=1g", "--volume", "/logs/verifier", "--mount", f"type=bind,src={repo},dst=/app/repo,readonly", args.image, "bash", "/tests/test.sh"])
            try:
                execution = subprocess.run(["docker", "start", "--attach", name], capture_output=True, text=True, timeout=240)
                (target / "container.stdout").write_text(execution.stdout)
                (target / "container.stderr").write_text(execution.stderr)
                command(["docker", "cp", name + ":/logs/verifier/.", str(target)])
            finally:
                subprocess.run(["docker", "rm", "--force", "--volumes", name], capture_output=True)
        metrics = json.loads((target / "results.json").read_text())
        reward = (target / "reward.txt").read_text().strip()
        expected = "1" if variant == "reference" or variant.startswith("equivalent-") else "0"
        record = {key: metrics[key] for key in ("tests_run", "passed", "failed", "skipped")}
        record.update(variant=variant, reward=reward, expected_reward=expected, valid=reward == expected and metrics["tests_run"] == 83 and metrics["skipped"] == 0, patch_sha256=hashlib.sha256(patch.read_bytes()).hexdigest() if patch else None)
        summary.append(record)
        print(json.dumps(record), flush=True)
    report = {"runtime": "Docker Python3.12.12 Node24.11.1", "all_expected_outcomes": all(row["valid"] for row in summary), "runs": summary}
    (args.output / "summary.json").write_text(json.dumps(report, indent=2) + "\n")
    raise SystemExit(0 if report["all_expected_outcomes"] else 1)


if __name__ == "__main__":
    main()
