"""Public validation/checker commands and offline watcher behavior."""
import contextlib
import importlib.machinery
import importlib.util
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]


def load(name, path):
    loader = importlib.machinery.SourceFileLoader(name, str(path))
    spec = importlib.util.spec_from_loader(name, loader)
    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)
    return module


watch = load('adapted_pr_wait', ROOT / 'skills/tstack/babysit-pr/scripts/pr-wait')


def command(script, *args):
    return subprocess.run([sys.executable, str(ROOT / 'scripts' / script), *map(str, args)], capture_output=True, text=True)


class Packaging(unittest.TestCase):
    def copied_root(self):
        temp = tempfile.TemporaryDirectory(prefix='adapted-validation-')
        self.addCleanup(temp.cleanup)
        root = Path(temp.name)
        for path in ['skills/tstack', 'skills/pstack']:
            shutil.copytree(ROOT / path, root / path, ignore=shutil.ignore_patterns('__pycache__'))
        shutil.copy2(ROOT / 'sources.json', root / 'sources.json')
        shutil.copy2(ROOT / 'LICENSES.md', root / 'LICENSES.md')
        return root

    def test_complete_catalog(self):
        result = command('validate_adaptations.py')
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(json.loads(result.stdout), {'skills': 11, 'files': 14, 'status': 'valid'})


    def test_missing_support_invalid_frontmatter_and_extra_skill_fail(self):
        for defect in ('support', 'frontmatter', 'extra'):
            with self.subTest(defect=defect):
                root = self.copied_root()
                if defect == 'support':
                    (root / 'skills/tstack/babysit-pr/references/bot-triage.md').unlink()
                elif defect == 'frontmatter':
                    (root / 'skills/pstack/unslop/SKILL.md').write_text('not a skill')
                else:
                    (root / 'skills/pstack/unselected').mkdir()
                result = command('validate_adaptations.py', '--root', root)
                self.assertEqual(result.returncode, 2, result.stdout)

    def test_selection_comes_from_manifest(self):
        root = self.copied_root()
        manifest = json.loads((root / 'sources.json').read_text())
        manifest['pstack']['selected'].append('example')
        (root / 'sources.json').write_text(json.dumps(manifest))
        directory = root / 'skills/pstack/example'
        directory.mkdir()
        (directory / 'SKILL.md').write_text('---\nname: example\ndescription: Synthetic fixture\n---\n')
        result = command('validate_adaptations.py', '--root', root)
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertEqual(json.loads(result.stdout)['skills'], 12)

    def test_executable_support_mode_required(self):
        root = self.copied_root()
        (root / 'skills/tstack/babysit-pr/scripts/pr-wait').chmod(0o644)
        result = command('validate_adaptations.py', '--root', root)
        self.assertEqual(result.returncode, 2, result.stdout)
        self.assertIn('not executable', result.stdout)

    def test_root_notices_require_both_authors_and_mit_grant(self):
        for missing in ('Theo Browne', 'Lauren Tan', 'Permission is hereby granted', None):
            with self.subTest(missing=missing):
                root = self.copied_root()
                path = root / 'LICENSES.md'
                if missing is None:
                    path.unlink()
                else:
                    path.write_text(path.read_text().replace(missing, 'removed'))
                result = command('validate_adaptations.py', '--root', root)
                self.assertEqual(result.returncode, 2, result.stdout)
                self.assertIn('LICENSES.md', result.stdout)


