#!/usr/bin/env python3
"""Select the published Matt manifest; delegate installation and hashes to npm skills."""
import argparse
from contextlib import contextmanager
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import stat
import subprocess
import tempfile

REPO = "https://github.com/mattpocock/skills"
MANIFEST = ".claude-plugin/plugin.json"
SELECTION = r"\./skills/(engineering|productivity)/([a-z0-9]+(?:-[a-z0-9]+)*)"
SHA = re.compile(r"[0-9a-f]{40}")
ROOT = Path(__file__).resolve().parents[1]
CLI = Path(os.environ.get("SKILLS_CLI", ROOT / "node_modules/skills/bin/cli.mjs"))
INSTALLER = {"package": "skills", "version": "1.7.4"}
MANAGED = ("skills/mattpocock", "third_party/mattpocock", "upstreams.lock.json")


class SyncError(ValueError):
    pass


def digest(data):
    return hashlib.sha256(data).hexdigest()


def safe_chain(root, relative):
    if not stat.S_ISDIR(root.lstat().st_mode):
        raise SyncError(f"Not a real directory: {root}")
    path = Path(relative)
    if path.is_absolute() or any(p == ".." or "\\" in p or any(ord(c) < 32 for c in p) for p in path.parts):
        raise SyncError(f"Invalid path: {relative}")
    current = root
    for part in path.parts:
        current /= part
        if current.is_symlink():
            raise SyncError(f"Symlink forbidden: {current}")
    return current


def regular(path):
    if not stat.S_ISREG(path.lstat().st_mode):
        raise SyncError(f"Not a regular file: {path}")
    return path.read_bytes()


def files(root):
    safe_chain(root, ".")
    result = {}
    for path in sorted(root.rglob("*")):
        relative = path.relative_to(root).as_posix()
        safe_chain(root, relative)
        if not path.is_dir():
            result[relative] = regular(path)
    return result


def parse_manifest(data):
    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise SyncError(f"Duplicate JSON key: {key}")
            result[key] = value
        return result
    obj = json.loads(data, object_pairs_hook=unique)
    selected = obj.get("skills") if isinstance(obj, dict) else None
    if not isinstance(selected, list) or not selected:
        raise SyncError("Manifest skills must be a nonempty explicit list")
    result = []
    for value in selected:
        match = re.fullmatch(SELECTION, value) if isinstance(value, str) else None
        if not match:
            raise SyncError(f"Unexpected published path: {value!r}")
        result.append((match[2], value[2:]))
    if len({name for name, _ in result}) != len(result):
        raise SyncError("Duplicate skill name")
    return sorted(result)


def run_cli(source, names, project):
    """Use only project-local copies, with no inherited agent homes or telemetry."""
    package = json.loads(regular(CLI.parent.parent / "package.json"))
    if package.get("name") != INSTALLER["package"] or package.get("version") != INSTALLER["version"]:
        raise SyncError("Run npm ci --ignore-scripts to install the pinned skills CLI")
    project.mkdir(parents=True, exist_ok=True)
    home = project / "home"
    home.mkdir(exist_ok=True)
    env = {"PATH": os.environ.get("PATH", ""), "HOME": str(home),
           "XDG_CONFIG_HOME": str(home / ".config"), "XDG_CACHE_HOME": str(home / ".cache"),
           "XDG_DATA_HOME": str(home / ".local/share"), "TMPDIR": str(home),
           "DISABLE_TELEMETRY": "1", "DO_NOT_TRACK": "1", "CI": "1", "NO_COLOR": "1"}
    result = subprocess.run(["node", str(CLI), "add", str(source), "--skill", *names,
                             "-a", "codex", "-y", "--copy"], cwd=project, env=env,
                            capture_output=True, text=True, timeout=180)
    if result.returncode:
        raise SyncError(f"skills CLI failed: {result.stderr}\n{result.stdout}")


def cli_lock(project, selected):
    """Keep CLI hashes; make local source paths relative to the pinned upstream."""
    lock = json.loads(regular(project / "skills-lock.json"))
    if lock.get("version") != 1 or set(lock["skills"]) != {name for name, _ in selected}:
        raise SyncError("CLI lock selection mismatch")
    for name, relative in selected:
        entry = lock["skills"][name]
        if entry.get("sourceType") != "local" or not re.fullmatch(r"[0-9a-f]{64}", entry.get("computedHash", "")):
            raise SyncError(f"Invalid CLI lock entry: {name}")
        entry["source"] = "./" + relative
    return lock


def write_json(path, data):
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def prepare(source, revision, stage):
    if not SHA.fullmatch(revision):
        raise SyncError("Revision must be a full lowercase 40-character commit SHA")
    raw = regular(safe_chain(source, MANIFEST))
    selected = parse_manifest(raw)
    license_data = regular(safe_chain(source, "LICENSE"))
    if b"MIT License" not in license_data or b"Permission is hereby granted" not in license_data:
        raise SyncError("Upstream MIT license missing or changed; human review required")
    # Validate the entire selection before invoking the installer or touching managed data.
    inventory = {name: files(safe_chain(source, relative)) for name, relative in selected}
    if any(not data.get("SKILL.md", b"").strip() for data in inventory.values()):
        raise SyncError("Missing or empty SKILL.md")
    project = stage / "cli"
    for name, relative in selected:
        # Exact subtrees avoid discovery of unpublished skills with the same frontmatter name.
        run_cli(source / relative, [name], project)
        if files(project / ".agents/skills" / name) != inventory[name]:
            raise SyncError(f"CLI did not preserve every upstream byte: {name}")
    lock = cli_lock(project, selected)
    dest = stage / "skills/mattpocock"
    dest.parent.mkdir(parents=True)
    shutil.move(project / ".agents/skills", dest)
    third_party = stage / "third_party/mattpocock"
    third_party.mkdir(parents=True)
    (third_party / "LICENSE").write_bytes(license_data)
    (third_party / "plugin.json").write_bytes(raw)
    write_json(third_party / "skills-lock.json", lock)
    write_json(stage / "upstreams.lock.json", {
        "schema_version": 2, "repository": REPO, "revision": revision, "installer": INSTALLER,
        "manifest_sha256": digest(raw), "license_sha256": digest(license_data)})


