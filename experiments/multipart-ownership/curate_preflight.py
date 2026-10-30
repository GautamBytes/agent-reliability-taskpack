import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import tempfile

from study import ROOT, read, sha, source_files, write


def main():
    records = []
    target = ROOT / "evidence/native-controls"
    target.mkdir(parents=True, exist_ok=False)
    for version in ("before", "after"):
        for variant, expected_reward in (("reference", 1), ("baseline", 0)):
            name = f"{version}-{variant}"
            job = ROOT / "evidence/native-preflight" / name
            native_paths = list(job.glob("*/result.json"))
            assert len(native_paths) == 1, name
            native_path = native_paths[0]
            native = read(native_path)
            metrics = read(native_path.parent / "verifier/results.json")
            assert native.get("exception_info") is None, name
            assert native["verifier_result"]["rewards"]["reward"] == metrics["reward"] == expected_reward
            expected_cases = read(ROOT / "versions" / version / "tests/expected-cases.json")
            assert sorted(case["name"] for case in metrics["cases"]) == sorted(expected_cases)
            assert metrics["tests_run"] == len(expected_cases) and metrics["skipped"] == 0
            with tempfile.TemporaryDirectory(prefix="ownership-control-proof-") as directory:
                repository = Path(directory) / "repo"
                shutil.copytree(ROOT / "versions" / version / "environment/repo", repository,
                                ignore=shutil.ignore_patterns(".git", "__pycache__", ".pytest_cache", "*.pyc"))
                if variant == "reference":
                    patch = ROOT / "versions" / version / "solution/reference.patch"
                    applied = subprocess.run(["git", "apply", str(patch)], cwd=repository, capture_output=True, text=True)
                    assert applied.returncode == 0, applied.stderr
                hashes = {key.removeprefix("src/werkzeug/"): hashlib.sha256(value).hexdigest() for key, value in source_files(repository).items()}
                assert hashes == metrics["source_hashes"], name
            output = target / name
            output.mkdir()
            shutil.copyfile(native_path, output / "harbor-result.json")
            for path in (native_path.parent / "verifier").iterdir():
                if path.is_file():
                    shutil.copyfile(path, output / path.name)
            records.append({"id": name, "coding_model_attempt": False, "native_agent": "oracle" if variant == "reference" else "nop",
                            "reward": expected_reward, "tests_run": metrics["tests_run"], "passed": metrics["passed"],
                            "failed": metrics["failed"], "skipped": metrics["skipped"], "source_hashes_verified": True,
                            "native_result_sha256": sha(output / "harbor-result.json"), "results_sha256": sha(output / "results.json")})
    write(target / "summary.json", {"all_gates_passed": True, "control_runs": records, "counted_coding_model_attempts": 0})
    print(json.dumps(records, indent=2))


if __name__ == "__main__":
    main()