class Updates(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory(prefix='adapted-upstream-')
        self.addCleanup(temp.cleanup)
        self.base = Path(temp.name)
        self.upstream = self.base / 'upstream'
        self.upstream.mkdir()
        self.git('init', '--quiet', '-b', 'main')
        self.git('config', 'user.name', 'Fixture')
        self.git('config', 'user.email', 'fixture@example.invalid')
        self.put('LICENSE', 'License baseline')
        self.put('skills/alpha/SKILL.md', 'alpha')
        self.put('skills/alpha/helper', 'helper baseline')
        self.put('skills/deleted/SKILL.md', 'delete me')
        self.baseline = self.commit()
        self.sources = json.loads((ROOT / 'sources.json').read_text())
        for spec in self.sources.values():
            if spec['mode'] == 'adapted':
                spec.update(repository=str(self.upstream), revision=self.baseline, path='skills', license='LICENSE', selected=['alpha'])
                spec.pop('skill_revisions', None)
        self.manifest = self.base / 'sources.json'

    def git(self, *args):
        return subprocess.check_output(['git', '-C', str(self.upstream), *args], stderr=subprocess.STDOUT).decode().strip()

    def put(self, relative, text):
        path = self.upstream / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)

    def commit(self):
        self.git('add', '.')
        self.git('commit', '--quiet', '--allow-empty', '-m', 'fixture')
        return self.git('rev-parse', 'HEAD')

    def check(self, expected):
        self.manifest.write_text(json.dumps(self.sources))
        before = self.manifest.read_bytes()
        result = command('check_adapted_updates.py', '--manifest', self.manifest, '--json')
        self.assertEqual(result.returncode, expected, result.stdout + result.stderr)
        self.assertEqual(self.manifest.read_bytes(), before)
        self.assertEqual(self.git('status', '--porcelain'), '')
        return json.loads(result.stdout)

    def test_current_and_unrelated_commits(self):
        self.assertFalse(self.check(0)['updates_available'])
        self.put('unrelated.txt', 'not a skill')
        self.commit()
        self.assertFalse(self.check(0)['updates_available'])

    def test_detects_skills_support_and_license_changes(self):
        self.put('skills/new/SKILL.md', 'new skill')
        self.put('skills/new/references/note.md', 'new support')
        shutil.rmtree(self.upstream / 'skills/deleted')
        self.put('skills/alpha/helper', 'changed helper')
        self.put('skills/alpha/new.md', 'added support')
        self.put('LICENSE', 'changed license')
        self.commit()
        report = self.check(1)['collections']['tstack']
        self.assertEqual(report['new_skills'], ['new'])
        self.assertEqual(report['removed_skills'], ['deleted'])
        self.assertEqual(report['modified_skills'], ['alpha'])
        self.assertEqual(report['changed_files'], ['alpha/helper'])
        self.assertIn('new/references/note.md', report['added_files'])
        self.assertEqual(report['removed_files'], ['deleted/SKILL.md'])
        self.assertTrue(report['license_changed'])

    def test_executable_mode_change_and_symlink_rejection(self):
        (self.upstream / 'skills/alpha/helper').chmod(0o755)
        self.commit()
        self.assertEqual(self.check(1)['collections']['tstack']['changed_files'], ['alpha/helper'])
        (self.upstream / 'skills/alpha/link').symlink_to('helper')
        self.commit()
        self.assertTrue(self.check(2)['errors'])

    def test_support_deletion(self):
        (self.upstream / 'skills/alpha/helper').unlink()
        self.commit()
        self.assertEqual(self.check(1)['collections']['pstack']['removed_files'], ['alpha/helper'])

    def test_override_pin_is_used_and_drift_is_reported(self):
        self.put('skills/alpha/helper', 'override content')
        alternate = self.commit()
        for spec in self.sources.values():
            if spec['mode'] == 'adapted':
                spec['skill_revisions'] = {'alpha': alternate}
        self.assertFalse(self.check(0)['updates_available'])
        self.put('skills/alpha/helper', 'drift after override')
        self.commit()
        self.assertEqual(self.check(1)['collections']['pstack']['changed_files'], ['alpha/helper'])

    def test_failure_precedes_updates_and_keeps_other_report(self):
        self.put('skills/alpha/helper', 'changed')
        self.commit()
        self.sources['pstack']['repository'] = str(self.base / 'missing')
        report = self.check(2)
        self.assertIn('tstack', report['collections'])
        self.assertIn('pstack', report['errors'])
        self.assertTrue(report['updates_available'])

    def test_bad_or_empty_current_inventory_fails(self):
        shutil.rmtree(self.upstream / 'skills')
        self.commit()
        self.assertTrue(self.check(2)['errors'])

    def test_bad_manifest_and_missing_pin_fail(self):
        self.sources['tstack']['revision'] = 'main'
        self.assertIn('manifest', self.check(2)['errors'])
        self.sources['tstack']['revision'] = 'a' * 40
        self.assertIn('tstack', self.check(2)['errors'])