def validate(root):
    meta = json.loads(regular(safe_chain(root, "upstreams.lock.json")))
    if (meta.get("schema_version") != 2 or meta.get("repository") != REPO
            or not SHA.fullmatch(meta.get("revision", "")) or meta.get("installer") != INSTALLER):
        raise SyncError("Invalid provenance metadata")
    third = files(safe_chain(root, "third_party/mattpocock"))
    if set(third) != {"LICENSE", "plugin.json", "skills-lock.json"}:
        raise SyncError("Unexpected provenance files")
    selected = parse_manifest(third["plugin.json"])
    if digest(third["plugin.json"]) != meta["manifest_sha256"] or digest(third["LICENSE"]) != meta["license_sha256"]:
        raise SyncError("Provenance content mismatch")
    managed = safe_chain(root, "skills/mattpocock")
    if {p.name for p in managed.iterdir()} != {name for name, _ in selected}:
        raise SyncError("Managed skill set differs from manifest")
    original = files(managed)
    # Reinstall locally to obtain official CLI hashes, not a second hash implementation.
    with tempfile.TemporaryDirectory(prefix="skills-check-") as temp:
        project = Path(temp)
        run_cli(managed, [name for name, _ in selected], project)
        if files(project / ".agents/skills") != original or cli_lock(project, selected) != json.loads(third["skills-lock.json"]):
            raise SyncError("Managed content differs from CLI lock; refusing local edits")
    return {"revision": meta["revision"], "skills": len(selected), "files": len(original)}


@contextmanager
def exclusive(root):
    guard = root / ".sync-in-progress"
    try:
        guard.mkdir()
    except FileExistsError as exc:
        raise SyncError("Another sync is active or left a stale .sync-in-progress; inspect before removing") from exc
    try:
        yield
    finally:
        guard.rmdir()


def install(root, stage):
    # Validation precedes replacement. Restore all targets on ordinary installation errors.
    validate(stage)
    for rel in MANAGED:
        safe_chain(root, rel)
    if any((root / rel).exists() for rel in MANAGED):
        validate(root)
    def content(path):
        return files(path) if path.is_dir() else regular(path)
    if all((root / rel).exists() and content(root / rel) == content(stage / rel) for rel in MANAGED):
        return False
    backup = stage / "backup"
    backup.mkdir()
    moved, installed = [], []
    try:
        for i, rel in enumerate(MANAGED):
            target = root / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            if target.exists():
                os.replace(target, backup / str(i))
                moved.append((target, backup / str(i)))
            os.replace(stage / rel, target)
            installed.append(target)
    except BaseException:
        for target in reversed(installed):
            shutil.rmtree(target) if target.is_dir() else target.unlink()
        for target, saved in reversed(moved):
            os.replace(saved, target)
        raise
    return True


def sync(source, root, revision):
    with exclusive(root), tempfile.TemporaryDirectory(prefix="skills-stage-") as temp:
        stage = Path(temp)
        prepare(source, revision, stage)
        return install(root, stage)


def git(*args, cwd=None):
    return subprocess.run(["git", "-c", "core.hooksPath=/dev/null", *args], cwd=cwd,
                          check=True, capture_output=True, text=True, timeout=180).stdout.strip()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, help="trusted local checkout or synthetic fixture; never execute upstream code")
    parser.add_argument("--revision", help="full commit SHA; local fixture callers assert provenance")
    parser.add_argument("--check", action="store_true", help="validate using the installed CLI, without network")
    args = parser.parse_args()
    try:
        if args.check:
            if args.source or args.revision:
                raise SyncError("--check cannot be combined with source/revision")
            print(json.dumps({"status": "valid", **validate(ROOT)}, sort_keys=True))
            return
        if args.revision and not SHA.fullmatch(args.revision):
            raise SyncError("Revision must be a full lowercase 40-character commit SHA")
        if args.source:
            source = args.source.absolute()
            changed = sync(source, ROOT, args.revision or git("rev-parse", "HEAD", cwd=source))
        else:
            revision = args.revision or git("ls-remote", REPO + ".git", "HEAD").partition("\t")[0]
            if not SHA.fullmatch(revision):
                raise SyncError("Upstream HEAD did not resolve to a full commit SHA")
            with tempfile.TemporaryDirectory(prefix="mattpocock-upstream-") as temp:
                source = Path(temp) / "upstream"
                git("clone", "--no-checkout", "--depth", "1", REPO + ".git", str(source))
                git("fetch", "--depth", "1", "origin", revision, cwd=source)
                git("checkout", "--detach", revision, cwd=source)
                if git("rev-parse", "HEAD", cwd=source) != revision:
                    raise SyncError("Fetched revision mismatch")
                changed = sync(source, ROOT, revision)
        print(json.dumps({"status": "updated" if changed else "unchanged", **validate(ROOT)}, sort_keys=True))
    except (OSError, ValueError, KeyError, TypeError, subprocess.SubprocessError) as exc:
        parser.exit(1, f"sync failed: {exc}\n")


if __name__ == "__main__":
    main()
