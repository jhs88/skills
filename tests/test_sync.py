"""Command-level sync tests use disposable clean Git destinations and the pinned npm CLI."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
REV1, REV2 = '1' * 40, '2' * 40


class SyncTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory(prefix='skills-test-')
        self.addCleanup(temp.cleanup)
        self.base = Path(temp.name)
        self.source, self.target = self.base / 'source', self.base / 'target'
        self.target.mkdir()
        shutil.copytree(ROOT / 'scripts', self.target / 'scripts', ignore=shutil.ignore_patterns('__pycache__'))
        shutil.copy2(ROOT / 'sources.json', self.target / 'sources.json')
        shutil.copy2(ROOT / '.gitignore', self.target / '.gitignore')
        self.git('init', '--quiet')
        self.git('config', 'user.name', 'Fixture')
        self.git('config', 'user.email', 'fixture@example.invalid')
        self.commit()
        (self.source / '.claude-plugin').mkdir(parents=True)
        (self.source / 'LICENSE').write_text('MIT License\nPermission is hereby granted\n')
        self.add_skill('alpha')
        self.manifest(['./skills/engineering/alpha'])

    def git(self, *args):
        return subprocess.check_output(['git', '-C', str(self.target), *args], stderr=subprocess.STDOUT).decode()

    def commit(self):
        self.git('add', '.')
        self.git('commit', '--quiet', '--allow-empty', '-m', 'fixture')

    def add_skill(self, name, category='engineering', text='Original'):
        directory = self.source / 'skills' / category / name
        directory.mkdir(parents=True, exist_ok=True)
        (directory / 'SKILL.md').write_text(f'---\nname: {name}\ndescription: Synthetic fixture\n---\n{text}\n')
        (directory / 'asset.bin').write_bytes(b'\x00\xff\r\n')
        return directory

    def manifest(self, paths):
        (self.source / '.claude-plugin/plugin.json').write_text(json.dumps({'skills': paths}))

    def command(self, *args, env=None):
        return subprocess.run([sys.executable, str(self.target / 'scripts/sync_mattpocock.py'), *args],
                              capture_output=True, text=True,
                              env={**os.environ, 'SKILLS_CLI': str(ROOT / 'node_modules/skills/bin/cli.mjs'), **(env or {})})

    def sync(self, revision=REV1):
        return self.command('--source', str(self.source), '--revision', revision)

    def success(self, result):
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        return json.loads(result.stdout)

    def snapshot(self):
        return {str(p.relative_to(self.target)): (p.read_bytes(), p.stat().st_mode & 0o777)
                for p in self.target.rglob('*') if p.is_file() and '.git' not in p.parts
                and '__pycache__' not in p.parts}

    def test_manifest_records_pin_without_hash_locks(self):
        self.assertEqual(self.success(self.sync())['status'], 'updated')
        manifest = json.loads((self.target / 'sources.json').read_text())
        self.assertEqual(manifest['mattpocock']['revision'], REV1)
        self.assertFalse(list(self.target.glob('**/*lock.json')))
        self.assertEqual(self.success(self.command('--check'))['skills'], 1)


    def refused_unchanged(self, result, before):
        self.assertNotEqual(result.returncode, 0, result.stdout)
        self.assertIn('sync failed:', result.stderr)
        self.assertEqual(self.snapshot(), before)

    def test_add_update_delete_and_exclude_unpublished_duplicate(self):
        self.add_skill('alpha', 'experimental', 'Wrong copy')
        self.add_skill('alpha', 'deprecated', 'Wrong copy')
        self.add_skill('unlisted')
        self.success(self.sync())
        self.commit()
        self.add_skill('beta', 'productivity')
        self.add_skill('alpha', text='Updated')
        self.manifest(['./skills/engineering/alpha', './skills/productivity/beta'])
        self.success(self.sync(REV2))
        self.assertIn('Updated', (self.target / 'skills/mattpocock/alpha/SKILL.md').read_text())
        self.assertEqual({p.name for p in (self.target / 'skills/mattpocock').iterdir()}, {'alpha', 'beta'})
        self.commit()
        self.manifest(['./skills/productivity/beta'])
        self.success(self.sync(REV2))
        self.assertFalse((self.target / 'skills/mattpocock/alpha').exists())
        self.assertTrue((self.target / 'skills/mattpocock/beta/asset.bin').exists())

    def test_idempotence_bytes_modes_and_isolated_home(self):
        helper = self.source / 'skills/engineering/alpha/helper'
        sentinel = self.base / 'executed'
        helper.write_text(f'#!/bin/sh\ntouch "{sentinel}"\n')
        helper.chmod(0o755)
        live = self.base / 'live'
        live.mkdir()
        result = self.command('--source', str(self.source), '--revision', REV1,
                              env={'HOME': str(live), 'CODEX_HOME': str(live), 'INSTALL_INTERNAL_SKILLS': 'true'})
        self.success(result)
        self.assertFalse(sentinel.exists())
        self.assertEqual(list(live.iterdir()), [])
        installed = self.target / 'skills/mattpocock/alpha/helper'
        self.assertEqual(installed.read_bytes(), helper.read_bytes())
        self.assertEqual(installed.stat().st_mode & 0o777, 0o755)
        self.assertEqual((installed.parent / 'asset.bin').read_bytes(), b'\x00\xff\r\n')
        self.commit()
        before = self.snapshot()
        mtimes = {p: p.stat().st_mtime_ns for p in self.target.rglob('*') if p.is_file() and '.git' not in p.parts}
        self.assertEqual(self.success(self.sync())['status'], 'unchanged')
        self.assertEqual(self.snapshot(), before)
        self.assertEqual(mtimes, {p: p.stat().st_mtime_ns for p in mtimes})

    def test_failed_selection_never_prunes(self):
        self.success(self.sync())
        self.commit()
        before = self.snapshot()
        manifest = self.source / '.claude-plugin/plugin.json'
        for raw in ['not json', '[]', '{}', '{"skills":[]}', '{"skills":"all"}',
                    '{"skills":[],"skills":["./skills/engineering/alpha"]}',
                    '{"skills":["./skills/engineering/missing"]}',
                    '{"skills":["./skills/engineering/alpha","./skills/engineering/alpha"]}',
                    '{"skills":["./skills/experimental/alpha"]}',
                    '{"skills":["./skills/engineering/../alpha"]}']:
            with self.subTest(raw=raw):
                manifest.write_text(raw)
                self.refused_unchanged(self.sync(), before)
        self.manifest(['./skills/engineering/alpha'])
        (self.source / 'skills/engineering/alpha/SKILL.md').unlink()
        self.refused_unchanged(self.sync(), before)

    def test_cli_failure_or_omission_never_prunes(self):
        self.success(self.sync())
        self.commit()
        before = self.snapshot()
        # npm skills skips metadata.json; refuse this rather than drop upstream bytes.
        extra = self.source / 'skills/engineering/alpha/metadata.json'
        extra.write_text('{}')
        self.refused_unchanged(self.sync(), before)
        extra.unlink()
        fake = self.base / 'fake-cli/bin/cli.mjs'
        fake.parent.mkdir(parents=True)
        fake.write_text('process.exit(23)')
        (fake.parent.parent / 'package.json').write_text('{"name":"skills","version":"1.7.4"}')
        result = self.command('--source', str(self.source), '--revision', REV1, env={'SKILLS_CLI': str(fake)})
        self.refused_unchanged(result, before)

    def test_dirty_worktree_and_index_refuse_local_edits(self):
        self.success(self.sync())
        self.commit()
        path = self.target / 'skills/mattpocock/alpha/SKILL.md'
        path.write_text('local edit')
        before = self.snapshot()
        result = self.sync()
        self.assertIn('Dirty sync scope', result.stderr)
        self.refused_unchanged(result, before)
        self.git('add', '.')
        self.refused_unchanged(self.sync(), before)

    def test_dirty_support_addition_deletion_and_scoped_docs_protected(self):
        self.success(self.sync())
        self.commit()
        for relative in ['skills/mattpocock/alpha/new.txt', 'docs/new.md', 'scripts/local.py']:
            path = self.target / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text('local addition')
            self.refused_unchanged(self.sync(), self.snapshot())
            path.unlink()
        (self.target / 'skills/mattpocock/alpha/asset.bin').unlink()
        self.refused_unchanged(self.sync(), self.snapshot())

    def test_unrelated_collection_is_not_owned(self):
        self.success(self.sync())
        self.commit()
        other = self.target / 'skills/local/keep.md'
        other.parent.mkdir(parents=True)
        other.write_text('not owned by sync')
        self.assertEqual(self.success(self.sync())['status'], 'unchanged')
        self.assertEqual(other.read_text(), 'not owned by sync')

    def test_check_is_structural_and_needs_no_cli(self):
        self.success(self.sync())
        self.commit()
        skill = self.target / 'skills/mattpocock/alpha/SKILL.md'
        skill.write_text(skill.read_text() + '\nReviewed local wording\n')
        self.assertEqual(self.success(self.command('--check', env={'SKILLS_CLI': '/not-installed'}))['status'], 'valid')
        skill.write_text('No frontmatter')
        self.assertNotEqual(self.command('--check').returncode, 0)

    def test_bad_revision_license_symlink_and_special_file_preserve_output(self):
        self.success(self.sync())
        self.commit()
        before = self.snapshot()
        for revision in ['main', 'a' * 39, 'A' * 40]:
            self.refused_unchanged(self.sync(revision), before)
        license_file = self.source / 'LICENSE'
        saved = license_file.read_bytes()
        license_file.unlink()
        self.refused_unchanged(self.sync(), before)
        license_file.write_bytes(saved)
        link = self.source / 'skills/engineering/alpha/link'
        link.symlink_to(license_file)
        self.refused_unchanged(self.sync(), before)
        link.unlink()
        os.mkfifo(link)
        self.refused_unchanged(self.sync(), before)

    def test_source_manifest_and_license_paths_are_declarative(self):
        manifest = json.loads((self.target / 'sources.json').read_text())
        manifest['mattpocock'].update(manifest='publication.json', license='COPYING')
        (self.target / 'sources.json').write_text(json.dumps(manifest))
        (self.source / '.claude-plugin/plugin.json').rename(self.source / 'publication.json')
        (self.source / 'LICENSE').rename(self.source / 'COPYING')
        self.commit()
        self.assertEqual(self.success(self.sync())['status'], 'updated')

    def test_target_symlink_cannot_escape_owned_subtree(self):
        outside = self.base / 'outside'
        outside.mkdir()
        sentinel = outside / 'keep'
        sentinel.write_text('not owned')
        (self.target / 'skills').symlink_to(outside, target_is_directory=True)
        before = self.snapshot()
        self.refused_unchanged(self.sync(), before)
        self.assertEqual(sentinel.read_text(), 'not owned')
        self.assertEqual({p.name for p in outside.iterdir()}, {'keep'})

    def test_failed_fetch_preserves_output(self):
        sources = json.loads((self.target / 'sources.json').read_text())
        sources['mattpocock']['repository'] = str(self.base / 'missing')
        (self.target / 'sources.json').write_text(json.dumps(sources))
        self.commit()
        self.refused_unchanged(self.command('--revision', REV1), self.snapshot())


if __name__ == '__main__':
    unittest.main()
