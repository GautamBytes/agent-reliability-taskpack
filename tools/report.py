import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import tarfile
import tomllib


ROOT = Path(__file__).resolve().parents[1]
TASKS = {
    "anyio-cancel-scope": {"checks": 169, "required": 165, "nonpasses": 4, "preservation": 145, "holdout": 20},
    "better-auth-indexes": {"checks": 83, "required": 83, "nonpasses": 0, "preservation": 50, "holdout": 32},
    "werkzeug-multipart": {"checks": 65, "required": 65, "nonpasses": 0, "preservation": 31, "holdout": 34},
}


def read(path):
    return json.loads((ROOT / path).read_text())


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def baseline_sources():
    verified = {}
    anyio = ROOT / "tasks/anyio-cancel-scope"
    manifest = json.loads((anyio / "evidence/baseline-manifest.json").read_text())
    for name, expected in manifest.items():
        assert digest(anyio / "environment/repo" / name) == expected, name
    verified["anyio-cancel-scope"] = len(manifest)
    for task, archive_name in (("better-auth-indexes", "tests/baseline.tar.gz"), ("werkzeug-multipart", "baseline-source.tar.gz")):
        folder = ROOT / "tasks" / task
        provenance = json.loads((folder / "provenance.json").read_text())
        archive_path = folder / archive_name
        assert digest(archive_path) == provenance["baseline_archive_sha256"]
        count = 0
        with tarfile.open(archive_path) as archive:
            for member in archive:
                if not member.isfile():
                    continue
                relative = Path(*Path(member.name).parts[1:])
                assert relative.parts and ".." not in relative.parts
                stream = archive.extractfile(member)
                assert stream is not None
                assert (folder / "environment/repo" / relative).read_bytes() == stream.read(), str(relative)
                count += 1
        verified[task] = count
    assert verified == {"anyio-cancel-scope": 92, "better-auth-indexes": 2240, "werkzeug-multipart": 290}
    return verified


def native_job(name, expected_reward):
    folder = ROOT / "evidence" / "native-controls" / name
    result = read(folder / "result.json")
    assert result["finished_at"] and result["stats"]["n_completed_trials"] == 3
    assert result["stats"]["n_errored_trials"] == 0
    scores = {}
    for path in sorted(folder.glob("*/result.json")):
        trial = json.loads(path.read_text())
        assert trial["exception_info"] is None, str(path)
        reward = trial["verifier_result"]["rewards"]["reward"]
        assert reward == expected_reward, str(path)
        task = next(task for task in TASKS if path.parent.name.startswith(task + "__"))
        metrics = json.loads((path.parent / "verifier/results.json").read_text())
        assert metrics["tests_run"] == TASKS[task]["checks"], str(path)
        assert metrics["skipped"] == TASKS[task]["nonpasses"], str(path)
        if expected_reward:
            assert metrics["passed"] == TASKS[task]["required"] and metrics["failed"] == 0
        else:
            assert metrics["failed"] > 0
        scores[task] = {key: metrics[key] for key in ("tests_run", "passed", "failed", "skipped")}
    assert set(scores) == set(TASKS)
    return scores


