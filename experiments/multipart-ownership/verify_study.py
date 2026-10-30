import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import tempfile

from study import ROOT, VERSIONS, check_frozen, read, sha, source_files


def reconstructed_source(version, trial):
    with tempfile.TemporaryDirectory(prefix="multipart-proof-audit-") as temporary:
        repository = Path(temporary) / "repo"
        shutil.copytree(ROOT / "versions" / version / "environment/repo", repository,
                        ignore=shutil.ignore_patterns(".git", "__pycache__", ".pytest_cache", "*.pyc"))
        patch = trial / "submitted.patch"
        if patch.stat().st_size:
            result = subprocess.run(["git", "apply", str(patch)], cwd=repository, capture_output=True, text=True)
            assert result.returncode == 0, result.stderr
        actual = {name: hashlib.sha256(data).hexdigest() for name, data in source_files(repository).items()}
        assert actual == read(trial / "submitted-source-sha256.json")
        return actual


def audit(require_replays=True):
    protocol = read(ROOT / "protocol.json")
    check_frozen(protocol)
    protocol_sha = sha(ROOT / "protocol.json")
    anchor = read(ROOT / "evidence/publication-anchor.json")
    assert protocol["public_pre_evaluation_anchor_required"] and anchor["github_protocol_bytes_verified"]
    assert anchor["protocol_sha256"] == protocol_sha and len(anchor["commit_sha"]) == 40
    expected = {name for pair in protocol["order"] for name in pair["attempts"]}
    paths = sorted((ROOT / "runs/curated").glob("*/summary.json"))
    assert {path.parent.name for path in paths} == expected and len(paths) == len(expected)
    records = []
    for path in paths:
        folder = path.parent
        summary = read(path)
        episode = read(folder / "episode.json")
        native = read(folder / "harbor-result.json")
        metrics = read(folder / "results.json")
        version = summary["version"]
        assert episode["id"] == summary["id"] == folder.name
        assert summary["protocol_sha256"] == episode["protocol_sha256"] == protocol_sha
        assert episode["public_anchor_sha256"] == sha(ROOT / "evidence/publication-anchor.json")
        assert episode["started_at"] > anchor["observed_at"]
        assert episode["task_unchanged"] and summary["task_unchanged"]
        assert episode["task_fingerprint"] == protocol["task_fingerprints"][version]
        assert summary["model"] == protocol["model"] and summary["reasoning"] == protocol["reasoning"]
        assert summary["solve_deadline_seconds"] == protocol["agent_timeout_seconds"]
        native_reward = native["verifier_result"]["rewards"]["reward"]
        assert summary["native_reward"] == native_reward
        assert summary["completed_pass"] == (native_reward == 1 and native.get("exception_info") is None)
        assert summary["saved_artifact_pass"] == (native_reward == 1)
        assert summary["status"] in {"PASS", "FAIL", "TIMEOUT"}, "Adjudicate non-model outcomes before reporting a rate"
        actual = reconstructed_source(version, folder)
        graded = {"src/werkzeug/" + name: digest for name, digest in metrics["source_hashes"].items()}
        assert graded == actual and summary["verifier_source_matches_artifact"]
        assert sha(folder / "submitted.patch") == summary["patch_sha256"]
        assert len(metrics["cases"]) == metrics["tests_run"]
        assert sorted(case["name"] for case in metrics["cases"]) == sorted(protocol["expected_case_names"][version]), "Missing case evidence requires explicit adjudication"
        assert metrics["tests_run"] == len(protocol["expected_case_names"][version]) and metrics["skipped"] == 0
        assert all(case["status"] in {"passed", "failed"} for case in metrics["cases"])
        if native_reward == 1:
            assert sorted(case["name"] for case in metrics["cases"]) == sorted(protocol["expected_case_names"][version])
            assert metrics["passed"] == metrics["tests_run"] == len(protocol["expected_case_names"][version])
            assert metrics["failed"] == metrics["skipped"] == 0
            assert all(case["status"] == "passed" for case in metrics["cases"])
        trace = read(folder / "trajectory.json")
        assert trace["agent"]["model_name"] == protocol["model"] and trace["agent"]["version"] == protocol["codex_cli"]
        assert trace.get("final_metrics") and trace["final_metrics"].get("total_prompt_tokens", 0) > 0
        assert all("message" not in step for step in trace["steps"])
        assert read(folder / "network-boundary.json") == {"github_proxy_denied": True, "direct_internet_blocked": True}
        network = [json.loads(line) for line in (folder / "network-connections.jsonl").read_text().splitlines()]
        assert any(row["decision"] == "allow" and row["host"].endswith("chatgpt.com") for row in network)
        assert any(row["decision"] == "deny" and row["host"] == "github.com" for row in network)
        if require_replays:
            replay = read(ROOT / "runs/replays" / folder.name / "replay.json")
            assert replay["source_hashes_verified"] and replay["matches_native_reward"] and replay["matches_native_case_statuses"]
            assert replay["patch_sha256"] == summary["patch_sha256"] and replay["reward"] == native_reward
        records.append(summary)
    totals = {}
    for version in VERSIONS:
        rows = [row for row in records if row["version"] == version]
        totals[version] = {"attempts": len(rows), "normal_completion_passes": sum(row["completed_pass"] for row in rows),
                           "collected_source_passes": sum(row["saved_artifact_pass"] for row in rows),
                           "timeouts": sum(row["status"] == "TIMEOUT" for row in rows)}
    aggregate = read(ROOT / "runs/summary.json")
    assert aggregate["protocol_sha256"] == protocol_sha and aggregate["model"] == protocol["model"]
    assert {row["id"]: row for row in aggregate["attempts"]} == {row["id"]: row for row in records}
    for version, value in totals.items():
        observed = aggregate["versions"][version]
        assert observed["attempts"] == value["attempts"] == protocol["attempts_per_version"]
        assert observed["completed_passes"] == value["normal_completion_passes"]
        assert observed["passing_saved_artifacts"] == value["collected_source_passes"]
        assert observed["timeouts"] == value["timeouts"] and observed["unresolved_or_infrastructure_outcomes"] == 0
    return {"audited_at": datetime.now(timezone.utc).isoformat(), "all_gates_passed": True,
            "protocol_sha256": protocol_sha, "counted_native_agent_attempts": len(records), "versions": totals,
            "exact_source_replays_required": require_replays, "actual_model": protocol["model"],
            "public_pre_evaluation_commit": anchor["commit_sha"],
            "interpretation": protocol["interpretation"], "atomic_deadline_snapshot_claimed": False}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Independently audit the frozen two-version study, source patches and recorded native outcomes.")
    parser.add_argument("--before-replays", action="store_true")
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    result = audit(not args.before_replays)
    if args.write:
        (ROOT / "AUDIT.json").write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result, indent=2))
