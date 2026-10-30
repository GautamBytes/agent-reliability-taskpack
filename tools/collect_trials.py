import argparse
import difflib
import hashlib
import json
from pathlib import Path
import shutil
import tomllib


ROOT = Path(__file__).resolve().parents[1]
SCOPES = {"anyio-cancel-scope": ("src/anyio",), "werkzeug-multipart": ("src/werkzeug",),
          "better-auth-indexes": ("packages/better-auth/src", "packages/core/src", "docs/lib/copy-schema")}


def production(task, path):
    if any(part in {"__pycache__", "node_modules", ".git"} for part in path.parts) or path.suffix == ".pyc":
        return False
    if task == "better-auth-indexes":
        return path.suffix in {".ts", ".tsx"} and not path.name.endswith((".test.ts", ".spec.ts", ".test.tsx", ".spec.tsx")) and "__tests__" not in path.parts
    return True


def files(task, repository):
    result = {}
    for scope in SCOPES[task]:
        directory = repository / scope
        if not directory.is_dir():
            raise ValueError(f"Missing collected source scope {directory}")
        for path in sorted(directory.rglob("*")):
            if path.is_file() and not path.is_symlink() and production(task, path.relative_to(repository)):
                result[path.relative_to(repository).as_posix()] = path.read_bytes()
    return result


def patch_and_hashes(task, candidate, target):
    baseline = files(task, ROOT / "tasks" / task / "environment" / "repo")
    submitted = files(task, candidate)
    chunks, changed = [], []
    for name in sorted(set(baseline) | set(submitted)):
        before, after = baseline.get(name), submitted.get(name)
        if before == after:
            continue
        changed.append(name)
        previous = before.decode().splitlines(keepends=True) if before is not None else []
        current = after.decode().splitlines(keepends=True) if after is not None else []
        diff = list(difflib.unified_diff(previous, current, fromfile=f"a/{name}" if before is not None else "/dev/null", tofile=f"b/{name}" if after is not None else "/dev/null"))
        for line in diff:
            if not line.endswith("\n"):
                chunks.extend([line + "\n", "\\ No newline at end of file\n"])
            else:
                chunks.append(line)
    patch = "".join(chunks)
    (target / "submitted.patch").write_text(patch)
    hashes = {name: hashlib.sha256(content).hexdigest() for name, content in submitted.items()}
    (target / "submitted-source-sha256.json").write_text(json.dumps(hashes, indent=2) + "\n")
    return {"changed_production_files": changed, "patch_sha256": hashlib.sha256(patch.encode()).hexdigest(), "source_files": len(hashes)}