def audit(write):
    verified_sources = baseline_sources()
    assert read("evidence/harbor-lint.json") == []
    references = native_job("final-references", 1)
    baselines = native_job("final-baselines", 0)
    anyio = read("evidence/final-anyio-controls/summary.json")
    betterauth = read("tasks/better-auth-indexes/evidence/release-semantic-matrix/summary.json")
    werkzeug = read("tasks/werkzeug-multipart/evidence/docker-adversarial-controls/summary.json")
    assert all(report["all_expected_outcomes"] for report in (anyio, betterauth, werkzeug))
    controls = {}
    for task, records in (("anyio-cancel-scope", anyio["variants"]), ("better-auth-indexes", betterauth["runs"]), ("werkzeug-multipart", werkzeug["variants"])):
        for record in records:
            assert int(record["reward"]) == int(record["expected_reward"]), record
            assert record["tests_run"] == TASKS[task]["checks"], record
            assert record["skipped"] == TASKS[task]["nonpasses"], record
        controls[task] = records
    rejected = [record for records in controls.values() for record in records
                if record["variant"] not in {"baseline", "reference", "forged-public-junit"} and not record["variant"].startswith("equivalent-")]
    alternatives = [record for records in controls.values() for record in records if record["variant"].startswith("equivalent-")]
    assert len(rejected) == 10 and all(int(record["reward"]) == 0 for record in rejected)
    assert len(alternatives) == 3 and all(int(record["reward"]) == 1 for record in alternatives)
    revision = read("FAIRNESS_REVISION.json")
    revised = {item["path"]: item for item in revision["changes"]}
    publication = read("PUBLICATION_METADATA.json") if (ROOT / "PUBLICATION_METADATA.json").exists() else {}
    metadata_changes = {item["path"]: item for item in publication.get("task_configuration_changes", [])}
    for path, item in revised.items():
        assert digest(ROOT / "tasks/better-auth-indexes" / path) == item["corrected_sha256"]
    trials = read("evidence/trial-summary.json")
    assert len(trials["trials"]) == 6 and trials["passed"] == 5 and trials["budget_exhaustions"] == 1 and trials["exceptions"] == 0
    expected_pairs = {(task, profile) for task in TASKS for profile in ("standard", "extended")}
    assert {(trial["task"], trial["profile"]) for trial in trials["trials"]} == expected_pairs
    for trial in trials["trials"]:
        folder = ROOT / "evidence/trials" / trial["id"]
        assert digest(folder / "submitted.patch") == trial["patch_sha256"]
        assert trial["cutoff_artifact_passed"] and trial["task_unchanged_during_trial"]
        assert trial["checks"]["tests_run"] == TASKS[trial["task"]]["checks"]
        episode = json.loads((folder / "episode.json").read_text())
        for relative, recorded in episode["task_fingerprint"].items():
            if relative == "provenance.json":
                continue
            current = digest(ROOT / "tasks" / trial["task"] / relative)
            if current != recorded:
                publication_path = "tasks/" + trial["task"] + "/" + relative
                if relative == "task.toml" and publication_path in metadata_changes:
                    item = metadata_changes[publication_path]
                    assert item["original_sha256"] == recorded and item["published_sha256"] == current
                    assert set(item["changed_fields"]) <= {"source", "task.authors"}
                    contract = tomllib.loads((ROOT / publication_path).read_text())
                    contract.pop("source", None)
                    contract.get("task", {}).pop("authors", None)
                    assert hashlib.sha256(json.dumps(contract, sort_keys=True).encode()).hexdigest() == item["execution_contract_sha256"]
                    continue
                assert trial["task"] == "better-auth-indexes" and relative in revised
                assert revised[relative]["original_sha256"] == recorded and revised[relative]["corrected_sha256"] == current
        replay = read("evidence/replays/" + trial["id"] + "/replay.json")
        assert replay["source_hashes_verified"] and replay["matches_all_expected_case_statuses"] and replay["matches_expected_reward"]
        assert replay["patch_sha256"] == trial["patch_sha256"] and float(replay["reward"]) == 1
        if trial["task"] == "better-auth-indexes":
            assert trial["fairness_rescored"] and trial["original_reward"] == 0
        boundary = read(folder / "network-boundary.json")
        assert boundary == {"github_proxy_denied": True, "direct_internet_blocked": True}
        trajectory = read(folder / "trajectory.json")
        assert all("message" not in step for step in trajectory["steps"])
    report = {"audited_at": datetime.now(timezone.utc).isoformat(), "all_gates_passed": True,
              "tasks": TASKS, "reference_results": references, "baseline_results": baselines,
              "reported_checks": 317, "required_passes": 313, "known_upstream_nonpasses": 4,
              "required_upstream_preservation": 226, "authored_behavioral_holdouts": 86, "focused_compile_checks": 1,
              "rejected_partial_fixes": len(rejected), "accepted_alternative_fixes": len(alternatives),
              "native_coding_attempts": 6, "normally_finished_passes": 5, "deadline_exhaustions": 1,
              "passing_saved_patches": 6, "source_patch_replays": 6, "infrastructure_exceptions": 0,
              "fairness_revision": revision["id"]}
    report["byte_verified_baseline_files"] = verified_sources
    table = ["# Native coding-agent trials", "", "All attempts used Codex 0.166.0 and gpt-6.1-sol through native Harbor 0.25.0. Each started fresh with the same public task and no private feedback.", "",
             "| Task | Profile | Deadline | Original checks | Final checks | Run outcome |",
             "| --- | --- | ---: | ---: | ---: | --- |"]
    for trial in trials["trials"]:
        original, final = trial["original_checks"], trial["checks"]
        outcome = "Completed" if trial["status"] == "PASS" else "Timed out; saved patch passes"
        table.append(f"| {trial['task']} | {trial['profile']} / {trial['reasoning']} | {trial['agent_timeout_seconds']}s | {original['passed']}/{original['tests_run']} | {final['passed']}/{final['tests_run']} | {outcome} |")
    table.extend(["", "AnyIO has four separately allowlisted upstream nonpasses: two Python-version skips and two xfails. The 165 required checks pass. No unexpected skip is accepted.", "",
                  "The Better Auth verifier originally rejected valid Drizzle bracket notation and bracket-quoted SQL Server OBJECT_ID syntax. A later independent review also found a whitespace-sensitive Prisma check. The corrected verifier executes generated Drizzle schemas and accepts the documented Prisma formatting alternatives. The public tasks and submitted patches did not change. All native attempts had finished before the correction. Original results, intermediate grader versions and exact case-status changes remain in the evidence. See FAIRNESS_REVISION.json and evidence/rescored/.", "",
                  "Five attempts completed normally. One exhausted its 300-second agent deadline. All six saved source patches pass the final functional checks and were reconstructed from their patches in fresh offline verifier containers. The timeout remains a timeout, and rescoring is not a new agent attempt.", "",
                  "This is a usability check of three historically public tasks at two budgets from one model family. It does not estimate general model accuracy, establish training-data independence or demonstrate frontier-model difficulty.", ""])
    if write:
        (ROOT / "evidence/release-audit.json").write_text(json.dumps(report, indent=2) + "\n")
        (ROOT / "TRIALS.md").write_text("\n".join(table))
        fingerprints = {str(path.relative_to(ROOT)): digest(path) for task in TASKS
                        for path in [ROOT / "tasks" / task / "instruction.md", ROOT / "tasks" / task / "task.toml", *sorted((ROOT / "tasks" / task / "tests").rglob("*"))]
                        if path.is_file() and not any(part in {"__pycache__", ".pytest_cache"} for part in path.parts)}
        (ROOT / "evidence/release-task-fingerprints.json").write_text(json.dumps(fingerprints, indent=2) + "\n")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Audit curated release evidence without access to raw agent workspaces.")
    parser.add_argument("--write", action="store_true", help="Regenerate the release audit, trial table and current task fingerprints")
    audit(parser.parse_args().write)
