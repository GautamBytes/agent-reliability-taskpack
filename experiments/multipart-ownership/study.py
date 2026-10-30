import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import difflib
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import tomllib
import uuid


ROOT = Path(__file__).resolve().parent
VERSIONS = ("before", "after")
MODEL = "gpt-6.1-sol"
DEFAULT_HARBOR = "/private/tmp/agent-taskpack-uv-cache/archive-v0/kvUjY28wjck_KvDqIdZt_/bin/harbor"


def now():
    return datetime.now(timezone.utc).isoformat()


def read(path):
    return json.loads(path.read_text())


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + "\n")


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def fingerprint(version):
    folder = ROOT / "versions" / version
    return {path.relative_to(folder).as_posix(): sha(path) for path in sorted(folder.rglob("*"))
            if path.is_file() and not any(part in {".git", "__pycache__", ".pytest_cache", "node_modules"} for part in path.relative_to(folder).parts)
            and path.suffix != ".pyc"}


def freeze():
    path = ROOT / "protocol.json"
    if path.exists():
        raise ValueError("A frozen protocol already exists; preserve it")
    configurations = {version: tomllib.loads((ROOT / "versions" / version / "task.toml").read_text()) for version in VERSIONS}
    assert all(config["agent"]["timeout_sec"] == 300 for config in configurations.values())
    assert all(config["environment"]["cpus"] == 2 and config["environment"]["memory_mb"] == 1024 for config in configurations.values())
    assert source_files(ROOT / "versions/before/environment/repo") == source_files(ROOT / "versions/after/environment/repo")
    gate = read(ROOT / "evidence/prefreeze-gate.json")
    assert gate["all_gates_passed"] and gate["counted_attempts_started"] == 0
    protocol = {"created_at": now(), "runner_sha256": sha(Path(__file__)), "replay_tool_sha256": sha(ROOT / "replay_study.py"),
                "contract_sha256": sha(ROOT / "CONTRACT.md"), "prefreeze_gate_sha256": sha(ROOT / "evidence/prefreeze-gate.json"),
                "source_basis_sha256": sha(ROOT / "evidence/source-basis.json"), "model": MODEL, "codex_cli": "0.166.0", "harbor": "0.25.0",
                "reasoning": "medium", "agent_timeout_seconds": 300, "attempts_per_version": 8,
                "public_pre_evaluation_anchor_required": True,
                "maximum_concurrent_attempts": 2, "order": [{"round": number, "attempts": [f"{version}-{number:02d}" for version in VERSIONS]} for number in range(1, 9)],
                "task_fingerprints": {version: fingerprint(version) for version in VERSIONS},
                "expected_case_names": {version: read(ROOT / "versions" / version / "tests/expected-cases.json") for version in VERSIONS},
                "primary_success": "Native agent completes normally within the configured 300-second solve phase and its verifier reward is 1 with complete per-case proof",
                "secondary_success": "Source collected by Harbor after the attempt has verifier reward 1, with timeouts separately reported; no atomic exact-cutoff filesystem snapshot is claimed",
                "run_policy": "One fresh container per attempt, no private feedback, no automatic Harbor episode retries, all planned runs retained, paired alternating conditions",
                "infrastructure_policy": "Infrastructure exceptions are retained and reported separately; they are not correctness failures or silent replacements",
                "interpretation": "Eight attempts per condition from one model family. Descriptive pilot, not a general accuracy, significance or contamination-free claim."}
    write(path, protocol)
    print(json.dumps({"protocol": str(path), "sha256": sha(path), "planned_attempts": 16}), flush=True)


def check_frozen(protocol):
    assert sha(Path(__file__)) == protocol["runner_sha256"], "Frozen runner changed"
    assert sha(ROOT / "replay_study.py") == protocol["replay_tool_sha256"], "Frozen replay tool changed"
    assert sha(ROOT / "CONTRACT.md") == protocol["contract_sha256"], "Frozen public contract changed"
    assert sha(ROOT / "evidence/prefreeze-gate.json") == protocol["prefreeze_gate_sha256"], "Frozen control gate changed"
    assert sha(ROOT / "evidence/source-basis.json") == protocol["source_basis_sha256"], "Frozen source basis changed"
    for name, digest in read(ROOT / "evidence/prefreeze-gate.json")["verified_files"].items():
        assert sha(ROOT / name) == digest, f"Frozen control evidence changed: {name}"
    for version in VERSIONS:
        assert fingerprint(version) == protocol["task_fingerprints"][version], f"Frozen task changed: {version}"


def source_files(repository):
    directory = repository / "src/werkzeug"
    assert directory.is_dir() and not directory.is_symlink(), str(directory)
    return {path.relative_to(repository).as_posix(): path.read_bytes() for path in sorted(directory.rglob("*"))
            if path.is_file() and not path.is_symlink() and "__pycache__" not in path.parts and path.suffix != ".pyc"}


