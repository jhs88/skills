#!/usr/bin/env python3
"""Vendor only the published upstream allowlist. Never execute upstream code."""
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
MANAGED = ("skills/mattpocock", "third_party/mattpocock", "upstreams.lock.json")


class SyncError(ValueError):
    pass


def digest(data):
    return hashlib.sha256(data).hexdigest()


def regular(path):
    if not stat.S_ISREG(path.lstat().st_mode):
        raise SyncError(f"Not a regular file: {path}")
    return path.read_bytes()


def directory(path):
    if not stat.S_ISDIR(path.lstat().st_mode):
        raise SyncError(f"Not a real directory: {path}")


def safe_chain(root, relative):
    directory(root)
    if Path(relative).is_absolute():
        raise SyncError(f"Absolute path forbidden: {relative}")
    current = root
    for part in Path(relative).parts:
        if part in ("", ".", "..") or "\\" in part or any(ord(c) < 32 for c in part):
            raise SyncError(f"Invalid path: {relative}")
        current /= part
        if current.is_symlink():
            raise SyncError(f"Symlink forbidden: {current}")
    return current


def files(root):
    directory(root)
    result = {}
    def fail_walk(error):
        raise error

    for base, dirs, names in os.walk(root, followlinks=False, onerror=fail_walk):
        for name in dirs + names:
            path = Path(base) / name
            rel = path.relative_to(root).as_posix()
            safe_chain(root, rel)
            if name in dirs:
                directory(path)
            else:
                result[rel] = regular(path)
    return dict(sorted(result.items()))


def parse_manifest(data):
    def unique_object(pairs):
        obj = {}
        for key, value in pairs:
            if key in obj:
                raise SyncError(f"Duplicate JSON key: {key}")
            obj[key] = value
        return obj

    try:
        obj = json.loads(data, object_pairs_hook=unique_object)
    except (ValueError, UnicodeError) as exc:
        raise SyncError(f"Malformed manifest: {exc}") from exc
    selected = obj.get("skills") if isinstance(obj, dict) else None
    if not isinstance(selected, list) or not selected:
        raise SyncError("Manifest skills must be a nonempty explicit list")
    result = []
    names = set()
    for value in selected:
        match = re.fullmatch(SELECTION, value) if isinstance(value, str) else None
        if not match:
            raise SyncError(f"Unexpected published path: {value!r}")
        name = match[2]
        if name in names:
            raise SyncError(f"Duplicate skill name: {name}")
        names.add(name)
        result.append((name, value[2:]))
    return sorted(result)


def tree_record(data):
    hashes = {name: digest(content) for name, content in sorted(data.items())}
    encoded = json.dumps(hashes, sort_keys=True, separators=(",", ":")).encode()
    return hashes, digest(encoded)


def prepare(source, revision, stage):
    if not SHA.fullmatch(revision):
        raise SyncError("Revision must be a full lowercase 40-character commit SHA")
    raw = regular(safe_chain(source, MANIFEST))
    selected = parse_manifest(raw)
    license_data = regular(safe_chain(source, "LICENSE"))
    if b"MIT License" not in license_data or b"Permission is hereby granted" not in license_data:
        raise SyncError("Upstream MIT license missing or changed; human review required")
    lock = {
        "schema_version": 1, "repository": REPO, "revision": revision,
        "manifest": {"path": MANIFEST, "sha256": digest(raw)},
        "selection": "explicit plugin manifest; engineering and productivity only",
        "license_sha256": digest(license_data), "skills": [],
    }
    for name, relative in selected:
        data = files(safe_chain(source, relative))
        if "SKILL.md" not in data or not data["SKILL.md"].strip():
            raise SyncError(f"Missing or empty SKILL.md: {relative}")
        dest = stage / "skills/mattpocock" / name
        dest.mkdir(parents=True)
        for rel, content in data.items():
            output = dest / rel
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_bytes(content)
        hashes, tree_hash = tree_record(data)
        lock["skills"].append({"name": name, "source": relative,
                               "files": hashes, "sha256": tree_hash})
    third_party = stage / "third_party/mattpocock"
    third_party.mkdir(parents=True)
    (third_party / "LICENSE").write_bytes(license_data)
    (third_party / "plugin.json").write_bytes(raw)
    (stage / "upstreams.lock.json").write_text(json.dumps(lock, indent=2) + "\n", encoding="utf-8")
    return lock


