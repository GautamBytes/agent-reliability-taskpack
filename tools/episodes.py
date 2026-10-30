import argparse
from datetime import datetime, timezone
import json
import hashlib
import os
from pathlib import Path
import shutil
import subprocess


ROOT = Path(__file__).resolve().parents[1]
PROFILES = {"standard": {"reasoning": "medium", "agent_timeout_multiplier": "0.5", "seconds": 300},
            "extended": {"reasoning": "high", "agent_timeout_multiplier": "1", "seconds": 600}}


def fingerprint(folder):
    values = {}
    for path in [folder / "instruction.md", folder / "task.toml", folder / "provenance.json", *sorted((folder / "tests").rglob("*"))]:
        if path.is_file() and not any(part in {"__pycache__", ".pytest_cache", "node_modules", "baseline"} for part in path.relative_to(folder).parts):
            values[path.relative_to(folder).as_posix()] = hashlib.sha256(path.read_bytes()).hexdigest()
    return values


def main():
    parser = argparse.ArgumentParser(description="Run a fresh native Harbor coding-agent attempt with recorded budgets.")
    parser.add_argument("task", choices=("anyio-cancel-scope", "better-auth-indexes", "werkzeug-multipart"))
    parser.add_argument("--profile", choices=PROFILES, required=True)
    parser.add_argument("--harbor", default=shutil.which("harbor"))
    parser.add_argument("--job-name")
    parser.add_argument("--output", type=Path, default=ROOT / "evidence" / "coding-agents")
    args = parser.parse_args()
    if not args.harbor:
        raise SystemExit("Install Harbor 0.25.0 or supply --harbor /absolute/path/to/harbor")
    profile = PROFILES[args.profile]
    name = args.job_name or f"{args.task}-{args.profile}"
    directory = args.output.resolve()
    directory.mkdir(parents=True, exist_ok=True)
    if (directory / name).exists():
        raise SystemExit("Choose a new job name. Existing trials must not be overwritten.")
    command = [args.harbor, "run", "-p", str(ROOT / "tasks" / args.task), "-a", "codex", "-m", "openai/gpt-6.1-sol",
               "--ak", f"reasoning_effort={profile['reasoning']}", "--ak", "web_search=disabled", "--ak", "version=0.166.0",
               "--agent-timeout-multiplier", profile["agent_timeout_multiplier"], "--ek", "auto_mounting=false",
               "-n", "1", "-r", "0", "-o", str(directory), "--job-name", name]
    record = {"task": args.task, "profile": args.profile, "model": "gpt-6.1-sol", "reasoning": profile["reasoning"],
              "agent_timeout_seconds": profile["seconds"], "codex_cli": "0.166.0", "harbor": "0.25.0",
              "started_at": datetime.now(timezone.utc).isoformat(), "command": command,
              "auth": "Existing ChatGPT login through native Harbor support; no credential content recorded",
              "web_search": "disabled", "solve_network": "internal Docker network with model/auth-only proxy",
              "attempt": 1, "private_feedback_provided_to_agent": False}
    record["task_fingerprint"] = fingerprint(ROOT / "tasks" / args.task)
    specification = directory / f"{name}.episode.json"
    specification.write_text(json.dumps(record, indent=2) + "\n")
    environment = dict(os.environ, CODEX_FORCE_AUTH_JSON="true")
    with (directory / f"{name}.console.log").open("w") as output:
        result = subprocess.run(command, env=environment, stdout=output, stderr=subprocess.STDOUT)
    record.update(finished_at=datetime.now(timezone.utc).isoformat(), process_exit_code=result.returncode)
    record["task_unchanged_during_trial"] = record["task_fingerprint"] == fingerprint(ROOT / "tasks" / args.task)
    specification.write_text(json.dumps(record, indent=2) + "\n")
    print(json.dumps({"task": args.task, "profile": args.profile, "exit_code": result.returncode, "job": str(directory / name)}))
    raise SystemExit(result.returncode)


if __name__ == "__main__":
    main()