def save_source(version, candidate, output):
    before = source_files(ROOT / "versions" / version / "environment/repo")
    after = source_files(candidate)
    patch = []
    changed = []
    for name in sorted(set(before) | set(after)):
        previous, current = before.get(name), after.get(name)
        if previous == current:
            continue
        changed.append(name)
        difference = difflib.unified_diff(previous.decode().splitlines(keepends=True) if previous is not None else [],
                                         current.decode().splitlines(keepends=True) if current is not None else [],
                                         fromfile=f"a/{name}" if previous is not None else "/dev/null",
                                         tofile=f"b/{name}" if current is not None else "/dev/null")
        for line in difference:
            patch.extend([line] if line.endswith("\n") else [line + "\n", "\\ No newline at end of file\n"])
    (output / "submitted.patch").write_text("".join(patch))
    write(output / "submitted-source-sha256.json", {name: hashlib.sha256(value).hexdigest() for name, value in after.items()})
    return {"patch_sha256": sha(output / "submitted.patch"), "changed_production_files": changed, "source_files": len(after)}


def collect(name, version, episode):
    job = ROOT / "runs/raw" / name
    paths = list(job.glob("*/result.json"))
    assert len(paths) == 1, (name, paths)
    trial = paths[0].parent
    native = read(paths[0])
    output = ROOT / "runs/curated" / name
    output.mkdir(parents=True, exist_ok=False)
    write(output / "episode.json", episode)
    shutil.copyfile(paths[0], output / "harbor-result.json")
    for path in (trial / "verifier").iterdir() if (trial / "verifier").is_dir() else []:
        if path.is_file():
            shutil.copyfile(path, output / path.name)
    exception = native.get("exception_info")
    reward = (native.get("verifier_result") or {}).get("rewards", {}).get("reward")
    kind = exception.get("exception_type") if exception else None
    infrastructure = {"EnvironmentBuildError", "EnvironmentStartError", "AgentSetupError", "VerifierSetupError", "EnvironmentNotFoundError", "AgentSetupTimeoutError", "EnvironmentStartTimeoutError"}
    status = "TIMEOUT" if kind == "AgentTimeoutError" else "VERIFIER_TIMEOUT" if kind == "VerifierTimeoutError" else "INFRASTRUCTURE_ERROR" if kind in infrastructure else "UNCLASSIFIED_EXCEPTION" if exception else "PASS" if reward == 1 else "FAIL" if reward == 0 else "UNSCORED"
    record = {"id": name, "version": version, "status": status, "native_reward": reward, "exception": exception,
              "completed_pass": exception is None and reward == 1, "saved_artifact_pass": reward == 1,
              "model": MODEL, "reasoning": "medium", "solve_deadline_seconds": 300,
              "started_at": episode["started_at"], "finished_at": episode["finished_at"],
              "task_unchanged": episode["task_unchanged"], "protocol_sha256": episode["protocol_sha256"]}
    metrics = read(output / "results.json") if (output / "results.json").is_file() else {}
    record["checks"] = {key: metrics.get(key) for key in ("tests_run", "passed", "failed", "skipped")}
    expected_names = read(ROOT / "protocol.json")["expected_case_names"][version]
    actual_cases = metrics.get("cases", [])
    record["case_evidence_complete"] = sorted(case["name"] for case in actual_cases) == sorted(expected_names) and metrics.get("tests_run") == len(expected_names)
    if reward == 1 and not (record["case_evidence_complete"] and metrics.get("passed") == len(expected_names) and metrics.get("failed") == 0 and metrics.get("skipped") == 0):
        record.update(status="EVIDENCE_ERROR", completed_pass=False, saved_artifact_pass=False)
    candidate = trial / "artifacts/app/repo"
    if (candidate / "src/werkzeug").is_dir():
        record.update(save_source(version, candidate, output))
        submitted_hashes = read(output / "submitted-source-sha256.json")
        verifier_hashes = {"src/werkzeug/" + key: value for key, value in metrics.get("source_hashes", {}).items()}
        record["verifier_source_matches_artifact"] = verifier_hashes == submitted_hashes
        if reward == 1 and not record["verifier_source_matches_artifact"]:
            record.update(status="EVIDENCE_ERROR", completed_pass=False, saved_artifact_pass=False)
        boundary = read(candidate / ".network-boundary.json")
        assert boundary == {"github_proxy_denied": True, "direct_internet_blocked": True}, name
        write(output / "network-boundary.json", boundary)
        network = []
        for path in (trial / "artifacts/network-proxy").glob("*.jsonl"):
            network.extend(json.loads(line) for line in path.read_text().splitlines())
        assert network, name
        (output / "network-connections.jsonl").write_text("".join(json.dumps(row) + "\n" for row in network))
        assert any(row["decision"] == "deny" and row["host"] == "github.com" for row in network), name
        assert any(row["decision"] == "allow" and row["host"].endswith("chatgpt.com") for row in network), name
    else:
        record.update(status="EVIDENCE_ERROR", completed_pass=False, saved_artifact_pass=False)
    trajectory = trial / "agent/trajectory.json"
    if trajectory.is_file():
        raw = read(trajectory)
        record["actual_agent"] = raw.get("agent")
        record["tool_call_steps"] = sum(bool(step.get("tool_calls")) for step in raw.get("steps", []))
        assert raw.get("agent", {}).get("model_name") == MODEL and raw.get("agent", {}).get("version") == "0.166.0", name
        write(output / "trajectory.json", {"schema_version": raw.get("schema_version"), "agent": raw.get("agent"),
              "steps": [{key: step[key] for key in ("step_id", "timestamp", "source", "tool_calls", "observation", "metrics") if key in step}
                        for step in raw.get("steps", []) if step.get("tool_calls") or step.get("observation")],
              "final_metrics": raw.get("final_metrics"), "export_note": "Tool calls, observations and metrics only; raw reasoning text omitted."})
    else:
        record.update(status="EVIDENCE_ERROR", completed_pass=False, saved_artifact_pass=False)
    write(output / "summary.json", record)
    print(json.dumps({key: record[key] for key in ("id", "status", "native_reward", "checks")}), flush=True)
    return record