def validate(root):
    lock = json.loads(regular(safe_chain(root, "upstreams.lock.json")))
    if lock.get("schema_version") != 1 or lock.get("repository") != REPO or not SHA.fullmatch(lock.get("revision", "")):
        raise SyncError("Invalid lock metadata")
    third_party = safe_chain(root, "third_party/mattpocock")
    third_files = files(third_party)
    if set(third_files) != {"LICENSE", "plugin.json"}:
        raise SyncError("Unexpected provenance files")
    raw = third_files["plugin.json"]
    selected = parse_manifest(raw)
    if lock["manifest"] != {"path": MANIFEST, "sha256": digest(raw)}:
        raise SyncError("Manifest hash mismatch")
    if digest(third_files["LICENSE"]) != lock["license_sha256"]:
        raise SyncError("License hash mismatch")
    managed = safe_chain(root, "skills/mattpocock")
    directory(managed)
    if set(p.name for p in managed.iterdir()) != {name for name, _ in selected}:
        raise SyncError("Managed skill set differs from manifest")
    records = lock["skills"]
    if not isinstance(records, list) or [(r["name"], r["source"]) for r in records] != selected:
        raise SyncError("Lock selection mismatch")
    total = 0
    for entry in records:
        data = files(managed / entry["name"])
        if not data.get("SKILL.md", b"").strip():
            raise SyncError("Missing or empty SKILL.md")
        hashes, tree_hash = tree_record(data)
        if entry["files"] != hashes or entry["sha256"] != tree_hash:
            raise SyncError(f"Content mismatch: {entry['name']}")
        total += len(data)
    return {"revision": lock["revision"], "skills": len(records), "files": total}


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
    # All validation happens first. Roll back all managed targets on ordinary errors.
    validate(stage)
    for rel in MANAGED:
        safe_chain(root, rel)
    if any((root / rel).exists() for rel in MANAGED):
        validate(root)  # Refuse to overwrite local edits or incomplete managed state.
    changed = any(not (root / rel).exists() or
                  (files(root / rel) != files(stage / rel) if (stage / rel).is_dir()
                   else regular(root / rel) != regular(stage / rel)) for rel in MANAGED)
    if not changed:
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
            if target.is_dir():
                shutil.rmtree(target)
            else:
                target.unlink()
        for target, saved in reversed(moved):
            os.replace(saved, target)
        raise
    return True


def sync(source, root, revision):
    directory(root)
    with exclusive(root), tempfile.TemporaryDirectory(prefix=".sync-stage-", dir=root) as temp:
        stage = Path(temp)
        prepare(source, revision, stage)
        return install(root, stage)


def git(*args, cwd=None):
    return subprocess.run(["git", "-c", "core.hooksPath=/dev/null", *args], cwd=cwd,
                          check=True, capture_output=True, text=True, timeout=180).stdout.strip()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, help="read a trusted local checkout or fixture; no upstream code is executed")
    parser.add_argument("--revision", help="full commit SHA; local fixture callers assert provenance")
    parser.add_argument("--check", action="store_true", help="validate local lock and copied files without network")
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
            revision = args.revision or git("rev-parse", "HEAD", cwd=source)
            changed = sync(source, ROOT, revision)
        else:
            revision = args.revision or git("ls-remote", REPO + ".git", "HEAD").partition("\t")[0]
            if not SHA.fullmatch(revision):
                raise SyncError("Upstream HEAD did not resolve to a full commit SHA")
            # tempfile honors TMPDIR; fetch and detach one exact revision.
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