class Watcher(unittest.TestCase):
    """Behavior cases adapted from Pi tests/test_tstack_skills.py, with no live GitHub calls."""
    def setUp(self):
        temp = tempfile.TemporaryDirectory(prefix='adapted-watch-')
        self.addCleanup(temp.cleanup)
        state = patch.object(watch, 'STATE_DIR', Path(temp.name))
        state.start()
        self.addCleanup(state.stop)

    def test_help_and_missing_input(self):
        path = ROOT / 'skills/tstack/babysit-pr/scripts/pr-wait'
        help_result = subprocess.run(['python3', str(path), '--help'], capture_output=True, text=True)
        self.assertEqual(help_result.returncode, 0)
        result = subprocess.run(['python3', str(path)], capture_output=True, text=True)
        self.assertEqual(result.returncode, 2)
        self.assertIn('missing PR number', result.stdout)

    def test_parse_and_invalid_target(self):
        with patch.object(watch, 'gh') as gh:
            self.assertEqual(watch.parse_target('https://github.com/owner/repo/pull/42', None), ('owner/repo', 42))
            gh.assert_called_once()
        with patch.object(watch, 'gh') as gh, contextlib.redirect_stdout(io.StringIO()):
            for raw in ['bad', '0', 'https://example.org/owner/repo/pull/2']:
                with self.assertRaises(SystemExit) as error:
                    watch.parse_target(raw, None)
                self.assertEqual(error.exception.code, 2)
            gh.assert_not_called()

    def test_duplicate_lock(self):
        handle = watch.lock('owner/repo', 42)
        self.addCleanup(handle.close)
        second = open(watch.STATE_DIR / 'owner__repo__42.lock', 'a+')
        self.addCleanup(second.close)
        with patch('builtins.open', return_value=second), contextlib.redirect_stdout(io.StringIO()), \
             self.assertRaises(SystemExit) as error:
            watch.lock('owner/repo', 42)
        self.assertEqual(error.exception.code, 2)

    def test_event_dedup_survives_restart(self):
        w = watch.Watcher('owner/repo', 42, 'any-change', 60)
        w.baseline = False
        with contextlib.redirect_stdout(io.StringIO()):
            w.emit('finding-1', 'new finding')
            w.save()
        resumed = watch.Watcher('owner/repo', 42, 'any-change', 60)
        with contextlib.redirect_stdout(io.StringIO()):
            resumed.emit('finding-1', 'new finding')
        self.assertEqual(resumed.events, 0)
        self.assertIn('finding-1', resumed.reported)

    def snapshot(self, state='OPEN'):
        return {'state': state, 'url': 'https://github.com/owner/repo/pull/42',
                'headRefOid': 'a'*40, 'baseRefName': 'main', 'author': {'login': 'author'},
                'viewer': 'viewer', 'comments': {'nodes': []}, 'reviews': {'nodes': []},
                'reviewThreads': {'nodes': []}, 'baseRef': {'target': {'oid': 'b'*40}},
                'mergeStateStatus': 'CLEAN'}

    def test_required_failure(self):
        w = watch.Watcher('owner/repo', 42, 'green', 60)
        w.required = {'test'}
        with patch.object(w, 'fetch_pr', return_value=self.snapshot()), \
             patch.object(w, 'fetch_checks', return_value={'test': {'bucket': 'fail', 'link': 'test-url'}}), \
             contextlib.redirect_stdout(io.StringIO()), self.assertRaises(SystemExit) as error:
            w.poll()
        self.assertEqual(error.exception.code, 1)

    def test_green_needs_stable_snapshot(self):
        w = watch.Watcher('owner/repo', 42, 'green', 60)
        w.required = {'test'}
        with patch.object(w, 'fetch_pr', return_value=self.snapshot()), \
             patch.object(w, 'fetch_checks', return_value={'test': {'bucket': 'pass', 'link': 'test-url'}}), \
             patch.object(w, 'behind', return_value=''), contextlib.redirect_stdout(io.StringIO()):
            w.poll()
            with self.assertRaises(SystemExit) as error:
                w.poll()
        self.assertEqual(error.exception.code, 0)

    def test_closed_vs_merged(self):
        for state, expected in [('CLOSED', 1), ('MERGED', 0)]:
            w = watch.Watcher('owner/repo', 42, 'green', 60)
            with patch.object(w, 'fetch_pr', return_value=self.snapshot(state)), \
                 contextlib.redirect_stdout(io.StringIO()), self.assertRaises(SystemExit) as error:
                w.poll()
            self.assertEqual(error.exception.code, expected)


if __name__ == '__main__':
    unittest.main()