def attempt(name, harbor, protocol):
    version = name.split("-", 1)[0]
    check_frozen(protocol)
    anchor = read(ROOT / "evidence/publication-anchor.json")
    assert anchor["protocol_sha256"] == sha(ROOT / "protocol.json") and anchor["github_protocol_bytes_verified"]
    directory = ROOT / "runs/raw"
    directory.mkdir(parents=True, exist_ok=True)
    assert not (directory / name).exists(), f"Existing native trial must not be overwritten: {name}"
    command = [harbor, "run", "-p", str(ROOT / "versions" / version), "-a", "codex", "-m", "openai/" + MODEL,
               "--ak", "reasoning_effort=medium", "--ak", "web_search=disabled", "--ak", "version=0.166.0",
               "--ek", "auto_mounting=false", "-n", "1", "-r", "0", "-o", str(directory), "--job-name", name]
    episode = {"id": name, "version": version, "started_at": now(), "command": command,
               "protocol_sha256": sha(ROOT / "protocol.json"), "task_fingerprint": protocol["task_fingerprints"][version],
               "public_anchor_sha256": sha(ROOT / "evidence/publication-anchor.json"),
               "private_feedback_provided": False, "auth": "Native Harbor support for existing authorized login; no credential contents recorded"}
    with (directory / (name + ".console.log")).open("w") as stream:
        result = subprocess.run(command, env=dict(os.environ, CODEX_FORCE_AUTH_JSON="true"), stdout=stream, stderr=subprocess.STDOUT)
    episode.update(finished_at=now(), process_exit_code=result.returncode, task_unchanged=fingerprint(version) == episode["task_fingerprint"])
    write(directory / (name + ".episode.json"), episode)
    assert episode["task_unchanged"], name
    return collect(name, version, episode)


def run_study(harbor):
    protocol = read(ROOT / "protocol.json")
    check_frozen(protocol)
    records = []
    for pair in protocol["order"]:
        print(json.dumps({"round": pair["round"], "starting": pair["attempts"]}), flush=True)
        with ThreadPoolExecutor(max_workers=2) as pool:
            jobs = [pool.submit(attempt, name, harbor, protocol) for name in pair["attempts"]]
            records.extend(job.result() for job in jobs)
        write(ROOT / "runs/progress.json", {"finished_at": now(), "attempts": records})
    check_frozen(protocol)
    report()


def report():
    protocol = read(ROOT / "protocol.json")
    check_frozen(protocol)
    rows = [read(path) for path in sorted((ROOT / "runs/curated").glob("*/summary.json"))]
    expected = {name for pair in protocol["order"] for name in pair["attempts"]}
    assert {row["id"] for row in rows} == expected and len(rows) == len(expected)
    assert all(row["protocol_sha256"] == sha(ROOT / "protocol.json") and row["task_unchanged"] for row in rows)
    summary = {}
    for version in VERSIONS:
        attempts = [row for row in rows if row["version"] == version]
        errors = [row for row in attempts if row["status"] not in {"PASS", "FAIL", "TIMEOUT"}]
        summary[version] = {"attempts": len(attempts), "completed_passes": sum(row["completed_pass"] for row in attempts),
                            "passing_saved_artifacts": sum(row["saved_artifact_pass"] for row in attempts),
                            "timeouts": sum(row["status"] == "TIMEOUT" for row in attempts), "unresolved_or_infrastructure_outcomes": len(errors),
                            "verifier_pass_rate": sum(row["saved_artifact_pass"] for row in attempts) / len(attempts) if not errors else None,
                            "completed_pass_rate": sum(row["completed_pass"] for row in attempts) / len(attempts) if not errors else None}
    write(ROOT / "runs/summary.json", {"reported_at": now(), "protocol_sha256": sha(ROOT / "protocol.json"), "model": MODEL,
                                       "versions": summary, "attempts": rows, "interpretation": protocol["interpretation"]})
    print(json.dumps(summary, indent=2), flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run a frozen matched ownership coding-task study without reusing old attempts.")
    parser.add_argument("command", choices=("freeze", "run", "report"))
    parser.add_argument("--harbor", default=shutil.which("harbor") or DEFAULT_HARBOR)
    arguments = parser.parse_args()
    if arguments.command == "freeze":
        freeze()
    elif arguments.command == "run":
        run_study(arguments.harbor)
    else:
        report()
