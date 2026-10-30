import argparse
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import uuid

from replay import ROOT, run


def main(destination):
    destination.mkdir(parents=True, exist_ok=False)
    task = ROOT / "tasks" / "anyio-cancel-scope"
    image = "oss-anyio-final-controls:local"
    built = run(["docker", "build", "--tag", image, str(task / "tests")])
    (destination / "build.log").write_text(built.stdout + built.stderr)
    variants = {"baseline": None, "reference": task / "solution" / "reference.patch"}
    variants.update({path.stem: path for path in sorted((task / "controls").glob("*.patch"))})
    records = []
    for variant, patch in variants.items():
        output = destination / variant
        output.mkdir()
        with tempfile.TemporaryDirectory(prefix="anyio-final-control-") as directory:
            repository = Path(directory) / "repo"
            shutil.copytree(task / "environment" / "repo", repository,
                            ignore=shutil.ignore_patterns(".git", "__pycache__", ".pytest_cache", "*.pyc"))
            if patch:
                run(["git", "apply", "--check", str(patch)], cwd=repository)
                run(["git", "apply", str(patch)], cwd=repository)
            container = "anyio-final-" + uuid.uuid4().hex[:12]
            run(["docker", "create", "--name", container, "--network", "none", "--cpus", "2", "--memory", "1g",
                 "--pids-limit", "512", "--security-opt", "no-new-privileges", "--read-only",
                 "--tmpfs", "/tmp:rw,nosuid,nodev,size=512m", "--volume", "/logs/verifier",
                 "--mount", f"type=bind,src={repository},dst=/app/repo,readonly", image, "bash", "/tests/test.sh"])
            try:
                completed = run(["docker", "start", "--attach", container])
                (output / "container.stdout").write_text(completed.stdout)
                (output / "container.stderr").write_text(completed.stderr)
                run(["docker", "cp", f"{container}:/logs/verifier/.", str(output)])
            finally:
                subprocess.run(["docker", "rm", "--force", "--volumes", container], capture_output=True)
        metrics = json.loads((output / "results.json").read_text())
        reward = int((output / "reward.txt").read_text())
        record = {"variant": variant, "reward": reward, "expected_reward": int(variant == "reference"),
                  **{key: metrics[key] for key in ("tests_run", "passed", "failed", "skipped")}}
        assert record["reward"] == record["expected_reward"], record
        assert record["tests_run"] == 169 and record["skipped"] == 4, record
        records.append(record)
        print(json.dumps(record), flush=True)
    (destination / "summary.json").write_text(json.dumps({"all_expected_outcomes": True, "variants": records}, indent=2) + "\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run AnyIO baseline, reference and all partial fixes with the release verifier.")
    parser.add_argument("--output", type=Path, required=True)
    main(parser.parse_args().output.resolve())
