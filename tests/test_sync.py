import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

SCRIPT = Path(__file__).resolve().parents[1] / "scripts/sync_mattpocock.py"
spec = importlib.util.spec_from_file_location("sync_mattpocock", SCRIPT)
updater = importlib.util.module_from_spec(spec)
spec.loader.exec_module(updater)
REV1, REV2 = "1" * 40, "2" * 40
LICENSE = b"MIT License\nCopyright fixture\nPermission is hereby granted\n\xff\n"


class SyncTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="skills-test-")
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.source = self.base / "source"
        self.root = self.base / "target"
        self.root.mkdir()
        (self.source / ".claude-plugin").mkdir(parents=True)
        (self.source / "LICENSE").write_bytes(LICENSE)
        self.add_skill("alpha")
        self.manifest(["./skills/engineering/alpha"])

    def add_skill(self, name, category="engineering", content=None):
        # Synthetic upstream fixtures. The real npm CLI requires valid frontmatter.
        if content is None:
            content = f"---\nname: {name}\ndescription: Synthetic test skill\n---\nOriginal\n".encode()
        dest = self.source / "skills" / category / name
        dest.mkdir(parents=True, exist_ok=True)
        (dest / "SKILL.md").write_bytes(content)
        (dest / "nested").mkdir(exist_ok=True)
        (dest / "nested/asset.bin").write_bytes(b"\x00\xff\r\n")
        return dest

    def manifest(self, paths):
        (self.source / updater.MANIFEST).write_text(json.dumps({"skills": paths}))

    def sync(self, revision=REV1):
        return updater.sync(self.source, self.root, revision)

    def snapshot(self):
        return {p.relative_to(self.root).as_posix(): p.read_bytes()
                for p in self.root.rglob("*") if p.is_file()}

    def assert_failed_unchanged(self, action):
        before = self.snapshot()
        with self.assertRaises((updater.SyncError, OSError, ValueError)):
            action()
        self.assertEqual(before, self.snapshot())

    def test_uses_official_cli_lock_with_portable_upstream_sources(self):
        self.sync()
        lock = json.loads((self.root / "third_party/mattpocock/skills-lock.json").read_text())
        self.assertEqual(lock["version"], 1)
        self.assertEqual(set(lock["skills"]), {"alpha"})
        self.assertEqual(lock["skills"]["alpha"]["source"], "./skills/engineering/alpha")
        self.assertEqual(lock["skills"]["alpha"]["sourceType"], "local")
        self.assertRegex(lock["skills"]["alpha"]["computedHash"], r"^[0-9a-f]{64}$")
        self.assertNotIn(str(self.base), json.dumps(lock))

    def test_add_update_remove_and_unpromoted_exclusion(self):
        self.add_skill("unpublished", "experimental")
        self.add_skill("also-unpublished")
        self.assertTrue(self.sync())
        dest = self.root / "skills/mattpocock"
        self.assertEqual([p.name for p in dest.iterdir()], ["alpha"])
        local = self.root / "skills/local/README.md"
        local.parent.mkdir()
        local.write_text("keep me")
        self.add_skill("beta", "productivity")
        updated = b"---\r\nname: alpha\r\ndescription: Updated synthetic skill\r\n---\r\nUpdated\r\n"
        (self.source / "skills/engineering/alpha/SKILL.md").write_bytes(updated)
        self.manifest(["./skills/engineering/alpha", "./skills/productivity/beta"])
        self.assertTrue(self.sync(REV2))
        self.assertEqual((dest / "alpha/SKILL.md").read_bytes(), updated)
        self.manifest(["./skills/productivity/beta"])
        self.assertTrue(self.sync(REV2))
        self.assertFalse((dest / "alpha").exists())
        self.assertTrue((dest / "beta/SKILL.md").exists())
        self.assertEqual(local.read_text(), "keep me")
        self.assertEqual(updater.validate(self.root)["skills"], 1)

    def test_unpublished_same_name_never_wins_discovery(self):
        for category in ("misc", "in-progress", "deprecated", "experimental"):
            self.add_skill("alpha", category, b"---\nname: alpha\ndescription: Not published\n---\nWrong copy\n")
        self.sync()
        self.assertIn(b"Original", (self.root / "skills/mattpocock/alpha/SKILL.md").read_bytes())
        self.assertEqual(updater.validate(self.root)["skills"], 1)

    def test_cli_failures_and_omitted_files_cannot_prune(self):
        self.sync()
        # The CLI intentionally skips metadata.json. Fail rather than silently lose bytes.
        omitted = self.source / "skills/engineering/alpha/metadata.json"
        omitted.write_text("{}")
        self.assert_failed_unchanged(self.sync)
        omitted.unlink()
        skill = self.source / "skills/engineering/alpha/SKILL.md"
        for invalid in (b"No frontmatter", b"---\nname: other\ndescription: Wrong name\n---\n"):
            skill.write_bytes(invalid)
            self.assert_failed_unchanged(self.sync)

    def test_local_added_and_deleted_support_files_are_refused(self):
        self.sync()
        path = self.root / "skills/mattpocock/alpha/nested/asset.bin"
        saved = path.read_bytes()
        path.unlink()
        self.assert_failed_unchanged(self.sync)
        path.write_bytes(saved)
        path.with_name("new.txt").write_text("local addition")
        self.assert_failed_unchanged(self.sync)

    def test_installer_gets_no_live_agent_environment_and_executes_no_skill_scripts(self):
        script = self.source / "skills/engineering/alpha/never-run.sh"
        sentinel = self.base / "executed"
        script.write_text(f"#!/bin/sh\ntouch '{sentinel}'\n")
        script.chmod(0o755)
        live = self.base / "live-home"
        live.mkdir()
        with mock.patch.dict(os.environ, {"HOME": str(live), "CODEX_HOME": str(live),
                                         "INSTALL_INTERNAL_SKILLS": "true"}):
            self.sync()
        self.assertFalse(sentinel.exists())
        self.assertEqual(list(live.iterdir()), [])
        self.assertEqual((self.root / "skills/mattpocock/alpha/never-run.sh").read_bytes(), script.read_bytes())

    def test_same_revision_is_noop_and_preserves_bytes_and_mtimes(self):
        self.sync()
        before = self.snapshot()
        mtimes = {p: p.stat().st_mtime_ns for p in self.root.rglob("*") if p.is_file()}
        self.assertFalse(self.sync())
        self.assertEqual(self.snapshot(), before)
        self.assertEqual(mtimes, {p: p.stat().st_mtime_ns for p in mtimes})
        self.assertEqual((self.root / "third_party/mattpocock/LICENSE").read_bytes(), LICENSE)
        self.assertEqual((self.root / "skills/mattpocock/alpha/nested/asset.bin").read_bytes(), b"\x00\xff\r\n")

    def test_empty_malformed_and_unexpected_manifests_fail_unchanged(self):
        self.sync()
        for value in [b"not json", b"{}", b'{"skills":[]}', b'{"skills":"all"}', b"[]",
                      b'{"skills": [], "skills": ["./skills/engineering/alpha"]}']:
            with self.subTest(value=value):
                (self.source / updater.MANIFEST).write_bytes(value)
                self.assert_failed_unchanged(self.sync)

    def test_invalid_paths_and_duplicate_names_fail_unchanged(self):
        self.sync()
        for paths in [["./skills/experimental/alpha"], ["skills/engineering/alpha"],
                      ["./skills/engineering/../alpha"], ["/skills/engineering/alpha"],
                      ["./skills/engineering/alpha/extra"], [3],
                      ["./skills/engineering/alpha", "./skills/productivity/alpha"],
                      ["./skills/engineering/alpha", "./skills/engineering/alpha"]]:
            with self.subTest(paths=paths):
                self.manifest(paths)
                self.assert_failed_unchanged(self.sync)

    def test_missing_skill_and_license_fail_unchanged(self):
        self.sync()
        skill = self.source / "skills/engineering/alpha/SKILL.md"
        original = skill.read_bytes()
        skill.unlink()
        self.assert_failed_unchanged(self.sync)
        skill.write_bytes(original)
        (self.source / "LICENSE").unlink()
        self.assert_failed_unchanged(self.sync)

    def test_symlink_files_directories_and_manifest_fail_unchanged(self):
        self.sync()
        for rel in ["skills/engineering/alpha/nested/link", "skills/engineering/alpha/link"]:
            path = self.source / rel
            path.symlink_to(self.source / "LICENSE")
            self.assert_failed_unchanged(self.sync)
            path.unlink()
        path = self.source / "skills/engineering/alpha/linked-directory"
        path.symlink_to(self.source / "skills", target_is_directory=True)
        self.assert_failed_unchanged(self.sync)
        path.unlink()
        manifest = self.source / updater.MANIFEST
        saved = manifest.read_bytes()
        manifest.unlink()
        (self.source / "saved.json").write_bytes(saved)
        manifest.symlink_to(self.source / "saved.json")
        self.assert_failed_unchanged(self.sync)

    def test_target_symlink_cannot_escape(self):
        outside = self.base / "outside"
        outside.mkdir()
        (outside / "keep").write_text("keep")
        (self.root / "skills").symlink_to(outside, target_is_directory=True)
        with self.assertRaises(updater.SyncError):
            self.sync()
        self.assertEqual((outside / "keep").read_text(), "keep")
        self.assertEqual({p.name for p in outside.iterdir()}, {"keep"})

    def test_local_modification_fails_without_overwrite(self):
        self.sync()
        (self.root / "skills/mattpocock/alpha/SKILL.md").write_text("local edit")
        self.assert_failed_unchanged(self.sync)

    def test_special_files_fail_unchanged(self):
        self.sync()
        os.mkfifo(self.source / "skills/engineering/alpha/pipe")
        self.assert_failed_unchanged(self.sync)

    def test_invalid_revisions_and_active_writer_fail_unchanged(self):
        self.sync()
        for revision in ["HEAD", "main", "a" * 39, "A" * 40, "../escape"]:
            with self.subTest(revision=revision):
                self.assert_failed_unchanged(lambda: self.sync(revision))
        guard = self.root / ".sync-in-progress"
        guard.mkdir()
        self.assert_failed_unchanged(self.sync)
        self.assertTrue(guard.is_dir())
        guard.rmdir()

    def test_failed_fetch_leaves_existing_tree_and_lock_unchanged(self):
        self.sync()
        # Run a CLI copy against this disposable destination, with a failing git executable.
        scripts = self.root / "scripts"
        scripts.mkdir()
        (scripts / SCRIPT.name).write_bytes(SCRIPT.read_bytes())
        bin_dir = self.base / "bin"
        bin_dir.mkdir()
        fake = bin_dir / "git"
        fake.write_text("#!/bin/sh\nexit 23\n")
        fake.chmod(0o755)
        before = self.snapshot()
        result = subprocess.run([sys.executable, str(scripts / SCRIPT.name)], capture_output=True,
                                env={**os.environ, "PATH": str(bin_dir)}, text=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("sync failed", result.stderr)
        self.assertEqual(before, self.snapshot())

    def test_install_error_rolls_back_all_targets(self):
        self.sync()
        before = self.snapshot()
        self.add_skill("beta")
        self.manifest(["./skills/engineering/beta"])
        replace = os.replace
        count = 0

        def fail_once(*args):
            nonlocal count
            count += 1
            if count == 4:
                raise OSError("injected install failure")
            return replace(*args)

        with mock.patch.object(updater.os, "replace", side_effect=fail_once):
            with self.assertRaises(OSError):
                self.sync(REV2)
        self.assertEqual(before, self.snapshot())
        updater.validate(self.root)

    def test_local_source_cli_and_offline_check(self):
        scripts = self.root / "scripts"
        scripts.mkdir()
        local_script = scripts / SCRIPT.name
        local_script.write_bytes(SCRIPT.read_bytes())
        env = {**os.environ, "SKILLS_CLI": str(updater.CLI)}
        result = subprocess.run([sys.executable, str(local_script), "--source", str(self.source),
                                 "--revision", REV1], capture_output=True, text=True, env=env)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)["status"], "updated")
        result = subprocess.run([sys.executable, str(local_script), "--check"], capture_output=True, text=True, env=env)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)["status"], "valid")


if __name__ == "__main__":
    unittest.main()
