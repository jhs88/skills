"""Offline tests for adapted imports, provenance, portable contracts, and update checking."""
from __future__ import annotations

import contextlib
import copy
import hashlib
import importlib.machinery
import importlib.util
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
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


checker = load('adapted_checker', ROOT / 'scripts/check_adapted_updates.py')
validator = load('adapted_validator', ROOT / 'scripts/validate_adaptations.py')
watch = load('adapted_pr_wait', ROOT / 'skills/tstack/babysit-pr/scripts/pr-wait')


class Packaging(unittest.TestCase):
    def test_complete_import_validation(self):
        self.assertEqual(validator.validate(), {'skills': 11, 'files': 14, 'adapted_files': 2, 'status': 'valid'})

    def test_source_and_output_provenance_are_separate(self):
        manifest = json.loads((ROOT / 'adaptations.lock.json').read_text())
        self.assertIn('dirty working tree', manifest['source']['state'])
        self.assertEqual(manifest['source']['head'], '39569d27e16029f16dff397acc1f2fbffeba1349')
        modified = {(s['name'], p) for s in manifest['skills'] for p in s['adapted_files']}
        self.assertEqual(modified, {('council', 'SKILL.md'), ('technical-writing', 'SKILL.md')})
        for item in manifest['skills']:
            self.assertEqual(set(item['source_files']), set(item['files']))
            for p in item['files']:
                if p not in item['adapted_files']:
                    self.assertEqual(item['source_files'][p], item['files'][p])

    def test_licenses_and_distinct_pstack_pins(self):
        manifest = json.loads((ROOT / 'adaptations.lock.json').read_text())
        pins = {s['name']: s['upstream_revision'] for s in manifest['skills'] if s['collection'] == 'pstack'}
        self.assertEqual(pins, {'technical-writing': 'bdf7aa355337897f167153e05069aca505dae17c',
                                'unslop': 'fd6dd6f7276956a532bb78a748a8d2818b6eb5f4'})
        for family, author in [('tstack', 'Theo Browne'), ('pstack', 'Lauren Tan')]:
            license_text = (ROOT / 'third_party' / family / 'LICENSE').read_text()
            self.assertIn('Copyright (c) 2026 ' + author, license_text)
            self.assertIn('Permission is hereby granted', license_text)
            self.assertTrue(license_text.rstrip().endswith('SOFTWARE.'))

    def test_reference_and_runtime_contracts(self):
        council = (ROOT / 'skills/tstack/council/SKILL.md').read_text()
        self.assertIn('existing configured GPT', council)
        self.assertIn('instead of substituting', council)
        self.assertNotIn('llamacpp', council)
        self.assertNotIn('CLIProxyAPI', council)
        self.assertIn('until all delegates are satisfied', council)
        self.assertIn('Budget end is not approval', (ROOT / 'skills/tstack/sol-loop/SKILL.md').read_text())
        self.assertIn('disable-model-invocation: true', (ROOT / 'skills/pstack/technical-writing/SKILL.md').read_text())

    def test_versionable_and_no_generated_imports(self):
        paths = list((ROOT / 'skills/tstack').rglob('*')) + list((ROOT / 'skills/pstack').rglob('*'))
        for path in paths:
            if path.is_file() and '__pycache__' not in path.parts:
                result = subprocess.run(['git', 'check-ignore', '--no-index', str(path)],
                                        cwd=ROOT, capture_output=True, text=True)
                self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        manifest = json.loads((ROOT / 'adaptations.lock.json').read_text())
        self.assertFalse(any('__pycache__' in p or p.endswith('.pyc') for s in manifest['skills'] for p in s['files']))

    def copied_root(self):
        temp = tempfile.TemporaryDirectory(prefix='adapted-validation-')
        self.addCleanup(temp.cleanup)
        root = Path(temp.name)
        for path in ['skills/tstack', 'skills/pstack', 'third_party/tstack', 'third_party/pstack']:
            shutil.copytree(ROOT / path, root / path, ignore=shutil.ignore_patterns('__pycache__'))
        shutil.copy2(ROOT / 'adaptations.lock.json', root / 'adaptations.lock.json')
        return root

    def test_changed_file_negative_control(self):
        root = self.copied_root()
        (root / 'skills/tstack/council/SKILL.md').write_text('changed')
        with self.assertRaisesRegex(ValueError, 'hashes/inventory'):
            validator.validate(root)

    def test_missing_support_negative_control(self):
        root = self.copied_root()
        (root / 'skills/tstack/babysit-pr/references/bot-triage.md').unlink()
        with self.assertRaisesRegex(ValueError, 'hashes/inventory'):
            validator.validate(root)

    def test_excluded_workflow_negative_control(self):
        root = self.copied_root()
        unwanted = root / 'skills/tstack/agent-gauntlet/SKILL.md'
        unwanted.parent.mkdir()
        unwanted.write_text('unwanted')
        with self.assertRaisesRegex(ValueError, 'discovery'):
            validator.validate(root)

    def test_readonly_weekly_workflow_contract(self):
        workflow = (ROOT / '.github/workflows/check-adapted-upstreams.yml').read_text()
        for expected in ['workflow_dispatch:', 'cron:', 'contents: read', 'persist-credentials: false',
                         'GITHUB_STEP_SUMMARY', 'exit "$status"']:
            self.assertIn(expected, workflow)
        for forbidden in ['contents: write', 'pull-requests: write', 'create-pull-request', 'npm ', 'pip install', 'gh issue']:
            self.assertNotIn(forbidden, workflow)
        self.assertIn('actions/checkout@11d5960a326750d5838078e36cf38b85af677262', workflow)


