import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import zipfile


ROOT = Path(__file__).resolve().parents[1]


def include(relative):
    if any(part in {".git", "__pycache__", ".pytest_cache", "node_modules", ".DS_Store"} for part in relative.parts) or relative.suffix == ".pyc":
        return False
    if relative.parts[:2] in {("evidence", "coding-agents"), ("evidence", "calibration")}:
        return False
    if relative.parts[:2] == ("evidence", "native-controls"):
        if len(relative.parts) < 4 or relative.parts[2] not in {"final-references", "final-baselines"}:
            return False
        return relative.name in {"result.json", "config.json"} or "verifier" in relative.parts
    return relative.name != "SHA256SUMS"


def main(destination, archive):
    subprocess.run([sys.executable, str(ROOT / "tools/report.py")], check=True, stdout=subprocess.DEVNULL)
    assert not destination.exists() and not archive.exists(), "Existing deliverables must not be overwritten"
    paths = [path for path in sorted(ROOT.rglob("*")) if path.is_file() and include(path.relative_to(ROOT))]
    assert not any(path.is_symlink() for path in paths), "Source symlinks need explicit review"
    destination.mkdir(parents=True)
    records = []
    for path in paths:
        relative = path.relative_to(ROOT)
        target = destination / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, target)
        records.append((hashlib.sha256(path.read_bytes()).hexdigest(), relative.as_posix()))
    (destination / "SHA256SUMS").write_text("".join(f"{digest}  {name}\n" for digest, name in records))
    subprocess.run([sys.executable, str(destination / "tools/report.py")], check=True, stdout=subprocess.DEVNULL)
    with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as output:
        for path in sorted(destination.rglob("*")):
            if path.is_file():
                output.write(path, destination.name + "/" + path.relative_to(destination).as_posix())
    with zipfile.ZipFile(archive) as output:
        assert output.testzip() is None
        for expected, name in records:
            assert hashlib.sha256(output.read(destination.name + "/" + name)).hexdigest() == expected, name
            assert hashlib.sha256((destination / name).read_bytes()).hexdigest() == expected, name
    answer = (destination / "APPLICATION_ANSWER.txt").read_text().rstrip()
    assert len(answer) <= 2000
    print(json.dumps({"folder": str(destination), "zip": str(archive), "zip_bytes": archive.stat().st_size,
                      "zip_sha256": hashlib.sha256(archive.read_bytes()).hexdigest(), "files_verified": len(records),
                      "answer_characters": len(answer)}, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Export and hash-check a curated task pack without raw duplicate workspaces or conversation files.")
    parser.add_argument("--destination", type=Path, required=True)
    parser.add_argument("--archive", type=Path, required=True)
    args = parser.parse_args()
    main(args.destination.expanduser().resolve(), args.archive.expanduser().resolve())