def collect(final):
    base = ROOT / "evidence" / "coding-agents"
    target_base = ROOT / "evidence" / "trials"
    target_base.mkdir(parents=True, exist_ok=True)
    records = []
    for episode_path in sorted(base.glob("*.episode.json")):
        specification = json.loads(episode_path.read_text())
        name = episode_path.name.removesuffix(".episode.json")
        trials = list((base / name).glob("*/result.json"))
        if not trials or "finished_at" not in specification:
            continue
        assert len(trials) == 1, name
        result_path = trials[0]
        trial = result_path.parent
        result = json.loads(result_path.read_text())
        output = target_base / name
        if output.exists():
            archived_episode = output / "episode.json"
            if not archived_episode.is_file() or json.loads(archived_episode.read_text()) != specification:
                raise ValueError(f"Episode {name} would overwrite a different archive; use a unique job name")
            archived_result = output / "harbor-result.json"
            if archived_result.is_file() and json.loads(archived_result.read_text()) != result:
                raise ValueError(f"Episode {name} has a different native result; refusing archive overwrite")
        output.mkdir(exist_ok=True)
        shutil.copyfile(episode_path, output / "episode.json")
        shutil.copyfile(result_path, output / "harbor-result.json")
        for source in (trial / "verifier").iterdir():
            if source.is_file():
                shutil.copyfile(source, output / source.name)
        trajectory = trial / "agent" / "trajectory.json"
        if trajectory.is_file():
            raw_trajectory = json.loads(trajectory.read_text())
            visible_steps = []
            for step in raw_trajectory.get("steps", []):
                if step.get("tool_calls") or step.get("observation"):
                    visible_steps.append({key: step[key] for key in ("step_id", "timestamp", "source", "tool_calls", "observation", "metrics") if key in step})
            trace = {"schema_version": raw_trajectory.get("schema_version"), "agent": raw_trajectory.get("agent"),
                     "steps": visible_steps, "final_metrics": raw_trajectory.get("final_metrics"),
                     "export_note": "Tool calls/results and metrics only. Reasoning and analysis text are omitted."}
            (output / "trajectory.json").write_text(json.dumps(trace, indent=2) + "\n")
        network = []
        for path in (trial / "artifacts" / "network-proxy").glob("*.jsonl"):
            shutil.copyfile(path, output / "network-connections.jsonl")
            network.extend(json.loads(line) for line in path.read_text().splitlines())
        allowed = sorted({item["host"] for item in network if item["decision"] == "allow"})
        denied = sorted({item["host"] for item in network if item["decision"] == "deny"})
        candidate = trial / "artifacts" / "app" / "repo"
        boundary = json.loads((candidate / ".network-boundary.json").read_text())
        (output / "network-boundary.json").write_text(json.dumps(boundary, indent=2) + "\n")
        metadata = patch_and_hashes(specification["task"], candidate, output)
        metrics = json.loads((output / "results.json").read_text()) if (output / "results.json").exists() else {}
        rewards = (result.get("verifier_result") or {}).get("rewards", {})
        exception = result.get("exception_info")
        reward = rewards.get("reward")
        timed_out = exception is not None and exception.get("exception_type") == "AgentTimeoutError"
        status = "TIMEOUT" if timed_out and reward in {0, 1} else "PASS" if reward == 1 and exception is None else "FAIL" if reward == 0 and exception is None else "EXCEPTION"
        record = {"id": name, "task": specification["task"], "profile": specification["profile"],
                  "model": specification["model"], "reasoning": specification["reasoning"],
                  "agent_timeout_seconds": specification["agent_timeout_seconds"], "reward": reward, "status": status,
                  "exception": exception, "task_unchanged_during_trial": specification.get("task_unchanged_during_trial"),
                  "budget_exhausted": timed_out, "cutoff_artifact_passed": reward == 1,
                  "checks": {key: metrics.get(key) for key in ("tests_run", "passed", "failed", "skipped")},
                  "allowed_network_hosts": allowed, "denied_network_hosts": denied, "network_boundary": boundary, **metadata}
        assert boundary == {"github_proxy_denied": True, "direct_internet_blocked": True}, name
        assert network and "github.com" in denied and any(host.endswith("chatgpt.com") for host in allowed), name
        assert specification.get("task_unchanged_during_trial") is True, name
        task_folder = ROOT / "tasks" / specification["task"]
        checked = {path: digest for path, digest in specification["task_fingerprint"].items() if path != "provenance.json"}
        revised = {}
        revision_path = ROOT / "FAIRNESS_REVISION.json"
        if specification["task"] == "better-auth-indexes" and revision_path.exists():
            revision = json.loads(revision_path.read_text())
            if any(checked.get(item["path"]) == item["original_sha256"] for item in revision["changes"]):
                revised = {item["path"]: item for item in revision["changes"]}
                assert all(checked.get(path) == item["original_sha256"] for path, item in revised.items()), (name, "Mixed verifier revision")
        publication_path = ROOT / "PUBLICATION_METADATA.json"
        publication = json.loads(publication_path.read_text()) if publication_path.exists() else {}
        metadata_changes = {item["path"]: item for item in publication.get("task_configuration_changes", [])}
        for path, digest in checked.items():
            actual_digest = hashlib.sha256((task_folder / path).read_bytes()).hexdigest()
            if actual_digest != digest:
                publication_name = "tasks/" + specification["task"] + "/" + path
                if path == "task.toml" and publication_name in metadata_changes:
                    item = metadata_changes[publication_name]
                    assert item["original_sha256"] == digest and item["published_sha256"] == actual_digest
                    assert set(item["changed_fields"]) <= {"source", "task.authors"}
                    contract = tomllib.loads((task_folder / path).read_text())
                    contract.pop("source", None)
                    contract.get("task", {}).pop("authors", None)
                    assert hashlib.sha256(json.dumps(contract, sort_keys=True).encode()).hexdigest() == item["execution_contract_sha256"]
                    continue
                assert path in revised and revised[path]["original_sha256"] == digest and revised[path]["corrected_sha256"] == actual_digest, (name, path)
        record["public_instruction_matches_trial"] = True
        record["verifier_fairness_revision"] = revision["id"] if revised else None
        record["original_reward"] = record["reward"]
        record["original_checks"] = dict(record["checks"])
        corrected = ROOT / "evidence" / "rescored" / name
        if revised and (corrected / "results.json").is_file():
            replay = json.loads((corrected / "replay.json").read_text())
            assert replay["trial"] == name and replay["fairness_revision"] == revision["id"], (name, "Rescore revision mismatch")
            assert replay["patch_sha256"] == metadata["patch_sha256"] and replay["source_hashes_verified"], (name, "Rescore patch mismatch")
            corrected_metrics = json.loads((corrected / "results.json").read_text())
            assert {case["name"] for case in metrics["cases"]} == {case["name"] for case in corrected_metrics["cases"]}, (name, "Rescore cases changed")
            record["reward"] = float((corrected / "reward.txt").read_text().strip())
            record["checks"] = {key: corrected_metrics.get(key) for key in ("tests_run", "passed", "failed", "skipped")}
            record["cutoff_artifact_passed"] = record["reward"] == 1
            if not record["budget_exhausted"]:
                record["status"] = "PASS" if record["reward"] == 1 else "FAIL"
            shutil.copyfile(corrected / "results.json", output / "corrected-results.json")
            record["fairness_rescored"] = True
        else:
            record["fairness_rescored"] = False
        (output / "summary.json").write_text(json.dumps(record, indent=2) + "\n")
        records.append(record)
    if final:
        expected = {(task, profile) for task in SCOPES for profile in ("standard", "extended")}
        assert {(record["task"], record["profile"]) for record in records} == expected
        assert all(record["status"] != "EXCEPTION" for record in records), "Classify and resolve infrastructure exceptions before finalizing"
        assert all(record["fairness_rescored"] for record in records if record["verifier_fairness_revision"] is not None), "Rescore affected original-verifier submissions with the corrected verifier"
    report = {"trials": records, "completed": len(records), "passed": sum(row["status"] == "PASS" for row in records),
              "normally_finished": sum(row["exception"] is None for row in records),
              "passing_saved_artifacts": sum(row["cutoff_artifact_passed"] for row in records),
              "failed": sum(row["status"] == "FAIL" for row in records), "exceptions": sum(row["status"] == "EXCEPTION" for row in records),
              "budget_exhaustions": sum(row["status"] == "TIMEOUT" for row in records),
              "interpretation": "Two fresh same-model-family budget profiles per task. Exploratory usability checks, not a statistical difficulty estimate or a contamination-free claim."}
    (ROOT / "evidence" / "trial-summary.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({key: report[key] for key in ("completed", "passed", "failed", "budget_exhaustions", "exceptions")}))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Collect auditable patches, source hashes and network evidence from completed native trials.")
    parser.add_argument("--final", action="store_true")
    collect(parser.parse_args().final)