class Updates(unittest.TestCase):
    def setUp(self):
        self.spec = {'upstream': checker.SOURCES['tstack'][0], 'revision': 'a' * 40,
                     'skill_revisions': {}, 'prefix': 'skills/', 'license_path': 'LICENSE',
                     'license_sha256': '9' * 64,
                     'source_files': {'example/SKILL.md': '1' * 64, 'example/scripts/helper': '2' * 64}}
        self.current = copy.deepcopy(self.spec['source_files'])

    def report(self, current=None, head=None):
        return checker.compare(self.spec, head or 'a' * 40,
                               self.current if current is None else current, '9' * 64)

    def test_current(self):
        self.assertFalse(self.report()['updates_available'])

    def test_unrelated_revision_does_not_claim_skill_update(self):
        self.assertFalse(self.report(head='b' * 40)['updates_available'])

    def test_new_skill_and_support(self):
        self.current.update({'new/SKILL.md': '3' * 64, 'new/references/guide.md': '4' * 64})
        result = self.report()
        self.assertEqual(result['new_skills'], ['new'])
        self.assertEqual(len(result['added_files']), 2)

    def test_deleted_skill(self):
        result = self.report({'other/SKILL.md': '3' * 64})
        self.assertEqual(result['removed_skills'], ['example'])
        self.assertEqual(len(result['removed_files']), 2)

    def test_changed_support(self):
        self.current['example/scripts/helper'] = '4' * 64
        result = self.report()
        self.assertEqual(result['modified_skills'], ['example'])
        self.assertEqual(result['changed_files'], ['example/scripts/helper'])

    def test_added_deleted_support(self):
        del self.current['example/scripts/helper']
        self.current['example/references/new.md'] = '4' * 64
        result = self.report()
        self.assertEqual(result['modified_skills'], ['example'])
        self.assertEqual(result['removed_files'], ['example/scripts/helper'])
        self.assertEqual(result['added_files'], ['example/references/new.md'])

    def test_license_change(self):
        result = checker.compare(self.spec, 'a' * 40, self.current, '0' * 64)
        self.assertTrue(result['updates_available'])
        self.assertTrue(result['license_changed'])

    def test_invalid_manifest_before_network(self):
        for key, value in [('upstream', 'https://example.org'), ('revision', 'main'),
                           ('source_files', {}), ('prefix', '../'), ('skill_revisions', {'absent': 'a'*40})]:
            with self.subTest(key=key), patch.object(checker, 'git') as git:
                with self.assertRaises(ValueError):
                    checker.check_collection('tstack', {**self.spec, key: value})
                git.assert_not_called()

    def test_bad_paths_and_hashes(self):
        for path, value in [('../escape', '1'*64), ('/absolute', '1'*64),
                            ('a//b', '1'*64), ('a/../b', '1'*64), ('a/\ncontrol', '1'*64),
                            ('a/SKILL.md', 'invalid')]:
            bad = {**self.spec, 'source_files': {**self.current, path: value}}
            with self.assertRaises(ValueError):
                checker.validate_collection('tstack', bad)

    def test_empty_symlink_submodule_snapshots_fail(self):
        for tree in [b'', b'120000 blob abc\tskills/example/SKILL.md\0',
                     b'160000 commit abc\tskills/example\0']:
            with patch.object(checker, 'git', return_value=tree), self.assertRaises(ValueError):
                checker.snapshot(Path('.'), 'a'*40, 'skills/')

    def test_pinned_once_and_source_verified(self):
        calls = []
        def fake_git(repo, *args):
            calls.append(args)
            if args[0] == 'rev-parse':
                return ('b'*40 + '\n').encode()
            if args[0] == 'show':
                return b'license'
            if args[0] == 'diff':
                return b'skills/example/scripts/helper\0'
            return b''
        spec = {**self.spec, 'license_sha256': checker.digest(b'license')}
        before = copy.deepcopy(spec)
        with patch.object(checker, 'git', side_effect=fake_git), patch.object(checker, 'snapshot', return_value=self.current):
            result = checker.check_collection('tstack', spec)
        self.assertEqual(spec, before)
        self.assertEqual(result['main_revision'], 'b'*40)
        self.assertEqual(sum(args[0] == 'rev-parse' for args in calls), 1)
        self.assertIn(('fetch', '--quiet', '--no-tags', '--depth=1', spec['upstream'], 'refs/heads/main'), calls)

    def test_source_hash_mismatch_fails(self):
        with patch.object(checker, 'git', return_value=('a'*40+'\n').encode()), \
             patch.object(checker, 'snapshot', return_value={'other/SKILL.md': '0'*64}), \
             self.assertRaisesRegex(ValueError, 'hashes/inventory'):
            checker.check_collection('tstack', self.spec)

    def test_distinct_pin_reconciliation(self):
        spec = {**self.spec, 'skill_revisions': {'example': 'c'*40}, 'license_sha256': checker.digest(b'license')}
        base = {**self.current, 'example/SKILL.md': '5'*64}
        def fake_git(repo, *args):
            if args[0] == 'rev-parse': return ('b'*40+'\n').encode()
            if args[0] == 'show': return b'license'
            return b''
        with patch.object(checker, 'git', side_effect=fake_git), \
             patch.object(checker, 'snapshot', side_effect=[base, self.current, self.current]) as snapshot:
            result = checker.check_collection('tstack', spec)
        self.assertFalse(result['updates_available'])
        self.assertEqual([c.args[1] for c in snapshot.call_args_list], ['a'*40, 'c'*40, 'b'*40])

    def test_cli_statuses_and_failure_precedence(self):
        for updates, errors, expected in [(False, {}, 0), (True, {}, 1),
                                          (True, {'pstack': 'network failed'}, 2)]:
            report = {'collections': {}, 'errors': errors, 'updates_available': updates,
                      'status': 'check_failed' if errors else 'complete'}
            output = io.StringIO()
            with patch.object(checker, 'check', return_value=report), contextlib.redirect_stdout(output):
                result = checker.main(['--json'])
            self.assertEqual(result, expected)
            self.assertEqual(json.loads(output.getvalue()), report)

    def test_partial_network_failure_keeps_other_report(self):
        manifest = json.loads((ROOT / 'adaptations.lock.json').read_text())
        with patch.object(checker, 'check_collection', side_effect=[self.report(), RuntimeError('network unavailable')]):
            result = checker.check(manifest)
        self.assertIn('tstack', result['collections'])
        self.assertIn('pstack', result['errors'])
        self.assertEqual(result['status'], 'check_failed')

    def test_cli_malformed_manifest_is_failure(self):
        with tempfile.TemporaryDirectory(prefix='adapted-bad-') as d:
            path = Path(d) / 'bad.json'
            for value in ['[]', '{}', 'not json', '{"schema_version":1,"collections":[]}']:
                path.write_text(value)
                with contextlib.redirect_stdout(io.StringIO()):
                    self.assertEqual(checker.main(['--manifest', str(path), '--json']), 2)

    def test_failed_check_preserves_local_imports_and_locks(self):
        paths = [ROOT / 'adaptations.lock.json']
        paths += [p for family in ['tstack', 'pstack'] for p in (ROOT / 'skills' / family).rglob('*')
                  if p.is_file() and '__pycache__' not in p.parts]
        before = {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}
        with patch.object(checker, 'git', side_effect=RuntimeError('network unavailable')), \
             contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(checker.main(['--json']), 2)
        self.assertEqual(before, {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in paths})

    def test_real_git_snapshot_without_network(self):
        with tempfile.TemporaryDirectory(prefix='adapted-git-fixture-') as d:
            repo = Path(d)
            git = lambda *args: subprocess.check_output(['git', '-C', d, *args], stderr=subprocess.STDOUT)
            git('init', '--quiet')
            (repo / 'skills/example/scripts').mkdir(parents=True)
            (repo / 'skills/example/SKILL.md').write_text('fixture skill')
            (repo / 'skills/example/scripts/helper').write_text('fixture helper')
            git('add', '.')
            git('-c', 'user.name=Fixture', '-c', 'user.email=fixture@example.invalid', 'commit', '--quiet', '-m', 'fixture')
            files = checker.snapshot(repo, 'HEAD', 'skills/')
            self.assertEqual(files, {'example/SKILL.md': checker.digest(b'fixture skill'),
                                     'example/scripts/helper': checker.digest(b'fixture helper')})


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
