import argparse
import json
from pathlib import Path
import shutil
import tomllib


ROOT = Path(__file__).resolve().parents[1]
TASKS = ("anyio-cancel-scope", "better-auth-indexes", "werkzeug-multipart")


def value(item):
    if isinstance(item, str):
        return json.dumps(item, ensure_ascii=False)
    if isinstance(item, bool):
        return "true" if item else "false"
    if isinstance(item, (int, float)):
        return str(item)
    if isinstance(item, list):
        return "[" + ", ".join(value(entry) for entry in item) + "]"
    if isinstance(item, dict):
        return "{ " + ", ".join(f"{json.dumps(key)} = {value(entry)}" for key, entry in item.items()) + " }"
    raise TypeError(type(item).__name__)


def write_toml(data):
    lines = []

    def section(table, path):
        if path:
            lines.extend(["", "[" + ".".join(path) + "]"])
        for key, item in table.items():
            if not isinstance(item, dict):
                lines.append(f"{key} = {value(item)}")
        for key, item in table.items():
            if isinstance(item, dict):
                section(item, [*path, key])

    section(data, [])
    result = "\n".join(lines) + "\n"
    assert tomllib.loads(result) == data
    return result


def configure(task_name):
    folder = ROOT / "tasks" / task_name
    config_path = folder / "task.toml"
    config = tomllib.loads(config_path.read_text())
    config["artifacts"] = [
        {"source": "/app/repo", "exclude": [".git", "node_modules", "**/node_modules", "__pycache__", "**/__pycache__", ".pytest_cache", ".hypothesis", ".pnpm-store"]},
        {"source": "/logs/proxy", "service": "model-egress", "destination": "network-proxy"},
    ]
    config["agent"]["timeout_sec"] = 600.0
    config["agent"]["user"] = "agent"
    config["verifier"]["environment_mode"] = "separate"
    config["verifier"]["user"] = "root"
    config["verifier"]["timeout_sec"] = max(config["verifier"].get("timeout_sec", 0), 300.0)
    for environment in (config["environment"], config["verifier"]["environment"]):
        environment["build_timeout_sec"] = 1200.0
        environment["cpus"] = 2
        environment["memory_mb"] = 3072 if task_name == "better-auth-indexes" else 1024
        environment["storage_mb"] = 8192 if task_name == "better-auth-indexes" else 2048
    config_path.write_text(write_toml(config))
    runtime = (ROOT / "runtime" / "Dockerfile").read_text().rstrip()
    for environment in ("environment", "tests"):
        dockerfile = folder / environment / "Dockerfile"
        content = dockerfile.read_text()
        lines = content.splitlines()
        if lines[0].strip() == "FROM oss-agent-base:20261030":
            content = runtime + "\n" + "\n".join(lines[1:]) + "\n"
        if environment == "environment" and "COPY network_probe.py /opt/network_probe.py" not in content:
            content += "COPY network_probe.py /opt/network_probe.py\n"
        dockerfile.write_text(content)
    shutil.copyfile(ROOT / "runtime" / "network_probe.py", folder / "environment" / "network_probe.py")
    shutil.copytree(ROOT / "runtime" / "proxy", folder / "environment" / "model_proxy", dirs_exist_ok=True)
    network = (ROOT / "runtime" / "agent-network.yaml").read_text().replace("../../../runtime/proxy", "./model_proxy")
    (folder / "environment" / "docker-compose.yaml").write_text(network)
    (folder / "tests" / "docker-compose.yaml").write_text("services:\n  main:\n    network_mode: none\n")
    print(f"Configured self-contained runtime, source artifacts and network boundary for {task_name}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Materialize native-agent runtime and isolation for one completed task.")
    parser.add_argument("task", choices=TASKS)
    configure(parser.parse_args().task)
